"""Built frontend + one backend on loopback. Never starts a tunnel or installs anything."""
import argparse
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8014)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    from app.config import Settings
    from app.services.runtime_health import inspect_runtime
    from app.services.presentation import PresentationGateway
    settings=Settings(frontend_dist=Path(os.environ.get('HANJANG_FRONTEND_DIST',ROOT/'frontend/dist')))
    # Validate credentials before binding or constructing services. Never print settings/secrets.
    PresentationGateway(None,settings)
    result=inspect_runtime(settings)
    if result['status']!='ready':
        print('Readiness failed: '+', '.join(k for k,v in result['checks'].items() if not v),file=sys.stderr)
        return 1
    if args.check_only:
        print('Configuration readiness OK (model inference and paid API not performed).')
        print(f'Copy provider={settings.copy_provider}; model={settings.copy_model}; paid_enabled={settings.copy_allow_paid}; '
              f'cumulative_requests={settings.copy_max_requests}; budget_usd={settings.copy_budget_usd:.2f}; app_retries={settings.copy_max_retries}.')
        return 0
    from app.main import create_app
    import uvicorn
    app=PresentationGateway(create_app(settings),settings)
    uvicorn.run(app,host='127.0.0.1',port=args.port,workers=1,access_log=False,proxy_headers=False)
    return 0


if __name__=='__main__':raise SystemExit(main())
