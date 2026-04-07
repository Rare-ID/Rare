# TypeScript Getting Started

The TypeScript platform kit is the fastest way to add Rare login to a Node.js platform.

## Install

For generic web handlers:

```bash
pnpm add @rare-id/platform-kit-web
```

For Express:

```bash
pnpm add @rare-id/platform-kit-web @rare-id/platform-kit-express
```

## Minimal Setup

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

export const resolveRareSession = createRareSessionResolver({
  sessionStore,
});
```

## Required Environment

```bash
PLATFORM_AUD=platform.example.com
```

Optional:

```bash
RARE_BASE_URL=https://api.rareid.cc
RARE_SIGNER_PUBLIC_KEY_B64=<rare signer public key>
PLATFORM_ID=platform-example-com
```

## Auth Flow

Issue a challenge:

```ts
const challenge = await rare.issueChallenge();
```

Complete login:

```ts
const result = await rare.completeAuth({
  nonce: body.nonce,
  agentId: body.agent_id,
  sessionPubkey: body.session_pubkey,
  delegationToken: body.delegation_token,
  signatureBySession: body.signature_by_session,
  publicIdentityAttestation: body.public_identity_attestation,
  fullIdentityAttestation: body.full_identity_attestation,
});
```

The SDK will:

- verify the signed challenge
- verify the delegation token
- verify the identity attestation
- enforce triad consistency
- create a platform session

## Session Lookup

```ts
const session = await resolveRareSession({
  authorizationHeader: request.headers.get("authorization"),
  cookieHeader: request.headers.get("cookie"),
});
```

## Next Pages

- [Express Integration](express-integration.md)
- [Next.js Integration](nextjs-integration.md)
- [TypeScript API Reference](api-reference.md)

