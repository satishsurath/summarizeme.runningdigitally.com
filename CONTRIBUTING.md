# Contributing to SummarizeMe

Thank you for your interest in contributing to SummarizeMe! This document
provides guidelines and instructions for contributing.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
By participating, you are expected to uphold this code.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/runningdigitally/summarizeme.runningdigitally.com.git
   cd summarizeme.runningdigitally.com
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your local values
   ```

5. **Run the development server:**
   ```bash
   docker compose -f docker-compose.dev.yml up -d
   ```

6. **Run tests:**
   ```bash
   .venv/bin/ruff check . && .venv/bin/ruff format .
   .venv/bin/pytest tests/ -q
   ```

## Pull Request Process

1. **Create a feature branch** from `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the coding standards:
   - Use `ruff` for linting and formatting
   - Add tests for new functionality
   - Update documentation as needed

3. **Run all checks before submitting:**
   ```bash
   .venv/bin/ruff check . && .venv/bin/ruff format .
   .venv/bin/pytest tests/ -q
   ```

4. **Commit your changes** with clear, descriptive messages:
   ```bash
   git add .
   git commit -m "feat: add support for youtu.be URLs"
   ```

5. **Push and open a Pull Request:**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Code review:**
   - All PRs require review before merging
   - PRs must pass CI checks (ruff, pytest, Docker build)
   - Address all review comments
   - Squash-merge to main with a descriptive subject line

## Coding Standards

- **Python 3.12+** compatible code only
- **ruff** for linting and formatting (configured in `pyproject.toml`)
- **Type hints** encouraged but not required (pyright `basic` mode)
- **Structured logging** via `shared_logger` from `app_config.py`
- **No print() statements** in application code (CLI scripts OK)
- **Specific exception handling** — no bare `except Exception`
- **Blueprints** for route organization (`blueprints/` directory)

## Testing

- **Unit tests:** `tests/unit/` — isolated behavior tests
- **Integration tests:** `tests/integration/` — route/database contracts
- **Run all tests:** `.venv/bin/pytest tests/ -q`
- **Run specific test:** `.venv/bin/pytest tests/integration/test_endpoints.py -v`

## Documentation

- Update `README.md` for user-facing changes
- Add docstrings to new public functions
- Update `CHANGELOG.md` with a brief description of changes
- Add architecture docs to `docs/` for significant changes

## Reporting Issues

1. Search existing issues to avoid duplicates
2. Use the issue template (if available)
3. Include:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Environment details (OS, Python version, Docker version)
   - Relevant logs or error messages

## Security

If you discover a security vulnerability, please:
1. **Do NOT open a public issue**
2. Email security@runningdigitally.com with details
3. Do not disclose the vulnerability publicly until it is fixed

See [SECURITY.md](SECURITY.md) for more details.

## License

By contributing, you agree that your contributions will be licensed under
the project's MIT License. See [LICENSE](LICENSE) for details.
