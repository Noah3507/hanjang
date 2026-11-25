"""Cut-out photos sit on the poster (no box, soft shadow); whole photos become a rounded card."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / 'templates/v3'
KEPT_FILLS = {'brand_a', 'brand_b', 'brand_c', 'visual_b'}


def test_photo_slot_is_marked_only_for_transparent_photos():
    slots = {p.name: p.read_text(encoding='utf-8').count('class="photo') for p in V3.glob('*.html')}
    marked = '<div class="photo {{ photo_fit }}{{ " cutout" if transparent else " whole-photo" }}">'
    for name, count in slots.items():  # every template that draws its own photo slot marks cut-outs
        if count:
            assert (V3 / name).read_text(encoding='utf-8').count(marked) == count, name
    assert {n for n, c in slots.items() if c} >= {'price_a.html', 'price_d.html', 'collection.html'}


def test_cutout_rules():
    css = (V3 / 'quality.css').read_text(encoding='utf-8')
    rule = re.search(r'\.ad((?::not\(\.[a-z_]+\))+) \.photo\.cutout\{background:transparent!important\}', css)
    assert rule and set(re.findall(r':not\(\.([a-z_]+)\)', rule.group(1))) == KEPT_FILLS
    assert re.search(r'\.photo\.cutout img\{filter:drop-shadow\(', css)


def test_whole_photo_card_rules():
    css = (V3 / 'quality.css').read_text(encoding='utf-8')
    assert '.photo.whole-photo{background:transparent!important;border-color:transparent!important}' in css
    assert re.search(r'\.photo\.whole-photo img\{border-radius:\d+px;box-shadow:', css)
    # Border width stays (only its colour goes), so the renderer's photo geometry is unchanged.
    assert 'border:0' not in css.split('.photo.whole-photo')[1].split('}')[0]


def test_photo_state_classes_are_not_used_by_other_elements():
    """The photo's state classes must not collide with existing classes (".original" is the original price)."""
    css = ''.join((V3 / n).read_text(encoding='utf-8') for n in ('price.css', 'collection.css', 'quality.css'))
    for state in ('cutout', 'whole-photo'):
        uses = re.findall(r'([^{}]*\.%s\b[^{]*)\{' % re.escape(state), css)
        assert uses and all('.photo.' + state in u for u in uses), state
