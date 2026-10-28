# Build the TypeScript/Three.js frontend with Node.
FROM node:20-bookworm-slim AS frontend-build
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Serve the compiled UI and simulation API with Python.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY config/ config/
COPY --from=frontend-build /workspace/frontend/dist/ frontend/dist/
RUN mkdir -p /workspace/results && chown 10001:10001 /workspace/results
USER 10001:10001
EXPOSE 10000
CMD ["python", "backend/serve.py"]
