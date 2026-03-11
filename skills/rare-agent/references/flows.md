# Rare Agent Flows

## Setup

Use these defaults unless the user explicitly gives different values:

```bash
export RARE_BASE_URL="https://api.rareid.cc"
```

For hosted mode, keep sensitive values in shell variables and never echo them back in plain text:

```bash
export AGENT_ID="..."
export HOSTED_MANAGEMENT_TOKEN="..."
```

## Hosted-Signer

### Register

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/agents/self_register" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "alice",
    "key_mode": "hosted-signer"
  }'
```

Success checks:

- response contains `agent_id`
- response contains `public_identity_attestation`
- response contains `hosted_management_token`

### Refresh Public Attestation

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/attestations/refresh" \
  -H 'Content-Type: application/json' \
  -d "{
    \"agent_id\": \"$AGENT_ID\"
  }"
```

### Issue Public Attestation

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/attestations/public/issue" \
  -H 'Content-Type: application/json' \
  -d "{
    \"agent_id\": \"$AGENT_ID\"
  }"
```

### Set Name

Prepare the signed payload:

```bash
SIGNED_SET_NAME="$(curl -sS \
  -X POST "$RARE_BASE_URL/v1/signer/sign_set_name" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $HOSTED_MANAGEMENT_TOKEN" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"name\": \"alice-v2\",
    \"ttl_seconds\": 120
  }")"
```

Submit the rename:

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/agents/set_name" \
  -H 'Content-Type: application/json' \
  -d "$SIGNED_SET_NAME"
```

### Issue Full Attestation

Prepare the signed request:

```bash
SIGNED_FULL="$(curl -sS \
  -X POST "$RARE_BASE_URL/v1/signer/sign_full_attestation_issue" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $HOSTED_MANAGEMENT_TOKEN" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"platform_aud\": \"platform\",
    \"ttl_seconds\": 120
  }")"
```

Issue the attestation:

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/attestations/full/issue" \
  -H 'Content-Type: application/json' \
  -d "$SIGNED_FULL"
```

### Request Upgrade

Choose a request id first:

```bash
export REQUEST_ID="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(12))
PY
)"
```

Prepare the signed upgrade request:

```bash
SIGNED_UPGRADE="$(curl -sS \
  -X POST "$RARE_BASE_URL/v1/signer/sign_upgrade_request" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $HOSTED_MANAGEMENT_TOKEN" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"target_level\": \"L1\",
    \"request_id\": \"$REQUEST_ID\",
    \"ttl_seconds\": 120
  }")"
```

Create the upgrade request:

```bash
SIGNED_UPGRADE_REQUEST="$(printf '%s' "$SIGNED_UPGRADE" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
payload["contact_email"] = "owner@example.com"
payload["send_email"] = True
print(json.dumps(payload))
')"
```

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/upgrades/requests" \
  -H 'Content-Type: application/json' \
  -d "$SIGNED_UPGRADE_REQUEST"
```

Check status:

```bash
curl -sS \
  "$RARE_BASE_URL/v1/upgrades/requests/$REQUEST_ID" \
  -H "Authorization: Bearer $HOSTED_MANAGEMENT_TOKEN"
```

Resend an L1 link:

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/upgrades/l1/email/send-link" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $HOSTED_MANAGEMENT_TOKEN" \
  -d "{
    \"upgrade_request_id\": \"$REQUEST_ID\"
  }"
```

Start L2 social verification:

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/upgrades/l2/social/start" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $HOSTED_MANAGEMENT_TOKEN" \
  -d "{
    \"upgrade_request_id\": \"$REQUEST_ID\",
    \"provider\": \"github\"
  }"
```

### Recovery

Inspect available factors:

```bash
curl -sS "$RARE_BASE_URL/v1/signer/recovery/factors/$AGENT_ID"
```

Send a recovery email link:

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/signer/recovery/email/send-link" \
  -H 'Content-Type: application/json' \
  -d "{
    \"agent_id\": \"$AGENT_ID\"
  }"
```

Verify a recovery email token:

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/signer/recovery/email/verify" \
  -H 'Content-Type: application/json' \
  -d '{
    "token": "<token-from-email>"
  }'
```

Start social recovery:

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/signer/recovery/social/start" \
  -H 'Content-Type: application/json' \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"provider\": \"github\"
  }"
```

## Self-Hosted

Install the only required helper dependency if needed:

```bash
python3 -m pip install cryptography
```

### Generate a Keypair

```bash
python3 skills/rare-agent/scripts/rare_sign.py gen-keypair \
  --private-key-file ~/.config/rare/agent.key
```

### Register

```bash
SIGNED_REGISTER="$(python3 skills/rare-agent/scripts/rare_sign.py register \
  --private-key-file ~/.config/rare/agent.key \
  --name alice)"
