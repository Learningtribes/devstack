# Local OrbStack run of the Python 3.13 production image. Run from this directory:  make -C k8s/py313 help
#
# Variables (environment or command line):
#   ALLOW_CONTEXT     kubectl context the scripts accept (default: orbstack); anything else is refused unless set explicitly
#   APP_OVERLAY       application overlay applied by k8s-local-up (default: overlays/orbstack-local;
#                     overlays/orbstack-local-all-workers runs all eight Celery queues)
#   FORCE_DB_INIT=1   rerun the db-init Job although it already completed
#   LMS_LOCAL_PORT / CMS_LOCAL_PORT   local ports of the smoke test port-forwards (default 18000 / 18010)
#   PURGE_LOCAL=1     k8s-local-down also removes .local/ (generated credentials and configuration), except .local/tls (the local CA)
#   PURGE_TLS=1       with PURGE_LOCAL=1 also removes .local/tls; the CA must then be trusted again in the keychain
#   INGRESS=traefik   k8s-local-up in the production-like Traefik mode (same as k8s-traefik-up); needs a namespace created in that mode
.DEFAULT_GOAL := help
.PHONY: help k8s-local-up k8s-local-status k8s-local-smoke k8s-local-admin k8s-local-down k8s-local-test k8s-local-render \
	k8s-traefik-up k8s-traefik-status k8s-traefik-smoke k8s-traefik-doctor k8s-traefik-down

PYTHON := uv run --no-project --python 3.13 python -B
OVERLAY_DIR := overlays/orbstack-local

help: ## Show the targets and variables
	@printf 'Variables:\n'
	@sed -n 's/^#   \(.*\)$$/  \1/p' $(firstword $(MAKEFILE_LIST))
	@printf '\nTargets:\n'
	@grep -E '^[a-z0-9-]+:.*## ' $(firstword $(MAKEFILE_LIST)) | sed 's/:.*## /\t/' | awk -F'\t' '{printf "  %-20s %s\n", $$1, $$2}'

k8s-local-up: ## Create the namespace, backing services, configuration, db-init and the application (scripts/up)
	./scripts/up

k8s-local-status: ## Pods, PVCs, rollouts, warning events, kubectl top if available (scripts/status)
	./scripts/status

k8s-local-smoke: ## Heartbeats, pages and one Celery task through a worker (scripts/smoke)
	./scripts/smoke

k8s-local-admin: ## Create or update one LMS administrator; the password is typed without echo (scripts/create-admin)
	./scripts/create-admin

k8s-local-down: ## Delete the namespace py313-prod-local only (scripts/down)
	./scripts/down

k8s-traefik-up: ## Production-like mode: Traefik, TLS, CoreDNS rewrite, static files, then the stack (INGRESS=traefik scripts/up)
	INGRESS=traefik ./scripts/up

k8s-traefik-status: ## Traefik, Ingress, static, certificates, CoreDNS custom config (scripts/traefik-status)
	./scripts/traefik-status

k8s-traefik-smoke: ## HTTPS, redirect, static files, logins, in-cluster trust, Celery; bypasses Clash (scripts/traefik-smoke)
	./scripts/traefik-smoke

k8s-traefik-doctor: ## Read-only host diagnosis (Clash fake-ip, proxy, keychain trust); prints the user's steps (scripts/traefik-doctor)
	./scripts/traefik-doctor

k8s-traefik-down: ## Remove only what the Traefik mode created (not the namespace py313-prod-local) (scripts/traefik-down)
	./scripts/traefik-down

k8s-local-test: ## Static manifest tests and script tests, no cluster needed
	$(PYTHON) -m unittest discover -s . -p 'test_manifests.py' -v
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py' -v
	@for f in scripts/lib.sh scripts/up scripts/status scripts/smoke scripts/down scripts/gen-local-secrets scripts/gen-local-config scripts/setup-elasticsearch scripts/gen-local-tls scripts/traefik-install scripts/traefik-status scripts/traefik-smoke scripts/traefik-doctor scripts/traefik-down; do bash -n $$f || exit 1; done; echo 'bash -n: ok'

k8s-local-render: ## Print the rendered local overlay (APP_OVERLAY=... for another one)
	@kubectl kustomize $(if $(APP_OVERLAY),$(APP_OVERLAY),$(OVERLAY_DIR))
