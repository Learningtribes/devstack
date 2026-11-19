# Production application image (`docker/py313/app/`)

One image for LMS, Studio, every Celery queue and the deploy Jobs of the Open edX Hawthorn platform on the Python 3.13 `py3-master` line. Platform and the Triboo theme at pinned commits, all apt/pip installs and the whole frontend build are done at image build time; nothing environment-specific (database, queue or ES credentials, JWT key, config JSON) is baked in. The Kubernetes manifests (`k8s/py313/`) depend on the contract below.

History and the staging-host comparison of this image: `triboo-doc/docs/staging/py313-docker-images/README.md`, section 0.

## Ownership

| Owner | What |
| --- | --- |
| Platform (`ci/py313/`) | install scripts and hash locks (`prepare_current_install.py`, `install.py`, `verify-platform-identity.py`, `layout.py`), the CI images (`Dockerfile.app`, `Dockerfile.bootstrap`: **not** copied here) |
| This directory | `app.Dockerfile`, `app-build-assets.sh` (asset pipeline), `app-entrypoint.sh` (container entry point), `build.sh`, `inputs.env` (pinned commits), `Makefile`, `test_app_image_contract.py` |
| Devstack `docker/py313/Dockerfile` | local replay runtime base; unrelated to this image except for the `/startup` scripts it stages |

The Platform commit must contain `ci/py313/layout.py` (Path contract v2). The `/startup` bring-up scripts in the image come from the Platform tree at that commit.

## Build, check, publish

```bash
export PLATFORM_REPO=<clone of https://github.com/Learningtribes/platform>
export THEME_REPO=<clone of https://github.com/Learningtribes/triboo-theme>

make check                                   # bash -n, shellcheck (if installed), docker buildx build --check
make test                                    # contract test, no Docker needed
make build IMAGE_TAG=<registry>/edxapp:py313-<yyyymmdd>-<sha7>        # native arch, --load
make build IMAGE_TAG=... TARGET_ARCH=amd64   # amd64 only on explicit request (QEMU on an arm64 host)
BUILDX_FLAGS="--push --progress=plain" make build IMAGE_TAG=...        # publish; index digest goes to the lock
make inspect IMAGE=<tag>
```

`make build` is `./build.sh <image-tag> [native|amd64|arm64]`. Both repositories need local clones in which the pinned commits exist (`git archive` of the commit is the build input; the working tree, `.git` and credentials never reach the build). Repository locations are not committed anywhere. Other flags: `FORCE=1`, `BUILDX_FLAGS`, `BUILD_DIR`; `PLATFORM_COMMIT` / `THEME_COMMIT` in the environment override `inputs.env`.

- **Pins**: `inputs.env` (`PLATFORM_COMMIT`, `THEME_COMMIT`). Bump them in a reviewed commit, not on the command line, for any image that is deployed.
- **Tag policy**: `name:version` required, `latest` refused, an existing local tag refused unless `FORCE=1`. Tag convention: `edxapp:py313-<yyyymmdd>-<platform sha7>`; deploy by digest (`image.lock.json` `index_digest`) where the registry allows it.
- **`build/image.lock.json`** (git-ignored): `tag`, `image_id`, `architecture`, `platform_sha`, `theme_sha`, `build_date`, `index_digest` (only after `--push`, otherwise `null`). The labels `org.opencontainers.image.revision` (Platform) and `com.learningtribes.theme.revision` (theme) carry the full commit shas.
- The removed positional form `build.sh PLATFORM_REPO PLATFORM_COMMIT THEME_REPO THEME_COMMIT TAG [platform]` is replaced by the environment variables above.
- Everything the build downloads is public (Debian mirrors, nodejs.org, PyPI, npm, GitHub repositories pinned in `runtime-public.in`). Debian packages are not version-pinned; the base image is digest-pinned.

## Image contract

| Item | Contract |
| --- | --- |
| Name / tag | `edxapp:py313-<yyyymmdd>-<platform sha7>`; never `latest`; pin by digest in manifests |
| Architecture | native build per arch; the arm64 build is verified here, amd64 is built under QEMU only (repeat on a native amd64 builder) |
| User | numeric `1000:1000` (`edxapp`), build args `APP_UID` / `APP_GID`; manifests set `runAsNonRoot`, `runAsUser`, `runAsGroup`, `fsGroup` to the same values |
| Root filesystem | read-only supported and verified; code, venv, theme and static root are root-owned and not writable by the service user |
| Ports | `8000` (LMS gunicorn), `8010` (Studio gunicorn) |
| `ENTRYPOINT` / `CMD` | `["/usr/bin/tini","--","/usr/local/bin/edxapp-entrypoint"]` / `["lms"]`; every process is `exec`'d, so SIGTERM reaches gunicorn / Celery directly |
| Working directory | `/edx/app/edxapp/edx-platform` |

Entrypoint commands (container `args`):

| Args | Process |
| --- | --- |
| `lms` | `gunicorn lms.wsgi:application` on `0.0.0.0:$PORT` (default 8000) |
| `cms` | `gunicorn cms.wsgi:application` on `0.0.0.0:$PORT` (default 8010) |
| `worker lms\|cms [celery args]` | `celery -A <system>.celery:APP worker [args]`, e.g. `--queues=edx.lms.core.default --hostname=edx.lms.core.default.%h --concurrency=1` |
| `manage lms\|cms [args]` | `python manage.py <system> --settings=$EDXAPP_SETTINGS [args]` |
| anything else | executed as given (`bash`, `python manage.py ...` with `startup_*` settings, `/startup` scripts) |

