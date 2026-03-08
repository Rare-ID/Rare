# Rare Identity Protocol for Python

Python reference package for the public Rare Identity Protocol.

This repository exposes the protocol primitives that third-party agents and platforms can rely on without depending on the private Rare backend implementation.

## Included

- `rare_identity_protocol`
  - signing inputs
  - challenge helpers
  - JWS / Ed25519 helpers
  - name normalization and validation
- `rare_identity_verifier`
  - identity attestation verification
  - delegation verification
  - Rare JWKS verification helpers
- `docs/`
  - RIP specifications
- `tests/`
  - protocol and verifier tests

## Install

```bash
pip install rare-identity-protocol
```

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
