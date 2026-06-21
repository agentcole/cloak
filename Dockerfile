# cloak round-trip masking proxy.
#
#   docker build -t cloak .
#   docker run -p 8788:8788 -e CLOAK_PROXY_UPSTREAM=https://api.openai.com cloak
#
# Then point your client's base URL at http://localhost:8788/v1
FROM python:3.12-slim

WORKDIR /app

# Project metadata + source (README/LICENSE are required by the build backend).
COPY pyproject.toml README.md LICENSE ./
COPY src ./src

# Core is dependency-free; install the lightweight proxy + phone extras. Add
# "ner" here too if you want local NER (pulls a much larger image).
RUN pip install --no-cache-dir ".[proxy,phone]"

# Run unprivileged.
RUN useradd --create-home --uid 10001 cloak
USER cloak

ENV CLOAK_PROXY_PORT=8788 \
    CLOAK_PROXY_UPSTREAM=https://api.openai.com \
    CLOAK_PROXY_DETECTORS=regex \
    CLOAK_PROXY_STRATEGY=placeholder

EXPOSE 8788

# Shell form so the env vars expand at runtime.
CMD cloak proxy \
    --host 0.0.0.0 \
    --port "$CLOAK_PROXY_PORT" \
    --upstream "$CLOAK_PROXY_UPSTREAM" \
    --detectors "$CLOAK_PROXY_DETECTORS" \
    --strategy "$CLOAK_PROXY_STRATEGY"
