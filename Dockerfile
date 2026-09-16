# Faculty / demo image for Vremio (Django + Gunicorn).
# Production salon on Railway does not use this file.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY backend/ /app/
COPY infra/docker/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

# collectstatic needs a dummy secret; DJANGO_BUILD skips production DB checks.
ENV DJANGO_BUILD=1 \
    DJANGO_SECRET_KEY=build-time-only-not-used-at-runtime \
    DJANGO_DEBUG=False
RUN python manage.py collectstatic --noinput

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD curl -fsS http://127.0.0.1:8000/health/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
