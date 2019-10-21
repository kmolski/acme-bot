FROM alpine

ENV DISCORD_TOKEN ""

ENV DIR /tmp/acme-bot
RUN mkdir -p ${DIR}/acme_bot

ENV BUILD_DEPS gcc libffi-dev make musl-dev python3-dev
ENV DEPS ffmpeg python3

RUN apk update && apk add ${BUILD_DEPS} ${DEPS}

WORKDIR ${DIR}
COPY requirements.txt ${DIR}/

RUN pip3 install -r requirements.txt

RUN apk del ${BUILD_DEPS}

COPY *.py ${DIR}/acme_bot
COPY music/*.py ${DIR}/acme_bot/music

RUN pip3 install {DIR}

ENTRYPOINT ["acme-bot"]
