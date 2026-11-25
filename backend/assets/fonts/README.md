# Offline v3 fonts

Unmodified official font files, pinned at acquisition (2026-11-25). These are
application assets, not user uploads or ML weights. Existing Noto Sans KR assets
remain in `templates/fonts/`; no B-owned template files are changed here.

| CSS family | File | Actual variable wght range | Source |
| --- | --- | --- | --- |
| `Noto Serif KR` | `NotoSerifKR-VF.ttf` | 200–900 | [Google Fonts, pinned commit](https://github.com/google/fonts/tree/6ebe737e44fd64ee736bbc6feed6136a6dbfd222/ofl/notoserifkr) |
| `Pretendard` | `PretendardVariable.ttf` | 45–930 | [Author's v1.3.9 release tree](https://github.com/orioncactus/pretendard/tree/v1.3.9/packages/pretendard/dist/public/variable) |

Both use SIL OFL 1.1. Commercial use, application bundling, redistribution and
embedding are permitted under the accompanying license/copyright
notices (`NotoSerifKR-OFL.txt`, `Pretendard-OFL.txt`). Do not sell the fonts by
themselves, remove notices, or rename modified fonts to reserved names. No font
conversion/subsetting/modification was performed. Font binaries are committed so
Windows and Linux CI use the same bytes without installation/CDN/network access.
`manifest.json` records exact SHA-256 hashes, MIME types and CSS weight ranges.
Internal font versions: Noto `2.003-H1`; Pretendard `1.309` (release v1.3.9).
License wording is preserved; one upstream trailing space was removed.

## B's CSS integration contract

In B-owned v3 stylesheets, use:

```css
/* Emotional, after B's layout review */
font-family: 'Noto Serif KR', HanjangNoto, sans-serif;
/* Price / Brand, after B's layout review */
font-family: Pretendard, HanjangNoto, sans-serif;
```

Choose weights within the manifest range; conventional 400/700 are tested.
Visual retains its existing `HanjangNoto` setting. A does not apply these choices
to production templates. The renderer finds named families in the combined v3
CSS and embeds only those faces plus the existing fallback. Keep family names
literal in these stylesheets, rather than injecting a family only in HTML.
No external CSS import is needed. `font-synthesis:none` remains in B's CSS.

All four manifest assets are checksum checked, including inactive primary faces.
Missing/corrupt files cause `RENDER_FONT_UNAVAILABLE`, never a silent replacement
of a missing primary asset. Individual unsupported primary glyphs may use bundled
HanjangNoto; the established Noto input coverage/emoji policy is not broadened.
Chromium waits for loading and rejects error states, non-custom OS fallback and
empty font evidence. `actual_fonts` records CDP glyph usage. Variable Noto's CDP
base family is `Noto Serif KR ExtraLight`; that name alone does not describe the
selected weight. CSS computed weight and the font's actual wght axis are also
verified. Byte fingerprints fence v3 cache/edit/ranking/download reuse.

## Verification

```powershell
$env:RUN_RENDER_TESTS='1'
.\.venv\Scripts\python.exe -m pytest tests/service/test_render_fonts.py tests/service/test_designs.py
```

No runtime download or paid API is involved.
