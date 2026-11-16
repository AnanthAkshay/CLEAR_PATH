# Contributing to ClearPath-lite

Thank you for contributing to ClearPath-lite! This document outlines guidelines for development, code styling, running tests, and submitting changes.

## Development Workflow

### 1. Environment Setup
Follow the instructions in [docs/SETUP.md](docs/SETUP.md) to initialize your Python virtual environment and install dependencies:
```bash
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# Linux/macOS: source venv/bin/activate
pip install -r requirements.txt
```

### 2. Code Style & Standards
- **Python Version:** Compatible with Python 3.10 through 3.14.
- **Type Annotations:** All function signatures and class definitions must include type hints (`from __future__ import annotations`).
- **Formatting:** Keep line lengths readable and adhere to PEP 8 standards.
- **Docstrings:** Use Google-style docstrings for public classes, functions, and modules.

### 3. Testing Requirements
Before committing or submitting a pull request, run the automated test suite and ensure all tests pass:
```bash
make test
# Or:
python -m pytest -q
```
All 114 tests must pass. If adding new features, include unit tests in the appropriate `tests/test_*.py` file. See [docs/TESTING.md](docs/TESTING.md) for testing guidelines and property-based invariant requirements.

### 4. Branching & Pull Request Process
1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make atomic, well-documented commits describing what was changed and why.
3. Verify simulation benchmarks remain green:
   ```bash
   python -m clearpath.scenarios.run_all
   ```
4. Push your branch and open a Pull Request against `main`. Ensure all checks pass and summarize the changes made.

