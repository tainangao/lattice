FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app

RUN pip install --no-cache-dir --upgrade pip uv

COPY --chown=user pyproject.toml uv.lock README.md /home/user/app/
COPY --chown=user lattice /home/user/app/lattice
COPY --chown=user data /home/user/app/data
COPY --chown=user main.py /home/user/app/main.py

RUN uv sync --frozen

EXPOSE 7860

CMD ["sh", "-lc", "uv run uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
