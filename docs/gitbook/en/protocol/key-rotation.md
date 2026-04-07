# Key Rotation (RIP-0004)

Rare publishes signing keys through a well-known JWKS endpoint so platforms can survive key rotation without manual reconfiguration.

## Endpoint

```text
GET /.well-known/rare-keys.json
```

Each key entry includes:

- `kid`
- `kty=OKP`
- `crv=Ed25519`
- `x`
- `retire_at`

Rare may also publish:

- `rare_role=identity`
- `rare_role=delegation`

## Rotation Rules

Rare implementations should:

1. publish a new key before using it
2. overlap old and new keys for at least 7 days
3. keep retired keys published until previously issued tokens expire

## Verifier Cache Policy

Verifiers should:

1. cache the JWKS for 1 to 24 hours
2. refresh once immediately on unknown `kid`
3. reject the token if the `kid` still cannot be resolved

## References

- Canonical RIP: `docs/rip/rip-0004-key-rotation.md`
- API: [Well-Known Endpoints](../api-reference/well-known.md)

