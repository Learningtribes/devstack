# syntax=docker/dockerfile:1.7
# Production (k8s) application image of py3-master: LMS, Studio and the Celery workers from one image.
# System packages, the Platform install (ci/py313/install.py), the Triboo theme and every frontend asset (Sass, webpack,
# locale catalogs, production collectstatic) are done at build time. Nothing environment-specific is baked in: no
# database/queue/ES credentials, no JWT key, no config JSON.
#
# Layout (Path contract v2, ci/py313/layout.py; the same tree as the staging host):
#   /edx/app/edxapp/edx-platform    code (root-owned, read-only for the service user)
#   /edx/app/edxapp/venvs/edxapp    virtualenv
#   /edx/app/edxapp/py313/          install receipts, theme (themes/hawthorn), compiled locale
#   /edx/app/edxapp/py313-config    CONFIG_ROOT: mount point of <lms|cms>.<env|auth>.json
#   /edx/var/edxapp/staticfiles     production static root (STATIC_ROOT_BASE)
#
# Inputs are two named build contexts holding `git archive` trees (build.sh creates them):
#   platform  = Learningtribes/platform at PLATFORM_COMMIT (must contain ci/py313/layout.py)
#   theme     = Learningtribes/triboo-theme at THEME_COMMIT
ARG PYTHON_IMAGE=python:3.13-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8
ARG APP_ROOT=/edx/app/edxapp

