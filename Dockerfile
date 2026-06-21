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

# Copy Python deps
COPY --from=backend-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-deps /usr/local/bin /usr/local/bin

# Copy backend
COPY backend/ .

# Copy built frontend
COPY --from=frontend-build /frontend/dist ./frontend/dist

EXPOSE 8000
CMD ["python", "main.py"]
