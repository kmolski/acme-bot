FROM python:3.11-slim-bullseye AS base

WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update

FROM base AS builder

ENV BUILD_DEPS="build-essential curl git libffi-dev"
RUN apt-get install -y --no-install-recommends ${BUILD_DEPS}
RUN pip install poetry
RUN python -m venv /venv

COPY pyproject.toml poetry.lock ./
RUN . /venv/bin/activate && poetry install --only main --no-root --all-extras

COPY ./ ./
RUN . /venv/bin/activate && poetry build

FROM base AS final

ENV RUNTIME_DEPS="ffmpeg grep units"
RUN apt-get upgrade \
    && apt-get install -y --no-install-recommends ${RUNTIME_DEPS} \
    && apt-get clean \
    && rm -rf -- /var/lib/apt/lists/*

COPY --from=builder /venv /venv
COPY --from=builder /app/dist .
RUN . /venv/bin/activate && pip install *.whl

COPY docker-entrypoint.sh ./
ENTRYPOINT ["./docker-entrypoint.sh"]
