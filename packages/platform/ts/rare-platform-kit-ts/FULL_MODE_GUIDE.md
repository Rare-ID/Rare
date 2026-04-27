# FULL MODE GUIDE (registered / production)

Use full-mode only when you need production governance or platform-bound full attestation.

## When To Upgrade

Stay on public-only until you need one of these:

- Rare platform registration
- raw `L0/L1/L2` governance without the public cap
- full identity attestation bound to your platform `aud`
- negative event ingest
- durable shared storage across instances

## Full-Mode Checklist

1. Keep your quickstart auth routes and session flow.
2. Replace in-memory stores with durable shared stores.
3. Register the platform with Rare.
4. Accept full identity attestation in `completeAuth`.
5. Enforce full token `payload.aud == PLATFORM_AUD`.
6. Add platform event ingest if needed.

Agent login remains URL-first in full-mode: `rare login --platform-url <url>` discovers `aud` from your auth challenge. Use `rare platform-check --platform-url <url> --full` for a full-mode smoke check, or add `--aud <platform_aud>` when you want a strict audience pin. Direct `rare issue-full-attestation --aud <platform_aud>` still requires explicit `aud` because it does not call the platform challenge endpoint.

## Platform Registration Flow

1. Ask Rare for a DNS challenge:

```ts
const challenge = await rare.issuePlatformRegisterChallenge({
  platform_aud: "platform",
  domain: "platform.example.com",
});
```

2. Publish the TXT record from `txt_name` and `txt_value`.
3. Complete registration:

```ts
await rare.completePlatformRegister({
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

## Storage Expectations

Production should use durable stores for:

- challenge nonce consumption
- replay claims
- platform sessions

Redis is the default recommendation for TypeScript.

## Event Ingest

If the platform sends negative event signals back to Rare, use:

- `kit.ingestNegativeEvents(...)`

Only surface this in the integration after login is already working.

## Demo

For an end-to-end local full-mode walkthrough, use:

- `DEMO_FULL_LOGIN.md`
