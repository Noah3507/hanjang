# Phase 16 — product visibility and advertising-copy quality

Local validation: 2026-11-16, Windows, Python 3.12.10 / Node 24.20.
Branch: `feat/ad-templates-v3`. Baseline: Phase 15 `f9c1deb`.
No paid calls, remote Git changes, presentation restart or B code changes.

## Delivered changes

- `product_geometry.py` normalizes EXIF orientation and measures alpha support
  at threshold 16. It trims transparent margins with 2% padding only when lost
  alpha mass is at most 0.002. Disconnected accessories remain included. Opaque
  photos are retained whole; their subject extent is explicitly unknown.
- The v3 worker fits measured support into circular/rectangular slots. Every
  supported alpha row is checked against the ellipse, rather than enlarging an
  image with CSS scale. Original uploaded bytes are retained. Prepared bytes are
  derived assets, with source/prepared hashes and crop evidence recorded.
- `quality.css` preserves the 16 source directions and palettes. Price A/C use
  measured circle placement, B strengthens price/body hierarchy, D uses a smaller
  bounded stamp. The other twelve receive body/CTA/period spacing improvements;
  Brand A balances the wordmark against the product, Brand C protects text with
  a solid backplate, Visual B reduces its heavy frame.
- Font fitting now overrides template `!important` rules for new requests, so
  long names can actually shrink within existing limits. It never truncates copy.
  Legacy worker requests without geometry metadata keep their previous behavior.
- V3 diagnostics add `subject_size` and `image_crop`; v2 rules and APIs remain
  unchanged. Opaque subjects return unavailable; intentional front gradients are
  reported as caution. These are heuristics, not a quality guarantee.
- Real-provider prompt version is `copy-v4-ad-direction`. Strategy directions
  favor advertising language, avoid repeated headline/body/CTA and prohibit
  unsupported claims. Expanded local claim checks and nonmutating advisory
  warnings inspect final bound copy. Facts, price placeholders, JSON contract,
  privacy gates, SDK and retry/cost policies remain intact. Mock is unchanged.
- `ad_quality_v1.json` contains separate fixed advertising-copy fixtures. They
  are used for free design review, never substituted into live Mock responses.

## Actual-photo evidence

The user's existing aburasoba original and rembg cutout were visually identified
locally. Source hashes were checked before/after; neither file was changed.
The 1600×1200 cutout's nonzero alpha bbox spanned almost the full width because
of faint background ghosts. Alpha >=16 support was `(363,241,1288,989)`; the
derived padded crop is `(344,222,1307,1008)`. Removed alpha mass was 0.00009372,
below the guard. This fixes the root cause of the tiny dish without discarding
meaningful disconnected parts or redrawing the product.

Final private review folder, relative to repository root:
`../phase16-work-20261116/review-candidate-02/`.

| Artifact | Content |
|---|---|
| `gallery.html`, `gallery.png` | Final sixteen actual-food designs |
| `price-before-after.html` | Pinned Phase 15 versus current A–D |
| `all-conditions.html` | 80 current PNGs: cutout, original, cosmetic, clothing, long copy/promotion |
| `subject-size-comparison.json` | Measured support boxes and preprocessing evidence |
| `model-comparison.json` | Real B before/after raw scores, ranks and timings |

Price A support width/height increased 1.8433×; C increased 1.8595×, without
unintended clipping. Baseline PNGs were rendered from pinned `git show` source;
adding the read-only legacy measurement probe produced byte-identical PNGs.
User photos and review PNGs are local-only and excluded from Git/PR. Synthetic
cosmetic/clothing assets are original code-generated test scenes, not downloaded
or license-assumed images. Original ZIP/AI/PNG reference files remain unchanged.

## Tests and limitations

| Check | Result |
|---|---|
| Backend full suite with installed rendering opt-in | 493 passed, no failures/skips; 293.53 s |
| Final renderer/geometry/copy focused rerun, render opt-in enabled | 25 passed, no skips; 84.83 s |
| Frontend Vitest | 74 passed in 17 files |
| TypeScript / production build | Passed; temporary build output preserved presentation assets |
| Actual browser v3 + existing v2 editor/diagnostics | 5 passed; 2.2 min |
| Offline rembg / CLIP | Existing models loaded and inferred successfully |
| Real B inference | Eight batches: four strategies × before/after; `bt-logistic-v1` |
| Final 80 PNGs | RGB 1080×1350; hashes, fonts, no text overflow/unintended clipping verified |
| Downloaded edited PNG/PDF | Strict PDF parse; one A4 page; embedded PNG RGB bytes exactly equal |
| GitHub Actions | Not run: no push or PR authorized |

