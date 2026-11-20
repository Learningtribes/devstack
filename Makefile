.DEFAULT_GOAL := help
.PHONY: requirements

DEVSTACK_WORKSPACE ?= $(shell pwd)/..

OS := $(shell uname)

COMPOSE_PROJECT_NAME=devstack

export DEVSTACK_WORKSPACE
export COMPOSE_PROJECT_NAME

# Python 3.13 is the only supported runtime. `make py313-dev-up` creates one fixed development environment and every
# py313-* / *-shell target defaults to it, so no arguments are needed. Set BRINGUP_CONFIG to address another run
# (for example a frozen-snapshot acceptance run created by py313-up).
BRINGUP_REPLAY := docker/py313/probe/startup-20261024-run01/replay
BRINGUP_PYTHON := uv run --no-project --python 3.13 python -B
BRINGUP_DEV_RUN_ID ?= dev313
BRINGUP_RUNS_ROOT ?= $(HOME)/workspace/hawthorn/py313-runs
BRINGUP_CONFIG ?= $(BRINGUP_RUNS_ROOT)/$(BRINGUP_DEV_RUN_ID)/config.json
DISCOVERY_IMAGE ?= ltdps/discovery:py313-local
export BRINGUP_RUNS_ROOT
define py313_require_config
	@test -f "$(BRINGUP_CONFIG)" || { echo "No environment at $(BRINGUP_CONFIG); create it with: make py313-dev-up" >&2; exit 1; }
endef
define py313_shell
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/shell.py --config "$(BRINGUP_CONFIG)" $(1)
endef
define py313_require_new_run
	@test -n "$(RUN_ID)" -a -n "$(LMS_PORT)" -a -n "$(CMS_PORT)" -a -n "$(PLATFORM_REPO)" -a -n "$(THEME_REPO)" || { \
	  echo "RUN_ID, LMS_PORT, CMS_PORT, PLATFORM_REPO and THEME_REPO (a triboo-theme checkout) are required (optional: PLATFORM_COMMIT DEVSTACK_REPO DEVSTACK_COMMIT RUN_ROOT SUBNET RUNTIME_IMAGE DISCOVERY_REPO DISCOVERY_IMAGE DISCOVERY_PORT)" >&2; exit 1; }
endef
BRINGUP_NEW_RUN_ARGS = --run-id "$(RUN_ID)" --lms-port "$(LMS_PORT)" --cms-port "$(CMS_PORT)" \
  --platform-repo "$(PLATFORM_REPO)" $(if $(PLATFORM_COMMIT),--platform-commit "$(PLATFORM_COMMIT)") \
  $(if $(DEVSTACK_REPO),--devstack-repo "$(DEVSTACK_REPO)") $(if $(DEVSTACK_COMMIT),--devstack-commit "$(DEVSTACK_COMMIT)") \
  $(if $(RUN_ROOT),--root "$(RUN_ROOT)") $(if $(SUBNET),--subnet "$(SUBNET)") \
  $(if $(RUNTIME_IMAGE),--runtime-image "$(RUNTIME_IMAGE)") $(if $(LIVE_PLATFORM),--live-platform) \
  $(if $(THEME_REPO),--theme-repo "$(THEME_REPO)") \
  $(if $(DISCOVERY_REPO),--discovery-repo "$(DISCOVERY_REPO)") \
  $(if $(DISCOVERY_IMAGE),--discovery-image "$(DISCOVERY_IMAGE)") \
  $(if $(DISCOVERY_PORT),--discovery-port "$(DISCOVERY_PORT)")

# Generates a help message. Borrowed from https://github.com/pydanny/cookiecutter-djangopackage.
help: ## Display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@perl -nle'print $& if m{^[\.a-zA-Z0-9_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}'

requirements: ## Install requirements
	pip install -r requirements/base.txt

upgrade: ## Upgrade requirements with pip-tools
	pip install -qr requirements/pip-tools.txt
	pip-compile --upgrade -o requirements/pip-tools.txt requirements/pip-tools.in
	pip-compile --upgrade -o requirements/base.txt requirements/base.in
	bash post-pip-compile.sh \
		requirements/pip-tools.txt \
		requirements/base.txt \

