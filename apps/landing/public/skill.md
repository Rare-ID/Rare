---
name: rare-agent
description: Register and operate a Rare agent identity with the supported CLI-first workflow. Use when an agent needs to read Rare onboarding instructions, register on Rare, explain hosted vs self-hosted key custody, request trust upgrades, issue attestations, complete Rare-enabled platform login, or recover hosted credentials through the public `rare` / `rare-signer` interface.
---

# Rare Agent

Use this skill when the user wants an agent to read `https://rareid.cc/skill.md` and handle Rare identity onboarding or follow-up operations.

## Execution Policy

- Read the public entry first when the user explicitly points at `https://rareid.cc/skill.md`.
- Treat this skill file and its linked public materials as the maintained CLI-first reference.
- Ask only for the next input required to make progress.
- For first-time registration, ask only for `name` and `host_mode`.
- Default to the `rare` CLI for user-visible operations.
- Use `rare-signer` or `rare signer-serve` for self-hosted mode.
- Do not default to raw `curl` flows for standard agent operations.
- Do not present `rare_agent_sdk` Python imports as the supported public API.

## Default Decisions

- `rare_base_url`: `https://api.rareid.cc`
- `host_mode`: recommend `hosted-signer`
- trust level: start at `L0`
- platform login: prefer public attestation before full attestation
- production `L2` social providers: `github`, `linkedin`, `x`

## Interaction Rules

- Explain that `name` is a display name, not the identity key.
- Explain that `agent_id` is the long-term Ed25519 public key.
- Ask for `email` only when the user chooses `L1`.
- Ask for `provider` only when the user chooses `L2`, and constrain choices to `github`, `linkedin`, or `x`.
- Ask for `platform_url` when the user wants platform login.
- Ask for `aud` only for platform-bound attestation or explicit strict audience pinning.
- Explain that production `L2` currently requires the agent to already be at `L1` or higher before a social upgrade request can be created.
- Do not claim `L1` or `L2` is complete until the external email or OAuth step is finished and status is re-checked.
- Treat `start-social` success as "OAuth started", not "L2 complete". The final state must come from the callback completing and the upgrade status changing.

## Hosted Vs Self-Hosted

- `hosted-signer`: Rare manages signing behind the API. Fastest path. Best default.
- `self-hosted`: the user keeps the private key locally. Use `rare-signer` so the main CLI process does not directly hold the key.

## Workflow Order

1. Ask for `name` and `host_mode`.
2. Register the identity.
3. Confirm the result contains an `agent_id`.
4. Ask what the user wants next only after registration succeeds.
5. Branch into upgrade, attestation, rename, recovery, or platform login only when requested.

## Runtime Notes

- Check the target Rare deployment if you need the currently enabled social providers.
- Do not infer that provider support is static unless a live readiness check confirms it.

## Resource Map

- Registration, upgrade, attestation, recovery, and platform command examples: [flows.md](./flows.md)
- User-facing parameter explanations: [parameter-explanations.md](./parameter-explanations.md)
- Runtime states, heartbeat checks, and safety boundaries: [runtime-protocol.md](./runtime-protocol.md)
