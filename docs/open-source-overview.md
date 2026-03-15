# Rare Open Source Overview

Rare is an identity and trust stack for AI agents operating on third-party platforms.

## Public Repositories

### `Rare-ID/rare-protocol-py`

Public protocol and verification reference for Python.

- protocol signing inputs
- Ed25519 / JWS helpers
- identity and delegation verification
- RIP documents
- protocol tests and vectors

Use this repository if you need to understand or audit the protocol itself.

### `Rare-ID/rare-agent-python`

Python SDK and CLI for the agent identity lifecycle.

- register an agent
- manage hosted or self-hosted keys
- refresh attestations
- request L1/L2 upgrades
- produce Rare login materials for platforms

Use this repository if you are building an agent.

### `Rare-ID/rare-platform-ts`

TypeScript toolkit for platform-side Rare integration.

- challenge issuance
- local verification-first login
- session and replay handling
- framework adapters for Express, Fastify, and Nest

Use this repository if you are integrating Rare into a platform.

## Recommended Reading Order

1. Start with `Rare-ID/rare-protocol-py` if you need protocol or security context.
2. Go to `Rare-ID/rare-agent-python` if you are building an agent.
3. Go to `Rare-ID/rare-platform-ts` if you are integrating a platform.

## Fast Adoption Paths

### Agent developer

1. Install `rare-agent-sdk`
2. Register an agent
3. Refresh public attestation
4. Use `rare login` or SDK login against your platform

### Platform developer

1. Install `@rare-id/platform-kit-web`
2. Issue a challenge
3. Complete auth with local verification
4. Enforce replay and triad checks

### Auditor or protocol reviewer

1. Read the RIP docs
2. Review verifier behavior
3. Check protocol vectors and tests

## Compatibility Snapshot

| Component | Current workspace version | Public role | Depends on |
| --- | --- | --- | --- |
| `rare-identity-protocol` | `0.1.0` | protocol primitives | cryptography |
| `rare-identity-verifier` | `0.1.0` | Python verification | `rare-identity-protocol` |
| `rare-agent-sdk` | `0.2.0` | agent SDK and CLI | `rare-identity-protocol` |
| `@rare-id/platform-kit-*` | `0.1.0` | platform integration | public protocol rules |

Current versions are still pre-`1.0`. Public API and protocol-facing changes should be treated carefully and documented explicitly.

## Notes

This document is the source draft for the public entrypoint template at `open-source/public-oss/Rare/README.md`.
