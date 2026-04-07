# Attestations

Endpoints for refreshing and issuing attestation tokens. Attestations are signed JWS tokens that prove an agent's identity and trust level.

---

## POST /v1/attestations/refresh

Refresh an existing attestation token for an agent. Returns a new token with an updated expiry while preserving the agent's current trust level.

**Authentication:** None (public).

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | The agent's unique identifier |

### Example

```json
// Request
POST /v1/attestations/refresh
Content-Type: application/json

{
  "agent_id": "Oq7V...base64url-public-key"
}
```

```json
// Response  200 OK
{
  "agent_id": "Oq7V...base64url-public-key",
  "profile": {
    "name": "my-agent"
  },
  "public_identity_attestation": "eyJhbGciOiJFZERTQSIs..."
}
```

---

## POST /v1/attestations/public/issue

Issue a public attestation for an agent. Public attestations are not bound to a specific audience and are capped at trust level L1. They use the JWS type `rare.identity.public+jws` and do not include an `aud` claim.

**Authentication:** None (public).

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | The agent's unique identifier |

### Response

Returns a JWS token with the following characteristics:

- **typ:** `rare.identity.public+jws`
- **aud:** not included
- **Trust level:** capped at L1 regardless of the agent's actual level

### Example

```json
// Request
POST /v1/attestations/public/issue
Content-Type: application/json

{
  "agent_id": "Oq7V...base64url-public-key"
}
```

```json
// Response  200 OK
{
  "agent_id": "Oq7V...base64url-public-key",
  "profile": {
    "name": "my-agent"
  },
  "public_identity_attestation": "eyJ0eXAiOiJyYXJlLmlkZW50aXR5LnB1YmxpYyIsImFsZyI6..."
}
```

---

## POST /v1/attestations/full/issue

Issue a full (audience-bound) attestation for an agent. Full attestations are bound to a specific platform audience and reflect the agent's real trust level, including L2. The request must be signed by the agent.

**Authentication:** None (the request itself is signed by the agent).

### Preconditions

- The target platform identified by `platform_aud` must be registered and active.

### Request Body

`IssueFullAttestationRequest`

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | The agent's unique identifier |
| `platform_aud` | string | Yes | The target platform's audience identifier |
| `nonce` | string | Yes | A unique, single-use nonce |
| `issued_at` | integer | Yes | Unix timestamp (seconds) when this request was created |
| `expires_at` | integer | Yes | Unix timestamp (seconds) when this request expires. The window between `issued_at` and `expires_at` must be at most **5 minutes**. |
| `signature_by_agent` | string | Yes | Signature over the canonical payload (see below) |

### Signature Payload

The `signature_by_agent` field must sign the following canonical string:

```
rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}
```

### Response

Returns a JWS token with the following characteristics:

- **typ:** `rare.identity.full+jws`
- **aud:** set to the value of `platform_aud`
- **Trust level:** the agent's real level, including L2 if applicable

### Example

```json
// Request
POST /v1/attestations/full/issue
Content-Type: application/json

{
  "agent_id": "Oq7V...base64url-public-key",
  "platform_aud": "platform.example.com",
  "nonce": "b7d2e4f9a1c3",
  "issued_at": 1714000000,
  "expires_at": 1714000300,
  "signature_by_agent": "MEUCIQD..."
}
```

```json
// Response  200 OK
{
  "agent_id": "Oq7V...base64url-public-key",
  "platform_aud": "platform.example.com",
  "full_identity_attestation": "eyJ0eXAiOiJyYXJlLmlkZW50aXR5LmZ1bGwiLCJhbGciOi..."
}
```
