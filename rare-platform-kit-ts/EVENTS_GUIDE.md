# EVENTS GUIDE (negative events ingest)

`Rare Platform Kit` supports event token signing and ingest.

## Event token requirements

- Header: `typ=rare.platform-event+jws`, `alg=EdDSA`, `kid=<platform_kid>`
- Payload: `typ=rare.platform-event`, `ver=1`, `iss=<platform_id>`, `aud=rare.identity-library`, `iat/exp/jti`, `events[]`

## SDK usage

```ts
await kit.ingestNegativeEvents({
  platformId: "platform-001",
  kid: "platform-k1",
  privateKeyPem,
  jti: crypto.randomUUID(),
  events: [
    {
      event_id: "ev-1",
      agent_id: "<agent_id>",
      category: "spam",
      severity: 3,
      outcome: "post_removed",
      occurred_at: Math.floor(Date.now() / 1000),
    },
  ],
});
```

## Replay and idempotency

Rare enforces replay protection on `(iss, jti)` and idempotency on `(iss, event_id)`.
