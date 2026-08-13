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

# Expose port for ADK web UI
EXPOSE 8080

# Set environment to non-interactive
ENV PYTHONUNBUFFERED=1

# Default entrypoint: run ADK web UI
CMD ["uv", "run", "adk", "web", ".", "--port", "8080"]
