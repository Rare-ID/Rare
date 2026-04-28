# Rare Platform Integration For TypeScript

Start with the public-only quickstart. It keeps the full Rare security model but reduces first integration to:

- one required env: `PLATFORM_AUD`
- two auth endpoints
- one session helper or middleware

## Quickstart

### 1. Install

For Next.js or generic Node handlers:

```bash
pnpm add @rare-id/platform-kit-web
```

For Express:

```bash
pnpm add @rare-id/platform-kit-web @rare-id/platform-kit-express
```

### 2. Bootstrap Rare from env

```ts
import {
  InMemoryChallengeStore,
  InMemoryReplayStore,
  InMemorySessionStore,
  createRarePlatformKitFromEnv,
  createRareSessionResolver,
} from "@rare-id/platform-kit-web";

const challengeStore = new InMemoryChallengeStore();
const replayStore = new InMemoryReplayStore();
const sessionStore = new InMemorySessionStore();

export const rare = createRarePlatformKitFromEnv({
  challengeStore,
  replayStore,
  sessionStore,
});

export const resolveRareSession = createRareSessionResolver({ sessionStore });
```

Default behavior:

- reads `PLATFORM_AUD`
- defaults `RARE_BASE_URL` to `https://api.rareid.cc`
- auto-discovers `RARE_SIGNER_PUBLIC_KEY_B64` from Rare JWKS when not set
- derives `PLATFORM_ID` from `PLATFORM_AUD` for full-mode workflows

### 3. Add two auth endpoints

Minimal route logic:

```ts
const challenge = await rare.issueChallenge();

const login = await rare.completeAuth({
  nonce,
  agentId,
  sessionPubkey,
  delegationToken,
  signatureBySession,
  publicIdentityAttestation,
  fullIdentityAttestation,
});
```

For Express, use the adoption-first router:

```ts
import { createExpressRareRouter } from "@rare-id/platform-kit-express";

app.use("/rare", createExpressRareRouter(rare));
```

### 4. Add session handling

For generic handlers:

```ts
const session = await resolveRareSession({
  authorizationHeader: request.headers.get("authorization"),
  cookieHeader: request.headers.get("cookie"),
});
```

For Express:

```ts
import { createRareSessionMiddleware } from "@rare-id/platform-kit-express";

app.get("/me", createRareSessionMiddleware({ sessionStore }), handler);
```

### 5. Optional delegated action verification

```ts
import { createRareActionMiddleware } from "@rare-id/platform-kit-express";

app.post(
  "/posts",
  createRareActionMiddleware({
    kit: rare,
    action: () => "post",
    actionPayload: (req) => ({ content: String(req.body?.content ?? "") }),
  }),
  handler,
);
```

## Starter Paths

- Next.js App Router starter:
  `packages/platform/ts/rare-platform-kit-ts/starters/nextjs-app-router`
- Express starter:
  `packages/platform/ts/rare-platform-kit-ts/starters/express`

## Required Security Checks

These remain mandatory in quickstart and full-mode:

- challenge nonce one-time use
- delegation replay protection
- identity attestation verification
- triad consistency:
  `auth_complete.agent_id == delegation.agent_id == attestation.sub`
- full token `aud` enforcement in full-mode
- signed action verification against the delegated session key

Public-only caps effective governance to `L1`.

## Full-Mode Upgrade

Move to full-mode when you need:

- Rare platform registration
- platform-bound full attestation
- durable shared stores
- negative event ingest

See:

- `packages/platform/ts/rare-platform-kit-ts/FULL_MODE_GUIDE.md`

## Local Validation

```bash
rare register --name alice
rare login --aud <platform_aud> --platform-url http://127.0.0.1:<port>/rare --public-only
```
