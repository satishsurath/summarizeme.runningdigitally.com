# Production Dockerfile — uses gunicorn
# Prevent .pyc files and ensure unbuffered stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for layer caching
# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (NEVER copy .env — secrets mounted at runtime)
COPY . /app
RUN chown -R appuser:appuser /app

# Expose the gunicorn port
# Create non-root user
RUN useradd --create-home appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
EXPOSE 8000

# Run gunicorn (production WSGI server)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300", "wsgi:app"]
