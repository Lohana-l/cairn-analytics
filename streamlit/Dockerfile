FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libpq-dev : psycopg2-binary runtime
# curl      : healthcheck (docker-compose)
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

COPY streamlit/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# L'image doit être autonome : en compose, le volume mount .:/app écrase
# ces COPY, mais un build standalone (docker run sans volume) doit fonctionner.
COPY app.py      .
COPY .streamlit  ./.streamlit
COPY pages       ./pages
COPY data        ./data
COPY ui          ./ui
COPY ingestion   ./ingestion

EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.port", "8501", \
     "--server.address", "0.0.0.0"]
