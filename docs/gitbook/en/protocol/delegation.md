# Delegation (RIP-0002)

Delegation tokens bind a short-lived session key to an agent identity for one platform audience and one scope set.

## Format

- JWS Compact Serialization
- `alg=EdDSA`
- header `typ=rare.delegation+jws`

## Required Payload Fields

- `typ=rare.delegation`
- `ver=1`
- `iss=agent|rare-signer`
- `agent_id`
- `session_pubkey`
- `aud`
- `scope`
- `iat`
- `exp`
- `act=delegated_by_agent|delegated_by_rare`

`jti` is optional in the schema, but platforms should require it in practice for replay protection.

## Signature Rules

- `iss=agent`: verify with the agent public key
- `iss=rare-signer`: verify with Rare's delegation signer key

## Verification Checklist

Platforms must:

1. verify the JWS signature
2. require exact `aud` match
3. require the requested action in `scope`
4. enforce timestamps with max 30-second skew
5. reject replay when `jti` has already been claimed

## Mandatory Triad Check

Delegation is never sufficient on its own. Platform login must enforce:

```text
auth_complete.agent_id == delegation.agent_id == identity_attestation.sub
```

This prevents identity mixing across artifacts.

## References

- Canonical RIP: `docs/rip/rip-0002-delegation.md`
- Concepts: [Delegation & Sessions](../concepts/delegation-and-sessions.md)

