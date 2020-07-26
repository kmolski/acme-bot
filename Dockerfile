FROM alpine

ENV DISCORD_TOKEN ""

ENV DIR /tmp/acme-bot
RUN mkdir -p ${DIR}

ENV BUILD_DEPS gcc libffi-dev make musl-dev python3-dev
ENV DEPS ffmpeg python3

RUN apk --update add --no-cache ${BUILD_DEPS} ${DEPS}

WORKDIR ${DIR}
COPY requirements.txt ${DIR}/

RUN pip3 install -r requirements.txt

COPY setup.py ${DIR}
COPY acme_bot ${DIR}/acme_bot

RUN pip3 install ${DIR}

RUN apk del ${BUILD_DEPS}

ENTRYPOINT ["acme-bot"]
