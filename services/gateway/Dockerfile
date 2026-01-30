# =============================================================================
# TRJM Gateway - Production Dockerfile
# =============================================================================
# Multi-stage build for optimized production image
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libldap2-dev \
    libsasl2-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Production image
# -----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS production

# Security: Create non-root user
RUN groupadd --gid 1000 trjm && \
    useradd --uid 1000 --gid trjm --shell /bin/bash --create-home trjm

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libldap-2.5-0 \
    libsasl2-2 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=trjm:trjm src/ ./src/
COPY --chown=trjm:trjm eval/ ./eval/

# Create necessary directories
RUN mkdir -p /data/uploads && chown -R trjm:trjm /data

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# Switch to non-root user
USER trjm

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
