# Well-Known Endpoints

Standard well-known endpoints for key discovery and local token verification.

---

## GET /.well-known/rare-keys.json

Returns a JSON Web Key Set (JWKS) containing Rare's public Ed25519 signing keys. Platforms use these keys to verify attestation and delegation tokens locally without making an API call to Rare on every request.

**Authentication:** None (public).

### Response

The response follows the standard JWKS format defined in [RFC 7517](https://datatracker.ietf.org/doc/html/rfc7517). Each key in the set has the following properties:

| Property | Type | Description |
|---|---|---|
| `kty` | string | Key type. Always `"OKP"` (Octet Key Pair) for Ed25519 keys. |
| `crv` | string | Curve identifier. Always `"Ed25519"`. |
| `kid` | string | Unique key identifier. Used to match a key to the `kid` header in a JWS token. |
| `x` | string | The public key, base64url-encoded. |
| `retire_at` | integer | Planned retirement timestamp for the key. |
| `rare_role` | string | Optional Rare-specific role hint such as `identity` or `delegation`. |

### Caching Recommendations

Platforms should cache the key set locally to avoid repeated network calls. The recommended strategy is:

1. Fetch and cache the JWKS on startup.
2. When verifying a token, look up the key by its `kid` header claim.
3. If a `kid` is not found in the local cache, re-fetch the JWKS from this endpoint.
4. If the `kid` is still not found after a fresh fetch, reject the token.

This approach ensures that key rotations are picked up automatically while minimizing network overhead.

### Example

```json
// Request
GET /.well-known/rare-keys.json
```

```json
// Response  200 OK
{
  "issuer": "rare",
  "keys": [
    {
      "kty": "OKP",
      "crv": "Ed25519",
      "kid": "rare-signer-2026-01",
      "x": "11qYAYKxCrfVS_7TyWQHOg7hcvPapiMlrwIaaPcHURo",
      "retire_at": 1770000000,
      "rare_role": "delegation"
    }
  ]
}
```
