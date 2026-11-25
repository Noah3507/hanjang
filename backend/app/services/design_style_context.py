"""A-owned service boundary: immutable resolved B styles, never client CSS."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from app.services import design_style
from app.services.analysis_kind import product_kind_hint

@dataclass(frozen=True)
class PageStyle:
    inputs: design_style.StyleInput
    version: str
    kind: str
    kind_source: str
    accent_source: str
    background_source: str
    variables: tuple[tuple[str,str], ...]
    analysis_snapshot: str | None = None

    def css(self):
        return design_style.Style(self.version,self.kind,self.kind_source,self.accent_source,
                                  self.background_source,dict(self.variables)).css()

@dataclass(frozen=True)
class StyleBundle:
    pages: tuple[PageStyle, ...]

    def page(self, template_id):
        return next(p for p in self.pages if p.inputs.template_id == template_id)

    def snapshot(self, ids=None):
        return {p.inputs.template_id:asdict(p) for p in self.pages if ids is None or p.inputs.template_id in ids}

def resolve_bundle(record, asset, draft, template_ids):
    analysis = record.analyses.get(asset.asset_id)
    palette=();hint=None;analysis_snapshot=None
    # Do not use a previous photo's last_analysis fallback. Caller holds analysis/upload locks.
    if analysis is not None and analysis.status == 'completed' and analysis.source_asset_id == asset.asset_id:
        if analysis.palette.status == 'available':
            palette=tuple((c.hex,c.proportion) for c in analysis.palette.colors)
        hint=product_kind_hint(analysis.clip)
        analysis_snapshot=sha256(json.dumps({'asset':analysis.source_asset_id,'version':analysis.analysis_version,
            'clip':analysis.clip.model_dump(mode='json'),'palette':analysis.palette.model_dump(mode='json')},
            sort_keys=True,allow_nan=False).encode()).hexdigest()
    pages=[]
    for tid in template_ids:
        data=design_style.StyleInput(tid,draft.mood,draft.facts.product_name,palette,
                                    hint.label if hint else None,hint.margin if hint else None)
        style=design_style.resolve_style(data)
        pages.append(PageStyle(data,style.version,style.kind,style.kind_source,style.accent_source,
                               style.background_source,tuple(sorted(style.variables.items())),analysis_snapshot))
    return StyleBundle(tuple(pages))
