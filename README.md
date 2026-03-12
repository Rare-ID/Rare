# Rare Open Source

Rare is an identity and trust stack for AI agents operating on third-party platforms.

This repository is the public entrypoint for the Rare open source ecosystem.

## What Rare Open Source Includes

Rare OSS is organized into three layers:

- protocol
- agent
- platform

## Repositories

### `Rare-ID/rare-protocol-py`

Public protocol and verification reference for Python.

Use this if you need:

- protocol signing inputs
- Ed25519 / JWS helpers
- identity and delegation verification
- RIP documents
- protocol tests and vectors

### `Rare-ID/rare-agent-python`

Python SDK and CLI for the agent identity lifecycle.

Use this if you need:

- agent registration
- hosted or self-hosted key flows
- attestation refresh
- L1/L2 upgrade flows
- login material generation for platforms

### `Rare-ID/rare-platform-ts`

TypeScript toolkit for platform-side Rare integration.

Use this if you need:

- challenge issuance
- local verification-first login
- replay and session handling
- Express / Fastify / Nest adapters

## How The Pieces Fit Together

```text
Agent SDK -> signs / requests -> Rare protocol artifacts -> Platform Kit -> local verification
```

## Choose Your Starting Point

### Protocol reviewer or auditor

Start with `Rare-ID/rare-protocol-py`.

### Agent developer

Start with `Rare-ID/rare-agent-python`.

### Platform integrator

Start with `Rare-ID/rare-platform-ts`.

## Recommended Reading Order

1. Read `Rare-ID/rare-protocol-py` for protocol and security context.
2. Read `Rare-ID/rare-agent-python` if you are building an agent.
3. Read `Rare-ID/rare-platform-ts` if you are integrating Rare into a platform.

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

## Compatibility Snapshot

| Component | Current workspace version | Public role | Depends on |
| --- | --- | --- | --- |
| `rare-identity-protocol` | `0.1.0` | protocol primitives | cryptography |
| `rare-identity-verifier` | `0.1.0` | Python verification | `rare-identity-protocol` |
| `rare-agent-sdk` | `0.2.0` | agent SDK and CLI | `rare-identity-protocol` |
| `@rare-id/platform-kit-*` | `0.1.0` | platform integration | public protocol rules |

Current versions are still pre-`1.0`. Public API and protocol-facing changes should be treated carefully and documented explicitly.
