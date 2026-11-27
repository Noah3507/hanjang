"""Compare Hanjang with a general image AI (e.g. ChatGPT) on things that can be measured.

Answers the professor's question "is using our service better than asking a general AI?"
without people rating the ads. Everything here is a fixed rule, so the same images give
the same numbers.

Two steps, both run from the repository root inside the service .venv (it already has
OpenCV, scikit-image, Pillow and httpx). OCR uses the Tesseract program with Korean data
(Mac: brew install tesseract tesseract-lang).

1. make-hanjang: make our ad for every case through the local server, then change only the
   price, and save both PNGs plus the time each took. The local server must be running; with
   the mock copy provider no paid call is made. If the server would call OpenAI, the script
   stops unless --allow-paid is given (paid calls need team agreement).
     .venv/bin/python scripts/ml_compare_general_ai.py make-hanjang \
         --cases artifacts/compare/cases.csv --out artifacts/compare/hanjang
2. measure: read the cases and every system's results (ours from step 1, the general AI's
   typed into artifacts/compare/results-general.csv by hand) and write the report.
     .venv/bin/python scripts/ml_compare_general_ai.py measure \
         --cases artifacts/compare/cases.csv \
         --results artifacts/compare/hanjang/results-hanjang.csv \
         --results artifacts/compare/results-general.csv --out artifacts/compare/report
Photos and ads stay in artifacts/ (git-ignored); ml/compare/ holds only the empty forms.

What is measured, per ad (see ml/compare/README.md for the reasons):
  text      OCR finds the store name, product name and the exact price; any other price
            amount on the ad counts as a wrong price.
  claims    words from our copy validator's claim list (할인, 무료, 인기, 수제, 국내산, ...) and
            numbers such as 30%, 1위, 1+1 that the case's facts do not support.
  product   SIFT keypoints of the uploaded photo matched in the ad (RANSAC inliers). A redrawn
            product keeps few exact details, so its inlier count is low.
  edit      after "change only the price": share of pixels that changed outside the price
            area, structural similarity (SSIM) outside it, and whether the new price is there
            and the old one gone.
  time/cost from the results file.
OCR can misread stylised letters for either system; the raw OCR text is kept in the report
so a reader can check any case.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / 'templates' / 'fonts' / 'NotoSansKR-Regular.otf'
CASE_FIELDS = ['case_id', 'photo', 'store_name', 'product_name', 'price_text', 'new_price_text',
               'mood', 'ad_goal', 'product_features', 'strategy']
RESULT_FIELDS = ['case_id', 'system', 'ad_image', 'edited_image', 'make_seconds', 'edit_seconds',
                 'cost_usd', 'attempts', 'notes']
# Matched keypoints that mean "the uploaded photo itself is in the ad". Calibration on a
# sample photo: the same photo pasted only 200 px wide kept 73; blurred or repainted copies
# kept 17-39. So 50 separates "same photo" from "a drawing of it".
INLIER_PASS = 50


# ---------------------------------------------------------------- shared helpers

def read_csv(path: Path) -> list[dict]:
    with open(path, encoding='utf-8-sig', newline='') as f:
        return [{k: (v or '').strip() for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def resolve(path: str, base: Path) -> Path:
    p = Path(path).expanduser()
    return p if p.is_absolute() else (base / p)


def claim_pattern() -> re.Pattern:
    """The CLAIMS regex of our copy validator, read from its source so nothing is copied by hand."""
    source = (ROOT / 'backend' / 'app' / 'services' / 'copy_validation.py').read_text(encoding='utf-8')
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'CLAIMS' for t in node.targets):
            return re.compile(ast.literal_eval(node.value.args[0]))
    raise SystemExit('copy_validation.py has no CLAIMS pattern')


def compact(text: str) -> str:
    return re.sub(r'[\s··|]+', '', text)


def amount(text: str) -> int | None:
    digits = re.sub(r'\D', '', text)
    return int(digits) if digits else None


# ---------------------------------------------------------------- OCR

@dataclass
class Word:
    text: str
    box: tuple[int, int, int, int]  # left, top, right, bottom in the image's own pixels


def ocr(image: Image.Image) -> list[Word]:
    """Tesseract on the grey image and its inverse (light text on dark), in sparse-text and
    single-block modes. Each setting misses different words, so all words are kept."""
    if not shutil.which('tesseract'):
        raise SystemExit('Tesseract is not installed. Mac: brew install tesseract tesseract-lang')
    grey = ImageOps.grayscale(image.convert('RGB'))
    words: list[Word] = []
    with tempfile.TemporaryDirectory() as tmp:
        outputs = []
        for i, variant in enumerate((grey, ImageOps.invert(grey))):
            path = Path(tmp) / f'{i}.png'
            variant.save(path)
            for psm in ('11', '6'):
                outputs.append(subprocess.run(['tesseract', str(path), '-', '-l', 'kor+eng', '--psm', psm, 'tsv'],
                                              capture_output=True, text=True, check=True).stdout)
    for out in outputs:
        for line in out.splitlines()[1:]:
            cols = line.split('\t')
            if len(cols) < 12 or not cols[11].strip() or float(cols[10]) < 30:
                continue
            l, t, w, h = map(int, cols[6:10])
            words.append(Word(cols[11].strip(), (l, t, l + w, t + h)))
    return words


def ocr_text(words: list[Word]) -> str:
    return ' '.join(w.text for w in words)


def contains(words: list[Word], value: str) -> tuple[bool, float]:
    """Exact (spaces ignored) and the best similarity of any run of words to the value."""
    target = compact(value)
    if not target:
        return True, 1.0
    if target in compact(ocr_text(words)):
        return True, 1.0
    best = 0.0
    texts = [compact(w.text) for w in words]
    for i in range(len(texts)):
        run = ''
        for j in range(i, min(i + 6, len(texts))):
            run += texts[j]
            best = max(best, SequenceMatcher(None, target, run).ratio())
    return False, round(best, 3)


# A comma-grouped amount counts with or without 원 (OCR often misreads a bold 원 as "2!");
# plain digits count only when 원 follows.
PRICE_RE = re.compile(r'\d{1,3}(?:[,.]\d{3})+|\d{3,}(?=\s*원)')


def prices(words: list[Word]) -> set[int]:
    found = set()
    for text in {' '.join(w.text for w in words)} | {w.text for w in words}:
        found |= {int(re.sub(r'\D', '', m)) for m in PRICE_RE.findall(text)}
    return found


def has_price(words: list[Word], want: int | None) -> bool:
    """The expected amount is on the ad. Besides a clean read, accept a digit run that starts with
    the amount and has at most two extra characters, which is how OCR misreads a trailing 원
    ("25000원" -> "2500074"). Only used to confirm the right price, never to find wrong ones."""
    if want is None:
        return False
    if want in prices(words):
        return True
    digits = str(want)
    runs = re.findall(r'\d[\d,.]*', ' '.join(w.text for w in words))
    return len(digits) >= 3 and any((r := re.sub(r'\D', '', run)).startswith(digits) and len(r) - len(digits) <= 2 for run in runs)


def price_boxes(words: list[Word], price_text: str) -> list[tuple[int, int, int, int]]:
    """Words that are part of the written price: their digits are a piece of the price's digits."""
    digits = re.sub(r'\D', '', price_text)
    boxes = []
    for w in words:
        d = re.sub(r'\D', '', w.text)
        if len(d) >= 2 and d in digits or (len(digits) >= 4 and digits in d):
            boxes.append(w.box)
    return boxes


