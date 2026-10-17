#!/usr/bin/env python3
"""Start the actual loopback CV backend; keep its generated token local to this host."""
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
def main():
    private = ROOT / '.private'
    private.mkdir(mode=0o700, exist_ok=True)
    token_file = private / 'device.token'
    if not token_file.exists():
        fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f: f.write(secrets.token_urlsafe(32))
    token = token_file.read_text().strip()
    if len(token) < 12: raise SystemExit('Invalid local device token')
    env = os.environ.copy()
    env['ARC_DEVICE_TOKEN'] = token
    env['ARC_ENABLE_POKER_ACTIONS'] = '0'
    # This launcher only starts CV; an API key in the parent shell does not enable billing.
    env.pop('OPENAI_API_KEY', None)
    print('CV server: http://127.0.0.1:8787', flush=True)
    print('Device token (enter on your phone; do not share): ' + token, flush=True)
    print('USB connection: run windows/03_CONNECT_PHONE.ps1 in another terminal.', flush=True)
    return subprocess.call([sys.executable, 'server.py'], cwd=ROOT/'server', env=env)
if __name__ == '__main__': raise SystemExit(main())
