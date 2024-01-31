SHELL := zsh

.PHONY: build build-release github-release local-release clean

IMAGE_NAME ?= "todoist-digest"
GITHUB_REPOSITORY ?= ""

# label is important here in order for the package to show up on the github repo
BUILD_CMD = nixpacks build . --name $(IMAGE_NAME) \
		--env NIXPACKS_PYTHON_VERSION \
		--env NIXPACKS_POETRY_VERSION \
		--label org.opencontainers.image.source=https://github.com/$(GITHUB_REPOSITORY) \
		--platform linux/arm64 \
		--tag latest

build:
	$(BUILD_CMD)

build-debug:
	$(BUILD_CMD) --out .
