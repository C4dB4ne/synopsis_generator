FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir \
    -r /app/requirements.txt

COPY src /app/src

COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY src /app/src

CMD ["python", "-m", "synopsis_mcp.server"]
