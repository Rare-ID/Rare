---
name: rare-agent
description: Register and operate a Rare agent identity with curl-first workflows, minimal just-in-time prompts, and a small local signing helper for self-hosted keys. Use when an agent needs to read Rare onboarding instructions, register on Rare, explain hosted vs self-hosted key custody, request trust upgrades, issue attestations, complete Rare-enabled platform login, or sign Rare action payloads without defaulting to the Python SDK.
---

# Rare Agent

Use this skill when the user wants an agent to read `https://rareid.cc/skill.md` and handle Rare identity onboarding or follow-up operations.

## Execution Policy

- Read the public entry first when the user explicitly points at `https://rareid.cc/skill.md`.
- Treat this skill directory as the canonical source if both the public mirror and local files are available.
- Ask only for the next input required to make progress.
- For first-time registration, ask only for `name` and `host_mode`.
- Prefer `curl` for Rare API calls.
- Use [`rare_sign.py`](./scripts/rare_sign.py) only when the user chooses `self-hosted` and a local signature is required.
- Do not default to `rare-agent-sdk`.

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
- Ask for `platform_url` and `aud` only when the user wants platform login or platform-bound attestation.
- Explain that production `L2` currently requires the agent to already be at `L1` or higher before a social upgrade request can be created.
- Do not claim `L1` or `L2` is complete until the external email or OAuth step is finished and status is re-checked.
- Treat `start-social` success as "OAuth started", not "L2 complete". The final state must come from the callback completing and the upgrade status changing.

## Hosted Vs Self-Hosted

- `hosted-signer`: Rare manages signing behind the API. Fastest path. Best default. This mode does not need `rare_sign.py` for normal Rare API flows.
- `self-hosted`: the user keeps the private key locally. Use [`rare_sign.py`](./scripts/rare_sign.py) for signing payloads.

## Workflow Order

1. Ask for `name` and `host_mode`.
2. Register the identity.
3. Confirm the result contains an `agent_id`.
4. Ask what the user wants next only after registration succeeds.
5. Branch into upgrade, attestation, rename, recovery, or platform login only when requested.

## Production Notes

- As verified on 2026-03-13, `https://api.rareid.cc/healthz` reports `enabled_social_providers` as `github`, `linkedin`, and `x`.
- As verified on 2026-03-13, the production flow works through `register -> L1 verify -> L2 request -> start-social`, and all three providers reach their real login/authorization pages.
- Do not infer that provider support is GitHub-only unless the live health/readiness checks say so.

## Resource Map

- Registration, upgrade, attestation, recovery, and platform command examples: [references/flows.md](./references/flows.md)
- User-facing parameter explanations: [references/parameter-explanations.md](./references/parameter-explanations.md)
- Runtime states, heartbeat checks, and safety boundaries: [references/runtime-protocol.md](./references/runtime-protocol.md)
- Local signing helper: [scripts/rare_sign.py](./scripts/rare_sign.py)
