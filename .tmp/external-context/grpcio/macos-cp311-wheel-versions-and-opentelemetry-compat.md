---
source: PyPI JSON API
library: grpcio + opentelemetry-exporter-otlp-proto-grpc
package: grpcio
topic: macOS CPython 3.11 wheel coverage and transitive pin compatibility
fetched: 2026-02-18T00:00:00Z
official_docs: https://pypi.org/project/grpcio/ ; https://pypi.org/project/opentelemetry-exporter-otlp-proto-grpc/
---

Relevant wheel/dependency facts for macOS Python 3.11:

1) grpcio `1.78.0`
- Wheel present for CPython 3.11 macOS:
  - `grpcio-1.78.0-cp311-cp311-macosx_11_0_universal2.whl`

2) grpcio `1.76.0` and `1.75.1`
- CPython 3.11 macOS wheels also use:
  - `macosx_11_0_universal2`

3) grpcio `1.63.2`
- CPython 3.11 macOS wheel:
  - `grpcio-1.63.2-cp311-cp311-macosx_10_9_universal2.whl`
- This is a lower deployment target than 1.75+ / 1.78.0.

4) grpcio `1.62.2`
- CPython 3.11 macOS wheel:
  - `grpcio-1.62.2-cp311-cp311-macosx_10_10_universal2.whl`

5) grpcio `1.58.0`
- CPython 3.11 macOS wheel:
  - `grpcio-1.58.0-cp311-cp311-macosx_10_10_universal2.whl`

6) Transitive constraint (OpenTelemetry exporter)
- `opentelemetry-exporter-otlp-proto-grpc==1.38.0` declares:
  - `grpcio<2.0.0,>=1.63.2` for Python `<3.13`
  - `grpcio<2.0.0,>=1.66.2` for Python `>=3.13`

Implication for Python 3.11:
- Pinning `grpcio==1.63.2` satisfies the current OpenTelemetry exporter lower bound and gives a lower macOS deployment target wheel.

Practical pyproject pin pattern:

```toml
[project]
dependencies = [
  "opentelemetry-exporter-otlp-proto-grpc>=1.38.0",
  "grpcio==1.63.2",
]
```

If source-build fallback still appears, force wheel-only install path in CI/dev bootstrap.
