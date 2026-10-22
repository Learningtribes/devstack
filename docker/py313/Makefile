COMPOSE := docker compose -f docker-compose.yml --env-file .env
IMAGE ?= ltdps/edxapp:py313-local
IMAGE_DEV ?= $(IMAGE)-dev
VENV_VOLUME ?= py313_venv
DEBIAN_MIRROR ?= https://mirrors.tuna.tsinghua.edu.cn/debian
DEBIAN_SECURITY_MIRROR ?= https://mirrors.tuna.tsinghua.edu.cn/debian-security
PIP_INDEX_URL ?= https://pypi.tuna.tsinghua.edu.cn/simple
NODE_DIST_URL ?= https://nodejs.org/dist
# Must point at a dedicated platform worktree (not the main checkout); no default on purpose.
PLATFORM_DIR ?=

BUILD_ARGS = --build-arg DEBIAN_MIRROR=$(DEBIAN_MIRROR) --build-arg DEBIAN_SECURITY_MIRROR=$(DEBIAN_SECURITY_MIRROR) \
  --build-arg PIP_INDEX_URL=$(PIP_INDEX_URL) --build-arg NODE_DIST_URL=$(NODE_DIST_URL)
ENV_KEYS := PY313_MYSQL_ROOT_PASSWORD PY313_MYSQL_PASSWORD PY313_RABBITMQ_PASSWORD PY313_MONGO_PASSWORD

.PHONY: env build up down destroy ps smoke rmq-matrix shell venv-reset

env:
	@touch .env && chmod 600 .env
	@for k in $(ENV_KEYS); do \
	  grep -q "^$$k=" .env || { echo "$$k=$$(openssl rand -hex 16)" >> .env; echo "added $$k"; }; \
	done

build:
	docker build --target runtime -t $(IMAGE) $(BUILD_ARGS) .
	docker build --target dev -t $(IMAGE_DEV) $(BUILD_ARGS) .

up: env
	$(COMPOSE) up -d --wait

down: env
	$(COMPOSE) --profile noperm down

destroy: env
	$(COMPOSE) --profile noperm down -v

ps: env
	$(COMPOSE) ps

smoke: env
	docker run --rm --network py313_default --env-file .env \
	  -v $(CURDIR)/smoke:/smoke:ro $(IMAGE) python /smoke/smoke.py

rmq-matrix: env
	$(COMPOSE) --profile noperm up -d --wait rabbitmq-noperm
	docker run --rm --network py313_default --env-file .env \
	  -v $(CURDIR)/smoke:/smoke:ro $(IMAGE) python /smoke/rmq_pidbox_matrix.py
	$(COMPOSE) --profile noperm rm -sf rabbitmq-noperm

shell: env
	@test -n "$(PLATFORM_DIR)" || { echo "set PLATFORM_DIR to a dedicated platform worktree"; exit 2; }
	@test -d "$(PLATFORM_DIR)" || { echo "PLATFORM_DIR is not a directory: $(PLATFORM_DIR)"; exit 2; }
	@if [ "$$(git -C "$(PLATFORM_DIR)" rev-parse --absolute-git-dir 2>/dev/null)" = "$$(git -C "$(PLATFORM_DIR)" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" ] \
	   && [ -z "$(ALLOW_MAIN_CHECKOUT)" ]; then \
	  echo "refusing: $(PLATFORM_DIR) is a main checkout, use 'git worktree add' (or ALLOW_MAIN_CHECKOUT=1)"; exit 2; fi
	docker run --rm -it --network py313_default --env-file .env -e PIP_INDEX_URL=$(PIP_INDEX_URL) \
	  -v $(VENV_VOLUME):/opt/venv -v $(abspath $(PLATFORM_DIR)):/edx/app/edxapp/edx-platform $(IMAGE_DEV) bash

venv-reset:
	docker volume rm $(VENV_VOLUME)
