FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY backend/pyproject.toml backend/README.md ./backend/
RUN pip install --no-cache-dir ./backend

# Copy application code
COPY agent/       ./agent/
COPY prompts/     ./prompts/
COPY backend/app/ ./backend/app/
COPY backend/alembic.ini ./backend/
COPY backend/alembic/    ./backend/alembic/

ENV PYTHONPATH=/app:/app/backend

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
