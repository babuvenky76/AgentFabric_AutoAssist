# Multi-stage build for AutoAssist
FROM python:3.11-slim as builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt


# Final stage
FROM python:3.11-slim

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Set environment variables
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV APP_NAME=AutoAssist

# Copy application code
COPY app/ ./app/
COPY observability/ ./observability/
COPY .env ./.env
COPY .env.example ./.env.example

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "-m", "app.main"]
