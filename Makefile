.PHONY: build build-release github-release local-release clean

IMAGE_NAME ?= "todoist-digest"
GITHUB_REPOSITORY ?= ""

# label is important here in order for the package to show up on the github repo
BUILD_CMD = nixpacks build . --name $(IMAGE_NAME) \
		--env NIXPACKS_PYTHON_VERSION \
		--env NIXPACKS_POETRY_VERSION \
		--label org.opencontainers.image.source=https://github.com/$(GITHUB_REPOSITORY) \
		--platform linux/arm64/v8 \
		--tag latest

build:
	$(BUILD_CMD)

build-debug:
	$(BUILD_CMD) --out .

docker-push: build
  if [ -z "$(GITHUB_REPOSITORY)" ]; then echo "GITHUB_REPOSITORY is not set" && exit 1; fi
	if [[ $(IMAGE_NAME) != *"ghcr"* ]]; then echo "IMAGE_NAME does not contain 'ghcr'" && exit 1; fi

	docker push $(IMAGE_NAME):latest