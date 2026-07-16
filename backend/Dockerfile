# Backend AgentFlow Studio — FastAPI (MVP)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY pyproject.toml ./

# Frontend estático (build de produção do Vite) servido em same-origin pela
# raiz do FastAPI (sem CORS no Conductor). STATIC_DIR aponta para este path.
COPY frontend_dist ./frontend/dist

ENV STATIC_DIR=/app/frontend/dist

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
