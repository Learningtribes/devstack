# DevOps handoff: Python 3.13 production image and Kubernetes configuration

Status at handoff: the image builds natively on arm64 and the stack runs on a single-node OrbStack cluster (LMS, Studio, default
Celery workers, in-cluster backing services, Traefik with local TLS). Everything below the "Not proven" heading is open.

## 1. What is delivered

| Deliverable | Path | Notes |
| --- | --- | --- |
| Application image build | `docker/py313/app/` | `app.Dockerfile`, `app-entrypoint.sh`, `app-build-assets.sh`, `build.sh`, `inputs.env` (pinned Platform and theme commits), contract test, README with the image contract |
| Kubernetes base | `k8s/py313/base/` | `lms`, `cms`, one Deployment per Celery queue, suspended CronJobs, ServiceAccount without API token |
| Schema job | `k8s/py313/jobs/` | `db-init` for an EMPTY database only (see 3.4) |
| Production overlay checklist | `k8s/py313/overlays/prod-example/README.md` | Checklist only, no values |
| Reference for the Traefik edge | `k8s/py313/traefik/`, `overlays/orbstack-local-traefik/` | Traefik v3, Ingress, static files service, TLS and CoreDNS handling as proven locally |
| Local run tooling | `k8s/py313/Makefile`, `scripts/` | Reproduces the verification on a laptop |

Local-only, do not carry to a real environment: `overlays/orbstack-local*` backing services, `scripts/gen-local-*`, the local CA,
`kube-system/coredns-custom`, the database name `py313_startup_local`.

## 2. Reproduce the verification

```bash
# image (native arch); PLATFORM_REPO and THEME_REPO are local clones that contain the pinned commits
PLATFORM_REPO=... THEME_REPO=... make -C docker/py313/app build IMAGE_TAG=edxapp:py313-<yyyymmdd>-<sha7>
make -C docker/py313/app test check
# local cluster (OrbStack, context orbstack)
make -C k8s/py313 k8s-local-test
INGRESS=traefik make -C k8s/py313 k8s-local-up
make -C k8s/py313 k8s-traefik-smoke
make -C k8s/py313 k8s-local-admin      # one administrator, password typed without echo
```

## 3. What DevOps must provide or decide

### 3.1 Build and release
- Target architecture. Only arm64 was built natively; amd64 was built once under QEMU and not repeated. Repeat on a native amd64 builder.
- Registry, tag convention (`edxapp:py313-<yyyymmdd>-<platform sha7>`) and deployment by digest (`build/image.lock.json` `index_digest` after `--push`).
- CI integration (gap F8-CI: the Jenkins `pr-head` check cannot build the commit), image scan, SBOM and signing.
- Build agent access: clones of the Platform and theme repositories (the theme remote is private), and egress to Debian mirrors, nodejs.org, PyPI, the npm registry and GitHub.
- Known image caveats: Debian packages are not version-pinned; the venv also contains the Paver and test tool locks; `node_modules` (376 MB) stays in the image.

### 3.2 Configuration and secrets
- The four files `lms|cms.env.json` and `lms|cms.auth.json` in Secret `edxapp-config`, `LOG_DESTINATION=console`. The local generator runs
  `generate_aws_config.py` as root in Docker; production needs its own rendering from the platform team's secret store.
- Secret `backing-credentials` keys are listed in `README.md` ("Secrets").
- Endpoints, credentials and CA for MySQL, MongoDB, Elasticsearch (TLS and authentication were exercised locally), RabbitMQ and memcached. Valkey is not used by the Platform config.

### 3.3 Edge (Traefik)
Production Traefik is not known to us. Needed to align the overlay: entry points, `Ingress` versus `IngressRoute`, middlewares (security headers,
rate limit, compression, the Studio body limit equivalent to nginx `client_max_body_size 2048M`), certificate resolver and ACME provider,
`forwardedHeaders` trust when a load balancer sits in front. The Platform needs `X-Forwarded-Proto` (`SECURE_PROXY_SSL_HEADER`).
Decide the static files path (nginx sidecar, a `static` Deployment as locally, or object storage and CDN) and whether the legacy nginx S3 proxy paths are still needed.

