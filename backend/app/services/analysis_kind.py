"""Design-only hint from existing CLIP category scores; no new inference."""
import math
from app.schemas.analysis import ProductKindHint

def product_kind_hint(clip):
    if clip.status != 'available':
        return None
    scores = {}
    for cue in clip.cues:
        if cue.category != 'category' or cue.candidate_id not in {'food','drink','dessert','nonfood'}:
            continue
        score = cue.similarity
        if (type(score) not in (int,float) or not math.isfinite(score) or not -1 <= score <= 1
                or cue.candidate_id in scores):
            return None  # duplicate/invalid category evidence is ambiguous
        scores[cue.candidate_id] = score
    if len(scores) < 2:
        return None
    ordered = sorted(scores.items(), key=lambda p: (-p[1],p[0]))
    if ordered[0][1] == ordered[1][1]:
        return None
    return ProductKindHint(label=ordered[0][0], similarity=ordered[0][1], margin=ordered[0][1]-ordered[1][1])
