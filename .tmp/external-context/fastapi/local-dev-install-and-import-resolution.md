---
source: Context7 API
library: FastAPI
package: fastapi
topic: local dev installation and import resolution
fetched: 2026-02-18
official_docs: https://fastapi.tiangolo.com/virtual-environments/
---

Relevant guidance for fixing `ModuleNotFoundError: No module named 'fastapi'` in local development:

- Use a virtual environment and install FastAPI into that environment (avoid global install confusion).
- Install FastAPI with standard extras when developing apps locally:

```bash
python -m pip install "fastapi[standard]"
```

- If you only install `fastapi` (without `[standard]`), some optional runtime pieces are not included.
- FastAPI docs emphasize virtual environments to avoid package mismatch between global/site Python installs.

Minimal setup pattern:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install "fastapi[standard]"
```
