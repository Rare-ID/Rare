# API Reference Overview

This page describes the conventions shared by all Rare API endpoints: base URLs, authentication, request format, error handling, rate limiting, and key discovery.

---

## Base URLs

| Environment | Base URL |
|---|---|
| Production | `https://api.rareid.cc` |
| Local development | `http://127.0.0.1:8000` |

All endpoint paths documented in this reference are relative to the base URL. For example, `POST /v1/agents/self_register` in production resolves to `https://api.rareid.cc/v1/agents/self_register`.

---

## Authentication

Different endpoints require different levels of authentication. Every endpoint falls into one of four categories.

### 1. No authentication (public)

Some endpoints are fully public and require no credentials. These include agent self-registration, attestation refresh, and public attestation issuance. Public write endpoints are rate-limited per client IP (see [Rate Limiting](#rate-limiting) below).

### 2. Bearer token (hosted signer)

Endpoints that manage a hosted-signer agent require the management token returned at registration:

```
Authorization: Bearer <hosted_management_token>
```

The token is issued during `self_register` when `key_mode` is `"hosted-signer"` and must be stored securely by the caller.

### 3. Admin Bearer token

Administrative endpoints -- such as identity-library write operations -- require an admin-level bearer token:

```
Authorization: Bearer <admin_token>
```

Admin tokens are provisioned out-of-band and are not available through the public API.

### 4. Agent Proof headers

As an alternative to bearer tokens, callers can authenticate by attaching a cryptographic proof via request headers. This is the primary authentication method for self-hosted agents and is accepted anywhere a bearer token would be.

| Header | Description |
|---|---|
| `X-Rare-Agent-Id` | The agent's unique identifier |
| `X-Rare-Agent-Nonce` | A unique, single-use nonce |
| `X-Rare-Agent-Issued-At` | Unix timestamp (seconds) when the proof was created |
| `X-Rare-Agent-Expires-At` | Unix timestamp (seconds) when the proof expires |
| `X-Rare-Agent-Signature` | Signature over the proof payload, produced by the agent's private key |

The server validates that the nonce has not been seen before, that the timestamps form a reasonable window, and that the signature matches the agent's registered public key.

The current proof payload format is:

```text
rare-agent-auth-v1:{agent_id}:{op}:{resource}:{nonce}:{issued_at}:{expires_at}
```

---

## Request Format

All request bodies must be JSON (`Content-Type: application/json`). The maximum accepted body size is **256 KB**.

---

## Error Format

Errors are returned as JSON with a single `detail` field:

```json
{
  "detail": "error message"
}
```

The API uses standard HTTP status codes:

| Status | Meaning |
|---|---|
| `400` | Bad request -- malformed input or failed validation |
| `401` | Unauthorized -- missing or invalid credentials |
| `403` | Forbidden -- valid credentials but insufficient permissions |
| `404` | Not found |
| `409` | Conflict -- resource already exists or state conflict |
| `413` | Payload too large |
| `422` | Unprocessable entity -- well-formed JSON but semantically invalid |
| `429` | Too many requests -- rate limit exceeded |
| `500` | Internal server error |

---

## Rate Limiting

Public write endpoints (`self_register`, recovery, and similar) are rate-limited per client IP. When the limit is exceeded the server responds with `429 Too Many Requests`. Clients should implement exponential back-off before retrying.

---

## Key Discovery

The server exposes a JWKS document for local verification of attestation tokens:

```
GET /.well-known/rare-keys.json
```

This endpoint returns a standard JWKS (JSON Web Key Set) containing the public keys the server uses to sign identity attestations and Rare-signed delegations. Platform integrators can fetch and cache these keys to verify JWS tokens locally without calling back to the Rare API on every request.
