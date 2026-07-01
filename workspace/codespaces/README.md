# codespaces

Core settings, workflows, and cost-control steps for my dev environments.

<br />

## Workflow Lifecycle

Always treat Codespaces as ephemeral environments to avoid configuration drift and cut costs.

1. **Branch:** Create `feature/branch-name` on GitHub (never work on `main`).
2. **Launch:** Repository -> `<> Code` -> `Codespaces` -> `...` -> `New with options...` -> Select branch.
3. **Ship:** Code, commit, push, and open Pull Request.
4. **Cleanup:** After merging the PR, delete the environment at [github.com/codespaces](https://github.com/codespaces) to stop storage billing.

<br />

## Secrets Management

Never hardcode credentials in `devcontainer.json` or source code.
* **Storage:** Add sensitive tokens in GitHub `Settings -> Secrets and variables -> Codespaces`.
* **Usage:** Access directly via environment variables inside the container (e.g., `os.Getenv("SECRET_NAME")`).

<br />

## Cost Controls

To optimize the GitHub personal free tier quota:
* **Idle Timeout:** Set to 10-15 minutes in personal GitHub settings (`Settings -> Codespaces -> Default idle timeout`).
* **Storage:** Delete inactive environments regularly. Stopped containers still consume storage quota.

<br />

## Stack Templates
* [`/go`](./go/) - Go 1.26+ boilerplate environment.

<br />

## How to Apply

1. Go to the target repository root and create the `.devcontainer/` folder.
2. Copy the desired technology folder from this repository (e.g., `/go`) into it:

   ```text
   target-repo/
   └── .devcontainer/
       └── go/
           ├── devcontainer.json
           └── README.md
   ```
