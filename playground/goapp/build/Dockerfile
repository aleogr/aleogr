# ---------------------------------------------------------------- #

ARG APP_NAME

ARG TARGET_OS=linux
ARG TARGET_ARCH=amd64

ARG BUILDER_IMG_VERSION=latest
ARG RELEASE_IMG_VERSION=latest

# ---------------------------------------------------------------- #

FROM cgr.dev/chainguard/go:${BUILDER_IMG_VERSION} AS builder

ARG APP_NAME
ARG TARGET_OS
ARG TARGET_ARCH

ENV CGO_ENABLED=0 \
    GOOS=${TARGET_OS} \
    GOARCH=${TARGET_ARCH}

WORKDIR /build
COPY go.mod .
RUN go mod download
COPY . .
RUN go build -ldflags="-w -s" -o /app ./cmd/${APP_NAME}

# ---------------------------------------------------------------- #

FROM cgr.dev/chainguard/static:${RELEASE_IMG_VERSION} AS release

COPY --from=builder /app /usr/local/bin/app
ENTRYPOINT ["/usr/local/bin/app"]