### 3.4 Database and migrations
- `db-init` is not a production migration tool: it requires a database name starting with `py313_startup_` or `py313_rebuild_`, and was proven only on an empty database and a rerun on it.
- There is no validated upgrade path for an existing production database (gap F8-DATA). Plan data migration, its position in the release flow (pre-deploy Job or hook) and rollback separately.
- The Django 5 session and signing change logs out every user at cutover (an existing owner decision).

### 3.5 Capacity and runtime parameters
- Resource requests and limits in `base/` are estimates; the local overlay carries idle measurements only. Web pods run two sync gunicorn workers (a single worker makes the `/heartbeat` readiness probe fail behind any long request); keep at least two.
- Studio import/export needs a writable `GITHUB_REPO_ROOT` and `MODULESTORE` `fs_root` (post-processed to the `data` volume), 3 Gi `/tmp` for the 2 GiB body, and storage shared between the cms and its workers: locally one PVC, in production S3 (`COURSE_IMPORT_EXPORT_BUCKET`) or a ReadWriteMany volume. Production hosts run 45 (LMS) and 16 (Studio) gunicorn workers: convert to replicas, `GUNICORN_WORKERS` and autoscaling after a load test.
- Worker `terminationGracePeriodSeconds` (open question Q8): the local value is a placeholder, staging uses `stopwaitsecs=432000`.
- Worker liveness (none today), NetworkPolicy and PodSecurity labels, scheduling constraints, which CronJobs to enable, their time zone, deadlines and the shared storage that the `metrics` job needs.

### 3.6 Learning Paths and course-discovery (no manifests here)

