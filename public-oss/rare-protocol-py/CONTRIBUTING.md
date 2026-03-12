# Contributing

## Scope

This repository is the public protocol layer for Rare. Contributions should stay within public protocol, verifier, docs, tests, and examples.

Out of scope:

- private Rare backend implementation
- hosted signer internals
- deployment or infrastructure details
- secrets, operations runbooks, or production wiring

## Before You Start

- Open an issue for behavior changes, protocol changes, or new public surface area.
- Keep protocol strings and token constraints backward compatible unless the change is explicitly documented.
- If you change protocol fields, signing inputs, or validation rules, update the RIP docs and tests in the same pull request.

## Development

```bash
pip install -r requirements-test.lock
pip install -e .[test] --no-deps
pytest -q
python -m build
```

## Pull Requests

- Keep changes focused and minimal.
- Add or update tests for protocol behavior changes.
- Call out any breaking changes and migration impact explicitly.
- Do not include private keys, tokens, or internal operational details.
