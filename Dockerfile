# ── Stage 1: Builder ──────────────────────────────────────────────────────────
# Installs dependencies into an isolated venv. This stage is discarded after
# the build — its pip cache, build tools, and wheel artifacts never reach prod.
FROM python:3.12-slim AS builder

WORKDIR /app

# Create a venv so we can copy it cleanly into the runtime stage
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
# Minimal image: only the venv and application code, no pip, no build tools.
FROM python:3.12-slim AS runtime

WORKDIR /app

# Non-root user for least-privilege execution
RUN adduser --disabled-password --no-create-home ghostnote

# Copy only the pre-built venv from the builder stage
COPY --from=builder /app/venv /app/venv

# Copy application code
COPY app/ ./app/

# Hand ownership to the non-root user
RUN chown -R ghostnote:ghostnote /app

USER ghostnote

ENV PATH="/app/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
