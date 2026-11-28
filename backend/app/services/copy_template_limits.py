"""A-side reader of B's measured contract; advisory lengths, never fact truncation."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STRATEGIES = ('emotional', 'price', 'visual', 'brand')
FIELDS = ('headline', 'body', 'cta')


def load_template_limits(root=None):
    root = Path(root) if root is not None else ROOT
    folder = root/'templates/v3'
    files = sorted(folder.glob('*.html')) + [folder/n for n in ('price.css','collection.css','quality.css','limits.json')]
    try:
        signature = tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in files)
    except OSError:
        return None
    encoded = _load(str(root),signature)
    return json.loads(encoded) if encoded is not None else None


@lru_cache(maxsize=8)
def _load(root,signature):
    from app.services.template_v3 import VERSION,REGISTRY
    folder = Path(root)/'templates/v3'
    try:
        data = json.loads((folder/'limits.json').read_text(encoding='utf-8'))
        files = sorted(folder.glob('*.html')) + [folder/n for n in ('price.css','collection.css','quality.css')]
        digest = sha256()
        for path in files:
            digest.update(path.name.encode()+b'\0'+path.read_bytes()+b'\0')
        if (data['schema']!='hanjang-template-limits-1' or data['template_version']!=VERSION
            or data['source_sha256']!=digest.hexdigest() or set(data['templates'])!=set(REGISTRY)
            or set(data['strategies'])!=set(STRATEGIES)):
            return None
        strategies = {}
        for strategy in STRATEGIES:
            strategies[strategy] = {}
            for field in FIELDS:
                item = data['strategies'][strategy][field]
                if any(type(item[k]) is not int for k in ('soft','hard')) or not 0<item['soft']<=item['hard']:
                    return None
                ids = [tid for tid in REGISTRY if REGISTRY[tid]['strategy']==strategy]
                if any(item[k]!=min(data['templates'][tid][field][k] for tid in ids) for k in ('soft','hard')):
                    return None
                strategies[strategy][field] = {k:item[k] for k in ('soft','hard')}
        # Do not send a decorative-source hash to the model or invalidate copy
        # solely because CSS changed while the measured numeric limits stayed equal.
        return json.dumps({'schema':data['schema'],'counting':data['counting'],'strategies':strategies})
    except (OSError,ValueError,KeyError,TypeError):
        return None


def review_bound_lengths(variants,limits):
    if not limits:return []
    warnings = set()
    for variant in variants:
        for field,text in variant.ad_copy.model_dump().items():
            measured = limits['strategies'][variant.strategy][field]
            if len(text)>measured['hard']:warnings.add('COPY_TEMPLATE_HARD_LIMIT_REVIEW')
            elif len(text)>measured['soft']:warnings.add('COPY_TEMPLATE_SOFT_LIMIT_REVIEW')
    return sorted(warnings)
