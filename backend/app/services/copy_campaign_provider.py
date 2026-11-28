"""Bounded two-call campaign recipe; uses an injected service budget, never experiment limits."""
from app.schemas.upload import InputDraft
from app.services.copy_openai import OpenAICopyProvider
from app.services.copy_contract import CopyFailure, ProviderResult, ProviderUsage
from app.services.copy_campaign import MODEL, instructions_for
from app.services.copy_prompt import input_bound
from app.services.copy_intensive import IntensiveCopyExperiment, ExperimentRequest
from app.services.copy_validation import validate_copy
import json,re


def correct_product_particle(candidate,payload):
    """Correct only a known Hangul allomorph OUTSIDE the immutable placeholder.

    Legacy validators stay unchanged. Never guess Latin/digit pronunciation,
    touch literal facts, trim prices, repair price particles or rewrite sentences.
    """
    value=json.loads(json.dumps(candidate))
    product=payload.get('product_name','')
    if not product or product!=product.rstrip() or not '\uac00'<=product[-1]<='\ud7a3':return value
    from app.services.copy_particles import PARTICLE,PAIRS
    jong=(ord(product[-1])-0xac00)%28
    for variant in value.get('variants',[]):
        for field in ('headline','body','cta'):
            text=variant.get('copy',{}).get(field)
            if not isinstance(text,str):continue
            token='[[product_name]]'
            def replace(match):
                suffix=match.group(1);particle=PARTICLE.match(suffix)
                if particle is None:return match.group(0)
                actual=particle.group(1)
                expected=('으로' if jong not in (0,8) else '로') if actual in ('으로','로') else PAIRS[actual][0 if jong else 1]
                return token+expected+suffix[len(actual):]
            variant['copy'][field]=re.sub(re.escape(token)+r'([^\[]*)',replace,text)
    return value


def omit_duplicate_fact_fields(candidate,payload):
    """Only isolated price tokens / whole body/CTA facts with an independent slot.

    Never truncate arbitrary prose, alter a fact/particle or remove a fact
    when any template lacks its independent slot. Raw SDK responses stay intact.
    """
    value=json.loads(json.dumps(candidate))
    for variant in value.get('variants',[]):
        slots=payload.get('displayed_facts_by_strategy',{}).get(variant.get('strategy'),[])
        if 'price_text' in slots:
            for field in ('headline','body','cta'):
                text=variant.get('copy',{}).get(field)
                if isinstance(text,str):
                    # Only an isolated placeholder token, never a literal price,
                    # attached particle, user fact or arbitrary sentence fragment.
                    without=re.sub(r'(?<!\S)\[\[price_text\]\](?: +|$)','',text).rstrip()
                    if without and without!=text:variant['copy'][field]=without
        for field in ('body','cta'):
            text=variant.get('copy',{}).get(field)
            if any(text in (f'[[{key}]]',payload.get(key)) for key in slots):
                variant['copy'][field]=''
    return value


