# Contributing RIPs

RIP governance rules are normative in `rip-0000-rip-process.md`. This document is only a contributor workflow guide.

## Workflow
1. Copy `RIP_TEMPLATE.md` into `docs/drafts/rip-draft-<slug>.md`.
2. Fill all required metadata and sections.
3. Open a pull request with the RIP PR template.
4. During review, maintainers may move the draft to `Review`.
5. If approved, maintainers assign a numeric id and rename the file to `rip-XXXX-<slug>.md`.
6. Promotion to `Accepted` requires two maintainer approvals and passing RIP CI validation.

## Author checklist
- Metadata keys are complete and valid.
- Status value follows RIP-0000.
- Required sections are present.
- `RIP_INDEX.md` is updated.
- `Replaces` and `Superseded-By` references are valid.
- Protocol changes include updated test vectors and impacted tests.

## Notes
- Do not self-assign numbered ids in draft PRs.
- Keep RIP content in English.
- If signing inputs or protocol payloads change, update related core docs and cross-repo tests in the same PR.
