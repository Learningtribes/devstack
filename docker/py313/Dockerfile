ARG PYTHON_IMAGE=python:3.13-slim-bookworm

FROM ${PYTHON_IMAGE} AS apt-base
ARG DEBIAN_MIRROR=http://deb.debian.org/debian
ARG DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
RUN sed -i \
        -e "s|http://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
        -e "s|http://deb.debian.org/debian\$|${DEBIAN_MIRROR}|g" \
        -e "s|http://deb.debian.org/debian |${DEBIAN_MIRROR} |g" \
        /etc/apt/sources.list.d/debian.sources

FROM apt-base AS build-base
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential pkg-config git curl ca-certificates xz-utils \
        default-libmysqlclient-dev \
        libldap2-dev libsasl2-dev \
        libgeos-dev \
        libxml2-dev libxslt1-dev libxmlsec1-dev \
        libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

FROM build-base AS wheels
COPY requirements-infra.txt requirements-native-probe.txt /tmp/
RUN pip wheel --wheel-dir /wheels -r /tmp/requirements-infra.txt -r /tmp/requirements-native-probe.txt

FROM build-base AS node
ARG NODE_VERSION=16.20.2
ARG NODE_DIST_URL=https://nodejs.org/dist
ARG TARGETARCH
RUN case "${TARGETARCH:-$(dpkg --print-architecture)}" in \
        arm64) NODE_ARCH=arm64 ;; \
        amd64) NODE_ARCH=x64 ;; \
        *) echo "unsupported arch" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "${NODE_DIST_URL}/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${NODE_ARCH}.tar.xz" \
        | tar -xJ -C /usr/local --strip-components=1

FROM apt-base AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates \
        libmariadb3 \
        libldap-2.5-0 libsasl2-2 \
        libgeos-c1v5 \
        libxml2 libxslt1.1 libxmlsec1 libxmlsec1-openssl \
        libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm
COPY --from=wheels /wheels /wheels
COPY requirements-infra.txt requirements-native-probe.txt /tmp/
RUN pip install --no-index --find-links /wheels -r /tmp/requirements-infra.txt -r /tmp/requirements-native-probe.txt \
    && rm -rf /wheels
WORKDIR /edx/app/edxapp/edx-platform
