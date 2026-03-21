---
name: rare-agent-cli
description: Register and operate a Rare agent identity with the official Agent CLI. Use when an agent should prefer `rare` and `rare-signer` over raw curl flows.
---

# Rare Agent CLI

Use this skill when the user wants CLI-first Rare onboarding or follow-up operations.

## Execution Policy

- Prefer the `rare` and `rare-signer` entrypoints.
- Treat `packages/agent/python/rare-agent-sdk-python/README.md` as the canonical CLI reference.
- Ask only for the next input required to make progress.
- For first-time registration, ask only for `name` and `host_mode`.
- Use `rare-signer` only when the user chooses `self-hosted`.
- If the user wants raw HTTP examples instead, switch to the sibling `rare-agent` curl-first skill.

## Default Decisions

- `rare_base_url`: `https://api.rareid.cc`
- `host_mode`: recommend `hosted-signer`
- trust level: start at `L0`
- platform login: prefer public attestation before full attestation
- production social providers: query the target Rare deployment if the current list matters

## Interaction Rules

- Explain that `name` is a display name, not the identity key.
- Explain that `agent_id` is the long-term Ed25519 public key.
- Ask for `email` only when the user chooses `L1`.
- Ask for `provider` only when the user chooses `L2`.
- Ask for `platform_url` and `aud` only when the user wants platform login or platform-bound attestation.
- Do not claim `L1` or `L2` is complete until the external email or OAuth step is finished and status is re-checked.

## Resource Map

- CLI command examples: [references/flows.md](./references/flows.md)
- Package README: [`packages/agent/python/rare-agent-sdk-python/README.md`](../../packages/agent/python/rare-agent-sdk-python/README.md)
- Shared explanation docs: [`skills/rare-agent/references/parameter-explanations.md`](../rare-agent/references/parameter-explanations.md)
- Shared runtime notes: [`skills/rare-agent/references/runtime-protocol.md`](../rare-agent/references/runtime-protocol.md)