Environment variables (image defaults; all can be overridden per pod):

| Variable | Default | Meaning |
| --- | --- | --- |
| `EDXAPP_SETTINGS` | `aws` | selects `<system>.envs.<name>`; must match `[a-z0-9_]+` (else exit 64) |
| `CONFIG_ROOT` | `/edx/app/edxapp/py313-config` | directory of `<lms\|cms>.env.json` and `.auth.json` |
| `PORT` | `8000` (lms) / `8010` (cms) | gunicorn bind port |
| `GUNICORN_WORKERS` | `2` (lms) / `1` (cms) | gunicorn workers per pod |
| `GUNICORN_TIMEOUT` | `300` | seconds |
| `GUNICORN_MAX_REQUESTS` | `1000` (lms) / `2000` (cms) | worker recycle |
| `GUNICORN_CMD_ARGS` | unset | any further gunicorn flags (extra container args after `lms`/`cms` are appended too) |
| `SERVICE_VARIANT`, `DJANGO_SETTINGS_MODULE` | set by the entrypoint | do not set |
| `EDXAPP_HOME`, `BRINGUP_APP_ROOT`, `VIRTUAL_ENV`, `PATH`, `HOME`, `LANG`, `PYTHONUNBUFFERED` | `/edx/app/edxapp`, same, `…/venvs/edxapp`, venv first, `/home/edxapp`, `C.UTF-8`, `1` | image layout; leave alone |

Mounts:

| Path | Kind | Notes |
| --- | --- | --- |
| `/edx/app/edxapp/py313-config` | Secret, read-only, `defaultMode: 0440`, `fsGroup` = gid | the four files `lms.env.json`, `lms.auth.json`, `cms.env.json`, `cms.auth.json`; produced by `/startup/generate_aws_config.py` (see Jobs). Required for `lms`, `cms`, `worker`, `manage`; the pod of a system needs only that system's pair |
| `/tmp` | `emptyDir` | Mako template cache |
| `/edx/var/log/lms`, `/edx/var/log/cms` | `emptyDir` | the platform hard-codes them; without write access login returns 500 |
| `/edx/var/edxapp/media`, `/edx/var/edxapp/data` | `emptyDir` or PVC | do not mount over `/edx/var/edxapp` itself: it holds the static root `/edx/var/edxapp/staticfiles` (Studio under `studio/`) |

Behaviour:

- **Exit codes**: `78` config file missing or unreadable by the running uid; `64` invalid `EDXAPP_SETTINGS` or a system name other than `lms`/`cms` for `worker`/`manage`. `passthrough` commands do not read the config.
- **Logging**: gunicorn access and error logs go to stdout. The application log follows `LOG_DESTINATION` in `<system>.env.json`; the generator writes `file` (to `/edx/var/log/<system>`), so set `console` in the Secret for pods that should log to stdout.
- **`/heartbeat`** (LMS and Studio) runs `HEARTBEAT_CHECKS`: modulestore (Mongo), MySQL, Elasticsearch (Celery and cache only with `?extended`). Use it for readiness and send a `Host` header from `ALLOWED_HOSTS`; it returns 500 while a backing service is down. Use a TCP check on the port for liveness so that a database outage does not restart pods.
- **Proxy**: `SECURE_PROXY_SSL_HEADER` is `X-Forwarded-Proto`; the ingress must set it.
- **Static files** come from the same image as the code (no drift): serve `/edx/var/edxapp/staticfiles` from a sidecar/nginx stage `COPY --from=<image>`, or publish it to object storage at release time.
- **Jobs** (schema, seeds, config generation) use this image: `/startup` holds the bring-up scripts, without secrets. Run e.g. `args: [python, manage.py, lms, shell, -c, "exec(open('/startup/<script>').read())"]` with `PYTHONPATH=/startup/settings`, `DJANGO_SETTINGS_MODULE=startup_lms|startup_schema` and the `BRINGUP_*` variables; mount a real `/startup/jwt-private.pem`. `generate_aws_config.py` chowns to root and group `BRINGUP_SERVICE_GROUP` (`edxapp`), so run it as root into a scratch volume and turn the result into the Secret; set `BRINGUP_STATE_DIR=/edx/var/edxapp`.
- **Celery**: `terminationGracePeriodSeconds` for workers is an open owner decision (staging uses `stopwaitsecs=432000`).

Not in the image: any credential, the four config files, site/theme DB rows. The venv also holds the Paver and test tool locks (`install.py` installs `ci.lock`); `node_modules` stays because no runtime-path proof exists.

## Tests

`make test` (stdlib only) asserts on `app.Dockerfile` (digest-pinned base, numeric non-root `USER`, `EXPOSE 8000 8010`, tini entrypoint, no credential-like `ARG`/`ENV`, no `/runtime` path, both commit labels, no `latest`) and runs `app-entrypoint.sh` against stub `gunicorn`/`celery`/`python` (exit 78/64, bind/worker/timeout arguments, celery invocation, `exec` without a shell wrapper and SIGTERM exit 0) and `build.sh` against a stub `docker` (tag policy, lock file). It does not prove the image builds or runs; for that use `make check`, a build and the run checks of the triboo-doc README ("Run checks on the arm64 image").