The full suite preceded the final Brand A CSS adjustment; the final focused
renderer/geometry/copy suite covers that adjustment. A non-opt-in preliminary
run had 19 passed / 6 skipped; the opt-in rerun executed all six. Existing
Starlette/AnyIO deprecation is unrelated. Browser evidence is in
`artifacts/phase16/e2e-final/`; actual PDF rasterization and checks are in
`artifacts/phase16/pdf-rendered.png` and `final-verification.json`.

Browser tests used Mock copy and actual Chromium. The v3 opt-in local-photo run
used the user's cutout and actual B model, then edited text/price, downloaded
PNG/PDF, switched strategy, restored/reloaded and checked preserved v2 output.
Other browser failure cases deliberately simulate errors. No real OpenAI output
was generated; improved prompt quality remains unverified with the paid model.

Final diagnostic counts across 80 designs:

| Rule | Normal | Caution | Unavailable | Problem |
|---|---:|---:|---:|---:|
| Contrast | 51 | 0 | 29 | 0 |
| Font size | 0 | 80 | 0 | 0 |
| Layout | 69 | 11 | 0 | 0 |
| Density | 78 | 2 | 0 | 0 |
| Subject size | 48 | 0 | 32 | 0 |
| Image crop | 71 | 9 | 0 | 0 |

Small labels remain below the existing 36px heuristic. Some text/image bounding
boxes intersect without glyph collision, and gradients intentionally overlay
photo areas. These warnings were not disabled. Twenty-nine contrast results
remain unknown over photos/complex backgrounds; opaque photos cannot establish
true product extent. Background-removal remnants within the supported subject
are not semantically repaired. At thumbnail scale some body text remains small;
visual polish and fidelity to reference originals still require human approval.

Model score/rank changes do not prove better design, sales or CTR. The same
four candidates were compared per strategy using unchanged B preprocessing and
weights. Brand A was re-inferred after its final adjustment. Raw results stay
local; model ranking and rule-based diagnostics stay separate in the UI.

| Strategy | Before descending preference | After descending preference |
|---|---|---|
| Emotional | D, A, B, C | D, B, A, C |
| Price | B, C, D, A | C, A, B, D |
| Brand | C, B, A, D | C, B, D, A |
| Visual | C, A, D, B | C, D, A, B |

Claim keyword checks are conservative, not a semantic fact-checker. Fixtures
do not establish that unseen paid generations will be accurate or attractive.

## Reproduction and user review

```powershell
$env:RUN_RENDER_TESTS='1'
.\.venv\Scripts\python.exe -m pytest
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run test -- --run
npm.cmd --prefix frontend run build
```

`scripts/service_phase16_review.py --photo-inventory <private-inventory.json>
--output <new-outside-folder>` reproduces a fresh review using the visually
confirmed private inventory; it refuses an existing output directory. It is a
local review utility, not a production photo discovery/download mechanism.

Isolated Mock-copy/actual-model development UI: `http://127.0.0.1:5187`, backend
`http://127.0.0.1:8017`. Existing servers/Tunnel were not restarted. Upload an
owned photo, save facts, use Mock copy, render v2, select a strategy and generate
four v3 designs; inspect warnings, optionally rank, edit one, download PNG/PDF.
The gallery can be reviewed without generating any jobs or calling an API.
Local processes do not survive reboot automatically.

Cost ledger remains 8 completed calls / $0.01274025; SHA-256:
`2b221949d6d59a36906e5150118bce454a4cc8c54ec077f873203cedb81597b6`.
No new paid calls. `.env`, credentials, transfer backup, venvs, model weights,
existing uploads/downloads and presentation processes are preserved.

See [PR draft](PR_AD_TEMPLATES_V3.md). User visual acceptance is pending.
