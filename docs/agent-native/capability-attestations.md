# Capability And Skill Attestations

Capability and skill attestations let an agent prove that a capability claim was issued by a trusted source, not merely self-declared in a prompt or README.

## Claim Shape

```json
{
  "typ": "rare.capability+jws",
  "ver": 1,
  "iss": "rare.capability-registry",
  "sub": "base64-ed25519-agent-public-key",
  "capabilities": [
    {
      "id": "mcp.github.read",
      "category": "mcp",
      "level": "verified",
      "confidence": 0.92,
      "evidence_hash": "sha256:..."
    }
  ],
  "iat": 1777220000,
  "exp": 1779820000
}
```

## Skill Mapping

- Codex or Moltbook style skills map to `category=skill`.
- MCP tools map to `category=mcp`.
- A2A card capabilities map to `category=a2a`.
- Platform-specific permissions map to `category=platform`.

Capability attestation does not replace delegation. Delegation answers "can this session act now"; capability attestation answers "who claims this agent has this skill, with what evidence and confidence".

## Migration

Start with public docs and registry-issued JWS tokens. Later versions can add revocation lists, transparency logs, and selective disclosure.
