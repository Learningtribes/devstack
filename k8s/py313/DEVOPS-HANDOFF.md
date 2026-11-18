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

## 4. Not proven

- Real browser behaviour behind Clash or AnyConnect; real certificates and ACME; parity with the production Traefik configuration.
- Services outside this change: forum, discovery, veda and xqueue of the legacy hosts have no manifests here.
- S3 media storage, mail relay, SAML and SSO, XQueue and certificate generation, `preview.` hosts, media uploads, a large (near 2 GiB) Studio import; a small course was exported in the pod and imported through the Studio endpoint; the HTTP export download was not exercised.
- Rolling update, rollback, autoscaling and node failure; `/heartbeat` removes every pod from the Service when MongoDB, MySQL or Elasticsearch is down (liveness is a TCP check on purpose).
- Monitoring: the application sends StatsD metrics to `localhost:8125` (seen in the pod logs); an agent or sidecar is required.
- Load behaviour: all measurements are idle values from one single-node arm64 cluster.

## 5. Evidence recorded locally (single-node OrbStack, arm64)
- Contract tests of the image (27), manifests (57) and scripts (34) pass; `buildx --check` reports no warnings.
- Pods run as uid 1000 with a read-only root filesystem; heartbeats return 200 on both hosts through Traefik over HTTPS; HTTP redirects to HTTPS without a container port in the `Location`; static CSS and JS are served; login works on LMS and Studio with a shared Secure session cookie; one Celery task is consumed; the Studio body limit returns 413 when lowered.
- Memory: about 3.6 GiB for the default stack (Elasticsearch about 0.9 GiB, MySQL about 0.6 GiB, each web pod about 0.5-0.6 GiB at idle with two workers).
- Traefik RBAC is least-privilege: a read-only ClusterRole for `ingressclasses` and `nodes`, plus Roles in `traefik` and `py313-prod-local` (no cluster-wide Secret access).
- The local CA carries name constraints (DNS/e-mail/URI limited to the domain, all IP addresses excluded). A CA made by an older script is kept and reported by `k8s-traefik-doctor` with the replacement steps (optional hardening).
