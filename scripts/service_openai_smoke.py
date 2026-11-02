"""One synthetic paid copy request only after separate explicit approval. Default: plan only."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--approved-paid-call',action='store_true')
    args=parser.parse_args()
    from app.services.copy_budget import MAX_COST
    if not args.execute:
        print(json.dumps({'mode':'plan_only','requests_max':1,'app_retries':0,'cost_ceiling_usd':MAX_COST,
            'note':'Separate user approval, paid gate, key and existing cumulative ledger are required.'}));return 0
    if not args.approved_paid_call:
        print('Not executed: explicit paid-call approval flag missing.');return 2
    from app.config import Settings
    from app.services.copy_provider import build_copy_provider
    from app.services.copy_prompt import provider_payload
    from app.services.copy_validation import validate_copy
    from app.services.copy_glyphs import supported_codepoints
    from app.schemas.upload import InputDraft
    from app.services.copy_contract import CopyFailure
    settings=Settings(copy_max_retries=0)
    if settings.copy_provider!='openai' or not settings.copy_allow_paid or not settings.openai_api_key:
        print('Not executed: OpenAI provider, paid gate and server key must be explicitly configured.');return 2
    draft=InputDraft.model_validate({'facts':{'store_name':'Synthetic shop','product_name':'Synthetic product','price_text':'3,000 KRW'},'mood':'warm'})
    provider=build_copy_provider(settings);usage=None
    try:
        supported_codepoints()
        reply=provider.generate(provider_payload(draft,None));usage=reply.usage
        validated=validate_copy(reply.text,draft)
        print(json.dumps({'status':'passed','strategies':[v.strategy for v in validated.variants],
            'distinct':len({v.ad_copy.model_dump_json() for v in validated.variants})==4,'usage':asdict(usage)},allow_nan=False))
        return 0
    except CopyFailure as error:
        usage=error.usage or usage
        print(json.dumps({'status':'failed','code':error.code,'usage':asdict(usage) if usage else None}));return 1
    except Exception:
        print(json.dumps({'status':'failed','code':'SMOKE_FAILED','usage':asdict(usage) if usage else None}));return 1
    finally:provider.close()


if __name__=='__main__':raise SystemExit(main())
