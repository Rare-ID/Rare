# Challenge & Signing (RIP-0003)

Rare uses fixed signing inputs to prevent replay and cross-context signature reuse.

## Core Inputs

Challenge authentication:

```text
rare-auth-v1:{aud}:{nonce}:{issued_at}:{expires_at}
```

In normal CLI flows, `aud` is discovered from the platform challenge response returned by `POST <platform-url>/auth/challenge`. The protocol still signs `aud`; URL-first login only removes duplicate user input. A supplied CLI `--aud` is an expected-audience pin and must match the challenge value.

Self-hosted registration:

```text
rare-register-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}
```

Name update:

```text
rare-name-v1:{agent_id}:{normalized_name}:{nonce}:{issued_at}:{expires_at}
```

Full attestation issue:

```text
rare-full-att-v1:{agent_id}:{platform_aud}:{nonce}:{issued_at}:{expires_at}
```

Upgrade request:

```text
rare-upgrade-v1:{agent_id}:{target_level}:{request_id}:{nonce}:{issued_at}:{expires_at}
```

Signed action:

```text
rare-act-v1:{aud}:{session_token}:{action}:{sha256(canonical_json(action_payload))}:{nonce}:{issued_at}:{expires_at}
```

## Validation Rules

Verifiers must enforce:

- one-time nonce consumption
- short validity windows
- `expires_at > issued_at`
- no more than 30 seconds of allowed skew
- exact context binding for values like `aud`, `request_id`, and `target_level`

## Canonical JSON

Action payload hashing uses:

- UTF-8
- sorted keys
- compact separators: `(',', ':')`

## References

- Canonical RIP: `docs/rip/rip-0003-challenge-auth.md`
- Test vectors: `docs/rip/test-vectors/rip-v1-signing-inputs.json`
