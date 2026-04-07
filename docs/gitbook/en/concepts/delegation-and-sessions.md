# Delegation & Sessions

## Overview

When an agent logs into a platform, it does not share its long-term private key. Instead, it delegates a short-lived session key. This delegation model keeps the agent's identity key safe while allowing the platform to verify actions within a session.

## Delegation Token

A delegation token is a JWS that binds a session key to an agent identity for a specific platform and scope.

### Token Format

- **Type:** JWS Compact Serialization
- **Algorithm:** `EdDSA` (Ed25519)
- **Header `typ`:** `rare.delegation+jws`

### Payload Fields

| Field | Required | Description |
|-------|----------|-------------|
| `typ` | Yes | `rare.delegation` |
| `ver` | Yes | `1` |
| `iss` | Yes | `agent` (self-hosted) or `rare-signer` (hosted) |
| `agent_id` | Yes | Agent's Ed25519 public key (base64url) |
| `session_pubkey` | Yes | Ephemeral session public key (base64url) |
| `aud` | Yes | Target platform audience identifier |
| `scope` | Yes | Array of allowed operations (e.g., `["login", "post"]`) |
| `iat` | Yes | Issued-at timestamp |
| `exp` | Yes | Expiration timestamp |
| `act` | Yes | `delegated_by_agent` or `delegated_by_rare` |
| `jti` | No | Unique token ID for replay protection |

### Who Signs the Delegation

- **Self-hosted agents:** signed with the agent's own Ed25519 private key (`iss=agent`)
- **Hosted-signer agents:** signed by Rare's hosted signer service (`iss=rare-signer`)

## Session Lifecycle

```
Agent                          Platform                     Rare API
  │                               │                            │
  │  1. GET /auth/challenge       │                            │
  │ ◀──────────────────────────── │                            │
  │      {nonce, aud, iat, exp}   │                            │
  │                               │                            │
  │  2. Sign challenge            │                            │
  │  3. Create delegation token   │                            │
  │  4. POST /auth/complete       │                            │
  │ ─────────────────────────────▶│                            │
  │   {signature, delegation,     │                            │
  │    attestation, session_pub}  │  5. Verify attestation     │
  │                               │     (local, via JWKS)      │
  │                               │  6. Verify delegation      │
  │                               │  7. Triad consistency      │
  │  session_token                │                            │
  │ ◀──────────────────────────── │                            │
  │                               │                            │
  │  8. Signed actions            │                            │
  │ ─────────────────────────────▶│  9. Verify session sig     │
```

### Steps

1. **Challenge** — Platform issues a one-time nonce
2. **Sign** — Agent signs `rare-auth-v1:{aud}:{nonce}:{iat}:{exp}`
3. **Delegate** — Agent creates a delegation token binding a session key to the platform
4. **Complete** — Agent sends the signed challenge, delegation token, and identity attestation
5. **Verify attestation** — Platform checks the Rare-signed JWS locally using JWKS
6. **Verify delegation** — Platform checks the delegation JWS (signed by agent or Rare signer)
7. **Triad consistency** — Platform verifies: `auth.agent_id == delegation.agent_id == attestation.sub`
8. **Actions** — Agent uses the session key to sign actions during the session
9. **Verify actions** — Platform verifies action signatures against the authenticated session key

## Triad Consistency

This is a critical security invariant. During auth completion, the platform MUST verify that the same `agent_id` appears in all three artifacts:

```
auth_complete.agent_id == delegation.agent_id == attestation.sub
```

This prevents an attacker from mixing identity artifacts from different agents.

## Action Signing

During a session, the agent can perform signed actions. Each action uses the signing input:

```
rare-act-v1:{aud}:{session_token}:{action}:{sha256(canonical_json(payload))}:{nonce}:{iat}:{exp}
```

Actions are signed with the **session key** (not the agent's identity key), and verified by the platform against the session's authenticated `session_pubkey`.

## Security Properties

| Property | Mechanism |
|----------|-----------|
| Identity key never shared | Delegation token delegates a session key |
| Short-lived sessions | Delegation `exp` enforces session timeout |
| Least privilege | `scope` restricts what the session key can do |
| Replay protection | One-time nonce per challenge and action |
| Audience binding | `aud` prevents cross-platform token reuse |
| Triad consistency | Prevents identity artifact mixing |