def claims(words: list[Word], case: dict, pattern: re.Pattern) -> list[str]:
    evidence = ' '.join(case.get(k, '') for k in ('store_name', 'product_name', 'price_text', 'product_features'))
    text = compact(ocr_text(words))
    found = [m.group() for m in pattern.finditer(text) if m.group() not in evidence]
    for m in re.finditer(r'\d+(?:\.\d+)?%|\d+\s*위|\d+\s*\+\s*\d+', text):
        if compact(m.group()) not in compact(evidence):
            found.append(m.group())
    return sorted(set(found))


# ---------------------------------------------------------------- product and edit measures

def keypoint_inliers(photo: Image.Image, ad: Image.Image) -> int:
    import cv2
    def grey(img, side):
        img = img.convert('RGB')
        img.thumbnail((side, side))
        return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
    a, b = grey(photo, 1024), grey(ad, 1350)
    sift = cv2.SIFT_create(nfeatures=4000)
    ka, da = sift.detectAndCompute(a, None)
    kb, db = sift.detectAndCompute(b, None)
    if da is None or db is None or len(ka) < 4 or len(kb) < 4:
        return 0
    pairs = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 4:
        return 0
    src = np.float32([ka[m.queryIdx].pt for m in good])
    dst = np.float32([kb[m.trainIdx].pt for m in good])
    _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    return int(mask.sum()) if mask is not None else 0


