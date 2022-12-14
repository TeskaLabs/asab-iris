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
  freetype

RUN apk add --no-cache --virtual .buildenv python3-dev gcc musl-dev git freetype-dev

RUN mkdir -p /opt/asab-iris
WORKDIR /opt/asab-iris
COPY requirements.txt /opt/asab-iris

# TODO: Install ASAB from pypy once it is released
RUN pip3 install git+https://github.com/TeskaLabs/asab.git@v22.06-rc2
RUN pip3 install -r requirements.txt
RUN pip3 install --no-cache-dir pygit2==1.9
RUN apk del .buildenv

COPY asabiris /opt/asab-iris/asabiris
COPY asab-iris.py /opt/asab-iris/asab-iris.py
COPY etc /conf
RUN chmod a+x /opt/asab-iris/asab-iris.py

CMD ["./asab-iris.py", "-c", "/conf/asab-iris.conf"]
