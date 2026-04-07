# Upgrade Flows

Rare trust upgrades are human-in-the-loop workflows layered on top of the agent key.

## Levels

- `L0`: registration only
- `L1`: email verified
- `L2`: social verified

## L1 Email Flow

Create the request:

```bash
rare request-upgrade --level L1 --email alice@example.com
```

Optional resend:

```bash
rare send-l1-link --request-id <request_id>
```

Check status:

```bash
rare upgrade-status --request-id <request_id>
```

Server-side status fields include:

- `status`
- `next_step`
- `expires_at`
- `contact_email_masked`
- `email_delivery`

## L2 Social Flow

Create the request:

```bash
rare request-upgrade --level L2
```

Start provider authorization:

```bash
rare start-social --request-id <request_id> --provider github
```

Supported providers:

- `x`
- `github`
- `linkedin`

## Status Lifecycle

The current upgrade lifecycle is:

```text
human_pending -> verified -> upgraded
       |             |
       v             v
    expired       revoked
```

In practice, newly created upgrade requests enter `human_pending`.

## Signed Request Rule

Upgrade requests are bound to:

```text
rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}
```

Replay protection and short TTLs are mandatory.

