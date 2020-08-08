FROM alpine:latest

ENV DISCORD_TOKEN ""
ENV DIR /tmp/acme-bot

RUN mkdir -p ${DIR}
WORKDIR ${DIR}

ENV BUILD_DEPS gcc libffi-dev make musl-dev python3-dev
ENV DEPS ffmpeg grep python3 py3-pip py3-wheel units

COPY requirements.txt ${DIR}/

RUN apk add --no-cache ${BUILD_DEPS} ${DEPS} \
    && pip3 install --no-cache-dir -r requirements.txt \
    && apk del ${BUILD_DEPS}

COPY setup.py ${DIR}/
COPY acme_bot ${DIR}/acme_bot

RUN pip3 install --no-cache-dir ${DIR}

ENTRYPOINT ["acme-bot"]
