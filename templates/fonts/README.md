# Bundled Korean font

Noto Sans KR Regular, Noto Sans CJK release **Sans2.004**, 4,644,748 bytes.

- Source: https://github.com/notofonts/noto-cjk/tree/Sans2.004/Sans/SubsetOTF/KR
- Download: https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/Sans/SubsetOTF/KR/NotoSansKR-Regular.otf
- SHA256: `69975a0ac8472717870aefeab0a4d52739308d90856b9955313b2ad5e0148d68`
- License: SIL Open Font License 1.1, bundled unchanged in [OFL.txt](OFL.txt).

The regular font is embedded locally as a data URI. The existing v2 renderer is unchanged.
The opt-in v3 renderer also bundles the actual **Noto Sans KR Bold** from the same
Sans2.004 release, under the unchanged OFL.txt:

- Source/download: https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/Sans/SubsetOTF/KR/NotoSansKR-Bold.otf
- SHA256: `5a6ceb287ed2fc6cfc6213144ebea68cbd94b20fc9eb873d8486493bf02d9bda`
- v3 uses exact 400/700 faces and disables synthesized weights.

Metadata records computed CSS weight and the actually used custom face. No CDN,
runtime font download, or OS font dependency is required. Unsupported glyph fallback
is rejected with RENDER_UNSUPPORTED_GLYPH. These are licensed application assets.
