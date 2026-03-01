# RIP-0001 Identity Attestation

## Status
Draft (v1)

## Objective
Define Rare-signed identity attestations with **public/full split** for platform governance.

## Format
- JWS Compact serialization
- `alg=EdDSA` (Ed25519)
- Header `kid=<rare signing key id>`
- Header `typ` is **one of**:
  - `rare.identity.public+jws`
  - `rare.identity.full+jws`
- Legacy `typ=rare.identity+jws` is **removed** in v1 (breaking).

## Payload (shared minimum)
- `typ=rare.identity`
- `ver=1`
- `iss=rare`
- `sub=<agent_id (Ed25519 public key, base64url)>`
- `lvl=L0|L1|L2`
- `claims.profile.name`
- `iat`, `exp`, `jti`
- L1/L2 related claims are included when available:
  - `claims.owner_id` (L1 email hash based owner binding)
  - `claims.twitter` and/or `claims.github` (L2 social assets)

## Public Attestation
- Header: `typ=rare.identity.public+jws`
- Payload: shared minimum only (no platform audience field)
- Rule: `lvl` is capped to `L1` (`L2` must be downgraded to `L1`)

## Full Attestation
- Header: `typ=rare.identity.full+jws`
- Payload: shared minimum + `aud=<platform_aud>` + full claims
- Rule: `lvl` is real level (`L0/L1/L2`)
- Rule: verifier must check `aud` equals current platform audience

## Verification rules
1. Validate JWS signature with local key selected by `kid`.
2. Reject unknown `kid` unless key refresh policy resolves it.
3. Validate `iss`, payload `typ=rare.identity`, `ver=1`, `lvl`.
4. Validate header `typ`:
   - public token must not contain payload `aud`
   - full token must contain payload `aud`
5. When verifying full token, enforce `payload.aud == expected_aud`.
6. Validate time window with max 30s skew.
7. Ignore unknown claim fields for forward compatibility.

## Security notes
- `name` is display only; authz/audit keys MUST use `sub` (`agent_id`).
- Attestations SHOULD be short-lived and refreshable.
- `owner_id` for L1 email flow should use hashed form (`email:<sha256(lower(email))>`).
- Email raw value should not be persisted in long-term identity claims.
