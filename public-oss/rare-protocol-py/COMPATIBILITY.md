# Compatibility

This repository is the source of truth for the public Rare protocol behavior used by the Python reference implementation.

## Current Matrix

| Package | Version | Compatible protocol behavior |
| --- | --- | --- |
| `rare-identity-protocol` | `0.1.0` | current public RIP documents in this repository |
| `rare-identity-verifier` | `0.1.0` | validates current public RIP documents in this repository |
| `rare-agent-sdk` | `0.2.0` | expects current signing inputs and token rules |
| `@rare-id/platform-kit-*` | `0.1.0` | expects current signing inputs and token rules |

## Compatibility Rules

- Changes to fixed signing inputs are protocol-breaking.
- Changes to required token claims or validation rules are compatibility-sensitive.
- New optional claims should remain forward compatible.
- Unknown claims should be ignored by verifiers unless explicitly documented otherwise.

## When Updating Protocol Behavior

If a change affects interoperability:

1. update the RIP docs
2. update protocol tests and vectors
3. update verifier tests
4. document the change in release notes
