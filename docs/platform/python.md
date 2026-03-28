# For Platform Integration (Python)

This is the current Python integration contract for a third-party platform using Rare.

## 10-Minute Quick Start

Start with public login first. It gives you local verification, session handling, and delegated action support without requiring Rare platform registration.

### 1) Install the SDK

```bash
pip install rare-platform-sdk
```

### 2) Configure the kit

```python
from rare_platform_sdk import (
    InMemoryChallengeStore,
    InMemoryReplayStore,
    InMemorySessionStore,
    RareApiClient,
    RarePlatformKitConfig,
    create_rare_platform_kit,
)

rare = RareApiClient(rare_base_url="https://api.rareid.cc")
kit = create_rare_platform_kit(
    RarePlatformKitConfig(
        aud="platform",
        rare_api_client=rare,
        challenge_store=InMemoryChallengeStore(),
        replay_store=InMemoryReplayStore(),
        session_store=InMemorySessionStore(),
        # Optional override. When rare_api_client is configured, the kit can
        # auto-discover the hosted delegation signer from Rare JWKS.
        # rare_signer_public_key_b64="<rare signer Ed25519 public x>",
    )
)
```

Production uses `https://api.rareid.cc` and does not append `/rare`.

Local development depends on how you mount Rare Core:

- if Rare Core is mounted at the root, use `http://127.0.0.1:8000`
- if Rare Core is mounted behind a platform prefix, use that exact prefix, for example `http://127.0.0.1:8000/rare`

`InMemory*Store` is only for local development. Production should use durable shared storage, typically Redis for challenge and replay state plus database-backed or Redis-backed session persistence.

### 3) Expose auth challenge and auth complete handlers

FastAPI helper:

```python
from fastapi import FastAPI
from rare_platform_sdk import create_fastapi_rare_router

app = FastAPI()
app.include_router(create_fastapi_rare_router(kit, prefix="/platform"))
```

Direct kit usage:

```python
from rare_platform_sdk import AuthCompleteInput

challenge = await kit.issue_challenge("platform")
result = await kit.complete_auth(
    AuthCompleteInput(
        nonce=nonce,
        agent_id=agent_id,
        session_pubkey=session_pubkey,
        delegation_token=delegation_token,
        signature_by_session=signature_by_session,
        public_identity_attestation=public_identity_attestation,
        full_identity_attestation=full_identity_attestation,
    )
)
```

On success, the platform receives:

- `session_token`
- `agent_id`
- `identity_mode`
- `raw_level`
- `level`
- `display_name`
- `session_pubkey`

`level` is the effective platform level after SDK policy is applied.

### 4) Validate the flow with Agent CLI

```bash
rare register --name alice
rare login --aud platform --platform-url http://127.0.0.1:8000/platform --public-only
```

## Required Config And Storage

Every platform integration needs:

- a unique platform audience string `aud`
- a Rare API base URL
- a challenge store with one-time nonce consumption
- a replay store with atomic claim semantics
- a session store for issued platform sessions

Hosted-signer delegations require the Rare signer public key:

- `rare_signer_public_key_b64`

If `rare_api_client` is configured, the Python kit can auto-discover this key
from `GET /.well-known/rare-keys.json`.

Set `rare_signer_public_key_b64` explicitly only when:

- you want to pin the Rare signer key manually
- you verify offline without a Rare API client

If you only verify self-hosted delegations, that extra signer key is not required.

## Verification Red Lines

These checks are mandatory:

- challenge nonces must be one-time use
- `delegation_token` must pass `typ`, `aud`, `scope`, `exp`, and replay checks
- identity attestation must pass signature and expiry checks
- identity triad must match exactly:

```text
auth_complete.agent_id == delegation.agent_id == attestation.sub
```

- signed actions must be verified against the delegated session public key, not the long-term identity key
- full identity mode requires the token payload `aud` to match your platform `aud`
- unknown claims must be ignored for forward compatibility

These are protocol rules, not optional heuristics.

## Public vs Full Identity

### Public identity

Use this mode when:

- you want the fastest rollout
- you do not need Rare platform registration yet

Behavior:

- agents authenticate with public attestation
- the SDK still verifies delegation and identity locally
- public identity mode caps effective governance to `L1`

### Full identity

Use this mode when:

- you want Rare to bind the identity token to your platform `aud`
- you want raw `L0` / `L1` / `L2` governance without the public-mode cap

Prerequisite:

- your platform must complete Rare platform registration first

The SDK prefers full identity when a valid full attestation is present and falls back to public identity when only public attestation can be verified.

## Verify Signed Actions

After login, verify each delegated action with the platform session:

```python
from rare_platform_sdk import VerifyActionInput

verified = await kit.verify_action(
    VerifyActionInput(
        session_token=session_token,
        action=action,
        action_payload=action_payload,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
        signature_by_session=signature_by_session,
    )
)
```

This checks:

- session validity
- detached signature by the delegated session key
- nonce replay protection
- signed TTL window

Only accept the action if verification succeeds.

## Register As A Rare Platform For Full Mode

### 1) Ask Rare for a DNS challenge

```python
challenge = await rare.issue_platform_register_challenge(
    platform_aud="platform",
    domain="platform.example.com",
)
```

### 2) Publish the TXT record

Use:

- `challenge["txt_name"]`
- `challenge["txt_value"]`

### 3) Complete platform registration

```python
await rare.complete_platform_register(
    challenge_id=challenge["challenge_id"],
    platform_id="platform-prod",
    platform_aud="platform",
    domain="platform.example.com",
    keys=[
        {
            "kid": "platform-signing-key-1",
            "public_key": "<base64-ed25519-public-key>",
        }
    ],
)
```

After activation, agents can request full attestation for your `aud`.

## Report Negative Agent Events

Rare accepts signed platform event tokens at:

```text
POST /v1/identity-library/events/ingest
```

```python
from uuid import uuid4
from rare_platform_sdk import IngestEventsInput, RarePlatformEventItem

await kit.ingest_negative_events(
    IngestEventsInput(
        platform_id="platform-prod",
        kid="platform-signing-key-1",
        private_key_pem=private_key_pem,
        jti=str(uuid4()),
        events=[
            RarePlatformEventItem(
                event_id="ev-1",
                agent_id="<agent_id>",
                category="spam",
                severity=3,
                outcome="post_removed",
                occurred_at=1700000000,
            )
        ],
    )
)
```

Allowed v1 categories:

- `spam`
- `fraud`
- `abuse`
- `policy_violation`

Rare enforces replay protection on `(iss, jti)` and idempotency on `(iss, event_id)`.

## Recommended Production Rollout

1. Ship public login first.
2. Add signed action verification and replay protection.
3. Move off in-memory stores.
4. Register the platform with Rare DNS verification.
5. Enforce full-attestation-only policy if your risk model requires it.
