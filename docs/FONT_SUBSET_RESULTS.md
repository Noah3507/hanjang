# Font subset integration results

Main `e862d38` includes merged PR #70. `git apply --check` and application of
`transfer/font-subset-for-A.patch` succeeded without conflict. The alpha-matte
patch, haze data and comparison image remain untouched; no B-owned files changed.

## B patch retained / safety adjustments

Retained: FontTools per-text subsetting, ASCII/punctuation base, all layout
features and name metadata, notdef outline, original SHA256 and Noto glyph gate,
variable axes, offline data URIs and the existing CSS family aliases.

Adjusted only the font service/tests and handoff documentation:

- Build from the **already verified bytes**, avoiding a second mutable-path read.
  Verify source bytes on every load, even on a warm cache hit; corrupt/missing
  originals still return RENDER_FONT_UNAVAILABLE. Unavailable glyph policy remains.
- Canonicalize the character set. Key cache by source digest, character set and
  subset-options/FontTools version; include the version in rendering identity.
  Edits with new characters build a different subset. No original asset is edited.
- LRU:128 entries **and16MiB font payload total**, at most1MiB/output and21000
  characters/key. Larger outputs are rendered but not retained. Keys/objects add
  overhead (worst-case character storage roughly10MiB plus metadata), so this is
  not a16MiB whole-process RSS claim. Compilation's transient memory is separate.
- Keep hinting rather than B's hinting=False, to preserve raster appearance.
- Rename generated primary names to `HanjangSubset` + source SHA256 prefix,
  including CFF and variable-instance PS names. Preserve author/license metadata
  and the original OFL files. CSS aliases remain HanjangNoto/Noto Serif KR/
  Pretendard. [Official OFL FAQ2.6/2.8](https://openfontlicense.org/ofl-faq/)
  treats per-text webfont subsets as modified versions subject to RFN conditions.

Current templates have no fixed visible text outside supplied values; brand_c
repeats the supplied store name. No CSS generated content/text transforms or
worker text insertion exists. All TemplateInput text fields, including optional
promotion/original-price/period, enter the character set; ASCII covers whitespace
and punctuation. Layout closure keeps generated shaping glyphs. If B later adds
fixed non-ASCII text, it must join this input before subsetting.

## Actual measurement

Windows Python3.12 / existing Node24 and Playwright Chromium. Same saved real v7
copy, actual jjajang/espresso photo, four strategy templates and isolated CSS
family override in both conditions. No template/photo/copy changes between arms.
The baseline loader is the exact main source; only font loading is swapped.
Each call starts a fresh Chromium. Final runs were repeated after concurrent
regression tests finished; earlier measurements are separately preserved.

| Case / primary family | Full primary bytes | Subset primary bytes | Full4 median | Subset4 median | First subset-cache-cold render |
| --- | ---: | ---: | ---: | ---: | ---: |
| jjajang / Noto Serif KR | 23,795,420 | 203,404 | 22.595s | 3.147s | 4.803s |
| espresso / Pretendard | 6,739,336 | 104,164 | 11.574s | 2.644s | 3.807s |

All individual4-template durations, seconds:

- Noto full:22.778/22.595/21.963; subset:4.803/3.103/3.147.
- Pretendard full:11.907/11.574/11.089; subset:3.807/2.644/2.611.
- Cold font CSS preparation (source verification + fallback faces + primary
  subsetting/base64, not primary subsetting alone):1.303s /1.362s respectively.
- Including both Noto fallback faces, embedded font payload falls from
  33,256,212→337,972 bytes and16,200,128→233,192 bytes respectively.
- The first subset run has an empty in-process subset cache; later runs reuse
  it. This is **not** an OS disk-cache-cold or machine-reboot benchmark.
- Process-tree peak memory was not measured; no estimate or B's0.18GB is claimed.
  The final representative cache held6 entries/468,508 payload bytes, not RSS.
- B's58KB /0.3s figures were not reproduced. Actual text/base/hinting preservation
  differ; no options were weakened to match the reported numbers. This is a local
  sample, not a universal latency promise or always2–4s cold-start claim.

Full/subset decoded pixels, text geometry and line counts were **equal for all8
comparison PNGs**, including price_c. The previous pixel instability did not
reappear in the dedicated16-template fallback-CSS test either.

## Verification and B handoff

- Backend whole suite:710 passed,44 explicit browser/model opt-in skips.
- Actual Chromium fonts:13 passed, including400/620/700, actual custom CDP faces,
  Jamo fallback, new Hangul/price/body/CTA API edit, unchanged other assets/style,
  stale rank clearing and old-download rejection. MockRanker fixture is explicit.
- Earlier fonts +16-template CSS pixel regression:20 passed. Initial fixture
  import and620→existing700 fallback test expectations were corrected, not the
  renderer or tolerances. Existing AnyIO deprecation warning remains.
- Glyphs include Korean/English/digits/currency/punctuation; fvar/gvar and GSUB/
  GPOS retained. Unsupported glyphs and subset failures remain explicit errors.
- Real gallery:17 images decode; console/pageerror0. The extra edited copy is
  clearly a user-edit simulation, not a newly generated LLM response.
- Frontend untouched; existing frontend/browser/release regression runs in CI.

B can keep the existing CSS aliases/weight ranges in
[the font contract](../backend/assets/fonts/README.md). CDP now reports renamed
subset faces; map their prefix to the existing source manifest SHA256 rather than
requiring the original familyName. Keep the existing template-version policy
when applying B-owned CSS. The new subset policy invalidates prior render caches.

Local gallery and raw measurements:
`artifacts/font-subset-20261126/clean/gallery.html`, `benchmark.json`,
`browser-check.json`; original concurrent-run evidence remains in the parent.
Open full/subset columns and compare the edited-new-hangul image. Existing saved
real copy/photo are reused. Original font, model and user-photo bytes, transfer
files and ledger remain unchanged. Paid/image API calls0; ledger15/$0.02431050.
Operating server and tunnel are untouched, no deployment or main merge.

```powershell
$env:RUN_RENDER_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/service/test_render_fonts.py tests/service/test_template_v3_style_vars.py
```

After CI/review, merge requires the user's explicit action/approval. B's template
CSS application and alpha-matte improvements remain independent follow-up PRs.
