# rare-identity-protocol

Python primitives for the public Rare Identity Protocol.

## What It Is

`rare-identity-protocol` provides the fixed signing inputs, token helpers, Ed25519/JWS utilities, and name policy rules used across Rare agent and platform flows.

## Who It Is For

- SDK authors implementing Rare-compatible clients
- Platform teams that need protocol-compatible signing inputs
- Security reviewers auditing the public protocol surface

## Why It Exists

Rare uses fixed signing strings and token constraints for challenge login, delegations, attestations, upgrades, and name updates. This package gives you a reference implementation for constructing those artifacts without depending on the private Rare backend.

## How It Fits Into Rare

- `rare-identity-protocol` defines the protocol building blocks
- `rare-identity-verifier` validates protocol artifacts on the platform side
- `rare-agent-sdk` provides Agent CLI tooling on top of this package
- `rare-platform-sdk` and `@rare-id/platform-kit-*` verify and orchestrate Rare login on third-party platforms

## Quick Start

```bash
pip install rare-identity-protocol
```

```python
from rare_identity_protocol import (
    build_auth_challenge_payload,
    generate_nonce,
    now_ts,
)

issued_at = now_ts()
payload = build_auth_challenge_payload(
    aud="platform",
    nonce=generate_nonce(18),
    issued_at=issued_at,
    expires_at=issued_at + 120,
)

print(payload)
```

## Production Notes

- `agent_id` is always the Ed25519 public key, not the display name.
- Fixed signing input formats are protocol redlines and should not be changed casually.
- Names must be normalized with `trim + NFKC`, length-limited, and checked against reserved words.
- Use this package together with `rare-identity-verifier` when you need local verification.

## Development

```bash
pip install -r requirements-test.lock
pip install -e .[test] --no-deps
pytest -q
python -m build
```
