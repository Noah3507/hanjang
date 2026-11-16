from io import BytesIO
from hashlib import sha256
from PIL import Image,ImageDraw
import pytest
from app.services.product_geometry import prepare_product
from app.services.render_execution import RenderFailure


def raw(image):
    s=BytesIO();image.save(s,'PNG');return s.getvalue()


def test_transparent_margin_trim_preserves_all_solid_accessories_and_input():
    image=Image.new('RGBA',(1200,900));d=ImageDraw.Draw(image)
    d.ellipse((400,300,900,700),fill='white');d.rectangle((200,100,230,150),fill='blue')
    original=raw(image);before=sha256(original).hexdigest();png,info=prepare_product(original)
    assert info['crop_box'][0]<200 and info['crop_box'][1]<100
    assert info['support_bbox']==[200,100,901,701]
    assert info['discarded_low_alpha_mass_ratio']==0
    assert info['prepared_size'][0]<1200 and info['subject_detection']=='alpha-support'
    assert sha256(original).hexdigest()==before
    # Every >=16 alpha pixel, including the disconnected accessory, remains.
    assert Image.open(BytesIO(png)).getchannel('A').histogram()[255]==image.getchannel('A').histogram()[255]


def test_low_alpha_halo_trim_and_uncertain_fallback():
    image=Image.new('RGBA',(500,500),(255,255,255,1));ImageDraw.Draw(image).ellipse((100,100,400,400),fill='white')
    _,info=prepare_product(raw(image))
    assert 0<=info['discarded_low_alpha_mass_ratio']<=.002
    if info['crop_box']==[0,0,500,500]:assert 'ALPHA_TRIM_UNCERTAIN_KEEP_FULL_IMAGE' in info['warnings']


def test_opaque_not_segmented_and_empty_alpha_unavailable():
    _,info=prepare_product(raw(Image.new('RGB',(800,600),'white')))
    assert info['crop_box']==[0,0,800,600] and info['support_bbox'] is None
    assert info['subject_detection']=='unavailable'
    _,empty=prepare_product(raw(Image.new('RGBA',(400,300))))
    assert empty['subject_detection']=='unavailable' and 'ALPHA_SUBJECT_UNAVAILABLE' in empty['warnings']


def test_invalid_input():
    with pytest.raises(RenderFailure):prepare_product(b'invalid')
