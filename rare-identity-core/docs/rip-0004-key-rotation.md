# RIP-0004 Key Rotation

## Status
Draft (v1)

## Objective
Allow third-party local verifier continuity during Rare key rotation.

## Well-known endpoint
`GET /.well-known/rare-keys.json`

Response:
- `issuer`
- `keys[]` where each key includes:
  - `kid`
  - `kty=OKP`
  - `crv=Ed25519`
  - `x` (base64url public key)
  - `retire_at` (unix ts)

## Rotation requirements
1. New signing key MUST be published before first issuance.
2. Old and new keys MUST overlap for >=7 days.
3. Retired keys SHOULD remain published until all issued tokens expire.

## Verifier cache policy
1. Cache keys (recommended 1h-24h).
2. On unknown `kid`, attempt one immediate refresh.
3. If still unresolved, reject token and emit audit log.
