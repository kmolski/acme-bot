FROM alpine

ENV DIR /opt/acme-bot

ENV BUILD_DEPS gcc make musl-dev
ENV DEPS ffmpeg libffi-dev python3-dev

RUN mkdir -p ${DIR}

COPY *.py ${DIR}/
COPY Pipfile ${DIR}/
# Do we need the line below?
COPY Pipfile.lock ${DIR}/

RUN apk update
RUN apk add ${BUILD_DEPS} ${DEPS}
RUN pip3 install pipenv

WORKDIR ${DIR}
RUN pipenv install --pre --deploy --system

RUN apk del ${BUILD_DEPS}

ENV DISCORD_TOKEN ""
ENTRYPOINT ["/opt/acme-bot/main.py"]