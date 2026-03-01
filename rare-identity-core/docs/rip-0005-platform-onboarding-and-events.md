# RIP-0005 Platform Onboarding and Events

## Status
Draft (v1)

## Objective
Define platform registration, full-attestation enablement, and negative-event ingestion for identity governance.

## Platform registration (DNS proof)

### 1) Request challenge
- Endpoint: `POST /v1/platforms/register/challenge`
- Input: `platform_aud`, `domain`
- Output: `challenge_id`, `txt_name`, `txt_value`, `expires_at`

### 2) Complete registration
- Endpoint: `POST /v1/platforms/register/complete`
- Input: `challenge_id`, `platform_id`, `platform_aud`, `domain`, `keys[]`
- Key item:
  - `kid`
  - `public_key` (Ed25519, base64url)
- Verification:
  - DNS TXT value at `txt_name` must contain `txt_value`
  - challenge must be unexpired and single-use
  - key ids must be unique
- Output: `platform_id`, `platform_aud`, `domain`, `status=active`

## Agent grant and full attestation

### Grant create/revoke
- `POST /v1/agents/platform-grants`
- `DELETE /v1/agents/platform-grants/{platform_aud}`
- Signed input: `rare-grant-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- Grants are long-lived until revoked.

### Grant list
- `GET /v1/agents/platform-grants/{agent_id}`

### Full attestation issue
- Endpoint: `POST /v1/attestations/full/issue`
- Signed input: `rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- Preconditions:
  - platform is registered and active
  - grant exists and not revoked
- Output: `full_identity_attestation`

## Agent requested human upgrade flow (L1/L2)

### Upgrade status model
- `requested`
- `human_pending`
- `verified`
- `upgraded`
- `expired`
- `revoked` (reserved)

### L1 email upgrade (magic link)
- `POST /v1/upgrades/requests`
  - signed input: `rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}`
  - `target_level=L1` requires `contact_email`
- `POST /v1/upgrades/l1/email/send-link`
  - sends one-time magic link token (v1 local stub returns token in response)
- `GET /v1/upgrades/l1/email/verify?token=...`
  - verifies token and auto-upgrades to `L1`
  - sets `owner_id=email:<sha256(lower(email))>`

### L2 social upgrade (X/GitHub any one)
- precondition: current level must be `L1` or above
- `POST /v1/upgrades/requests` with `target_level=L2`
- `POST /v1/upgrades/l2/social/start`
  - input: `upgrade_request_id`, `provider=x|github`
  - output: `authorize_url`, `state`
- `GET /v1/upgrades/l2/social/callback`
  - input: `provider`, `code`, `state`
  - verifies oauth state and auto-upgrades to `L2`
- `POST /v1/upgrades/l2/social/complete`
  - local integration shortcut for passing provider snapshot directly

### Shared status query
- `GET /v1/upgrades/requests/{upgrade_request_id}`
  - returns current state and next step

## Platform event token (negative only in v1)

### Token format
- Header:
  - `typ=rare.platform-event+jws`
  - `alg=EdDSA`
  - `kid=<platform_kid>`
- Payload:
  - `typ=rare.platform-event`
  - `ver=1`
  - `iss=<platform_id>`
  - `aud=rare.identity-library`
  - `iat`, `exp`, `jti`
  - `events[]`

### Allowed categories
- `spam`
- `fraud`
- `abuse`
- `policy_violation`

### Ingest endpoint
- `POST /v1/identity-library/events/ingest`
- Input: `event_token`
- Verification:
  1. platform key lookup by `kid` and signature verification
  2. payload `typ/ver/iss/aud` validation
  3. time window validation
  4. replay protection on `(iss, jti)`
  5. idempotent dedupe on `(iss, event_id)`
- Side effects:
  - update `IdentityProfile.risk_score`
  - update `labels` (e.g. `abuse-reported`, `fraud-risk`)
  - update `metadata.platform_event_counts`
