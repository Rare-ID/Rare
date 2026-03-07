# RIP-0005 Platform Onboarding and Events

RIP: 0005
Title: Platform Onboarding and Events
Status: Accepted
Type: Standards Track
Author: Rare Maintainers
Created: 2026-03-03
Updated: 2026-03-03
Requires: 0001, 0002, 0003
Replaces: None
Superseded-By: None
Discussion: https://github.com/rare-project/rare/discussions

## Abstract
This RIP defines platform onboarding, full attestation issuance for registered platforms, human-in-the-loop upgrade states, and negative event ingestion into the identity library.

## Motivation
Rare needs a consistent path for third-party platforms to register trust anchors, receive audience-bound identity assertions, and report governance-relevant security events.

## Specification
### Platform registration with DNS proof
Step 1: request challenge
- Endpoint: `POST /v1/platforms/register/challenge`
- Input: `platform_aud`, `domain`
- Output: `challenge_id`, `txt_name`, `txt_value`, `expires_at`

Step 2: complete registration
- Endpoint: `POST /v1/platforms/register/complete`
- Input: `challenge_id`, `platform_id`, `platform_aud`, `domain`, `keys[]`
- Key item fields:
  - `kid`
  - `public_key` (Ed25519 base64url)

Validation requirements:
1. DNS TXT record at `txt_name` contains `txt_value`.
2. Challenge is unexpired and single-use.
3. Key ids are unique.

Output fields include `platform_id`, `platform_aud`, `domain`, `status=active`.

### Full attestation for registered platform
Full attestation issue:
- Endpoint: `POST /v1/attestations/full/issue`
- Signed input: `rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- Policy: `expires_at - issued_at <= 300`

Preconditions:
1. Platform is registered and active.

### Human upgrade flow (L1 and L2)
Upgrade status model:
- `requested`
- `human_pending`
- `verified`
- `upgraded`
- `expired`
- `revoked` (reserved)

L1 email flow:
- `POST /v1/upgrades/requests` (`target_level=L1`, requires `contact_email`)
- `POST /v1/upgrades/l1/email/send-link`
- `POST /v1/upgrades/l1/email/verify`

L2 social flow:
- `POST /v1/upgrades/requests` (`target_level=L2`)
- `POST /v1/upgrades/l2/social/start`
- `GET /v1/upgrades/l2/social/callback`
- `POST /v1/upgrades/l2/social/complete`

Shared status query:
- `GET /v1/upgrades/requests/{upgrade_request_id}`

Upgrade request signing input:
- `rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}`
- Policy: `expires_at - issued_at <= 300`

### Platform event token (negative events only in v1)
Header requirements:
- `typ=rare.platform-event+jws`
- `alg=EdDSA`
- `kid=<platform_kid>`

Payload requirements:
- `typ=rare.platform-event`
- `ver=1`
- `iss=<platform_id>`
- `aud=rare.identity-library`
- `iat`, `exp`, `jti` (`jti` is mandatory)
- `events[]`

Allowed categories:
- `spam`
- `fraud`
- `abuse`
- `policy_violation`

Ingest endpoint:
- `POST /v1/identity-library/events/ingest`
- Input: `event_token`

Validation requirements:
1. Lookup platform key by `kid` and verify signature.
2. Validate payload `typ`, `ver`, `iss`, `aud`.
3. Validate time window.
4. Enforce replay protection on `(iss, jti)`.
5. Enforce idempotent dedupe on `(iss, event_id)`.

### Hosted signer API security
- All `/v1/signer/*` endpoints require `Authorization: Bearer <hosted_management_token>`.
- Hosted token is issued at `POST /v1/agents/self_register`.
- Hosted token is bound to one hosted `agent_id`.
- `ttl_seconds` for signer requests is capped at 300.
- Token lifecycle endpoints:
  - `POST /v1/signer/rotate_management_token`
  - `POST /v1/signer/revoke_management_token`

## Backward Compatibility
This RIP documents v1 onboarding and governance flows without changing signed payload formats. Existing clients remain compatible when they already follow v1 endpoints and signed input policies.

## Security Considerations
- DNS challenge single-use and expiry are mandatory.
- Full attestation signatures must be nonce-protected and short-lived.
- Upgrade flows require replay-safe tokens and verified ownership signals.
- Event ingestion requires signature validation, replay protection, and dedupe to resist abuse.

## Test Vectors/Examples
- Signing input vectors: `rare-identity-core/docs/test-vectors/rip-v1-signing-inputs.json`
- Integration checks: `rare-agent-sdk-python/tests/test_sdk.py`

## Reference Implementation
- `rare-identity-core/services/rare_api/main.py`
- `rare-identity-core/services/rare_api/service.py`
- `rare-identity-core/tests/test_core.py`
- `rare-agent-sdk-python/tests/_platform_stub.py`
- `rare-agent-sdk-python/tests/test_sdk.py`
