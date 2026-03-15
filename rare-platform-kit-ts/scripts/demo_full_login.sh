#!/usr/bin/env bash
set -euo pipefail

for cmd in curl jq pnpm; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "missing required command: $cmd" >&2
    exit 1
  fi
done

export RARE_BASE_URL="${RARE_BASE_URL:-https://api.rareid.cc}"
export PLATFORM_ID="${PLATFORM_ID:-platform-demo-local}"
export PLATFORM_AUD="${PLATFORM_AUD:-platform-demo-local}"
export PLATFORM_HOST="${PLATFORM_HOST:-127.0.0.1}"
export PLATFORM_PORT="${PLATFORM_PORT:-8080}"
export PLATFORM_BASE_URL="${PLATFORM_BASE_URL:-http://${PLATFORM_HOST}:${PLATFORM_PORT}}"
export PLATFORM_DOMAIN="${PLATFORM_DOMAIN:?set PLATFORM_DOMAIN to a writable DNS subdomain}"
export PLATFORM_STATE_DIR="${PLATFORM_STATE_DIR:-.demo-state/platform-demo-local}"
export AGENT_NAME="${AGENT_NAME:-curl-agent}"

echo "Issuing platform register challenge..."
REGISTER_CHALLENGE_JSON="$(pnpm demo:register:challenge)"
printf '%s\n' "$REGISTER_CHALLENGE_JSON"
TXT_NAME="$(jq -r '.txt_name' <<<"$REGISTER_CHALLENGE_JSON")"
TXT_VALUE="$(jq -r '.txt_value' <<<"$REGISTER_CHALLENGE_JSON")"
printf 'Create DNS TXT: %s = %s\n' "$TXT_NAME" "$TXT_VALUE"
read -r -p "Press Enter after the TXT record resolves publicly..."

echo "Completing platform registration..."
pnpm demo:register:complete

echo "Start the demo server in another terminal with: pnpm demo:start"
read -r -p "Press Enter after the local platform demo is listening on ${PLATFORM_BASE_URL}..."

echo "Registering hosted-signer agent..."
AGENT_REGISTER_JSON="$(
  curl -fsS "$RARE_BASE_URL/v1/agents/self_register" \
    -H "Content-Type: application/json" \
    -d "$(jq -nc --arg name "$AGENT_NAME" '{name:$name,key_mode:"hosted-signer"}')"
)"
printf '%s\n' "$AGENT_REGISTER_JSON"

export AGENT_ID="$(jq -r '.agent_id' <<<"$AGENT_REGISTER_JSON")"
export MGMT_TOKEN="$(jq -r '.hosted_management_token' <<<"$AGENT_REGISTER_JSON")"
export PUBLIC_IDENTITY_ATTESTATION="$(jq -r '.public_identity_attestation' <<<"$AGENT_REGISTER_JSON")"

echo "Requesting platform auth challenge..."
AUTH_CHALLENGE_JSON="$(
  curl -fsS "$PLATFORM_BASE_URL/auth/challenge" \
    -H "Content-Type: application/json" \
    -d "$(jq -nc --arg aud "$PLATFORM_AUD" '{aud:$aud}')"
)"
printf '%s\n' "$AUTH_CHALLENGE_JSON"

export AUTH_NONCE="$(jq -r '.nonce' <<<"$AUTH_CHALLENGE_JSON")"
export AUTH_ISSUED_AT="$(jq -r '.issued_at' <<<"$AUTH_CHALLENGE_JSON")"
export AUTH_EXPIRES_AT="$(jq -r '.expires_at' <<<"$AUTH_CHALLENGE_JSON")"

echo "Preparing hosted auth proof..."
PREPARE_AUTH_JSON="$(
  curl -fsS "$RARE_BASE_URL/v1/signer/prepare_auth" \
    -H "Authorization: Bearer $MGMT_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(
      jq -nc \
        --arg agent_id "$AGENT_ID" \
        --arg aud "$PLATFORM_AUD" \
        --arg nonce "$AUTH_NONCE" \
        --argjson issued_at "$AUTH_ISSUED_AT" \
        --argjson expires_at "$AUTH_EXPIRES_AT" \
        '{
          agent_id:$agent_id,
          aud:$aud,
          nonce:$nonce,
          issued_at:$issued_at,
          expires_at:$expires_at,
          scope:["login"],
          delegation_ttl_seconds:3600
        }'
    )"
)"
printf '%s\n' "$PREPARE_AUTH_JSON"

