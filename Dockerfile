# Production Dockerfile — uses gunicorn
FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (NEVER copy .env — secrets mounted at runtime)
COPY . /app

# Expose the gunicorn port
EXPOSE 8000

# Run gunicorn (production WSGI server)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "300", "wsgi:app"]
