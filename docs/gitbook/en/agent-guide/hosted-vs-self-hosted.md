# Hosted vs Self-Hosted

Rare supports two agent key-management models.

## Hosted-Signer

Rare generates and stores the long-term Ed25519 key.

Choose this when:

- the agent runtime cannot safely persist keys
- you want the simplest operational path
- you need recovery flows

Trade-offs:

- signing depends on Rare infrastructure
- access to the management token becomes a sensitive control point

Related capabilities:

- management token rotation
- email recovery
- social recovery for eligible L2 agents

## Self-Hosted

The agent keeps the long-term Ed25519 key locally.

Choose this when:

- you need full control over key custody
- you want no hosted signing dependency
- you already have secure key storage or HSM-like controls

Trade-offs:

- no recovery path through Rare if the key is lost
- you must operate local secret storage safely

## Recommended Setup for Self-Hosted

Use `rare-signer` so the main CLI process does not directly hold the agent private key:

```bash
rare-signer
rare register --name alice --key-mode self-hosted
```

The signer stores its key file under the Rare config directory with restricted permissions.

## Decision Rule

Use hosted-signer for fast adoption and operator recovery.

Use self-hosted when key custody is a hard requirement rather than a preference.

