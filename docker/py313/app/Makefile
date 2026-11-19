# Production application image: lint, contract test, build and inspection.
#
# Variables
#   PLATFORM_REPO  local clone of https://github.com/Learningtribes/platform        (required by check, build)
#   THEME_REPO     local clone of https://github.com/Learningtribes/triboo-theme    (required by check, build)
#   IMAGE_TAG      name:version of the image to build, never `latest`      (required by build)
#   TARGET_ARCH    native (default, the host's), amd64 or arm64
#   FORCE          1 allows overwriting a tag that already exists locally
#   BUILDX_FLAGS   extra `docker buildx build` flags, default --load (e.g. "--push --progress=plain")
#   PLATFORM_COMMIT, THEME_COMMIT  override the pins of inputs.env
#   IMAGE          image reference to show (required by inspect)
SHELL := /bin/bash
HERE := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
SCRIPTS := build.sh app-entrypoint.sh app-build-assets.sh
TARGET_ARCH ?= native

.PHONY: check test build inspect

check:
	cd $(HERE) && for f in $(SCRIPTS); do bash -n $$f || exit 1; done
	cd $(HERE) && if command -v shellcheck >/dev/null; then shellcheck $(SCRIPTS); else echo 'shellcheck not installed: skipped'; fi
	cd $(HERE) && ./build.sh --check

test:
	cd $(HERE) && uv run --no-project --python 3.13 python -B -m unittest -v test_app_image_contract

build:
	@test -n "$(IMAGE_TAG)" || { echo 'set IMAGE_TAG=name:version'; exit 2; }
	cd $(HERE) && ./build.sh "$(IMAGE_TAG)" "$(TARGET_ARCH)"

inspect:
	@test -n "$(IMAGE)" || { echo 'set IMAGE=name:version'; exit 2; }
	@docker image inspect "$(IMAGE)" --format 'id:         {{.Id}}{{"\n"}}arch:       {{.Architecture}}{{"\n"}}user:       {{.Config.User}}{{"\n"}}ports:      {{range $$p, $$_ := .Config.ExposedPorts}}{{$$p}} {{end}}{{"\n"}}entrypoint: {{json .Config.Entrypoint}}{{"\n"}}cmd:        {{json .Config.Cmd}}{{"\n"}}workdir:    {{.Config.WorkingDir}}{{"\n"}}labels:{{"\n"}}{{range $$k, $$v := .Config.Labels}}  {{$$k}}={{$$v}}{{"\n"}}{{end}}'
