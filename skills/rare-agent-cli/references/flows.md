# Rare Agent CLI Flows

## Setup

Use these defaults unless the user explicitly gives different values:

```bash
export RARE_BASE_URL="https://api.rareid.cc"
```

## Hosted-Signer

### Register

```bash
rare register --rare-url "$RARE_BASE_URL" --name alice
```

### Refresh Public Attestation

```bash
rare refresh-attestation --rare-url "$RARE_BASE_URL"
```

### Set Name

```bash
rare set-name --rare-url "$RARE_BASE_URL" --name alice-v2
```

### Request L1 Upgrade

```bash
rare request-upgrade --rare-url "$RARE_BASE_URL" --level L1 --email owner@example.com
rare upgrade-status --rare-url "$RARE_BASE_URL" --request-id <request_id>
```

### Request L2 Upgrade

```bash
rare request-upgrade --rare-url "$RARE_BASE_URL" --level L2
rare start-social --rare-url "$RARE_BASE_URL" --request-id <request_id> --provider github
```

### Platform Login

```bash
rare login \
  --rare-url "$RARE_BASE_URL" \
  --platform-url http://127.0.0.1:8000/platform \
  --aud platform \
  --public-only
```

## Self-Hosted

### Start Local Signer

```bash
rare-signer
```

### Register

```bash
rare register --rare-url "$RARE_BASE_URL" --name alice --key-mode self-hosted
```

### Inspect Local State

```bash
rare show-state --rare-url "$RARE_BASE_URL" --paths
```
