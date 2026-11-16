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
2. Claude Code plugin marketplace (`.claude-plugin/`).
3. Reusable CI/CD: parameterized workflows and composite actions (`.github/`).
4. Dev Container Features for GitHub Codespaces (`.devcontainer/features/`).

All of this is **TOOLING** for my development laboratory (the "lab", at `lab.aleogr.dev`).

Personal premises:

- I practice "vibe coding" (I don't write code), but I want to be able to open a development environment on the web.
- Many projects in development at the same time.
- Always seek the **LOWEST POSSIBLE COST** in development.

Terminology (these are different things):

- **Project environment**: `lab`, `hom`, `prd` ([section 6](#6-the-lab-project-environments-and-minimum-cost)).
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
- Orchestrator plugin: `aleogr` (e.g. `/aleogr:project-create`). Install id: `aleogr@aleogr`.
- Family plugins: `aleogr-<family>-<provider>` (e.g. `aleogr-repo-github`, `aleogr-cloud-gcp`, `aleogr-dns-cloudflare`, `aleogr-stack-go`).

### Skills

- Family skills: `<provider>_<action>`, defined by the skill's **FOLDER NAME** (e.g. `skills/github_repo-create/`). Full command: `/aleogr-repo-github:github_repo-create`, `/aleogr-cloud-gcp:gcp_environment-create`, `/aleogr-dns-cloudflare:cloudflare_record-add`, `/aleogr-stack-go:go_setup`.
- **Exactly one underscore**, separating the provider from the action; hyphens separate words inside each part. This keeps the boundary visible when the provider has more than one word — cloud products carry the full provider: `aws-route53_record-add`, `gcp-cloud-sql_database-create`.
- **NO plugin `SKILL.md` has the `name:` field in its frontmatter.** The name comes from the folder and Claude Code applies the plugin prefix. Reason: there is a recurring bug (issue anthropics/claude-code#22063, resolved in March 2026 and reported again as a regression in June) in which the `name:` field makes the skill lose the plugin prefix; the plugin documentation advises against using `name:`.
- The provider in the skill name is an **ADDITIONAL and deliberate** protection: even if the `plugin:skill` namespace fails (regression, or a surface that shows skills without prefix), there is no collision between plugins. The redundancy in the command (`github` appears twice) is consciously accepted.
- **Object first, action after**, in every skill: the action part is `<object>-<verb>` (e.g. `repo-create`, `branch-protect`, `record-add`), and the verb may carry a complement (`ci-set-secret`). It groups skills by object in the command menu and follows the order of the CLIs the skills use (`gh repo create`). A skill without an object is just the verb (`go_setup`).
- Orchestrator skills have no technology and carry no provider; they are `<object>-<verb>` (e.g. `/aleogr:project-declare`, `/aleogr:project-apply`, `/aleogr:component-add`).
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

- Reusable workflows: prefix by purpose (`ci-`, `cd-`, `release-`).
- Workflows that run in this repository itself: prefix `self-`.
- The purpose comes first because the workflows folder is flat (the prefix is the only grouping) and it mirrors the projects' `ci.yml`/`cd.yml`.

### Composite actions

- Actions of a technology: `<technology>-<action>`, technology first (e.g. `go-setup`, `java-setup`), in the same order as skills (`go_setup`) and Features (`go`). It groups a technology's actions together and avoids confusion with the official ones (`actions/setup-go`).
- Generic actions, without a technology: verb and object (e.g. `detect-changes`).

### Dev Container Features

- Own Features: named after the **TECHNOLOGY, WITHOUT prefix**, because the published address already works as a prefix: `ghcr.io/aleogr/aleogr/<id>` (e.g. `go`, `java`, `python`, `android`).
- The Feature common to all projects is called `base`.
- Direct correspondence with plugins: `aleogr-stack-go` ↔ Feature `go`; `aleogr-platform-android` ↔ Feature `android`.

### Claude Code cloud environments

- Named by **NEEDS PROFILE** (e.g. `lab`, `lab-android`). By project only as a last resort, for a heavy and rare combination of profiles ([section 14.2](#142-claude-code-cloud-environments)).

### Cloud environments (GCP project IDs)

- `aleogr-<environment>-<project>-<random>` (e.g. `aleogr-lab-iam-c4vc`).
- `<environment>`: `lab`, `hom` or `prd`. It comes first, so that every laboratory and every production environment sort together and the thing that must not be confused is at the front of the name.
- `<random>`: four random characters, lowercase letters and digits, to make the ID unique.
- GCP limits an ID to 30 characters, which leaves **14 characters for the project name**. IDs are permanent: immutable, and a deleted one is never available again.

### Project and platform resources in the lab

- Project resources in the lab: services `<project>-<component>`, database `<project>` (normalized to the format accepted by the database), record `<project>.lab.aleogr.dev`, label `aleogr-project=<project>`.
- Lab platform resources: label `aleogr-platform=lab`.

### Tests

- Separate GitHub organization: `aleogr-sandbox`. It may also hold my own experiments, which never use the `test-` prefix or the `aleogr-test` topic.
- One short random `<id>` per test, used in **ALL** of the test's resources:
  - repository `test-<id>`;
  - topic `aleogr-test`;
  - services `test-<id>-<component>`;
  - database `test_<id>`;
  - record `test-<id>.lab.aleogr.dev`;
  - label `aleogr-test=<id>`.
- The name `test` and the `test-` prefix are **RESERVED**: the schema and `project-declare` reject real project names equal to `test` (its topic `aleogr-test` would collide with the test marker) or starting with `test-`.

---

## 2. Structure of aleogr/aleogr

**Premise: clean root.** Only `README.md` and `docs/` are visible at the root; everything else lives in dot folders: `.github/` and `.devcontainer/`, required by convention, and `.claude-plugin/`, which holds the whole marketplace.

The tree below is the **TARGET**; "(skeleton)" marks what exists since the first task and "(built)" what exists with its stage 1 content. Everything else is planned.

```
aleogr/aleogr/
├── README.md                                  ← GitHub profile (do not touch without asking)
├── docs/
│   ├── DESIGN.md                              ← source of truth (skeleton)
│   ├── CONTRACTS.md                           ← contracts of every plugin family
│   ├── PROVIDER-FACTS.md                      ← how the providers behave (facts, not decisions)
│   ├── plans/                                 ← implementation plans and run checklists (built)
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
│   │   ├── go-setup/action.yml                (future)
│   │   └── java-setup/action.yml              (future)
│   └── workflows/                             ← flat folder (GitHub requirement), organized by prefix
│       ├── README.md                          ← prefixes, workflow_call only, workflows-v1 (skeleton)
│       ├── self-validate-marketplace.yml      ← validates marketplace and example declarations on every PR
│       ├── self-lint.yml                      ← static checks of workflows and scripts on every PR
│       ├── self-test-features.yml             ← tests the Features (test/ folder) on every PR
│       ├── self-publish-features.yml          ← publishes the Features to GHCR
│       ├── self-cleanup-tests.yml             ← scheduled: deletes resources of old tests
│       ├── ci-go.yml                          (future, reusable)
│       ├── ci-java.yml                        (future, reusable)
│       └── cd-cloud-run.yml                   (future, reusable)
└── .claude-plugin/                            ← the whole marketplace; the repository root is the marketplace root
    ├── README.md                              ← how to register the marketplace (skeleton)
    ├── marketplace.json                       (built: aleogr, aleogr-cloud-gcp)
    ├── tests/                             ← skill tests: run.sh, fake gcloud in bin/, scenarios/ (built, section 15.1)
    ├── schemas/
    │   ├── README.md                          ← purpose, versioning and examples of the schema (skeleton)
    │   ├── project.schema.json
    │   └── examples/                          ← example declarations (JSON only, fictitious values)
    │       └── go-gcp-cloudflare.json         (future)
    └── plugins/
        ├── README.md                          ← names, family types, plugin skeleton (skeleton)
        ├── aleogr/                            ← orchestrator (MVP; built: manifest, defaults.json and the three platform skills)
        │   ├── .claude-plugin/plugin.json
        │   ├── defaults.json              ← my personal defaults (choices only, no IDs)
        │   ├── skills/
        │   │   ├── tools-check/SKILL.md           (built)
        │   │   ├── platform-plan/SKILL.md         (built)
        │   │   ├── platform-apply/SKILL.md        (built)
        │   │   ├── project-declare/SKILL.md
        │   │   ├── project-plan/SKILL.md
        │   │   └── project-apply/SKILL.md
        │   ├── hooks/hooks.json               ← destructive command guard
        │   └── scripts/guard-destructive.sh
        ├── aleogr-repo-github/                (MVP)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/
        │       ├── github_repo-create/SKILL.md        ← contract
        │       ├── github_repo-configure/SKILL.md     ← contract
        │       ├── github_branch-protect/SKILL.md     ← contract
        │       ├── github_ci-set-secret/SKILL.md      ← contract
        │       ├── github_ci-setup/SKILL.md           ← contract
        │       └── github_claude-app-install/SKILL.md ← extra (future)
        ├── aleogr-cloud-gcp/                  (MVP; built: manifest and the four skills below)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/ gcp_environment-describe (built), gcp_environment-create (built), gcp_services-enable (built), gcp_budget-alert-setup (built), gcp_deploy-setup
        └── aleogr-dns-cloudflare/             (MVP)
            ├── .claude-plugin/plugin.json
            ├── .mcp.json                      ← official Cloudflare MCP (https://mcp.cloudflare.com/mcp)
            └── skills/ cloudflare_record-add
```

### 2.1 Documentation rules

- One short `README.md` per folder that has local rules to explain, always pointing to the corresponding section of `docs/DESIGN.md` (source of truth).
- Prefer a README over `.gitkeep`, which is used only where a README would be repetitive (`.devcontainer/features/src/` and `test/`, where dev container tooling expects only Feature subfolders).
- **NEVER create `.github/README.md`**: GitHub looks for the README in `.github/`, then at the root and then in `docs/`, and a README in `.github/` would replace my profile's. READMEs in `.github/actions/` and `.github/workflows/` don't have this problem.
- Do not create a plugin folder before the plugin itself.

### 2.2 Marketplace structure rules

- `marketplace.json` lives at `.claude-plugin/marketplace.json`, the standard location. The marketplace root is therefore the repository root (the directory containing `.claude-plugin/`); `source` paths are relative to it (`./.claude-plugin/plugins/aleogr`), without `..`.
- **Everything of the marketplace lives inside `.claude-plugin/`** (plugins, tests, schemas), to keep the repository root clean, in the same way as `.github/actions/` and `.devcontainer/features/`. Claude Code only requires the catalog file there; keeping the rest beside it is my choice.
- Each plugin has `.claude-plugin/plugin.json` (only the manifest lives inside `.claude-plugin/`); `skills/`, `agents/`, `hooks/`, `scripts/` and `.mcp.json` live at the plugin root. Scripts are referenced with `${CLAUDE_PLUGIN_ROOT}`.
- Local validation: `claude plugin validate .` (from the repository root). Local test: `claude plugin marketplace add .`.
- A plugin cannot read files outside its own folder once installed, so files the skills read (`defaults.json`, `contracts.json`) live inside the plugin that uses them: the orchestrator, `.claude-plugin/plugins/aleogr/`. Skills reference them as `${CLAUDE_PLUGIN_ROOT}/defaults.json`.
- **Do NOT use the `dependencies` field** to link the orchestrator to the family plugins: that would install every family in every project. Activation is decided by each project's declaration, via `plugins-sync`.

### 2.3 Registering the marketplace

The catalog is at the standard location, so the marketplace is registered like any other: `claude plugin marketplace add aleogr/aleogr`, or the `extraKnownMarketplaces` block below. Where it is done depends on where Claude Code runs:

- **Local (Windows app):** by hand once per computer in `~/.claude/settings.json`; and by `plugins-sync` in each project's `.claude/settings.json` (family plugins in project scope).
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
        "repo": "aleogr/aleogr"
      }
    }
  },
  "enabledPlugins": {
    "aleogr@aleogr": true
  }
}
```

- **Registering is not installing:** `enabledPlugins` only marks a plugin as enabled. Each plugin is installed once per computer, from the plugin browser of the app or with `claude plugin install <plugin>@aleogr`.
- **Visibility (local):** the marketplace catalog shows all plugins; among installed ones, `aleogr` appears everywhere (user scope) and family plugins appear only in the projects that activated them (project scope).
- **Schema URL in projects:** `https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json`.

---

## 3. Public repository conditions

- The profile repository must be public; marketplace, actions, workflows and Features are public. They contain only **generic TOOLING, NEVER data** (see [section 7](#7-where-data-lives)). Example declarations in `.claude-plugin/schemas/examples/` use fictitious values; `defaults.json` and `docs/cloud-environments/` contain only choices, no IDs or secrets.
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

- The reusable pieces live in `aleogr/aleogr`; each project has **THIN** workflows generated by the `<provider>_ci-setup` skill of the `repo-*` plugin (on GitHub, `github_ci-setup`), which only call the reusable ones with parameters.
- **A single `.github/workflows/ci.yml` per project:**
  - a `changes` job detects what changed (initially `dorny/paths-filter` pinned by SHA; candidate to become the composite action `aleogr/aleogr/.github/actions/detect-changes`, which receives the list of components);
  - one job per component, with `needs: changes` and `if:` on the corresponding output, calling its stack's reusable workflow (e.g. `aleogr/aleogr/.github/workflows/ci-go.yml@<sha>` with `working-directory` and `go-version`);
  - two components of the same stack = two jobs calling the same reusable workflow.
- **Do NOT use one workflow per component with `on.push.paths`:** the native filter applies to the whole workflow, and a workflow that didn't trigger leaves the required check pending forever, blocking the PR. A job skipped by `if:` counts as success.
- Secrets are passed explicitly by name to reusable workflows (**do not use `secrets: inherit`**), making visible in the project what each one receives.
- Deploy in `cd.yml` (or later jobs of the same file) with `needs:` on the component's CI and a condition to run only on `main`. With multiple project environments ([section 6](#6-the-lab-project-environments-and-minimum-cost)), `cd.yml` deploys to `lab` and promotes to the following environments.
- CI is the **single deploy path**, hosting-* included: no provider Git integration deploying on its own on every push (previews per PR, when wanted, are also made by CI).
- CI reaches clouds without long-lived keys: cloud-* `ci-identity-setup` sets up OIDC federation.
- **Future GitLab:** reusable workflows and composite actions only serve GitHub Actions. A `gitlab_ci-setup` would need pipeline templates.
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

- **The single point of parameterization is `project.json`**, not the Feature. The technology version is declared once in the declaration (default from `defaults.json` when omitted) and the orchestrator writes it both to the official Feature and to the CI workflow parameter ([section 10.6](#106-whathow-split)). The generated `devcontainer.json` is not edited by hand, so listing two Features per technology costs nothing.
- An own Feature **cannot forward its options** to the official one: in the Feature specification, `dependsOn` options are literal values in `devcontainer-feature.json`, options only reach the Feature's own `install.sh`, and `installsAfter` only orders. A wrapper accepting `version` would have to reinstall the language itself.
- A technology's folder only exists if I have something to add. If the official one is enough, the `stack-*` contributes only that.
- **Claude Code authentication in codespaces:** `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` (generated with `claude setup-token`) stored as a Codespaces secret.
- **Layout:** Feature sources in `.devcontainer/features/src/<id>/` and tests in `.devcontainer/features/test/<id>/` (layout expected by the dev containers CLI). The subfolder has the same name as the `id`. The `devcontainer.json` of `aleogr/aleogr` itself references the local Features by relative path (e.g. `./features/src/base`) to test before publishing.
- **Publishing** via `self-publish-features.yml` to GHCR (namespace `aleogr/aleogr`). GHCR packages are born private: mark each Feature as public on first publication.
- Projects' `devcontainer.json` is a **shared file**: each stack/platform contributes its entries in `features` without touching the others. Monorepo: a single `devcontainer.json` by default; one per component (`.devcontainer/<component>/devcontainer.json`) when some platform declares a heavy or conflicting toolchain.
- What is specific to Codespaces (Codespaces secrets, prebuilds) are extra skills of `aleogr-repo-github` (e.g. `github_codespaces-configure`).
- iOS/watchOS (macOS) and firmware (physical device) don't build in a codespace: the devcontainer is for editing and using Claude Code; the build happens in CI (macOS runner) or in the Windows app. The `platform-*` records this limit.
- **Do NOT use `aleogr/aleogr` as the Codespaces dotfiles repository** (it would require a script at the root or links to the dot folders); `base` achieves the goal.
- **Cost:** set a spending limit and quick idle shutdown in Codespaces.
- Codespaces complements Claude Code on the web: it adds a full editor, a running application and port preview.

---

## 6. The lab, project environments and minimum cost

- I own the domain `aleogr.dev`. The lab (`lab.aleogr.dev`) is **EVERYTHING that is not production**: development and staging of my projects and the tests of the tooling itself.

### 6.1 Addresses of a project's environments

- **`lab`** (development): `<project>.lab.aleogr.dev`; tenants: `<tenant>.<project>.lab.aleogr.dev` (per-tenant routing is done by the application, by hostname).
- **`hom`** (optional): environment as a **SUFFIX** of the project, `<project>-hom.lab.aleogr.dev`, with tenants `<tenant>.<project>-hom.lab.aleogr.dev`. Never `hom.<project>.lab...`, which would be confused with a tenant.
- **Tenants in `lab` and `hom` are EXPLICIT, there is no wildcard:** I create each tenant by hand, so each one is declared and gets its own DNS record and its own mapping at the destination, with its own certificate. A new tenant takes a few minutes to answer, while the certificate is issued.
- **`prd`** (optional): the project's own domain or, without one, `<project>.aleogr.dev` (first-level subdomain, covered by Cloudflare's free certificate).
- **A multi-tenant project in `prd` requires its own domain:** `<tenant>.<project>.aleogr.dev` is second level and is not covered by the free certificate, while `<tenant>.<own-domain>` is.
- The orchestrator derives the names from the project name and the environment; I only declare which environments the project has.

Declaration (replaces a simple `domains` field):

```json
"environments": {
  "lab":  { "host": "project2.lab.aleogr.dev",     "tenants": ["acme", "globex"] },
  "hom":  { "host": "project2-hom.lab.aleogr.dev", "tenants": ["acme"] },
  "prd":  null
}
```

### 6.2 HTTPS and certificates

- `.dev` requires HTTPS (the domain is on browsers' HSTS preload list): there is no HTTP, not even in development.
- Cloudflare's free Universal SSL covers only the root domain and the first subdomain level. `project1.lab.aleogr.dev` (second level) and tenants (third level), with proxy on, are **NOT covered** and fail with errors like `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`.
- **Decision:** `lab` and `hom` use **UNPROXIED** records (DNS only), with the certificate issued by the destination; only `prd` uses proxied records, covered by the free certificate. Nothing is paid for certificates.
- The destination issues one certificate per hostname: the project's host and each tenant's. On GCP, a Cloud Run domain mapping per hostname ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)).

### 6.3 Protection and single access point

- **Lab protection: a login in front of every service, by default.** The concern is COST: any public address is found and visited by bots, and each visit wakes the service. So in `lab` and `hom` every service requires a login that is checked BEFORE the request reaches it; whoever is not on the allowed list is refused by the provider and the service does not even wake up. On GCP: IAP enabled directly on the Cloud Run service, with a Google account, no load balancer ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). A tester is added by e-mail to the allowed list.
- **A component that must stay open is declared public** in `project.json` (e.g. an API that receives webhooks from a payment provider, an API called by a mobile app), and only that one has no login. Everything that calls a service without a logged-in person stops working behind the login.
- **Cost ceilings are always on**, with or without login ([section 6.5](#65-minimum-cost-contract-rule-in-the-lab-project-environment)); they are what protects the components declared public.
- In `prd` none of this applies: production is public by definition.
- **No single access point:** every hostname has its own DNS record pointing to its destination. The dns-* contract in the lab is `record-add`; there is no router and no route.

### 6.4 Lab platform × project resources

- **Each project has its own cloud environment per project environment** (on GCP, its own project: [section 1](#cloud-environments-gcp-project-ids)). Whatever costs nothing while idle belongs to the project: services that scale to zero, secrets, storage, image registry.
- **Lab platform:** only what has a FIXED cost is shared, created ONCE ([section 6.8](#68-lab-shared-resources)). Each cloud provider (GCP, AWS, Azure) has its own version of the lab platform, with the same logic.
- **Project resources in the platform:** created INSIDE the shared resource (e.g. database + user on the shared instance).
- The family contract gains the `shared` or `dedicated` mode; in the `lab` project environment the default is `shared`. E.g. db-* in the lab creates database + user on the single instance; in production, its own instance.
- Isolation within shared resources by name and labels ([section 1](#1-names)); a project's `project-plan` sees only what is its own; `*-remove` never touches what belongs to another.

### 6.5 Minimum cost (contract rule in the `lab` project environment)

- Scale to zero whenever possible.
- Smallest tier/size available.
- Nothing with fixed cost per project (load balancer, static IP, NAT, dedicated instances).
- **Ceilings:** every service has a maximum number of instances (one or two), and every paid service the project uses (LLM, SMS, e-mail...) gets its own spending limit, so that the worst case has a known cost.
- Warn and ask for confirmation before creating anything with a fixed cost.
- Budget alerts configured on each provider's lab platform.
- Cache and search (whose managed offerings usually have fixed cost): in the lab, prefer serverless or free-tier providers, with one namespace/index prefix per project.

### 6.6 Personal defaults

- In `.claude-plugin/plugins/aleogr/defaults.json` (public, choices only, no IDs), read by `project-declare` to pre-fill declarations: lab domain (`lab.aleogr.dev`), GitHub owner, preferred cloud and region, DNS provider, which services the lab platform shares.

### 6.7 GCP: organization, folders and billing

- **Every GCP project lives inside the organization**, never loose under my user account.
- **The shared project is the one exception to the folders:** it lives directly under the organization, outside every folder, because it serves both `lab` and `hom` and belongs to neither ([section 6.8](#68-lab-shared-resources)). Rules applied to a folder do not reach it; only the organization's do.
- **One folder per environment**, with the same names used in the project IDs ([section 1](#cloud-environments-gcp-project-ids)): `lab`, `hom`, `prd`. A project is created in the folder of its environment, which allows permissions and policies per environment. A folder is created when its first project exists.
- **Preferred region: `us-central1`**, for every project and for the shared environment (same region as the shared database; Cloud Run domain mappings exist there). It is the default in `defaults.json` ([section 6.6](#66-personal-defaults)).
- **The billing account belongs to the organization**, with a budget alert on the whole account ([section 6.5](#65-minimum-cost-contract-rule-in-the-lab-project-environment)).
- **Few organization policies, chosen one by one.** The organization already comes with a set enforced by default, which stays as it is ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)); it includes the one that matters most here, forbidding the creation of service account keys, because CI reaches the cloud without long-lived keys ([section 4](#4-cicd)). Consequence for every project: each service runs as its own service account with explicit roles, since default service accounts get none.
- Not used: deep folder hierarchies, more than one organization, separate administrative roles per person.
- The identifiers of the organization, the folders and the billing account are not versioned (the repository is public); they follow [section 7](#7-where-data-lives).

### 6.8 Lab shared resources

- **One shared cloud environment for everything that is not production**, with a generic name so that it can hold any shared resource that appears: on GCP, `aleogr-lab-shared-<random>`. It serves `lab` AND `hom`, so on GCP it is created directly under the organization, not in the folder of an environment ([section 6.7](#67-gcp-organization-folders-and-billing)); "lab" in the name is the umbrella of [section 6](#6-the-lab-project-environments-and-minimum-cost), as in the domain. `prd` never uses it.
- `shared` is a **RESERVED** project name ([section 11.1](#111-json-schema)).
- Accepted trade: `lab` and `hom` of every project share performance and availability, and the separation between them protects against accidents only ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). A project that needs an isolated `hom` uses the `dedicated` mode.
- **Shared database:** one Cloud SQL PostgreSQL instance, the smallest tier, with one database per project and environment (`<project>`, `<project>_hom`).
- **The instance is OFF by default** (it does not scale to zero, and it is the only fixed cost of the lab):
  - **started on demand**, when I am going to work: by the skill `gcp-cloud-sql_instance-start` (where `gcloud` is authenticated) or by a manually triggered workflow of `aleogr/aleogr` (from anywhere, including the phone);
  - **stopped every night by a scheduler inside GCP**, at a fixed time, so that stopping never depends on me remembering; it can also be stopped by hand, by the skill `gcp-cloud-sql_instance-stop` or by the same manually triggered workflow (which offers both start and stop);
  - starting takes minutes ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)): skills and deploys that need the database check whether it is running and say so, instead of failing with a connection error;
  - the backup window must fall in hours when the instance is usually running.
- **What the platform is made of** (on GCP): the shared project, the database instance, the scheduler that stops it, the identity the manual workflow uses to start and stop it, and the budget alert.
- **How it is created and changed:** by the orchestrator, with skills that run commands, from the platform declaration ([section 11](#11-project-model)) — the same mechanism as the projects, with the same rules ([section 10.4](#104-behavior-of-every-skill)). It is created once, from the Windows app, where the CLIs are authenticated ([section 14](#14-where-i-run-claude-code)). Its state is what exists in the cloud ([section 7](#7-where-data-lives)).

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
- The platform's change history comes from the hooks' audit log and the providers' audit logs; decisions are versioned in Git (`.claude-plugin/plugins/aleogr/defaults.json`).
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

Each family has a contract: the same ACTIONS, with the same kind of result, across providers; the skill is named `<provider>_<action>`. The orchestrator builds the name by joining the provider (from the declaration) with the action (fixed in the contract).

**The contracts of every family live in [`docs/CONTRACTS.md`](CONTRACTS.md)** (common rules + one action table per family). Decided common rules:

- Standard verbs (`*-describe`, `*-create`, `*-configure`, `*-setup`, `*-grant`, `*-remove`/`*-archive`); **`*-describe` is mandatory in every family** (read-only, normalized state; basis of `project-plan` and of every final verification).
- Modes: `plan`/`apply` in every changing action; `shared`/`dedicated`; `test`/`live` in special-care families.
- **Every skill ends with an `aleogr-result` JSON block** (status, resources, outputs, `secretRef`s, cost, pending items). Its `requests` field (DNS records, CI secrets/variables, devcontainer Features, required checks) is how a family hands work to another: families never call each other; the orchestrator routes the requests in the right apply step.
- Secret values never pass through the conversation: secrets are produced straight into secrets-* and referenced by `secretRef`.
- In cloud-*, the object is "environment", not "project", because clouds have different concepts (project on GCP, account on AWS, subscription/resource group on Azure).

**Machine-readable version:** `CONTRACTS.md` is the text source of the contracts. When the validation is implemented, the mandatory actions of each family are also available in a `contracts.json` (family, type, scope and actions), read by `marketplace-validate`, `self-validate-marketplace.yml`, `project-plan`/`project-apply` and `plugin-create`; how the two are kept in sync (one generated from the other, or checked against it) is decided then. Its location is open ([section 18](#18-open-items)).

### 10.2 Mode, names and labels

- Every family skill accepts the `shared` mode (inside the lab platform) or `dedicated` (own resources); in the `lab` project environment, the default is `shared`.
- Every skill applies the labels and conventional names from [section 1](#1-names) to EVERYTHING it creates.

### 10.3 Extending contracts

- The contract is the common MINIMUM; plugins may have extra skills, following the same naming convention (e.g. `github_claude-app-install`, `github_codespaces-configure`, `cloudflare_cache-purge`).
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
- **repo-\*** generates the workflow in the platform's format (`<provider>_ci-setup`; on GitHub, thin workflows calling the reusable ones from `aleogr/aleogr`).
- **The orchestrator** assembles the `devcontainer.json` and the project's SessionStart hook for Claude Code cloud sessions ([section 14.2](#142-claude-code-cloud-environments)), from the same contributions.
- CI and devcontainer come from the SAME declaration: the declared language version goes both to the workflow parameter and to the devcontainer's official Feature, avoiding drift. Changing it in project.json + project-apply updates both.

### 10.7 Shared files and stack hooks

- Shared files at the project root (.gitignore, .editorconfig, pre-commit, Dependabot/Renovate, devcontainer.json) receive contributions:
  - in text files, marked sections (`# >>> aleogr-stack-go` ... `# <<< aleogr-stack-go`);
  - in structured files, each contributor adds/updates only its own entries;
  - never replacement.
- Stack hooks filter by file extension and exit silently if it is not their language.

### 10.8 Special-care families (payments, registrar, store, sms, publish)

- Test mode by default.
- No purchase, production or store submission without explicit confirmation.
- Signing keys only via secrets-*.

---

## 11. Project model

- **Personal preference:** the SMALLEST possible number of repositories. Monorepo whenever it makes sense; in multi-repo projects, prefer the federated layout (creates no extra repository).
- A project is a list of components (stack, platform, deploy/distribution, location = directory or repository), the project environments ([section 6](#6-the-lab-project-environments-and-minimum-cost)) and the project's shared services.
- **Declaration** in `.aleogr/project.json` in the project repository (what I WANT; edited by me or by the `project-declare` skill). **State** in `.aleogr/state.json` (what EXISTS; only the orchestrator writes it). Neither stores secrets, only references.
- The **lab platform** is managed by the same orchestrator, with the same declaration format (marked as `"kind": "platform"`), but without its own repository: choices in `defaults.json`, identifiers by convention and variables, state discovered in the cloud ([section 7](#7-where-data-lives)). Projects point to it in the `lab` project environment.

### 11.1 JSON Schema

- In `.claude-plugin/schemas/project.schema.json` (versioned; `version` field in project.json; `$schema` for autocomplete).
- Exclusive families = object; combinable = list.
- Exactly one `primary` cloud (contains + minContains/maxContains = 1).
- payments `mode` with default "test".
- Project names cannot be `test` or `shared`, nor start with `test-`.
- A component may be declared public; without it, in `lab` and `hom` the component is behind the lab login ([section 6.3](#63-protection-and-single-access-point)).
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
  - `platform-plan`: compares the lab platform choices in `defaults.json` with the cloud; changes nothing (implemented for the free part: shared project, APIs, budget alert);
  - `platform-apply`: creates and changes the lab platform ([section 6.8](#68-lab-shared-resources)) as `platform-plan` lists (implemented for the free part; asks for one confirmation unless called with `confirm=yes`);
  - `project-declare`: edits project.json through questions, pre-filling from `defaults.json`, without executing;
  - `project-plan`: compares declaration, state and reality; changes nothing;
  - `project-apply`: executes the plan in order.
  - `platform-*` act on the lab platform; `project-*` remain for projects.
- **Shortcuts:** `project-create`, `component-add`, `service-add`, `tenant-add` (declares a tenant in an environment and applies it).
- **Maintenance:**
  - `tools-check` (implemented for `gcloud` and where Claude runs): CLIs, authentication, MCPs, devices; identifies whether it runs locally, in a codespace or in a cloud session and warns about what is not possible there;
  - `plugins-sync`: writes `extraKnownMarketplaces` and installs/disables family plugins in project scope;
  - `component-remove`, `service-remove`: stop before deleting, asking for confirmation.
- **Marketplace** (perhaps in a separate `aleogr-dev` plugin, open decision):
  - `plugin-create`: generates the skeleton already following the standard (names, mandatory `category` and `displayName`, contract skills);
  - `marketplace-validate`.

### 12.1 What `marketplace-validate` checks

`marketplace-validate` (and the `self-validate-marketplace.yml` workflow, on every PR) checks:

- `claude plugin validate .`;
- family skills in the `<provider>_<action>` format, with the object first in the action;
- NO `name:` in the frontmatter of `SKILL.md` files inside `.claude-plugin/plugins/`;
- no skill name equal to a built-in command;
- `marketplace.json` entry equal to the `plugin.json` `name`;
- `category` and `displayName` present;
- mandatory contract skills present in each family plugin;
- declarations in `.claude-plugin/schemas/examples/` valid against the schema.

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
12. Final `project-plan` must say "nothing to do".

---

## 13. Other components

### 13.1 Hooks

Deterministic guarantees; general ones live in `aleogr`, specific ones in each family.

- **PreToolUse on Bash** blocking destructive commands (deleting a project/repo, public visibility, removing DNS, dropping a database, removing services) outside a confirmed *-remove. **NARROW** exceptions, only for test resources listed in a test's state:
  - repositories (test organization + name `test-<id>` + topic `aleogr-test` + NOT archived);
  - DNS records `test-<id>` or `test-<id>-<environment>` under `lab.aleogr.dev`, and the tenants below them;
  - databases `test_<id>`;
  - cloud services/resources `test-<id>-...` with label `aleogr-test=<id>`.
- **PreToolUse on Write/Edit** blocking secrets in versioned files.
- **PostToolUse on Write/Edit** validating project.json against the schema.
- **PostToolUse formatting** per stack.
- **SessionStart** injecting a summary of the declaration and manual open items.
- **SessionStart in the project repository**, only when `CLAUDE_CODE_REMOTE=true`, installing the project's light needs in Claude Code cloud sessions ([section 14.2](#142-claude-code-cloud-environments)).
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

- Scheduled (weekly) GitHub Action running project-plan on projects and opening an issue on drift.

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
- **Environments do NOT compose:** a session runs in exactly ONE environment; there is no inheritance or sum of environments. A project that needs two profiles cannot use both.
- **Composition therefore happens in layers:**
  1. the `lab` environment is the single base, common to every project;
  2. light project-specific needs are installed by a **SessionStart hook in the project repository** (only when `CLAUDE_CODE_REMOTE=true`), generated by the orchestrator from the declaration, with each `stack-*`/`platform-*` contributing its part — this is the layer that composes;
  3. an additional environment exists only for what the hook cannot provide: heavy toolchain (needs the setup script cache), different network or different network secrets.
- What ONLY the environment can provide: network access, network secrets, variables and the setup script cache. The repository hook runs on every session start, without that cache, and only reaches what the environment's network allows.
- **Default:** one environment per NEEDS PROFILE. An environment per project is accepted only as a last resort, for a heavy and rare combination of profiles.

#### `lab` environment (default, the only one at first)

- Custom network: default package manager list + domains the sessions need to reach (e.g. `*.lab.aleogr.dev`).
- Setup script: registers the `aleogr` marketplace and installs the orchestrator (`claude plugin marketplace add` + `claude plugin install`), and writes my personal `~/.claude/CLAUDE.md`. Same responsibility as the `base` Feature ([section 5](#5-dev-containers-and-codespaces)); keep them consistent. Test whether plugin installation works at this stage.
- Network secrets for APIs with a fixed token; variables only with non-sensitive values.

#### Additional environments

- ONLY when a truly different profile appears and the repository hook is not enough: heavy toolchain (e.g. `lab-android` with the Android SDK, keeping the `lab` script under the cache limit) or different network (e.g. one without network, for reviewing third-party code).
- A project that needs an additional profile PLUS something light uses that profile's environment and gets the rest from its SessionStart hook. Only a combination of two heavy profiles requires an environment of its own.

#### Canonical version

- Environments are configured in the claude.ai interface, not by file. The CANONICAL version (setup script, allowed domains, description of network secrets without values) is versioned in `docs/cloud-environments/<environment>.md` in `aleogr/aleogr`, without IDs or secrets, and copied to the interface when it changes.
- **Setup scripts are assembled from FRAGMENTS:** each profile is one fragment (e.g. base, Android SDK); an environment's script is the sum of the fragments it needs, with every additional environment starting from the base fragment. A combined environment reuses the fragments instead of duplicating script text.

---

## 15. Tests

> This section records the **DIRECTION** of the tests. Execution details are still open and will be defined before implementation; **do not implement anything from this section without confirmation**.

Tests test the **TOOLING** (`aleogr/aleogr`), not my products: "if I run `/aleogr:project-create` with this declaration, does a working project come out?". Not to be confused with the `hom` project environment, which tests a product. Tests are a lab activity and use the **LAB PLATFORM** (zero extra infrastructure cost and realism: they exercise the same sharing as real projects).

### 15.1 Layer 1 — in the repository itself (static, creating nothing outside), on every PR

- `self-validate-marketplace.yml`: validation of the marketplace and naming rules, and of the example declarations against the schema.
- `self-lint.yml`: static checks of workflows and hook scripts.
- `self-test-features.yml`: Feature tests with the dev containers CLI, using `.devcontainer/features/test/`.
- Skill tests (`.claude-plugin/tests/`): `run.sh <scenario>` runs the real skills headless (`claude -p`) against fake CLIs (a fake `gcloud` in `.claude-plugin/tests/bin/`, with numbered responses for calls that must answer differently before and after a change) and checks the logged calls and the final answer against the scenario's `expect.txt` (line types in `.claude-plugin/tests/README.md`). They create nothing outside the repository, are run by hand for now (no workflow), and each run costs model usage.
- Apart from `.claude-plugin/tests/`, the only "tests folder" in the repository is `.claude-plugin/schemas/examples/`, with the test INPUTS (declarations with fictitious values), never projects with code.

### 15.2 Layer 2 — local development

- Load a plugin straight from its folder with `--plugin-dir`, or register the local marketplace with `claude plugin marketplace add .`, and experiment in a test folder in the Windows app. Nothing is published.

### 15.3 Layer 3 — end to end

The test OUTPUTS (the created projects) live **OUTSIDE** `aleogr/aleogr`, because only a real repository reproduces what is tested: repository creation and protection, secrets, workflows (GitHub only runs those at the root; cross-repository calls must be exercised), Codespaces and `.claude/settings.json` (read from the root). Tests inside `aleogr/aleogr` would also change the repository's own protection and secrets and pollute its history.

- Separate GitHub organization (`aleogr-sandbox`), free: test repositories never show up in my personal account, and organization-level secrets can be tested. Address: `github.com/aleogr-sandbox/test-<id>`.
- Run from the **WINDOWS APP** (repository creation doesn't work in cloud sessions, [section 14](#14-where-i-run-claude-code)).
- Test what is in the PR's **BRANCH**, before merge:
  - reusable workflows referenced by branch name (`@<branch>`);
  - marketplace registered with `"ref": "<branch>"`;
  - Features tested by layer 1 (and, if needed, published with a pre-release version).
- Each test uses an `<id>` in ALL resources ([section 1](#1-names)): repository `test-<id>`, services `test-<id>-<component>` in the lab's cloud environment, database `test_<id>` on the shared instance, `test-<id>.lab.aleogr.dev` (with project environments: `test-<id>-<environment>.lab.aleogr.dev`; tenants: `<tenant>.test-<id>.lab.aleogr.dev`).
- **The test:** run `/aleogr:project-create` with a declaration from `.claude-plugin/schemas/examples/`; check:
  - green CI;
  - address responding (and tenants, if any);
  - codespace opening with the right tools;
  - a Claude Code cloud session in the `lab` environment working on the created repository;
  - final `project-plan` saying "nothing to do".
- **Example scenarios:**
  - simple backend (1 component, 1 project environment);
  - multi-tenant monorepo (2 components, two tenants, CI running only the changed component's job);
  - two project environments (lab + hom, with promotion in cd.yml);
  - Android app (only repository, CI and devcontainer, no DNS or cloud).
- **Every test creates a new `test-<id>` repository**; there is no fixed, reused test repository. Skills that only touch files of a project are tested with a minimal declaration (repository only, no cloud or DNS).
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
- The catalog in a subfolder (`marketplace/.claude-plugin/marketplace.json`, registered with `path`): the Claude Code desktop app downloads such a marketplace but lists no plugin from it ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). The catalog is at the standard location, and the marketplace content went into `.claude-plugin/`.
- `actions/` folder at the root: composite actions live in `.github/actions/`.
- `devcontainers/`, `codespaces/` or `features/` folders at the root: Features live in `.devcontainer/features/`.
- `aleogr-` prefix on Features (e.g. `aleogr-setup`, `aleogr-go`): redundant with the address `ghcr.io/aleogr/aleogr/`; use `base`, `go`, `java`...
- Per-technology Features that reinstall the language, that use `dependsOn` on the official one, or that wrap the official one to receive the version themselves.
- Family skills with the action only (`repo-create`): would be cleaner and trust the namespace, but I chose the additional protection of the provider in the name.
- Composite actions named like the official ones, action first (`setup-go`, `setup-java`): replaced by technology first (`go-setup`, `java-setup`).
- Verb first in skill names (`declare-project`, `github_create-repo`): replaced by object first (`project-declare`, `github_repo-create`).
- `check-environment` as the name of the orchestrator skill that checks CLIs and authentication: "environment" already means the project environment, the cloud environment and the Claude Code cloud environment; it became `tools-check`.
- `<action>-<provider>` format (`create-repo-github`): replaced by `<provider>_<action>` (`github_repo-create`), which groups skills by provider.
- `name:` field in the frontmatter of plugin `SKILL.md`.
- `dependencies` linking the orchestrator to the family plugins.
- Relying on the repository's `.claude/settings.json` to bring plugins to Claude Code cloud sessions (they don't install those plugins).
- One Claude Code cloud environment per repository or per project as the default (accepted only as a last resort, section 14.2); secrets in those environments' variables.
- A strict "never by repository or project" rule for Claude Code cloud environments: environments do not compose, so combined profiles are solved by the repository's SessionStart hook and, as a last resort, by a per-project environment.
- Creating or configuring repositories from Claude Code cloud sessions (GitHub proxy limits).
- `.gitkeep` where a short README can document the folder; `.github/README.md` (would replace the profile README); plugin folder created before the plugin.
- A fixed test repository reused on each run: it would need a second naming pattern outside the reserved `test-` prefix (or the cleanup would delete it) and logic to restore its initial state.
- Test projects (with code) inside `aleogr/aleogr`; test repositories in the personal account; a separate cloud project only for tests (fixed "sandbox" on GCP); a new cloud project for each test.
- Separate DNS trees for tests (`sandbox.aleogr.dev`, `sandbox.lab.aleogr.dev`): tests live directly in the lab with a reserved prefix, for the shorter URL.
- Path-based tests (`lab.aleogr.dev/test-<id>`): would require a router, apps under a subpath (different from reality), origin shared between tests (cookies and storage leaking) and would not support tenants.
- Staging as `hom.<project>.lab.aleogr.dev` (conflicts with tenants).
- Proxied records in `lab` and `hom`, paying for Advanced Certificate Manager; and Cloudflare Access as the lab protection (requires proxied records).
- Terraform for the lab platform, applied by CI (alone, or mixed with skills for the projects): deterministic and reviewable, but a second way of working for five or six pieces created once, with a state bucket, an identity with many permissions and a pull request per change. It stays as the way out if the shared instance suffers unwanted changes.
- For the lab protection: no login, only cost ceilings (bots keep spending up to the ceiling, including on endpoints that call paid services); login only inside the application (the request reaches the service and costs before the login is checked). Chosen: a login in front of every service, plus the ceilings.
- For tenant addresses in the lab: a Cloudflare Worker routing every lab hostname, with proxied records and flattened names (a format different from production, undoes the unproxied decision, and one piece whose failure takes the whole lab down); a load balancer with a wildcard certificate (fixed cost); tenants by path or header only in the lab (behaviour different from production). Chosen: one record and one mapping per tenant.
- In the lab: dedicated instances per project, load balancer, static IP, NAT or any fixed cost per project.
- A single lab cloud environment holding the resources of every project: each project has its own, and only fixed-cost resources are shared.
- For the shared lab database: always on (fixed cost with nobody using it); sleeping only on weeknights (saves little); a serverless PostgreSQL outside GCP (another provider, and a connection different from production). Chosen: off by default, started on demand.
- Using `aleogr/aleogr` as the Codespaces dotfiles repository.
- One CI workflow per component with an `on.push.paths` filter (blocks required checks).
- `secrets: inherit` in reusable workflows.
- The name "bootstrap" (generic, ambiguous with the CSS framework); `init` (built-in command).
- A single generic skill like "setup-cloud".
- Versioning the same project on more than one Git host (mirroring).
- The same component replicated on more than one cloud.
- Mandatory central repository in multi-repo projects.
- Family skills calling other families' skills directly: replaced by `requests` in the `aleogr-result` block, routed by the orchestrator.
- Deploys through the hosting provider's own Git integration: CI is the single deploy path.
- Long-lived cloud keys stored as CI secrets: replaced by OIDC (`ci-identity-setup`).
- Managed cache/search with fixed cost in the lab: serverless or free tier instead.
- Versioned content in Portuguese: everything in the repository is in English (section 0).

---

## 17. Implementation strategy

- Build guided by the **NEXT REAL PROJECT**: only the plugins, workflows, actions and Features it requires (probably `aleogr`, `aleogr-repo-github`, `aleogr-cloud-gcp`, `aleogr-dns-cloudflare`, the `base` Feature, the `lab` cloud environment and the reusable workflows for the project's stacks). **Goal:** the project comes out of nothing without me opening any dashboard.
- Before the first project: redesign and declare the lab platform, from scratch ([sections 6](#6-the-lab-project-environments-and-minimum-cost), [7](#7-where-data-lives) and [18](#18-open-items)).
- **Orchestrator MVP:** `tools-check`, `project-declare`, `project-plan`, `project-apply`, plus the destructive command guard hook (already with the test exceptions) and read permissions in `allow`.
- The next real project's declaration, with fictitious values, becomes the first example in `.claude-plugin/schemas/examples/` and the first end-to-end test, before being applied to the real project.
- New families, providers, actions, workflows, Features and cloud environments come in when a real project needs them.

---

## 18. Open items

- [x] **Create the lab platform, free part (stage 1):** the shared project, its APIs and the budget alert ([section 6.8](#68-lab-shared-resources)). Created on 2026-11-16 by `platform-apply`, in the Windows app.
- [x] **First real run of stage 1**, by me in the Windows app, on 2026-11-16, following [`plans/2026-11-16-lab-platform-stage-1-run.md`](plans/2026-11-16-lab-platform-stage-1-run.md). It ended with `nothing to do`; what it showed is in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [x] `platform-plan`, run without a project id, finds the existing shared project by its labels: confirmed on 2026-11-16, in a new session.
- [ ] **Create the lab platform, database part (stage 2)** ([sections 6.1, 6.3 and 6.8](#68-lab-shared-resources)): the database instance (off by default), the scheduler that stops it, the identity and the manual workflow to start and stop it. The previous lab was removed and its decisions were not inherited; only the provider behaviour learned there was kept, in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [ ] Decide how a multi-tenant project is served in `prd` (own domain, proxied records), when the first one exists.
- [ ] Test, on the first lab service: that IAP enabled directly on Cloud Run also protects the address that arrives through a domain mapping (the documentation says "all ingress paths" but does not name domain mappings), and that it has no cost in this use.
- [ ] Create the Claude Code `lab` cloud environment; test whether the setup script can register the marketplace and install plugins; define the allowed domains and network secrets (e.g. Cloudflare API token); version the canonical definition in `docs/cloud-environments/lab.md`.
- [ ] Measure the project SessionStart hook in cloud sessions (it runs on every session start, without the setup script cache) to define the practical limit of a "light" need; above it, the need goes to an environment.
- [ ] Check how Claude Code cloud environments can be associated with repositories in the current product (section 14.2 says they do not belong to repositories) and whether that changes the naming rule.
- [ ] Define how FAMILY plugins reach cloud sessions. Options:
  - (a) the `lab` setup script installs all marketplace plugins (no collision, thanks to the provider in skill names, but more skills in context);
  - (b) a project SessionStart hook, only when `CLAUDE_CODE_REMOTE=true`, installs the declaration's plugins (test whether they load without restarting the session).
- [ ] Define the test execution details ([section 15](#15-tests)) before implementing them.
- [ ] Define the lab platform identifiers that cannot be deduced and store them as Actions variables in `aleogr/aleogr`; configure budget alerts.
- [x] Registration via `extraKnownMarketplaces` with `path`: tested on 2026-11-16 in the Windows app. The marketplace is downloaded, but the app lists no plugin from it. The catalog moved to the standard location ([section 2.2](#22-marketplace-structure-rules)).
- [x] Plugins install in the Windows app from the catalog at the standard location, with the plugin folders inside `.claude-plugin/`: confirmed on 2026-11-16.
- [ ] Test referencing a local Feature in a nested path (`./features/src/base`); if it doesn't work, move the Features up one level.
- [ ] Mark the Features as public on GHCR after the first publication.
- [ ] Configure the Codespaces spending limit and idle timeout; create the Codespaces secret for Claude Code authentication.
- [x] Can an installed plugin read files of the marketplace outside its own folder? No. `defaults.json` lives in the orchestrator plugin (`.claude-plugin/plugins/aleogr/`) and `contracts.json` (section 10.1) will live there too.
- [ ] Decide whether plugin-create/marketplace-validate live in `aleogr` or in `aleogr-dev`.
- [ ] Evaluate, with the MVP, making projects' `state.json` lighter or just a cache of discovery.
- [ ] Configure protection of `aleogr/aleogr`'s `main` (require PR) and check 2FA.
- [ ] Choose the next real project to guide the MVP.
