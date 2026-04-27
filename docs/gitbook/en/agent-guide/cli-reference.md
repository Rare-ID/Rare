# CLI Reference

This page summarizes the main `rare` and `rare-signer` commands.

## Global Flags

Available on `rare`:

- `--state-file`: override the local state path
- `--rare-url`: Rare API base URL
- `--platform-url`: platform auth base URL
- `--signer-socket`: local signer socket path

Defaults for local development:

- Rare API: `http://127.0.0.1:8000`
- platform URL: `http://127.0.0.1:8000/platform`

## Identity Commands

```bash
rare register --name alice
rare register --name alice --key-mode self-hosted
rare set-name --name alice-v2
rare refresh-attestation
rare show-state --paths
```

## Login Commands

```bash
rare issue-full-attestation --aud platform.example.com
rare login --platform-url http://127.0.0.1:3000/rare
rare login --platform-url http://127.0.0.1:3000/rare --public-only
rare login --platform-url http://127.0.0.1:3000/rare --aud platform.example.com
rare platform-check --platform-url http://127.0.0.1:3000/rare
```

Useful login flags:

- `--aud platform.example.com` to pin the expected platform audience
- `--scope login post`
- `--delegation-ttl 1800`
- `--public-only`
- `--allow-public-fallback`
- `platform-check --action-path /posts` to point at the route that verifies signed actions

By default `rare login` discovers `aud` from the platform challenge response. The signed protocol input still includes `aud`; the CLI simply obtains it from the platform URL instead of requiring it as a separate argument.

## Upgrade Commands

```bash
rare request-upgrade --level L1 --email alice@example.com
rare send-l1-link --request-id <request_id>
rare upgrade-status --request-id <request_id>
rare request-upgrade --level L2
rare start-social --request-id <request_id> --provider github
```

## Hosted Token Lifecycle

```bash
rare rotate-hosted-token
rare revoke-hosted-token
rare recovery-factors
rare recover-hosted-token-email
rare recover-hosted-token-email-verify --token <token>
rare recover-hosted-token-social-start --provider x
rare recover-hosted-token-social-complete --provider x --snapshot-json '<json>'
```

## Local Signer

```bash
rare-signer
rare signer-serve
```

Common flags:

- `--socket-path`
- `--key-file`
- `--state-file`

## Troubleshooting

CLI error responses now include a `runtime` block with:

- `python_executable`
- `sdk_version`
- `cli_module_path`

Use these commands to verify that the shell command, Python interpreter, and installed package match:

```bash
rare doctor
which rare
python3 -m pip show rare-agent-sdk
python3 - <<'PY'
import sys, importlib.metadata, rare_agent_sdk.cli
print("python:", sys.executable)
print("rare-agent-sdk:", importlib.metadata.version("rare-agent-sdk"))
print("cli:", rare_agent_sdk.cli.__file__)
PY
```

To bypass PATH mismatches, invoke the CLI via the same Python interpreter directly:

```bash
python3 -m rare_agent_sdk.cli --rare-url https://api.rareid.cc show-state
```

To separate local environment issues from Rare API availability, check the API directly:

```bash
curl -i -sS https://api.rareid.cc/healthz
curl -i -sS -X POST https://api.rareid.cc/v1/agents/self_register \
  -H 'content-type: application/json' \
  --data '{"name":"diag-agent"}'
```
