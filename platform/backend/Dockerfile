FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install --with-deps chromium

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
ENV HF_HUB_DISABLE_TELEMETRY=1 SEMANTIC_MODEL_CACHE=/opt/lecrown-models
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='/opt/lecrown-models', threads=2)"

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
