"""Validate explicit commercial facts. Never format/rewrite raw user prices."""
from decimal import Decimal, ROUND_HALF_UP
import re
from datetime import date
from app.services.render_execution import RenderFailure


def amount(raw):
    m = re.fullmatch(r'\s*(?:(USD|KRW|EUR|[$€])\s*)?([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)\s*(원|USD|KRW|EUR)?\s*', raw)
    if not m:
        raise RenderFailure('V3_PROMOTION_REVIEW_REQUIRED')
    a, number, b = m.groups()
    currencies = {'원':'KRW', '$':'USD', '€':'EUR'}
    a, b = currencies.get(a,a), currencies.get(b,b)
    if a and b and a != b:
        raise RenderFailure('V3_PROMOTION_INVALID')
    return Decimal(number.replace(',','')), a or b


def validate_promotion(data):
    if data.discount_text and not data.original_price:
        raise RenderFailure('V3_PROMOTION_INVALID')
    if data.original_price:
        price, currency = amount(data.price_text)
        original, original_currency = amount(data.original_price)
        if currency != original_currency or original <= 0 or price < 0 or price >= original:
            raise RenderFailure('V3_PROMOTION_INVALID')
        if data.discount_text:
            m = re.fullmatch(r'([0-9]+(?:\.[0-9]{1,2})?)%', data.discount_text)
            if not m:
                raise RenderFailure('V3_PROMOTION_INVALID')
            supplied = Decimal(m[1])
            places = len(m[1].split('.')[1]) if '.' in m[1] else 0
            expected = ((original-price)*100/original).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
            if supplied != expected or supplied <= 0 or supplied > 100:
                raise RenderFailure('V3_PROMOTION_INVALID')
    if data.period_text:
        m = re.fullmatch(r'(\d{4})[.-](\d{2})[.-](\d{2})\s*[~–]\s*(?:(\d{4})[.-])?(\d{2})[.-](\d{2})', data.period_text)
        try:
            if not m:raise ValueError()
            a,b,c,y,e,f=m.groups()
            if date(int(a),int(b),int(c)) > date(int(y or a),int(e),int(f)):
                raise ValueError()
        except ValueError:
            raise RenderFailure('V3_PROMOTION_INVALID') from None
