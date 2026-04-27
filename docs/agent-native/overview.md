# Agent Native Overview

Rare is an identity and trust layer for agent-native systems. The design center is not user login; it is portable agent identity, delegated sessions, and verifiable trust signals that can move across tools and platforms.

## Direction

- Identity: `agent_id` is the Ed25519 public key.
- Authentication: platforms challenge delegated session keys, not long-term keys.
- Trust: `level` remains identity assurance, while `trust_signals[]` carries ecosystem evidence with source, confidence, decay, evidence hash, and dispute status.
- Discovery: `/.well-known/rare-agent.json` gives agents a machine-readable entry point for Rare identity and capability metadata.
- Interop: Rare references can be embedded into A2A Agent Cards, MCP auth middleware, skills, and To Agent Service style runtime descriptors.

## URL-First Login

Agent login should be URL-first:

```bash
rare login --platform-url https://platform.example.com/rare
rare platform-check --platform-url https://platform.example.com/rare
```

The platform challenge response must include `aud`. The CLI signs the protocol input with that returned value. `--aud` is an optional strict pin for scripted or high-assurance environments.

## Compatibility Surface

`risk_score` remains as a derived compatibility field while integrations migrate toward structured `trust_signals[]`.

Full attestation issuance still requires an explicit target audience unless the audience has already been discovered from a platform challenge.
