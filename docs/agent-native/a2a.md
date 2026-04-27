# A2A Agent Card Adapter

A2A Agent Cards can embed Rare references so callers can bind a human-readable agent card to a cryptographic identity.

## Card Extension

```json
{
  "name": "Research Agent",
  "url": "https://agent.example.com",
  "capabilities": ["research", "summarization"],
  "extensions": {
    "rare": {
      "agent_id": "base64-ed25519-public-key",
      "public_identity_attestation": "rare.identity.public+jws...",
      "well_known": "https://agent.example.com/.well-known/rare-agent.json",
      "required_aud": "agent.example.com"
    }
  }
}
```

## Verification

1. Fetch the card and `/.well-known/rare-agent.json`.
2. Verify the public identity attestation using Rare JWKS.
3. Require `attestation.sub == extensions.rare.agent_id`.
4. For platform login, call the platform challenge endpoint and use the returned `aud`.
5. If `required_aud` is present, treat it like a strict audience pin.

This keeps A2A discovery ergonomic while preserving Rare's protocol invariant that authorization is based on the Ed25519 `agent_id`.
