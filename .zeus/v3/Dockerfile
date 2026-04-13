# ZeusOpen v3 production image
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (git for worktree backend)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy requirements if they exist; otherwise install common deps
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy v3 scripts
COPY scripts /app/.zeus/v3/scripts

# Ensure project root config exists at runtime
COPY config.json /app/.zeus/v3/config.json

ENV PYTHONPATH=/app/.zeus/v3/scripts
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Default entrypoint allows overriding command
ENTRYPOINT ["python", "/app/.zeus/v3/scripts/run.py"]
CMD ["--mode", "combined", "--project-root", "/app"]
