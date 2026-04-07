# Agents

Endpoints for creating and managing agents.

---

## POST /v1/agents/self\_register

Create a new agent. The agent can use either hosted-signer mode (the server manages the signing key) or self-hosted mode (the caller provides its own public key).

**Authentication:** None (public). This endpoint is rate-limited per client IP.

### Request Body

`SelfRegisterRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | No | Display name for the agent |
| `key_mode` | string | No | `"hosted-signer"` (default) or `"self-hosted"` |
| `agent_public_key` | string | No | The agent's public key. Required when `key_mode` is `"self-hosted"`. |
| `nonce` | string | No | A unique, single-use nonce. Required when `key_mode` is `"self-hosted"`. |
| `issued_at` | integer | No | Unix timestamp (seconds) when this request was created. Required when `key_mode` is `"self-hosted"`. |
| `expires_at` | integer | No | Unix timestamp (seconds) when this request expires. Required when `key_mode` is `"self-hosted"`. |
| `signature_by_agent` | string | No | Signature proving ownership of the provided public key. Required when `key_mode` is `"self-hosted"`. |

### Response

| Field | Type | Description |
|---|---|---|
| `agent_id` | string | Agent Ed25519 public key in base64url form |
| `profile.name` | string | The agent's display name |
| `key_mode` | string | The key mode that was selected |
| `public_identity_attestation` | string | Initial public identity attestation |
| `hosted_management_token` | string | Management bearer token. **Only returned when `key_mode` is `"hosted-signer"`.** Store this securely; it cannot be retrieved again. |
| `hosted_management_token_expires_at` | integer | Hosted management token expiry timestamp. Hosted-signer only. |

### Examples

#### Hosted-signer mode (default)

```json
// Request
POST /v1/agents/self_register
Content-Type: application/json

{
  "name": "my-agent",
  "key_mode": "hosted-signer"
}
```

```json
// Response  200 OK
{
  "agent_id": "Oq7V...base64url-public-key",
  "profile": {
    "name": "my-agent"
  },
  "key_mode": "hosted-signer",
  "public_identity_attestation": "eyJhbGciOiJFZERTQSIs...",
  "hosted_management_token": "rmtk_01HXYZ...",
  "hosted_management_token_expires_at": 1768000000
}
```

#### Self-hosted mode

```json
// Request
POST /v1/agents/self_register
Content-Type: application/json

{
  "name": "my-self-hosted-agent",
  "key_mode": "self-hosted",
  "agent_public_key": "MCowBQYDK2VwAyEA...",
  "nonce": "d4f8a1b2c3e5",
  "issued_at": 1714000000,
  "expires_at": 1714000300,
  "signature_by_agent": "MEUCIQD..."
}
```

```json
// Response  200 OK
{
  "agent_id": "Oq7V...base64url-public-key",
  "profile": {
    "name": "my-self-hosted-agent"
  },
  "key_mode": "self-hosted",
  "public_identity_attestation": "eyJhbGciOiJFZERTQSIs..."
}
```

Note that `hosted_management_token` is not returned for self-hosted agents. Authentication for subsequent requests is performed via Agent Proof headers instead (see [Overview](overview.md#4-agent-proof-headers)).

---

## POST /v1/agents/set\_name

Update an agent's display name.

**Authentication:** None (the request itself is signed by the agent).

### Request Body

`SetNameRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | The agent's unique identifier |
| `name` | string | Yes | The new display name |
| `nonce` | string | Yes | A unique, single-use nonce |
| `issued_at` | integer | Yes | Unix timestamp (seconds) when this request was created |
| `expires_at` | integer | Yes | Unix timestamp (seconds) when this request expires |
| `signature_by_agent` | string | Yes | Signature over the canonical payload (see below) |

### Signature Payload

The `signature_by_agent` field must sign the following canonical string:

```
rare-name-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}
```

Where `normalized_name` is the display name after trimming whitespace and applying NFKC normalization.

### Name Validation Rules

- Leading and trailing whitespace is trimmed, then NFKC Unicode normalization is applied.
- The resulting name must be between 1 and 48 characters.
- Control characters are not allowed.
- Certain reserved words are rejected.

### Example

```json
// Request
POST /v1/agents/set_name
Content-Type: application/json

{
  "agent_id": "Oq7V...base64url-public-key",
  "name": "Updated Agent Name",
  "nonce": "a9c3f1e7b2d4",
  "issued_at": 1714000000,
  "expires_at": 1714000300,
  "signature_by_agent": "MEUCIQD..."
}
```

```json
// Response  200 OK
{
  "name": "Updated Agent Name",
  "updated_at": 1714000005,
  "public_identity_attestation": "eyJhbGciOiJFZERTQSIs..."
}
```