def edit_change(before: Image.Image, after: Image.Image, boxes: list[tuple[int, int, int, int]]) -> dict:
    from skimage.metrics import structural_similarity
    before = before.convert('RGB')
    resized = after.size != before.size
    after = after.convert('RGB').resize(before.size, Image.LANCZOS) if resized else after.convert('RGB')
    a = np.asarray(before, dtype=np.int16)
    b = np.asarray(after, dtype=np.int16)
    outside = np.ones(a.shape[:2], bool)
    pad = round(0.02 * before.width)
    for l, t, r, btm in boxes:
        outside[max(0, t - pad):btm + pad, max(0, l - pad):r + pad] = False
    changed = np.abs(a - b).max(axis=2) > 30
    _, ssim_map = structural_similarity(np.asarray(before.convert('L')), np.asarray(after.convert('L')),
                                        full=True, data_range=255)
    return {'price_area_found': bool(boxes), 'size_changed': resized,
            'changed_outside_price': round(float(changed[outside].mean()), 4),
            'ssim_outside_price': round(float(ssim_map[outside].mean()), 4)}


# ---------------------------------------------------------------- measure

def measure_one(case: dict, row: dict, base: Path, pattern: re.Pattern) -> dict:
    ad = Image.open(resolve(row['ad_image'], base))
    photo = Image.open(resolve(case['photo'], base))
    words = ocr(ad)
    store_ok, store_sim = contains(words, case['store_name'])
    product_ok, product_sim = contains(words, case['product_name'])
    want = amount(case['price_text'])
    found = prices(words)
    inliers = keypoint_inliers(photo, ad)
    out = {'case_id': case['case_id'], 'system': row['system'],
           'store_name_ok': store_ok, 'store_name_similarity': store_sim,
           'product_name_ok': product_ok, 'product_name_similarity': product_sim,
           'price_ok': has_price(words, want), 'wrong_prices': sorted(found - {want}),
           'unsupported_claims': claims(words, case, pattern),
           'product_inliers': inliers, 'product_kept': inliers >= INLIER_PASS,
           'make_seconds': float(row['make_seconds']) if row.get('make_seconds') else None,
           'edit_seconds': float(row['edit_seconds']) if row.get('edit_seconds') else None,
           'cost_usd': float(row['cost_usd']) if row.get('cost_usd') else None,
           'attempts': int(row['attempts']) if row.get('attempts') else None,
           'ocr_text': ocr_text(words)}
    if row.get('edited_image') and case.get('new_price_text'):
        after = Image.open(resolve(row['edited_image'], base))
        after_words = ocr(after)
        scale_x, scale_y = ad.width / after.width, ad.height / after.height
        boxes = price_boxes(words, case['price_text']) + [
            (round(l * scale_x), round(t * scale_y), round(r * scale_x), round(b * scale_y))
            for l, t, r, b in price_boxes(after_words, case['new_price_text'])]
        after_prices = prices(after_words)
        out.update(edit_change(ad, after, boxes))
        out['edit_new_price_ok'] = has_price(after_words, amount(case['new_price_text']))
        out['edit_old_price_gone'] = want not in after_prices
        out['edited_ocr_text'] = ocr_text(after_words)
    return out


def share(values) -> str:
    values = [v for v in values if v is not None]
    return f'{sum(bool(v) for v in values)}/{len(values)}' if values else '-'


def median(values, digits=1) -> str:
    values = [v for v in values if v is not None]
    return f'{statistics.median(values):.{digits}f}' if values else '-'


