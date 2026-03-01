# RIP-0003 Challenge Auth

## Status
Draft (v1)

## Objective
Prevent replay and cross-platform signature reuse during login and actions.

## Challenge signing input
`rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}`

Platform MUST:
1. Issue one-time nonce and store state (`issued|consumed|expired`).
2. Consume nonce at first `auth/complete` attempt (success/failure both consume).
3. Enforce short TTL and <=30s skew.
4. Reject nonce replay.

## Self-hosted register signing input
`rare-register-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}`

Rare MUST:
1. Require proof signature for `self-hosted` registration.
2. Verify `signature_by_agent` using `agent_id` public key.
3. Validate timestamps with <=30s skew.
4. Reject invalid signature or malformed key.

## Action signing input
`rare-act-v1:{aud}:{session_token}:{action}:{sha256(canonical_json(action_payload))}:{nonce}:{issued_at}:{expires_at}`

Platform MUST:
1. Verify `signature_by_session` with authenticated `session_pubkey`.
2. Validate action nonce one-time usage per session.
3. Validate timestamps and action type.
4. Validate `aud` and `session_token` binding.

## Platform Grant signing input (new in v1)
`rare-grant-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`

Rare MUST:
1. Verify `signature_by_agent` using `agent_id` public key.
2. Validate timestamps with <=30s skew.
3. Enforce one-time nonce per `agent_id`.
4. Support create/revoke grant with same signing input shape.

## Full Attestation issue signing input (new in v1)
`rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`

Rare MUST:
1. Verify `signature_by_agent` using `agent_id` public key.
2. Validate timestamps with <=30s skew.
3. Enforce one-time nonce per `agent_id`.
4. Issue full attestation only when platform is registered and grant is active.

## Upgrade request signing input (new in v1)
`rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}`

Rare MUST:
1. Verify `signature_by_agent` using `agent_id` public key.
2. Validate timestamps with <=30s skew.
3. Enforce one-time nonce per `agent_id`.
4. Bind signed payload to exact `target_level` and `request_id`.
5. Reject replayed request nonces and reused `request_id`.

## Canonical JSON
- UTF-8
- `sort_keys=true`
- compact separators `(',', ':')`
