"""Approved quality experiment. Every paid action needs an explicit unique run id.

Uses the original ledger, preserves its first 19 records and never auto-retries.
This is not B's general-AI comparison tool or a production configuration.
"""
import argparse
import base64
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import time
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from app.config import Settings
from app.schemas.upload import InputDraft
from app.schemas.analysis import Cue
from app.services.copy_contract import CopyFailure
from app.services.copy_prompt import provider_payload
from app.services.copy_intensive import ExperimentRequest, IntensiveCopyExperiment, request_arguments, RATES
from app.services.copy_validation import validate_copy
from app.services.copy_quality import review_ad_copy

OUT = ROOT/'artifacts/ad-quality-intensive'
LEDGER = ROOT/'artifacts/copy-usage/ledger.json'
INITIAL_HASH = 'e7ad7fbfe406ae96237d4d9fbe1601ba6f2a837bda8a49c9cc072619de753446'


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def ledger():
    data = json.loads(LEDGER.read_text(encoding='utf-8'))
    return data, {'calls': len(data['calls']), 'cost': str(sum((Decimal(str(c['cost_ceiling_usd'])) for c in data['calls']), Decimal(0))), 'sha256': sha256(LEDGER.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'call'])
    p.add_argument('--id'); p.add_argument('--product', choices=['jjajang', 'espresso'], default='jjajang')
    p.add_argument('--goal', choices=['menu_promotion', 'store_visit', 'order'], default='menu_promotion')
    p.add_argument('--model', choices=list(RATES), default=list(RATES)[0])
    p.add_argument('--mode', choices=['single', 'pool', 'revise', 'select'], default='single')
    p.add_argument('--prior'); p.add_argument('--features')
    p.add_argument('--direction', choices=['baseline', 'editorial', 'campaign'], default='baseline')
    p.add_argument('--reasoning', choices=['none', 'low'], default='none')
    p.add_argument('--review-notes')
    p.add_argument('--photo-approved', action='store_true')
    p.add_argument('--execute-approved-paid-call', action='store_true')
    args = p.parse_args()
    if args.command == 'prepare':
        original, before = ledger()
        assert before['sha256'] == INITIAL_HASH and before['calls'] == 19 and Decimal(before['cost']) == Decimal('.03153750')
        OUT.mkdir(exist_ok=False)
        write(OUT/'initial-ledger.json', original)
        import openai
        settings = Settings()
        with openai.OpenAI(api_key=settings.openai_api_key.get_secret_value(), max_retries=0, timeout=30., base_url='https://api.openai.com/v1') as client:
            available = {model: client.models.retrieve(model).id == model for model in RATES}
        assert all(available.values())
        write(OUT/'authorization.json', {'initial': before, 'max_new_attempts': 150, 'total_call_limit': 169, 'cumulative_budget_usd': 5.,
             'rates': RATES, 'official_sources': ['https://developers.openai.com/api/docs/models/gpt-5.4-mini','https://developers.openai.com/api/docs/models/gpt-5.4'],
             'model_access_verified_by_free_get': available, 'automatic_retries': 0, 'service_limits_changed': False})
        print('Prepared: both model IDs accessible; original ledger19 unchanged; zero generation calls')
        return
    assert args.execute_approved_paid_call and args.id and args.id.replace('-', '').replace('_','').isalnum()
    initial = json.loads((OUT/'initial-ledger.json').read_text(encoding='utf-8'))['calls']
    current, before = ledger()
    assert current['calls'][:19] == initial and 19 <= before['calls'] < 169 and Decimal(before['cost']) < 5
    common = json.loads((ROOT/'artifacts/ad-quality-20261125/common-input.json').read_text(encoding='utf-8'))['cases']
    case = next(c for c in common if c['id'] == args.product)
    photo = ROOT/case['photo']
    assert photo.is_file() and sha256(photo.read_bytes()).hexdigest() == case['photo_sha256']
    draft = InputDraft.model_validate({**case['draft'], 'ad_goal': args.goal, 'photo_mode': 'cutout',
                                     **({'product_features': args.features} if args.features else {})})
    payload = provider_payload(draft, {'visual_hints': [Cue.model_validate(c) for c in case['analysis']['clip']['cues']]}, 'v8.1')
    prior = json.loads((OUT/args.prior/'raw.txt').read_text(encoding='utf-8')) if args.prior else None
    if args.mode == 'select' and prior and 'sets' in prior:
        eligible = []
        for item in prior['sets']:
            try:
                validate_copy(json.dumps(item, ensure_ascii=False), draft)
                eligible.append(item)
            except CopyFailure:
                pass  # Raw rejected sets remain in their original folder, never repaired.
        if not eligible: raise SystemExit('No fact-valid candidate set; no selection call')
        prior = {'sets': eligible}
    image_url = None; image_metadata = None
    if args.photo_approved:
        assert args.product == 'jjajang'  # Only this user-provided photo is authorized.
        from PIL import Image, ImageOps
        image = ImageOps.exif_transpose(Image.open(photo)).convert('RGB')
        image.thumbnail((768,768))
        buffer = io.BytesIO(); image.save(buffer, format='JPEG', quality=90)
        encoded = buffer.getvalue()
        image_url = 'data:image/jpeg;base64,'+base64.b64encode(encoded).decode()
        image_metadata = {'source_sha256': case['photo_sha256'], 'transmitted_sha256': sha256(encoded).hexdigest(),
                          'size': image.size, 'bytes': len(encoded), 'exif_removed': True, 'detail': 'low', 'user_approved': True}
    request = ExperimentRequest(payload, args.model, args.mode, prior, image_url, args.direction, args.reasoning, args.review_notes)
    arguments, bound = request_arguments(request)
    rates = RATES[args.model]
    reservation = (bound*rates[0]+arguments['max_output_tokens']*rates[2])/1e6
    assert Decimal(before['cost'])+Decimal(str(reservation)) <= 5
    folder = OUT/args.id; folder.mkdir(exist_ok=False)  # one-use marker before any dispatch
    write(folder/'plan.json', {'product': args.product, 'goal': args.goal, 'mode': args.mode, 'model': args.model,
          'direction': args.direction, 'draft': draft.model_dump(mode='json'), 'payload': payload, 'prior': args.prior, 'photo': case['photo'],
          'photo_sha256': case['photo_sha256'], 'analysis': case['analysis'], 'image': image_metadata,
          'input_token_ceiling': bound, 'reservation_usd': reservation, 'ledger_before': before})
    def capture(arguments, response):
        sanitized = json.loads(json.dumps(arguments))
        for part in sanitized['input'][0]['content']:
            if part['type'] == 'input_image': part['image_url'] = image_metadata
        write(folder/'request.json', sanitized)
        if response is None: return
        write(folder/'response.json', response.model_dump(mode='json'))
        (folder/'raw.txt').write_text(response.output_text or '', encoding='utf-8')
    import openai
    settings = Settings(); started = time.perf_counter()
    result = {'id': args.id, 'status': 'failed', 'automatic_retries': 0}
    with openai.OpenAI(api_key=settings.openai_api_key.get_secret_value(), base_url='https://api.openai.com/v1', timeout=90., max_retries=0) as client:
        try:
            reply = IntensiveCopyExperiment(LEDGER, client, approved=True).generate(request, capture)
            parsed = json.loads(reply.text)
            sets = parsed['sets'] if args.mode == 'pool' else [parsed]
            outcomes = []
            for i, item in enumerate(sets):
                try:
                    bound_copy = validate_copy(json.dumps(item, ensure_ascii=False), draft)
                    write(folder/f'bound-{i}.json', bound_copy.model_dump(mode='json', by_alias=True))
                    outcomes.append({'set': i, 'status': 'passed', 'warnings': review_ad_copy(bound_copy.variants, args.goal, profile='v8.1', draft=draft)})
                except CopyFailure as e:
                    outcomes.append({'set': i, 'status': 'failed', 'code': e.code, 'reason': e.reason})
            result.update(status='evaluated', sets=outcomes)
        except CopyFailure as e:
            result.update(error=e.code)
    result['seconds'] = time.perf_counter()-started
    current, after = ledger(); assert current['calls'][:19] == initial
    result.update(ledger_after=after, original_records_preserved=True)
    write(folder/'result.json', result)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()
