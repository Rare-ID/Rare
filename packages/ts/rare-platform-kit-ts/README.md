# Rare Platform Kit

TypeScript toolkit for platforms integrating Rare with local verification-first defaults.

## What It Is

`Rare Platform Kit` helps third-party platforms issue challenges, complete Rare login, verify identity and delegation artifacts locally, and optionally ingest platform event signals back into Rare.

## Who It Is For

- Platform teams adding Rare login to Node.js or web backends
- Framework users on Express, Fastify, or Nest
- Security-conscious integrators that want local verification instead of backend coupling

## Why It Exists

Platforms adopting Rare need more than an HTTP client. They need challenge storage, replay protection, session handling, identity verification, delegation verification, and a clear boundary between public protocol artifacts and private Rare backend services.

## How It Fits Into Rare

- `rare-protocol-py` defines the public protocol and reference verification rules
- `rare-agent-sdk` produces the login and attestation materials
- `Rare Platform Kit` is the platform-side integration and local verification layer

## Quick Start

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

const rare = new RareApiClient({ rareBaseUrl: "https://api.rareid.cc" });
const kit = createRarePlatformKit({
  aud: "platform",
  rareApiClient: rare,
  challengeStore: new InMemoryChallengeStore(),
  replayStore: new InMemoryReplayStore(),
  sessionStore: new InMemorySessionStore(),
});
```

Read next:

- `QUICKSTART.md` for the public-only path
- `FULL_MODE_GUIDE.md` for registered full-attestation mode
- `DEMO_FULL_LOGIN.md` for a local full-mode platform demo using `curl`
- `EVENTS_GUIDE.md` for platform event ingest
- `examples/http-minimal.ts` for a copy-paste server flow

## Packages

- `@rare-id/platform-kit-core`
- `@rare-id/platform-kit-client`
- `@rare-id/platform-kit-web`
- `@rare-id/platform-kit-redis`
- `@rare-id/platform-kit-express`
- `@rare-id/platform-kit-fastify`
- `@rare-id/platform-kit-nest`

## Production Notes

- Local verification is the default design goal, not an optional extra.
- Platforms must validate challenge nonce one-time use and enforce replay protection.
- Full identity mode requires `payload.aud == expected_aud`.
- Public and full identity modes still require triad consistency:
  `auth_complete.agent_id == delegation.agent_id == attestation.sub`.
- Governance should cap public identity mode to `L1` even if other data is present.

## Development

```bash
pnpm install
pnpm demo:register:challenge
pnpm demo:register:complete
pnpm demo:start
pnpm -r build
pnpm -r lint
pnpm -r typecheck
pnpm -r test
```
