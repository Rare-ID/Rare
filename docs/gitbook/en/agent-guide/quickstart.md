# Agent Quick Start

The supported public surface for agents is the CLI:

- `rare`
- `rare-signer`

The Python module internals under `rare_agent_sdk` are not a supported public API.

## Install

```bash
pip install rare-agent-sdk
```

## Hosted-Signer Flow

This is the simplest path.

```bash
rare register --name alice --rare-url https://api.rareid.cc
rare refresh-attestation --rare-url https://api.rareid.cc
rare show-state --paths
```

Hosted mode stores:

- public state in `~/.config/rare/state.json`
- the management token in a separate secret file under `~/.config/rare/keys/`

## Self-Hosted Flow

Use this when the agent must keep its own key:

```bash
rare-signer
rare register --name alice --key-mode self-hosted
rare show-state --paths
```

The local signer keeps the agent key outside the main CLI process and signs over local IPC.

## Login to a Platform

Public-only login:

```bash
rare login \
  --aud platform.example.com \
  --platform-url http://127.0.0.1:3000/rare \
  --public-only
```

Full-attestation login:

```bash
rare issue-full-attestation --aud platform.example.com
rare login \
  --aud platform.example.com \
  --platform-url http://127.0.0.1:3000/rare
```

## Next Pages

- [CLI Reference](cli-reference.md)
- [Hosted vs Self-Hosted](hosted-vs-self-hosted.md)
- [Upgrade Flows](upgrade-flows.md)

