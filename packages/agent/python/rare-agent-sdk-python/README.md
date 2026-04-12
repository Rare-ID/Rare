# rare-agent-sdk

CLI tooling for the Rare agent identity lifecycle.

## What It Is

`rare-agent-sdk` keeps its historical package name for now, but the supported public surface is CLI-only. It helps an agent register, manage identity, request upgrades, issue attestations, and complete Rare login flows against Rare-compatible platforms.

## Who It Is For

- Agent operators and tool builders that want a packaged CLI
- Teams choosing between Rare hosted signing and self-hosted keys
- Operators testing end-to-end login and attestation flows locally

## Why It Exists

Rare login is not just a single token exchange. Agents need to manage keys, sign fixed protocol payloads, refresh attestations, handle human verification upgrades, and produce delegation material for platforms. This package ships the Agent CLI and local signer needed to operate that lifecycle.

## How It Fits Into Rare

- `rare-identity-protocol` defines the public protocol rules
- `rare-agent-sdk` provides the Agent CLI and local signer tooling
- `Rare Platform Kit` is the platform-side toolkit that verifies what this CLI produces

## Quick Start

```bash
pip install rare-agent-sdk
```

Use the hosted Rare API:

```bash
rare register --name alice --rare-url https://api.rareid.cc
rare refresh-attestation --rare-url https://api.rareid.cc
rare show-state --rare-url https://api.rareid.cc
```

## Production Notes

- `agent_id` is the Ed25519 public key and remains the primary identity key.
- Two operating modes are supported:
  - `hosted-signer`: Rare manages signing on behalf of the agent.
  - `self-hosted`: the agent keeps its own private key.
- Self-hosted keys are stored separately from the JSON state file under `~/.config/rare/keys/` with `0600` permissions.
- `rare-signer` lets you keep the private key out of the main CLI process by signing over local IPC.
- Imported Python modules under `rare_agent_sdk` are internal implementation details and are not a supported public API.

## Common CLI Flows

```bash
# start a local signer for self-hosted mode
rare-signer

# register and manage identity
rare register --name alice
rare register --name alice --key-mode self-hosted
rare set-name --name alice-v2
rare refresh-attestation

# request human verification upgrades
rare request-upgrade --level L1 --email alice@example.com
rare send-l1-link --request-id <request_id>
rare upgrade-status --request-id <request_id>
rare request-upgrade --level L2
rare start-social --request-id <request_id> --provider linkedin

# produce login material for a third-party platform
rare issue-full-attestation --aud platform
rare login --aud platform --platform-url http://127.0.0.1:8000/platform
rare login --aud platform --public-only

# recovery and inspection
rare recovery-factors
rare recover-hosted-token-email
rare recover-hosted-token-email-verify --token <token>
rare recover-hosted-token-social-start --provider x
rare show-state --paths
```

## Troubleshooting

Recent CLI error responses include a `runtime` block with:

- `python_executable`
- `sdk_version`
- `cli_module_path`

Use these commands to confirm the shell command, Python environment, and installed package all match:

```bash
which rare
python3 -m pip show rare-agent-sdk
python3 - <<'PY'
import sys, importlib.metadata, rare_agent_sdk.cli
print("python:", sys.executable)
print("rare-agent-sdk:", importlib.metadata.version("rare-agent-sdk"))
print("cli:", rare_agent_sdk.cli.__file__)
PY
```

To bypass shell PATH issues, run the CLI through the same Python interpreter explicitly:

```bash
python3 -m rare_agent_sdk.cli --rare-url https://api.rareid.cc show-state
```

To distinguish local environment issues from Rare API availability, verify the API directly:

```bash
curl -i -sS https://api.rareid.cc/healthz
curl -i -sS -X POST https://api.rareid.cc/v1/agents/self_register \
  -H 'content-type: application/json' \
  --data '{"name":"diag-agent"}'
```

## Development

```bash
pip install -r requirements-test.lock
pip install -e .[test] --no-deps
pytest -q
python -m build
```

## Related Repositories

- Main Rare repository: `https://github.com/Rare-ID/Rare`
