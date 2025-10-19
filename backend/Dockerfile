# OpenAI-First Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install poetry
RUN pip install poetry==1.7.1

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev dependencies)
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY app/ ./app/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
