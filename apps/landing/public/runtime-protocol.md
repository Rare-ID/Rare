# Runtime Protocol

## States

- `unregistered`
- `registered_l0`
- `upgrade_pending`
- `upgraded`
- `platform_session_ready`

## Heartbeat

Run these checks at the matching stage:

- After registration, confirm the response contains `agent_id`.
- After hosted registration, confirm the response also contains `hosted_management_token`.
- After any public attestation issue or refresh, confirm the response contains `public_identity_attestation`.
- After an upgrade request is created, persist the `request_id`.
- After an email or OAuth step completes, re-check upgrade status before claiming success.
- Before platform login, confirm `platform_url`, challenge `aud`, challenge timestamps, and a usable attestation are all present.
- Before platform action signing, confirm the current session key and session token belong to the same platform audience.

## Safety Boundaries

- Never print private keys.
- Never print the full hosted management token.
- Never dump complete local state files unless the user explicitly asks and understands the risk.
- Never explain `name` as the unique identity key.
- Never claim `L1` or `L2` is complete until the external proof step has finished and status has been verified.

## Escalation Rules

- If the user only wants initial registration, stop after registration succeeds.
- If the platform challenge does not provide an `aud`, treat the platform as not Rare-compatible and stop before platform login. Ask for `aud` only for explicit full-attestation issuance or strict pinning.
- If the user chooses `self-hosted`, explain the custody risk before starting `rare-signer`.
- If an operation fails because stronger trust is required, then ask whether to start the matching upgrade flow.
- If CLI output suggests an environment mismatch, compare `which rare`, `python3 -m pip show rare-agent-sdk`, and `python3 -m rare_agent_sdk.cli ...` before assuming a Rare API fault.
