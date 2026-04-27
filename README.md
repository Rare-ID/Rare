<p align="center">
  <img src="docs/assets/rare-banner.svg" alt="Rare banner" width="900" />
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="https://rareid.cc">
    <img alt="Website" src="https://img.shields.io/badge/Website-rareid.cc-111111?style=for-the-badge" />
  </a>
  <a href="https://github.com/Rare-ID/Rare">
    <img alt="GitHub" src="https://img.shields.io/badge/GitHub-Rare--ID%2FRare-111111?style=for-the-badge" />
  </a>
  <a href="https://x.com/rareaip">
    <img alt="X" src="https://img.shields.io/badge/X-@rareaip-111111?style=for-the-badge" />
  </a>
  <a href="https://discord.gg/SNWYHS4nfW">
    <img alt="Discord" src="https://img.shields.io/badge/Discord-Join%20Community-111111?style=for-the-badge" />
  </a>
</p>

## Why Rare

Most internet identity is built for humans: emails, passwords, and OAuth accounts. Agents need something else. They identify with keys, act with signatures, and need trust and permissions that can travel across products. Rare packages that into a public protocol, a reference service, an Agent CLI, and platform integration kits.

## Core Model

- `agent_id` is always the Ed25519 public key.
- Control is proven with signatures, not bearer identity tokens.
- Rare trust is expressed through attestations such as `L0`, `L1`, and `L2`.
- Platforms authenticate delegated session keys, not the long-term identity key directly.
- Replay protection and fixed signing inputs are protocol requirements, not implementation details.

## What Rare Provides

- Portable agent identity across products and platforms
- Trust signaling that platforms can use for governance
- Short-lived capability sessions instead of long-lived shared secrets
- Public protocol specs, test vectors, and reference implementations

## Quick Start

### Agent Quick Start

Copy this prompt into your agent:

```text
Read https://www.rareid.cc/skill.md and follow the instructions to register Rare
```

If you want your agent to join Rare, start with `https://www.rareid.cc/skill.md`. That page contains the exact instructions your agent should follow.

Rare currently publishes `skills/rare-agent/` as the public CLI-based Agent operating skill.
CLI usage remains documented in `packages/agent/python/rare-agent-sdk-python/README.md`.

The supported Agent package interface is the `rare` / `rare-signer` CLI surface. `rare_agent_sdk` Python imports are not a supported public API.

Platform login is URL-first. In normal flows the CLI asks the platform for a challenge, reads the returned `aud`, and signs against that audience:

```bash
rare login --platform-url http://127.0.0.1:8000/platform --public-only
rare platform-check --platform-url http://127.0.0.1:8000/platform
```

Use `--aud <expected_aud>` only when you want to pin the expected platform audience explicitly. `rare issue-full-attestation --aud <aud>` still requires an audience because it does not contact a platform challenge endpoint.

### Platform Quick Start

TypeScript:

```bash
pnpm add @rare-id/platform-kit-core @rare-id/platform-kit-client @rare-id/platform-kit-web
```

```ts
import { RareApiClient } from "@rare-id/platform-kit-client";
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKit,
} from "@rare-id/platform-kit-web";

const rareApiClient = new RareApiClient({
  rareBaseUrl: "https://api.rareid.cc",
});

const kit = createRarePlatformKit({
  aud: "platform",
  rareApiClient,
  challengeStore: new InMemoryChallengeStore(),
  replayStore: new InMemoryReplayStore(),
  sessionStore: new InMemorySessionStore(),
  // Required when you verify hosted-signer delegations.
  // rareSignerPublicKeyB64: "<rare signer Ed25519 public x>",
});
```

Python:

```bash
pip install rare-platform-sdk
```

```python
from rare_platform_sdk import (
    InMemoryChallengeStore,
    InMemoryReplayStore,
    InMemorySessionStore,
    RareApiClient,
    RarePlatformKitConfig,
    create_rare_platform_kit,
)

rare_api_client = RareApiClient(rare_base_url="https://api.rareid.cc")
kit = create_rare_platform_kit(
    RarePlatformKitConfig(
        aud="platform",
        rare_api_client=rare_api_client,
        challenge_store=InMemoryChallengeStore(),
        replay_store=InMemoryReplayStore(),
        session_store=InMemorySessionStore(),
        # Required when you verify hosted-signer delegations.
        # rare_signer_public_key_b64="<rare signer Ed25519 public x>",
    )
)
```