class CampaignCopyProvider(OpenAICopyProvider):
    def generate(self, payload):
        if not self.allow_paid:raise CopyFailure('COPY_PAID_DISABLED')
        if not self.api_key:raise CopyFailure('COPY_KEY_MISSING')
        if self.model!=MODEL:raise CopyFailure('COPY_MODEL_NOT_APPROVED')
        if input_bound(payload,instructions_for(payload))>12000:raise CopyFailure('COPY_INPUT_LIMIT')
        if self.client is None:
            import openai
            self.client=openai.OpenAI(api_key=self.api_key,base_url='https://api.openai.com/v1',timeout=60.,max_retries=0)
        if getattr(self.client,'max_retries',0)!=0:raise CopyFailure('COPY_PROVIDER_CONFIG_INVALID')
        draft=InputDraft.model_validate({'facts':{k:payload[k] for k in ('store_name','product_name','price_text')},
            'mood':payload['mood'],'product_features':payload['product_features'],'ad_goal':payload['ad_goal'],
            **({'facts':{**{k:payload[k] for k in ('store_name','product_name','price_text')},'address':payload['address']},'use_address_for_copy':True} if payload.get('address') else {})})
        engine=IntensiveCopyExperiment(self.budget.path,self.client,budget=self.budget,
            instructions_resolver=instructions_for,recipe_tag=self.prompt_version)
        request=ExperimentRequest(payload,model=MODEL,direction='campaign',reasoning='low',mode='pool')
        pool=engine.generate(request,lambda *a:None)
        try:sets=json.loads(pool.text)['sets']
        except (ValueError,KeyError,TypeError):raise CopyFailure('COPY_SCHEMA_INVALID',usage=pool.usage) from None
        eligible=[];changes=[];warnings=set()
        if not isinstance(sets,list) or len(sets)!=2:raise CopyFailure('COPY_SCHEMA_INVALID',usage=pool.usage)
        for candidate in sets:
            try:
                corrected=correct_product_particle(candidate,payload)
                cleaned=omit_duplicate_fact_fields(corrected,payload)
                validate_copy(json.dumps(cleaned,ensure_ascii=False),draft)
                by_strategy={}
                for variant in cleaned['variants']:
                    strategy=variant['strategy'];flags=set()
                    before=next(v['copy'] for v in candidate['variants'] if v['strategy']==strategy)
                    middle=next(v['copy'] for v in corrected['variants'] if v['strategy']==strategy)
                    if middle!=before:flags.add('COPY_PRODUCT_PARTICLE_ADJUSTED')
                    if variant['copy']!=middle:flags.add('COPY_DUPLICATE_FACT_OMITTED')
                    by_strategy[strategy]=flags
                eligible.append(cleaned)
                changes.append(by_strategy)
            except (CopyFailure,TypeError,AttributeError):pass
        if not eligible:raise CopyFailure('COPY_EXPERIMENT_NO_VALID_CANDIDATES',usage=pool.usage)
        total=pool.usage
        if len(eligible)==1:
            selected={s:0 for s in ('emotional','price','visual','brand')}
        else:
            from dataclasses import replace
            try:
                choice=engine.generate(replace(request,mode='choose',prior={'sets':eligible}),lambda *a:None)
            except CopyFailure as error:
                u=error.usage or ProviderUsage()
                raise CopyFailure(error.code,usage=ProviderUsage(
                    (total.input_tokens or 0)+(u.input_tokens or 0),(total.output_tokens or 0)+(u.output_tokens or 0),
                    (total.estimated_cost_usd or 0)+(u.estimated_cost_usd or 0),u.reserved_unknown_cost_usd)) from None
            total=ProviderUsage(total.input_tokens+choice.usage.input_tokens,total.output_tokens+choice.usage.output_tokens,total.estimated_cost_usd+choice.usage.estimated_cost_usd)
            try:selected=json.loads(choice.text)['selected']
            except (ValueError,KeyError,TypeError):raise CopyFailure('COPY_SCHEMA_INVALID',usage=total) from None
        strategies=('emotional','price','visual','brand')
        if not isinstance(selected,dict) or set(selected)!=set(strategies) or any(type(v) is not int or not 0<=v<len(eligible) for v in selected.values()):
            raise CopyFailure('COPY_SCHEMA_INVALID',usage=total)
        from app.services.copy_quality import review_ad_copy
        for strategy in strategies:
            compatible=[]
            for index,candidate in enumerate(eligible):
                raw=next(v for v in candidate['variants'] if v['strategy']==strategy)
                from app.schemas.copy import Variant
                variant=Variant.model_validate(raw)
                if 'COPY_GOAL_REVIEW' not in review_ad_copy([variant],draft.ad_goal,profile='campaign',draft=draft):compatible.append(index)
            if compatible and selected[strategy] not in compatible:selected[strategy]=compatible[0]
        final={'variants':[next(v for v in eligible[selected[s]]['variants'] if v['strategy']==s) for s in strategies]}
        for strategy in strategies:warnings.update(changes[selected[strategy]][strategy])
        text=json.dumps(final,ensure_ascii=False)
        try:validated=validate_copy(text,draft)
        except CopyFailure as error:
            raise CopyFailure(error.code,usage=total,reason=error.reason) from None
        from app.services.copy_template_limits import review_bound_lengths
        warnings.update(review_bound_lengths(validated.variants,payload.get('template_copy_limits')))
        return ProviderResult(text,total,tuple(sorted(warnings)))
