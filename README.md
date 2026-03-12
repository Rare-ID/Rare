# Rare

Rare is an identity and trust stack for AI agents on third-party platforms.
This repository is the public entrypoint to the Rare open source ecosystem.
Start with the repo that matches your role: protocol, agent, or platform.

## Start Here

### `Rare-ID/rare-protocol-py`

Protocol and verification reference.

For auditors, security reviewers, and protocol implementers.

Start here if you need the protocol rules, verifier behavior, or RIP docs.

### `Rare-ID/rare-agent-python`

Agent identity lifecycle SDK.

For agent builders.

Start here if you need registration, attestation, login, or key-management flows.

### `Rare-ID/rare-platform-ts`

Platform integration toolkit.

For platforms verifying Rare identities.

Start here if you need challenge handling, local verification, replay protection, or framework adapters.

## Architecture

```text
Agent SDK -> Rare protocol artifacts -> Platform Kit -> local verification
```

Agents produce Rare protocol artifacts.
Platforms verify them locally using the platform kit.

## Fastest Paths

### I'm building an agent

1. Go to `Rare-ID/rare-agent-python`.
2. Register an agent and issue login materials.
3. Use `Rare-ID/rare-platform-ts` on the receiving platform side.

### I'm integrating a platform

1. Go to `Rare-ID/rare-platform-ts`.
2. Issue a challenge and complete auth with local verification.
3. Check `Rare-ID/rare-protocol-py` if you need protocol or verifier details.

## Stability

Rare OSS is pre-`1.0`. Expect some API and protocol-facing changes; check each repository for version-specific details.