def summary(rows: list[dict]) -> str:
    systems = sorted({r['system'] for r in rows}, key=lambda s: (s != 'hanjang', s))
    lines = ['| 항목 | ' + ' | '.join(systems) + ' |', '|---|' + '---|' * len(systems)]
    def line(label, fn):
        lines.append(f'| {label} | ' + ' | '.join(fn([r for r in rows if r['system'] == s]) for s in systems) + ' |')
    line('가격 정확 (광고 수)', lambda rs: share(r['price_ok'] for r in rs))
    line('틀린 가격이 적힌 광고', lambda rs: share(bool(r['wrong_prices']) for r in rs))
    line('가게명 정확', lambda rs: share(r['store_name_ok'] for r in rs))
    line('상품명 정확', lambda rs: share(r['product_name_ok'] for r in rs))
    line('근거 없는 표현이 있는 광고', lambda rs: share(bool(r['unsupported_claims']) for r in rs))
    line(f'상품 사진 유지 (특징점 {INLIER_PASS}개 이상)', lambda rs: share(r['product_kept'] for r in rs))
    line('상품 특징점 일치 수 (중앙값)', lambda rs: median([r['product_inliers'] for r in rs], 0))
    line('가격 수정 후 새 가격 있음', lambda rs: share(r.get('edit_new_price_ok') for r in rs))
    line('가격 수정 후 예전 가격 없어짐', lambda rs: share(r.get('edit_old_price_gone') for r in rs))
    line('가격 수정 시 가격 밖 바뀐 픽셀 비율 (중앙값)', lambda rs: median([r.get('changed_outside_price') for r in rs], 3))
    line('가격 수정 시 가격 밖 SSIM (중앙값, 1=그대로)', lambda rs: median([r.get('ssim_outside_price') for r in rs], 3))
    line('만드는 시간 초 (중앙값)', lambda rs: median([r['make_seconds'] for r in rs]))
    line('가격 수정 시간 초 (중앙값)', lambda rs: median([r['edit_seconds'] for r in rs]))
    line('비용 USD (합계)', lambda rs: f"{sum(r['cost_usd'] or 0 for r in rs):.3f}")
    return '\n'.join(lines)


