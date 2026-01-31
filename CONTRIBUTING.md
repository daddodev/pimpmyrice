# Contributing to PimpMyRice

Thanks for contributing! All documentation lives at [pimpmyrice.vercel.app/docs](https://pimpmyrice.vercel.app/docs).

- [💬 Discord](https://discord.gg/TDrSB2wk6c)
- [🐛 Issues](https://github.com/daddodev/pimpmyrice/issues)

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/pimpmyrice.git
cd pimpmyrice
uv sync --dev
uv pip install -e .
pytest
```

## Code Standards

All checks run in CI. Set them up in your editor or run them locally before pushing:

```bash
ruff check src/pimpmyrice tests
ruff format --check src/pimpmyrice tests
isort --check src/pimpmyrice tests
mypy src/pimpmyrice tests
pytest
```

Fix automatically where possible:

```bash
ruff check --fix src/pimpmyrice
ruff format src/pimpmyrice
isort src/pimpmyrice
```

### Style

- **Line length**: 88 characters
- **Type hints**: Strict mode enabled
- **Imports**: stdlib → third-party → local (use `TYPE_CHECKING` for circular deps)
- **Docstrings**: Google-style
- Use `pathlib.Path`, Pydantic models, and `log.exception()` for errors

## Pull Requests

1. Create a focused branch: `git checkout -b feature/description`
2. Make atomic commits following existing patterns
3. Ensure all checks pass
4. Reference related issues in the PR description

## License

Contributions are licensed under MIT.
