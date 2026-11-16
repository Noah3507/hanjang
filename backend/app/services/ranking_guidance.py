"""Display policy from the active local bundle; never infer model confidence."""
import json
import math


def close_call_gap(ranker, ranking):
    if ranking is None or ranking.source != 'model':
        return None
    model_file = getattr(ranker, 'model_file', None)
    if model_file is None:
        return None
    try:
        raw = (model_file.parent / 'manifest.json').read_bytes()
        if len(raw) > 1_000_000:
            return None
        manifest = json.loads(raw)
        gap = manifest.get('close_call_score_gap')
        if (manifest.get('model_version') != ranking.model_version
                or isinstance(gap, bool) or not isinstance(gap, (int, float))
                or not math.isfinite(gap) or gap <= 0):
            return None
        return gap
    except (OSError, ValueError, TypeError, AttributeError):
        return None
