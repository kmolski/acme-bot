FROM debian:stable

ENV DISCORD_TOKEN ""
ENV DIR /tmp/acme-bot

RUN mkdir -p ${DIR}
WORKDIR ${DIR}

ENV BUILD_DEPS libffi-dev python3-dev python3-wheel
ENV DEPS ffmpeg grep python3 python3-pip python3-setuptools units

COPY requirements.txt ${DIR}/

RUN apt-get update \
    && apt-get install -y --no-install-recommends ${BUILD_DEPS} ${DEPS} \
    && pip3 install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove ${BUILD_DEPS} \
    && apt-get clean \
    && rm -rf -- /var/lib/apt/lists/*

COPY setup.py ${DIR}/
COPY acme_bot ${DIR}/acme_bot

RUN pip3 install --no-cache-dir ${DIR}

ENTRYPOINT ["acme-bot"]
