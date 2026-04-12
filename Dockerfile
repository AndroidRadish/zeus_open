# ZeusOpen v2 Backend Dockerfile
# Packages the FastAPI backend + v2 orchestrator scripts into a runnable container.

FROM python:3.11-slim

LABEL maintainer="zeus-open"
LABEL description="ZeusOpen v2 multi-agent orchestration backend"

# Install system dependencies (git for workspace bootstrapping, graphviz for SVG rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the entire project
COPY . /app

# Expose the default v2 server port
EXPOSE 8234

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8234/status')" || exit 1

# Default: start the v2 backend on 0.0.0.0:8234
CMD ["python", ".zeus/v2/scripts/zeus_server.py", "--host", "0.0.0.0", "--port", "8234"]
