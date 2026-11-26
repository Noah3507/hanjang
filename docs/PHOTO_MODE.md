# Photo mode service contract (A → B)

Based on main `b568536`: PR #68 fonts and PR #69 whole-photo cards are merged.
Only the original-photo option is implemented here. Font subsetting and alpha
cleanup patches are not available and are not recreated or included.

## Input API

`photo_mode` is a top-level InputDraft/DraftResponse field, next to `mood` and
`ad_goal`, not inside `facts`. Enum: `cutout | original`, default `cutout`.

Authenticated `PUT /api/v1/jobs/{job_id}/input` example:

```json
{
  "facts": {"store_name":"골목반점","product_name":"짜장면","price_text":"7,000원"},
  "mood":"warm",
  "photo_mode":"original"
}
```

`GET /api/v1/jobs/{job_id}/input` returns these fields plus `job_id`,
`status:"pending"`, `product_features`, `use_address_for_copy`, `ad_goal` and
`expires_at`. `status` is the existing draft status, not rendering status.
PUT still requires facts/mood; this is not a partial PATCH. Omission of photo_mode
preserves the stored choice. Old input without the field defaults to cutout.
Explicit null/unknown enum is422. Ownership/session/TTL remain unchanged.
No frontend, template, ML or `design_style.py` files are edited by A.

Example GET/PUT response (synthetic IDs/time):

```json
{
  "job_id":"example-job",
  "status":"pending",
  "facts":{"store_name":"골목반점","product_name":"짜장면","price_text":"7,000원","address":null,"instagram_handle":null},
  "mood":"warm",
  "photo_mode":"original",
  "product_features":null,
  "use_address_for_copy":false,
  "ad_goal":"menu_promotion",
  "expires_at":"2026-11-27T00:00:00Z"
}
```

## Which photo is used

- `original`: read the immutable upload; apply EXIF orientation; alpha-composite
  over opaque white **before** dropping alpha; convert to RGB; thumbnail to
  `photo_max_side` (default1600), preserving aspect ratio without crop/upscaling.
  The render-only PNG is not written back over the uploaded file. Fully
  transparent hidden RGB cannot turn into black marks. Partial alpha is blended
  onto white; this deliberately changes the displayed background, not the file.
- `cutout`: reuse an existing processed asset if present; otherwise retain the
  existing selected/original fallback. No processing or inference is triggered.
  Availability/quality is still visible through the existing photo-processing
  response. This option is not a new guarantee of a successful cutout.
- Analysis's existing `photo_source` selection is a separate anchor and is not
  changed by photo_mode. Mode changes do not call `/photo-source`, `/photo-analysis`
  or `/photo-processing`. Existing processed/original assets remain stored.
- The B templates consume the existing `transparent` evidence from
  `prepare_product`: RGB original yieldsFalse/whole-photo; alpha cutout yieldsTrue.
  No card flag or per-template exception is added. All16 templates are supported,
  including price_a/price_c/emotional_d/brand_a/brand_b with small card slots.
- Original subject position is unknown. Existing subject_size is **unavailable**
  in the current implementation, with its existing explanation; do not fabricate
  a size or hide that status. Image/overlay diagnostics remain intact.

## Snapshot and B frontend state handling

1. Save the complete draft with photo_mode; use the returned draft for requests.
2. If only this field changed, keep the existing copy and analysis/palette.
   `GET copy-generation` retains its copy_key and is_current. The LLM payload and
   copy input hash exclude photo_mode. Other copy dependencies are unchanged.
3. Mark displayed render/design/ranking state stale and fetch authoritative GETs.
   Do not show an earlier mode's rank on the new preview.
4. `POST rendering` uses existing copy_key and the latest `expected_input`,
   including `photo_mode`; then poll rendering and request the desired v3 strategy.
   **Do not generate new copy or rerun photo processing for a mode-only change.**
5. Re-request ranking only for the successful current design revision/snapshot.
   Existing exact-match caches may be reused on a mode roundtrip; a result whose
   whole identity matches is safe to reuse, not a stale result of another mode.

Rendering/edit `expected_input.photo_mode` must match stored draft. An old client
omitting it still works for cutout; an original-mode render request with omitted
field defaults to cutout and receives409. Copy-generation compares all its actual
input dependencies while ignoring this render-only field; a mode-only repeat
request returns the cached copy and does not require another provider call.

Rendering request shape (replace synthetic IDs with current GET values):

