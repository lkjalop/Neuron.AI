###########################
# Production Hardened Image
# Multi-stage build: builder (installs deps) -> runtime (copy only needed artifacts)
# Notes:
#  - Pin Python minor version for reproducibility.
#  - Use non-root numeric UID/GID (10001) for runtime.
#  - Leverage wheels cache layer separation for faster rebuilds.
#  - Avoid copying tests, docs (optional) into final runtime image to slim attack surface.
#  - Set read-only root FS suggestion (can be enforced via runtime/orchestrator).
###########################

FROM python:3.11-slim AS builder
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=off PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# System build deps (only in builder) – add as needed (e.g., build-essential, git)
RUN apt-get update \
	&& apt-get install -y --no-install-recommends build-essential curl \
	&& rm -rf /var/lib/apt/lists/*

# Requirements separate copy to maximize caching
COPY requirements.txt ./
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# Copy source (only after deps to preserve cache)
COPY src ./src
COPY docs ./docs

###########################
# Runtime stage
###########################
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Create non-root user with deterministic UID/GID
RUN groupadd -g 10001 neuron \
	&& useradd -u 10001 -g neuron -m -s /usr/sbin/nologin neuron

# Copy wheels from builder then install (no build tools needed now)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
	&& rm -rf /wheels

# Copy only runtime-relevant directories
COPY --from=builder /app/src ./src
# Optionally include minimal docs or API spec; leaving docs out reduces size
COPY artifacts/openapi.json ./artifacts/openapi.json

# Drop privileges
USER neuron:neuron

EXPOSE 8000

# Healthcheck (FastAPI /livez endpoint could be added later). Using TCP check placeholder.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1',8000)); s.close()" || exit 1

# Command
CMD ["python", "-m", "uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000", "--factory"]

# Security Hardening Tips (operational):
#  - Consider read-only root filesystem (Kubernetes: securityContext.readOnlyRootFilesystem: true)
#  - Add seccomp/apparmor profiles & drop Linux capabilities (compose/k8s manifests).
#  - Validate SBOM (artifacts) before deployment.
