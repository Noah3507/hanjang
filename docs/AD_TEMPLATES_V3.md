# Phase 14: opt-in price templates v3

## Scope and compatibility

Base: main `c7892d8` (PR #52 already merged). The existing `RenderExecution`,
four-strategy HTTP rendering, Candidate schema, editing, downloads, diagnostics
API and B ML code are unchanged. No selection UI or LLM API is added.

`backend/app/services/template_v3.py` exposes `render_templates(TemplateInput,
photo_bytes, template_ids=None)`. Defaults are **four price variations**, not four
strategies. `REGISTRY` reserves 16 IDs; only `price_a` through `price_d` are
implemented. Other IDs return `RENDER_INVALID_TEMPLATE`. The version is
`ad-templates-v3-price-1`. Template IDs are not candidate/asset IDs: each result
has new random candidate/asset IDs, revision 1, input snapshot, PNG hash,
measurement and existing `diagnostics_engine.analyze` output. These are local
render envelopes, not persisted HTTP Candidates or authorized downloadable assets.

## Source review and rights

Original ZIP was read unchanged. A new **outside-repository** folder contains
76 extracted files: 16 AI and 60 PNG (16 examples, 32 short/long templates,
12 strategy contact sheets). All names, sizes and hashes are in `inventory.json`.
Paths were checked for traversal, absolute/drive paths, backslashes, symlinks,
case-insensitive duplicates and expanded size limits before extraction.

All 16 AI files contain a PDF-compatible single 1080×1350 page. Existing pypdf
read page boxes, embedded subset font names, text runs, font sizes and matrices.
This does **not** recover Illustrator's editable layer model. PDF extraction
contains replacement characters in some spaces; these extracted strings are
analysis evidence only, never user copy. `ai-pdf-analysis.json` and
`ai-text-runs.json` retain these limitations. Geometry below is visually estimated
from PNGs, not exact reconstructed Illustrator coordinates.

No source PNG/AI, example photo, brand name, example promotion or embedded font
was copied into Git or used as a flattened background. Only HTML/CSS geometry was
reconstructed. Team assets and example-photo/font rights still need owner review
before public/commercial use. Existing regular Noto font is retained; new real
Noto Sans KR Bold comes unchanged from the same Sans2.004 official release:

- https://github.com/notofonts/noto-cjk/tree/Sans2.004/Sans/SubsetOTF/KR
- https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/Sans/SubsetOTF/KR/NotoSansKR-Bold.otf
- SHA256 `5a6ceb287ed2fc6cfc6213144ebea68cbd94b20fc9eb873d8486493bf02d9bda`
- SIL OFL 1.1, retained `templates/fonts/OFL.txt`; embedding/bundling allowed under
  its conditions: https://openfontlicense.org/open-font-license-official-text/

Original price/brand PDF fonts are Pretendard (multiple weights), emotional uses
Noto Serif KR ExtraLight. This implementation uses Noto Sans KR 400/700: font
shape and weight differ from the reference; it is not pixel-identical. No
synthetic bold, OS fallback, runtime font/model/network download or generated
product reinterpretation occurs. Both font hashes and cmap are checked; Chromium
CDP verifies actual custom fonts per text node.

## Sixteen source specifications

All coordinates are **estimated** `(x,y,w,h)` in 1080×1350 PNG px. Text is
dynamic throughout. Brand/CTA slots use input only. No reference English slogan
or decorative copy is automatically invented. Exact implementation geometry for
the four price templates is authoritative in `templates/v3/price.css`.

| ID | Image slot / shape | Text slots and hierarchy | Background / decoration |
|---|---|---|---|
| emotional_a | (190,180,700,710), rectangle | brand/top (100,85,880,30); headline (230,980,620,140), center ~48 serif; body (180,1140,720,70) ~22; footer brand | pale gray; thin top rule, spacious gallery |
| emotional_b | (0,0,1080,930), cover | headline (95,1020,700,140) ~48 serif; body (95,1180,750,60) ~22; brand bottom right | deep green lower fade; photo gradient; text-photo contrast needs sampled evidence |
| emotional_c | (440,230,560,690), rectangle | headline (80,245,300,240) ~48 serif left; body (80,680,300,120) ~22; image caption below; brand bottom | warm cream; editorial columns and hairline |
| emotional_d | (235,350,610,650), circular/arch | headline (220,150,640,150) centered ~48 serif; body (220,1110,640,60) ~22; brand bottom | dark green; outlined arch; light text |
| price_a | (520,290,670,650), right-clipped circle | product (64,240,440,210), 72 bold; headline/body left; raw price (64,939,720,205), 146 bold; brand header; CTA/footer | yellow, black rails and circle outline; optional dark discount badge |
| price_b | (0,0,1080,780), cover | product (64,798,690,127), 54 bold; headline/body below; raw price (64,1110,720,116), 100 bold; store on photo label | white photo over black panel; optional yellow promotion/badge |
| price_c | (327.5,790,425,425), circle | price (64,230,952,210), 178 bold; centered product (100,470,880,110), 56 bold; headline/body stacked; brand/CTA footer | black field and yellow price/pill; photo reduced to retain extra input fields |
| price_d | (140,250,800,800), rectangle | brand top; product (64,118,952,100), 68 bold; headline/body bottom-left; raw price in red circle (650,975,340,92), 72 bold | white field, red opaque stamp overlapping photo; black footer |
| brand_a | (195,220,200,200), letter inset | wordmark (70,220,940,640), left ~180 bold; brand (70,1090,940,100); body and CTA below | forest green; cream/lime display hierarchy; no arbitrary English translation |
| brand_b | (220,240,640,640), emblem circle | brand/title (120,950,840,100), center ~76 bold; subtitle (180,1080,720,60); CTA bottom | cream; green circular surround |
| brand_c | (180,200,720,730), bordered rectangle | brand/title (100,1000,880,100), center ~72 bold; body/CTA below | green repeated input-brand pattern, lime image border; clipping must be deliberate |
| brand_d | (420,540,580,630), rectangle | Korean brand (65,140,950,330), left ~130 bold; headline/body left column; CTA bottom | lime field, green wordmark, footer rule |
| visual_a | (0,0,1080,1350), full bleed | brand top-left; headline (70,1120,700,140), ~44 bold; body/CTA bottom-right | full photo, variable contrast, safe-area text |
| visual_b | (60,60,960,1090), rectangle | headline (80,1180,650,90), ~38 bold; brand/CTA bottom-right | off-white polaroid frame |
| visual_c | (0,0,1080,1350), cover | brand top; headline (70,1100,850,160), ~56 bold; body/CTA overlay | dark cinematic gradients top/bottom |
| visual_d | (0,135,1080,1080), rectangle | centered brand (100,40,880,50); headline (70,1250,750,60), ~32; CTA right | black film rails; contained photo |

Short/long PNG pairs retain their principal photo slots. Longer names generally
wrap to extra lines and promotion/date/brand expand. Some reference claims (100%
discount, inconsistent example prices) are illustrations, not valid product
facts. They are never defaults. Non-price templates above are specifications,
not implemented or approved commercial designs. Their price slots are not
visible in the sources; adding prices requires a future approved variant rather
than inventing a source slot.

## Text, images, promotions and diagnostics

All user text is escaped by Jinja2. Facts and price, including whitespace and
currency, are never normalized, split, translated, truncated or replaced.
Required names/price/headline must be nonempty. Optional original_price,
discount_text, promotion_text and period_text are caller-supplied verified facts;
missing fields are omitted without leaving fake text. No discount arithmetic or
limited-sale/efficacy/CTA claim is generated. The current HTTP facts contract does
not contain promotion fields: exposing these requires separate schema/ownership
review; this local implementation does not change it.

Natural keep-all Korean wrapping → bounded tracking/line-height adjustment →
font-size down to 76% (at least 22px, price 42px) → explicit
`RENDER_LAYOUT_OVERFLOW`. No ellipsis/deletion; fixed photo and text slots do not
shrink to hide failure. `fit_steps` records the actual adjustments. This first
set has no alternate-layout search or slot expansion, because source layouts are
fixed. They remain possible future reviewed variants.

Photos keep aspect ratio: transparent input uses contain, opaque input uses
cover, with geometric clipping. Content can be
cropped, especially tall bottles or horizontal products in circles; product
identity completeness needs human review. The circular slot may still clip a
contained rectangular silhouette at its corners. Transparent input is supported; no
background removal or image synthesis is performed here. EXIF orientation is
interpreted without modifying the stored input. D's opaque stamp intentionally
overlaps the photo: diagnostic bbox collision can correctly remain a caution.
No automatic palette recoloring is applied.

The existing diagnostics engine receives measured text/geometry/custom fonts
and PNG/background evidence. Unknown image/transparent/effect contrast remains
unavailable; this is not a full accessibility guarantee. No contrast, optical
balance or photography quality is fabricated. Low font size/density warnings
are recorded, not turned into ranking scores or silently suppressed.

## Reproduce offline

```powershell
$env:RUN_RENDER_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/service/test_template_v3.py -q
.\.venv\Scripts\python.exe scripts/service_template_v3_review.py --output '..\phase14-new-comparison'
```

Output must be a **new** folder outside the repo; existing results are never
overwritten. The review script creates original synthetic product drawings
(bottle/shirt/speaker), not licensed third-party product photos. These establish
layout/ratio/contrast edge cases but cannot prove real-photo art direction.
Each case reuses the exact same image and copy for v2/v3. Input data, source hash,
PNG hashes, measured typography, fit steps, diagnostics and identities are saved
in metadata.json. Gallery HTML/PNG show the four price variants together.

## Service/UI and ML follow-up

Before production integration: agree an additive version/variant selection
request and promotion-fact contract; keep original four-strategy response;
persist normal session-owned TTL assets; preserve revision/snapshot/stale
checks during editing and inference; add selection UI and browser service E2E.
No unprotected file path should be returned as a public URL.

Other 12 IDs can be implemented with new HTML/CSS, explicit slot/claims specs,
real fonts and the same renderer checks. Mark implemented only after tests.
The B model takes final PNGs and IDs; do not pretend four price variants are
four different strategies, reuse stale ranks, mix readability into raw score,
or assume a model trained on older layouts generalizes. Review ranking request
contract before admitting same-strategy variants. No B code/training is changed.
