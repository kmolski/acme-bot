FROM python:3.10.2-bullseye AS base

WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

FROM base AS builder

ENV BUILD_DEPS="build-essential curl libffi-dev python3-dev"
RUN apt-get update \
    && apt-get install -y --no-install-recommends ${BUILD_DEPS}
RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev --no-root

COPY . .
RUN poetry build

FROM base AS final

ENV RUNTIME_DEPS="ffmpeg grep units"
RUN apt-get update \
    && apt-get install -y --no-install-recommends ${RUNTIME_DEPS} \
    && apt-get clean \
    && rm -rf -- /var/lib/apt/lists/*

COPY --from=builder /app/dist .
RUN pip install *.whl

ENTRYPOINT ["acme-bot"]
