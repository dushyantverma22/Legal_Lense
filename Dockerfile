# Dockerfile

# ── Stage 1: dependency builder ───────────────────────────────────────────────
# Separate stage so pip install is isolated from source code changes.
# This is the layer-cache strategy in action:
# requirements.txt changes rarely → pip install layer is cached almost always.
# src/ changes constantly → only the COPY src/ layer rebuilds.

FROM python:3.11-slim AS builder

WORKDIR /app

# System deps needed by some Python packages (PyMuPDF needs libmupdf headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# CRITICAL: copy requirements BEFORE source code.
# This way, editing chunker.py does NOT invalidate the pip install cache.
COPY requirements.txt .

# Install all dependencies into a prefix we'll copy to the final stage.
# --no-cache-dir keeps the image smaller (no pip download cache stored).
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: production runtime ───────────────────────────────────────────────
# A fresh slim image that copies ONLY what's needed from the builder.
# Result: smaller final image (no build tools, no pip cache).

FROM python:3.11-slim AS production

WORKDIR /app

# Runtime system deps only (PyMuPDF needs these at runtime too)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source — this layer rebuilds on every code change (that's fine)
COPY src/       ./src/
COPY config/    ./config/
COPY tests/     ./tests/  
COPY frontend/ ./frontend/
COPY pytest.ini .

# Create the data directory that PDFs will be uploaded into.
# In production this is a mounted volume — this just ensures the path exists.
RUN mkdir -p data/raw data/eval

# CONCEPT: non-root user for security.
# Running as root inside a container means a container escape = root on the host.
# This creates a minimal user that only has access to /app.
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

# Document which port the app listens on (doesn't actually publish it — that's docker run -p)
EXPOSE 8000

# Health check: Docker will call this every 30s.
# If it fails 3 times, the container is marked unhealthy and restarted.
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" \
    || exit 1

# CONCEPT: CMD vs ENTRYPOINT.
# CMD is the default command — can be overridden by docker run args.
# Using JSON array form (exec form) means uvicorn gets signals directly,
# so Ctrl+C / SIGTERM causes graceful shutdown, not orphaned processes.
CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--timeout-graceful-shutdown", "30", \
     "--log-level", "info"]