# Platform Onboarding (RIP-0005)

RIP-0005 covers platform registration, audience-bound identity, upgrade flows, and platform event ingest.

## DNS-Based Platform Registration

Step 1:

```text
POST /v1/platforms/register/challenge
```

Input:

- `platform_aud`
- `domain`

Output:

- `challenge_id`
- `txt_name`
- `txt_value`
- `expires_at`

Step 2:

```text
POST /v1/platforms/register/complete
```

Input:

- `challenge_id`
- `platform_id`
- `platform_aud`
- `domain`
- `keys[]`

## Full Attestation for Registered Platforms

Full attestation issuance requires:

- a registered active platform
- the fixed signing input:
  `rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- a max signed window of 300 seconds

## Human Upgrade Flows

L1:

- `POST /v1/upgrades/requests`
- `POST /v1/upgrades/l1/email/send-link`
- `POST /v1/upgrades/l1/email/verify`

L2:

- `POST /v1/upgrades/requests`
- `POST /v1/upgrades/l2/social/start`
- `GET /v1/upgrades/l2/social/callback`
- `POST /v1/upgrades/l2/social/complete`

## Platform Event Tokens

Negative event tokens use:

- header `typ=rare.platform-event+jws`
- payload `typ=rare.platform-event`
- `aud=rare.identity-library`
- replay protection on `(iss, jti)`
- idempotent dedupe on `(iss, event_id)`

Allowed categories:

- `spam`
- `fraud`
- `abuse`
- `policy_violation`

## Hosted Signer Notes

All `/v1/signer/*` endpoints require:

```text
Authorization: Bearer <hosted_management_token>
```

Signer request TTL caps:

- normal signing requests: `300` seconds
- delegation/session signing: `3600` seconds

## References

- Canonical RIP: `docs/rip/rip-0005-platform-onboarding-and-events.md`
- Full mode guide: [Platform SDK Full Mode](../platform-sdk/full-mode.md)

