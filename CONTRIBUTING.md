# Contributing to ics-tools

## Setup and checks

Use Python 3.10 or later. From a checkout, install development tools:

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy src
python -m pytest -q
python examples/demo.py
python -m build
python -m twine check dist/*
```

The editable install uses Hatchling. A network-restricted environment needs the build backend
and development dependencies provisioned beforehand. Do not skip quality gates to release.
Tests use synthetic data without network access; pytest's optional cache plugin is disabled
so the suite also runs in restricted workspaces. CI checks Python 3.10–3.13 on Linux and Windows.
Keep runtime dependencies empty, public APIs compatible, and both README languages aligned.
Use Conventional Commits (`fix:`, `feat:`, `docs:`, `test:`, `ci:`, `chore:`).
Add a regression test that fails before fixing a defect.

## Releasing (maintainer only)

1. Update the Unreleased section of CHANGELOG.md and choose a SemVer version. Breaking changes
   during 0.x increment the minor version.
2. Update both `pyproject.toml` and `src/ics_tools/__init__.py`; run all checks above.
3. Review the built wheel and sdist, including `py.typed`, and run `twine check` as the dry run.
4. Commit with `chore(release): vX.Y.Z`, then create the matching `vX.Y.Z` tag.
5. After release approval, push the tag. This triggers `publish.yml`, which verifies the tag,
   reruns checks, builds artifacts, and publishes them through PyPI trusted publishing.

Configure a [PyPI trusted publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
(or pending publisher for the first release) with owner `YusufBeratZengin`, repository `ics-tools`,
workflow `publish.yml`, and environment `pypi`. Configure that GitHub environment's protection rules.
No stored API credential is required. External publisher/environment configuration is a maintainer step;
adding the workflow does not configure those services or publish a release.
