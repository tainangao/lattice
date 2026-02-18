---
source: Context7 API
library: pip
package: pip
topic: editable installs with pyproject.toml (PEP 660) gotchas
fetched: 2026-02-18
official_docs: https://pip.pypa.io/en/stable/topics/local-project-installs/
---

Relevant pip guidance for local pyproject-based development installs:

- Recommended editable install command for a local project:

```bash
python -m pip install -e .
```

- For non-editable local install (closer to production behavior):

```bash
python -m pip install .
```

- Reinstall may be needed when project metadata changes (for editable installs).
- `pip install --editable` fallback to `setup.py develop` is deprecated when using old setuptools (63 or older).
- For modern editable installs with `pyproject.toml`, use a PEP 660-capable backend/toolchain (e.g., newer setuptools) and an up-to-date pip.

Minimal pyproject-focused local dev install pattern:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e .
```
