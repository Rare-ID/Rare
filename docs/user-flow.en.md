# Rare User Flow (Agent Perspective)

This document describes the currently active Rare v1 flow, from registration to platform login, then L1/L2 upgrades and full identity authorization.

## 1. Roles and Credentials
- `agent_id`: Long-term Agent identity (Ed25519 public key, base64url).
- `agent private key`: Used only for signing and must never be exposed to platforms.
- `public_identity_attestation`: Basic identity token issued by Rare, capped at L1 visibility.
- `full_identity_attestation`: Platform-bound full identity token issued by Rare, includes `aud` and may include real L2.
- `delegation_token`: Short-lived token authorizing a session public key for platform use.

## 2. Registration (L0)
### 2.1 Hosted Key Mode (`hosted-signer`)
1. Agent calls `POST /v1/agents/self_register` with optional `name`.
2. Rare creates `agent_id` and hosts the private key.
3. Response includes:
- `agent_id`
- `profile.name`
- `public_identity_attestation`
- `key_mode=hosted-signer`
- `hosted_management_token` (returned once; required by `/v1/signer/*`)
- `hosted_management_token_expires_at` (unix seconds; token expiry)

### 2.2 Self-hosted Key Mode (`self-hosted`)
1. Agent generates an Ed25519 keypair locally.
2. Agent signs the registration string: `rare-register-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}`.
3. Agent calls `POST /v1/agents/self_register` with public key and signature.
4. Rare verifies the signature and registers successfully (private key is never returned).

## 3. Optional Upgrade (Agent Requests Human Verification)
## 3.1 Upgrade to L1 (Email Magic Link)
1. Agent submits an upgrade request:
- Signing string: `rare-upgrade-v1:{agent_id}:L1:{request_id}:{nonce}:{issued_at}:{expires_at}`
- API: `POST /v1/upgrades/requests`
- Required: `contact_email`
2. Rare creates `upgrade_request_id` and sets status to `human_pending`.
3. Rare sends a magic link (local stub):
- `POST /v1/upgrades/l1/email/send-link`
- Requires management auth (hosted bearer or self-hosted signed proof headers)
- Raw `token`/`magic_link` are returned only when `RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS=1`.
4. Human clicks the link:
- `GET /v1/upgrades/l1/email/verify?token=...`
5. Rare auto-upgrades to L1 and updates:
- `owner_id=email:<sha256(lower(email))>`
- `level=L1`
- Issues a new `public_identity_attestation`

## 3.2 Upgrade to L2 (Either X or GitHub)
Prerequisite: Agent is already L1.

Path A (OAuth callback):
1. Agent creates an upgrade request (`target_level=L2`, signed with `rare-upgrade-v1`).
2. `POST /v1/upgrades/l2/social/start` to get `authorize_url,state`.
- Requires management auth (hosted bearer or self-hosted signed proof headers)
3. Social callback: `GET /v1/upgrades/l2/social/callback?provider=x|github&code=...&state=...`.
4. Rare auto-upgrades to L2 and writes social claims.

Path B (Local integration shortcut):
1. `POST /v1/upgrades/l2/social/complete` with `provider_user_snapshot`.
- Requires management auth (hosted bearer or self-hosted signed proof headers)
- Disabled by default; enable only for local dev with `RARE_ALLOW_LOCAL_UPGRADE_SHORTCUTS=1`.
2. Rare validates and auto-upgrades to L2.

## 4. Full Identity Authorization for Platforms (grant + full)
By default, only `public_identity_attestation` is used.  
To allow a platform to receive full identity (including real L2), Agent must grant explicit permission.

1. Agent grants a platform:
- Signing string: `rare-grant-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- API: `POST /v1/agents/platform-grants`
2. Agent requests full attestation:
- Signing string: `rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}`
- API: `POST /v1/attestations/full/issue`
3. Rare checks prerequisites:
- Platform is registered (DNS proof complete)
- Grant is active (not revoked)
4. Rare returns `full_identity_attestation` (audience-bound).

## 5. Login to a Third-party Platform
1. Platform issues challenge: `POST /auth/challenge`.
2. Agent prepares session proof:
- Challenge signing string: `rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}`
- Generates session keypair and signs challenge.
- Creates delegation (`aud/scope/exp`).
3. Agent calls platform `POST /auth/complete` with:
- `agent_id`
- `session_pubkey`
- `delegation_token`
- `signature_by_session`
- `public_identity_attestation`
- Optional `full_identity_attestation`
4. Platform verifier validates locally, then login succeeds.

## 6. Post-login Action Signing
1. Agent signs each action:
- `rare-act-v1:{aud}:{session_token}:{action}:{sha256(payload)}:{nonce}:{issued_at}:{expires_at}`
2. Platform verifies signature using session public key and enforces nonce replay protection.

## 7. Common Query and Management APIs
- List granted platforms: `GET /v1/agents/platform-grants/{agent_id}` (`Authorization: Bearer <admin_or_bound_hosted_token>`)
- Revoke platform grant: `DELETE /v1/agents/platform-grants/{platform_aud}`
- Refresh public attestation: `POST /v1/attestations/public/issue`
- Check upgrade status: `GET /v1/upgrades/requests/{upgrade_request_id}` (`Authorization: Bearer <admin_or_bound_hosted_token>`)
- Self-hosted signed proof headers are accepted for the two read APIs above:
- `X-Rare-Agent-Id`
- `X-Rare-Agent-Nonce`
- `X-Rare-Agent-Issued-At`
- `X-Rare-Agent-Expires-At`
- `X-Rare-Agent-Signature`

### Hosted signer API auth (new)
- Every `/v1/signer/*` call must include `Authorization: Bearer <hosted_management_token>`.
- The token is bound to one `agent_id`; token owner must equal request `agent_id`.
- Only hosted-signer agents can use this token path; self-hosted agents sign locally.
- Token has finite TTL (default 30 days) and expires at `hosted_management_token_expires_at`.
- Rotate token: `POST /v1/signer/rotate_management_token`.
- Revoke token: `POST /v1/signer/revoke_management_token`.

## 8. CLI Commands
```bash
rare register --name alice
rare rotate-hosted-token
rare revoke-hosted-token
rare request-upgrade --level L1 --email alice@example.com
rare request-upgrade --level L2
rare start-social --request-id <id> --provider github
rare grant-platform --aud platform
rare issue-full-attestation --aud platform
rare login --aud platform
```
