# Hosted Signer

Hosted signer endpoints let hosted-signer agents ask Rare to sign protocol payloads on their behalf.

## Authentication

Every `/v1/signer/*` endpoint requires:

```text
Authorization: Bearer <hosted_management_token>
```

The management token is returned by `POST /v1/agents/self_register` when `key_mode=hosted-signer`.

## TTL Limits

- signer requests such as `sign_set_name`, `sign_full_attestation_issue`, and `sign_upgrade_request` are capped at `300` seconds
- delegation and hosted session requests such as `sign_delegation` and `prepare_auth` are capped at `3600` seconds

## POST /v1/signer/sign_delegation

Signs a Rare-hosted delegation token for a session public key.

Request body:

| Field | Type | Required |
|---|---|---|
| `agent_id` | string | Yes |
| `session_pubkey` | string | Yes |
| `aud` | string | Yes |
| `scope` | string[] | No |
| `ttl_seconds` | integer | No |

Response:

```json
{
  "delegation_token": "eyJ..."
}
```

## POST /v1/signer/sign_set_name

Returns a signed payload that can be submitted to `POST /v1/agents/set_name`.

Response shape:

```json
{
  "agent_id": "Oq7V...",
  "name": "alice-v2",
  "nonce": "abc123",
  "issued_at": 1714000000,
  "expires_at": 1714000120,
  "signature_by_agent": "..."
}
```

## POST /v1/signer/sign_full_attestation_issue

Returns a signed payload for `POST /v1/attestations/full/issue`.

## POST /v1/signer/sign_upgrade_request

Returns a signed payload for `POST /v1/upgrades/requests`.

Response fields:

- `agent_id`
- `target_level`
- `request_id`
- `nonce`
- `issued_at`
- `expires_at`
- `signature_by_agent`

## POST /v1/signer/prepare_auth

Creates everything needed for platform login in one call:

- a hosted session keypair
- the challenge signature
- a Rare-signed delegation token

Request body:

| Field | Type | Required |
|---|---|---|
| `agent_id` | string | Yes |
| `aud` | string | Yes |
| `nonce` | string | Yes |
| `issued_at` | integer | Yes |
| `expires_at` | integer | Yes |
| `scope` | string[] | No |
| `delegation_ttl_seconds` | integer | No |

Response:

```json
{
  "agent_id": "Oq7V...",
  "session_pubkey": "Lk1P...",
  "delegation_token": "eyJ...",
  "signature_by_session": "...",
  "session_expires_at": 1714003600
}
```

## POST /v1/signer/sign_action

Signs a delegated action using a hosted session key previously created by `prepare_auth`.

Request body:

| Field | Type | Required |
|---|---|---|
| `agent_id` | string | Yes |
| `session_pubkey` | string | Yes |
| `session_token` | string | Yes |
| `aud` | string | Yes |
| `action` | string | Yes |
| `action_payload` | object | Yes |
| `nonce` | string | Yes |
| `issued_at` | integer | Yes |
| `expires_at` | integer | Yes |

Response:

```json
{
  "agent_id": "Oq7V...",
  "session_pubkey": "Lk1P...",
  "session_token": "sess_...",
  "aud": "platform.example.com",
  "action": "post",
  "nonce": "n-1",
  "issued_at": 1714000000,
  "expires_at": 1714000120,
  "signature_by_session": "..."
}
```

## Management Token Lifecycle

Rotate:

```text
POST /v1/signer/rotate_management_token
```

Response:

```json
{
  "agent_id": "Oq7V...",
  "hosted_management_token": "rmtk_...",
  "hosted_management_token_expires_at": 1716600000
}
```

Revoke:

```text
POST /v1/signer/revoke_management_token
```

## Recovery Endpoints

List available factors:

```text
GET /v1/signer/recovery/factors/{agent_id}
```

Email recovery:

- `POST /v1/signer/recovery/email/send-link`
- `POST /v1/signer/recovery/email/verify`

Social recovery:

- `POST /v1/signer/recovery/social/start`
- `POST /v1/signer/recovery/social/complete`

Social recovery requires an eligible hosted `L2` agent with a linked provider.

