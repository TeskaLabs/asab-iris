FROM pcr.teskalabs.com/alpine:3.18 AS building
MAINTAINER TeskaLabs Ltd (support@teskalabs.com)

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
    git \
    python3-dev \
    py3-pip \
    libffi-dev \
    openssl-dev \
    libgit2-dev \
    gcc \
    g++ \
    musl-dev \
    freetype-dev \
     cairo-dev

RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir pygit2==1.11 aiokafka aiosmtplib msal fastjsonschema
RUN pip3 install --no-cache-dir jinja2 markdown pyyaml xhtml2pdf git+https://github.com/TeskaLabs/asab.git@v25.25.01
RUN pip3 install --no-cache-dir sentry-sdk slack_sdk pytz

RUN mkdir -p /app/asab-iris

COPY . /app/asab-iris

FROM pcr.teskalabs.com/alpine:3.18 AS shiping

RUN apk add --no-cache \
  python3 \
  libgit2

COPY --from=building /usr/lib/python3.11/site-packages /usr/lib/python3.11/site-packages

COPY ./asabiris      /app/asab-iris/asabiris
COPY ./asab-iris.py  /app/asab-iris/asab-iris.py
COPY ./library  /app/asab-iris/library
COPY ./CHANGELOG.md     /app/asab-iris/CHANGELOG.md

RUN set -ex \
  && mkdir /conf \
  && touch conf/asab-iris.conf

WORKDIR /app/asab-iris
CMD ["python3", "asab-iris.py", "-c", "/conf/asab-iris.conf"]