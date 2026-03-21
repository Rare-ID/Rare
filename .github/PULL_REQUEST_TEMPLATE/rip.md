## RIP Pull Request

### RIP metadata
- RIP file: `docs/rip/<file>.md`
- Current status: `<Draft|Review|Accepted|Final|Withdrawn|Superseded>`
- Target status after merge: `<Draft|Review|Accepted|Final|Withdrawn|Superseded>`

### Change summary
Describe the protocol or process change in one short paragraph.

### Compatibility impact
- [ ] No backward compatibility impact
- [ ] Backward compatible with migration notes
- [ ] Breaking change (requires rollout plan)

Details:

### Security review
Describe security impact, threat model changes, and mitigations.

### Test vectors and tests
- [ ] `Test Vectors/Examples` section updated in RIP
- [ ] Core tests updated if behavior changed
- [ ] Cross-repo integration tests updated if required

### Signature and protocol impact
- [ ] No signing input or payload format changes
- [ ] Signing input changed and corresponding RIP/test updates included
- [ ] Payload schema changed and verifier/test updates included

### Cross-references
- `Requires`: `<None or ids>`
- `Replaces`: `<None or ids>`
- `Superseded-By`: `<None or ids>`

### Acceptance gate (maintainers)
- [ ] RIP docs validator is passing in CI
- [ ] Two maintainer approvals are present
