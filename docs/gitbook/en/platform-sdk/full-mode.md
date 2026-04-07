# Platform SDK Full Mode

Full mode is the production track for platforms that need platform-bound identity and governance.

## When You Need It

Stay on quick start until you need one of these:

- raw `L2` visibility instead of public-token `L1` capping
- Rare platform registration
- full attestations bound to your `PLATFORM_AUD`
- durable challenge, replay, and session stores
- negative event ingest into the identity library

## What Changes

Quick start and full mode share the same login shape. Full mode adds platform-level state and stronger governance semantics.

| Area | Quick Start | Full Mode |
|---|---|---|
| Identity token used at login | Public attestation is enough | Full attestation preferred |
| Effective governance level | Public tokens cap at `L1` | Real `L0` / `L1` / `L2` |
| Platform registration | Not required | Required |
| Storage | In-memory is acceptable for local work | Durable shared stores required |
| Negative event ingest | Optional and uncommon | Expected for governance-heavy platforms |

## Full-Mode Checklist

1. Replace in-memory stores with durable shared stores.
2. Register the platform with Rare using DNS proof.
3. Accept and validate `full_identity_attestation`.
4. Enforce exact `aud == PLATFORM_AUD` on full tokens.
5. Keep replay protection for both challenge and delegation flows.
6. Add event ingest only after login is stable.

## Platform Registration

Use the Rare API client to register your platform:

1. Request a challenge:

```json
POST /v1/platforms/register/challenge
{
  "platform_aud": "platform.example.com",
  "domain": "example.com"
}
```

2. Publish the returned DNS TXT record.
3. Complete registration with your platform public keys.

The current DNS record name is:

```text
_rare-challenge.<domain>
```

## Storage Expectations

Production deployments should use shared storage for:

- challenge nonce consumption
- delegation replay claims
- signed action replay claims
- session storage

For TypeScript, Redis-backed stores are the default recommendation. For Python, Redis stores are included in the SDK.

## Event Ingest

Registered platforms can send negative governance signals back to Rare:

- `spam`
- `fraud`
- `abuse`
- `policy_violation`

The SDK can sign a `rare.platform-event+jws` token and submit it to:

```text
POST /v1/identity-library/events/ingest
```

## Next Steps

- [TypeScript API Reference](typescript/api-reference.md)
- [Python API Reference](python/api-reference.md)
- [Protocol: Platform Onboarding](../protocol/platform-onboarding.md)

