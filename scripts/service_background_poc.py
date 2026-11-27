"""One explicit text-only image call. No user image or business facts accepted."""
from pathlib import Path
from hashlib import sha256
import argparse,json,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.services.background_provider import MODEL,THEMES,OpenAIBackgroundProvider

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--theme',choices=list(THEMES),required=True)
    p.add_argument('--id',required=True)
    p.add_argument('--approved-paid-call',action='store_true',required=True)
    args=p.parse_args()
    if not args.id.replace('-','').isalnum():raise ValueError('Invalid local run id')
    out=ROOT/'artifacts/ai-background-poc';out.mkdir(parents=True,exist_ok=True)
    folder=out/args.id;folder.mkdir(exist_ok=False)
    ledger=ROOT/'artifacts/copy-usage/ledger.json';before=sha256(ledger.read_bytes()).hexdigest()
    if before!='43d7e939de8cea8d82357188ce528ae97f1e087726248605518e3ce538834084':
        raise ValueError('LLM ledger differs from approved baseline; stop before paid request')
    def capture(arguments,response):
        (folder/'request.json').write_text(json.dumps(arguments,ensure_ascii=False,indent=2),encoding='utf-8')
        if response is not None:(folder/'response.json').write_text(response.model_dump_json(indent=2),encoding='utf-8')
    import openai
    settings=Settings();started=time.perf_counter();result={'theme':args.theme,'model':MODEL,'automatic_retries':0,'status':'failed'}
    with openai.OpenAI(api_key=settings.openai_api_key.get_secret_value(),base_url='https://api.openai.com/v1',max_retries=0,timeout=180.) as client:
        provider=OpenAIBackgroundProvider(client,out/'image-ledger.json',allow_paid=True)
        try:
            reply=provider.generate(args.theme,args.id,capture)
            (folder/'background.png').write_bytes(reply.png)
            result.update(status='generated',sha256=reply.sha256,cost_usd=reply.cost_usd,call_id=reply.call_id)
        except RuntimeError as e:result['error']=str(e)
    if sha256(ledger.read_bytes()).hexdigest()!=before:
        raise ValueError('LLM ledger changed during experiment; stop')
    result.update(seconds=time.perf_counter()-started,llm_ledger_unchanged=True)
    (folder/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['status']=='generated' else 1

if __name__=='__main__':sys.exit(main())
