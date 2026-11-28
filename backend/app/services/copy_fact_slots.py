"""Conservative intersection of actual v2/v3 independent fact fields."""
from html.parser import HTMLParser
from pathlib import Path
from functools import lru_cache
from jinja2 import Environment,FileSystemLoader,StrictUndefined,select_autoescape

FIELDS=('store_name','product_name','price_text')


class FactFields(HTMLParser):
    def __init__(self):super().__init__();self.fields=set()
    def handle_starttag(self,tag,attrs):
        value=dict(attrs).get('data-field')
        if value in FIELDS:self.fields.add(value)


def common_fields(pages):
    result=set(FIELDS)
    for page in pages:
        parser=FactFields();parser.feed(page);result &= parser.fields
    return [key for key in FIELDS if key in result] if pages else []


def displayed_fact_slots():
    root=Path(__file__).resolve().parents[3]/'templates'
    files=sorted([*root.glob('*.html'),*(root/'v3').glob('*.html')])
    signature=tuple((str(p.relative_to(root)),p.stat().st_mtime_ns,p.stat().st_size) for p in files)
    return {strategy:list(fields) for strategy,fields in _slots(signature)}


@lru_cache(maxsize=8)
def _slots(signature):
    from app.services.template_v3 import TemplateInput,REGISTRY
    root=Path(__file__).resolve().parents[3]/'templates'
    data=TemplateInput('STORE','PRODUCT','PRICE','HEADLINE','BODY','CTA')
    env=Environment(loader=FileSystemLoader(root),undefined=StrictUndefined,autoescape=select_autoescape(['html']))
    v3=Environment(loader=FileSystemLoader(root/'v3'),undefined=StrictUndefined,autoescape=select_autoescape(['html']))
    result={}
    for strategy in ('emotional','price','visual','brand'):
        try:
            pages=[env.get_template(strategy+'.html').render(css='',texts=data.text_values(),strategy=strategy,mood='warm',photo='data:image/png;base64,')]
            for tid in REGISTRY:
                if REGISTRY[tid]['strategy']==strategy:
                    for transparent in (True,False):
                        pages.append(v3.get_template(tid+'.html').render(css='',data=data,photo='data:image/png;base64,',photo_fit='contain',transparent=transparent,template_id=tid))
            result[strategy]=common_fields(pages)
        except Exception:
            result[strategy]=[]  # Never promise missing facts on unknown templates.
    return tuple((key,tuple(value)) for key,value in result.items())
