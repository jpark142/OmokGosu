# OmokGosu — multi-stage build for Fly.io / any Docker host.
#
# Stages:
#   1. python-build : compile C++ pybind module into a wheel
#   2. web-build    : compile React frontend with vite
#   3. runtime      : slim Python image with the wheel, server source, and dist

# ----- 1. C++ pybind11 module -----
FROM python:3.11-slim AS python-build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY VERSION CMakeLists.txt pyproject.toml ./
COPY cpp/ cpp/

RUN pip install --no-cache-dir scikit-build-core "pybind11>=2.12"
RUN pip install --no-cache-dir .

# ----- 2. React frontend -----
FROM node:20-slim AS web-build

WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ----- 3. Slim runtime -----
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Carry over the compiled omok_core wheel from stage 1.
COPY --from=python-build /usr/local/lib/python3.11/site-packages \
                         /usr/local/lib/python3.11/site-packages

# Server source + install (editable so changes inside the container can hot-reload
# if someone wants, though we ship --workers 1 without --reload in prod).
COPY server/ /app/server/
RUN pip install --no-cache-dir -e /app/server

# Frontend bundle, served by FastAPI via static.py.
COPY --from=web-build /web/dist /app/web/dist

# Persistent SQLite. Fly volume is mounted at /data; OMOK_DB_PATH points there.
ENV OMOK_DB_PATH=/data/omok.sqlite
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "omok_server.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
