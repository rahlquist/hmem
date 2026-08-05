# hermes-benchmark: pinned reproducible benchmark image
#
# Pins hermes-agent at f5be9236 and hmem at 37a2581 so benchmark runs
# are fully deterministic and reproducible. No runtime changes to
# existing code — this image only packages the two repos at their
# pinned commits plus the hmem pilot harness.
#
# Build:
#   docker build -t hermes-benchmark:latest \
#     -f docker/benchmark/Dockerfile \
#     /home/rahlquist/hmem
#
# Run:
#   docker run --rm hermes-benchmark:latest
#   docker run --rm hermes-benchmark:latest python3 -m pilot.cli --validate-only
#   docker run --rm hermes-benchmark:latest python3 -m pilot.cli --out-dir /tmp/out --repetitions 3 --seed 7

FROM debian:13.4-slim AS base

ARG HERMES_COMMIT=f5be9236e00ddf2f2a412697f267078fc4ee068e
ARG HMEM_COMMIT=37a258108a5c20b18cac2ed6ca35d96c39933004

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive

# ---------------------------------------------------------------------------
# Stage 1: clone both repos at their pinned commits
# ---------------------------------------------------------------------------
FROM base AS source

RUN apt-get -o Acquire::Retries=3 update && \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        ca-certificates git && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Clone hermes-agent at pinned commit
RUN git clone --no-checkout https://github.com/NousResearch/hermes-agent.git hermes-agent && \
    cd hermes-agent && \
    git checkout ${HERMES_COMMIT}

# hmem is local — copy from build context (already at 37a2581 on main)
COPY . hmem


# ---------------------------------------------------------------------------
# Stage 2: runtime image with Python + hmem pilot
# ---------------------------------------------------------------------------
FROM base AS runtime

RUN apt-get -o Acquire::Retries=3 update && \
    apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        ca-certificates python3 python3-venv python3-pip git procps && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -d /home/benchmark -s /bin/bash benchmark

# Copy hermes-agent source (read-only reference)
COPY --from=source --chown=root:root /build/hermes-agent /opt/hermes-agent

# Copy hmem source (the repo at 37a2581)
COPY --from=source --chown=root:root /build/hmem /opt/hmem

# Write pinned commit metadata
RUN printf '%s\n' "${HERMES_COMMIT:-f5be9236e00ddf2f2a412697f267078fc4ee068e}" > /opt/hermes-agent/.pinned_commit && \
    printf '%s\n' "37a258108a5c20b18cac2ed6ca35d96c39933004" > /opt/hmem/.pinned_commit

WORKDIR /opt/hmem

# Verify the pilot harness works (no third-party deps required)
RUN python3 -c "import pilot; print(f'pilot v{pilot.PILOT_VERSION} OK')" && \
    python3 -m pilot.cli --validate-only

# Environment
ENV HERMES_AGENT_COMMIT=f5be9236e00ddf2f2a412697f267078fc4ee068e
ENV HMEM_COMMIT=37a258108a5c20b18cac2ed6ca35d96c39933004

USER benchmark

# Default: print build info + run validation
CMD ["python3", "-c", "import pilot, os; print(f'hermes-benchmark | hermes={os.environ[\"HERMES_AGENT_COMMIT\"][:8]} | hmem={os.environ[\"HMEM_COMMIT\"][:8]} | pilot v{pilot.PILOT_VERSION}'); print('hello-world: benchmark image is ready')"]
