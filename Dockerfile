# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEPLOYMENT_MODE=demo \
    DEMO_DATA_DIR=/tmp/research-assistant-demo \
    PORT=10000 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    MPLCONFIGDIR=/tmp/research-assistant-mpl

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system workbench \
    && useradd --system --gid workbench --home-dir /app workbench

WORKDIR /app
COPY requirements.lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements.lock.txt

COPY --chown=workbench:workbench backend/app/ ./backend/app/
COPY --chown=workbench:workbench samples/ ./samples/
COPY --chown=workbench:workbench scripts/start_demo.py ./scripts/start_demo.py
COPY --from=frontend-build --chown=workbench:workbench /build/frontend/dist/ ./frontend/dist/

USER workbench
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '10000') + '/api/health', timeout=4).close()"
CMD ["python", "scripts/start_demo.py"]
