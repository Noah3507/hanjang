"""Conservative checks at immutable fact boundaries, not a Korean grammar engine."""
import re
from app.services.copy_contract import CopyFailure

PARTICLE = re.compile(r'(으로|로|을|를|은|는|이|가|과|와)(?:만|도|는|부터|까지)?(?=$|[\s,.!?…:;·])')
PAIRS = {'을': ('을', '를'), '를': ('을', '를'),
         '은': ('은', '는'), '는': ('은', '는'),
         '이': ('이', '가'), '가': ('이', '가'),
         '과': ('과', '와'), '와': ('과', '와')}


def check_fact_particles(text, facts):
    """Inspect final text, including literals that did not use placeholders.

    Never change a fact or guess the pronunciation of digits/Latin brand names.
    Uncertain attached particles require review, without an automatic paid retry.
    """
    for key in ('price_text', 'product_name'):
        fact = facts[key]
        for occurrence in re.finditer(re.escape(fact), text):
            remainder = text[occurrence.end():]
            gap = len(remainder) - len(remainder.lstrip())
            particle = PARTICLE.match(remainder.lstrip())
            if particle is None:
                continue
            ending = fact.rstrip()[-1]
            if not '\uac00' <= ending <= '\ud7a3':
                raise CopyFailure('COPY_PARTICLE_REVIEW_REQUIRED')
            jong = (ord(ending) - 0xAC00) % 28
            actual = particle.group(1)
            expected = ('으로' if jong not in (0, 8) else '로') if actual in ('으로', '로') else PAIRS[actual][0 if jong else 1]
            if gap or fact != fact.rstrip() or actual != expected:
                raise CopyFailure('COPY_PARTICLE_INVALID')
