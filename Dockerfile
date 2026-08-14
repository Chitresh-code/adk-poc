# syntax=docker/dockerfile:1

FROM python:3.12-slim

WORKDIR /app

# Install uv package manager
RUN pip install uv

# Copy agents directory with project configuration
COPY agents/ agents/

# Install dependencies via uv (reads from pyproject.toml and uv.lock)
WORKDIR /app/agents
RUN uv sync --frozen --no-dev

# Expose port for the ADK API server
EXPOSE 8080

# Set environment to non-interactive
ENV PYTHONUNBUFFERED=1

# Default entrypoint: API server only, no bundled UI served here. The web/
# service builds and serves the branded frontend separately and proxies API
# calls to this container; --with_ui still registers the /dev/apps/*
# routes (agent graph, README-based suggested prompts) the frontend needs,
# it just doesn't expose ADK's own bundled UI anywhere reachable, since
# nothing proxies to /dev-ui/. --allow_origins is required even though web/
# proxies same-origin: ADK's own origin-check middleware compares the
# browser's Origin header against what it sees as its own scheme+host,
# which is the internal container address (adk-agents:8080) once behind a
# reverse proxy, not the externally-visible http://localhost:8080 the
# browser actually sent, so it has to be told explicitly.
CMD ["uv", "run", "--frozen", "adk", "api_server", ".", "--host", "0.0.0.0", "--port", "8080", "--with_ui", "--allow_origins=http://localhost:8080"]
