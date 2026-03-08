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
- A writable local environment
  - Python `3.11+`
  - permission to create or update local SDK state
- If logging into a platform later:
  - the platform audience string `aud`
  - the platform base URL
- If requesting `L1`:
  - an email address
- If requesting `L2`:
  - a supported social provider
  - current Beta recommendation: `github`

## Ask For Inputs Just-In-Time

Do not ask for every possible input at the start.
Ask only for the next values needed to make progress.

### Inputs needed up front

If the user did not provide these values, ask for them before registration:

- `rare_base_url`
  - default production value: `https://api.rareid.cc`
- `name`
  - initial display name for registration

### Ask later only if the workflow requires it

- `email`
  - only required for `L1`
- `provider`
  - only required for `L2`
  - default Beta provider: `github`
- `platform_base_url`
  - required only when the user wants platform login or platform-bound attestation
- `aud`
  - required only when the user wants platform login or full attestation
  - this is the platform audience string that identifies the target platform to Rare
  - think of it as the platform identifier expected inside the attestation or login flow
  - example: if a platform says "use aud `platform-demo`", then the agent must use exactly `platform-demo`

## What The Agent Can And Cannot Fully Automate

The agent can usually complete on its own:

- SDK install
- identity registration
- rename
- `L0` usage
- attestation issuance
- challenge login against a reachable platform
- local state inspection

The agent cannot fully complete without external help:

- `L1` email verification
  - requires access to the recipient inbox
- `L2` social upgrade
  - requires a real browser session and provider consent
- full end-to-end platform login
  - only if the platform itself is not running or not reachable

Do not claim the flow is fully complete until those external steps are actually done.

## Prompting Policy

Prefer this interaction order:

1. Confirm Rare API URL if it was not given.
2. Register identity first.
3. Only after registration succeeds, ask whether the user wants:
   - trust upgrade
   - platform login
   - attestation issuance
4. Ask for `aud`, `platform_base_url`, `email`, or `provider` only when that specific branch is chosen.

This keeps the first interaction minimal and avoids blocking registration on platform details.

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

Verify install:

```bash
rare --help
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

Success criteria:

- command exits with code `0`
- local state now contains an `agent_id`
- `rare --rare-url https://api.rareid.cc show-state` returns a registered identity

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

Success criteria:

- `request-upgrade` returns a `request_id`
- `upgrade-status` eventually moves to a completed state
- local state reflects the new trust level after the external step finishes

Important:

- `L1` is not complete until the mailbox link is opened
- `L2` is not complete until the GitHub OAuth browser flow returns successfully

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

## Minimal Autonomous Execution Plan

When acting independently, use this order:

1. Confirm `rare_base_url`
2. Install or verify `rare-agent-sdk`
3. Ask for `name` if it was not provided
4. Register with `hosted-signer` unless self-custody was explicitly requested
5. Run `show-state` and confirm an `agent_id` exists
6. Ask what the user wants next:
   - stop at registered identity
   - raise trust
   - issue attestation
   - log into a platform
7. If platform login or full attestation is required:
   - collect `platform_base_url` and `aud`
   - explain `aud` if the user did not know it
   - choose `public-only` first unless the user explicitly requires full attestation
8. If higher trust is required:
   - request `L1` or `L2`
   - stop and wait for the real-world verification step to finish
9. Re-check `upgrade-status`
10. Only after success, issue attestation or perform platform login

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
- Registration or login behaves unexpectedly on a reused machine
  Existing local SDK state may be influencing the flow; inspect `show-state` before retrying.

## Completion Checklist

Do not mark the task done until the relevant checks below are true:

- Registration flow
  - `show-state` shows a stable `agent_id`
- `L1`
  - email link was actually opened
  - `upgrade-status` reports completion
- `L2`
  - GitHub consent flow actually returned
  - `upgrade-status` reports completion
- Platform login
  - challenge/login command succeeded
  - resulting platform session or auth completion is visible on the platform side

## Current Production Defaults

- Rare API base URL: `https://api.rareid.cc`
- Recommended L2 provider in Beta: `github`
- Python package to install: `rare-agent-sdk`
- The SDK no longer depends on the full `rare-identity-core` Python package
