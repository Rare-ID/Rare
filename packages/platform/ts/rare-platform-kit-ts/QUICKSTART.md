# QUICKSTART (public-only / adoption-first)

This path is for the first Rare integration on a platform.

## Install

```bash
pnpm add @rare-id/platform-kit-web
```

For Express:

```bash
pnpm add @rare-id/platform-kit-web @rare-id/platform-kit-express
```

## Bootstrap from env

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

const rare = createRarePlatformKitFromEnv({
  challengeStore,
  replayStore,
  sessionStore,
});

const resolveRareSession = createRareSessionResolver({ sessionStore });
```

Required env:

- `PLATFORM_AUD`

Optional env:

- `RARE_BASE_URL`
- `RARE_SIGNER_PUBLIC_KEY_B64`

Defaults:

- `RARE_BASE_URL=https://api.rareid.cc`
- signer key via Rare JWKS when `RARE_SIGNER_PUBLIC_KEY_B64` is absent

## Add Two Auth Endpoints

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

Express shortcut:

```ts
import { createExpressRareRouter } from "@rare-id/platform-kit-express";

app.use("/rare", createExpressRareRouter(rare));
```

## Add Session Handling

Generic route handlers:

```ts
const session = await resolveRareSession({
  authorizationHeader: request.headers.get("authorization"),
  cookieHeader: request.headers.get("cookie"),
});
```

Express:

```ts
import { createRareSessionMiddleware } from "@rare-id/platform-kit-express";

app.get("/me", createRareSessionMiddleware({ sessionStore }), handler);
```

## Verify Delegated Writes

```ts
import { createRareActionMiddleware } from "@rare-id/platform-kit-express";
```

Use it on routes that accept delegated signed actions.

## Security Notes

Quickstart still enforces:

- challenge nonce one-time use
- delegation replay protection
- identity/delegation triad consistency
- local attestation verification
- public-mode governance cap to `L1`

## Local Validation

```bash
rare register --name alice
rare login --platform-url http://127.0.0.1:<port>/rare --public-only
rare platform-check --platform-url http://127.0.0.1:<port>/rare
```

The platform auth challenge must return `aud`. The Rare CLI discovers that value from `POST <platform-url>/auth/challenge`; `--aud <platform_aud>` is only needed as a strict expected-audience pin.
