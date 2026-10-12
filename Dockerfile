FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1

COPY pyproject.toml ./
RUN uv sync --no-install-project

COPY src ./src

CMD ["uv", "run", "python", "-m", "src.worker"]
