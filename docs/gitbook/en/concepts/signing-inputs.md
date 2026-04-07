# Signing Inputs

Rare uses deterministic signing input strings to ensure that signatures are context-bound and replay-resistant. Every protocol operation has a fixed-format string that the agent signs.

## Design Principles

- **Versioned prefix** — each signing string starts with a version identifier (e.g., `rare-auth-v1`), allowing future format changes
- **Context binding** — fields like `aud`, `agent_id`, and `action` prevent cross-context reuse
- **Replay protection** — every string includes a `nonce`, `issued_at`, and `expires_at`
- **Deterministic** — the exact same inputs always produce the exact same signing string

## Signing Input Formats

### Challenge Authentication

```
rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}
```

Used when an agent authenticates with a platform. The platform issues the `nonce` and `aud`.

**Example:**
```
rare-auth-v1:my-platform:abc123:1700000000:1700000300
```

### Self-Registration

```
rare-register-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}
```

Used when a self-hosted agent registers with Rare. Signed by the agent's own key.

### Action Signing

```
rare-act-v1:{aud}:{session_token}:{action}:{sha256(canonical_json(action_payload))}:{nonce}:{issued_at}:{expires_at}
```

Used for signed actions within a session. Signed by the session key.

**Canonical JSON** rules for action payload hashing:
- UTF-8 encoding
- `sort_keys=true`
- Compact separators: `(',', ':')`

### Name Update

```
rare-name-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}
```

Used when an agent changes its display name.

### Full Attestation Issue

```
rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}
```

Used when requesting a full (audience-bound) attestation for a specific platform.

**Policy:** `expires_at - issued_at <= 300` (max 5-minute validity window).

### Upgrade Request

```
rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}
```

Used when requesting an identity upgrade (L1 or L2).

**Policy:** `expires_at - issued_at <= 300`.

### Agent Proof (API authentication)

```
rare-agent-auth-v1:{agent_id}:{op}:{resource}:{nonce}:{issued_at}:{expires_at}
```

Used as an alternative to bearer tokens for authenticating API requests. The agent signs a proof that includes the operation and resource being accessed.

## Validation Rules

All verifiers MUST enforce:

| Rule | Detail |
|------|--------|
| Nonce is one-time | Track state: `issued → consumed → expired` |
| Nonce consumed on first use | Reject all subsequent attempts |
| Short TTL | Max 30-second clock skew allowed |
| Signature verification | Use the appropriate public key (agent key, session key, or Rare signer key) |
| Context fields match | `aud`, `agent_id`, `request_id`, etc. must match the expected values |

## Reference

- Specification: [RIP-0003 Challenge and Signing Inputs](../protocol/challenge-signing.md)
- Test vectors: `docs/rip/test-vectors/rip-v1-signing-inputs.json`