```json
{
  "expected_asset_id":"00000000000000000000000000000000",
  "expected_copy_key":"11111111111111111111111111111111",
  "expected_input":{
    "facts":{"store_name":"골목반점","product_name":"짜장면","price_text":"7,000원"},
    "mood":"warm",
    "photo_mode":"original",
    "product_features":null,
    "use_address_for_copy":false,
    "ad_goal":"menu_promotion"
  }
}
```

`source_asset_id`/`expected_asset_id` remain the existing analysis-selected photo
anchor for compatibility, even in original mode. They do not newly identify the
normalized rendering bytes. The existing renderer `photo_sha256` identifies the
upload; `processed_photo_sha256` records the **actual bytes sent to rendering**.
Render identity includes mode, actual rendering-photo SHA256, normalization policy
version and max_side. V3 identity builds on that v2 source and existing style/font
fingerprints. Palette and product-kind style inputs remain unchanged.

Start/completion/GET/edit/export/rank fencing uses this identity. A mode change
during rendering cannot promote old work as current; a v3 edit cannot overwrite
the latest source. A missing/tampered photo stales the last success while preserving
its metadata, and a new render/edit fails explicitly instead of deleting it.

## Editing/download/error handling

Use the existing candidate PATCH and download endpoints, current revision,
expected_asset_id and snapshot. Original mode stays active through headline,
body, CTA and candidate-only price edits. Facts, styles, font rules and the other
three assets follow the existing contracts. Price edits do not update the global
draft price. No new editing/export system is introduced.

Errors retain existing envelope/session protection:

- 422: invalid enum; `RENDER_PHOTO_INVALID` if original decode/normalization fails.
- 409: stale rendering/edit/design/download snapshot; `RENDER_PHOTO_CHANGED` for
  source checksum mismatch. Cached previews can remain available as stale metadata.
- 401/404/410: existing session, ownership/resource, expiry policy.

No paid calls, runtime download, operating-server restart or deployment is needed.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest tests/service/test_photo_mode.py
.\.venv\Scripts\python.exe -m pytest
```

Actual local evidence: `artifacts/photo-mode-20261126/gallery.html`, `report.json`,
`jjajang-original-measurements.json`, `espresso-original-measurements.json`.
Stored actual LLM responses are explicitly replayed through a mock-labelled
adapter; no new LLM output is claimed. Saved real CLIP clues are replayed (not
new CLIP inference). Local rembg prepares one initial cutout per product using
the unchanged model/algorithm; transitions reuse it with0 additional model calls.
Chromium and bt-logistic-v1 ranking are actual. The current running server is not
used for mutations; tests use an isolated app and private upload root.

Two products: jjajang and espresso; cutout→original→cutout, all16 original
templates for jjajang, representative espresso, original edits and actual PNG/PDF
downloads. PDF is rasterized with the existing local PDFium tooling. User photos,
generated outputs, replay scripts, model/environment files and ledger are not
committed. The original ledger15 calls/$0.02431050 is checked by hash before/after.

Frontend selection UI is B's next step; the backend API can be exercised with
authenticated requests using the workflow above. Rendering success does not
establish aesthetic quality or improve the unchanged cutout model.

## Executed results

- Backend full:704 passed,43 skipped (explicit browser/model opt-ins).
- Latest photo-mode + editor-resilience tests:37 passed, including expiry410
  during source reads. Earlier recovery run:35 passed; request-shape mistakes
  in new tests and missing-source snapshot
  handling were corrected before the final full run.
- Actual isolated Chromium/API: both products switched cutout→original→cutout
  without new copy/analysis/processing dispatch; initial cached setup is distinct
  from transition costs. Style snapshots and upload bytes remained unchanged.
- All16 jjajang original templates and one additional espresso price_a rendered
  with transparentFalse, no measured invalid layout; the five small-card templates
  received no exceptions. 43 comparison images in the local gallery.
- Original v3 title/price edit, existing other assets, stale download rejection,
  actual bt-logistic-v1 ranking and PNG/A4 PDF downloads passed. Original v2 render,
  title edit and PNG/PDF/stale checks passed separately (`v2-check.json`).
- PDFium rendered the downloaded PDFs; embedded decoded image pixels equal PNG.
  The actual jjajang PDF rendering was visually inspected for text/price/photo
  presence and clipping. Cutout haze remains visible and is not repaired here.
- Subject_size remains unavailable for opaque originals, not guessed or hidden.
- Frontend is untouched; existing frontend and browser/release workflows run in CI.
- Known existing Starlette/AnyIO deprecation warning remains.

No operating server was started/restarted for these checks. TestClient apps and
their own Chromium/model workers exited after verification. Existing server and
tunnel are preserved. Paid ledger15/$0.02431050 hash remained unchanged.
