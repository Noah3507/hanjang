"""Background-removal cleanup: faint residue goes, the product (with plates and separate pieces) stays."""
from io import BytesIO

import numpy as np
import cv2
import pytest
from PIL import Image, ImageDraw, ImageFilter

from app.services.photo_matte import FAINT_ALPHA, clean_alpha
from app.services.photo_processor import process_photo


def disc(alpha, box, value):
    image = Image.fromarray(alpha)
    ImageDraw.Draw(image).ellipse(box, fill=value)
    return np.asarray(image).copy()


def test_far_haze_goes_and_the_product_stays():
    haze = np.asarray(Image.fromarray(disc(np.zeros((400, 400), np.uint8), (20, 20, 380, 380), 90))
                      .filter(ImageFilter.GaussianBlur(20))).copy()
    alpha = disc(haze, (150, 150, 250, 250), 255)
    cleaned = clean_alpha(alpha)
    product = alpha == 255
    assert (cleaned[product] == 255).all()   # product untouched
    assert cleaned[30:60, 30:60].max() == 0 and alpha[30:60, 30:60].max() > 0  # far haze removed


def test_faint_pixels_go_even_next_to_the_product():
    alpha = disc(np.zeros((300, 300), np.uint8), (100, 100, 200, 200), 255)
    alpha[90:100, 140:160] = FAINT_ALPHA - 1
    alpha[201:203, 140:160] = FAINT_ALPHA + 20  # a soft edge within 3 % of the product's size stays
    alpha[230:233, 140:160] = FAINT_ALPHA + 20  # the same softness farther away goes
    cleaned = clean_alpha(alpha)
    assert cleaned[90:100, 140:160].max() == 0
    assert (cleaned[201:203, 140:160] == FAINT_ALPHA + 20).all()
    assert cleaned[230:233, 140:160].max() == 0


def test_plates_and_separate_pieces_stay():
    alpha = disc(np.zeros((400, 400), np.uint8), (40, 60, 360, 340), 255)  # an opaque plate
    for x in (60, 160, 260):
        alpha = disc(alpha, (x, 360, x + 60, 395), 255)  # separate pieces below it
    assert (clean_alpha(alpha) == alpha).all()


def test_no_solid_part_leaves_alpha_unchanged():
    alpha = np.full((50, 50), 100, np.uint8)
    assert (clean_alpha(alpha) == alpha).all()


def test_process_photo_changes_only_alpha():
    image = Image.new('RGB', (200, 200), (120, 80, 40))
    ImageDraw.Draw(image).rectangle((60, 60, 140, 140), fill=(200, 120, 42))
    buffer = BytesIO()
    image.save(buffer, 'PNG')
    mask = Image.new('L', (200, 200), 0)
    ImageDraw.Draw(mask).rectangle((60, 60, 140, 140), fill=255)
    ImageDraw.Draw(mask).rectangle((0, 0, 30, 30), fill=90)  # stray residue in a corner
    result = process_photo(buffer.getvalue(), lambda rgb: mask)
    with Image.open(BytesIO(result.png)) as out:
        out = out.convert('RGBA')
        assert out.getpixel((100, 100)) == (200, 120, 42, 255)
        assert out.getpixel((10, 10))[3] == 0
    with Image.open(BytesIO(result.mask_png)) as cleaned_mask:
        assert cleaned_mask.getpixel((10, 10)) == 0 and cleaned_mask.getpixel((100, 100)) == 255


def test_tiny_disconnected_opaque_piece_is_not_noise_by_size_alone():
    alpha=np.zeros((200,200),np.uint8)
    alpha[50:150,50:150]=255
    alpha[10,10]=255
    cleaned=clean_alpha(alpha)
    assert cleaned[10,10]==255
    assert np.array_equal(cleaned[alpha>=128],alpha[alpha>=128])


def test_empty_and_transparent_masks_are_safe_and_deterministic():
    for shape in ((0,0),(1,1),(80,100)):
        alpha=np.zeros(shape,np.uint8)
        before=alpha.copy();first=clean_alpha(alpha);second=clean_alpha(alpha)
        assert np.array_equal(first,second) and np.array_equal(alpha,before)
        assert first.shape==shape and first.dtype==np.uint8


def test_cleanup_failure_keeps_existing_failure_contract(monkeypatch):
    from app.services import photo_processor
    image=Image.new('RGB',(300,300),(120,80,40));stream=BytesIO();image.save(stream,'PNG')
    def fail(alpha):raise RuntimeError('internal detail')
    monkeypatch.setattr(photo_processor,'clean_alpha',fail)
    result=process_photo(stream.getvalue(),lambda image:Image.new('L',image.size,255))
    assert result.png is None and result.warnings==['PHOTO_PROCESSING_FAILED']


def test_all_rgb_values_and_input_alpha_are_preserved_without_resize():
    rng=np.random.default_rng(42)
    source=rng.integers(0,256,(256,320,4),dtype=np.uint8)
    stream=BytesIO();Image.fromarray(source).save(stream,'PNG');raw=stream.getvalue()
    mask=Image.new('L',(320,256),0);ImageDraw.Draw(mask).rectangle((80,60,240,200),fill=255)
    result=process_photo(raw,lambda image:mask)
    output=np.asarray(Image.open(BytesIO(result.png)))
    assert np.array_equal(output[:,:,:3],source[:,:,:3])
    assert np.all(output[:,:,3]<=source[:,:,3])
    assert np.array_equal(np.asarray(Image.open(BytesIO(raw))),source)


@pytest.mark.parametrize('radius',[2,16,17,32,64])
def test_fast_zone_is_pixel_exact_to_b_original_ellipse(radius):
    from app.services.photo_matte import near_zone
    core=np.zeros((240,280),bool);core[20:40,80:91]=True;core[180:210,230:260]=True;core[0,0]=True
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(2*radius+1,2*radius+1))
    original=cv2.dilate(core.astype(np.uint8),kernel).astype(bool)
    assert np.array_equal(near_zone(core,radius),original)
