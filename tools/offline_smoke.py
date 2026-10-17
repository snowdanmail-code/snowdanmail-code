#!/usr/bin/env python3
"""Real HTTP integration smoke test with synthetic JPEG; no internet, GPT, or cash actions."""
import base64
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TOKEN = 'v21-synthetic-smoke-only-token'
JPEG = b'\xff\xd8' + b'a-lab-frame-not-a-real-screen' + b'\xff\xd9'

def fetch(url, payload=None, token=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if token: headers['X-Device-Token'] = token
    req = Request(url, data=data, headers=headers, method='POST' if payload is not None else 'GET')
    try:
        with urlopen(req,timeout=2) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        return error.code, json.loads(error.read())


def main():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        port = s.getsockname()[1]
    env=os.environ.copy()
    env['ARC_DEVICE_TOKEN'] = TOKEN
    env['ARC_PORT'] = str(port)
    env['ARC_ENABLE_POKER_ACTIONS'] = '0'
    env.pop('OPENAI_API_KEY',None)
    proc = subprocess.Popen([sys.executable,'server.py'],cwd=ROOT/'server',env=env,
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    base=f'http://127.0.0.1:{port}'
    try:
        for _ in range(60):
            if proc.poll() is not None:
                raise RuntimeError(f'Backend failed: code {proc.returncode}')
            try:
                code,health=fetch(base+'/health')
                break
            except (URLError, TimeoutError):
                time.sleep(0.1)
        else: raise TimeoutError('Backend did not start')
        assert code==200 and health['actions_enabled'] is False
        code,_=fetch(base+'/diagnostics/ping')
        assert code==401, code
        code,ping=fetch(base+'/diagnostics/ping',token=TOKEN)
        assert code==200 and ping['mode']=='offline_connection_diagnostic', (code,ping)
        assert ping['action'] is None and ping['money_actions_enabled'] is False
        assert ping['uses_openai_api'] is False and ping['image_processed'] is False
        payload={'request':'describe','image_base64':base64.b64encode(JPEG).decode('ascii')}
        code,_=fetch(base+'/analyze',payload)
        assert code==401, code
        code,out=fetch(base+'/analyze',payload,TOKEN)
        assert code==200 and out['mode']=='demo' and out['action'] is None, (code,out)
        code,blocked=fetch(base+'/tap',payload,TOKEN)
        assert code==404, (code,blocked)
        draw={'request':'math_draw_odds','hero_cards':['Ah','Kh'],
              'board_cards':['Qh','Jh','2c'], 'outs_cards':['3h','4h']}
        code,odds=fetch(base+'/math/draw-odds',draw,TOKEN)
        assert code==200 and odds['method']=='exact_hypergeometric', (code,odds)
        assert abs(odds['hit_next_card_probability']-2/47)<1e-12
        assert odds['money_actions_enabled'] is False and odds['action'] is None
        code,_=fetch(base+'/math/draw-odds',draw)
        assert code==401, code
        print('PASS: HTTP health, auth rejection, JPEG roundtrip, exact draw odds, read-only RTT probe, no tap endpoint')
    finally:
        proc.terminate()
        try: proc.wait(timeout=3)
        except subprocess.TimeoutExpired: proc.kill()

if __name__=='__main__': main()
