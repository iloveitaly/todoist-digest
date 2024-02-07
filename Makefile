.PHONY: build build-release github-release local-release clean

GITHUB_REPOSITORY ?= $(shell gh repo view --json nameWithOwner --jq '.nameWithOwner' | tr -d '[:space:]')
IMAGE_NAME ?= ghcr.io/$(GITHUB_REPOSITORY)
IMAGE_TAG ?= latest

# label is important here in order for the package to show up on the github repo
BUILD_CMD = nixpacks build . --name $(IMAGE_NAME) \
		--env NIXPACKS_PYTHON_VERSION \
		--env NIXPACKS_POETRY_VERSION \
		--label org.opencontainers.image.source=https://github.com/$(GITHUB_REPOSITORY) \
		--platform linux/arm64/v8 \
		--tag latest

build:
	$(BUILD_CMD)

build-shell: build
	docker run -it $(IMAGE_NAME):$(IMAGE_TAG) bash -c 'source /opt/venv/bin/activate'

build-debug:
	$(BUILD_CMD) --out .

docker-push: build
	docker push $(IMAGE_NAME):$(IMAGE_TAG)