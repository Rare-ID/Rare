# RIP-0003 Challenge and Signing Inputs

RIP: 0003
Title: Challenge and Signing Inputs
Status: Accepted
Type: Standards Track
Author: Rare Maintainers
Created: 2026-03-03
Updated: 2026-03-03
Requires: None
Replaces: None
Superseded-By: None
Discussion: https://github.com/Rare-ID/Rare/discussions

## Abstract
This RIP defines fixed signing input formats for challenge login, self-registration, action signing, full attestation issue authorization, and upgrade requests.

## Motivation
Deterministic signing inputs are required to prevent replay, cross-context signature reuse, and incompatible client/server implementations.

## Specification
### Challenge signing input
`rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}`

Platform requirements:
1. Issue one-time nonce and track state (`issued|consumed|expired`).
2. Consume nonce on first completion attempt.
3. Enforce short TTL and max 30 second skew.
4. Reject nonce replay.

### Self-hosted register signing input
`rare-register-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}`

Rare requirements:
1. Verify `signature_by_agent` using `agent_id` public key.
2. Enforce max 30 second skew.
3. Reject malformed signatures and keys.

### Action signing input
`rare-act-v1:{aud}:{session_token}:{action}:{sha256(canonical_json(action_payload))}:{nonce}:{issued_at}:{expires_at}`

Platform requirements:
1. Verify `signature_by_session` with authenticated `session_pubkey`.
2. Enforce one-time action nonce per session.
3. Validate timestamps and action type.
4. Validate `aud` and `session_token` binding.

### Full attestation issue signing input
`rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`

Rare requirements:
1. Verify `signature_by_agent` using `agent_id`.
2. Enforce max 30 second skew.
3. Enforce one-time nonce per `agent_id`.
4. Issue full attestation only when platform is active.

### Upgrade request signing input
`rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}`

Rare requirements:
1. Verify `signature_by_agent` using `agent_id`.
2. Enforce max 30 second skew.
3. Enforce one-time nonce per `agent_id`.
4. Bind signature to exact `target_level` and `request_id`.
5. Reject replayed request nonce and reused `request_id`.

### Canonical JSON
Action payload canonicalization MUST use:
- UTF-8
- `sort_keys=true`
- compact separators `(',', ':')`

## Backward Compatibility
This RIP standardizes v1 signing strings and should remain stable. Any future format change requires a new versioned prefix.

## Security Considerations
- One-time nonce consumption is mandatory for replay defense.
- Short signature validity windows reduce exposure to captured payloads.
- Context fields (`aud`, `request_id`, `target_level`) prevent cross-flow signature reuse.

## Test Vectors/Examples
- Test vectors: `docs/rip/test-vectors/rip-v1-signing-inputs.json`
- Example challenge string: `rare-auth-v1:platform:abc:1700000000:1700000300`

## Reference Implementation
- `packages/python/rare-identity-protocol-python/src/rare_identity_protocol`
- `services/rare-identity-core/services/rare_api/service.py`
- `services/rare-identity-core/tests/test_core.py`
- `packages/python/rare-agent-sdk-python/tests/test_sdk.py`
