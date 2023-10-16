FROM alpine:3.16

MAINTAINER TeskaLabs Ltd (support@teskalabs.com)
USER root
ENV LANG C.UTF-8

RUN set -ex \
  && apk update \
  && apk upgrade

RUN apk add --no-cache \
  python3 \
  py3-pip \
  libgit2 \
  freetype

RUN apk add --no-cache --virtual .buildenv python3-dev gcc musl-dev git libgit2-dev freetype-dev

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