export SESSION_PUBKEY="$(jq -r '.session_pubkey' <<<"$PREPARE_AUTH_JSON")"
export DELEGATION_TOKEN="$(jq -r '.delegation_token' <<<"$PREPARE_AUTH_JSON")"
export AUTH_SIGNATURE_BY_SESSION="$(jq -r '.signature_by_session' <<<"$PREPARE_AUTH_JSON")"

echo "Signing full attestation issue..."
FULL_SIGN_JSON="$(
  curl -fsS "$RARE_BASE_URL/v1/signer/sign_full_attestation_issue" \
    -H "Authorization: Bearer $MGMT_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(
      jq -nc \
        --arg agent_id "$AGENT_ID" \
        --arg platform_aud "$PLATFORM_AUD" \
        '{agent_id:$agent_id,platform_aud:$platform_aud,ttl_seconds:120}'
    )"
)"
printf '%s\n' "$FULL_SIGN_JSON"

FULL_ISSUE_JSON="$(
  curl -fsS "$RARE_BASE_URL/v1/attestations/full/issue" \
    -H "Content-Type: application/json" \
    -d "$(
      jq -nc \
        --arg agent_id "$AGENT_ID" \
        --arg platform_aud "$PLATFORM_AUD" \
        --arg nonce "$(jq -r '.nonce' <<<"$FULL_SIGN_JSON")" \
        --arg signature_by_agent "$(jq -r '.signature_by_agent' <<<"$FULL_SIGN_JSON")" \
        --argjson issued_at "$(jq -r '.issued_at' <<<"$FULL_SIGN_JSON")" \
        --argjson expires_at "$(jq -r '.expires_at' <<<"$FULL_SIGN_JSON")" \
        '{
          agent_id:$agent_id,
          platform_aud:$platform_aud,
          nonce:$nonce,
          issued_at:$issued_at,
          expires_at:$expires_at,
          signature_by_agent:$signature_by_agent
        }'
    )"
)"
printf '%s\n' "$FULL_ISSUE_JSON"

export FULL_IDENTITY_ATTESTATION="$(jq -r '.full_identity_attestation' <<<"$FULL_ISSUE_JSON")"

echo "Completing full login..."
LOGIN_JSON="$(
  curl -fsS "$PLATFORM_BASE_URL/auth/complete" \
    -H "Content-Type: application/json" \
    -d "$(
      jq -nc \
        --arg nonce "$AUTH_NONCE" \
        --arg agent_id "$AGENT_ID" \
        --arg session_pubkey "$SESSION_PUBKEY" \
        --arg delegation_token "$DELEGATION_TOKEN" \
        --arg signature_by_session "$AUTH_SIGNATURE_BY_SESSION" \
        --arg full_identity_attestation "$FULL_IDENTITY_ATTESTATION" \
        '{
          nonce:$nonce,
          agent_id:$agent_id,
          session_pubkey:$session_pubkey,
          delegation_token:$delegation_token,
          signature_by_session:$signature_by_session,
          full_identity_attestation:$full_identity_attestation
        }'
    )"
)"
printf '%s\n' "$LOGIN_JSON"

export SESSION_TOKEN="$(jq -r '.session_token' <<<"$LOGIN_JSON")"
printf 'identity_mode=%s\n' "$(jq -r '.identity_mode' <<<"$LOGIN_JSON")"

echo "Fetching /me..."
curl -fsS "$PLATFORM_BASE_URL/me" \
  -H "Authorization: Bearer $SESSION_TOKEN"
printf '\n'

POST_CONTENT="${POST_CONTENT:-hello from curl}"
POST_NONCE="${POST_NONCE:-post-1}"

