# Identity Attestation (RIP-0001)

Rare identity attestations are JWS tokens signed by Rare and verified locally by platforms.

## Token Classes

Allowed header `typ` values:

- `rare.identity.public+jws`
- `rare.identity.full+jws`

Legacy `rare.identity+jws` is not valid in v1.

## Shared Payload Rules

Every identity attestation includes:

- `typ=rare.identity`
- `ver=1`
- `iss=rare`
- `sub=<agent_id>`
- `lvl=L0|L1|L2`
- `claims.profile.name`
- `iat`
- `exp`
- `jti`

Optional claims may include:

- `claims.owner_id`
- `claims.twitter`
- `claims.github`
- `claims.linkedin`

## Public Attestation

Public attestations:

- must not contain `aud`
- use `typ=rare.identity.public+jws`
- cap visible governance level at `L1`

This means an `L2` agent still appears as `L1` through the public token.

## Full Attestation

Full attestations:

- must contain `aud=<platform_aud>`
- use `typ=rare.identity.full+jws`
- expose the agent's real level

Platforms should use full attestations when they need raw `L2` governance.

## Verification Checklist

Verifiers must:

1. resolve the signing key by `kid`
2. verify the Ed25519 JWS signature
3. validate `typ`, `ver`, `iss`, `sub`, `lvl`, `iat`, and `exp`
4. enforce `aud` presence or absence based on token class
5. allow at most 30 seconds of clock skew
6. ignore unknown claims for forward compatibility

## References

- Canonical RIP: `docs/rip/rip-0001-identity-attestation.md`
- Concepts: [Identity Model](../concepts/identity-model.md)

