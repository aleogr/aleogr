# go

Development environment blueprint for pure Go microservices. 

> Global setup steps, secrets management, and cost policies: [Global Guide](../README.md).

<br />

### Components & Tools Installed

* **Base Image:** `mcr.microsoft.com/devcontainers/go:1.26-bookworm` (Official Debian-based image).
* **I/O Optimization:** Anonymous Docker volumes mounted to cache `go build` targets and `go.mod` downloads, bypassing cloud I/O throttling.
* **Linter:** `golangci-lint` automatically installed on container boot via `postCreateCommand`.
* **Formatting:** Native `gofmt` and automatic import organization enabled on file save.

#### VS Code Extensions Bundled
* `golang.go` (gopls, autocomplete, code navigation, and test runner).
* `usernamehw.errorlens` (Inline compiler error and warning highlighting).
* `tamasfe.even-better-toml` (TOML configuration file validation).
