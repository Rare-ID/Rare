# Rare Verification Invariants

These invariants are the security contract that tests should enforce across Python and TypeScript implementations.

## Identity Attestation

- Header `typ` must be exactly `rare.identity.public+jws` or `rare.identity.full+jws`.
- Payload `typ` must be exactly `rare.identity`.
- Payload `ver` must be `1`.
- Payload `iss` must be `rare`.
- Payload `sub` must be a valid Ed25519 public key and is the `agent_id`.
- Payload `lvl` must be `L0`, `L1`, or `L2`.
- Public attestations must not include `aud`.
- Full attestations must include `aud`, and it must exactly match the expected platform audience.
- `iat` and `exp` must be integers and must pass the configured clock-skew window.
- Unknown claims must be ignored for forward compatibility.

## Delegation

- Header `typ` must be exactly `rare.delegation+jws`.
- Payload `typ` must be exactly `rare.delegation`.
- Payload `ver` must be `1`.
- Payload `agent_id` must be a valid Ed25519 public key.
- `iss=agent` delegations must verify with `agent_id`.
- `iss=rare-signer` delegations must verify with the Rare delegation signer key.
- `act` must match the issuer: `delegated_by_agent` or `delegated_by_rare`.
- `aud` must exactly match the platform audience.
- `scope` must include the required operation.
- `session_pubkey` must be present.
- `jti` must be present for platform-kit login replay protection.
- `iat` and `exp` must be integers and must pass the configured clock-skew window.

## Platform Login

- The platform challenge nonce is one-time use.
- The session key must sign `rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}`.
- The delegation `session_pubkey` must equal the authenticated session public key.
- The identity triad must hold:
  `auth_complete.agent_id == delegation.agent_id == identity_attestation.sub`.
- Public identity mode caps effective `L2` to `L1`.
- Full identity mode requires platform-bound full attestation.

## Signed Actions

- The platform session token must resolve to an unexpired session.
- The action signing input is:
  `rare-act-v1:{aud}:{session_token}:{action}:{sha256(canonical_json(action_payload))}:{nonce}:{issued_at}:{expires_at}`.
- `canonical_json` must be deterministic across supported SDKs.
- The action nonce is one-time use per session token.
- The action signature must verify against the session public key.

## Platform Events

- Header `typ` must be exactly `rare.platform-event+jws`.
- Payload `typ` must be exactly `rare.platform-event`.
- Payload `aud` must be exactly `rare.identity-library`.
- Platform event `kid` must resolve to an active registered platform key.
- Platform event `jti` must be one-time use per platform issuer.
- `(platform_id, event_id)` must be idempotent.
- Event categories must be allowlisted.

## Verification Commands

Run the focused security checks:

```bash
./scripts/security_check.sh
```

Run the broader core-service security pass as well:

```bash
RARE_SECURITY_FULL=1 ./scripts/security_check.sh
```
