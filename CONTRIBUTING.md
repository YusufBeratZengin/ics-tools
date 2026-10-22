# Contributing to ics-tools

Thank you for your interest in contributing to `ics-tools`.

## Development Setup

`ics-tools` has zero runtime dependencies and requires Python 3.10 or later.

1. Clone the repository:
   ```bash
   git clone https://github.com/YusufBeratZengin/ics-tools.git
   cd ics-tools
   ```

2. (Optional) Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install development dependencies or run tests directly using the Python standard library:
   ```bash
   # Using pytest:
   python -m pytest

   # Or using standard library unittest (zero extra packages needed):
   python -m unittest discover -s tests
   ```

## Guidelines

- **Zero runtime dependencies**: The core library and CLI must never depend on third-party runtime packages. Use the Python standard library (`zoneinfo`, `datetime`, `re`, `argparse`, `csv`, etc.).
- **RFC 5545 Compliance**: Keep line folding at 75 octets (UTF-8 bytes aware), CRLF line endings, and proper parameter quoting.
- **Commit Messages**: Follow [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat: ...`, `fix: ...`, `test: ...`, `docs: ...`).
- **Testing**: Add unit tests for every bug fix or new feature in the `tests/` directory. Ensure all tests pass across platforms.
- **Code Style**: Follow PEP 8 and include type annotations (`py.typed` is provided).
