---
name: rare-agent
description: Use when an AI agent needs to onboard to Rare, register an identity, request trust upgrades, obtain public or full attestations, log into a Rare-enabled platform, and sign actions through the Python SDK or CLI against a deployed Rare API.
---

# Rare Agent Skill

This file is intentionally written in `SKILL.md` format.
If you want Codex or another agent runner to load it as a reusable skill, copy it to:

```text
<skill-folder>/SKILL.md
```

## When To Use This Skill

Use this skill when an agent needs to:

- register an identity on Rare
- choose between `hosted-signer` and `self-hosted` key custody
- raise trust from `L0` to `L1` or `L2`
- obtain identity attestations for a platform
- complete Rare challenge login against a platform
- sign delegated actions after login

Do not use this skill for platform-side verification logic. That belongs in [FOR_PLATFORM.md](/Volumes/ST7/Projects/Rare/FOR_PLATFORM.md).

## What The Agent Needs

- A Rare API base URL
  Example production value: `https://api.rareid.cc`
- The Python SDK
  Install with `pip install rare-agent-sdk`
- If logging into a platform:
  - the platform audience string `aud`
  - the platform base URL
- If requesting `L1`:
  - an email address
- If requesting `L2`:
  - a supported social provider
  - current Beta recommendation: `github`

## Default Decisions

- Prefer `hosted-signer` unless the user explicitly needs self-custodied signing keys.
- Prefer `L1` and `L2` only when the platform policy requires stronger trust than `L0`.
- Prefer public attestation login first when the platform is not Rare-registered.
- Prefer full attestation login only for Rare-registered platforms with a matching `aud`.

## Identity Model

- `L0`: registered key only
- `L1`: human email verified
- `L2`: stronger human verification through social proof

The agent identifier is always `agent_id` (the Ed25519 public key). Display `name` is not the identity key.

## Quick Start

### 1) Install

```bash
pip install rare-agent-sdk
```

### 2) Register

Hosted signer:

```bash
rare --rare-url https://api.rareid.cc register --name alice
```

Self-hosted signer:

```bash
rare --rare-url https://api.rareid.cc register --name alice --key-mode self-hosted
```

### 3) Raise trust when needed

L1:

```bash
rare --rare-url https://api.rareid.cc request-upgrade --level L1 --email alice@example.com
rare --rare-url https://api.rareid.cc upgrade-status --request-id <request_id>
```

L2:

```bash
rare --rare-url https://api.rareid.cc request-upgrade --level L2
rare --rare-url https://api.rareid.cc start-social --request-id <request_id> --provider github
rare --rare-url https://api.rareid.cc upgrade-status --request-id <request_id>
```

### 4) Log into a platform

Public-only login:

```bash
rare \
  --rare-url https://api.rareid.cc \
  --platform-url https://platform.example.com \
  login --aud platform --public-only
```

Full login for a Rare-registered platform:

```bash
rare \
  --rare-url https://api.rareid.cc \
  --platform-url https://platform.example.com \
  issue-full-attestation --aud platform

rare \
  --rare-url https://api.rareid.cc \
  --platform-url https://platform.example.com \
  login --aud platform
```

### 5) Inspect local state when debugging

```bash
rare --rare-url https://api.rareid.cc show-state
```

`show-state` redacts the hosted management token, but the state file still contains sensitive material. Do not expose it.

## Hosted vs Self-Hosted

### Hosted signer

Choose this when:

- the agent wants the fastest onboarding
- the agent does not want local key custody
- server-mediated signing is acceptable

Operationally:

- the agent only needs the SDK and API access
- Rare manages signer operations behind the API

### Self-hosted

Choose this when:

- the agent must keep the signing key locally
- the agent operator requires custody separation

Operationally:

- the SDK still works
- a local key file is created
- optional local signer daemon is available through `rare signer-serve`

## Python SDK Pattern

```python
from rare_agent_sdk import AgentClient, AgentState

state = AgentState()
client = AgentClient(
    rare_base_url="https://api.rareid.cc",
    platform_base_url="https://platform.example.com",
    state=state,
)

client.register(name="agent-1")
client.request_upgrade_l1(email="owner@example.com")
client.login(aud="platform", prefer_full=False)
```

## Recommended Agent Workflow

1. Register with `hosted-signer` unless self-custody is explicitly required.
2. Stay at `L0` unless a platform policy requires `L1` or `L2`.
3. Use public login for unregistered platforms.
4. Use full attestation only for a Rare-registered platform audience.
5. After login, sign platform actions with the delegated session key rather than the root agent key.

## Failure Cases To Recognize

- `request-upgrade L1 requires --email`
  The agent requested `L1` without an email input.
- Full attestation fails but public works
  The platform is probably not Rare-registered for that `aud`.
- Social start succeeds but `L2` does not complete
  The browser OAuth step has not finished yet.
- Login fails after a long pause
  Challenge or delegation TTL likely expired; start a fresh login.

## Current Production Defaults

- Rare API base URL: `https://api.rareid.cc`
- Recommended L2 provider in Beta: `github`
- Python package to install: `rare-agent-sdk`
- The SDK no longer depends on the full `rare-identity-core` Python package
