# ------------------ Default configuration ------------------ #

REGISTRY   := aleogr
PROJECT    := goapp
TAG        ?= latest
IMAGE_NAME := $(REGISTRY)/$(PROJECT)

# ------------------------ Help menu ------------------------ #

.PHONY: help
help: ## Display this help screen
	@echo "Usage: make [target]"
	@echo ""
	@echo "----------------- GO BUILD COMMANDS -----------------"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		grep "go-" | sort | awk 'BEGIN {FS = ":.*?## "}; \
		{printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "--------------- DOCKER BUILD COMMANDS ---------------"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		grep "docker-" | sort | awk 'BEGIN {FS = ":.*?## "}; \
		{printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'


# -------------------- Go Build Targets --------------------- #

.PHONY: go-build
go-build: ## Compile the whole project into dist/
	@echo "Building the project..."
	@go build -o dist/ ./cmd/...


.PHONY: go-build-app1
go-build-app1: ## Compile app1 into dist/
	@echo "Building app1..."
	@go build -o dist/ ./cmd/app1


.PHONY: go-clean
go-clean: ## Remove build artifacts
	@echo "Cleaning build artifacts..."
	@go clean
	@rm -rf dist/


.PHONY: go-reset
go-reset: ## Perform a deep clean (Go cache + dist)
	@echo "Performing deep reset (Go cache + dist)..."
	@go clean -cache -testcache -modcache
	@rm -rf dist/


.PHONY: go-test
go-test: ## Run all project tests
	@echo "Running tests..."
	@go test -v ./...


.PHONY: go-bench
go-bench: ## Run all benchmarks
	@echo "Running benchmarks..."
	@go test -v -bench=. ./...

# ------------------- Docker Build Targets ------------------ #

.PHONY: docker-build-app1
docker-build-app1: ## Build app1 image only
	@echo "Building Docker image: $(IMAGE_NAME)-app1:$(TAG)..."
	@docker buildx build \
		--platform linux/amd64 \
		--build-arg APP_NAME=app1 \
		-t $(IMAGE_NAME)-app1:$(TAG) \
		-f build/Dockerfile .
