# rare-identity-verifier

Python verification helpers for Rare identity attestations and delegations.

## What It Is

`rare-identity-verifier` validates Rare identity tokens, delegation tokens, and Rare JWKS documents with the protocol redlines enforced.

## Who It Is For

- Python platforms integrating Rare login
- Backend services that need local verification-first behavior
- Auditors reviewing Rare token validation logic

## Why It Exists

Platforms should be able to verify Rare-issued artifacts locally instead of treating the Rare API as an always-online oracle. This package centralizes the identity and delegation checks that matter for production integrations.

## How It Fits Into Rare

- `rare-identity-protocol` constructs protocol artifacts
- `rare-identity-verifier` validates those artifacts
- `rare-agent-sdk` produces agent-side materials
- `@rare-id/platform-kit-*` offers the TypeScript equivalent for platform integrations

## Quick Start

```bash
pip install rare-identity-verifier
```

```python
from rare_identity_verifier import parse_rare_jwks, verify_identity_attestation

jwks = parse_rare_jwks({
    "keys": [
        {
            "kid": "rare-key-1",
            "kty": "OKP",
            "crv": "Ed25519",
            "x": "<rare signer public key>",
        }
    ]
})

result = verify_identity_attestation(
    "<identity_jws>",
    key_resolver=lambda kid: jwks.get(kid),
    expected_aud="platform",
)

print(result.payload["sub"], result.payload["lvl"])
```

## Production Notes

- Identity token headers only allow `rare.identity.public+jws` and `rare.identity.full+jws`.
- Public identity tokens must not contain `aud`; full identity tokens must match the expected audience.
- Delegation verification must enforce `aud`, `scope`, `jti`, and `exp`.
- Platform login still needs identity triad consistency checks outside the raw token verification step.

## Development

```bash
pip install -r requirements-test.lock
pip install -e .[test] --no-deps
pytest -q
python -m build
```
