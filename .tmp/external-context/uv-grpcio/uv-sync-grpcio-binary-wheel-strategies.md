---
source: Context7 API + PyPI JSON API
library: uv, pip, grpcio
package: uv-grpcio
topic: avoid grpcio source builds on macOS Python 3.11 with uv sync
fetched: 2026-02-18T00:00:00Z
official_docs: https://docs.astral.sh/uv/ ; https://pip.pypa.io/en/stable/ ; https://pypi.org/project/grpcio/1.78.0/
---

Relevant facts for this issue:

1) grpcio 1.78.0 has a macOS CPython 3.11 wheel on PyPI:
- `grpcio-1.78.0-cp311-cp311-macosx_11_0_universal2.whl`
- Source: PyPI release JSON for `grpcio==1.78.0`

2) uv supports pip-style binary controls:
- `--only-binary :all:` refuses source builds if no wheel exists
- `--no-binary` forces source (or source-preferred) behavior
- uv enforces `--only-binary` more strictly for direct URL deps than pip

3) pip/requirements global options support:
- `--only-binary`
- `--prefer-binary`
- `--no-binary`

4) uv build escape hatches:
- For known build-isolation breakage, use `uv pip install --no-build-isolation ...`
- Project-level package-specific control: `[tool.uv] no-build-isolation-package = ["..."]`

Practical command patterns:

```bash
# Fail fast if any dependency would need source build
uv pip install --only-binary :all: grpcio==1.78.0

# Prefer wheels globally when both sdist and wheel are possible
uv pip install --prefer-binary grpcio==1.78.0

# Sync from lockfile while refreshing resolver/cache state
uv sync --refresh --reinstall
```

Constraints strategy (when using requirements/constraints files):

```txt
--only-binary=:all:
--prefer-binary
grpcio==1.78.0
```

Use `--only-binary=:all:` in CI to catch unexpected source-build regressions early.
