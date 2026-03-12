# Trust Model

Rare Platform Kit is designed for local verification-first integration.

## What the Platform Should Verify Locally

- challenge signature by the session key
- delegation token signature and claims
- identity attestation signature and claims
- replay protection for challenge and delegation use
- identity triad consistency:
  `auth_complete.agent_id == delegation.agent_id == attestation.sub`

## What Rare Still Provides

- public identity attestations
- full identity attestations for registered platforms
- Rare JWKS for identity verification
- optional hosted services around the broader Rare ecosystem

## Main Boundary

The platform should not need to trust the private Rare backend for every login decision after it has the signed artifacts and the correct public keys.

## Integration Guidance

- prefer local verification over synchronous backend trust
- treat nonce consumption and replay protection as mandatory
- require `aud` checks for full identity mode
- cap public identity governance to `L1`
