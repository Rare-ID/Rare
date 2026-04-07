# Platform SDK Quick Start

Use this path when you want Rare login working on a platform with the fewest moving parts.

Quick start still preserves the core protocol guarantees:

- one-time challenge nonce consumption
- local verification of identity attestations
- delegation verification
- triad consistency:
  `auth_complete.agent_id == delegation.agent_id == attestation.sub`

## What You Build

Your platform needs three things:

1. A challenge endpoint: `POST /auth/challenge`
2. A completion endpoint: `POST /auth/complete`
3. Session lookup for later requests

In public-only mode, this is enough to authenticate Rare agents and gate features up to effective level `L1`.

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

Defaults:

- `RARE_BASE_URL` defaults to `https://api.rareid.cc`
- the SDK can discover the Rare signer delegation key from `/.well-known/rare-keys.json`
- `PLATFORM_ID` is derived from `PLATFORM_AUD` when omitted

## Choose Your SDK

- [TypeScript Getting Started](typescript/getting-started.md)
- [Python Getting Started](python/getting-started.md)

## Public-Only vs Full-Mode

Start with public-only if you want:

- fast integration
- local verification
- no platform registration on day one
- no need for raw `L2` visibility

Move to [Full Mode](full-mode.md) when you need:

- Rare platform registration
- audience-bound full attestations
- raw `L2` governance
- negative event ingest
- durable multi-instance storage

## Local Validation

Once your auth routes exist, validate end to end:

```bash
rare register --name alice --rare-url https://api.rareid.cc
rare login \
  --aud platform.example.com \
  --platform-url http://127.0.0.1:3000/rare \
  --public-only
```

If login succeeds, your platform has already verified:

- the signed challenge
- the delegation token
- the identity attestation
- session key binding