lms-shell: ## Open a shell in the development runtime with LMS settings (no arguments)
	$(call py313_shell,lms)

cms-shell: ## Open a shell in the development runtime with CMS settings (no arguments)
	$(call py313_shell,cms)

py313-build-discovery: ## Build the course-discovery runtime image locally (DISCOVERY_REPO=<checkout>; DEBIAN_MIRROR/DEBIAN_SECURITY_MIRROR/NODE_DIST_URL override the Dockerfile defaults)
	@test -n "$(DISCOVERY_REPO)" || { echo "set DISCOVERY_REPO to a course-discovery checkout" >&2; exit 2; }
	@test -f "$(DISCOVERY_REPO)/ci/py313/Dockerfile" || { echo "no ci/py313/Dockerfile in $(DISCOVERY_REPO)" >&2; exit 2; }
	docker build -f "$(DISCOVERY_REPO)/ci/py313/Dockerfile" -t "$(DISCOVERY_IMAGE)" \
	  $(if $(DEBIAN_MIRROR),--build-arg DEBIAN_MIRROR="$(DEBIAN_MIRROR)") \
	  $(if $(DEBIAN_SECURITY_MIRROR),--build-arg DEBIAN_SECURITY_MIRROR="$(DEBIAN_SECURITY_MIRROR)") \
	  $(if $(NODE_DIST_URL),--build-arg NODE_DIST_URL="$(NODE_DIST_URL)") \
	  "$(DISCOVERY_REPO)"

py313-shell-discovery: ## Open a shell in the run's course-discovery container (no arguments)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/shell.py --config "$(BRINGUP_CONFIG)" discovery

py313-status-discovery: ## Show the run's course-discovery container state and /health/ code
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/discovery.py --config "$(BRINGUP_CONFIG)" status

py313-update-db-discovery: ## Run course-discovery migrations in the run's discovery container
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/discovery.py --config "$(BRINGUP_CONFIG)" migrate

py313-check-discovery: ## Run Django's system checks for course-discovery
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/discovery.py --config "$(BRINGUP_CONFIG)" check

py313-test-discovery: ## Run the course-discovery pytest suite against the run's MySQL (SELECTORS="<paths>" to narrow)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/discovery.py --config "$(BRINGUP_CONFIG)" test $(SELECTORS)

py313-new-run: ## Create a new Python 3.13 run directory and config; prints the config path (RUN_ID LMS_PORT CMS_PORT PLATFORM_REPO)
	$(py313_require_new_run)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/new_run.py $(BRINGUP_NEW_RUN_ARGS)

