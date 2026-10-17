"""Strict RS256 OIDC ID-token verification against a trusted issuer JWKS."""
from __future__ import annotations
import base64
import json
import time
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
from .oauth import AuthError

ISSUER = 'https://auth.openai.com'


def _b64(s):
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def verify_id_token(token: str, jwks: dict, client_id: str, nonce: str, *, now: int | None = None) -> dict:
    try:
        header, payload, signature = token.split('.')
        h, p = json.loads(_b64(header)), json.loads(_b64(payload))
        if h.get('alg') != 'RS256' or not h.get('kid') or h.get('crit'):
            raise AuthError('Unsupported JWT header')
        keys = [k for k in jwks.get('keys', []) if k.get('kid') == h['kid'] and k.get('kty') == 'RSA' and k.get('use', 'sig') == 'sig' and k.get('alg', 'RS256') == 'RS256']
        if len(keys) != 1:
            raise AuthError('No unique trusted signing key')
        key = keys[0]
        n = int.from_bytes(_b64(key['n']), 'big')
        e = int.from_bytes(_b64(key['e']), 'big')
        rsa.RSAPublicNumbers(e, n).public_key().verify(_b64(signature), (header + '.' + payload).encode(), padding.PKCS1v15(), hashes.SHA256())
        t = int(time.time()) if now is None else now
        aud = p.get('aud')
        aud_ok = aud == client_id if isinstance(aud, str) else isinstance(aud, list) and client_id in aud and p.get('azp') == client_id
        if p.get('iss') != ISSUER or not aud_ok or p.get('nonce') != nonce or not p.get('sub') or not isinstance(p.get('exp'), int) or p['exp'] <= t or ('nbf' in p and p['nbf'] > t) or ('iat' in p and p['iat'] > t + 60):
            raise AuthError('OIDC identity claims invalid')
        return p
    except (ValueError, TypeError, KeyError, InvalidSignature) as exc:
        raise AuthError('ID token signature or claims invalid') from exc


def fetch_openai_jwks(transport) -> dict:
    """Discover keys only from trusted OpenAI OIDC metadata; reject foreign JWKS URLs."""
    r = transport.get(ISSUER + '/.well-known/openid-configuration', timeout=15, allow_redirects=False)
    if r.status_code != 200:
        raise AuthError('OIDC discovery unavailable')
    d = r.json()
    url = d.get('jwks_uri')
    if d.get('issuer') != ISSUER or not isinstance(url, str) or not url.startswith(ISSUER + '/'):
        raise AuthError('Untrusted OIDC discovery')
    r2 = transport.get(url, timeout=15, allow_redirects=False)
    if r2.status_code != 200:
        raise AuthError('JWKS unavailable')
    return r2.json()
