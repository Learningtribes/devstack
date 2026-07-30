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
    libxml2-dev libxslt-dev libxmlsec1-dev xmlsec1 pkg-config libjpeg-dev zlib1g-dev \
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
        "pip==20.3.4" "setuptools==44.1.1" "wheel==0.34.2"

# The published 1.5.3 wheel has an incorrect unconditional futures dependency.
# Build the verified official sdist with the locked R1 packaging toolchain.
ADD https://files.pythonhosted.org/packages/55/b0/64dca0c66160f3a2e5ded33e12fd57beb5e6bc1e67cd3b2d24c6506e0155/django-pipeline-1.5.3.tar.gz /tmp/django-pipeline-1.5.3.tar.gz
RUN echo "48e71c8b1781533adee64561cca20c9f17d40136211c2b32531e70ffe7fb0ced  /tmp/django-pipeline-1.5.3.tar.gz" | sha256sum -c - \
    && pip --version \
    && python -c "import setuptools, wheel; print('setuptools', setuptools.__version__); print('wheel', wheel.__version__)" \
    && pip install --no-cache-dir --no-index --find-links=/tmp --no-deps \
        "django-pipeline==1.5.3" \
    && rm -f /tmp/django-pipeline-1.5.3.tar.gz

# Resolve the complete base set normally with the already-pinned toolchain.
RUN pip install --no-cache-dir --constraint /tmp/py36-constraints.txt \
    -r /tmp/py36-base.txt

# 2. Git-only packages and LT vendored XBlocks
# All exact source identities are maintained in the requirements file; their
# dependencies are resolved through the same complete constraints set.
# xblock-utils requires future, not the stale Python 2-only futures package;
# future==1.0.0 is installed from py36-base.txt under these constraints.
RUN pip install --no-cache-dir --force-reinstall --constraint /tmp/py36-constraints.txt \
    -r /tmp/py36-git-requirements.txt

# Platform-owned Django apps and XModule descriptors are registered through
# separate setup.py entry points. Install only their package metadata and
# top-level package markers from the read-only Platform build context.
COPY --from=platform /setup.py /tmp/platform-metadata/setup.py
COPY --from=platform /cms/__init__.py /tmp/platform-metadata/cms/__init__.py
COPY --from=platform /lms/__init__.py /tmp/platform-metadata/lms/__init__.py
COPY --from=platform /openedx/__init__.py /tmp/platform-metadata/openedx/__init__.py
COPY --from=platform /common/lib/capa/setup.py /tmp/capa-metadata/setup.py
COPY --from=platform /common/lib/capa/capa/__init__.py /tmp/capa-metadata/capa/__init__.py
COPY --from=platform /common/lib/xmodule/setup.py /tmp/xmodule-metadata/setup.py
COPY --from=platform /common/lib/xmodule/xmodule/__init__.py /tmp/xmodule-metadata/xmodule/__init__.py
RUN pip install --no-cache-dir --no-deps /tmp/platform-metadata \
    && pip install --no-cache-dir --no-deps /tmp/capa-metadata \
    && pip install --no-cache-dir --no-deps /tmp/xmodule-metadata \
    && python -c "import pkg_resources; assert list(pkg_resources.iter_entry_points('xmodule.v1', 'course')); assert list(pkg_resources.iter_entry_points('xmodule.v1', 'hidden')); print('XModule entry points OK')" \
    && rm -rf /tmp/platform-metadata /tmp/capa-metadata /tmp/xmodule-metadata

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
