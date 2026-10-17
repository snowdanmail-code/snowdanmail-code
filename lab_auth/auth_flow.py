"""Finish an OAuth attempt only after identity verification and explicit scope grant."""
from __future__ import annotations
from dataclasses import dataclass
from .oauth import OAuthClient, AuthAttempt, AuthError
from .identity import verify_id_token, fetch_openai_jwks
from .providers import PLAN_SCOPE

@dataclass(frozen=True)
class ValidatedSession:
    client_id: str
    subject: str
    email: str | None
    scopes: frozenset[str]
    credentials: dict

    @property
    def sharing_enabled(self) -> bool:
        return PLAN_SCOPE in self.scopes


def complete_login(attempt: AuthAttempt, callback_url: str, transport, *, existing_subject: str | None = None) -> ValidatedSession:
    issued_client, tokens = OAuthClient(transport).exchange(attempt, callback_url)
    keys = fetch_openai_jwks(transport)
    claims = verify_id_token(tokens['id_token'], keys, issued_client, attempt.nonce)
    if existing_subject is not None and existing_subject != claims['sub']:
        raise AuthError('Reauthorization switched accounts')
    scopes = frozenset(tokens['scope'].split())
    if PLAN_SCOPE not in scopes:
        # Identity-only sign-in is not permission to consume the plan.
        return ValidatedSession(issued_client, claims['sub'], claims.get('email'), scopes, tokens)
    return ValidatedSession(issued_client, claims['sub'], claims.get('email'), scopes, tokens)
