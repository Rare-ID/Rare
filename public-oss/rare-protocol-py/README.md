# Rare Identity Protocol for Python

Reference implementation of the public Rare Identity Protocol for Python.

## What It Is

This repository contains the protocol-facing Python building blocks that agents and platforms can depend on without pulling in the private Rare backend implementation.

## Who It Is For

- Platform teams that need local verification of Rare tokens
- SDK authors building Rare-compatible clients
- Security auditors reviewing protocol logic and test vectors

## Why It Exists

Rare login and governance depend on fixed signing inputs, token constraints, replay rules, and public verification behavior. This repository makes those rules explicit and reusable.

## How It Fits Into Rare

- `rare_identity_protocol` builds protocol payloads, signatures, and token helpers
- `rare_identity_verifier` validates identity attestations, delegations, and Rare JWKS
- `docs/` contains the public RIP documents
- `tests/` contains protocol tests and reference vectors

This repository is the protocol layer that the Rare agent SDK and platform kit build on top of.

## Quick Start

Install the protocol primitives:

```bash
pip install rare-identity-protocol
```

Install the verifier when you need local token validation:

```bash
pip install rare-identity-verifier
```

Minimal verification example:

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

verified = verify_identity_attestation(
    "<identity_jws>",
    key_resolver=lambda kid: jwks.get(kid),
    expected_aud="platform",
)

print(verified.payload["sub"], verified.payload["lvl"])
```

## Production Notes

- `agent_id` is always the Ed25519 public key.
- Public identity tokens must not contain `aud`.
- Full identity tokens must match the platform audience.
- Delegation verification must enforce `aud`, `scope`, `jti`, `iat`, and `exp`.
- Unknown claims should be ignored for forward compatibility.

Additional docs:

- `STATUS.md`
- `COMPATIBILITY.md`

## Local Development

```bash
pip install -r requirements-test.lock
pip install -e .[test] --no-deps
pytest -q
python -m build
```

## Related Repositories

- Agent SDK: `https://github.com/Rare-ID/rare-agent-python`
- Platform SDK: `https://github.com/Rare-ID/rare-platform-ts`