```

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/agents/self_register" \
  -H 'Content-Type: application/json' \
  -d "{
    \"name\": \"$(printf '%s' "$SIGNED_REGISTER" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"name\"])')\",
    \"key_mode\": \"self-hosted\",
    \"agent_public_key\": \"$(printf '%s' "$SIGNED_REGISTER" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"agent_id\"])')\",
    \"nonce\": \"$(printf '%s' "$SIGNED_REGISTER" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"nonce\"])')\",
    \"issued_at\": $(printf '%s' "$SIGNED_REGISTER" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"issued_at\"])'),
    \"expires_at\": $(printf '%s' "$SIGNED_REGISTER" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"expires_at\"])'),
    \"signature_by_agent\": \"$(printf '%s' "$SIGNED_REGISTER" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"signature_by_agent\"])')\"
  }"
```

### Set Name

```bash
SIGNED_SET_NAME="$(python3 skills/rare-agent/scripts/rare_sign.py set-name \
  --private-key-file ~/.config/rare/agent.key \
  --agent-id "$AGENT_ID" \
  --name alice-v2)"
```

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/agents/set_name" \
  -H 'Content-Type: application/json' \
  -d "$SIGNED_SET_NAME"
```

### Issue Full Attestation

```bash
SIGNED_FULL="$(python3 skills/rare-agent/scripts/rare_sign.py issue-full-attestation \
  --private-key-file ~/.config/rare/agent.key \
  --agent-id "$AGENT_ID" \
  --platform-aud platform)"
```

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/attestations/full/issue" \
  -H 'Content-Type: application/json' \
  -d "$SIGNED_FULL"
```

### Request Upgrade

```bash
SIGNED_UPGRADE="$(python3 skills/rare-agent/scripts/rare_sign.py upgrade-request \
  --private-key-file ~/.config/rare/agent.key \
  --agent-id "$AGENT_ID" \
  --target-level L1 \
  --contact-email owner@example.com)"
```

```bash
curl -sS \
  -X POST "$RARE_BASE_URL/v1/upgrades/requests" \
  -H 'Content-Type: application/json' \
  -d "$SIGNED_UPGRADE"
```

### Platform Login

Get the platform challenge:

```bash
CHALLENGE="$(curl -sS \
  -X POST "https://platform.example.com/auth/challenge" \
  -H 'Content-Type: application/json' \
  -d '{
    "aud": "platform"
  }')"
```

Generate local auth proof:

```bash
AUTH_PROOF="$(python3 skills/rare-agent/scripts/rare_sign.py prepare-auth \
  --private-key-file ~/.config/rare/agent.key \
  --agent-id "$AGENT_ID" \
  --aud platform \
  --nonce "$(printf '%s' "$CHALLENGE" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"nonce\"])')" \
  --issued-at "$(printf '%s' "$CHALLENGE" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"issued_at\"])')" \
  --expires-at "$(printf '%s' "$CHALLENGE" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"expires_at\"])')" \
  --session-private-key-file ~/.config/rare/platform-session.key)"
```

Complete platform login:

```bash
curl -sS \
  -X POST "https://platform.example.com/auth/complete" \
  -H 'Content-Type: application/json' \
  -d "{
    \"nonce\": \"$(printf '%s' "$CHALLENGE" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"nonce\"])')\",
    \"agent_id\": \"$AGENT_ID\",
    \"session_pubkey\": \"$(printf '%s' "$AUTH_PROOF" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"session_pubkey\"])')\",
    \"delegation_token\": \"$(printf '%s' "$AUTH_PROOF" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"delegation_token\"])')\",
    \"signature_by_session\": \"$(printf '%s' "$AUTH_PROOF" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"signature_by_session\"])')\",
    \"public_identity_attestation\": \"<public_identity_attestation>\"
  }"
```

### Sign a Platform Action

```bash
SIGNED_ACTION="$(python3 skills/rare-agent/scripts/rare_sign.py sign-action \
  --session-private-key-file ~/.config/rare/platform-session.key \
  --aud platform \
  --session-token "<session_token>" \
  --action post \
  --action-payload '{"content":"hello"}')"
```

```bash
curl -sS \
  -X POST "https://platform.example.com/posts" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer <session_token>" \
  -d "{
    \"content\": \"hello\",
    \"nonce\": \"$(printf '%s' "$SIGNED_ACTION" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"nonce\"])')\",
    \"issued_at\": $(printf '%s' "$SIGNED_ACTION" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"issued_at\"])'),
    \"expires_at\": $(printf '%s' "$SIGNED_ACTION" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"expires_at\"])'),
    \"signature_by_session\": \"$(printf '%s' "$SIGNED_ACTION" | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"signature_by_session\"])')\"
  }"
```

## External Steps

- `L1` requires access to the target mailbox.
- `L2` requires a real browser session and provider consent.
- Do not say the trust level is upgraded until status is re-checked after the external step.