py313-up: ## Create a run and bring up the complete local LMS/Studio environment (same variables as py313-new-run; SKIP_UNIT_TESTS=1)
	$(py313_require_new_run)
	@CONFIG=$$($(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/new_run.py $(BRINGUP_NEW_RUN_ARGS)) && \
	  $(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/bring_up.py --config "$$CONFIG" $(if $(SKIP_UNIT_TESTS),--skip-unit-tests)

py313-dev-up: RUN_ID ?= $(BRINGUP_DEV_RUN_ID)
py313-dev-up: LMS_PORT ?= 18000
py313-dev-up: CMS_PORT ?= 18010
py313-dev-up: PLATFORM_REPO ?= $(DEVSTACK_WORKSPACE)/platform
py313-dev-up: THEME_REPO ?= $(wildcard $(DEVSTACK_WORKSPACE)/src/themes/hawthorn)
py313-dev-up: ## Create the fixed development environment (dev313, LMS 18000, Studio 18010): the sibling platform checkout is bind-mounted read-write, not copied; THEME_REPO=<theme checkout> (default ../src/themes/hawthorn if present) is mounted as theme hawthorn; a missing discovery image is built from DISCOVERY_REPO
	@if [ -n "$(DISCOVERY_REPO)" ]; then \
	  case "$(DISCOVERY_IMAGE)" in \
	    *@sha256:*) echo "discovery: $(DISCOVERY_IMAGE) is a published digest; preflight pulls it" ;; \
	    *) if docker image inspect "$(DISCOVERY_IMAGE)" >/dev/null 2>&1; then \
	         echo "discovery: image $(DISCOVERY_IMAGE) already present"; \
	       else \
	         echo "discovery: image $(DISCOVERY_IMAGE) is missing; building it from $(DISCOVERY_REPO)"; \
	         $(MAKE) py313-build-discovery DISCOVERY_REPO="$(DISCOVERY_REPO)" DISCOVERY_IMAGE="$(DISCOVERY_IMAGE)" \
	           $(if $(DEBIAN_MIRROR),DEBIAN_MIRROR="$(DEBIAN_MIRROR)") \
	           $(if $(DEBIAN_SECURITY_MIRROR),DEBIAN_SECURITY_MIRROR="$(DEBIAN_SECURITY_MIRROR)") \
	           $(if $(NODE_DIST_URL),NODE_DIST_URL="$(NODE_DIST_URL)") || exit 1; \
	       fi ;; \
	  esac; \
	fi
	$(MAKE) py313-up LIVE_PLATFORM=1 RUN_ID="$(RUN_ID)" LMS_PORT="$(LMS_PORT)" CMS_PORT="$(CMS_PORT)" PLATFORM_REPO="$(PLATFORM_REPO)" THEME_REPO="$(THEME_REPO)" \
	  $(if $(DISCOVERY_REPO),DISCOVERY_REPO="$(DISCOVERY_REPO)") $(if $(DISCOVERY_IMAGE),DISCOVERY_IMAGE="$(DISCOVERY_IMAGE)") \
	  $(if $(DISCOVERY_PORT),DISCOVERY_PORT="$(DISCOVERY_PORT)")

py313-restart: ## Restart LMS and Studio of the development environment so they pick up code changes
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/restart.py --config "$(BRINGUP_CONFIG)"

py313-rebuild-assets: ## Rebuild XModule + Sass/webpack into the live tree/STATIC_ROOT (no collectstatic; then py313-restart)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/rebuild.py --config "$(BRINGUP_CONFIG)" assets

py313-rebuild-translations: ## Recompile locale catalogs + collectstatic (use after .po changes or for collectstatic-only files)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/rebuild.py --config "$(BRINGUP_CONFIG)" translations

py313-rebuild-all: ## Rebuild assets then translations (repeatable; unlike the one-shot assets bring-up phase)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/rebuild.py --config "$(BRINGUP_CONFIG)" all

py313-rebuild-npm: ## npm ci only when webpack is missing (does not re-run after package-lock.json changes)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/rebuild.py --config "$(BRINGUP_CONFIG)" npm

py313-stop: ## Stop every container of the environment without deleting data (reverse of py313-start)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/lifecycle.py --config "$(BRINGUP_CONFIG)" stop

py313-start: ## Start every stopped container of the environment and re-dispatch LMS/CMS/discovery
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/lifecycle.py --config "$(BRINGUP_CONFIG)" start

py313-shell-lms: ## Shell in the run's runtime with LMS settings (works for any run age)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/lifecycle.py --config "$(BRINGUP_CONFIG)" --system lms shell

py313-shell-cms: ## Shell in the run's runtime with CMS settings (works for any run age)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/lifecycle.py --config "$(BRINGUP_CONFIG)" --system cms shell

py313-status: ## Show container states, ports and heartbeats of the development environment
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/status.py --config "$(BRINGUP_CONFIG)"

py313-destroy: ## Remove only the Docker resources owned by the development environment, keep its directory (DRY_RUN=1, PURGE_DIR=1)
	$(py313_require_config)
	@$(BRINGUP_PYTHON) $(BRINGUP_REPLAY)/destroy_run.py --config "$(BRINGUP_CONFIG)" $(if $(DRY_RUN),--dry-run) $(if $(PURGE_DIR),--purge-dir)

studio-shell: ## Alias of cms-shell
	$(call py313_shell,cms)

stats: ## Get per-container CPU and memory utilization data
	docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
