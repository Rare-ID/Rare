# Rare Platform Kit

TypeScript toolkit for platforms integrating Rare with adoption-first defaults.

## Integration Modes

- `public-only / quickstart`: start here for first integration
- `full-mode / production`: add platform registration, durable stores, full attestation, and event ingest

Quickstart keeps the Rare security model but reduces setup to:

- one required env: `PLATFORM_AUD`
- two auth endpoints
- one session helper or middleware

## Quickstart

Install the package that matches your app:

```bash
pnpm add @rare-id/platform-kit-web
```

For Express:

```bash
pnpm add @rare-id/platform-kit-web @rare-id/platform-kit-express
```

Bootstrap Rare from env:

```ts
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKitFromEnv,
} from "@rare-id/platform-kit-web";

const rare = createRarePlatformKitFromEnv({
  challengeStore: new InMemoryChallengeStore(),
  replayStore: new InMemoryReplayStore(),
  sessionStore: new InMemorySessionStore(),
});
```

Defaults:

- `RARE_BASE_URL=https://api.rareid.cc`
- `RARE_SIGNER_PUBLIC_KEY_B64` auto-discovered from Rare JWKS when omitted
- `PLATFORM_ID` derived from `PLATFORM_AUD` for full-mode workflows

## Express Helpers

```ts
import {
  createExpressRareRouter,
  createRareActionMiddleware,
  createRareSessionMiddleware,
} from "@rare-id/platform-kit-express";
```

## Starter Templates

- Next.js App Router starter:
  `starters/nextjs-app-router`
- Express starter:
  `starters/express`

## Read Next

- `QUICKSTART.md`
- `FULL_MODE_GUIDE.md`
- `EVENTS_GUIDE.md`
- `DEMO_FULL_LOGIN.md`
