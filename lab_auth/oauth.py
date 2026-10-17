"""Official SIWC authorization primitives, deliberately decoupled from game runtime.

The caller must start a 127.0.0.1 listener before launching the system browser.
This module never opens a browser, receives a real callback or spends plan credits itself.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass
import hashlib
import hmac
import secrets
from urllib.parse import parse_qs, urlencode, urlsplit
import uuid

AUTH_URL = 'https://auth.openai.com/api/accounts/authorize'
TOKEN_URL = 'https://auth.openai.com/api/accounts/oauth/token'
RESOURCE = 'https://api.openai.com/v1'
SCOPES = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'

class AuthError(ValueError):
    pass


def _callback_uri(uri: str) -> None:
    p = urlsplit(uri)
    if p.scheme != 'http' or p.hostname != '127.0.0.1' or p.path != '/auth/callback' or not p.port or p.username or p.password or p.query or p.fragment:
        raise AuthError('Callback must be exact HTTP loopback 127.0.0.1:<port>/auth/callback')


def make_host_id() -> str:
    return 'urn:uuid:' + str(uuid.uuid4())


@dataclass(frozen=True)
class AuthAttempt:
    state: str
    nonce: str
    verifier: str
    callback_uri: str
    host_id: str
    requested_client_id: str
    agent_name: str

    @property
    def challenge(self) -> str:
        return base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode('ascii')).digest()).decode().rstrip('=')

    def authorization_url(self, id_token_hint: str | None = None) -> str:
        params = {
            'client_id': self.requested_client_id,
            'ext_agent_host_id': self.host_id,
            'response_type': 'code',
            'redirect_uri': self.callback_uri,
            'scope': SCOPES,
            'resource': RESOURCE,
            'state': self.state,
            'nonce': self.nonce,
            'code_challenge_method': 'S256',
            'code_challenge': self.challenge,
        }
        if self.requested_client_id == 'dynamic_agent_client':
            params['agent_name_hint'] = self.agent_name
        elif id_token_hint:
            params['id_token_hint'] = id_token_hint
        return AUTH_URL + '?' + urlencode(params)

    def callback(self, callback_url: str) -> tuple[str, str]:
        a, b = urlsplit(callback_url), urlsplit(self.callback_uri)
        if (a.scheme, a.netloc, a.path) != (b.scheme, b.netloc, b.path) or a.fragment:
            raise AuthError('Callback redirect URI mismatch')
        q = parse_qs(a.query, keep_blank_values=True, strict_parsing=True)
        if any(len(v) != 1 for v in q.values()):
            raise AuthError('Duplicate callback parameter')
        if not hmac.compare_digest(q.get('state', [''])[0], self.state):
            raise AuthError('OAuth state mismatch')
        if 'error' in q:
            raise AuthError('OAuth authorization denied or failed')
        code = q.get('code', [''])[0]
        if not code:
            raise AuthError('Missing authorization code')
        returned_id = q.get('client_id', [''])[0]
        if self.requested_client_id == 'dynamic_agent_client':
            if not returned_id or returned_id == 'dynamic_agent_client':
                raise AuthError('Missing issued dynamic client ID')
            client_id = returned_id
        else:
            if returned_id and returned_id != self.requested_client_id:
                raise AuthError('Issued client ID changed on reauthorization')
            client_id = self.requested_client_id
        return code, client_id


def make_attempt(callback_uri: str, host_id: str, agent_name: str = 'AI Remote Control Lab', client_id: str | None = None) -> AuthAttempt:
    _callback_uri(callback_uri)
    if not host_id.startswith('urn:uuid:'):
        raise AuthError('Persistent host ID must be a urn:uuid')
    uuid.UUID(host_id.removeprefix('urn:uuid:'))
    if not agent_name or len(agent_name) > 100:
        raise AuthError('Invalid application name')
    if client_id == 'dynamic_agent_client':
        raise AuthError('Pass None for initial dynamic registration')
    return AuthAttempt(secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64), callback_uri, host_id, client_id or 'dynamic_agent_client', agent_name)


class OAuthClient:
    def __init__(self, transport):
        self.transport = transport

    def exchange(self, attempt: AuthAttempt, callback_url: str) -> tuple[str, dict]:
        code, issued_id = attempt.callback(callback_url)
        r = self.transport.post(TOKEN_URL, data={
            'grant_type': 'authorization_code', 'client_id': issued_id,
            'code': code, 'code_verifier': attempt.verifier,
            'redirect_uri': attempt.callback_uri, 'resource': RESOURCE,
        }, timeout=15, allow_redirects=False)
        if r.status_code != 200:
            raise AuthError('Token exchange failed (no credentials stored)')
        obj = r.json()
        if not all(isinstance(obj.get(k), str) and obj[k] for k in ('id_token', 'access_token', 'scope')):
            raise AuthError('Token response missing identity, access token, or granted scopes')
        return issued_id, obj

    def refresh(self, client_id: str, refresh_token: str) -> dict:
        if client_id == 'dynamic_agent_client' or not refresh_token:
            raise AuthError('Invalid refresh registration')
        r = self.transport.post(TOKEN_URL, data={
            'grant_type': 'refresh_token', 'client_id': client_id,
            'refresh_token': refresh_token, 'resource': RESOURCE,
        }, timeout=15, allow_redirects=False)
        if r.status_code != 200:
            raise AuthError('Token refresh failed')
        obj = r.json()
        if not obj.get('access_token') or not obj.get('refresh_token'):
            raise AuthError('Refresh must atomically rotate access and refresh tokens')
        return obj


class PendingAuthorization:
    """In-memory one-shot callback validator for a single running loopback listener."""
    def __init__(self, attempt: AuthAttempt):
        self.attempt = attempt
        self._used = False

    def consume(self, callback_url: str) -> tuple[str, str]:
        if self._used:
            raise AuthError('Authorization callback already consumed')
        # Consume even a bad callback, fail closed. Start a new attempt to retry.
        self._used = True
        return self.attempt.callback(callback_url)


def load_or_create_host_id(path):
    """Stable per-installation host UUID stored without tokens or account data."""
    from pathlib import Path
    import os
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if p.exists():
        val = p.read_text().strip()
        if not val.startswith('urn:uuid:'):
            raise AuthError('Invalid stored host ID')
        uuid.UUID(val.removeprefix('urn:uuid:'))
        return val
    val = make_host_id()
    # Exclusive creation to avoid overwriting another installation's ID.
    with p.open('x') as f:
        f.write(val + '\n')
    if os.name == 'posix':
        os.chmod(p, 0o600)
    return val
