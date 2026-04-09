# Use a lightweight Python base image
FROM python:3.13-slim

# Install uv for high-speed dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration and dependency files
COPY pyproject.toml uv.lock ./

# Install project dependencies
RUN uv sync --frozen --no-cache

# Copy the application code
COPY . .

# Copy and prepare entrypoint script
COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose the FastAPI port
EXPOSE 8000

# Set the environment variable to ensure logs are shown immediately
ENV PYTHONUNBUFFERED=1

# Use the entrypoint script to handle Kubeconfig patching
ENTRYPOINT ["docker-entrypoint.sh"]

# Default command to run the server
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
