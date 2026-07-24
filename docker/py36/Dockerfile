FROM python:3.6-slim

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

# 1. PyPI packages
COPY py36-base.txt /tmp/
RUN pip install --no-cache-dir "pip<21.0" "setuptools<45" \
    && pip install --no-cache-dir -r /tmp/py36-base.txt

# 2. Git-only packages (edX forks not on PyPI)
RUN pip install --no-cache-dir \
    git+https://github.com/edx/django-celery.git@756cb57aad765cb2b0d37372c1855b8f5f37e6b0 \
    git+https://github.com/edx/django-rest-framework.git@1ceda7c086fddffd1c440cc86856441bbf0bd9cb \
    git+https://github.com/edx/django-wiki.git@v0.0.18 \
    git+https://github.com/edx/codejail.git@a320d43ce6b9c93b17636b2491f724d9e433be47 \
    git+https://github.com/edx/django-oauth-plus.git@01ec2a161dfc3465f9d35b9211ae790177418316 \
    git+https://github.com/edx/django-openid-auth.git@0.15.1 \
    git+https://github.com/edx/django-rest-framework-oauth.git@0a43e8525f1e3048efe4bc70c03de308a277197c \
    git+https://github.com/edx/MongoDBProxy.git@25b99097615bda06bd7cdfe5669ed80dc2a7fed0 \
    git+https://github.com/Learningtribes/djangosaml2idp.git@master \
    git+https://github.com/appliedsec/pygeoip.git@95e69341cebf5a6a9fbf7c4f5439d458898bdc3b \
    git+https://github.com/dgrtwo/ParsePy.git@7949b9f754d1445eff8e8f20d0e967b9a6420639 \
    git+https://github.com/Learningtribes/edx-ora2@hawthorn#egg=ora2 \
    git+https://github.com/Learningtribes/xblock-done.git@hawthorn#egg=lbmdone-xblock \
    git+https://github.com/edx/xblock-lti-consumer.git@v1.1.8

# 3. LT vendored XBlocks (from src/)
RUN pip install --no-cache-dir \
    git+https://github.com/Learningtribes/edx_xblock_scorm@hawthorn \
    git+https://github.com/Learningtribes/xblock-drag-and-drop-v2@hawthorn \
    # xblock-utils needs futures fix: install separately

# 4. importlib_resources backport (3.6 needs this, stdlib in 3.7+)
RUN pip install --no-cache-dir importlib-resources

# Verify
RUN python3 -c "\
import django; print('Django', django.VERSION); \
import celery; print('celery', celery.VERSION); \
import pymongo; print('pymongo', pymongo.version); \
import kombu.async; print('kombu.async OK'); \
import MySQLdb; print('mysqlclient OK'); \
print('Image build OK')"

CMD ["python3"]
