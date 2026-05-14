FROM python:3.11.12-slim

WORKDIR /app

# Non-root user for security
RUN addgroup --system filtrant && adduser --system --ingroup filtrant --uid 1000 filtrant

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-create data dirs and set ownership before switching user
RUN mkdir -p data/incoming_cvs data/processed_cvs data/failed_cvs ml \
    && chown -R filtrant:filtrant /app

USER filtrant

EXPOSE 8000

# 2 uvicorn workers behind gunicorn; timeout matches LLM call duration
CMD ["gunicorn", "src.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
