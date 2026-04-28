# Rare Agent CLI Flows

## Setup

Use these defaults unless the user explicitly gives different values:

```bash
export RARE_BASE_URL="https://api.rareid.cc"
export PLATFORM_URL="https://platform.example.com/rare"
export PLATFORM_AUD="platform"
```

Install the supported public package surface:

```bash
pip install -U rare-agent-sdk
```

If the shell environment looks suspicious, verify the actual CLI path and package version:

```bash
which rare
python3 -m pip show rare-agent-sdk
python3 - <<'PY'
import sys, importlib.metadata, rare_agent_sdk.cli
print("python:", sys.executable)
print("rare-agent-sdk:", importlib.metadata.version("rare-agent-sdk"))
print("cli:", rare_agent_sdk.cli.__file__)
PY
```

To bypass PATH mismatches, invoke the CLI through the same Python interpreter:

```bash
python3 -m rare_agent_sdk.cli --rare-url "$RARE_BASE_URL" show-state
```

## Hosted-Signer

### Register

```bash
rare register --name alice --rare-url "$RARE_BASE_URL"
```

Success checks:

- output contains `agent_id`
- output contains `public_identity_attestation`
- output contains `hosted_management_token`

### Refresh Public Attestation

```bash
rare refresh-attestation --rare-url "$RARE_BASE_URL"
```

### Set Name

```bash
rare set-name --name alice-v2 --rare-url "$RARE_BASE_URL"
```

### Issue Full Attestation

```bash
rare issue-full-attestation --aud "$PLATFORM_AUD" --rare-url "$RARE_BASE_URL"
```

### Request Upgrade

Production note:

- `L2` requests are only accepted after the agent has already reached `L1` or higher.

Request `L1`:

```bash
rare request-upgrade \
  --level L1 \
  --email owner@example.com \
  --rare-url "$RARE_BASE_URL"
```

Check status:

```bash
rare upgrade-status --request-id <request_id> --rare-url "$RARE_BASE_URL"
```

Resend an L1 link:

```bash
rare send-l1-link --request-id <request_id> --rare-url "$RARE_BASE_URL"
```

Request `L2`:

```bash
rare request-upgrade --level L2 --rare-url "$RARE_BASE_URL"
rare start-social --request-id <request_id> --provider github --rare-url "$RARE_BASE_URL"
```

Supported production providers:

- `github`
- `linkedin`
- `x`

If `start-social` succeeds, expect an `authorize_url`. The upgrade is still pending until the provider OAuth callback finishes and a follow-up status check shows the request completed.

### Platform Login

Public-only login:

```bash
rare login \
  --platform-url "$PLATFORM_URL" \
  --rare-url "$RARE_BASE_URL" \
  --public-only
```

Full-attestation login:

```bash
rare login \
  --platform-url "$PLATFORM_URL" \
  --rare-url "$RARE_BASE_URL"
```

Strict audience pinning:

```bash
rare login \
  --platform-url "$PLATFORM_URL" \
  --aud "$PLATFORM_AUD" \
  --rare-url "$RARE_BASE_URL"
```

Platform smoke check:

```bash
rare platform-check \
  --platform-url "$PLATFORM_URL" \
  --rare-url "$RARE_BASE_URL"
```

Normal login discovers `aud` from the platform challenge response. Use `--aud` only when the caller wants to pin the expected value. Full attestation issuance still uses explicit `rare issue-full-attestation --aud "$PLATFORM_AUD"` because it has no platform challenge step.

### Recovery

Inspect available factors:

```bash
rare recovery-factors --rare-url "$RARE_BASE_URL"
```

Send a recovery email link:

```bash
rare recover-hosted-token-email --rare-url "$RARE_BASE_URL"
```

Verify a recovery email token:

```bash
rare recover-hosted-token-email-verify \
  --token <token-from-email> \
  --rare-url "$RARE_BASE_URL"
```

Start social recovery:

```bash
rare recover-hosted-token-social-start \
  --provider github \
  --rare-url "$RARE_BASE_URL"
```

Supported production recovery providers:

- `github`
- `linkedin`
- `x`

Rotate or revoke the hosted management token:

```bash
rare rotate-hosted-token --rare-url "$RARE_BASE_URL"
rare revoke-hosted-token --rare-url "$RARE_BASE_URL"
```

## Self-Hosted

Use `rare-signer` or `rare signer-serve` so the main CLI process does not directly hold the long-term private key.

### Start the Local Signer

```bash
rare-signer
```

Or explicitly:

```bash
rare signer-serve
```

### Register

```bash
rare register --name alice --key-mode self-hosted --rare-url "$RARE_BASE_URL"
```

### Set Name

```bash
rare set-name --name alice-v2 --rare-url "$RARE_BASE_URL"
```

### Issue Full Attestation

```bash
rare issue-full-attestation --aud "$PLATFORM_AUD" --rare-url "$RARE_BASE_URL"
```

### Request Upgrade

```bash
rare request-upgrade \
  --level L1 \
  --email owner@example.com \
  --rare-url "$RARE_BASE_URL"
```

```bash
rare request-upgrade --level L2 --rare-url "$RARE_BASE_URL"
rare start-social --request-id <request_id> --provider github --rare-url "$RARE_BASE_URL"
```

### Platform Login

```bash
rare login \
  --platform-url "$PLATFORM_URL" \
  --rare-url "$RARE_BASE_URL" \
  --public-only
```

## Not in the Stable Public CLI Surface

The supported public interface is the `rare` / `rare-signer` CLI.

Do not default to:

- raw `curl` workflows for normal agent operations
- `rare_agent_sdk` Python imports as a public SDK surface
- internal helper scripts as the recommended user path

If a user needs lower-level action signing or custom session handling beyond the public CLI commands, explain that this is not the primary supported operating path and switch to the platform integration docs or explicitly call out that they are entering internal / advanced territory.

## External Steps

- `L1` requires access to the target mailbox.
- `L2` requires a real browser session and provider consent.
- Do not say the trust level is upgraded until status is re-checked after the external step.
