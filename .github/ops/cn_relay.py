"""Encrypt a freshly supplied code for an already waiting CN session."""
import json
import os
from pathlib import Path
import sys
import time
from cn_protocol import GitHub, waiting_request, code_payload, encrypt_payload

def main():
    try:
        auth=os.environ['CN_AUTH_RUN'];nonce=os.environ['CN_AUTH_NONCE'];commit=os.environ['GITHUB_SHA']
        api=GitHub(os.environ['GH_TOKEN']);waiting=waiting_request(api,auth,nonce,commit)
        code=os.environ.get('APPLE_CN_2FA_CODE','').strip()
        value={'schema':'cn-live-code-v1','auth_run':auth,'commit':commit,'nonce':nonce,'issued_at':int(time.time()),'code':code}
        code_payload(value,waiting)
        output=Path('cn-code-out');output.mkdir(mode=0o700)
        recipient=json.loads(Path('config/delivery.json').read_text())['recipient']
        encrypt_payload(str(Path(sys.argv[1]).resolve()),output/'code.age',value,recipient)
        print('{"schema":"cn-live-code-relay-v1","status":"encrypted_for_waiting_session"}')
        return 0
    except Exception:
        print('{"schema":"cn-live-code-relay-v1","status":"relay_rejected"}')
        return 2
if __name__=='__main__':raise SystemExit(main())
