# FULL MODE GUIDE (registered-full)

Use this mode when your platform needs real L0/L1/L2 governance.

## Flow

1. Platform requests DNS challenge
- `POST /v1/platforms/register/challenge`
2. Platform sets DNS TXT and completes register
- `POST /v1/platforms/register/complete`
3. Agent issues full attestation
- `POST /v1/attestations/full/issue`
4. Platform calls `completeAuth` with both tokens
- SDK prefers full token and falls back to public if full is unavailable.

## Governance behavior

- `identity_mode=full`: use raw `L0/L1/L2`.
- `identity_mode=public`: SDK returns `effective_level` capped at `L1`.

## Security checks

- Full token must satisfy `payload.aud == platform_aud`.
- Triad and replay checks are still mandatory.