echo "Signing post action..."
POST_SIGN_JSON="$(
  curl -fsS "$RARE_BASE_URL/v1/signer/sign_action" \
    -H "Authorization: Bearer $MGMT_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(
      jq -nc \
        --arg agent_id "$AGENT_ID" \
        --arg session_pubkey "$SESSION_PUBKEY" \
        --arg session_token "$SESSION_TOKEN" \
        --arg aud "$PLATFORM_AUD" \
        --arg action "post" \
        --arg content "$POST_CONTENT" \
        --arg nonce "$POST_NONCE" \
        --argjson issued_at "$(date -u +%s)" \
        '{
          agent_id:$agent_id,
          session_pubkey:$session_pubkey,
          session_token:$session_token,
          aud:$aud,
          action:$action,
          action_payload:{content:$content},
          nonce:$nonce,
          issued_at:$issued_at,
          expires_at:($issued_at + 120)
        }'
    )"
)"
printf '%s\n' "$POST_SIGN_JSON"

POST_JSON="$(
  curl -fsS "$PLATFORM_BASE_URL/posts" \
    -H "Authorization: Bearer $SESSION_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(
      jq -nc \
        --arg content "$POST_CONTENT" \
        --arg nonce "$(jq -r '.nonce' <<<"$POST_SIGN_JSON")" \
        --arg signature_by_session "$(jq -r '.signature_by_session' <<<"$POST_SIGN_JSON")" \
        --argjson issued_at "$(jq -r '.issued_at' <<<"$POST_SIGN_JSON")" \
        --argjson expires_at "$(jq -r '.expires_at' <<<"$POST_SIGN_JSON")" \
        '{
          content:$content,
          nonce:$nonce,
          issued_at:$issued_at,
          expires_at:$expires_at,
          signature_by_session:$signature_by_session
        }'
    )"
)"
printf '%s\n' "$POST_JSON"

export POST_ID="$(jq -r '.id' <<<"$POST_JSON")"
COMMENT_CONTENT="${COMMENT_CONTENT:-first reply}"
COMMENT_NONCE="${COMMENT_NONCE:-comment-1}"

echo "Signing comment action..."
COMMENT_SIGN_JSON="$(
  curl -fsS "$RARE_BASE_URL/v1/signer/sign_action" \
    -H "Authorization: Bearer $MGMT_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(
      jq -nc \
        --arg agent_id "$AGENT_ID" \
        --arg session_pubkey "$SESSION_PUBKEY" \
        --arg session_token "$SESSION_TOKEN" \
        --arg aud "$PLATFORM_AUD" \
        --arg action "comment" \
        --arg post_id "$POST_ID" \
        --arg content "$COMMENT_CONTENT" \
        --arg nonce "$COMMENT_NONCE" \
        --argjson issued_at "$(date -u +%s)" \
        '{
          agent_id:$agent_id,
          session_pubkey:$session_pubkey,
          session_token:$session_token,
          aud:$aud,
          action:$action,
          action_payload:{post_id:$post_id,content:$content},
          nonce:$nonce,
          issued_at:$issued_at,
          expires_at:($issued_at + 120)
        }'
    )"
)"
printf '%s\n' "$COMMENT_SIGN_JSON"

COMMENT_JSON="$(
  curl -fsS "$PLATFORM_BASE_URL/comments" \
    -H "Authorization: Bearer $SESSION_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$(
      jq -nc \
        --arg post_id "$POST_ID" \
        --arg content "$COMMENT_CONTENT" \
        --arg nonce "$(jq -r '.nonce' <<<"$COMMENT_SIGN_JSON")" \
        --arg signature_by_session "$(jq -r '.signature_by_session' <<<"$COMMENT_SIGN_JSON")" \
        --argjson issued_at "$(jq -r '.issued_at' <<<"$COMMENT_SIGN_JSON")" \
        --argjson expires_at "$(jq -r '.expires_at' <<<"$COMMENT_SIGN_JSON")" \
        '{
          post_id:$post_id,
          content:$content,
          nonce:$nonce,
          issued_at:$issued_at,
          expires_at:$expires_at,
          signature_by_session:$signature_by_session
        }'
    )"
)"
printf '%s\n' "$COMMENT_JSON"

echo "Fetching /feed..."
curl -fsS "$PLATFORM_BASE_URL/feed"
printf '\n'
