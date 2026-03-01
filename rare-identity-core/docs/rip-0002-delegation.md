# RIP-0002 Delegation

## Status
Draft (v1)

## Objective
Bind a short-lived session key to agent identity for platform login and actions.

## Format
- JWS Compact serialization
- `alg=EdDSA`
- Header: `typ=rare.delegation+jws`

## Payload (minimum)
- `typ=rare.delegation`
- `ver=1`
- `iss=agent|rare-signer`
- `agent_id`
- `session_pubkey`
- `aud`
- `scope` (e.g. `login`, `post`, `comment`)
- `iat`, `exp`
- `act=delegated_by_agent|delegated_by_rare`
- optional `jti`

## Verification rules
1. Verify JWS signature:
   - `iss=agent` -> verify by `agent_id` public key.
   - `iss=rare-signer` -> verify by Rare signer key.
2. Validate `aud` exact match.
3. Validate required `scope` for current action.
4. Validate timestamps with <=30s skew.
5. If `jti` present, enforce replay protection until expiry.

## Relationship with Identity Attestation (v1)
- Delegation format is unchanged in v1.
- Platform audience binding for full identity is carried by `identity_attestation.payload.aud`,
  not by delegation payload changes.
- Platform login must still enforce identity triad consistency:
  - `auth_complete.agent_id == delegation.agent_id == identity_attestation.sub`
- Suggested policy:
  - Use `public` attestation for low-friction login (max governance `L1`)
  - Use `full` attestation for registered platform governance (`L0/L1/L2` real level)
