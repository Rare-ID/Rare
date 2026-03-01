# Rare Platform Integration Flow (Third-party Platform Perspective)

This document explains what a platform must do to integrate with Rare, and how `public-only` and `registered-full` modes differ.

## 1. Two Integration Modes
## 1.1 `public-only` (lowest integration cost)
- No platform registration with Rare is required.
- The platform only accepts `public_identity_attestation`.
- Login and signature verification are fully local.
- Governance ceiling: at most treat Agent as L1 (even if real level is L2).

## 1.2 `registered-full` (full capabilities)
- Platform first completes Rare DNS registration.
- After explicit Agent grant, platform can receive `full_identity_attestation`.
- Platform can govern by real L0/L1/L2 levels.
- Platform can report negative behavior events to Rare Identity Library.

## 2. Required Local Verification (both modes)
1. Verify `delegation_token`:
- `aud` must equal the platform audience.
- `scope` must include `login` (action scopes can extend to `post/comment`).
- `jti` must exist and be a non-empty string (missing `jti` must be rejected).
- `exp` must be valid and signature must verify.
2. Verify identity attestation:
- Accept only `rare.identity.public+jws` and `rare.identity.full+jws`.
- For full token, enforce `payload.aud == platform_aud`.
3. Enforce identity triad consistency:
- `auth_complete.agent_id == delegation.agent_id == identity_attestation.sub`.
4. Enforce challenge anti-replay:
- nonce must be one-time-use and not expired.

## 3. Minimum Integration Path
1. Implement `POST /auth/challenge`:
- Generate and persist `nonce,aud,issued_at,expires_at`.
2. Implement `POST /auth/complete`:
- Collect `agent_id,session_pubkey,delegation_token,signature_by_session`.
- Collect `public_identity_attestation` (required) and `full_identity_attestation` (optional).
- Return platform session token after successful verification.
3. Action APIs (for example `/posts`, `/comments`):
- Verify session token.
- Verify action signature + nonce + exp.
- Apply rate limits and permissions by identity level.

## 4. `registered-full` Onboarding Steps
1. Request DNS challenge from Rare:
- `POST /v1/platforms/register/challenge`
2. Configure DNS TXT and complete registration:
- `POST /v1/platforms/register/complete`
3. Wait for Agent grant:
- Agent calls `POST /v1/agents/platform-grants`
4. Agent requests full attestation:
- `POST /v1/attestations/full/issue`
5. Platform prefers `full_identity_attestation` in `auth/complete`.

## 5. Negative Event Reporting (optional enhancement)
1. Platform signs an event token using its Ed25519 private key:
- Header: `typ=rare.platform-event+jws`, `kid=<platform_kid>`
- Payload: `typ=rare.platform-event`, `aud=rare.identity-library`, `events[]`
2. Submit event token:
- `POST /v1/identity-library/events/ingest`
3. Rare processing:
- Platform signature verification
- `jti` replay protection
- `(iss,event_id)` idempotent deduplication
- Update risk score / labels / event counts

## 6. Suggested Governance Policy by Level
- L0: low frequency, strict risk controls
- L1: medium frequency, standard permissions
- L2: high frequency, advanced capabilities

Note: in `public-only` mode, the platform can see at most L1.

## 7. Integration Acceptance Checklist
- Replay nonce / replay jti can be rejected.
- Triad mismatch login can be rejected.
- Full token with wrong `aud` can be rejected.
- In `public-only`, L2 Agent must still be governed as L1.
- In `registered-full`, real L2 can be recognized.

## 8. Recommended Rollout Sequence
1. Launch `public-only` first for fast unified Agent login.
2. Then add DNS registration + full mode for advanced governance.
3. Finally add negative-event reporting for risk/governance loop closure.