FROM ${PYTHON_IMAGE} AS builder
ARG TARGETARCH
ARG APP_ROOT
ARG NODE_VERSION=16.20.2
ARG UV_VERSION=0.11.23
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8 UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 BRINGUP_APP_ROOT=${APP_ROOT}
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential pkg-config default-libmysqlclient-dev libldap2-dev libsasl2-dev libgeos-dev \
        libxml2-dev libxslt1-dev libxmlsec1-dev libxmlsec1-openssl libjpeg-dev zlib1g-dev \
        git curl ca-certificates xz-utils openssl gettext graphviz libgraphviz-dev xmlsec1 \
    && rm -rf /var/lib/apt/lists/*
# Node with a verified checksum (Webpack 4 and node-sass-era tooling need Node 16).
RUN set -eux; \
    case "${TARGETARCH:-$(dpkg --print-architecture)}" in arm64) a=arm64 ;; amd64) a=x64 ;; *) echo unsupported arch >&2; exit 1 ;; esac; \
    f="node-v${NODE_VERSION}-linux-${a}.tar.xz"; cd /tmp; \
    curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/${f}"; \
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" | grep " ${f}\$" | sha256sum -c -; \
    tar -xJf "$f" -C /usr/local --strip-components=1; rm "$f"; node -v
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
# generate_aws_config.py (asset step) resolves the service group by name.
RUN groupadd edxapp

# 1. Platform install: the same scripts the staging deploy runs (05-inputs.sh, 06-install-runtime.sh).
#    /startup holds the staged bring-up scripts plus the two placeholders the preparer insists on.
RUN install -d /startup /input "${APP_ROOT}" \
    && install -m 600 /dev/null /startup/.acceptance-credentials.json \
    && openssl genrsa -out /startup/jwt-private.pem 2048 2>/dev/null && chmod 600 /startup/jwt-private.pem
RUN --mount=type=bind,from=platform,target=/input/platform \
    --mount=type=bind,from=platform,source=ci/py313,target=/canary \
    --mount=type=cache,target=/root/.cache/uv \
    set -eux; \
    test -f /canary/layout.py; \
    python3.13 -B /canary/bringup/prepare_current_install.py; \
    python3.13 -B /canary/install.py; \
    "${APP_ROOT}/venvs/edxapp/bin/python" -B /canary/verify-platform-identity.py; \
    uv pip freeze --python "${APP_ROOT}/venvs/edxapp/bin/python" > "${APP_ROOT}/py313/pip-freeze.txt"; \
    cp /input/ci.lock "${APP_ROOT}/py313/ci.lock"

# 2. Theme: committed tree of the theme repository, where prepare_theme_inputs.py would export it.
ARG THEME_COMMIT
COPY --from=theme / ${APP_ROOT}/py313/themes/hawthorn
RUN printf '%s\n' "${THEME_COMMIT}" > "${APP_ROOT}/py313/themes/source-commit"

# 3. Frontend assets and production static root.
COPY app-build-assets.sh /usr/local/bin/app-build-assets.sh
RUN --mount=type=cache,target=/root/.npm \
    bash /usr/local/bin/app-build-assets.sh

# 4. Drop what only the build needs: bring-up secret placeholders, the replay static tree and its config.
RUN rm -f /startup/jwt-private.pem /startup/.acceptance-credentials.json \
    && rm -rf "${APP_ROOT}/py313/static" "${APP_ROOT}/py313/config"

FROM ${PYTHON_IMAGE} AS final
ARG APP_ROOT
ARG PLATFORM_COMMIT
ARG THEME_COMMIT
# Numeric uid/gid so that runAsNonRoot can be enforced; match fsGroup and any shared volume (the staging host uses 1001).
ARG APP_UID=1000
ARG APP_GID=1000
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
# Runtime counterparts of the build libraries (must stay in step with the builder list; the ldd check below fails the build otherwise).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl tini \
        libmariadb3 libldap-2.5-0 libsasl2-2 libgeos-c1v5 \
        libxml2 libxslt1.1 libxmlsec1 libxmlsec1-openssl xmlsec1 \
        libjpeg62-turbo zlib1g graphviz libglib2.0-0 libx11-6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g "${APP_GID}" edxapp \
    && useradd -l -u "${APP_UID}" -g edxapp -d /home/edxapp -m -s /bin/bash edxapp
COPY --from=builder ${APP_ROOT} ${APP_ROOT}
COPY --from=builder /startup /startup
COPY --from=builder /edx/var/edxapp/staticfiles /edx/var/edxapp/staticfiles
COPY app-entrypoint.sh /usr/local/bin/edxapp-entrypoint
# Code and assets stay root-owned and read-only for the service user; only data and log directories are writable.
# The platform hard-codes /edx/var/log/lms|cms: without write access login returns 500.
RUN chmod 755 /usr/local/bin/edxapp-entrypoint \
    && install -d -o edxapp -g edxapp /edx/var/log/lms /edx/var/log/cms /edx/var/log/py313 \
        /edx/var/edxapp /edx/var/edxapp/media /edx/var/edxapp/data \
        "${APP_ROOT}/py313/media" "${APP_ROOT}/py313/data" "${APP_ROOT}/py313/logs" \
    && install -d -m 750 -o root -g edxapp "${APP_ROOT}/py313-config" \
    && venv="${APP_ROOT}/venvs/edxapp" \
    && missing=$(find "$venv" -name '*.so*' \( -path '*MySQLdb*' -o -path '*xmlsec*' -o -path '*lxml*' -o -path '*ldap*' -o -path '*PIL*' -o -path '*pygraphviz*' \) -exec ldd {} + 2>/dev/null | grep -c 'not found' || true) \
    && [ "${missing:-0}" -eq 0 ] \
    && ! grep -rIl '/runtime/' "$venv/bin" "$venv"/lib/python3.13/site-packages/*.pth \
    && "$venv/bin/python" -c 'import django, MySQLdb, xmlsec, lxml.etree, ldap, PIL, gunicorn, celery; assert django.VERSION[:2] == (5, 2)'
ENV BRINGUP_APP_ROOT=${APP_ROOT} EDXAPP_HOME=${APP_ROOT} VIRTUAL_ENV=${APP_ROOT}/venvs/edxapp \
    PATH=${APP_ROOT}/venvs/edxapp/bin:/usr/local/bin:/usr/bin:/bin \
    CONFIG_ROOT=${APP_ROOT}/py313-config EDXAPP_SETTINGS=aws \
    LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/home/edxapp
LABEL org.opencontainers.image.title="py313 edxapp (LMS, Studio, workers)" \
      org.opencontainers.image.source="https://github.com/Learningtribes/platform" \
      org.opencontainers.image.revision="${PLATFORM_COMMIT}" \
      com.learningtribes.theme.revision="${THEME_COMMIT}"
EXPOSE 8000 8010
USER ${APP_UID}:${APP_GID}
WORKDIR ${APP_ROOT}/edx-platform
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/edxapp-entrypoint"]
CMD ["lms"]
