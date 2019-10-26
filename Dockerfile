FROM alpine

ENV DISCORD_TOKEN ""

ENV DIR /tmp/acme-bot
RUN mkdir -p ${DIR}

ENV BUILD_DEPS gcc libffi-dev make musl-dev python3-dev
ENV DEPS ffmpeg python3

RUN apk update && apk add ${BUILD_DEPS} ${DEPS}

WORKDIR ${DIR}
COPY requirements.txt ${DIR}/

COPY setup.py ${DIR}
COPY acme_bot ${DIR}/acme_bot

RUN pip3 install -r requirements.txt

RUN apk del ${BUILD_DEPS}

ENTRYPOINT ["acme-bot"]
