# Image de l'API atelier de couture (Python 3.12.2)
FROM python:3.12.2-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dépendances d'abord : cette couche reste en cache tant que requirements.txt ne change pas.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Code de l'application et migrations
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY docker/entrypoint.sh /entrypoint.sh

# Exécution sans les droits root
RUN chmod +x /entrypoint.sh \
    && useradd --create-home --uid 1000 atelier \
    && chown -R atelier:atelier /app
USER atelier

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
