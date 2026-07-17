FROM ghcr.io/astral-sh/uv:0.7-python3.13-bookworm-slim AS builder

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY src/ src/
COPY pyproject.toml uv.lock README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.13-slim-bookworm

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY src/ src/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

VOLUME /app/data

EXPOSE 8000

CMD ["granian", "--interface", "asgi", "colorink.main:app", "--host", "0.0.0.0", "--port", "8000"]
