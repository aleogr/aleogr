# DESIGN — aleogr/aleogr

> **Source of truth** for this repository. Every change of decision is recorded here first, and the READMEs of the affected folders are updated in the same commit.

## Contents

- [0. Context and terminology](#0-context-and-terminology)
- [1. Names](#1-names)
- [2. Structure of aleogr/aleogr](#2-structure-of-aleograleogr)
- [3. Public repository conditions](#3-public-repository-conditions)
- [4. CI/CD](#4-cicd)
- [5. Dev containers and Codespaces](#5-dev-containers-and-codespaces)
- [6. The lab, project environments and minimum cost](#6-the-lab-project-environments-and-minimum-cost)
- [7. Where data lives](#7-where-data-lives)
- [8. Family types](#8-family-types)
- [9. Family map](#9-family-map-direction-not-a-task-list)
- [10. Contract rules](#10-contract-rules-apply-to-all-families)
- [11. Project model](#11-project-model)
- [12. Skills of the `aleogr` orchestrator](#12-skills-of-the-aleogr-orchestrator)
- [13. Other components](#13-other-components)
- [14. Where I run Claude Code](#14-where-i-run-claude-code)
- [15. Tests](#15-tests)
- [16. Discarded decisions](#16-discarded-decisions)
- [17. Implementation strategy](#17-implementation-strategy)
- [18. Open items](#18-open-items)

---

## 0. Context and terminology

A personal Claude Code plugin marketplace to automate the setup of new projects (repository, cloud, DNS, stacks, platforms, services, CI/CD and development environment), which today I do manually by clicking through dashboards.

Everything lives in my GitHub profile repository, `aleogr/aleogr`, which has **four roles**:

1. GitHub profile (root `README.md`).
2. Claude Code plugin marketplace (`marketplace/`).
3. Reusable CI/CD: parameterized workflows and composite actions (`.github/`).
4. Dev Container Features for GitHub Codespaces (`.devcontainer/features/`).

All of this is **TOOLING** for my development laboratory (the "lab", at `lab.aleogr.dev`).

Personal premises:

- I practice "vibe coding" (I don't write code), but I want to be able to open a development environment on the web.
- Many projects in development at the same time.
- Always seek the **LOWEST POSSIBLE COST** in development.

Terminology (these are different things):

- **Project environment**: `lab`, `homolog`, `prod` ([section 6](#6-the-lab-project-environments-and-minimum-cost)).
- **Claude Code cloud environment**: the configuration where Claude Code cloud sessions run ([section 14](#14-where-i-run-claude-code)).

Working rules for this repository:

- **Language:** everything versioned in the repository — code, comments, documentation and commit messages — is written in **English**. Conversation with the assistant happens in Portuguese.
- Whenever a decision changes, update `docs/DESIGN.md` and the affected READMEs, and commit.
- NEVER create `.github/README.md`; do NOT change the root `README.md` (profile) without an explicit request.
- Do not create plugin folders nor implement plugins, skills, actions, workflows or Features without explicit instruction.

---

## 1. Names

### Marketplace and plugins

- Marketplace: `name` = `aleogr`. Repository: `aleogr/aleogr`.
- Orchestrator plugin: `aleogr` (e.g. `/aleogr:new-project`). Install id: `aleogr@aleogr`.
- Family plugins: `aleogr-<family>-<provider>` (e.g. `aleogr-repo-github`, `aleogr-cloud-gcp`, `aleogr-dns-cloudflare`, `aleogr-stack-go`).

### Skills

- Family skills: `<provider>-<action>`, defined by the skill's **FOLDER NAME** (e.g. `skills/github-create-repo/`). Full command: `/aleogr-repo-github:github-create-repo`, `/aleogr-cloud-gcp:gcp-create-environment`, `/aleogr-dns-cloudflare:cloudflare-add-record`, `/aleogr-stack-go:go-setup`.
- Cloud products carry the full provider: `aws-route53-add-record`, `gcp-cloud-sql-create-database`.
- **NO plugin `SKILL.md` has the `name:` field in its frontmatter.** The name comes from the folder and Claude Code applies the plugin prefix. Reason: there is a recurring bug (issue anthropics/claude-code#22063, resolved in March 2026 and reported again as a regression in June) in which the `name:` field makes the skill lose the plugin prefix; the plugin documentation advises against using `name:`.
- The provider in the skill name is an **ADDITIONAL and deliberate** protection: even if the `plugin:skill` namespace fails (regression, or a surface that shows skills without prefix), there is no collision between plugins. The redundancy in the command (`github` appears twice) is consciously accepted.
- Orchestrator skills have no technology and carry no provider (e.g. `/aleogr:declare-project`).
- Skill descriptions name the provider explicitly (Claude picks the skill for automatic invocation based on the description). Frontmatter example:

```markdown
---
description: Creates a GitHub repository using the gh CLI and configures the local remote. Use when starting a project hosted on GitHub.
---
```

- Never use names equal to Claude Code built-in commands (`init`, `doctor`, `status`, `review`, `context`, `config` etc.).

### marketplace.json

- The entry in `marketplace.json` and the `name` in `plugin.json` must be equal.
- Every `marketplace.json` entry has a `category` (e.g. `orchestrator`, `repo`, `cloud`, `dns`, `stack`) and a readable `displayName` (e.g. "GitHub (repository)"); optional `tags` for search.

### Workflows

- Reusable workflows: prefix by purpose (`ci-`, `deploy-`, `release-`).
- Workflows that run in this repository itself: prefix `self-`.

### Dev Container Features

- Own Features: named after the **TECHNOLOGY, WITHOUT prefix**, because the published address already works as a prefix: `ghcr.io/aleogr/aleogr/<id>` (e.g. `go`, `java`, `python`, `android`).
- The Feature common to all projects is called `base`.
- Direct correspondence with plugins: `aleogr-stack-go` ↔ Feature `go`; `aleogr-platform-android` ↔ Feature `android`.

### Claude Code cloud environments

- Named by **NEEDS PROFILE** (e.g. `lab`, `lab-android`), never by repository or project.

### Project and platform resources in the lab

- Project resources in the lab: services `<project>-<component>`, database `<project>` (normalized to the format accepted by the database), record `<project>.lab.aleogr.dev`, label `aleogr-project=<project>`.
- Lab platform resources: label `aleogr-platform=lab`.

### Tests

- Separate GitHub organization, with the **NAME STILL OPEN** (referred to here as `<test-org>`).
- One short random `<id>` per test, used in **ALL** of the test's resources:
  - repository `test-<id>`;
  - topic `aleogr-test`;
  - services `test-<id>-<component>`;
  - database `test_<id>`;
  - record `test-<id>.lab.aleogr.dev`;
  - label `aleogr-test=<id>`.
- The `test-` prefix is **RESERVED**: the schema and `declare-project` reject real project names starting with `test-`.

---

## 2. Structure of aleogr/aleogr

**Premise: clean root.** Only `README.md`, `docs/` and `marketplace/` are visible at the root; everything else lives in the dot folders required by convention (`.github/`, `.devcontainer/`).

The tree below is the **TARGET**; "(skeleton)" marks what exists since the first task.

```
aleogr/aleogr/
├── README.md                                  ← GitHub profile (do not touch without asking)
├── docs/
│   ├── DESIGN.md                              ← source of truth (skeleton)
│   └── cloud-environments/                    (future) canonical version of the Claude Code cloud environments
│       └── lab.md                             ← setup script, allowed domains, no IDs or secrets
├── .devcontainer/
│   ├── devcontainer.json                      ← environment of aleogr/aleogr itself (uses the local Features)
│   └── features/                              ← Dev Container Features distributed to projects
│       ├── README.md                          ← name by technology, installsAfter, base (skeleton)
│       ├── src/
│       │   ├── .gitkeep                       (skeleton; remove when the first Feature exists)
│       │   ├── base/                          ← present in every project
│       │   │   ├── devcontainer-feature.json
│       │   │   └── install.sh
│       │   ├── go/                            (only if there are preferences to add to the official one)
│       │   ├── java/                          (same)
│       │   └── python/                        (same)
│       └── test/
│           ├── .gitkeep                       (skeleton; remove when the first test exists)
│           ├── base/test.sh
│           └── go/ ...
├── .github/                                   ← NEVER create .github/README.md
│   ├── dependabot.yml                         ← updates action references of this repo
│   ├── actions/                               ← composite actions (subfolders allowed)
│   │   ├── README.md                          ← how to reference, actions-v1, SHA (skeleton)
│   │   ├── detect-changes/action.yml          (future)
│   │   ├── setup-go/action.yml                (future)
│   │   └── setup-java/action.yml              (future)
│   └── workflows/                             ← flat folder (GitHub requirement), organized by prefix
│       ├── README.md                          ← prefixes, workflow_call only, workflows-v1 (skeleton)
│       ├── self-validate-marketplace.yml      ← validates marketplace and example declarations on every PR
│       ├── self-lint.yml                      ← static checks of workflows and scripts on every PR
│       ├── self-test-features.yml             ← tests the Features (test/ folder) on every PR
│       ├── self-publish-features.yml          ← publishes the Features to GHCR
│       ├── self-cleanup-tests.yml             ← scheduled: deletes resources of old tests
│       ├── ci-go.yml                          (future, reusable)
│       ├── ci-java.yml                        (future, reusable)
│       └── deploy-cloud-run.yml               (future, reusable)
└── marketplace/                               ← marketplace root
    ├── README.md                              ← how to register the marketplace (skeleton)
    ├── defaults.json                          ← my personal defaults (choices only, no IDs) (future)
    ├── .claude-plugin/
    │   └── marketplace.json
    ├── schemas/
    │   ├── README.md                          ← purpose, versioning and examples of the schema (skeleton)
    │   ├── project.schema.json
    │   └── examples/                          ← example declarations (JSON only, fictitious values)
    │       └── go-gcp-cloudflare.json         (future)
    └── plugins/
        ├── README.md                          ← names, family types, plugin skeleton (skeleton)
        ├── aleogr/                            ← orchestrator (MVP)
        │   ├── .claude-plugin/plugin.json
        │   ├── skills/
        │   │   ├── check-environment/SKILL.md
        │   │   ├── declare-project/SKILL.md
        │   │   ├── plan-project/SKILL.md
        │   │   └── apply-project/SKILL.md
        │   ├── hooks/hooks.json               ← destructive command guard
        │   └── scripts/guard-destructive.sh
        ├── aleogr-repo-github/                (MVP)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/
        │       ├── github-create-repo/SKILL.md        ← contract
        │       ├── github-configure-repo/SKILL.md     ← contract
        │       ├── github-protect-branch/SKILL.md     ← contract
        │       ├── github-set-ci-secret/SKILL.md      ← contract
        │       ├── github-setup-ci/SKILL.md           ← contract
        │       └── github-install-claude-app/SKILL.md ← extra (future)
        ├── aleogr-cloud-gcp/                  (MVP)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/ gcp-create-environment, gcp-enable-services, gcp-setup-deploy
        └── aleogr-dns-cloudflare/             (MVP)
            ├── .claude-plugin/plugin.json
            ├── .mcp.json                      ← official Cloudflare MCP (https://mcp.cloudflare.com/mcp)
            └── skills/ cloudflare-add-record
```

### 2.1 Documentation rules

- One short `README.md` per folder that has local rules to explain, always pointing to the corresponding section of `docs/DESIGN.md` (source of truth).
- Prefer a README over `.gitkeep`, which is used only where a README would be repetitive (`.devcontainer/features/src/` and `test/`, where dev container tooling expects only Feature subfolders).
- **NEVER create `.github/README.md`**: GitHub looks for the README in `.github/`, then at the root and then in `docs/`, and a README in `.github/` would replace my profile's. READMEs in `.github/actions/` and `.github/workflows/` don't have this problem.
- Do not create a plugin folder before the plugin itself.

### 2.2 Marketplace structure rules

- `marketplace.json` lives at `marketplace/.claude-plugin/marketplace.json`. The marketplace root is `marketplace/` (the directory containing `.claude-plugin/`); `source` paths are relative to it (`./plugins/aleogr`), without `..`.
- Each plugin has `.claude-plugin/plugin.json` (only the manifest lives inside `.claude-plugin/`); `skills/`, `agents/`, `hooks/`, `scripts/` and `.mcp.json` live at the plugin root. Scripts are referenced with `${CLAUDE_PLUGIN_ROOT}`.
- Local validation: `claude plugin validate ./marketplace`. Local test: `claude plugin marketplace add ./marketplace`.
- **Do NOT use the `dependencies` field** to link the orchestrator to the family plugins: that would install every family in every project. Activation is decided by each project's declaration, via `sync-plugins`.

### 2.3 Registering the marketplace

Since `marketplace.json` is not at the repository root, `claude plugin marketplace add aleogr/aleogr` **does not work**. Registration is done in `extraKnownMarketplaces`, through four paths, depending on where Claude Code runs:

- **Local (Windows app):** by hand once per computer in `~/.claude/settings.json`; and by `sync-plugins` in each project's `.claude/settings.json` (family plugins in project scope).
- **Codespaces:** by the `base` Feature.
- **Claude Code cloud sessions:** by the cloud environment's SETUP SCRIPT ([section 14](#14-where-i-run-claude-code)). **WARNING:** cloud sessions do NOT install plugins or marketplaces declared in the repository's `.claude/settings.json` (`enabledPlugins`/`extraKnownMarketplaces`).
- **To test a branch:** add `"ref": "<branch>"` to `source`.

Settings block:

```json
{
  "extraKnownMarketplaces": {
    "aleogr": {
      "source": {
        "source": "github",
        "repo": "aleogr/aleogr",
        "path": "marketplace/.claude-plugin/marketplace.json",
        "sparsePaths": ["marketplace"]
      }
    }
  },
  "enabledPlugins": {
    "aleogr@aleogr": true
  }
}
```

- **Visibility (local):** the marketplace catalog shows all plugins; among installed ones, `aleogr` appears everywhere (user scope) and family plugins appear only in the projects that activated them (project scope).
- **Schema URL in projects:** `https://raw.githubusercontent.com/aleogr/aleogr/main/marketplace/schemas/project.schema.json`.

---

## 3. Public repository conditions

- The profile repository must be public; marketplace, actions, workflows and Features are public. They contain only **generic TOOLING, NEVER data** (see [section 7](#7-where-data-lives)). Example declarations in `marketplace/schemas/examples/` use fictitious values; `defaults.json` and `docs/cloud-environments/` contain only choices, no IDs or secrets.
- **Separate versions per product:**
  - prefixed tags for workflows and actions (`workflows-v1`, `actions-v1`);
  - the marketplace follows the default branch and the `plugin.json` versions;
  - each Feature has its own semver version in `devcontainer-feature.json`, published to GHCR (independent of Git tags);
  - in projects, `uses:` are pinned by SHA (Dependabot/Renovate update them).
- Reusable workflows have only `on: workflow_call`, so they don't run on every commit in this repository.
- **Protection matching the reach:** `main` protected (require PR, even working alone), 2FA, SHAs pinned in consumers.
- Composite actions are referenced as `aleogr/aleogr/.github/actions/<name>@<sha>` (or `./.github/actions/<name>` within this repo). Publishing an action on the GitHub Marketplace would require its own repository; that is not the goal.
- Being public is deliberate and brings advantages on GitHub's free plan:
  - branch protection available;
  - unlimited Actions minutes on standard runners;
  - workflows and actions usable by repositories of other owners (such as the test organization);
  - Features and schema readable without authentication.

---

## 4. CI/CD

- The reusable pieces live in `aleogr/aleogr`; each project has **THIN** workflows generated by the `<provider>-setup-ci` skill of the `repo-*` plugin (on GitHub, `github-setup-ci`), which only call the reusable ones with parameters.
- **A single `.github/workflows/ci.yml` per project:**
  - a `changes` job detects what changed (initially `dorny/paths-filter` pinned by SHA; candidate to become the composite action `aleogr/aleogr/.github/actions/detect-changes`, which receives the list of components);
  - one job per component, with `needs: changes` and `if:` on the corresponding output, calling its stack's reusable workflow (e.g. `aleogr/aleogr/.github/workflows/ci-go.yml@<sha>` with `working-directory` and `go-version`);
  - two components of the same stack = two jobs calling the same reusable workflow.
- **Do NOT use one workflow per component with `on.push.paths`:** the native filter applies to the whole workflow, and a workflow that didn't trigger leaves the required check pending forever, blocking the PR. A job skipped by `if:` counts as success.
- Secrets are passed explicitly by name to reusable workflows (**do not use `secrets: inherit`**), making visible in the project what each one receives.
- Deploy in `cd.yml` (or later jobs of the same file) with `needs:` on the component's CI and a condition to run only on `main`. With multiple project environments ([section 6](#6-the-lab-project-environments-and-minimum-cost)), `cd.yml` deploys to `lab` and promotes to the following environments.
- **Future GitLab:** reusable workflows and composite actions only serve GitHub Actions. A `gitlab-setup-ci` would need pipeline templates.
  - Preferred option (fewer repositories): templates in `aleogr/aleogr` itself (e.g. `.gitlab/ci/`), included in projects by public URL.
  - Alternative: CI/CD components from the GitLab catalog (requires a project hosted on GitLab).
  - Decide only when there is a real project on GitLab.

---

## 5. Dev containers and Codespaces

- Codespaces reads the `.devcontainer/devcontainer.json` of the opened repository; each project has its own, **THIN**, generated by the orchestrator from the declaration. What is reusable are the Dev Container Features (open standard: they work in Codespaces, local VS Code and JetBrains IDEs).
- Every project gets: the official Claude Code Feature (`ghcr.io/anthropics/devcontainer-features/claude-code:1.0`) and `ghcr.io/aleogr/aleogr/base:1`.
- **`base`:** registers the `aleogr` marketplace (block from [section 2.3](#23-registering-the-marketplace)) in Claude Code's user settings inside the container, so the orchestrator is available in any codespace, even an empty one, and brings what is common to all projects. The `base` Feature (Codespaces) and the setup script of the `lab` cloud environment (Claude Code cloud sessions, [section 14](#14-where-i-run-claude-code)) have the **SAME responsibility, in two vehicles**; keep both consistent.
- **Per-technology Features** (`go`, `java`, `python`, `android`...) are a **PREFERENCES LAYER** over the official Features (e.g. `ghcr.io/devcontainers/features/go`): linters, formatter, language server, debugger, editor extensions. **They do NOT reinstall the language.** They declare `"installsAfter": ["ghcr.io/devcontainers/features/<technology>"]` to run after the official one.
- **Do NOT use `dependsOn` for the official one:** a dependency's options are fixed in the Feature definition, and the version declared in project.json would not reach the installed language. The generated `devcontainer.json` lists BOTH, with the version on the official one:

```json
"features": {
  "ghcr.io/devcontainers/features/go:1": { "version": "1.23" },
  "ghcr.io/aleogr/aleogr/go:1": {},
  "ghcr.io/anthropics/devcontainer-features/claude-code:1.0": {},
  "ghcr.io/aleogr/aleogr/base:1": {}
}
```

- A technology's folder only exists if I have something to add. If the official one is enough, the `stack-*` contributes only that.
- **Claude Code authentication in codespaces:** `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` (generated with `claude setup-token`) stored as a Codespaces secret.
- **Layout:** Feature sources in `.devcontainer/features/src/<id>/` and tests in `.devcontainer/features/test/<id>/` (layout expected by the dev containers CLI). The subfolder has the same name as the `id`. The `devcontainer.json` of `aleogr/aleogr` itself references the local Features by relative path (e.g. `./features/src/base`) to test before publishing.
- **Publishing** via `self-publish-features.yml` to GHCR (namespace `aleogr/aleogr`). GHCR packages are born private: mark each Feature as public on first publication.
- Projects' `devcontainer.json` is a **shared file**: each stack/platform contributes its entries in `features` without touching the others. Monorepo: a single `devcontainer.json` by default; one per component (`.devcontainer/<component>/devcontainer.json`) when some platform declares a heavy or conflicting toolchain.
- What is specific to Codespaces (Codespaces secrets, prebuilds) are extra skills of `aleogr-repo-github` (e.g. `github-configure-codespaces`).
- iOS/watchOS (macOS) and firmware (physical device) don't build in a codespace: the devcontainer is for editing and using Claude Code; the build happens in CI (macOS runner) or in the Windows app. The `platform-*` records this limit.
- **Do NOT use `aleogr/aleogr` as the Codespaces dotfiles repository** (it would require a script at the root or links to the dot folders); `base` achieves the goal.
- **Cost:** set a spending limit and quick idle shutdown in Codespaces.
- Codespaces complements Claude Code on the web: it adds a full editor, a running application and port preview.

---

## 6. The lab, project environments and minimum cost

- I own the domain `aleogr.dev`. The lab (`lab.aleogr.dev`) is **EVERYTHING that is not production**: development and staging of my projects and the tests of the tooling itself.

### 6.1 Addresses of a project's environments

- **`lab`** (development): `<project>.lab.aleogr.dev`; tenants: `<tenant>.<project>.lab.aleogr.dev`, served by the wildcard `*.<project>.lab.aleogr.dev` (per-tenant routing is done by the application, by hostname).
- **`homolog`** (optional): environment as a **SUFFIX** of the project, `<project>-homolog.lab.aleogr.dev`, with its own wildcard `*.<project>-homolog.lab.aleogr.dev`. Never `homolog.<project>.lab...`, which would be confused with a tenant and captured by the project's wildcard.
- **`prod`** (optional): the project's own domain or, without one, `<project>.aleogr.dev` (first-level subdomain, covered by Cloudflare's free certificate).
- The orchestrator derives the names from the project name and the environment; I only declare which environments the project has.

Declaration (replaces a simple `domains` field):

```json
"environments": {
  "lab":     { "host": "project2.lab.aleogr.dev",         "tenants": "wildcard" },
  "homolog": { "host": "project2-homolog.lab.aleogr.dev", "tenants": "wildcard" },
  "prod":    null
}
```

### 6.2 HTTPS and certificates

- `.dev` requires HTTPS (the domain is on browsers' HSTS preload list): there is no HTTP, not even in development.
- Cloudflare's free Universal SSL covers only the root domain and the first subdomain level. `project1.lab.aleogr.dev` (second level) and tenants (third level), with proxy on, are **NOT covered** and fail with errors like `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`.
- Ways out: Advanced Certificate Manager (paid) with Total TLS or advanced certificates; or unproxied records, with the certificate issued by the destination.
- The solution used today in my lab is **PENDING** investigation ([section 18](#18-open-items)).

### 6.3 Protection and single access point

- **Lab protection:** Cloudflare Access requiring login for `*.lab.aleogr.dev` (requires proxied records). Extra skill of the Cloudflare plugin, applied once for the whole lab. External testers are added by e-mail to the rule.
- **Single access point:** today I access all lab projects through a single access point, WITHOUT a load balancer. The current implementation is **PENDING** investigation ([section 18](#18-open-items)). If it is a single routing point (e.g. a Cloudflare Worker routing by hostname), adding a project to the lab becomes "adding a route" at that point, with a single DNS wildcard configured once; the dns-* contract in the lab will be adjusted according to the result.

### 6.4 Lab platform × project resources

- **Lab platform:** created ONCE and shared by all projects in development (e.g. a single Cloud SQL instance, the single access point under `lab.aleogr.dev`, the DNS wildcard, Access protection, the lab's secret vault). Each cloud provider (GCP, AWS, Azure) has its own version of the lab platform, with the same logic.
- **Project resources:** created INSIDE the platform (e.g. database + user on the shared instance, service in the lab's cloud environment, route in the single access point, secrets prefixed with the project).
- The family contract gains the `shared` or `dedicated` mode; in the `lab` project environment the default is `shared`. E.g. db-* in the lab creates database + user on the single instance; in production, its own instance.
- Isolation within shared resources by name and labels ([section 1](#1-names)); a project's `plan-project` sees only what is its own; `remove-*` never touches what belongs to another.

### 6.5 Minimum cost (contract rule in the `lab` project environment)

- Scale to zero whenever possible.
- Smallest tier/size available.
- Nothing with fixed cost per project (load balancer, static IP, NAT, dedicated instances).
- Warn and ask for confirmation before creating anything with a fixed cost.
- Budget alerts configured on each provider's lab platform.

### 6.6 Personal defaults

- In `marketplace/defaults.json` (public, choices only, no IDs), read by `declare-project` to pre-fill declarations: lab domain (`lab.aleogr.dev`), GitHub owner, preferred cloud and region, DNS provider, which services the lab platform shares.

---

## 7. Where data lives

- **There will be NO private `aleogr/lab` repository, nor tooling in a private repository.** Lab platform data is split into three types:

| Type | Where it lives | Publicly visible? |
|---|---|---|
| Secrets (passwords, tokens, keys) | the provider's `secrets-*` (e.g. GCP Secret Manager) + GitHub Actions/Codespaces secrets when workflows or codespaces need them + network secrets of the Claude Code cloud environment ([section 14](#14-where-i-run-claude-code)) | no |
| Identifiers (lab cloud project ID, DNS zone ID...) | naming convention (preferred) + GitHub Actions variables in `aleogr/aleogr`, read with `gh variable get` | no |
| Lab platform state | discovered in the cloud itself via labels and names (the cloud is the source of truth); if not enough, a state file in a private versioned bucket | no |
| Tooling | `aleogr/aleogr` | yes, on purpose |

- GitHub secrets cannot be read back: they serve to deliver credentials to workflows/codespaces, not to store information the orchestrator queries.
- Actions variables are not publicly visible even in a public repository, but logs of public workflows are: **no workflow may print variables**.
- Environment variables of Claude Code cloud environments are readable by whoever uses the environment: **never put secrets in them**.
- **Discovery rules:**
  - label on everything that accepts labels (`aleogr-platform`, `aleogr-project`, `aleogr-test`);
  - name by convention ALWAYS (it is the identifier of resources without labels, such as databases inside the shared instance and DNS records);
  - variables only for what cannot be deduced (ideally only IDs chosen once).
- The platform's change history comes from the hooks' audit log and the providers' audit logs; decisions are versioned in Git (`defaults.json`).
- PROJECT data (`project.json`, `state.json`) stays in each project's repository. **Open question:** apply the same discovery principle to projects, making `state.json` lighter or just a cache (see in practice, with the MVP).

---

## 8. Family types

- **Exclusive:** one provider per project (or per domain).
- **Combinable:** several at the same time.
- **Scope:** project, component (directory or repository) or domain.

---

## 9. Family map (direction, NOT a task list)

| Family | Representatives | Type | Scope |
|---|---|---|---|
| repo-* | github, gitlab, bitbucket | exclusive (no mirroring) | project |
| cloud-* | aws, azure, gcp | combinable, with exactly one primary | project |
| secrets-* | aws-secrets-manager, gcp-secret-manager, azure-key-vault | exclusive | project |
| tracker-* | jira, linear, asana | exclusive | project |
| wiki-* | confluence, notion, gitbook | exclusive | project |
| notify-* | slack, microsoft-teams, discord | combinable | project |
| registrar-* | godaddy, namecheap, cloudflare | exclusive per domain | domain |
| dns-* | cloudflare, aws-route53, gcp-cloud-dns | exclusive per domain | domain |
| cdn-* | cloudflare, akamai, aws-cloudfront | exclusive per domain | domain |
| db-* | aws-rds, gcp-cloud-sql, azure-sql | combinable | project |
| cache-* | aws-elasticache, gcp-memorystore, redis-cloud | exclusive | project |
| storage-* | aws-s3, gcp-storage, azure-blob | combinable | project |
| registry-* | docker-hub, ghcr, aws-ecr | exclusive | project |
| hosting-* | vercel, netlify, cloudflare-pages | combinable | component |
| search-* | elastic, algolia, aws-opensearch | exclusive | project |
| auth-* | auth0, firebase-auth, aws-cognito | exclusive | project |
| email-* | sendgrid, aws-ses, mailgun | exclusive | project |
| sms-* | twilio, vonage, sinch | exclusive | project |
| push-* | fcm, apns, onesignal | combinable | component |
| payments-* | stripe, paypal, adyen | combinable | project |
| llm-* | anthropic, openai, google-gemini | combinable | project |
| flags-* | launchdarkly, unleash, flagsmith | exclusive | project |
| monitoring-* | sentry, datadog, new-relic | combinable | project |
| analytics-* | google-analytics, mixpanel, amplitude | combinable | component |
| stack-* | typescript, python, java (and go etc.) | combinable | component |
| platform-* (mobile) | android, ios, harmonyos | combinable | component |
| platform-* (desktop) | windows, macos, linux | combinable | component |
| platform-* (embedded) | zephyr, esp-idf, stm32cube | combinable | component |
| platform-* (wearable) | wearos, watchos, garmin-connect-iq | combinable | component |
| store-* | google-play, apple-app-store, microsoft-store | combinable | component |
| publish-* | npm, pypi, maven-central | combinable | component |

Notes:

- Representatives are for reference, not a precise ranking; independent alternatives (Vault, 1Password, Doppler, Supabase, Neon, Clerk, Flathub etc.) may make more sense.
- Web is not a platform (it is stack + hosting).
- CI belongs to repo-*; container deployment to cloud-*.

---

## 10. Contract rules (apply to all families)

### 10.1 Contracts

Each family has a contract: the same ACTIONS, with the same kind of result, across providers; the skill is named `<provider>-<action>`. The orchestrator builds the name by joining the provider (from the declaration) with the action (fixed in the contract). Current contracts:

- **repo-\***:
  - `<provider>-create-repo` (URL and remote);
  - `<provider>-configure-repo` (merge, features);
  - `<provider>-protect-branch` (rules on the main branch);
  - `<provider>-set-ci-secret` (repo or org/group level);
  - `<provider>-setup-ci` (thin pipeline per component).
  - E.g. `github-create-repo` ↔ `gitlab-create-repo`.
- **cloud-\***:
  - `<provider>-create-environment` (returns the environment ID);
  - `<provider>-enable-services`;
  - `<provider>-setup-deploy` (returns the public hostname).
  - Proposal: "environment" instead of "project", because clouds have different concepts (project on GCP, account on AWS, subscription/resource group on Azure).
- **dns-\***: `<provider>-add-record` (receives name + target). In the lab, it may become "add a route to the single access point" ([section 6.3](#63-protection-and-single-access-point)).
- **stack-\***: `<technology>-setup` (receives the component directory).

### 10.2 Mode, names and labels

- Every family skill accepts the `shared` mode (inside the lab platform) or `dedicated` (own resources); in the `lab` project environment, the default is `shared`.
- Every skill applies the labels and conventional names from [section 1](#1-names) to EVERYTHING it creates.

### 10.3 Extending contracts

- The contract is the common MINIMUM; plugins may have extra skills, following the same naming convention (e.g. `github-install-claude-app`, `github-configure-codespaces`, `cloudflare-protect-lab`).
- Contracts are only extracted when a second real provider exists; do not invent them in the abstract.
- When a feature depends on the provider's plan and is not available, the skill warns and records it as an open item in the checklist, instead of failing or pretending it was applied.

### 10.4 Behavior of every skill

- Checks before creating (idempotent).
- Shows each command before running it.
- Stops and asks for confirmation before irreversible or costly actions.
- Follows the MINIMUM COST rule in the lab ([section 6.5](#65-minimum-cost-contract-rule-in-the-lab-project-environment)).
- Ends with a verification (e.g. `gh repo view`, `gcloud ... describe`, DNS lookup).
- What cannot be automated becomes a checklist.
- platform-* skills start by checking the environment (OS, SDK, connected device).

### 10.5 Tools and dependencies between families

- CLI first (gh, glab, gcloud, aws, az); MCP when there is no good CLI or the official MCP is better. The MCP goes in the family plugin's `.mcp.json`.
- cloud-* provides the base (account/project, identities, permissions, APIs, deploy); service families assume the base exists. The orchestrator guarantees the order.
- secrets-* is unique per project, usually on the primary cloud; credentials for other clouds also live there. In the lab, project secrets live in the lab platform's vault, prefixed with the project.

### 10.6 "What/how" split

- **stack-\*** provides the language version, build/test/lint commands, cache and devcontainer Features (the official one and, if it exists, my preferences layer).
- **platform-\*** provides toolchain, required runner, Features and limits (what doesn't run in a codespace).
- **repo-\*** generates the workflow in the platform's format (`<provider>-setup-ci`; on GitHub, thin workflows calling the reusable ones from `aleogr/aleogr`).
- **The orchestrator** assembles the `devcontainer.json`.
- CI and devcontainer come from the SAME declaration: the declared language version goes both to the workflow parameter and to the devcontainer's official Feature, avoiding drift. Changing it in project.json + apply-project updates both.

### 10.7 Shared files and stack hooks

- Shared files at the project root (.gitignore, .editorconfig, pre-commit, Dependabot/Renovate, devcontainer.json) receive contributions:
  - in text files, marked sections (`# >>> aleogr-stack-go` ... `# <<< aleogr-stack-go`);
  - in structured files, each contributor adds/updates only its own entries;
  - never replacement.
- Stack hooks filter by file extension and exit silently if it is not their language.

### 10.8 Special-care families (payments, registrar, store)

- Test mode by default.
- No purchase, production or store submission without explicit confirmation.
- Signing keys only via secrets-*.

---

## 11. Project model

- **Personal preference:** the SMALLEST possible number of repositories. Monorepo whenever it makes sense; in multi-repo projects, prefer the federated layout (creates no extra repository).
- A project is a list of components (stack, platform, deploy/distribution, location = directory or repository), the project environments ([section 6](#6-the-lab-project-environments-and-minimum-cost)) and the project's shared services.
- **Declaration** in `.aleogr/project.json` in the project repository (what I WANT; edited by me or by the `declare-project` skill). **State** in `.aleogr/state.json` (what EXISTS; only the orchestrator writes it). Neither stores secrets, only references.
- The **lab platform** is managed by the same orchestrator, with the same declaration format (marked as `"kind": "platform"`), but without its own repository: choices in `defaults.json`, identifiers by convention and variables, state discovered in the cloud ([section 7](#7-where-data-lives)). Projects point to it in the `lab` project environment.

### 11.1 JSON Schema

- In `marketplace/schemas/project.schema.json` (versioned; `version` field in project.json; `$schema` for autocomplete).
- Exclusive families = object; combinable = list.
- Exactly one `primary` cloud (contains + minContains/maxContains = 1).
- payments `mode` with default "test".
- Project names cannot start with `test-`.
- `environments` field ([section 6.1](#61-addresses-of-a-projects-environments)).
- Plugin name derived from family + provider.
- Each family plugin may publish a sub-schema for its options.
- Optional `notes` field (JSON does not accept comments).

### 11.2 Supported layouts (same format)

- **monorepo:** one project.json at the root.
- **manifest:** a PRIVATE repository containing only the full declaration; components point to it; never `aleogr/aleogr`.
- **federated:** each repository has its fragment with `"layout": "federated"`; members found by topic (e.g. `aleogr-my-project`); idempotent creation; removing a shared service checks all members first.
- First of all, decide whether it is ONE project (shares services) or SEVERAL related projects (each with its own declaration).

### 11.3 Activating family plugins

- **Local (Windows app):** in PROJECT SCOPE (versioned `.claude/settings.json`, with the `extraKnownMarketplaces` block from [section 2.3](#23-registering-the-marketplace)), according to the declaration. In multi-repo, each repository activates only the families that concern it.
- **Claude Code cloud sessions:** the repository's `.claude/settings.json` does NOT install plugins in them. Plugins arrive through the cloud environment's setup script ([section 14](#14-where-i-run-claude-code)). How family plugins get there is **PENDING** ([section 18](#18-open-items)).
- **What the repository brings to cloud sessions** (single-repository session): `CLAUDE.md`, `.claude/skills/`, `.claude/agents/`, `.claude/commands/`, `.claude/rules/`, hooks and permissions from `.claude/settings.json`, `.mcp.json`.

---

## 12. Skills of the `aleogr` orchestrator

- **Core:**
  - `declare-project`: edits project.json through questions, pre-filling from `defaults.json`, without executing;
  - `plan-project`: compares declaration, state and reality; changes nothing;
  - `apply-project`: executes the plan in order.
- **Shortcuts:** `new-project`, `add-component`, `add-service`.
- **Maintenance:**
  - `check-environment`: CLIs, authentication, MCPs, devices; identifies whether it runs locally, in a codespace or in a cloud session and warns about what is not possible there;
  - `sync-plugins`: writes `extraKnownMarketplaces` and installs/disables family plugins in project scope;
  - `remove-component`, `remove-service`: stop before deleting, asking for confirmation.
- **Marketplace** (perhaps in a separate `aleogr-dev` plugin, open decision):
  - `create-plugin`: generates the skeleton already following the standard (names, mandatory `category` and `displayName`, contract skills);
  - `validate-marketplace`.

### 12.1 What `validate-marketplace` checks

`validate-marketplace` (and the `self-validate-marketplace.yml` workflow, on every PR) checks:

- `claude plugin validate ./marketplace`;
- family skills in the `<provider>-<action>` format;
- NO `name:` in the frontmatter of `SKILL.md` files inside `marketplace/plugins/`;
- no skill name equal to a built-in command;
- `marketplace.json` entry equal to the `plugin.json` `name`;
- `category` and `displayName` present;
- mandatory contract skills present in each family plugin;
- declarations in `marketplace/schemas/examples/` valid against the schema.

### 12.2 Apply order

1. Repositories.
2. Domain registration.
3. Cloud base (or verification of the lab platform).
4. Secrets.
5. Infrastructure (db, cache, storage, registry, search).
6. Services (auth, email, sms, payments, llm, flags).
7. Components (stack, platform, hosting, push), including devcontainer.json.
8. DNS, routes and CDN (collects records from previous steps).
9. Operations (monitoring, analytics, notify).
10. CI/CD (thin ci.yml and cd.yml, secrets).
11. Distribution (store, publish).
12. Final `plan-project` must say "nothing to do".

---

## 13. Other components

### 13.1 Hooks

Deterministic guarantees; general ones live in `aleogr`, specific ones in each family.

- **PreToolUse on Bash** blocking destructive commands (deleting a project/repo, public visibility, removing DNS, dropping a database, removing services) outside a confirmed remove-*. **NARROW** exceptions, only for test resources listed in a test's state:
  - repositories (test organization + name `test-<id>` + topic `aleogr-test` + NOT archived);
  - DNS records `test-<id>` or `test-<id>-<environment>` under `lab.aleogr.dev`, and the tenants below them;
  - databases `test_<id>`;
  - cloud services/resources `test-<id>-...` with label `aleogr-test=<id>`.
- **PreToolUse on Write/Edit** blocking secrets in versioned files.
- **PostToolUse on Write/Edit** validating project.json against the schema.
- **PostToolUse formatting** per stack.
- **SessionStart** injecting a summary of the declaration and manual open items.
- **PostToolUse on Bash** recording an audit log of infrastructure commands (also the lab platform's history).
- Hooks in the repository's `.claude/settings.json` also run in single-repository cloud sessions; to run something only in the cloud, check `CLAUDE_CODE_REMOTE=true`.

### 13.2 Agents

- Per-family executors (isolate the CLIs' verbose output).
- Independent auditor without write tools, which verifies the final state without having seen the execution.
- Plan reviewer before apply.
- Plugin agents cannot declare hooks, mcpServers or permissionMode.

### 13.3 LSP servers

- Each stack-* brings its language server (e.g. gopls).

### 13.4 Commands

- Not used; everything is a skill.

### 13.5 Settings/permissions

- `allow` for read-only commands (gh repo view, gh variable get, gcloud ... describe/list).
- `ask` for what creates or changes.
- `deny` for what must never run.

### 13.6 Projects' CLAUDE.md

- Short; points to `.aleogr/project.json`, says not to edit `state.json` by hand, keeps conventions.
- Per-directory CLAUDE.md with each stack's conventions.

### 13.7 Future

- Scheduled (weekly) GitHub Action running plan-project on projects and opening an issue on drift.

---

## 14. Where I run Claude Code

- I use Claude Code in the Windows app and on the web (cloud sessions), and I want to be able to use GitHub Codespaces.
- Infrastructure setup (creating repositories, gcloud auth login, Cloudflare OAuth, gh auth login) is done in the **WINDOWS APP**. Avoid storing admin-level credentials in the cloud.
- iOS/watchOS require macOS (build via macOS runner in CI); embedded and wearables usually require the device connected to the Windows app.

### 14.1 Claude Code cloud sessions (web, app, mobile, `claude --cloud`)

- They run on a fresh Ubuntu machine for each session, with the repository cloned and common tools preinstalled (including `gh`, Go, Java 21, Node, Python, Docker, PostgreSQL, Redis).
- What arrives from the repository: see [section 11.3](#113-activating-family-plugins).
- What does **NOT** arrive: plugins and marketplaces from the repository's `.claude/settings.json`; my personal `~/.claude/` (CLAUDE.md, skills, user plugins); MCPs added at local/user scope; interactive login (SSO).
- **GitHub in cloud sessions:** operations go through a proxy that keeps my credentials outside the machine. `gh` is installed, but:
  - the API only serves repositories ATTACHED to the session (others get 403);
  - GraphQL calls are rejected, which breaks `gh pr` and `gh issue`, even with your own `GH_TOKEN`;
  - use `gh api` (REST) for attached repositories.
  - Therefore, **creating and configuring new repositories is NOT a job for cloud sessions**.

### 14.2 Claude Code cloud environments

The configuration in which each cloud session runs.

- Each environment defines:
  - network access (None, Trusted, Full or Custom);
  - environment variables (readable by whoever uses the environment: **NEVER secrets**);
  - network secrets (keys attached by the proxy to requests to the listed hosts, invisible to the session; for APIs with a fixed token, such as Cloudflare's);
  - setup script (runs as root before Claude Code starts; cached if it finishes within about 5 minutes; cache rebuilt when the script changes and expires after about 7 days).
- They are **PERSONAL** (belong to my account) and do **NOT belong to repositories**; the choice is per session (selector on web/app; `/remote-env` sets the command-line default; `remote.defaultEnvironmentId` in a project's `.claude/settings.json` pins the environment of sessions started with `claude --cloud` in that project). Environments shared with an organization only exist on Team/Enterprise plans.
- **GOOD PRACTICE:** one environment per NEEDS PROFILE, never per repository or project (avoids duplicated identical scripts).

#### `lab` environment (default, the only one at first)

- Custom network: default package manager list + domains the sessions need to reach (e.g. `*.lab.aleogr.dev`).
- Setup script: registers the `aleogr` marketplace and installs the orchestrator (`claude plugin marketplace add` + `claude plugin install`), and writes my personal `~/.claude/CLAUDE.md`. Same responsibility as the `base` Feature ([section 5](#5-dev-containers-and-codespaces)); keep them consistent. Test whether plugin installation works at this stage.
- Network secrets for APIs with a fixed token; variables only with non-sensitive values.

#### Additional environments

- ONLY when a truly different profile appears: heavy toolchain (e.g. `lab-android` with the Android SDK, keeping the `lab` script under the cache limit) or different network (e.g. one without network, for reviewing third-party code).

#### Canonical version

- Environments are configured in the claude.ai interface, not by file. The CANONICAL version (setup script, allowed domains, description of network secrets without values) is versioned in `docs/cloud-environments/<environment>.md` in `aleogr/aleogr`, without IDs or secrets, and copied to the interface when it changes.

---

## 15. Tests

> This section records the **DIRECTION** of the tests. Execution details are still open and will be defined before implementation; **do not implement anything from this section without confirmation**.

Tests test the **TOOLING** (`aleogr/aleogr`), not my products: "if I run `/aleogr:new-project` with this declaration, does a working project come out?". Not to be confused with the `homolog` project environment, which tests a product. Tests are a lab activity and use the **LAB PLATFORM** (zero extra infrastructure cost and realism: they exercise the same sharing as real projects).

### 15.1 Layer 1 — in the repository itself (static, creating nothing outside), on every PR

- `self-validate-marketplace.yml`: validation of the marketplace and naming rules, and of the example declarations against the schema.
- `self-lint.yml`: static checks of workflows and hook scripts.
- `self-test-features.yml`: Feature tests with the dev containers CLI, using `.devcontainer/features/test/`.
- The only "tests folder" in the repository is `marketplace/schemas/examples/`, with the test INPUTS (declarations with fictitious values), never projects with code.

### 15.2 Layer 2 — local development

- Load a plugin straight from its folder with `--plugin-dir`, or register the local marketplace with `claude plugin marketplace add ./marketplace`, and experiment in a test folder in the Windows app. Nothing is published.

### 15.3 Layer 3 — end to end

The test OUTPUTS (the created projects) live **OUTSIDE** `aleogr/aleogr`, because only a real repository reproduces what is tested: repository creation and protection, secrets, workflows (GitHub only runs those at the root; cross-repository calls must be exercised), Codespaces and `.claude/settings.json` (read from the root). Tests inside `aleogr/aleogr` would also change the repository's own protection and secrets and pollute its history.

- Separate GitHub organization (`<test-org>`, name open), free: test repositories never show up in my personal account, and organization-level secrets can be tested. Address: `github.com/<test-org>/test-<id>`.
- Run from the **WINDOWS APP** (repository creation doesn't work in cloud sessions, [section 14](#14-where-i-run-claude-code)).
- Test what is in the PR's **BRANCH**, before merge:
  - reusable workflows referenced by branch name (`@<branch>`);
  - marketplace registered with `"ref": "<branch>"`;
  - Features tested by layer 1 (and, if needed, published with a pre-release version).
- Each test uses an `<id>` in ALL resources ([section 1](#1-names)): repository `test-<id>`, services `test-<id>-<component>` in the lab's cloud environment, database `test_<id>` on the shared instance, `test-<id>.lab.aleogr.dev` (with project environments: `test-<id>-<environment>.lab.aleogr.dev`; tenants: `<tenant>.test-<id>.lab.aleogr.dev`).
- **The test:** run `/aleogr:new-project` with a declaration from `marketplace/schemas/examples/`; check:
  - green CI;
  - address responding (and tenants, if any);
  - codespace opening with the right tools;
  - a Claude Code cloud session in the `lab` environment working on the created repository;
  - final `plan-project` saying "nothing to do".
- **Example scenarios:**
  - simple backend (1 component, 1 project environment);
  - multi-tenant monorepo (2 components, wildcard, CI running only the changed component's job);
  - two project environments (lab + homolog, with promotion in cd.yml);
  - Android app (only repository, CI and devcontainer, no DNS or cloud).
- Not every test needs a new repository: skills that only touch files of an existing project can use a FIXED test repository in the organization, reused on each run.
- Initially run manually; automate later, if it makes sense.

### 15.4 Payments

- Always in test mode.

### 15.5 Cleanup

The scheduled workflow `self-cleanup-tests.yml` deletes tests older than a few days, in this order:

1. Read the `state.json` of the `test-<id>` repository.
2. Delete the external resources (cloud, also checking the label `aleogr-test=<id>`; DNS records/routes matching the pattern; databases `test_<id>`; codespaces).
3. Delete the repository LAST (the state is in it).

The destructive command guard has exceptions ONLY for these cases ([section 13.1](#131-hooks)).

---

## 16. Discarded decisions

- Dedicated marketplace repository (`aleogr-claude-plugins`): replaced by `aleogr/aleogr`.
- Tooling in a private repository (`aleogr/lab` with everything): on the free plan it would lose branch protection, unlimited Actions minutes and use of the workflows by repositories of other owners (such as the test organization), and would complicate Features, schema and marketplace.
- Private `aleogr/lab` repository only for lab platform data: replaced by secrets in the vault, identifiers by convention and Actions variables, and state discovered in the cloud.
- `marketplace.json` at the repository root (with `metadata.pluginRoot`): passed over in favor of everything inside `marketplace/`, for organization.
- `actions/` folder at the root: composite actions live in `.github/actions/`.
- `devcontainers/`, `codespaces/` or `features/` folders at the root: Features live in `.devcontainer/features/`.
- `aleogr-` prefix on Features (e.g. `aleogr-setup`, `aleogr-go`): redundant with the address `ghcr.io/aleogr/aleogr/`; use `base`, `go`, `java`...
- Per-technology Features that reinstall the language, or that use `dependsOn` on the official one.
- Family skills with the action only (`create-repo`): would be cleaner and trust the namespace, but I chose the additional protection of the provider in the name.
- `<action>-<provider>` format (`create-repo-github`): replaced by `<provider>-<action>` (`github-create-repo`), which groups skills by provider.
- `name:` field in the frontmatter of plugin `SKILL.md`.
- `dependencies` linking the orchestrator to the family plugins.
- Relying on the repository's `.claude/settings.json` to bring plugins to Claude Code cloud sessions (they don't install those plugins).
- One Claude Code cloud environment per repository or per project; secrets in those environments' variables.
- Creating or configuring repositories from Claude Code cloud sessions (GitHub proxy limits).
- `.gitkeep` where a short README can document the folder; `.github/README.md` (would replace the profile README); plugin folder created before the plugin.
- Test projects (with code) inside `aleogr/aleogr`; test repositories in the personal account; a separate cloud project only for tests (fixed "sandbox" on GCP); a new cloud project for each test.
- Separate DNS trees for tests (`sandbox.aleogr.dev`, `sandbox.lab.aleogr.dev`): tests live directly in the lab with a reserved prefix, for the shorter URL.
- Path-based tests (`lab.aleogr.dev/test-<id>`): would require a router, apps under a subpath (different from reality), origin shared between tests (cookies and storage leaking) and would not support tenants.
- Staging as `homolog.<project>.lab.aleogr.dev` (conflicts with tenants).
- In the lab: dedicated instances per project, load balancer, static IP, NAT or any fixed cost per project.
- Using `aleogr/aleogr` as the Codespaces dotfiles repository.
- One CI workflow per component with an `on.push.paths` filter (blocks required checks).
- `secrets: inherit` in reusable workflows.
- The name "bootstrap" (generic, ambiguous with the CSS framework); `init` (built-in command).
- A single generic skill like "setup-cloud".
- Versioning the same project on more than one Git host (mirroring).
- The same component replicated on more than one cloud.
- Mandatory central repository in multi-repo projects.
- Versioned content in Portuguese: everything in the repository is in English (section 0).

---

## 17. Implementation strategy

- Build guided by the **NEXT REAL PROJECT**: only the plugins, workflows, actions and Features it requires (probably `aleogr`, `aleogr-repo-github`, `aleogr-cloud-gcp`, `aleogr-dns-cloudflare`, the `base` Feature, the `lab` cloud environment and the reusable workflows for the project's stacks). **Goal:** the project comes out of nothing without me opening any dashboard.
- Before the first project: understand and declare the existing lab platform ([sections 6](#6-the-lab-project-environments-and-minimum-cost) and [7](#7-where-data-lives)), based on the pending investigation.
- **Orchestrator MVP:** `check-environment`, `declare-project`, `plan-project`, `apply-project`, plus the destructive command guard hook (already with the test exceptions) and read permissions in `allow`.
- The next real project's declaration, with fictitious values, becomes the first example in `marketplace/schemas/examples/` and the first end-to-end test, before being applied to the real project.
- New families, providers, actions, workflows, Features and cloud environments come in when a real project needs them.

---

## 18. Open items

- [ ] **INVESTIGATE (read-only) how the lab works today:**
  - in Cloudflare: DNS records for `lab` and `*.lab` (CNAME to `*.cfargotunnel.com` = tunnel; to `ghs.googlehosted.com` = Cloud Run domain mapping; to `*.run.app` = direct service; A record = VM with reverse proxy; proxy on or off), Workers and routes on `lab.aleogr.dev`, tunnels and Access (Zero Trust), SSL/TLS → Edge Certificates (advanced certificates, Total TLS);
  - in GCP: Cloud Run domain mappings, VMs and the shared Cloud SQL instance.
  - The result defines: the certificate solution, the dns-* contract in the lab (record or route) and the lab platform declaration.
- [ ] Create the Claude Code `lab` cloud environment; test whether the setup script can register the marketplace and install plugins; define the allowed domains and network secrets (e.g. Cloudflare API token); version the canonical definition in `docs/cloud-environments/lab.md`.
- [ ] Define how FAMILY plugins reach cloud sessions. Options:
  - (a) the `lab` setup script installs all marketplace plugins (no collision, thanks to the provider in skill names, but more skills in context);
  - (b) a project SessionStart hook, only when `CLAUDE_CODE_REMOTE=true`, installs the declaration's plugins (test whether they load without restarting the session).
- [ ] Decide the name of the GitHub test organization. Ideas: `aleogr-sandbox`; or `aleogr-graveyard`, which would also receive my retired projects (transferred and ALWAYS archived, never with the `test-` prefix or the `aleogr-test` topic). The guard's exception rules already cover both scenarios.
- [ ] Define the test execution details ([section 15](#15-tests)) before implementing them.
- [ ] Define the lab platform identifiers that cannot be deduced and store them as Actions variables in `aleogr/aleogr`; configure budget alerts.
- [ ] Test registration via `extraKnownMarketplaces` with `path` (and with a branch `ref`) and the resolution of relative paths from `marketplace/`.
- [ ] Test referencing a local Feature in a nested path (`./features/src/base`); if it doesn't work, move the Features up one level.
- [ ] Mark the Features as public on GHCR after the first publication.
- [ ] Configure the Codespaces spending limit and idle timeout; create the Codespaces secret for Claude Code authentication.
- [ ] Confirm "create-environment" as the cloud-* action name.
- [ ] Decide whether create-plugin/validate-marketplace live in `aleogr` or in `aleogr-dev`.
- [ ] Evaluate, with the MVP, making projects' `state.json` lighter or just a cache of discovery.
- [ ] Configure protection of `aleogr/aleogr`'s `main` (require PR) and check 2FA.
- [ ] Choose the next real project to guide the MVP.
