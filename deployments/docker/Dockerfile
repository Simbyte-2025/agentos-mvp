FROM python:3.11-slim

WORKDIR /app

# Seguridad básica: usuario no-root
RUN useradd -m appuser

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY agentos /app/agentos
COPY config /app/config

ENV AGENTOS_WORKSPACE_ROOT=/app

USER appuser

EXPOSE 8080

CMD ["uvicorn", "agentos.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
