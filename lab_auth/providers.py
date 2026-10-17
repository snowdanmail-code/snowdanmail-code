"""Provider-neutral lab-only model discovery and fixed harmless diagnostic prompt.

Intentionally NO generic inference endpoint and NO link to live game or Android control.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
import json

API = 'https://api.openai.com/v1'
LAB_PROMPT = 'Reply with exactly: Laboratory connection OK.'
PLAN_SCOPE = 'chatgpt.tokens.use.direct'

class ProviderError(RuntimeError):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind

@dataclass(frozen=True)
class LabResponse:
    model: str
    text: str
    completed: bool

class ModelProvider(Protocol):
    def auth_header(self) -> dict: ...
    def list_models(self, transport) -> list[dict]: ...
    def lab_ping(self, transport, model: str) -> LabResponse: ...


def _check_http(r):
    if r.status_code == 429:
        raise ProviderError('rate_limit', 'Usage or rate limit reached; do not auto-retry')
    if r.status_code in (401, 403):
        raise ProviderError('auth', 'Authorization expired or insufficient permissions')
    if r.status_code >= 400:
        raise ProviderError('http', f'API HTTP error {r.status_code}')

class _Common:
    def list_models(self, transport) -> list[dict]:
        r = transport.get(API + '/models', headers=self.auth_header(), timeout=15, allow_redirects=False)
        _check_http(r)
        data = r.json()
        # Plan sharing returns `models`, ordinary API often returns `data`.
        models = data.get('models', data.get('data', []))
        return [{'slug': m.get('slug', m.get('id')), 'display_name': m.get('display_name', m.get('id', ''))}
                for m in models if m.get('visibility', 'list') == 'list' and (m.get('slug') or m.get('id'))]

    def lab_ping(self, transport, model: str) -> LabResponse:
        if not model or not isinstance(model, str):
            raise ProviderError('input', 'Choose a model returned by list_models')
        payload = {'model': model, 'input': [{'role': 'user', 'content': LAB_PROMPT}], 'store': False, 'stream': True}
        r = transport.post(API + '/responses', headers={**self.auth_header(), 'Content-Type': 'application/json'},
                           json=payload, timeout=30, stream=True, allow_redirects=False)
        _check_http(r)
        text_parts = []
        completed = False
        # Requests iter_lines works with SSE; ignore non-data lines, parse terminal events.
        for raw in r.iter_lines(decode_unicode=True):
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            if not raw or not raw.startswith('data:'):
                continue
            data = raw[5:].strip()
            if data == '[DONE]':
                break
            try:
                event = json.loads(data)
            except (ValueError, TypeError) as exc:
                raise ProviderError('stream', 'Invalid SSE JSON') from exc
            typ = event.get('type')
            if typ == 'response.output_text.delta':
                text_parts.append(str(event.get('delta', '')))
            elif typ == 'response.completed':
                completed = True
                break
            elif typ in ('response.failed', 'response.incomplete', 'error'):
                error = (event.get('response') or {}).get('error') or event.get('error') or {}
                code = error.get('code', 'unknown') if isinstance(error, dict) else 'unknown'
                if code in ('subscription_sharing_usage_limit_exceeded', 'subscription_sharing_usage_unavailable'):
                    raise ProviderError('plan_limit', 'ChatGPT plan usage limit or sharing unavailable')
                raise ProviderError('stream', f'Inference did not complete: {code}')
        if not completed:
            raise ProviderError('incomplete', 'SSE stream ended without response.completed')
        return LabResponse(model, ''.join(text_parts), True)

class ChatGPTPlanProvider(_Common):
    def __init__(self, access_token: str, scopes: set[str]):
        if PLAN_SCOPE not in scopes:
            raise ProviderError('scope', 'ChatGPT plan sharing not granted')
        if not access_token:
            raise ProviderError('auth', 'Missing OAuth access token')
        self._access_token = access_token

    def auth_header(self) -> dict:
        return {'Authorization': 'Bearer ' + self._access_token}

class APIKeyProvider(_Common):
    """Future paid provider; never falls back to it automatically."""
    def __init__(self, api_key: str):
        if not api_key:
            raise ProviderError('auth', 'Missing API key')
        self._api_key = api_key

    def auth_header(self) -> dict:
        return {'Authorization': 'Bearer ' + self._api_key}
