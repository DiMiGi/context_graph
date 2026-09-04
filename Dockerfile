FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ /app/server/
COPY web/ /app/web/

ENV PYTHONPATH=/app/server
ENV DATA_PATH=/data/projects
ENV PORT=8899
ENV HOST=0.0.0.0
ENV OMP_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV OMP_WAIT_POLICY=PASSIVE

EXPOSE 8899

CMD ["python", "server/app/main.py"]
