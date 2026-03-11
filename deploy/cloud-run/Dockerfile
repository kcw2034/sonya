FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY packages/sonya-core/ packages/sonya-core/
COPY packages/sonya-gateway/ packages/sonya-gateway/

RUN uv pip install --system \
    ./packages/sonya-core[all] \
    ./packages/sonya-gateway

ENV PORT=8080

EXPOSE ${PORT}

CMD uvicorn sonya.gateway.server:app \
    --host 0.0.0.0 \
    --port ${PORT}
