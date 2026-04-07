# Identity Model

## Agent ID

Every Rare agent is identified by its Ed25519 public key. This is the `agent_id` — a base64url-encoded string that serves as the agent's permanent, portable identity.

```
agent_id = base64url(Ed25519_public_key)
```

Key properties:
- **Self-sovereign** — the agent generates its own key pair; no central authority issues the identity
- **Deterministic** — the same key always produces the same `agent_id`
- **Collision-resistant** — Ed25519 keys are 256-bit; collision is computationally infeasible
- **Portable** — the `agent_id` works across all Rare-compatible platforms

## Key Modes

Rare supports two key management modes:

### Hosted Signer

Rare generates and stores the agent's private key (encrypted at rest with AES-GCM or GCP KMS). The agent interacts with the key through the `/v1/signer/*` API endpoints using a bearer management token.

- Best for: agents that cannot securely store a private key locally
- Trade-off: relies on Rare's infrastructure for signing operations
- Recovery: email and social recovery flows are available

### Self-Hosted

The agent generates and stores its own key pair. A local signer daemon (`rare-signer`) manages the private key via IPC.

- Best for: agents that need full control over their cryptographic material
- Trade-off: the agent is responsible for key security and backup
- No recovery path through Rare if the key is lost

## Agent Name

Each agent has a human-readable display name subject to these rules:
- Normalized using `trim + NFKC` Unicode normalization
- Length: 1–48 characters
- No control characters
- Reserved words are rejected
- Name changes require a signed request with replay protection

**Important:** The name is display data only. It MUST NOT be used as an authorization key. The `agent_id` (public key) is the only stable identity for authorization and audit.

## Identity Tokens

Rare signs JWS (JSON Web Signature) tokens that attest to an agent's identity. These tokens use:

- **Algorithm:** `EdDSA` with Ed25519
- **Format:** JWS Compact Serialization
- **Key discovery:** `/.well-known/rare-keys.json` (JWKS)

There are two token types:

| Token Type | Header `typ` | Has `aud`? | Max Level |
|------------|-------------|------------|-----------|
| Public attestation | `rare.identity.public+jws` | No | L1 |
| Full attestation | `rare.identity.full+jws` | Yes | L2 |

### Shared Payload Fields

Every identity token includes:

| Field | Description |
|-------|-------------|
| `typ` | `rare.identity` |
| `ver` | `1` |
| `iss` | `rare` |
| `sub` | `agent_id` (Ed25519 public key, base64url) |
| `lvl` | Trust level: `L0`, `L1`, or `L2` |
| `claims.profile.name` | Agent display name |
| `iat` | Issued-at timestamp |
| `exp` | Expiration timestamp |
| `jti` | Unique token identifier |

Optional claims: `claims.owner_id`, `claims.twitter`, `claims.github`, `claims.linkedin`.
