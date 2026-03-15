# RIP-0002 Delegation

RIP: 0002
Title: Delegation
Status: Accepted
Type: Standards Track
Author: Rare Maintainers
Created: 2026-03-03
Updated: 2026-03-03
Requires: 0003
Replaces: None
Superseded-By: None
Discussion: https://github.com/rare-project/rare/discussions

## Abstract
This RIP defines short-lived delegation tokens that bind session keys to agent identity for login and action authorization.

## Motivation
Platforms need an agent session model that supports local verification without repeatedly calling Rare online services. Delegation tokens provide audience and scope constraints for safe action execution.

## Specification
### Token format
- JWS Compact Serialization.
- `alg=EdDSA`.
- Header `typ` MUST be `rare.delegation+jws`.

### Payload requirements
Payload MUST include:
- `typ=rare.delegation`
- `ver=1`
- `iss=agent|rare-signer`
- `agent_id`
- `session_pubkey`
- `aud`
- `scope`
- `iat`, `exp`
- `act=delegated_by_agent|delegated_by_rare`

Payload MAY include:
- `jti`

### Verification rules
Verifiers MUST:
1. Verify signature:
   - `iss=agent` uses `agent_id` public key
   - `iss=rare-signer` uses Rare signer key
2. Require exact `aud` match.
3. Require action scope to include requested operation.
4. Enforce timestamps with max 30 second clock skew.
5. Enforce replay protection when `jti` is present.

### Relationship with identity attestation
Delegation verification MUST be paired with identity verification. Platform login MUST enforce triad consistency:
- `auth_complete.agent_id == delegation.agent_id == identity_attestation.sub`

## Backward Compatibility
Delegation shape remains stable in v1. Audience binding for full identity is carried by RIP-0001 full attestation and does not require delegation payload changes.

## Security Considerations
- Delegation tokens should have short TTLs.
- Scope should be least privilege for each session.
- Replay protection should persist until token expiry.
- Triad consistency checks are mandatory to prevent mixed-identity attacks.

## Test Vectors/Examples
Example payload fields:
- `iss=agent`
- `aud=platform`
- `scope=["login","post"]`
- `act=delegated_by_agent`

## Reference Implementation
- `packages/python/rare-identity-protocol-python/src/rare_identity_protocol`
- `packages/python/rare-identity-verifier-python/src/rare_identity_verifier`
- `packages/python/rare-agent-sdk-python/tests/_platform_stub.py`
- `packages/python/rare-agent-sdk-python/tests/test_sdk.py`
