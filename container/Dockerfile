# Multi-stage build for smaller, more secure image
FROM python:3.11-slim as builder

# Suppress debconf warnings
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage - distroless-like slim image
FROM python:3.11-slim

# Build arguments
ARG GIT_SHA=unknown
ARG APP_VERSION=dev

# Suppress debconf warnings
ENV DEBIAN_FRONTEND=noninteractive

# Create non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app && \
    chown -R appuser:appuser /app

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser app.py .
COPY --chown=appuser:appuser app_main.py .
COPY --chown=appuser:appuser prompt_protection.py .
COPY --chown=appuser:appuser file_security.py .
COPY --chown=appuser:appuser api.py .
COPY --chown=appuser:appuser start.sh .

# Make startup script executable
RUN chmod +x start.sh

# Set environment variables
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    STREAMLIT_SERVER_PORT=8000 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    GIT_SHA=${GIT_SHA} \
    APP_VERSION=${APP_VERSION} \
    API_ENABLED=false \
    API_PORT=8001

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8000 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/_stcore/health')" || exit 1

# Run startup script
CMD ["./start.sh"]
