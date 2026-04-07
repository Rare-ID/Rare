# Upgrades

Endpoints for moving agent identity from `L0` to `L1` and from `L1` to `L2`.

## POST /v1/upgrades/requests

Create an upgrade request. The request is self-authenticating because the agent signs:

```text
rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}
```

Request body:

| Field | Type | Required | Description |
|---|---|---|---|
| `agent_id` | string | Yes | Agent Ed25519 public key |
| `target_level` | string | Yes | `L1` or `L2` |
| `request_id` | string | Yes | Unique request identifier |
| `nonce` | string | Yes | Single-use nonce |
| `issued_at` | integer | Yes | Request creation time |
| `expires_at` | integer | Yes | Must be within 300 seconds of `issued_at` |
| `signature_by_agent` | string | Yes | Detached signature over the fixed payload |
| `contact_email` | string | No | Required for `L1` |
| `send_email` | boolean | No | Defaults to `true` for `L1` |

### Status Lifecycle

```text
human_pending -> verified -> upgraded
       |             |
       v             v
    expired       revoked
```

In the current implementation, newly created requests enter `human_pending`.

### Example Response

```json
{
  "upgrade_request_id": "upreq_01HABCD...",
  "agent_id": "Oq7V...base64url-public-key",
  "target_level": "L1",
  "status": "human_pending",
  "next_step": "verify_email",
  "expires_at": 1714086400,
  "contact_email_masked": "a***e@example.com",
  "email_delivery": {
    "state": "queued",
    "provider": "NoopEmailProvider",
    "attempt_count": 1,
    "last_attempt_at": 1714000000,
    "last_error_code": null,
    "last_error_detail": null
  }
}
```

## GET /v1/upgrades/requests/{upgrade_request_id}

Returns the current request state.

Authentication:

- hosted management bearer token
- agent proof headers

Typical fields:

- `upgrade_request_id`
- `agent_id`
- `target_level`
- `status`
- `next_step`
- `expires_at`
- `failure_reason`
- `contact_email_masked`
- `social_provider`

## POST /v1/upgrades/l1/email/send-link

Send or resend the L1 verification email.

Request body:

```json
{
  "upgrade_request_id": "upreq_01HABCD..."
}
```

Response fields include:

- `upgrade_request_id`
- `sent`
- `expires_at`
- `verify_endpoint`
- `delivery`

## POST /v1/upgrades/l1/email/verify

Complete L1 verification using the email token.

Request body:

```json
{
  "token": "vt_01HEFGH..."
}
```

Successful response includes the upgraded level and a refreshed public attestation.

## POST /v1/upgrades/l2/social/start

Start OAuth authorization for `x`, `github`, or `linkedin`.

Request body:

```json
{
  "upgrade_request_id": "upreq_01HABCD...",
  "provider": "github"
}
```

Response:

```json
{
  "upgrade_request_id": "upreq_01HABCD...",
  "provider": "github",
  "state": "oauth-state-123",
  "expires_at": 1714000600,
  "authorize_url": "https://github.com/login/oauth/authorize?client_id=...&state=..."
}
```

## GET /v1/upgrades/l2/social/callback

OAuth callback endpoint used by the provider redirect. Integrators do not call this directly.

## POST /v1/upgrades/l2/social/complete

Local-development shortcut for completing L2 with a provider snapshot. This endpoint is only useful when local shortcut mode is enabled on the Rare service.

Request body:

| Field | Type | Required |
|---|---|---|
| `upgrade_request_id` | string | Yes |
| `provider` | string | Yes |
| `provider_user_snapshot` | object | Yes |

