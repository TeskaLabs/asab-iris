FROM alpine:3.18 AS building
MAINTAINER TeskaLabs Ltd (support@teskalabs.com)
USER root

# Include build environment variables from GitLab CI/CD
ARG CI_COMMIT_BRANCH
ARG CI_COMMIT_TAG
ARG CI_COMMIT_REF_NAME
ARG CI_COMMIT_SHA
ARG CI_COMMIT_TIMESTAMP
ARG CI_JOB_ID
ARG CI_PIPELINE_CREATED_AT
ARG CI_RUNNER_ID
ARG CI_RUNNER_EXECUTABLE_ARCH
ARG GITHUB_HEAD_REF
ARG GITHUB_JOB
ARG GITHUB_SHA
ARG GITHUB_REPOSITORY

ENV LANG C.UTF-8

RUN set -ex \
  && apk update \
  && apk upgrade

RUN apk add --no-cache \
  python3 \
  py3-pip \
  libgit2 \
  freetype

RUN apk add --no-cache --virtual .buildenv python3-dev gcc musl-dev git libgit2-dev freetype-dev cairo-dev

RUN pip3 install sentry-sdk slack_sdk

RUN mkdir -p /opt/asab-iris
WORKDIR /opt/asab-iris
COPY requirements.txt /opt/asab-iris
COPY library /opt/asab-iris/library

# TODO: Install ASAB from pypy once it is released
RUN pip3 install git+https://github.com/TeskaLabs/asab.git
RUN pip3 install -r requirements.txt
RUN apk del .buildenv

COPY asabiris /opt/asab-iris/asabiris
COPY asab-iris.py /opt/asab-iris/asab-iris.py
COPY etc /conf
RUN chmod a+x /opt/asab-iris/asab-iris.py

CMD ["./asab-iris.py", "-c", "/conf/asab-iris.conf"]
