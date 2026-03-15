# RIP-0000 RIP Process and Governance

RIP: 0000
Title: RIP Process and Governance
Status: Final
Type: Meta
Author: Rare Maintainers
Created: 2026-03-03
Updated: 2026-03-03
Requires: None
Replaces: None
Superseded-By: None
Discussion: https://github.com/rare-project/rare/discussions

## Abstract
This RIP defines the canonical process for authoring, reviewing, accepting, and evolving Rare Improvement Proposals (RIPs). It is the only normative source for RIP metadata, status lifecycle, document structure, numbering policy, and governance rules.

## Motivation
Rare protocol and integration behavior must remain auditable and predictable across repositories. A single governance specification prevents process drift, improves contributor onboarding, and enables automated validation in CI.

### Inspiration and scope statement
The RIP process is inspired by established proposal workflows such as NIP, RFC, and BIP.
Rare is building Agent-native identity and governance interfaces, not a Nostr social event network.
Rare acknowledges these process lineages and cites them as references:
- NIP: `https://github.com/nostr-protocol/nips`
- RFC: `https://www.rfc-editor.org/`
- BIP: `https://github.com/bitcoin/bips`

## Specification
### Scope and authority
All normative RIP process rules are defined in this document. Supporting files such as `RIP_TEMPLATE.md`, `CONTRIBUTING_RIP.md`, and CI scripts are non-normative and must not redefine process rules.

### English-only policy
RIP documents MUST be written in English, including metadata values, section headings, and normative text. External discussion links may point to content in any language.

### File naming and location
- Numbered RIPs MUST live in `services/rare-identity-core/docs` and match `rip-XXXX-slug.md`.
- Draft RIPs MUST live in `services/rare-identity-core/docs/drafts` and match `rip-draft-slug.md`.
- `XXXX` is a four digit zero-padded identifier.

### Required metadata block
Every RIP MUST define the following metadata keys exactly once near the document top:
- `RIP`
- `Title`
- `Status`
- `Type`
- `Author`
- `Created`
- `Updated`
- `Requires`
- `Replaces`
- `Superseded-By`
- `Discussion`

Metadata requirements:
- Numbered RIPs MUST set `RIP` to the matching four digit id.
- Draft RIPs MUST set `RIP: TBA`.
- `Status` MUST be one of: `Draft`, `Review`, `Accepted`, `Final`, `Withdrawn`, `Superseded`.
- `Requires`, `Replaces`, and `Superseded-By` MUST be `None` or a comma-separated list of four digit ids.

### Required section structure
Every RIP MUST contain these top-level sections:
- `Abstract`
- `Motivation`
- `Specification`
- `Backward Compatibility`
- `Security Considerations`
- `Test Vectors/Examples`
- `Reference Implementation`

### Status lifecycle
Allowed statuses:
- `Draft`: initial proposal state.
- `Review`: active maintainer review state.
- `Accepted`: approved for implementation and ecosystem use.
- `Final`: stable, widely deployed, and no longer expected to change except errata.
- `Withdrawn`: proposal removed from active consideration.
- `Superseded`: replaced by one or more newer RIPs.

Allowed transitions:
- `Draft -> Review`
- `Review -> Draft`
- `Review -> Accepted`
- `Accepted -> Final`
- `Accepted -> Superseded`
- `Final -> Superseded`
- `Draft -> Withdrawn`
- `Review -> Withdrawn`
- `Accepted -> Withdrawn`

### Number allocation policy
- Community contributors submit drafts using `rip-draft-slug.md`.
- Maintainers allocate official numeric ids when promoting a draft to a numbered RIP.
- Contributors MUST NOT self-assign numbered ids in new draft submissions.

### Review and acceptance policy
- Promotion to `Accepted` requires:
  - passing RIP document CI validation,
  - two maintainer approvals on the pull request.
- Repository branch protection SHOULD enforce these requirements.

### Superseding policy
- A RIP that replaces an earlier RIP MUST set `Replaces` with the earlier id(s).
- A replaced RIP MUST set `Superseded-By` with the replacing id(s) and set status to `Superseded`.
- Cross references MUST resolve to existing numbered RIP ids.

### Index consistency
All RIPs (numbered and draft) MUST be listed in `RIP_INDEX.md` with correct id, status, title, and file path.

## Backward Compatibility
This governance standard does not alter protocol payload formats, signing input strings, or verifier semantics. It only standardizes proposal process and document shape.

## Security Considerations
A consistent proposal process reduces security regression risk by requiring explicit compatibility and security analysis in every RIP. CI checks reduce accidental omission of required sections and broken superseding links.

## Test Vectors/Examples
Example metadata block:

```text
RIP: 0006
Title: Example Proposal
Status: Draft
Type: Standards Track
Author: Example Author
Created: 2026-03-03
Updated: 2026-03-03
Requires: 0001
Replaces: None
Superseded-By: None
Discussion: https://github.com/rare-project/rare/issues/123
```

## Reference Implementation
- `services/rare-identity-core/docs/RIP_TEMPLATE.md`
- `services/rare-identity-core/docs/CONTRIBUTING_RIP.md`
- `services/rare-identity-core/docs/RIP_INDEX.md`
- `scripts/validate_rip_docs.py`
- `.github/workflows/tests.yml`
