#!/usr/bin/env bash
# Build stage only: the asset pipeline of staging step 09, run against throwaway settings values.
# The startup_* and aws settings modules refuse to load without credentials and a config tree, so a disposable
# one is generated here and deleted at the end; none of it reaches the final image.
set -euo pipefail

ROOT=${BRINGUP_APP_ROOT:?BRINGUP_APP_ROOT must be set}
STATE=$ROOT/py313
PLATFORM=$ROOT/edx-platform
STATIC_BASE=/edx/var/edxapp/staticfiles
BUILD_CONFIG=/tmp/build-config

export PATH=$ROOT/venvs/edxapp/bin:/usr/local/bin:/usr/bin:/bin:$PLATFORM/node_modules/.bin
export LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/startup/settings
export BRINGUP_PLATFORM_ROOT=$PLATFORM
export BRINGUP_LMS_DOMAIN=lms.build.invalid BRINGUP_CMS_DOMAIN=cms.build.invalid BRINGUP_SCHEME=https
export BRINGUP_SERVICE_GROUP=edxapp BRINGUP_STATIC_BASE=$STATIC_BASE BRINGUP_CONFIG_OUT=$BUILD_CONFIG
export BRINGUP_STATE_DIR=/edx/var/edxapp
BRINGUP_STARTUP_SECRET_KEY="build-$(openssl rand -hex 24)"
export BRINGUP_STARTUP_SECRET_KEY BRINGUP_STARTUP_XQUEUE_PASSWORD=build-only
export BRINGUP_MYSQL_PASSWORD=build-only BRINGUP_MONGO_PASSWORD=build-only BRINGUP_RABBITMQ_PASSWORD=build-only
export BRINGUP_DATABASE_NAME=py313_startup_build BRINGUP_MONGO_DB=py313_startup_build
export BRINGUP_CACHE_PREFIX=py313_build BRINGUP_ES_INDEX_PREFIX=py313_build_
export BRINGUP_MYSQL_HOST=127.0.0.1 BRINGUP_MONGO_HOST=127.0.0.1 BRINGUP_MEMCACHED_HOST=127.0.0.1 BRINGUP_RABBITMQ_HOST=127.0.0.1 BRINGUP_ES_HOST=127.0.0.1

mkdir -p "$STATE"/{media,data,logs,config,static/lms,static/cms,locale} /edx/var/log/lms /edx/var/log/cms /edx/var/edxapp
cd "$PLATFORM"

echo '== 1. replay build: vendor copy, xmodule assets, Sass, theme Sass, webpack, locale catalogs'
npm ci --legacy-peer-deps --ignore-scripts --no-audit --no-fund
DJANGO_SETTINGS_MODULE=startup_lms python manage.py lms shell -c \
  "from pathlib import Path;exec(compile(Path('/startup/build_xmodule_assets.py').read_text(),'x','exec'))"
NODE_OPTIONS=--max-old-space-size=2048 bash /startup/build_frontend.sh
for system in lms cms; do
  DJANGO_SETTINGS_MODULE=startup_$system python manage.py "$system" shell -c \
    "from pathlib import Path;exec(compile(Path('/startup/locale_static.py').read_text(),'l','exec'))"
done
test -s "$STATE/static/lms/webpack-stats.json"
test -s "$STATE/static/cms/webpack-stats.json"

echo '== 2. production static root (the settings of lms.envs.aws / cms.envs.aws)'
mkdir -p "$STATIC_BASE/studio"
cp "$STATE/static/lms/webpack-stats.json" "$STATIC_BASE/webpack-stats.json"
cp "$STATE/static/cms/webpack-stats.json" "$STATIC_BASE/studio/webpack-stats.json"
mkdir -p lms/static/js/i18n cms/static/js/i18n
cp -a "$STATE/static/lms/js/i18n/." lms/static/js/i18n/
cp -a "$STATE/static/cms/js/i18n/." cms/static/js/i18n/
DJANGO_SETTINGS_MODULE=startup_lms python manage.py lms shell -c "exec(open('/startup/generate_aws_config.py').read())"
export CONFIG_ROOT=$BUILD_CONFIG
for system in lms cms; do
  SERVICE_VARIANT=$system python manage.py "$system" collectstatic --noinput --settings=aws > "/tmp/collectstatic-$system.log" 2>&1 \
    || { tail -n 40 "/tmp/collectstatic-$system.log"; exit 1; }
  tail -n 2 "/tmp/collectstatic-$system.log"
done
chmod -R a+rX "$STATIC_BASE"
test -s "$STATIC_BASE/staticfiles.json"
test -s "$STATIC_BASE/studio/staticfiles.json"

rm -rf "$BUILD_CONFIG" /tmp/collectstatic-*.log
echo "== done: $(du -sh "$STATIC_BASE" | cut -f1) static, $(du -sh "$PLATFORM/node_modules" | cut -f1) node_modules"
