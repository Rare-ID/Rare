# Status

## Stability

Current repository status: usable for evaluation and early integration, pre-`1.0`.

What is relatively stable:

- local verification-first login flow
- challenge, replay, and session abstractions
- framework adapters and core verification behavior

What may still change:

- adapter ergonomics
- package boundaries inside the monorepo
- additional examples and storage integrations

## Compatibility

| Package set | Version | Protocol dependency |
| --- | --- | --- |
| `@rare-id/platform-kit-*` | `0.1.0` | current public Rare protocol rules |
| `rare-agent-sdk` | `0.2.0` | produces compatible login artifacts |
| `rare-identity-protocol` | `0.1.0` | reference protocol behavior |

Until `1.0`, changes affecting login verification, session semantics, or adapter behavior should be treated as compatibility-sensitive.