Studio's Learning Path feature spans the image's database and a separate discovery service that this bundle does not deploy. Everything below
was found on the single-host staging on 2026-11-19 (read back there) and in the code at Platform `3c3f2f721d1`; none of it was run on Kubernetes.
Reference (triboo-doc `master`): [`docs/staging/py313-staging-discovery-enable-20261119.md`](https://github.com/Learningtribes/triboo-doc/blob/master/docs/staging/py313-staging-discovery-enable-20261119.md) and [`docs/py313/course-discovery-py313-upgrade-2026-11-13.md`](https://github.com/Learningtribes/triboo-doc/blob/master/docs/py313/course-discovery-py313-upgrade-2026-11-13.md) section 3.6.

**Data in the edxapp database (not in the image).** Three rows are configuration data that no migration creates:
the user `lms_catalog_service_user` (active, not staff, unusable password), a `CatalogIntegration` row with `enabled=True`, and a
`ProgramsApiConfig` row with `enabled` and `enable_student_dashboard`. Without the last one Studio shows no Learning Path entry and the
LMS hides every Learning Path surface; without the user, creating a Learning Path fails with `User.DoesNotExist` **after** discovery has accepted the
POST (`ProgramESIndex.add_new_program` resolves it unguarded). The image ships `/startup/seed_learning_path_config.py` for this, but it refuses any database whose
name does not start with `py313_` (a guard for the local replay), so production needs its own seeding step. It is idempotent (rows are only appended when the
active one disagrees).

**Discovery (Platform side of the contract).**

| Item | Requirement | Why |
| --- | --- | --- |
| `COURSE_CATALOG_API_URL` in `lms.env.json` and `cms.env.json` | the in-cluster discovery Service URL, `.../api/v1/` | The Platform default is `http://0.0.0.0:18381/api/v1/`, which only works when discovery shares the host. Studio sends `Host: <site_domain>`, so the URL host is free. |
| discovery `django_site` and `core_partner` | one Site whose domain is the public **LMS** host, a Partner with id 1 (`DEFAULT_PARTNER_ID`); `SITE_ID` stays unset | discovery resolves the Site from the request `Host` and reuses `request.site.domain` as `https://{domain}/oauth2/access_token`; an empty table makes every URL, `/health/` included, answer 500. `127.0.0.1` and Studio hosts do not work. |
| Studio `SiteConfiguration.site_domain` | the LMS host, not the Studio host | It is the `Host` Studio sends; the Studio host does not serve `/oauth2`. |
| JWT | Studio's `JWT_AUTH` (`JWT_ISSUER`, `JWT_AUDIENCE`, `JWT_SECRET_KEY`) equals discovery's `JWT_AUTH.JWT_ISSUERS[0]` | Studio signs the token (`JwtBuilder`); `/api/v1/programs/` validates it, `/api/v1/refresh_course_metadata/` does not. |
| discovery `JWT_AUTH_HEADER_PREFIX` | `JWT` | drf-jwt 1.19 defaults to `Bearer`; the Platform sends `JWT <token>`. Only `settings/py313.py` of discovery sets it, `settings.production` does not (fix open in course-discovery). |
| discovery `COURSES_API` | `URL`, `OIDC_URL_ROOT`, and the id/secret of an LMS OAuth (DOT) application | discovery fetches course metadata from the LMS with client credentials. |

The configuration this bundle renders gives Studio **no** `JWT_AUTH`: `generate_aws_config.py` writes only `JWT_PRIVATE_SIGNING_KEY` and only for the LMS, so Studio signs
with the Platform defaults (`change-me` for issuer, audience and secret, as on staging today). Set real values in `cms.auth.json` and mirror them in discovery before this is more than a test setup.

Elasticsearch: Studio indexes Learning Paths under the `program_index` name (with the configured index prefix) and creates it on the first write; the search user must be
allowed to create it. The local run does this; staging had not exercised it when this was written. The hot-index command (`run_hot_index`) is separately broken (triboo-doc issue #3).

## 4. Not proven

- Real browser behaviour behind Clash or AnyConnect; real certificates and ACME; parity with the production Traefik configuration.
- Services outside this change: forum, discovery, veda and xqueue of the legacy hosts have no manifests here (discovery's contract with the Platform is in 3.6).
- S3 media storage, mail relay, SAML and SSO, XQueue and certificate generation, `preview.` hosts, media uploads, a large (near 2 GiB) Studio import; a small course was exported in the pod and imported through the Studio endpoint; the HTTP export download was not exercised.
- Rolling update, rollback, autoscaling and node failure; `/heartbeat` removes every pod from the Service when MongoDB, MySQL or Elasticsearch is down (liveness is a TCP check on purpose).
- Monitoring: the application sends StatsD metrics to `localhost:8125` (seen in the pod logs); an agent or sidecar is required.
- Load behaviour: all measurements are idle values from one single-node arm64 cluster.

## 5. Evidence recorded locally (single-node OrbStack, arm64)
- **Pin bump 2026-11-19**: `inputs.env` moved from Platform `b0db03a9e3e` to `3c3f2f721d1` (adds the program-index factory fix and the Learning Path bring-up seed, Platform #2474; theme unchanged at `e4ed4e346811`; no lock or requirement changes).
  The image was rebuilt natively on arm64 (`edxapp:py313-prodimage-3c3f2f7-local`, id `5f7532872c52`); contract tests (27) and manifests (57) pass, `build.sh --check` reports no warnings, and the built image contains
  the removed legacy index mapping, the `TieredCache.delete_all_tiers` fix and `/startup/seed_learning_path_config.py`. **The cluster run, the Traefik smoke and the login checks listed below were recorded on the previous image and were not repeated on this one.**
- Contract tests of the image (27), manifests (57) and scripts (34) pass; `buildx --check` reports no warnings.
- Pods run as uid 1000 with a read-only root filesystem; heartbeats return 200 on both hosts through Traefik over HTTPS; HTTP redirects to HTTPS without a container port in the `Location`; static CSS and JS are served; login works on LMS and Studio with a shared Secure session cookie; one Celery task is consumed; the Studio body limit returns 413 when lowered.
- Memory: about 3.6 GiB for the default stack (Elasticsearch about 0.9 GiB, MySQL about 0.6 GiB, each web pod about 0.5-0.6 GiB at idle with two workers).
- Traefik RBAC is least-privilege: a read-only ClusterRole for `ingressclasses` and `nodes`, plus Roles in `traefik` and `py313-prod-local` (no cluster-wide Secret access).
- The local CA carries name constraints (DNS/e-mail/URI limited to the domain, all IP addresses excluded). A CA made by an older script is kept and reported by `k8s-traefik-doctor` with the replacement steps (optional hardening).
