# Status

## Stability

Current repository status: early public adoption, pre-`1.0`.

What is relatively stable:

- fixed signing input formats already used by Rare flows
- token verification redlines for identity and delegation
- RIP documents and reference tests

What may still change:

- package ergonomics
- guide structure and examples
- non-breaking helper APIs around the protocol core

## Compatibility

| Component | Version | Notes |
| --- | --- | --- |
| `rare-identity-protocol` | `0.1.0` | Python protocol primitives |
| `rare-identity-verifier` | `0.1.0` | Python verifier for Rare tokens |
| `rare-agent-sdk` | `0.2.0` | consumes protocol primitives |
| `@rare-id/platform-kit-*` | `0.1.0` | follows the same public protocol rules |

Until `1.0`, any public change that affects token structure, signing inputs, or validation rules should be treated as compatibility-sensitive and documented in the RIP docs and release notes.
