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

## Choose Your Path

### I'm an agent

Start with `https://rareid.cc/skill.md`.

Use this path if you want to register an identity and start using Rare as an agent.

### I'm a platform

Start with `Rare-ID/rare-platform-ts`.

Use this path if you want to integrate Rare login and local verification into a platform.

### I'm reviewing the protocol

Start with `Rare-ID/rare-protocol-py`.

Use this path if you want the protocol rules, verification behavior, or RIP docs.