Platform integration documentation starts here:

- `docs/platform/README.md`
- `docs/platform/typescript.md`
- `docs/platform/python.md`
- `packages/platform/python/rare-platform-sdk-python/README.md`
- `packages/platform/ts/rare-platform-kit-ts/README.md`

Notes:

- Production Rare API base URL is `https://api.rareid.cc` and does not append `/rare`.
- Local development should use the exact mounted Rare Core base URL, for example `http://127.0.0.1:8000` or `http://127.0.0.1:8000/rare`.
- `docs/platform/README.md` is the canonical platform docs index.
- `docs/platform/typescript.md` is the canonical TypeScript guide.
- `docs/platform/python.md` is the canonical Python guide.

## Use Cases

- Autonomous AI agents that need cryptographic identity across tools
- Agent marketplaces where trust and history should travel with the agent
- API ecosystems that want capability gating based on Rare trust levels
- Cross-platform governance systems that share abuse and policy signals

## Repository Map

- `packages/shared/python/rare-identity-protocol-python/`: protocol primitives and signing inputs
- `packages/shared/python/rare-identity-verifier-python/`: Python verification helpers
- `services/rare-identity-core/`: FastAPI reference implementation of the Rare API
- `packages/agent/python/rare-agent-sdk-python/`: Agent CLI package and local signer tooling
- `packages/platform/python/rare-platform-sdk-python/`: Python platform SDK source tree
- `packages/platform/ts/rare-platform-kit-ts/`: TypeScript platform SDK source tree
- `docs/rip/`: RIP specifications and protocol vectors
- `skills/rare-agent/`: maintained public CLI-based Agent operating skill
- `scripts/`: test, validation, and release helper scripts

## Documentation

- `docs/platform/README.md`: platform docs index
- `docs/platform/typescript.md`: TypeScript platform integration guide
- `docs/platform/python.md`: Python platform integration guide
- `docs/rip/RIP_INDEX.md`: protocol index
- `docs/release-guide.md`: package release workflow
- `packages/agent/python/rare-agent-sdk-python/README.md`: Agent CLI usage
- `packages/platform/python/rare-platform-sdk-python/README.md`: Python platform SDK guide
- `packages/platform/ts/rare-platform-kit-ts/README.md`: TypeScript platform SDK guide

## More Links

- Website: `https://rareid.cc`
- Whitepaper: `https://rareid.cc/whitepaper`
- Docs: `https://rareid.cc/docs`
- GitHub org: `https://github.com/Rare-ID`
- X: `https://x.com/rareaip`
- Discord: `https://discord.gg/SNWYHS4nfW`

## Local Development

Set up the workspace:

```bash
just setup
```

Or set up Python manually:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
pip install -r ./packages/shared/python/rare-identity-protocol-python/requirements-test.lock
pip install -r ./packages/shared/python/rare-identity-verifier-python/requirements-test.lock
pip install -e "./packages/shared/python/rare-identity-protocol-python[test]"
pip install -e "./packages/shared/python/rare-identity-verifier-python[test]"
pip install -r ./services/rare-identity-core/requirements-test.lock
pip install -r ./packages/agent/python/rare-agent-sdk-python/requirements-test.lock
pip install -r ./packages/platform/python/rare-platform-sdk-python/requirements-test.lock
pip install -e "./services/rare-identity-core[test]"
pip install -e "./packages/agent/python/rare-agent-sdk-python[test]"
pip install -e "./packages/platform/python/rare-platform-sdk-python[test]"
```

Run the standard checks:

```bash
just security
just test
```

Equivalent direct commands:

```bash
python scripts/validate_rip_docs.py --strict
python scripts/check_repo_hygiene.py
./scripts/security_check.sh
./scripts/test_all.sh
python -m compileall packages/shared/python/rare-identity-protocol-python packages/shared/python/rare-identity-verifier-python services/rare-identity-core packages/agent/python/rare-agent-sdk-python packages/platform/python/rare-platform-sdk-python
```

## Contributing

See `CONTRIBUTING.md`, `SECURITY.md`, and `SUPPORT.md`.
