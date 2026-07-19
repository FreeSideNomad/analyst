# analyst — single self-contained image: FastAPI + DuckDB engine + built web UI.
#
#   docker run -p 8000:8000 -v analyst-data:/data ghcr.io/freesidenomad/analyst
#
# Everything runs in this one container; your data stays in the /data volume.
# LLM features (NL Q&A, live cataloguing) activate when ANTHROPIC_API_KEY is
# set — raw bulk data still never leaves the box (only schema/profiles/capped
# samples/small results cross to the model). See the user manual.

# ── 1. frontend build ────────────────────────────────────────────────
FROM oven/bun:1 AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/bun.lock* ./
RUN bun install --frozen-lockfile || bun install
COPY frontend/ ./
RUN bun run build

# ── 2. python runtime ────────────────────────────────────────────────
FROM python:3.14-slim AS runtime
# Node.js powers the Claude Agent SDK (live LLM mode); harmless when unused.
# libgomp1 is LightGBM's OpenMP runtime (feature 012 model training).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg libgomp1 \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get purge -y gnupg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
# Project layout is src/ — install deps first (cached layer), code second.
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ src/
COPY README.md ./
RUN uv sync --frozen --no-dev

COPY --from=web /app/frontend/dist /app/web

ENV ANALYST_DATA_DIR=/data \
    ANALYST_WEB_DIST=/app/web \
    PATH="/app/.venv/bin:$PATH"
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "analyst.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# ML variant (feature 018): + the CPU torch stack for relational graph
# models. Build with `--target ml` (tag analyst:ml). linux/amd64 only —
# pyg-lib publishes no linux/arm64 wheel; Apple-Silicon Docker runs it
# under Rosetta emulation.
FROM runtime AS ml
RUN uv sync --frozen --no-dev --extra ml

# Default (last) target stays the lean runtime image.
FROM runtime
