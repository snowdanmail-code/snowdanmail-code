"""Isolated lab-only OpenAI authorization and provider adapters.

NOT imported by Android/game control code. No monetary actions or gameplay.
"""
from .oauth import AuthAttempt, AuthError, OAuthClient, make_attempt
from .providers import ChatGPTPlanProvider, APIKeyProvider, LabResponse, ProviderError
