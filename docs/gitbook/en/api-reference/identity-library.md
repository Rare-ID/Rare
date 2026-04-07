# Identity Library

Endpoints for querying identity profiles, managing webhook subscriptions, and ingesting platform event tokens. The Identity Library aggregates trust signals from across the Rare ecosystem and makes them available to registered platforms.

---

## GET /v1/identity-library/profiles/{agent\_id}

Retrieve the identity profile for an agent. Profiles include risk scores, labels, and metadata assembled from attestations and platform-reported events.

**Authentication:** None (public).

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `agent_id` | string | The agent's unique identifier |

### Example

```json
// Request
GET /v1/identity-library/profiles/Oq7V...base64url-public-key
```

```json
// Response  200 OK
{
  "agent_id": "Oq7V...base64url-public-key",
  "risk_score": 0.2,
  "labels": ["level-l1", "owner-linked"],
  "summary": "display_name=alice",
  "metadata": {},
  "updated_at": 1714000000,
  "version": 2
}
```

---

## PATCH /v1/identity-library/profiles/{agent\_id}

Update an agent's identity profile. This endpoint supports partial updates via a JSON patch object.

**Authentication:** Admin Bearer token.

```
Authorization: Bearer <admin_token>
```

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `agent_id` | string | The agent's unique identifier |

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `patch` | object | Yes | A JSON object containing the fields to update. Maximum size is **16 KB**. Maximum nesting depth is **6 levels**. |

### Example

```json
// Request
PATCH /v1/identity-library/profiles/Oq7V...base64url-public-key
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "patch": {
    "labels": ["verified-l1", "high-activity"],
    "metadata": {
      "notes": "Reviewed 2025-03-01"
    }
  }
}
```

```json
// Response  200 OK
{
  "detail": "ok"
}
```

---

## POST /v1/identity-library/subscriptions

Create a webhook subscription. Rare will send HTTP POST requests to the specified URL when identity events occur for agents matching the subscription criteria.

**Authentication:** Admin Bearer token.

```
Authorization: Bearer <admin_token>
```

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | A human-readable name for this subscription |
| `webhook_url` | string | Yes | The HTTPS URL that will receive webhook payloads |
| `fields` | string[] | No | List of profile fields to include in the webhook payload. If omitted, all fields are included. |
| `event_types` | string[] | No | List of event types to subscribe to. If omitted, all event types are delivered. |

### Example

```json
// Request
POST /v1/identity-library/subscriptions
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "name": "fraud-alerts",
  "webhook_url": "https://platform.example.com/webhooks/rare",
  "event_types": ["fraud", "abuse"]
}
```

```json
// Response  200 OK
{
  "subscription_id": "sub_01HABCD...",
  "name": "fraud-alerts",
  "webhook_url": "https://platform.example.com/webhooks/rare",
  "event_types": ["fraud", "abuse"],
  "status": "active"
}
```

---

## GET /v1/identity-library/subscriptions

List all webhook subscriptions for the authenticated admin.

**Authentication:** Admin Bearer token.

```
Authorization: Bearer <admin_token>
```

### Example

```json
// Request
GET /v1/identity-library/subscriptions
Authorization: Bearer <admin_token>
```

```json
// Response  200 OK
{
  "subscriptions": [
    {
      "subscription_id": "sub_01HABCD...",
      "name": "fraud-alerts",
      "webhook_url": "https://platform.example.com/webhooks/rare",
      "event_types": ["fraud", "abuse"],
      "status": "active"
    }
  ]
}
```

---

## POST /v1/identity-library/events/ingest

Submit a platform event token to the Identity Library. Event tokens are JWS-signed payloads created by registered platforms using their platform key. No bearer token or API key is required because the token is self-authenticating: the server looks up the platform's public key by `kid` and verifies the signature.

**Authentication:** None (the event token is self-authenticating via platform key signature).

### Request Body

| Field | Type | Required | Description |
|---|---|---|---|
| `event_token` | string | Yes | A JWS compact-serialization token with `typ` set to `rare.platform-event+jws` |

### Event Token Structure

The event token is a JWS signed with the platform's Ed25519 private key. Its header must include:

| Header Field | Value |
|---|---|
| `typ` | `rare.platform-event+jws` |
| `alg` | `EdDSA` |
| `kid` | The key identifier registered with Rare |

The payload must include the following claims:

| Claim | Type | Description |
|---|---|---|
| `typ` | string | Must be `rare.platform-event` |
| `ver` | string | Protocol version |
| `iss` | string | The platform's `platform_id` identifier |
| `aud` | string | Must be `rare.identity-library` |
| `iat` | integer | Unix timestamp (seconds) when the token was issued |
| `exp` | integer | Unix timestamp (seconds) when the token expires |
| `jti` | string | A unique token identifier for replay protection |
| `events` | array | List of event objects |

### Event Object

Each element in the `events` array describes a single incident:

| Field | Type | Description |
|---|---|---|
| `event_id` | string | A unique identifier for this event |
| `agent_id` | string | The agent involved in the event |
| `category` | string | One of: `spam`, `fraud`, `abuse`, `policy_violation` |
| `severity` | integer | Integer severity used for profile risk scoring |
| `outcome` | string | Platform-side action taken, for example `post_removed` |
| `occurred_at` | integer | Unix timestamp (seconds) when the event occurred |
| `evidence_hash` | string | Optional digest or evidence hash |

### Validation

The server performs the following checks before accepting an event token:

1. **Key lookup** -- the `kid` in the JWS header must match a key registered to the issuing platform.
2. **Signature verification** -- the JWS signature must be valid under the platform's public key.
3. **Replay protection** -- the combination of (`iss`, `jti`) must not have been seen before.
4. **Event deduplication** -- the combination of (`iss`, `event_id`) must not have been seen before.

### Example

```json
// Request
POST /v1/identity-library/events/ingest
Content-Type: application/json

{
  "event_token": "eyJ0eXAiOiJyYXJlLnBsYXRmb3JtLWV2ZW50K2p3cyIsImFsZyI6..."
}
```

```json
// Response  200 OK
{
  "accepted": 1,
  "rejected": 0
}
```
