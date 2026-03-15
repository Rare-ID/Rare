# RIP-0001 Identity Attestation

RIP: 0001
Title: Identity Attestation
Status: Accepted
Type: Standards Track
Author: Rare Maintainers
Created: 2026-03-03
Updated: 2026-03-03
Requires: 0003, 0004
Replaces: None
Superseded-By: None
Discussion: https://github.com/rare-project/rare/discussions

## Abstract
This RIP defines Rare-signed identity attestations for platform login and governance. It specifies two token classes, public and full, so platforms can choose low-friction identity or audience-bound identity with stronger governance guarantees.

## Motivation
Rare needs a portable identity token that can be verified locally by third-party platforms. A split model between public and full attestation enables broad interoperability while preserving audience scoping for platform-specific governance.

## Specification
### Token format
- JWS Compact Serialization.
- `alg=EdDSA` with Ed25519 keys.
- Header `kid` identifies the Rare signing key.
- Header `typ` MUST be one of:
  - `rare.identity.public+jws`
  - `rare.identity.full+jws`
- Legacy header value `rare.identity+jws` is not valid in v1.

### Shared payload requirements
Payload MUST include:
- `typ=rare.identity`
- `ver=1`
- `iss=rare`
- `sub=<agent_id>` where `agent_id` is Ed25519 public key (base64url)
- `lvl=L0|L1|L2`
- `claims.profile.name`
- `iat`, `exp`, `jti`

When available, payload MAY include:
- `claims.owner_id`
- `claims.twitter`
- `claims.github`
- `claims.linkedin`

Provider mapping notes:
- `claims.twitter` remains the compatibility slot for X-linked L2 identities.
- `claims.linkedin` is optional and MAY omit `vanity_name` when only a stable LinkedIn subject/id is available.

### Public attestation
- Header: `typ=rare.identity.public+jws`
- Payload MUST NOT contain `aud`.
- Governance level in payload is capped at `L1`.

### Full attestation
- Header: `typ=rare.identity.full+jws`
- Payload MUST include `aud=<platform_aud>`.
- Governance level is the real level (`L0`, `L1`, or `L2`).

### Verification rules
Verifiers MUST:
1. Verify signature using the key selected by `kid`.
2. Reject unresolved `kid` unless local key refresh resolves it.
3. Validate `typ`, `ver`, `iss`, `sub`, `lvl`, `iat`, and `exp`.
4. Enforce `aud` rules by header `typ`:
   - public token: `aud` absent
   - full token: `aud` present and equals expected audience
5. Apply max 30 second clock skew.
6. Ignore unknown claims for forward compatibility.

## Backward Compatibility
This RIP intentionally drops legacy `typ=rare.identity+jws`. Integrations still using legacy type must migrate to the public/full split. No signing input string changes are introduced.

## Security Considerations
- `sub` (`agent_id`) is the stable identity key for authz and audit.
- `name` is display data only and MUST NOT be used as an authorization key.
- Attestations should be short-lived and refreshable.
- `owner_id` for email-backed L1 identity should use hashed form and avoid storing raw email in persistent claims.

## Test Vectors/Examples
- Test vectors: `services/rare-identity-core/docs/test-vectors/rip-v1-signing-inputs.json`
- Example full token checks:
  - header `typ=rare.identity.full+jws`
  - payload `aud=platform`
  - payload `lvl=L2`

## Reference Implementation
- `packages/python/rare-identity-protocol-python/src/rare_identity_protocol`
- `packages/python/rare-identity-verifier-python/src/rare_identity_verifier`
- `services/rare-identity-core/services/rare_api/service.py`
- `services/rare-identity-core/tests/test_core.py`
