# Codespaces Reference Guide

Core settings, workflows, and cost-control steps for my dev environments.

---

## 🔄 Workflow Lifecycle (Feature-Branch)

Always treat Codespaces as ephemeral environments to avoid configuration drift and cut costs.

1. **Branch:** Create `feature/branch-name` on GitHub (never work on `main`).
2. **Launch:** Repository -> `<> Code` -> `Codespaces` -> `...` -> `New with options...` -> Select branch.
3. **Ship:** Code, commit, push, and open Pull Request.
4. **Cleanup:** After merging the PR, delete the environment at [github.com/codespaces](https://github.com/codespaces) to stop storage billing.

---

## 🔒 Secrets Management

Never hardcode credentials in `devcontainer.json` or source code.
* **Storage:** Add sensitive tokens in GitHub `Settings -> Secrets and variables -> Codespaces`.
* **Usage:** Access directly via environment variables inside the container (e.g., `os.Getenv("SECRET_NAME")`).

---

## 💰 FinOps & Cost Controls

To optimize the GitHub personal free tier quota:
* **Idle Timeout:** Set to 10-15 minutes in personal GitHub settings (`Settings -> Codespaces -> Default idle timeout`).
* **Storage:** Delete inactive environments regularly. Stopped containers still consume storage quota.

---

## 📁 Stack Blueprints
* [`/go`](./go/) - Go 1.26+ boilerplate environment.
