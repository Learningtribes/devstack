# The probe is currently measured on the Linux ARM64 builder. Pin the
# architecture-specific manifest so a rebuild cannot silently move to a new
# Python 3.6 base image.
FROM python:3.6-slim@sha256:ac11ce85a603a835533b2ec608246fef2fea4a4b4790df97a20d9cce7032faf6

LABEL description="Open edX Hawthorn Py3.6 migration image — Django 1.11 + celery 3.1"
LABEL maintainer="Learning Tribes"

# System dependencies (apt works via devstack_default network)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git gcc g++ make \
    default-libmysqlclient-dev \
    libgeos-dev libgeos-c1v5 \
    libldap2-dev libsasl2-dev \
    libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev \
    libgraphviz-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /edx/app/edxapp/edx-platform

# uv 0.1.44 is the probe toolchain selected for the Python 3.6 image.
# The release archive is architecture-specific and verified before install.
ADD https://github.com/astral-sh/uv/releases/download/0.1.44/uv-aarch64-unknown-linux-gnu.tar.gz /tmp/uv.tar.gz
RUN echo "afb7039f033546d55730dae38a106dd56b358117a565a42bf3ebda9c48db53c6  /tmp/uv.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/uv.tar.gz -C /tmp \
    && install -m 0755 /tmp/uv-aarch64-unknown-linux-gnu/uv /usr/local/bin/uv \
    && rm -rf /tmp/uv.tar.gz /tmp/uv-aarch64-unknown-linux-gnu \
    && uv --version

# 1. PyPI packages
COPY py36-base.txt py36-constraints.txt py36-git-requirements.txt /tmp/
RUN pip install --no-cache-dir --constraint /tmp/py36-constraints.txt \
        "pip==20.3.4" "setuptools==44.1.1" "wheel==0.34.2" \
    && pip install --no-cache-dir --constraint /tmp/py36-constraints.txt \
        -r /tmp/py36-base.txt

# 2. Git-only packages and LT vendored XBlocks
# All exact source identities are maintained in the requirements file; their
# dependencies are resolved through the same complete constraints set.
# xblock-utils requires future, not the stale Python 2-only futures package;
# future==1.0.0 is installed from py36-base.txt under these constraints.
RUN pip install --no-cache-dir --constraint /tmp/py36-constraints.txt \
    -r /tmp/py36-git-requirements.txt

# Verify. uv is retained in the image, but no released uv runner can execute
# Python 3.6; use the image interpreter directly for this smoke check.
RUN uv --version \
    && /usr/local/bin/python -c "\
import django; print('Django', django.VERSION); \
import celery; print('celery', celery.VERSION); \
import pymongo; print('pymongo', pymongo.version); \
import importlib; importlib.import_module('kombu.async'); print('kombu.async OK'); \
import MySQLdb; print('mysqlclient OK'); \
print('Image build OK')"

CMD ["python3"]
