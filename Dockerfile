FROM python:3.12-slim-bookworm

# WeasyPrint system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py navigation.py ./
COPY database/ database/
COPY reporting/ reporting/
COPY utils/ utils/
COPY views/ views/
COPY streamlit_pages/ streamlit_pages/
COPY templates/ templates/

# Persistent volumes
VOLUME ["/app/data", "/app/reports", "/app/certs"]

# Generate self-signed cert if none exists, then start app
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import ssl, urllib.request; urllib.request.urlopen('https://127.0.0.1:8443/_stcore/health', context=ssl._create_unverified_context(), timeout=3).read()"

ENTRYPOINT ["/docker-entrypoint.sh"]
