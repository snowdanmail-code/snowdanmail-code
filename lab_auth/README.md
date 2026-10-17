# AI Remote Control v2.5: Sign in with ChatGPT LAB (NOT LIVE)

This directory is **independent** of `server/`, `android/`, and any game control code. It has no general-purpose inference endpoint, no browser automation, no betting, and no monetary operations. The only inference function sends a fixed harmless diagnostic prompt. All v2.5 tests use synthetic credentials and fake network transports; they make **zero real OpenAI requests**.

Implements offline-testable primitives matching the published 2026 Sign in with ChatGPT flow:

1. Create/persist host UUID (`make_host_id`); construct authorization request with `dynamic_agent_client`, `agent_name_hint`, `ext_agent_host_id`, OAuth state, OIDC nonce, S256 PKCE, and required scopes. **A loopback listener must be started by the host before opening the system browser**; not implemented in this release.
2. Validate exact loopback callback and state; use the **issued** `client_id` for token exchange. Handle reauthorization without `client_id` callback and reject mismatched client IDs.
3. Fetch OIDC discovery/JWKS from trusted issuer, verify RS256 ID token signature, issuer, audience, expiry and nonce; compare subject on reauthorization. Verify granted `chatgpt.tokens.use.direct` scope before inference.
4. Store credentials in password-encrypted AES-GCM/Scrypt vault with atomic file replacement and POSIX `0600` mode. This is a **prototype**; Windows ACL / Android Keystore integration and credential lifecycle UX are not implemented.
5. Two providers share a `ModelProvider` interface: `ChatGPTPlanProvider` (OAuth Bearer) and `APIKeyProvider` (future separately billed API key). No automatic paid fallback. Model discovery GET `/v1/models`; lab-only POST `/v1/responses` uses `store=false`, `stream=true`, requires terminal `response.completed`, and handles HTTP 429 / streaming usage limits.

**Security / limitations:** The provider is not wired into 1win, Android accessibility, screenshots, or existing server endpoints. Do not use with real-money gambling. No real sign-in, model listing, or inference has been performed; availability and Plus limits are unverified. In production, integrate a real loopback callback host and secure OS key store, then test consent and account switching with explicit user action. Do not commit tokens, account details, or screenshots. Credential files are excluded by `.gitignore`.

## Local tests

```bash
python -m unittest discover -s lab_auth/tests -v
```

Official references:
- https://developers.openai.com/siwc/token-sharing-open-source/sign-in
- https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference
- https://openai.com/policies/usage-policies/
