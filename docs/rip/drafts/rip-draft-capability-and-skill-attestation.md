# RIP-TBA Capability and Skill Attestation

RIP: TBA
Title: Capability and Skill Attestation
Status: Draft
Type: Standards Track
Author: Rare Community
Created: 2026-04-27
Updated: 2026-04-27
Requires: 0001, 0002, 0003
Replaces: None
Superseded-By: None
Discussion: https://github.com/Rare-ID/Rare/issues/1

## Abstract
This draft defines a portable attestation format for agent capabilities and skills. It lets platforms, registries, and tool hosts issue signed claims about what an agent can do, with confidence, evidence, and expiry.

## Motivation
Agent-native systems increasingly rely on skills, MCP servers, A2A Agent Cards, hosted tools, and To Agent Service style descriptors. Plain capability text is easy to spoof and hard to revoke. Rare needs a signed capability layer that complements identity assurance and delegated sessions.

## Specification
Capability attestations are compact JWS tokens with header `typ=rare.capability+jws`. The payload MUST contain `typ=rare.capability`, `ver=1`, `iss`, `sub`, `capabilities`, `iat`, and `exp`.

`sub` MUST be the Ed25519 `agent_id`. Each capability item MUST include `id`, `category`, `level`, `confidence`, and `evidence_hash`. `category` SHOULD be one of `skill`, `mcp`, `a2a`, `platform`, or `other`. `confidence` MUST be a number from 0.0 to 1.0. Unknown fields MUST be ignored by verifiers.

Verifiers MUST validate JWS signature, issuer key, expiry, `sub` public-key shape, and capability item shape. Capability attestations MUST NOT grant runtime access by themselves. Runtime access still requires delegation and action verification.

## Backward Compatibility
This proposal is additive. Existing identity attestations, delegation tokens, and platform sessions remain unchanged.

## Security Considerations
Capability attestations can be abused as reputation laundering if issuers are weak. Consumers SHOULD track issuer trust, expiry, evidence hashes, revocation, and dispute status. A capability claim MUST NOT bypass delegated-session scope checks.

## Test Vectors/Examples
Example payload:

```json
{
  "typ": "rare.capability",
  "ver": 1,
  "iss": "rare.capability-registry",
  "sub": "base64-ed25519-agent-public-key",
  "capabilities": [
    {
      "id": "mcp.github.read",
      "category": "mcp",
      "level": "verified",
      "confidence": 0.92,
      "evidence_hash": "sha256:example"
    }
  ],
  "iat": 1777220000,
  "exp": 1779820000
}
```

## Reference Implementation
- `docs/agent-native/capability-attestations.md`
- `docs/agent-native/mcp.md`
- `docs/agent-native/a2a.md`
