FROM python:3.11-slim AS backend-deps
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

COPY --from=backend-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-deps /usr/local/bin /usr/local/bin

COPY backend/ .

# Frontend dist lands at /frontend/dist — matches main.py's "../frontend/dist" relative to /app
COPY --from=frontend-build /frontend/dist /frontend/dist

VOLUME ["/data"]

ENV FB_DB_PATH=/data/flipperboards.db \
    FB_UPLOAD_DIR=/data/uploads \
    FB_HOST=0.0.0.0 \
    FB_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/screens')"

CMD ["python", "main.py"]
