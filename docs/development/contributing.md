# Contributing

We welcome contributions to Codex Aura! Here's how you can help.

## Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/codex-aura.git`
3. Create a virtual environment: `python -m venv venv`
4. Activate it: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Unix)
5. Install development dependencies: `pip install -e ".[dev]"`
6. Run tests: `pytest`

## Code Style

We use:
- **Black** for code formatting
- **ruff** for linting
- **mypy** for type checking

Run all checks:

```bash
ruff check src/
black src/
mypy src/
```

## Testing

- Write tests for new features
- Maintain test coverage above 80%
- Run tests: `pytest`
- Run with coverage: `pytest --cov=src/codex_aura`

## Pull Request Process

1. Create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes
3. Run tests and linting
4. Update documentation if needed
5. Commit with clear messages
6. Push and create PR

## Commit Messages

Use conventional commits:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation
- `test:` for tests
- `refactor:` for code refactoring

## Issue Reporting

- Use issue templates
- Provide clear reproduction steps
- Include environment details
- Add code examples when possible

## Documentation

- Update docs for new features
- Keep examples current
- Test documentation builds: `mkdocs build`

## Code Review

- Be respectful and constructive
- Focus on code quality and maintainability
- Suggest improvements, don't demand changes
- Approve when requirements are met

## Release Process

- Semantic versioning (MAJOR.MINOR.PATCH)
- Changelog maintained in `CHANGELOG.md`
- Releases created from `main` branch
- Pre-releases use `-rc.N` suffix

## Community

- Join our Discord server
- Follow us on Twitter
- Read our blog for updates