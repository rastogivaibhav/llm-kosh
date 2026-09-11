# Contributing to llm-kosh

Thanks for contributing to `llm-kosh`. The project welcomes focused bug fixes, tests, documentation improvements, interoperability work, and well-scoped feature proposals that preserve the local-first and auditable design.

## Before you start

- Search existing issues before opening a duplicate.
- For larger features or architectural changes, open an issue first so the scope and compatibility expectations are clear.
- Do not include private cartridge data, API keys, credentials, or customer/user data in issues, fixtures, logs, or pull requests.
- Security-sensitive reports should follow [SECURITY.md](SECURITY.md) instead of being disclosed publicly.

## Development setup

Python 3.10 or newer is required.

```bash
python -m pip install -e ".[server,watch,ingest]"
python -m pytest -q
```

For packaging or release changes, also run:

```bash
python -m build
python -m twine check dist/*
```

If your change affects optional semantic-search behaviour, install the `semantic` extra and run the relevant tests locally.

## Pull requests

A good pull request should:

- explain the user or maintainer problem being solved;
- keep the change as small and reviewable as practical;
- add or update tests when behaviour changes;
- update documentation when commands, permissions, configuration, or security boundaries change;
- avoid unrelated generated files or local artifacts;
- preserve backwards compatibility unless the change is intentionally breaking and clearly documented.

## Security-sensitive areas

Changes involving MCP permissions, HTTP transport, export/packing, secret scanning, filesystem intake, private-context access, or ledger integrity should include explicit tests for both the allowed path and the denied/unsafe path.

## Commit and review expectations

Clear commit messages and reproducible evidence make review easier. Maintainers may ask for a smaller patch, additional tests, or documentation before merge. Automated tooling can assist review, but maintainers remain responsible for accepting changes.

## License

By contributing to this repository, you agree that your contributions will be licensed under the repository's [MIT License](LICENSE).
