# RIP-0004 Key Rotation

RIP: 0004
Title: Key Rotation
Status: Accepted
Type: Standards Track
Author: Rare Maintainers
Created: 2026-03-03
Updated: 2026-03-03
Requires: None
Replaces: None
Superseded-By: None
Discussion: https://github.com/rare-project/rare/discussions

## Abstract
This RIP defines Rare signing key discovery and rotation rules to preserve verifier continuity across key changes.

## Motivation
Platforms and SDKs need deterministic behavior when key ids rotate, without requiring immediate manual reconfiguration.

## Specification
### Well-known endpoint
`GET /.well-known/rare-keys.json`

Response requirements:
- `issuer`
- `keys[]` where each key includes:
  - `kid`
  - `kty=OKP`
  - `crv=Ed25519`
  - `x` (base64url public key)
  - `retire_at` (unix timestamp)

### Rotation requirements
1. A new signing key MUST be published before first token issuance.
2. Old and new keys MUST overlap for at least 7 days.
3. Retired keys SHOULD remain published until all previously issued tokens expire.

### Verifier cache policy
1. Cache key set for 1 to 24 hours.
2. On unknown `kid`, perform one immediate refresh.
3. If still unresolved, reject token and emit audit logs.

## Backward Compatibility
This RIP keeps existing key publication format and clarifies minimum overlap and cache refresh behavior.

## Security Considerations
- Overlap windows reduce denial risk during rotation.
- Immediate refresh-on-miss mitigates stale-cache failures.
- Rejecting unresolved `kid` prevents accepting unverifiable tokens.

## Test Vectors/Examples
Example key entry:

```json
{
  "kid": "rare-2026-01",
  "kty": "OKP",
  "crv": "Ed25519",
  "x": "base64url-encoded-public-key",
  "retire_at": 1770000000
}
```

## Reference Implementation
- `services/rare-identity-core/services/rare_api/main.py`
- `services/rare-identity-core/services/rare_api/service.py`
- `services/rare-identity-core/tests/test_core.py`
