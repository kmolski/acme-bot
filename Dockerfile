FROM python:3.13-slim-bookworm AS base

WORKDIR /app
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

FROM base AS builder

ENV BUILD_DEPS="build-essential curl git libffi-dev"
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ${BUILD_DEPS}
RUN pip install poetry
RUN python -m venv /venv

COPY pyproject.toml poetry.lock ./
RUN . /venv/bin/activate && poetry install --only main --no-root --all-extras

COPY ./ ./
RUN if [ ! -f dist/*.whl ]; then \
        . /venv/bin/activate && poetry build; \
    fi

FROM base AS final

LABEL org.opencontainers.image.title="acme-bot" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.authors="Krzysztof Molski" \
      org.opencontainers.image.source="https://github.com/kmolski/acme-bot"

ENV RUNTIME_DEPS="grep units"
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ${RUNTIME_DEPS} \
    && apt-get clean \
    && rm -rf -- /var/lib/apt/lists/*

COPY --from=builder /venv /venv
COPY --from=builder /app/dist .
RUN . /venv/bin/activate && pip install *.whl

COPY docker-entrypoint.sh /usr/local/bin/
ENTRYPOINT ["docker-entrypoint.sh"]
