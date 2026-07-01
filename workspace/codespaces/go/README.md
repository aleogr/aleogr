# Blueprint: Go Pure (1.26+)

Development environment blueprint for pure Go microservices. 

> 📘 Global workflow, secrets, and cost policies: [Global Guide](../README.md).

## 🛠️ Components & Tools Installed

* **Base:** `mcr.microsoft.com/devcontainers/go:1.26-bookworm` (Official Debian image).
* **I/O Optimization:** Dedicated anonymous Docker volumes mounted to cache `go build` and `go.mod` downloads to bypass cloud I/O throttling.
* **Linter:** `golangci-lint` installed on container boot via `postCreateCommand`.
* **Format:** Integrated `gofmt` and auto-import organization on file save.

### VS Code Extensions Bundled
* `golang.go` (gopls, autocomplete, navigation).
* `usernamehw.errorlens` (Inline error/warning highlighting).
* `tamasfe.even-better-toml` (TOML validation).

## 🚀 How to Apply to a Project

1. Copy the structure below into the target repository root:
   ```text
   .devcontainer/
   └── go/
       ├── devcontainer.json
       └── README.md

2. Adjust the "image" tag version inside devcontainer.json if required by the project's go.mod.
