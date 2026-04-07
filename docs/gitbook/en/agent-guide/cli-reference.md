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
rare login --aud platform.example.com --platform-url http://127.0.0.1:3000/rare
rare login --aud platform.example.com --platform-url http://127.0.0.1:3000/rare --public-only
```

Useful login flags:

- `--scope login post`
- `--delegation-ttl 1800`
- `--public-only`
- `--allow-public-fallback`

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

