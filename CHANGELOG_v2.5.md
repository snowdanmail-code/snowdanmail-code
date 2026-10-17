# v2.5.0-lab

- Added isolated lab_auth/ with official SIWC OAuth PKCE/dynamic-client primitives, OIDC JWT validation, encrypted local credential prototype and two interchangeable provider adapters.
- Added fixed harmless Responses API streaming lab ping; no generic inference/game endpoints.
- Added 44 offline unit tests using synthetic identities, RSA test keys and fake network responses.
- CI job extended to install cryptography and run lab_auth tests.
- Preserved existing Android/game source unchanged. No real sign-in, API request, APK build or monetary action.
