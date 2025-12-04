# Contributing to Codex Aura

Thank you for your interest in contributing to Codex Aura! We welcome contributions from the community.

## How to Contribute

### 1. Fork the Repository

Fork the repository on GitHub and clone your fork locally:

```bash
git clone https://github.com/your-username/codex-aura.git
cd codex-aura
```

### 2. Set Up Development Environment

Install the package in development mode with all dependencies:

```bash
pip install -e ".[dev]"
```

### 3. Run Tests

Make sure all tests pass before making changes:

```bash
pytest
```

For coverage report:

```bash
pytest --cov=codex_aura --cov-report=html
```

### 4. Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check code style
ruff check src/

# Auto-fix issues
ruff check src/ --fix

# Format code
ruff format src/
```

### 5. Make Changes

- Create a feature branch: `git checkout -b feature/your-feature-name`
- Write tests for new functionality
- Ensure all tests pass
- Update documentation if needed
- Follow the existing code style

### 6. Submit Pull Request

1. Push your changes to your fork
2. Create a Pull Request on GitHub
3. Provide a clear description of the changes
4. Reference any related issues

## Development Setup

### Prerequisites

- Python 3.11+
- pip
- git

### Installing Dependencies

```bash
# Install in development mode
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_models.py

# Run with coverage
pytest --cov=codex_aura
```

### Building Documentation

```bash
# Generate API docs
pydoc codex_aura
```

## Code Style Guidelines

- Use type hints for all function parameters and return values
- Write docstrings in Google style format
- Keep functions small and focused
- Use descriptive variable names
- Add tests for all new functionality
- Maintain test coverage above 80%

## Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch
3. **Commit** your changes with clear messages
4. **Push** to your fork
5. **Create** a Pull Request with:
   - Clear title describing the change
   - Detailed description of what was changed and why
   - Reference to any related issues
6. **Wait** for review and address any feedback

## Issue Templates

We use GitHub issue templates to ensure consistent and complete bug reports and feature requests. When creating an issue, please use the appropriate template:

- **Bug Report**: For reporting bugs and unexpected behavior
- **Feature Request**: For proposing new features or enhancements
- **Documentation**: For documentation improvements or corrections

## Reporting Issues

When reporting bugs or requesting features:

- Use the GitHub issue tracker
- Provide clear steps to reproduce
- Include relevant code samples
- Specify your Python version and OS

## License

By contributing to Codex Aura, you agree that your contributions will be licensed under the Apache License 2.0.