# Production overlay checklist (no manifests, no values)

A real overlay is a kustomization with `resources: [../../base]` and no backing services (they are managed). It has to set:

- **Image**: `images: [{name: edxapp, newName: <registry>/edxapp, digest: sha256:<digest>}]`. Tags are mutable; use the digest. Keep
  `imagePullPolicy: IfNotPresent` and add `imagePullSecrets` to the ServiceAccount if the registry needs credentials.
- **Namespace** and the two Secrets `edxapp-config` and `backing-credentials` (from the secret store of the platform team, not git).
- **Replicas** of `lms` and `cms`, and `GUNICORN_WORKERS` per pod (production hosts run 45 and 16 on one machine).
- **Resources** measured on real load (base values are estimates).
- **External endpoints** of MySQL, MongoDB, Elasticsearch, RabbitMQ and memcached: they are not manifests but values inside
  `lms|cms.env.json` / `.auth.json` (`edxapp-config`) and, for `db-init`, `jobs/bringup.env`-style `BRINGUP_*_HOST` variables in
  the ConfigMap `py313-bringup-env`.
- **Readiness `Host` header**: the public host name, if `localhost` is not in `ALLOWED_HOSTS`.
- **Ingress / Gateway** with TLS, `X-Forwarded-Proto` set (`SECURE_PROXY_SSL_HEADER`), and a static-file path (nginx, sidecar or CDN).
- **`terminationGracePeriodSeconds`** of workers (owner decision Q8, see `../../README.md`).
- **CronJobs**: which to enable (`suspend: false`), the time zone, and where the `metrics` inputs and outputs live.
- **Scheduling**: node selectors or tolerations, topology spread across zones (base spreads across nodes, `ScheduleAnyway`).
- **Network policy** and PodSecurity labels on the namespace (the application pods set every field the `restricted` profile checks: non-root, no privilege escalation, capabilities dropped, seccomp `RuntimeDefault`).
