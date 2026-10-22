COMPOSE := docker compose -f docker-compose.yml --env-file .env
IMAGE ?= ltdps/edxapp:py313-local
DEBIAN_MIRROR ?= https://mirrors.tuna.tsinghua.edu.cn/debian
DEBIAN_SECURITY_MIRROR ?= https://mirrors.tuna.tsinghua.edu.cn/debian-security
PIP_INDEX_URL ?= https://pypi.tuna.tsinghua.edu.cn/simple
NODE_DIST_URL ?= https://nodejs.org/dist
PLATFORM_DIR ?= $(abspath ../../../platform)

.PHONY: env build up down destroy ps smoke shell

env:
	@test -f .env && echo ".env exists" || { \
	  printf 'PY313_MYSQL_ROOT_PASSWORD=%s\nPY313_MYSQL_PASSWORD=%s\nPY313_RABBITMQ_PASSWORD=%s\n' \
	    "$$(openssl rand -hex 16)" "$$(openssl rand -hex 16)" "$$(openssl rand -hex 16)" > .env; \
	  chmod 600 .env; echo ".env created"; }

build:
	docker build -t $(IMAGE) \
	  --build-arg DEBIAN_MIRROR=$(DEBIAN_MIRROR) --build-arg DEBIAN_SECURITY_MIRROR=$(DEBIAN_SECURITY_MIRROR) \
	  --build-arg PIP_INDEX_URL=$(PIP_INDEX_URL) --build-arg NODE_DIST_URL=$(NODE_DIST_URL) .

up: env
	$(COMPOSE) up -d --wait

down:
	$(COMPOSE) down

destroy:
	$(COMPOSE) down -v

ps:
	$(COMPOSE) ps

smoke: env
	docker run --rm --network py313_default --env-file .env \
	  -v $(CURDIR)/smoke:/smoke:ro $(IMAGE) python /smoke/smoke.py

shell: env
	docker run --rm -it --network py313_default --env-file .env \
	  -v $(PLATFORM_DIR):/edx/app/edxapp/edx-platform $(IMAGE) bash
