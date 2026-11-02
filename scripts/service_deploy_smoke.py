"""Read-only health/readiness check. Remote requests require an explicit gate."""
import argparse
import base64
import json
import os
import urllib.request
import urllib.error
from urllib.parse import urlparse


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        # Do not forward an origin credential to a redirected address.
        return None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',default='http://127.0.0.1:8014')
    parser.add_argument('--allow-remote',action='store_true')
    args=parser.parse_args();url=urlparse(args.url)
    if url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        print('Use an origin URL without credentials/path/query.');return 2
    local=url.hostname in ('127.0.0.1','localhost','::1')
    if not local and (not args.allow_remote or url.scheme!='https'):
        print('Remote HTTPS smoke requires prior deployment approval and --allow-remote.');return 2
    if url.scheme not in ('http','https'):return 2
    headers={};password=os.environ.get('HANJANG_PRESENTATION_PASSWORD')
    if password:
        value=os.environ.get('HANJANG_PRESENTATION_USER','presenter')+':'+password
        headers['Authorization']='Basic '+base64.b64encode(value.encode()).decode()
    try:
        opener=urllib.request.build_opener(NoRedirect())
        for route in ('/health','/ready'):
            with opener.open(urllib.request.Request(args.url.rstrip('/')+route,headers=headers),timeout=10) as response:
                body=json.load(response)
                if response.status!=200 or body.get('status') not in ('ok','ready'):raise ValueError()
        print('Health/readiness passed (no inference or paid request).');return 0
    except Exception:
        print('Smoke failed: check authentication, readiness or network. No response contents logged.');return 1


if __name__=='__main__':raise SystemExit(main())
