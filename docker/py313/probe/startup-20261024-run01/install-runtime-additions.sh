#!/bin/bash
set -euo pipefail
export PATH=/opt/venv/bin:$PATH
# Registered inputs are read-only; build copies are writable and reusable.
mkdir -p /runtime/build-sources/require-1.0.11-py313 /runtime/build-sources/splash-1.3.0-py313
cp -a /startup/dependencies/django-require-1.0.11/. /runtime/build-sources/require-1.0.11-py313/
cp -a /startup/dependencies/django-splash-1.3.0/. /runtime/build-sources/splash-1.3.0-py313/
uv pip install --python /runtime/venv/bin/python 'Django==5.2.13' 'django-oauth-toolkit==3.2.0' 'setuptools==79.0.1' /runtime/build-sources/splash-1.3.0-py313 /runtime/build-sources/require-1.0.11-py313

mkdir -p /runtime/build-sources/fs-2.4.16-py313
cp -a /startup/dependencies/fs-2.4.16/. /runtime/build-sources/fs-2.4.16-py313/
uv pip install --python /runtime/venv/bin/python --no-deps /runtime/build-sources/fs-2.4.16-py313

mkdir -p /runtime/build-sources/edx-search-5.0.0-lt
cp -a /startup/dependencies/edx-search-5.0.0-lt/. /runtime/build-sources/edx-search-5.0.0-lt/
uv pip install --python /runtime/venv/bin/python --reinstall --no-deps /runtime/build-sources/edx-search-5.0.0-lt

mkdir -p /runtime/build-sources/xblock-poll-1.15.1-py313
cp -a /startup/dependencies/xblock_poll-1.15.1/. /runtime/build-sources/xblock-poll-1.15.1-py313/
uv pip install --python /runtime/venv/bin/python --reinstall --no-deps /runtime/build-sources/xblock-poll-1.15.1-py313

mkdir -p /runtime/build-sources/django-ratelimit-backend-2.0-py313
cp -a /startup/dependencies/django-ratelimit-backend-2.0/. /runtime/build-sources/django-ratelimit-backend-2.0-py313/
uv pip install --python /runtime/venv/bin/python --reinstall --no-deps /runtime/build-sources/django-ratelimit-backend-2.0-py313

mkdir -p /runtime/build-sources/edx-completion-5.0.0-py313
cp -a /startup/dependencies/edx_completion-5.0.0/. /runtime/build-sources/edx-completion-5.0.0-py313/
uv pip install --python /runtime/venv/bin/python --reinstall --no-deps /runtime/build-sources/edx-completion-5.0.0-py313

mkdir -p /runtime/build-sources/edx-sga-0.28.0-py313
cp -a /startup/patched/edx-sga/. /runtime/build-sources/edx-sga-0.28.0-py313/
uv pip install --python /runtime/venv/bin/python --reinstall --no-deps /runtime/build-sources/edx-sga-0.28.0-py313

# LT IdP fixed source da3798ea6be76ce392f3d3f26aa75d0fdccbf7fe; Django URL API adaptation.
mkdir -p /runtime/build-sources/djangosaml2idp-lt-py313
cp -a /startup/dependencies/djangosaml2idp-lt/. /runtime/build-sources/djangosaml2idp-lt-py313/
uv pip install --python /runtime/venv/bin/python --reinstall --no-deps /runtime/build-sources/djangosaml2idp-lt-py313

mkdir -p /runtime/build-sources/pysaml2-7.5.5-py313
cp -a /startup/dependencies/pysaml2-7.5.5/. /runtime/build-sources/pysaml2-7.5.5-py313/
uv pip install --python /runtime/venv/bin/python --reinstall --no-deps /runtime/build-sources/pysaml2-7.5.5-py313

uv pip install --python /runtime/venv/bin/python python-memcached==1.62

/runtime/venv/bin/python /startup/install_dogapi.py