def sheet(case: dict, rows: list[dict], base: Path, out: Path):
    """One row per case: the photo, then each system's ad and its price-edited version."""
    tiles = [('원본 사진', resolve(case['photo'], base))]
    for r in sorted(rows, key=lambda r: (r['system'] != 'hanjang', r['system'])):
        tiles.append((f"{r['system']} 광고", resolve(r['ad_image'], base)))
        if r.get('edited_image'):
            tiles.append((f"{r['system']} 가격 수정", resolve(r['edited_image'], base)))
    w, h, label = 360, 450, 40
    canvas = Image.new('RGB', (w * len(tiles), h + label), 'white')
    font = ImageFont.truetype(str(FONT), 22) if FONT.exists() else ImageFont.load_default()
    draw = ImageDraw.Draw(canvas)
    for i, (name, path) in enumerate(tiles):
        img = Image.open(path).convert('RGB')
        img.thumbnail((w - 12, h - 12))
        canvas.paste(img, (i * w + (w - img.width) // 2, label + (h - img.height) // 2))
        draw.text((i * w + 10, 8), name, fill='black', font=font)
    canvas.save(out)


def cmd_measure(args):
    cases = {c['case_id']: c for c in read_csv(args.cases)}
    base = args.cases.resolve().parent
    pattern = claim_pattern()
    results = []
    for path in args.results:
        for row in read_csv(path):
            if not row.get('ad_image'):
                continue
            row['_base'] = path.resolve().parent
            results.append(row)
    args.out.mkdir(parents=True, exist_ok=True)
    measured = []
    for row in sorted(results, key=lambda r: (r['case_id'], r['system'])):
        case = cases.get(row['case_id'])
        if not case:
            sys.exit(f"results mention unknown case {row['case_id']}")
        # Paths in a results file are relative to that file; the case photo to the cases file.
        case = {**case, 'photo': str(resolve(case['photo'], base))}
        print(f"measuring {row['case_id']} / {row['system']}", file=sys.stderr)
        measured.append(measure_one(case, row, row['_base'], pattern))
    for case_id, case in cases.items():
        rows = [r for r in results if r['case_id'] == case_id]
        if rows:
            fixed = [{**r, 'ad_image': str(resolve(r['ad_image'], r['_base'])),
                      'edited_image': str(resolve(r['edited_image'], r['_base'])) if r.get('edited_image') else ''}
                     for r in rows]
            sheet(case, fixed, base, args.out / f'sheet-{case_id}.png')
    (args.out / 'measurements.json').write_text(json.dumps(measured, ensure_ascii=False, indent=2), encoding='utf-8')
    table = summary(measured)
    (args.out / 'summary.md').write_text('# 일반 AI 비교 결과\n\n' + table + '\n', encoding='utf-8')
    print(table)


# ---------------------------------------------------------------- make-hanjang

class Server:
    def __init__(self, url: str):
        import httpx
        self.http = httpx.Client(base_url=url.rstrip('/') + '/api/v1', timeout=60)
        self.token = self.http.post('/sessions').raise_for_status().json()['session_token']

    def call(self, method, path, **kw):
        r = self.http.request(method, path, headers={'X-Hanjang-Session': self.token}, **kw)
        if r.status_code >= 400:
            raise SystemExit(f'{method} {path} -> {r.status_code}: {r.text[:300]}')
        return r

    def wait(self, path, busy=('pending', 'processing'), limit=240, done=lambda s: True):
        for _ in range(limit):
            state = self.call('GET', path).json()
            if state['status'] not in busy and done(state):
                return state
            time.sleep(1)
        raise SystemExit(f'{path} did not finish')


def snapshot(draft: dict) -> dict:
    return {k: draft.get(k) for k in ('facts', 'mood', 'product_features', 'use_address_for_copy', 'ad_goal', 'photo_mode')}


def make_case(server: Server, case: dict, base: Path, out: Path, allow_paid: bool) -> dict:
    photo = resolve(case['photo'], base)
    mime = 'image/png' if photo.suffix.lower() == '.png' else 'image/jpeg'
    start = time.monotonic()
    up = server.call('POST', '/uploads', files={'photo': (photo.name, photo.read_bytes(), mime)}).json()
    job = up['job_id']
    facts = {'store_name': case['store_name'], 'product_name': case['product_name'], 'price_text': case['price_text'],
             'address': None, 'instagram_handle': None}
    draft = server.call('PUT', f'/jobs/{job}/input', json={
        'facts': facts, 'mood': case.get('mood') or 'warm', 'ad_goal': case.get('ad_goal') or 'menu_promotion',
        'product_features': case.get('product_features') or None}).json()
    # Same order as the site's one-click flow (frontend/src/flow/generate.ts).
    photo_state = server.call('GET', f'/jobs/{job}/photo-processing').json()
    if photo_state['status'] == 'pending':
        server.call('POST', f'/jobs/{job}/photo-processing')
    photo_state = server.wait(f'/jobs/{job}/photo-processing')
    asset = photo_state['processed']['asset_id'] if photo_state['photo_source'] == 'processed' and photo_state.get('processed') else photo_state['original']['asset_id']
    try:
        server.call('POST', f'/jobs/{job}/photo-analysis', json={'expected_asset_id': asset})
        server.wait(f'/jobs/{job}/photo-analysis', busy=('processing',), limit=150)
    except SystemExit as error:  # analysis is optional on the site too
        print(f"  analysis skipped: {error}", file=sys.stderr)
    copy = server.call('GET', f'/jobs/{job}/copy-generation').json()
    if copy['provider'] == 'openai' and not allow_paid:
        raise SystemExit('The server would make a paid OpenAI copy call. Use the mock provider, or pass --allow-paid after team agreement.')
    server.call('POST', f'/jobs/{job}/copy-generation', json={'expected_asset_id': asset, 'expected_input': snapshot(draft)})
    copy = server.wait(f'/jobs/{job}/copy-generation', busy=('processing',), limit=90)
    if copy['status'] != 'completed':
        raise SystemExit(f"copy failed: {copy.get('error')}")
    server.call('POST', f'/jobs/{job}/rendering', json={'expected_asset_id': asset, 'expected_copy_key': copy['copy_key'],
                                                        'expected_input': snapshot(draft)})
    render = server.wait(f'/jobs/{job}/rendering', busy=('processing',))
    if render['status'] != 'completed':
        raise SystemExit(f"render failed: {render.get('error')}")
    strategy = case.get('strategy') or 'price'
    path = f'/jobs/{job}/designs/{strategy}'
    server.call('POST', path, json={'expected_render_revision': render['revision'],
                                    'expected_source_asset_id': render['source_asset_id'], 'expected_copy_key': render['copy_key']})
    designs = server.wait(path, busy=('processing',))
    if designs['status'] != 'completed':
        raise SystemExit(f"designs failed: {designs.get('error')}")
    designs = server.call('POST', path + '/ranking', json={'expected_revision': designs['revision'],
                                                           'expected_snapshot': designs['snapshot']}).json()
    if not designs.get('ranking'):
        designs = server.wait(path, busy=('processing',), done=lambda s: s.get('ranking') or s.get('ranking_error'))
    make_seconds = time.monotonic() - start
    # One ad per system: our top-ranked design (A if ranking failed), like the first thing a user sees.
    items = sorted((designs.get('ranking') or {}).get('items') or [], key=lambda i: i['rank'])
    chosen = next((c for c in designs['candidates'] if items and c['candidate_id'] == items[0]['candidate_id']), designs['candidates'][0])
    out.mkdir(parents=True, exist_ok=True)
    ad_path = out / f"{case['case_id']}-hanjang.png"
    ad_path.write_bytes(server.call('GET', f"/assets/{chosen['png']['asset_id']}").content)
    row = {'case_id': case['case_id'], 'system': 'hanjang', 'ad_image': ad_path.name, 'make_seconds': f'{make_seconds:.1f}',
           'cost_usd': '0' if copy['provider'] == 'mock' else '', 'attempts': '1',
           'notes': f"{chosen['template_id']}; copy={copy['provider']}"}
    if case.get('new_price_text'):
        start = time.monotonic()
        server.call('PATCH', f"{path}/candidates/{chosen['candidate_id']}", json={
            'expected_revision': designs['revision'], 'expected_snapshot': designs['snapshot'],
            'expected_asset_id': chosen['png']['asset_id'], 'copy': chosen['copy'], 'price_text': case['new_price_text']})
        edited = server.wait(path, busy=('processing',), done=lambda s: not s.get('editing'))
        if edited.get('error'):
            raise SystemExit(f"price edit failed: {edited['error']}")
        new = next(c for c in edited['candidates'] if c['template_id'] == chosen['template_id'])
        edit_path = out / f"{case['case_id']}-hanjang-edited.png"
        edit_path.write_bytes(server.call('GET', f"/assets/{new['png']['asset_id']}").content)
        row.update(edited_image=edit_path.name, edit_seconds=f'{time.monotonic() - start:.1f}')
    return row


def cmd_make(args):
    server = Server(args.server)
    base = args.cases.resolve().parent
    rows = []
    for case in read_csv(args.cases):
        print(f"making {case['case_id']}", file=sys.stderr)
        rows.append(make_case(server, case, base, args.out, args.allow_paid))
    write_csv(args.out / 'results-hanjang.csv', rows, RESULT_FIELDS)
    print(f"wrote {args.out / 'results-hanjang.csv'}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    make = sub.add_parser('make-hanjang', help='make our ads and price edits through the local server')
    make.add_argument('--cases', type=Path, required=True)
    make.add_argument('--out', type=Path, default=Path('artifacts/compare/hanjang'))
    make.add_argument('--server', default='http://127.0.0.1:8000')
    make.add_argument('--allow-paid', action='store_true')
    make.set_defaults(run=cmd_make)
    measure = sub.add_parser('measure', help='measure every system and write the report')
    measure.add_argument('--cases', type=Path, required=True)
    measure.add_argument('--results', type=Path, action='append', required=True)
    measure.add_argument('--out', type=Path, default=Path('artifacts/compare/report'))
    measure.set_defaults(run=cmd_measure)
    args = parser.parse_args(argv)
    args.run(args)


if __name__ == '__main__':
    main()
