# For Platform Integration

This document is the current integration contract for a third-party platform using Rare.

## What You Need

- A unique platform audience string `aud`
- A Rare API base URL
  Example production value: `https://api.rareid.cc`
- Platform-side persistent stores for:
  - auth challenge nonces
  - replay protection
  - issued platform sessions
- TypeScript packages:

```bash
pnpm add @rare-id/platform-kit-core @rare-id/platform-kit-client @rare-id/platform-kit-web
```

You do not deploy these SDK packages to GCP. They run inside your own platform service.

## Minimal Wiring

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
});
```

`InMemory*Store` is only for local development. Production should use durable shared storage, typically Redis plus database-backed session persistence.

## Login Flow

### 1) Issue a Rare challenge

```ts
const challenge = await kit.issueChallenge("platform");
```

Return the challenge payload to the agent or browser flow that is performing Rare login.

### 2) Complete auth

```ts
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

On success you get:

- `session_token`
- `agent_id`
- `identity_mode`
- `raw_level`
- effective platform `level`

## Verification Rules You Must Enforce

- The challenge nonce must be one-time use.
- `delegation_token` must pass audience, scope, expiry, and replay checks.
- Identity attestation must pass signature and expiry checks.
- Identity triad must match exactly:

```text
auth_complete.agent_id == delegation.agent_id == attestation.sub
```

- Signed actions must be verified against the delegated session public key, not the root identity key.

These are protocol red lines, not optional heuristics.

## Public vs Full Identity

### Public identity

Use when:

- you want the fastest rollout
- you do not need Rare platform registration yet

Result:

- agents can authenticate with public attestation
- governance should treat the user as public identity mode

### Full identity

Use when:

- you want platform-bound attestations
- you want Rare to bind the identity token to your platform `aud`

Prerequisite:

- your platform must complete Rare platform registration

## Verify Signed Actions

For every signed action request, call:

```ts
const verified = await kit.verifyAction({
  sessionToken,
  action,
  actionPayload,
  nonce,
  issuedAt,
  expiresAt,
  signatureBySession,
});
```

This checks:

- platform session validity
- detached signature by delegated session key
- nonce replay protection
- signed TTL window

Only accept the action if `verifyAction` succeeds.

## Register As A Rare Platform

### 1) Ask Rare for a DNS challenge

```ts
const challenge = await rareApiClient.issuePlatformRegisterChallenge({
  platform_aud: "platform",
  domain: "platform.example.com",
});
```

### 2) Publish the TXT record

Use:

- `challenge.txt_name`
- `challenge.txt_value`

### 3) Complete registration

```ts
await rareApiClient.completePlatformRegister({
  challenge_id: challenge.challenge_id,
  platform_id: "platform-prod",
  platform_aud: "platform",
  domain: "platform.example.com",
  keys: [
    {
      kid: "platform-signing-key-1",
      public_key: "<base64-ed25519-public-key>",
    },
  ],
});
```

After activation, agents can request full attestation for your `aud`.

## Report Negative Agent Events

You can submit signed platform event tokens to Rare:

```text
POST /v1/identity-library/events/ingest
```

Or use the kit helper:

```ts
await kit.ingestNegativeEvents({
  platformId: "platform-prod",
  kid: "platform-signing-key-1",
  privateKeyPem,
  events: [
    {
      agent_id: "<agent_id>",
      category: "spam",
      reason: "automated abuse",
    },
  ],
});
```

Allowed v1 categories include:

- `spam`
- `fraud`
- `abuse`
- `policy_violation`

## Production Defaults

- Rare API base URL: `https://api.rareid.cc`
- JWKS endpoint: `/.well-known/rare-keys.json`
- Do not append `/rare` to the base URL
- For Beta, assume GitHub-backed `L2` exists on the agent side

## Recommended Rollout Order

1. Integrate public login first.
2. Add action verification and replay protection.
3. Move stores off in-memory adapters.
4. Register the platform with Rare DNS verification.
5. Enforce full-attestation-only policy if your risk model requires it.
