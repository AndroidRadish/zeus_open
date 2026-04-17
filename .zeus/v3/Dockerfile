# ZeusOpen v3 production image
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (git for worktree backend)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy v3 scripts
COPY .zeus/v3/scripts /app/.zeus/v3/scripts

# Ensure project root config exists at runtime
COPY .zeus/v3/config.json /app/.zeus/v3/config.json

# Entrypoint for auto-start initialization
COPY .zeus/v3/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENV PYTHONPATH=/app/.zeus/v3/scripts
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["--mode", "combined", "--project-root", "/app"]
