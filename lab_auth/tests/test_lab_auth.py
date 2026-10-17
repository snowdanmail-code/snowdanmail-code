from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlsplit
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from lab_auth.oauth import make_attempt, make_host_id, OAuthClient, AuthError, TOKEN_URL
from lab_auth.identity import verify_id_token, fetch_openai_jwks
from lab_auth.auth_flow import complete_login
from lab_auth.storage import EncryptedVault
from lab_auth.providers import ChatGPTPlanProvider, APIKeyProvider, ProviderError, LAB_PROMPT

CALLBACK = 'http://127.0.0.1:1455/auth/callback'

class FakeResponse:
    def __init__(self, status=200, data=None, lines=None):
        self.status_code = status
        self._data = data or {}
        self._lines = lines or []
    def json(self): return self._data
    def iter_lines(self, decode_unicode=False): return iter(self._lines)

class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
    def post(self, url, **kwargs):
        self.calls.append(('POST', url, kwargs))
        return self.responses.pop(0)
    def get(self, url, **kwargs):
        self.calls.append(('GET', url, kwargs))
        return self.responses.pop(0)

def enc(obj):
    return base64.urlsafe_b64encode(json.dumps(obj, separators=(',', ':')).encode()).decode().rstrip('=')

def jwt_and_keys(nonce, client_id='oaiapp_test', *, override=None):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()
    def b64int(x): return base64.urlsafe_b64encode(x.to_bytes((x.bit_length() + 7) // 8, 'big')).decode().rstrip('=')
    jwks = {'keys': [{'kty':'RSA', 'kid':'test-key', 'alg':'RS256', 'use':'sig', 'n':b64int(pub.n), 'e':b64int(pub.e)}]}
    claims = {'iss':'https://auth.openai.com','aud':client_id,'sub':'test-sub','nonce':nonce,'exp':int(time.time())+1800,'iat':int(time.time()),'email':'test@example.test'}
    claims.update(override or {})
    head = enc({'alg':'RS256','kid':'test-key','typ':'JWT'})
    payload = enc(claims)
    body = (head + '.' + payload).encode()
    sig = key.sign(body, padding.PKCS1v15(), hashes.SHA256())
    return (body.decode() + '.' + base64.urlsafe_b64encode(sig).decode().rstrip('=')), jwks

class TestOAuth(unittest.TestCase):
    def setUp(self):
        self.attempt = make_attempt(CALLBACK, make_host_id())
    def callback(self, *, state=None, cid='oaiapp_test', code='synthetic'):
        return CALLBACK + '?code=' + code + '&state=' + (state or self.attempt.state) + '&client_id=' + cid
    def test_url_params(self):
        url = self.attempt.authorization_url()
        q = parse_qs(urlsplit(url).query)
        self.assertEqual(urlsplit(url).hostname, 'auth.openai.com')
        self.assertEqual(q['client_id'], ['dynamic_agent_client'])
        self.assertEqual(q['ext_agent_host_id'], [self.attempt.host_id])
        self.assertEqual(q['agent_name_hint'], ['AI Remote Control Lab'])
        self.assertEqual(q['code_challenge_method'], ['S256'])
        self.assertIn('chatgpt.tokens.use.direct', q['scope'][0])
        self.assertEqual(q['redirect_uri'], [CALLBACK])
        self.assertEqual(q['code_challenge'], [self.attempt.challenge])
    def test_random_values_unique(self):
        other = make_attempt(CALLBACK, self.attempt.host_id)
        self.assertNotEqual(other.state, self.attempt.state)
        self.assertNotEqual(other.nonce, self.attempt.nonce)
        self.assertNotEqual(other.verifier, self.attempt.verifier)
    def test_pkce_challenge(self):
        expect = base64.urlsafe_b64encode(hashlib.sha256(self.attempt.verifier.encode()).digest()).decode().rstrip('=')
        self.assertEqual(self.attempt.challenge, expect)
    def test_callback_issued_id(self):
        self.assertEqual(self.attempt.callback(self.callback()), ('synthetic', 'oaiapp_test'))
    def test_state_mismatch(self):
        with self.assertRaises(AuthError): self.attempt.callback(self.callback(state='forged'))
    def test_callback_host_mismatch(self):
        with self.assertRaises(AuthError): self.attempt.callback(self.callback().replace('127.0.0.1','localhost'))
    def test_callback_port_mismatch(self):
        with self.assertRaises(AuthError): self.attempt.callback(self.callback().replace('1455','1456'))
    def test_callback_duplicate_state(self):
        with self.assertRaises(AuthError): self.attempt.callback(self.callback()+'&state='+self.attempt.state)
    def test_callback_error(self):
        with self.assertRaises(AuthError): self.attempt.callback(CALLBACK+'?error=access_denied&state='+self.attempt.state)
    def test_missing_issued_id(self):
        with self.assertRaises(AuthError): self.attempt.callback(self.callback(cid=''))
    def test_callback_replay_state_is_not_auto_consumed(self):
        # Production callback listener must consume pending attempts exactly once.
        self.assertEqual(self.attempt.callback(self.callback())[1], 'oaiapp_test')
    def test_returning_client(self):
        a = make_attempt(CALLBACK, self.attempt.host_id, client_id='oaiapp_test')
        self.assertNotIn('agent_name_hint', parse_qs(urlsplit(a.authorization_url()).query))
        self.assertEqual(a.callback(CALLBACK+'?code=c&state='+a.state), ('c','oaiapp_test'))
        with self.assertRaises(AuthError): a.callback(CALLBACK+'?code=c&state='+a.state+'&client_id=oaiapp_other')
    def test_bad_callback_uri(self):
        for uri in ['http://localhost:1455/auth/callback','http://127.0.0.1:1455/callback','https://127.0.0.1:1455/auth/callback']:
            with self.subTest(uri=uri), self.assertRaises(AuthError): make_attempt(uri, self.attempt.host_id)
    def test_token_exchange_uses_issued_id(self):
        transport = FakeTransport([FakeResponse(data={'id_token':'id','access_token':'access','scope':'openid'})])
        cid, _ = OAuthClient(transport).exchange(self.attempt, self.callback())
        self.assertEqual(cid, 'oaiapp_test')
        self.assertEqual(transport.calls[0][2]['data']['client_id'], 'oaiapp_test')
        self.assertEqual(transport.calls[0][2]['data']['code_verifier'], self.attempt.verifier)
        self.assertEqual(transport.calls[0][2]['data']['redirect_uri'], CALLBACK)
    def test_exchange_failure(self):
        with self.assertRaises(AuthError): OAuthClient(FakeTransport([FakeResponse(400)])).exchange(self.attempt, self.callback())
    def test_refresh_rotates(self):
        o = OAuthClient(FakeTransport([FakeResponse(data={'access_token':'new','refresh_token':'new-refresh'})]))
        self.assertEqual(o.refresh('oaiapp_test','old')['refresh_token'], 'new-refresh')
        with self.assertRaises(AuthError): OAuthClient(FakeTransport([FakeResponse(data={'access_token':'new'})])).refresh('oaiapp_test','old')

class TestIdentity(unittest.TestCase):
    def setUp(self):
        self.nonce='test-nonce'
        self.token, self.jwks = jwt_and_keys(self.nonce)
    def test_valid_signature(self):
        self.assertEqual(verify_id_token(self.token,self.jwks,'oaiapp_test',self.nonce)['sub'],'test-sub')
    def test_nonce_rejected(self):
        with self.assertRaises(AuthError): verify_id_token(self.token,self.jwks,'oaiapp_test','different')
    def test_audience_rejected(self):
        with self.assertRaises(AuthError): verify_id_token(self.token,self.jwks,'oaiapp_other',self.nonce)
    def test_expired_rejected(self):
        token, keys = jwt_and_keys(self.nonce,override={'exp':int(time.time())-1})
        with self.assertRaises(AuthError): verify_id_token(token,keys,'oaiapp_test',self.nonce)
    def test_bad_issuer_rejected(self):
        token, keys = jwt_and_keys(self.nonce,override={'iss':'https://other.example'})
        with self.assertRaises(AuthError): verify_id_token(token,keys,'oaiapp_test',self.nonce)
    def test_tamper_rejected(self):
        parts=self.token.split('.')
        parts[1]=enc({'sub':'attacker'})
        with self.assertRaises(AuthError): verify_id_token('.'.join(parts),self.jwks,'oaiapp_test',self.nonce)
    def test_untrusted_jwks_discovery(self):
        t=FakeTransport([FakeResponse(data={'issuer':'https://auth.openai.com','jwks_uri':'https://evil.example/jwks'})])
        with self.assertRaises(AuthError): fetch_openai_jwks(t)
    def test_complete_login_scope(self):
        attempt = make_attempt(CALLBACK, make_host_id())
        token, keys = jwt_and_keys(attempt.nonce)
        responses=[FakeResponse(data={'id_token':token,'access_token':'synthetic','scope':'openid chatgpt.tokens.use.direct'}),FakeResponse(data={'issuer':'https://auth.openai.com','jwks_uri':'https://auth.openai.com/keys'}),FakeResponse(data=keys)]
        s=complete_login(attempt,CALLBACK+'?code=synthetic&state='+attempt.state+'&client_id=oaiapp_test',FakeTransport(responses))
        self.assertTrue(s.sharing_enabled)
        self.assertEqual(s.subject,'test-sub')
    def test_complete_login_without_plan_scope(self):
        attempt=make_attempt(CALLBACK,make_host_id())
        token,keys=jwt_and_keys(attempt.nonce)
        t=FakeTransport([FakeResponse(data={'id_token':token,'access_token':'synthetic','scope':'openid'}),FakeResponse(data={'issuer':'https://auth.openai.com','jwks_uri':'https://auth.openai.com/keys'}),FakeResponse(data=keys)])
        s=complete_login(attempt,CALLBACK+'?code=x&state='+attempt.state+'&client_id=oaiapp_test',t)
        self.assertFalse(s.sharing_enabled)
    def test_reauthorization_identity_mismatch(self):
        attempt=make_attempt(CALLBACK,make_host_id())
        token,keys=jwt_and_keys(attempt.nonce)
        t=FakeTransport([FakeResponse(data={'id_token':token,'access_token':'synthetic','scope':'openid'}),FakeResponse(data={'issuer':'https://auth.openai.com','jwks_uri':'https://auth.openai.com/keys'}),FakeResponse(data=keys)])
        with self.assertRaises(AuthError): complete_login(attempt,CALLBACK+'?code=x&state='+attempt.state+'&client_id=oaiapp_test',t,existing_subject='someone-else')

class TestVault(unittest.TestCase):
    def test_encrypted_roundtrip_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            v=EncryptedVault(Path(tmp)/'secrets','correct horse battery staple')
            path=v.save('oaiapp_test','subject',{'access_token':'SECRET_TOKEN','refresh_token':'SECRET_REFRESH'})
            raw=path.read_bytes()
            self.assertNotIn(b'SECRET_TOKEN',raw)
            self.assertNotIn(b'SECRET_REFRESH',raw)
            self.assertEqual(v.load('oaiapp_test','subject')['refresh_token'],'SECRET_REFRESH')
            if os.name=='posix': self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with self.assertRaises(Exception): EncryptedVault(Path(tmp)/'secrets','incorrect passphrase').load('oaiapp_test','subject')
            data=json.loads(raw); data['ciphertext']=base64.b64encode(b'bad').decode(); path.write_text(json.dumps(data))
            with self.assertRaises(Exception): v.load('oaiapp_test','subject')
    def test_short_password_rejected(self):
        with self.assertRaises(AuthError): EncryptedVault(Path('/tmp/x'),'short')

class TestProviders(unittest.TestCase):
    def test_scope_required(self):
        with self.assertRaises(ProviderError): ChatGPTPlanProvider('synthetic',{'openid'})
    def test_model_list(self):
        p=ChatGPTPlanProvider('synthetic',{'chatgpt.tokens.use.direct'})
        t=FakeTransport([FakeResponse(data={'models':[{'slug':'test-model','display_name':'Test','visibility':'list'},{'slug':'hidden','visibility':'hidden'}]})])
        self.assertEqual(p.list_models(t),[{'slug':'test-model','display_name':'Test'}])
        self.assertEqual(t.calls[0][1],'https://api.openai.com/v1/models')
    def test_fixed_lab_prompt_and_stream_flags(self):
        p=ChatGPTPlanProvider('synthetic',{'chatgpt.tokens.use.direct'})
        lines=['event: response.output_text.delta','data: '+json.dumps({'type':'response.output_text.delta','delta':'Laboratory connection OK.'}),'data: '+json.dumps({'type':'response.completed'})]
        t=FakeTransport([FakeResponse(lines=lines)])
        out=p.lab_ping(t,'test-model')
        self.assertTrue(out.completed)
        self.assertEqual(out.text,'Laboratory connection OK.')
        body=t.calls[0][2]['json']
        self.assertEqual(body['input'][0]['content'],LAB_PROMPT)
        self.assertIs(body['store'],False)
        self.assertIs(body['stream'],True)
    def test_rate_limit_no_retry(self):
        t=FakeTransport([FakeResponse(429)])
        with self.assertRaises(ProviderError) as ctx: ChatGPTPlanProvider('synthetic',{'chatgpt.tokens.use.direct'}).lab_ping(t,'test-model')
        self.assertEqual(ctx.exception.kind,'rate_limit')
        self.assertEqual(len(t.calls),1)
    def test_stream_usage_limit(self):
        lines=['data: '+json.dumps({'type':'response.failed','response':{'error':{'code':'subscription_sharing_usage_limit_exceeded'}}})]
        with self.assertRaises(ProviderError) as ctx: ChatGPTPlanProvider('synthetic',{'chatgpt.tokens.use.direct'}).lab_ping(FakeTransport([FakeResponse(lines=lines)]),'test-model')
        self.assertEqual(ctx.exception.kind,'plan_limit')
    def test_incomplete_stream(self):
        with self.assertRaises(ProviderError) as ctx: ChatGPTPlanProvider('synthetic',{'chatgpt.tokens.use.direct'}).lab_ping(FakeTransport([FakeResponse(lines=['data: '+json.dumps({'type':'response.output_text.delta','delta':'hello'})])]),'test-model')
        self.assertEqual(ctx.exception.kind,'incomplete')
    def test_api_key_provider_same_contract(self):
        p=APIKeyProvider('synthetic-key')
        t=FakeTransport([FakeResponse(data={'data':[{'id':'api-model'}]})])
        self.assertEqual(p.list_models(t),[{'slug':'api-model','display_name':'api-model'}])
        self.assertEqual(p.auth_header(),{'Authorization':'Bearer synthetic-key'})
    def test_no_game_integration_imports(self):
        import inspect
        import lab_auth.providers as providers
        src=inspect.getsource(providers)
        self.assertNotIn('import server',src)
        self.assertNotIn('import android',src)
        self.assertNotIn('def place_bet',src)

if __name__=='__main__': unittest.main()

class TestPendingAuthorization(unittest.TestCase):
    def test_one_shot_callback(self):
        from lab_auth.oauth import PendingAuthorization
        attempt = make_attempt(CALLBACK, make_host_id())
        pending = PendingAuthorization(attempt)
        cb = CALLBACK + '?code=c&state=' + attempt.state + '&client_id=oaiapp_test'
        self.assertEqual(pending.consume(cb), ('c', 'oaiapp_test'))
        with self.assertRaises(AuthError): pending.consume(cb)
    def test_invalid_consumes_attempt(self):
        from lab_auth.oauth import PendingAuthorization
        attempt = make_attempt(CALLBACK, make_host_id())
        pending = PendingAuthorization(attempt)
        cb = CALLBACK + '?code=c&state=' + attempt.state + '&client_id=oaiapp_test'
        with self.assertRaises(AuthError): pending.consume(cb.replace(attempt.state,'bad'))
        with self.assertRaises(AuthError): pending.consume(cb)
    def test_host_id_stable(self):
        from lab_auth.oauth import load_or_create_host_id
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'host-id'
            host1=load_or_create_host_id(path)
            host2=load_or_create_host_id(path)
            self.assertEqual(host1,host2)
            if os.name=='posix': self.assertEqual(path.stat().st_mode & 0o777,0o600)

class TestAdditionalFailurePaths(unittest.TestCase):
    def setUp(self):
        self.p = ChatGPTPlanProvider('synthetic',{'chatgpt.tokens.use.direct'})
    def test_stream_incomplete_event(self):
        lines=['data: '+json.dumps({'type':'response.incomplete','response':{'error':{'code':'partial'}}})]
        with self.assertRaises(ProviderError) as ctx: self.p.lab_ping(FakeTransport([FakeResponse(lines=lines)]),'test-model')
        self.assertEqual(ctx.exception.kind,'stream')
    def test_unauthorized(self):
        with self.assertRaises(ProviderError) as ctx: self.p.list_models(FakeTransport([FakeResponse(401)]))
        self.assertEqual(ctx.exception.kind,'auth')
    def test_unavailable_plan(self):
        lines=['data: '+json.dumps({'type':'response.failed','response':{'error':{'code':'subscription_sharing_usage_unavailable'}}})]
        with self.assertRaises(ProviderError) as ctx: self.p.lab_ping(FakeTransport([FakeResponse(lines=lines)]),'test-model')
        self.assertEqual(ctx.exception.kind,'plan_limit')
    def test_no_unapproved_model_fallback(self):
        t=FakeTransport([FakeResponse(429)])
        with self.assertRaises(ProviderError): self.p.list_models(t)
        self.assertEqual(len(t.calls),1)
    def test_vault_atomic_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            v=EncryptedVault(Path(tmp)/'secrets','correct horse battery staple')
            first=v.save('oaiapp_test','subject',{'access_token':'OLD','refresh_token':'OLD'})
            second=v.save('oaiapp_test','subject',{'access_token':'NEW','refresh_token':'NEW'})
            self.assertEqual(first,second)
            self.assertEqual(v.load('oaiapp_test','subject')['refresh_token'],'NEW')
            self.assertEqual(len(list((Path(tmp)/'secrets').glob('.vault-*'))),0)
