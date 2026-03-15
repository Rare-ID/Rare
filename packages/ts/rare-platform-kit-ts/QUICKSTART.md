# QUICKSTART (public-only in <=30 minutes)

This guide helps a third-party platform ship Rare login quickly with local verification.

## 1) Install

```bash
pnpm add @rare-id/platform-kit-core @rare-id/platform-kit-client @rare-id/platform-kit-web
```

## 2) Wire stores and kit

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
  // hosted-signer delegation verification requires this key
  // rareSignerPublicKeyB64: "<rare signer Ed25519 public x>",
});
```

## 3) Add two handlers

```ts
const challenge = await kit.issueChallenge("platform");
const login = await kit.completeAuth({
  nonce,
  agentId,
  sessionPubkey,
  delegationToken,
  signatureBySession,
  publicIdentityAttestation,
  fullIdentityAttestation,
});
```

## 4) Enforce protocol redlines

- Must validate `delegation_token`: `typ/aud/scope/jti/exp`.
- Must validate identity token: `typ/ver/iss`.
- Must enforce triad:
  `auth_complete.agent_id == delegation.agent_id == identity_attestation.sub`.
- Must enforce challenge nonce one-time use.
- For public identity mode, governance is capped to L1 automatically.

## 5) Validate with Agent CLI

```bash
rare register --name alice
rare login --aud platform --platform-url http://127.0.0.1:8000/platform --public-only
```

本地联调时也可以改回自建 Rare Core URL，例如 `http://127.0.0.1:8000`。
