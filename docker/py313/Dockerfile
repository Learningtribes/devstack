ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8
ARG BUILD_DEPS="build-essential pkg-config default-libmysqlclient-dev libldap2-dev libsasl2-dev libgeos-dev \
 libxml2-dev libxslt1-dev libxmlsec1-dev libjpeg-dev zlib1g-dev"

FROM ${PYTHON_IMAGE} AS apt-base
ARG DEBIAN_MIRROR=http://deb.debian.org/debian
ARG DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security
RUN sed -i \
        -e "s|http://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
        -e "s|http://deb.debian.org/debian\$|${DEBIAN_MIRROR}|g" \
        -e "s|http://deb.debian.org/debian |${DEBIAN_MIRROR} |g" \
        /etc/apt/sources.list.d/debian.sources

FROM apt-base AS build-base
ARG BUILD_DEPS
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
RUN apt-get update && apt-get install -y --no-install-recommends \
        ${BUILD_DEPS} git curl ca-certificates xz-utils \
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
ENV VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /opt/venv
# Bind mounts keep the 98MB wheel cache out of the image layers.
RUN --mount=type=bind,from=wheels,source=/wheels,target=/wheels \
    --mount=type=bind,source=requirements-infra.txt,target=/tmp/requirements-infra.txt \
    --mount=type=bind,source=requirements-native-probe.txt,target=/tmp/requirements-native-probe.txt \
    pip install --no-index --find-links /wheels -r /tmp/requirements-infra.txt -r /tmp/requirements-native-probe.txt
WORKDIR /edx/app/edxapp/edx-platform

# Runtime plus a compiler toolchain, for installing platform requirements that need sdists.
# /opt/venv is meant to be a named volume (see Makefile `shell`); PIP_INDEX_URL is passed at run time.
FROM runtime AS dev
ARG BUILD_DEPS
RUN apt-get update && apt-get install -y --no-install-recommends ${BUILD_DEPS} \
    && rm -rf /var/lib/apt/lists/*
