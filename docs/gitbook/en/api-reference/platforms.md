# Platforms

Endpoints for registering a platform with Rare. Platform registration uses a DNS-based challenge to verify domain ownership, similar to how certificate authorities validate domain control.

---

## POST /v1/platforms/register/challenge

Request a registration challenge for a new platform. The response includes a DNS TXT record that must be created under the platform's domain to prove ownership.

**Authentication:** None.

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `platform_aud` | string | Yes | The audience identifier the platform will use (typically the domain name) |
| `domain` | string | Yes | The domain to verify ownership of |

### Response

| Field | Type | Description |
|---|---|---|
| `challenge_id` | string | Unique identifier for this challenge |
| `txt_name` | string | The DNS TXT record name to create (e.g., `_rare-challenge.example.com`) |
| `txt_value` | string | The value to set in the DNS TXT record |
| `expires_at` | integer | Unix timestamp (seconds) when this challenge expires |

### DNS Verification

After receiving the challenge, the platform operator must create a DNS TXT record:

```
Name:  <txt_name>
Value: <txt_value>
```

The record must be resolvable before calling the completion endpoint. DNS propagation may take several minutes depending on the provider.

### Example

```json
// Request
POST /v1/platforms/register/challenge
Content-Type: application/json

{
  "platform_aud": "platform.example.com",
  "domain": "example.com"
}
```

```json
// Response  200 OK
{
  "challenge_id": "ch_01HABCD...",
  "txt_name": "_rare-challenge.example.com",
  "txt_value": "rare-platform-register-v1:platform.example.com:ch_01HABCD...",
  "expires_at": 1714003600
}
```

---

## POST /v1/platforms/register/complete

Complete platform registration after the DNS challenge has been set up. The server verifies the TXT record, validates the challenge, and registers the platform along with its public keys.

**Authentication:** None.

### Preconditions

- The DNS TXT record specified in the challenge response must be resolvable.
- The challenge must not have expired.
- Each challenge can only be used once.

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `challenge_id` | string | Yes | The challenge identifier returned by the challenge endpoint |
| `platform_id` | string | Yes | A unique identifier for the platform |
| `platform_aud` | string | Yes | The audience identifier (must match the value used in the challenge request) |
| `domain` | string | Yes | The domain (must match the value used in the challenge request) |
| `keys` | array | Yes | Array of public key objects to register |

Each element in the `keys` array has the following structure:

| Field | Type | Description |
|---|---|---|
| `kid` | string | A unique key identifier |
| `public_key` | string | The Ed25519 public key in base64url encoding |

### Validation

The server performs the following checks:

1. **DNS verification** -- the TXT record at `txt_name` must contain the expected `txt_value`.
2. **Challenge expiry** -- the challenge must not have expired.
3. **Single use** -- the challenge can only be consumed once.
4. **Key uniqueness** -- all `kid` values in the `keys` array must be unique.

### Response

| Field | Type | Description |
|---|---|---|
| `platform_id` | string | The registered platform identifier |
| `platform_aud` | string | The platform's audience identifier |
| `domain` | string | The verified domain |
| `status` | string | Registration status; `"active"` on success |

### Example

```json
// Request
POST /v1/platforms/register/complete
Content-Type: application/json

{
  "challenge_id": "ch_01HABCD...",
  "platform_id": "plat_01HEFGH...",
  "platform_aud": "platform.example.com",
  "domain": "example.com",
  "keys": [
    {
      "kid": "platform-key-2025-01",
      "public_key": "MCowBQYDK2VwAyEA..."
    }
  ]
}
```

```json
// Response  200 OK
{
  "platform_id": "plat_01HEFGH...",
  "platform_aud": "platform.example.com",
  "domain": "example.com",
  "status": "active"
}
```
