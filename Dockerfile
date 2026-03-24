FROM python:3.12-slim

LABEL maintainer="DataSpoc <dev@dataspoc.com>"
LABEL description="DataSpoc Pipe — Data ingestion engine. Singer + Parquet + Bucket."

# System deps (cron + flock for scheduling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    util-linux \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy project
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/

# Install dataspoc-pipe with all cloud extras (s3, gcs, azure)
RUN uv pip install --system -e ".[s3,gcs,azure]"

# Initialize config structure
RUN dataspoc-pipe init

# Local lake directory for dev/testing
RUN mkdir -p /lake

# To install Singer taps, run:
#   docker exec dataspoc-pipe uv pip install --system <tap-name>
# Example:
#   docker exec dataspoc-pipe uv pip install --system pipelinewise-tap-postgres

# Volumes for user configs and local lake
VOLUME ["/root/.dataspoc-pipe", "/lake"]

ENTRYPOINT ["dataspoc-pipe"]
CMD ["--help"]
