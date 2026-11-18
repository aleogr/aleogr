# DESIGN — aleogr/aleogr

> **Source of truth** for this repository. Every change of decision is recorded here first, and the READMEs of the affected folders are updated in the same commit.

## Contents

- [0. Context and terminology](#0-context-and-terminology)
- [1. Names](#1-names)
- [2. Structure of aleogr/aleogr](#2-structure-of-aleograleogr)
- [3. Public repository conditions](#3-public-repository-conditions)
- [4. CI/CD](#4-cicd)
- [5. Dev containers and Codespaces](#5-dev-containers-and-codespaces)
- [6. Project environments, the shared platform and minimum cost](#6-project-environments-the-shared-platform-and-minimum-cost)
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

All of this is **TOOLING** for my projects, which live under my domain `aleogr.dev` ([section 6](#6-project-environments-the-shared-platform-and-minimum-cost)).

Personal premises:

- I practice "vibe coding" (I don't write code), but I want to be able to open a development environment on the web.
- Many projects in development at the same time.
- Always seek the **LOWEST POSSIBLE COST** in development.

Terminology (these are different things):

- **Project environment**: `dev`, `hom`, `prd` ([section 6](#6-project-environments-the-shared-platform-and-minimum-cost)).
- **Shared platform**: the resources with a fixed cost that `dev`, `hom` and the tests share ([section 6.8](#68-shared-platform-resources)). Everything that is not production has no special name.
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

- Named by **NEEDS PROFILE** (e.g. `base`, `android`). By project only as a last resort, for a heavy and rare combination of profiles ([section 14.2](#142-claude-code-cloud-environments)).

### Cloud environments (GCP project IDs)

- `aleogr-<environment>-<project>-<random>` (e.g. `aleogr-dev-iam-c4vc`).
- `<environment>`: `dev`, `hom` or `prd`. It comes first, so that every development and every production environment sort together and the thing that must not be confused is at the front of the name.
- `<random>`: four random characters, lowercase letters and digits, to make the ID unique.
- GCP limits an ID to 30 characters, which leaves **14 characters for the project name**. IDs are permanent: immutable, and a deleted one is never available again.
- The shared platform project is the one exception: `aleogr-shared-<random>`, with no environment, because it serves `dev`, `hom` and the tests ([section 6.8](#68-shared-platform-resources)).
- Labels: `aleogr-project=<project>` and `aleogr-environment=dev|hom|prd`; the shared project has `aleogr-project=shared` and `aleogr-platform=shared`, and no `aleogr-environment`.

### Project and shared platform resources

- Project resources: services `<project>-<component>`, database `<project>` on the shared instance (normalized to the format accepted by the database), record `<project>-<environment>.aleogr.dev` ([section 6.1](#61-addresses-of-a-projects-environments)), labels `aleogr-project=<project>` and `aleogr-environment=<environment>`.
- Shared platform resources: names starting with `aleogr-shared` (project `aleogr-shared-<random>`, instance `aleogr-shared`, jobs `aleogr-shared-stop-weeknight` and `aleogr-shared-stop-weekend`, service account `aleogr-shared-sql-switch`; the custom role is `aleogrSharedSqlSwitch`, since role ids take no hyphen; the budget alert is `aleogr`, on the whole billing account) and label `aleogr-platform=shared` ([section 6.8](#68-shared-platform-resources)).

### Tests

- Separate GitHub organization: `aleogr-sandbox`. It may also hold my own experiments, which never use the `test-` prefix or the `aleogr-test` topic.
- One short random `<id>` per test, used in **ALL** of the test's resources:
  - repository `test-<id>`;
  - topic `aleogr-test`;
  - services `test-<id>-<component>`;
  - database `test_<id>`;
  - GCP projects `aleogr-<environment>-test-<id>-<random>`, in the folder of their environment inside `tst` ([section 6.7](#67-gcp-organization-folders-and-billing)). **Provisional**, to confirm with the first disposable scenario: it follows from the id rule (so `<id>` has at most 9 characters, `test-<id>` being a project name of at most 14), each test would use up project ids, which are permanent, and whether the label `aleogr-test=<id>` is also set on these projects is not decided;
  - records `test-<id>-<environment>.aleogr.dev`, tenants `<tenant>.test-<id>-<environment>.aleogr.dev`;
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
│       └── base.md                            ← setup script, allowed domains, no IDs or secrets
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
│       ├── self-shared-database.yml           ← manually triggered: starts, stops or shows the state of the shared platform's database
│       ├── ci-go.yml                          (future, reusable)
│       ├── ci-java.yml                        (future, reusable)
│       └── cd-cloud-run.yml                   (future, reusable)
└── .claude-plugin/                            ← the whole marketplace; the repository root is the marketplace root
    ├── README.md                              ← how to register the marketplace (skeleton)
    ├── marketplace.json                       (built: aleogr, aleogr-cloud-gcp, aleogr-db-gcp-cloud-sql, aleogr-repo-github)
    ├── tests/                             ← skill tests: run.sh, fake gcloud, gh and git in bin/, scenarios/ (built, section 15.1)
    ├── schemas/
    │   ├── README.md                          ← purpose, versioning and examples of the schema (built)
    │   ├── project.schema.json                ← the declaration, version 1: the project name and its repository (built)
    │   └── examples/                          ← example declarations (JSON only, fictitious values)
    │       ├── repo-only.json                 ← a version 1 declaration (built)
    │       └── go-gcp-cloudflare.json         (future)
    └── plugins/
        ├── README.md                          ← names, family types, plugin skeleton (skeleton)
        ├── aleogr/                            ← orchestrator (MVP; built: manifest, defaults.json, the three platform skills and the three project skills)
        │   ├── .claude-plugin/plugin.json
        │   ├── defaults.json              ← my personal defaults (choices only, no IDs)
        │   ├── skills/
        │   │   ├── tools-check/SKILL.md           (built)
        │   │   ├── platform-plan/SKILL.md         (built)
        │   │   ├── platform-apply/SKILL.md        (built)
        │   │   ├── project-declare/SKILL.md       (built)
        │   │   ├── project-plan/SKILL.md          (built)
        │   │   └── project-apply/SKILL.md         (built)
        │   ├── hooks/hooks.json               ← destructive command guard
        │   └── scripts/guard-destructive.sh
        ├── aleogr-repo-github/                (MVP; built: manifest, the ruleset file and the five skills marked built)
        │   ├── .claude-plugin/plugin.json
        │   ├── files/ruleset-main.json        ← the ruleset `main` that github_branch-protect sends (same rules as aleogr/aleogr's)
        │   └── skills/
        │       ├── github_repo-describe/SKILL.md      ← contract (built)
        │       ├── github_repo-create/SKILL.md        ← contract (built)
        │       ├── github_repo-configure/SKILL.md     ← contract (built)
        │       ├── github_branch-protect/SKILL.md     ← contract (built)
        │       ├── github_checkout-setup/SKILL.md     ← contract: the folder's checkout and the declaration sent at the birth (built)
        │       ├── github_ci-set-secret/SKILL.md      ← contract
        │       ├── github_ci-setup/SKILL.md           ← contract
        │       └── github_claude-app-install/SKILL.md ← extra (future)
        ├── aleogr-cloud-gcp/                  (MVP; built: manifest and the four skills below)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/ gcp_environment-describe (built), gcp_environment-create (built), gcp_services-enable (built), gcp_budget-alert-setup (built), gcp_deploy-setup
        ├── aleogr-db-gcp-cloud-sql/           ← the shared platform's database: instance skills (describe, create, start, stop, switch-setup)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/ gcp-cloud-sql_instance-describe, gcp-cloud-sql_instance-create, gcp-cloud-sql_instance-start, gcp-cloud-sql_instance-stop, gcp-cloud-sql_instance-switch-setup
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
- Deploy in `cd.yml` (or later jobs of the same file) with `needs:` on the component's CI and a condition to run only on `main`. With multiple project environments ([section 6](#6-project-environments-the-shared-platform-and-minimum-cost)), `cd.yml` deploys to `dev` and promotes to the following environments.
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
- **`base`:** registers the `aleogr` marketplace (block from [section 2.3](#23-registering-the-marketplace)) in Claude Code's user settings inside the container, so the orchestrator is available in any codespace, even an empty one, and brings what is common to all projects. The `base` Feature (Codespaces) and the setup script of the `base` cloud environment (Claude Code cloud sessions, [section 14](#14-where-i-run-claude-code)) have the **SAME responsibility, in two vehicles**; keep both consistent.
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

## 6. Project environments, the shared platform and minimum cost

- I own the domain `aleogr.dev`. A project has up to three environments: `dev` (development), `hom` (staging) and `prd` (production). Everything that is not production (`dev`, `hom` and the tests of the tooling itself) has no special name; the resources it shares are **the shared platform** ([section 6.8](#68-shared-platform-resources)).

### 6.1 Addresses of a project's environments

- **Every address is directly under `aleogr.dev`, with the environment as a SUFFIX of the project:** `<project>-<environment>.aleogr.dev` (`prj1-dev.aleogr.dev`, `prj1-hom.aleogr.dev`, `prj1-prd.aleogr.dev`); tenants: `<tenant>.<project>-<environment>.aleogr.dev` (per-tenant routing is done by the application, by hostname). The environment is always in the name, so no project can collide with the other names of the domain. Never `hom.<project>...`, which would be confused with a tenant.
- **`id.aleogr.dev` is reserved** (my e-mail aliases): it is never a project address.
- **`dev`** (development) and **`hom`** (optional, staging) use those addresses.
- **Tenants in `dev` and `hom` are EXPLICIT, there is no wildcard:** I create each tenant by hand, so each one is declared and gets its own DNS record and its own mapping at the destination, with its own certificate. A new tenant takes a few minutes to answer, while the certificate is issued.
- **`prd`** (optional): `<project>-prd.aleogr.dev` only for simple systems. **A sensitive system, such as an identity provider (IAM), uses its own domain in `prd`:** every address under `aleogr.dev` is the same site to a browser, so a development system can set cookies that reach a production one.
- **A multi-tenant project in `prd` requires its own domain:** `<tenant>.<project>-prd.aleogr.dev` is second level and is not covered by the free certificate, while `<tenant>.<own-domain>` is.
- **Tests:** `test-<id>-<environment>.aleogr.dev`, tenants `<tenant>.test-<id>-<environment>.aleogr.dev` ([section 15](#15-tests)).
- The orchestrator derives the names from the project name and the environment; I only declare which environments the project has.

Declaration (replaces a simple `domains` field):

```json
"environments": {
  "dev":  { "host": "project2-dev.aleogr.dev", "tenants": ["acme", "globex"] },
  "hom":  { "host": "project2-hom.aleogr.dev", "tenants": ["acme"] },
  "prd":  null
}
```

### 6.2 HTTPS and certificates

- `.dev` requires HTTPS (the domain is on browsers' HSTS preload list): there is no HTTP, not even in development.
- Cloudflare's free Universal SSL covers only the root domain and the first subdomain level. Project addresses (`project1-dev.aleogr.dev`) are first level and covered; tenants (`acme.project1-dev.aleogr.dev`, second level), with proxy on, are **NOT covered** and fail with errors like `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`.
- **Decision:** `dev` and `hom` use **UNPROXIED** records (DNS only), with the certificate issued by the destination; only `prd` uses proxied records, covered by the free certificate. Nothing is paid for certificates.
  - For a project's address this is a **CHOICE**, not a limit: the free certificate would cover it, but the login already refuses strangers ([section 6.3](#63-protection-and-single-access-point)) and each extra layer is one more thing to fail.
  - Tenants are second level and stay unproxied, with the destination's certificate.
  - Before proxying any environment (`prd` included), test that the destination (a Cloud Run domain mapping) still issues and renews its certificate behind the proxy ([section 18](#18-open-items)).
- The destination issues one certificate per hostname: the project's host and each tenant's. On GCP, a Cloud Run domain mapping per hostname ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)).

### 6.3 Protection and single access point

- **Protection outside production: a login in front of every service, by default.** The concern is COST: any public address is found and visited by bots, and each visit wakes the service. So in `dev` and `hom` every service requires a login that is checked BEFORE the request reaches it; whoever is not on the allowed list is refused by the provider and the service does not even wake up. On GCP: IAP enabled directly on the Cloud Run service, with a Google account, no load balancer ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). A tester is added by e-mail to the allowed list.
- **A component that must stay open is declared public** in `project.json` (e.g. an API that receives webhooks from a payment provider, an API called by a mobile app), and only that one has no login. Everything that calls a service without a logged-in person stops working behind the login.
- **Cost ceilings are always on**, with or without login ([section 6.5](#65-minimum-cost-contract-rule-in-the-dev-project-environment)); they are what protects the components declared public.
- In `prd` none of this applies: production is public by definition.
- **No single access point:** every hostname has its own DNS record pointing to its destination. The dns-* contract in `dev` and `hom` is `record-add`; there is no router and no route.

### 6.4 Shared platform × project resources

- **Each project has its own cloud environment per project environment** (on GCP, its own project: [section 1](#cloud-environments-gcp-project-ids)). Whatever costs nothing while idle belongs to the project: services that scale to zero, secrets, storage, image registry.
- **Shared platform:** only what has a FIXED cost is shared, created ONCE ([section 6.8](#68-shared-platform-resources)). Each cloud provider (GCP, AWS, Azure) has its own version of the shared platform, with the same logic.
- **Project resources in the platform:** created INSIDE the shared resource (e.g. database + user on the shared instance).
- The family contract gains the `shared` or `dedicated` mode; in the `dev` project environment the default is `shared`. E.g. db-* in `dev` creates database + user on the single instance; in production, its own instance.
- Isolation within shared resources by name and labels ([section 1](#1-names)); a project's `project-plan` sees only what is its own; `*-remove` never touches what belongs to another.

### 6.5 Minimum cost (contract rule in the `dev` project environment)

- Scale to zero whenever possible.
- Smallest tier/size available.
- Nothing with fixed cost per project (load balancer, static IP, NAT, dedicated instances).
- **Ceilings:** every service has a maximum number of instances (one or two), and every paid service the project uses (LLM, SMS, e-mail...) gets its own spending limit, so that the worst case has a known cost.
- Warn and ask for confirmation before creating anything with a fixed cost.
- Budget alerts configured on each provider's shared platform.
- Cache and search (whose managed offerings usually have fixed cost): in `dev`, prefer serverless or free-tier providers, with one namespace/index prefix per project.

### 6.6 Personal defaults

- In `.claude-plugin/plugins/aleogr/defaults.json` (public, choices only, no IDs), read by `project-declare` to pre-fill declarations: the domain (`aleogr.dev`), preferred cloud and region, DNS provider, which services the shared platform shares.

### 6.7 GCP: organization, folders and billing

- **Every GCP project lives inside the organization**, never loose under my user account.
- **The shared project is the one exception to the folders:** it lives directly under the organization, outside every folder, because it serves `dev`, `hom` and the tests and belongs to none of them ([section 6.8](#68-shared-platform-resources)). Rules applied to a folder do not reach it; only the organization's do.
- **One folder per environment**, directly under the organization, with the same names used in the project IDs ([section 1](#cloud-environments-gcp-project-ids)): `dev`, `hom`, `prd`. A project is created in the folder of its environment, which allows permissions and policies per environment. A folder is created when its first project exists.
- **A fourth folder, `tst`, is not an environment: it mirrors the organization for the projects that test the tooling** (such as the reference project `pilot`, [section 15](#15-tests)), with the environment folders inside it (`tst/dev`, `tst/hom`; created when first needed). A test project is created by the same rule as a real one, in the folder named after its environment, with the search starting inside `tst` instead of at the organization (`gcp_environment-create` with `root=tst`), so the tests exercise the real path. The automatic cleanup of tests, when it exists, gets permission to delete projects only inside `tst`. The shared project stays outside the folders and serves `tst` too.
- The skills never create folders: a missing folder stops `gcp_environment-create`, which says which folder to create.
- **Preferred region: `us-central1`**, for every project and for the shared platform (same region as the shared database; Cloud Run domain mappings exist there). It is the default in `defaults.json` ([section 6.6](#66-personal-defaults)).
- **The billing account belongs to the organization**, with a budget alert on the whole account ([section 6.5](#65-minimum-cost-contract-rule-in-the-dev-project-environment)).
- **Few organization policies, chosen one by one.** The organization already comes with a set enforced by default, which stays as it is ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)); it includes the one that matters most here, forbidding the creation of service account keys, because CI reaches the cloud without long-lived keys ([section 4](#4-cicd)). Consequence for every project: each service runs as its own service account with explicit roles, since default service accounts get none.
- Not used: deeper folder hierarchies than the environment folders and `tst`, more than one organization ([section 16](#16-discarded-decisions)), separate administrative roles per person.
- The identifiers of the organization, the folders and the billing account are not versioned (the repository is public); they follow [section 7](#7-where-data-lives).

### 6.8 Shared platform resources

- **One shared cloud environment for everything that is not production**, with a generic name so that it can hold any shared resource that appears: on GCP, the project `aleogr-shared-<random>`, display name `shared`, labels `aleogr-project=shared` and `aleogr-platform=shared` (no environment in the id and no `aleogr-environment` label). It serves `dev`, `hom` and the tests, so on GCP it is created directly under the organization, not in the folder of an environment ([section 6.7](#67-gcp-organization-folders-and-billing)). `prd` never uses it. The skills address it as `project=shared platform=shared`, never with an environment (`gcp_environment-describe`, `gcp_environment-create`, `gcp_services-enable`; the orchestrator's `platform-plan` and `platform-apply` pass it so).
- `shared` is a **RESERVED** project name ([section 11.1](#111-json-schema)).
- Accepted trade: `dev` and `hom` of every project share performance and availability, and the separation between them protects against accidents only ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). A project that needs an isolated `hom` uses the `dedicated` mode.
- **Shared database:** one Cloud SQL PostgreSQL instance, `aleogr-shared`, the smallest tier, with one database per project and environment, the environment always in the name as in the addresses (`<project>_dev`, `<project>_hom`). It has a public address with no authorized networks, so nothing connects to it directly: access goes through the Cloud SQL connector, authenticated by IAM. The disk is 10 GiB with automatic growth off (disks never shrink, and `gcloud` has no flag for a growth limit); a full disk is a visible failure and I grow it by hand. Deletion protection is on.
- **The instance is OFF by default** (it does not scale to zero, and it is the only fixed cost of the shared platform). Stopped, it still costs its disk and its idle public address: about R$ 50 per month while stopped ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). Nothing with that cost is created without my seeing the amount and saying yes:
  - **started on demand**, when I am going to work: by the skill `gcp-cloud-sql_instance-start` (where `gcloud` is authenticated) or by a manually triggered workflow of `aleogr/aleogr` (from anywhere, including the phone);
  - **stopped by a scheduler inside GCP**, so that stopping never depends on me remembering: two Cloud Scheduler jobs in the shared project (`aleogr-shared-stop-weeknight` and `aleogr-shared-stop-weekend`) call the Cloud SQL Admin API, with no function in between (Cloud Scheduler cannot send the API's HTTP `PATCH`, so each job sends a `POST` with the header `X-HTTP-Method-Override: PATCH`), in `America/Sao_Paulo` time, at 22:30 from Sunday to Thursday and at 04:00 on Saturday and Sunday (Friday and Saturday nights have no fixed end). It can also be stopped by hand, by the skill `gcp-cloud-sql_instance-stop` or by the same manually triggered workflow (`self-shared-database.yml`, which offers `start`, `stop` and `status`);
  - starting takes minutes ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)): skills and deploys that need the database check whether it is running and say so, instead of failing with a connection error;
  - the backup window starts at 20:00 (`America/Sao_Paulo`), an hour when the instance is usually running; a window that falls while it is stopped produces no backup and no error.
- **What the platform is made of** (on GCP): the shared project, the database instance, the scheduler that stops it, the identity that starts and stops it, and the budget alert (`aleogr`, on the whole billing account).
- **One switch identity:** a service account, `aleogr-shared-sql-switch`, with a custom role, `aleogrSharedSqlSwitch`, limited to reading and updating the instance (`cloudsql.instances.get`, `cloudsql.instances.update`). The scheduler jobs run as it, and the workflow impersonates it through workload identity federation (a pool and a GitHub provider in the shared project, accepting only tokens of `aleogr/aleogr` on `main`); no key file exists. The switch is created before the instance, so that the night stop already exists if the creation is interrupted.
- **GitHub secrets:** the workflow reads three Actions secrets of `aleogr/aleogr`, `GCP_SHARED_PROJECT_ID`, `GCP_SHARED_WIF_PROVIDER` and `GCP_SHARED_SWITCH_ACCOUNT` (the shared project's id, the federation provider's name and the switch account's e-mail), pasted by hand from the values the platform skills print ([`cloud-shell.md`](cloud-shell.md)); the repository's logs are public and only secrets are masked.
- **How it is created and changed:** by the orchestrator, with skills that run commands, from the platform declaration ([section 11](#11-project-model)) — the same mechanism as the projects, with the same rules ([section 10.4](#104-behavior-of-every-skill)). It is created once, from the Windows app or Google Cloud Shell, where the CLIs are authenticated ([section 14](#14-where-i-run-claude-code)). Its state is what exists in the cloud ([section 7](#7-where-data-lives)).

---

## 7. Where data lives

- **There will be NO private repository for the shared platform's data, nor tooling in a private repository.** Shared platform data is split into three types:

| Type | Where it lives | Publicly visible? |
|---|---|---|
| Secrets (passwords, tokens, keys) | the provider's `secrets-*` (e.g. GCP Secret Manager) + GitHub Actions/Codespaces secrets when workflows or codespaces need them + network secrets of the Claude Code cloud environment ([section 14](#14-where-i-run-claude-code)) | no |
| Identifiers (shared cloud project ID, DNS zone ID...) | naming convention (preferred) + GitHub Actions variables in `aleogr/aleogr`, read with `gh variable get` | no |
| Shared platform state | discovered in the cloud itself via labels and names (the cloud is the source of truth); if not enough, a state file in a private versioned bucket | no |
| Tooling | `aleogr/aleogr` | yes, on purpose |

- GitHub secrets cannot be read back: they serve to deliver credentials to workflows/codespaces, not to store information the orchestrator queries.
- Actions variables are not publicly visible even in a public repository, but logs of public workflows are: **no workflow may print variables**.
- Environment variables of Claude Code cloud environments are readable by whoever uses the environment: **never put secrets in them**.
- **Discovery rules:**
  - label on everything that accepts labels (`aleogr-platform`, `aleogr-project`, `aleogr-test`);
  - name by convention ALWAYS (it is the identifier of resources without labels, such as databases inside the shared instance and DNS records);
  - variables only for what cannot be deduced (ideally only IDs chosen once).
- The platform's change history comes from the hooks' audit log and the providers' audit logs; decisions are versioned in Git (`.claude-plugin/plugins/aleogr/defaults.json`).
- PROJECT data: the declaration (`.aleogr/project.json`) stays in each project's repository. A project's state follows the same discovery principle as the shared platform's: it is read from the providers, and `project-plan` learns what exists from GitHub itself (the repository, its settings and topics, its protection and its copy of the declaration). **There is no `.aleogr/state.json`**; a state file is added only for something that cannot be discovered.

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

- Every family skill accepts the `shared` mode (inside the shared platform) or `dedicated` (own resources); in the `dev` project environment, the default is `shared`.
- Every skill applies the labels and conventional names from [section 1](#1-names) to EVERYTHING it creates.

### 10.3 Extending contracts

- The contract is the common MINIMUM; plugins may have extra skills, following the same naming convention (e.g. `github_claude-app-install`, `github_codespaces-configure`, `cloudflare_cache-purge`).
- Contracts are only extracted when a second real provider exists; do not invent them in the abstract.
- When a feature depends on the provider's plan and is not available, the skill warns and records it as an open item in the checklist, instead of failing or pretending it was applied.
- Such a feature is `pending`, in `plan` and in `apply` alike: nothing is changed and the `pending` list has one `plan-limit` item saying what the plan forbids ([`CONTRACTS.md`](CONTRACTS.md) section 1.2), so that `plan` never promises what `apply` cannot do. Only an answer of the provider that names the plan counts; any other refusal is `failed`.

### 10.4 Behavior of every skill

- Checks before creating (idempotent).
- Shows each command before running it.
- Stops and asks for confirmation before irreversible or costly actions.
- Follows the MINIMUM COST rule in `dev` ([section 6.5](#65-minimum-cost-contract-rule-in-the-dev-project-environment)).
- Ends with a verification (e.g. `gh repo view`, `gcloud ... describe`, DNS lookup).
- What cannot be automated becomes a checklist.
- platform-* skills start by checking the environment (OS, SDK, connected device).

### 10.5 Tools and dependencies between families

- CLI first (gh, glab, gcloud, aws, az); MCP when there is no good CLI or the official MCP is better. The MCP goes in the family plugin's `.mcp.json`.
- cloud-* provides the base (account/project, identities, permissions, APIs, deploy); service families assume the base exists. The orchestrator guarantees the order.
- secrets-* is unique per project, usually on the primary cloud; credentials for other clouds also live there. In `dev` and `hom`, project secrets live in the shared platform's vault, prefixed with the project.

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
- A project is a list of components (stack, platform, deploy/distribution, location = directory or repository), the project environments ([section 6](#6-project-environments-the-shared-platform-and-minimum-cost)) and the project's shared services.
- **Declaration** in `.aleogr/project.json` in the project repository (what I WANT; written by the `project-declare` skill or by hand). **State** is what EXISTS, discovered from the providers ([section 7](#7-where-data-lives)); there is no state file. The declaration stores no secret, only references.
- The **shared platform** is managed by the same orchestrator, with the same declaration format (marked as `"kind": "platform"`), but without its own repository: choices in `defaults.json`, identifiers by convention and variables, state discovered in the cloud ([section 7](#7-where-data-lives)). Projects point to it in the `dev` and `hom` project environments.

### 11.1 JSON Schema

- In `.claude-plugin/schemas/project.schema.json` (versioned; `version` field in project.json; `$schema` for autocomplete).
- Exclusive families = object; combinable = list.
- Exactly one `primary` cloud (contains + minContains/maxContains = 1).
- payments `mode` with default "test".
- Project names cannot be `test` or `shared`, nor start with `test-`.
- A component may be declared public; without it, in `dev` and `hom` the component is behind the login ([section 6.3](#63-protection-and-single-access-point)).
- `environments` field ([section 6.1](#61-addresses-of-a-projects-environments)).
- Plugin name derived from family + provider.
- Each family plugin may publish a sub-schema for its options.
- Optional `notes` field (JSON does not accept comments).
- A repository's visibility is declared, `public` or `private`, with the default `private`: making a repository public later is easy, the opposite does not undo what was seen.
- Nothing becomes public without its own confirmation, whether at creation or by a change (`confirmVisibility=public`); a change to private needs `confirmVisibility=private`. A skill does not wait for the answer: without the confirmation it changes nothing of the visibility, ends with the question and the exact command that confirms it.
- In a free organization, a private repository has no branch protection (the plan forbids rulesets there): `branch-protect` reports `pending`, and `main` is held by the working rule (Claude Code opens the pull request, the owner merges), not by GitHub.
- **Version 1** of the declaration holds only what has been proven: `version` (`1`), `name`, `repo` and the optional `notes`. `repo` has `provider` (`github`, the only one implemented), `owner`, `name`, `visibility`, `description`, `topics` (extra topics only) and `settings`, which is complete in the file (the seven keys `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects`), so the file says everything about the repository without the defaults. The schema is strict (no unknown key at any level); the skills check a declaration by the same rules written in their own text, so no validator is needed where they run. The declaration grows by stage: components, environments, cloud, database and DNS enter with the stage that proves them ([section 17](#17-implementation-strategy)). Example: `examples/repo-only.json`.
- **The topic `aleogr-<name>` is derived, not typed:** `repo.topics` never holds it; the topics sent to the provider are `aleogr-<name>` plus `repo.topics`, sorted, without duplicates.

### 11.2 Supported layouts (same format)

- **monorepo:** one project.json at the root.
- **manifest:** a PRIVATE repository containing only the full declaration; components point to it; never `aleogr/aleogr`.
- **federated:** each repository has its fragment with `"layout": "federated"`; members found by topic (e.g. `aleogr-my-project`); idempotent creation; removing a shared service checks all members first.
- First of all, decide whether it is ONE project (shares services) or SEVERAL related projects (each with its own declaration).

### 11.3 Activating family plugins

- **Local (Windows app):** in PROJECT SCOPE (versioned `.claude/settings.json`, with the `extraKnownMarketplaces` block from [section 2.3](#23-registering-the-marketplace)), according to the declaration. In multi-repo, each repository activates only the families that concern it.
- **Claude Code cloud sessions:** the repository's `.claude/settings.json` does NOT install plugins in them. Plugins arrive through the cloud environment's setup script ([section 14](#14-where-i-run-claude-code)). How family plugins get there is **PENDING** ([section 18](#18-open-items)).
- **What the repository brings to cloud sessions** (single-repository session): `CLAUDE.md`, `.claude/skills/`, `.claude/agents/`, `.claude/commands/`, `.claude/rules/`, hooks and permissions from `.claude/settings.json`, `.mcp.json`.

### 11.4 The declaration in its repository

- The declaration is written in the project's folder, before the repository exists, and travels with the code.
- **The birth.** A repository that does not exist is born in one `project-apply` run: created with its README, configured, the declaration sent as its first content after the README, then `main` protected. That push is the only direct push to `main` in the repository's life. It is made only to a repository whose default branch has exactly one commit (the README) and no declaration, and before the protection exists; on a repository already protected it is never made.
- **Commit identity.** The folder becomes a checkout of the repository, and its commit identity is set in that checkout only (local git configuration): the account's login as the name and GitHub's no-reply address as the e-mail. A real e-mail address is never used and no global configuration is changed; later commits from that folder carry the same identity.
- **After the birth, only the merged declaration is applied.** A change goes: edit the declaration, pull request, merge, update the folder, `project-apply`. While the local declaration differs from the repository's copy (compared as JSON values, not byte by byte), `project-plan` compares nothing else and shows `merge first`, and `project-apply` stops before any change.
- **Adoption.** A repository with any other history and no declaration is never pushed to: the plan shows `open a pull request`, the declaration enters by pull request, and from its merge the repository is applied like any other.

---

## 12. Skills of the `aleogr` orchestrator

- **Core:**
  - `platform-plan`: compares the shared platform choices in `defaults.json` with the cloud; changes nothing (implemented for the free part: shared project, APIs, budget alert);
  - `platform-apply`: creates and changes the shared platform ([section 6.8](#68-shared-platform-resources)) as `platform-plan` lists (implemented for the free part; asks for one confirmation unless called with `confirm=yes`);
  - `project-declare` (implemented for version 1 of the declaration): writes or edits `.aleogr/project.json` in the current folder from `key=value` arguments. A new declaration needs `name`, `owner` and `description` and takes the rest from `defaults.json`; an existing one keeps everything the arguments do not change, and its `name`, owner and repository name are never changed (that is another project). It writes the file in its canonical form, runs no command and changes nothing on GitHub; `created`, `updated`, `unchanged` or `failed`;
  - `project-plan` (implemented for the repository): validates the declaration, runs `tools-check command=gh`, `github_repo-describe` and `github_checkout-setup mode=plan`, and prints five items with their state and action: `repository`, `settings` (description, topics and the seven settings), `visibility`, `declaration` and `protection`. It changes nothing and ends with `nothing to do` only when every action is `none`. `merge first` and `open a pull request` are actions only the owner can take;
  - `project-apply` (implemented for the repository): runs `project-plan`, takes the plan's confirmation, invokes the `aleogr-repo-github` skills in the order of [section 12.2](#122-apply-order) and runs `project-plan` again; `nothing to do` comes only from that last plan. It stops, changing nothing, on `merge first` or `open a pull request`, and stops at the first step that ends `failed` or `pending` (except the protection's plan limit on a private repository, the expected end there).
  - **Confirmation:** one per run, for the whole plan, and a run is all or nothing. A plan that changes no visibility is confirmed by `confirm=yes`; a plan that creates a public repository or makes one public only by `confirmVisibility=public`, and one that makes a repository private only by `confirmVisibility=private`, which then confirm the whole plan. Without the confirmation its plan needs, the run ends `pending`, changes nothing and shows the text that confirms; a `confirmVisibility` the plan does not need is `failed`, so a confirmation never applies to another plan.
  - Status rule: `pending` as a status means nothing was changed. Once something was done the status says what (`created`, `updated`) and what is left is an item of the `pending` list.
  - The `project-*` skills run no `gh` or `git` command themselves and never wait for an answer.
  - `platform-*` act on the shared platform (they address its project as `project=shared platform=shared`); `project-*` remain for projects.
- **Shortcuts:** `project-create`, `component-add`, `service-add`, `tenant-add` (declares a tenant in an environment and applies it).
- **Maintenance:**
  - `tools-check` (implemented for `gcloud` and where Claude runs, and for `gh` when called with `command=gh`; with no argument it checks only `gcloud`, so the platform skills do not depend on `gh`): CLIs, authentication, MCPs, devices; identifies whether it runs locally, in a codespace or in a cloud session and warns about what is not possible there;
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

1. Repositories: create → configure (settings, then visibility) → send the declaration (only at the birth, [section 11.4](#114-the-declaration-in-its-repository)) → protect.
2. Domain registration.
3. Cloud base (or verification of the shared platform).
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
  - DNS records `test-<id>-<environment>` directly under `aleogr.dev`, and the tenants below them;
  - databases `test_<id>`;
  - cloud services/resources `test-<id>-...` with label `aleogr-test=<id>`; on GCP, a test's projects only inside the folder `tst` ([section 6.7](#67-gcp-organization-folders-and-billing)).
- The hook is built with the first `*-remove` skill (`database-remove`), when there is something for it to guard and a real case to test it against on Windows. Until then the shared instance is covered by the provider's deletion protection.
- **PreToolUse on Write/Edit** blocking secrets in versioned files.
- **PostToolUse on Write/Edit** validating project.json against the schema.
- **PostToolUse formatting** per stack.
- **SessionStart** injecting a summary of the declaration and manual open items.
- **SessionStart in the project repository**, only when `CLAUDE_CODE_REMOTE=true`, installing the project's light needs in Claude Code cloud sessions ([section 14.2](#142-claude-code-cloud-environments)).
- **PostToolUse on Bash** recording an audit log of infrastructure commands (also the shared platform's history).
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

- Short; points to `.aleogr/project.json`, keeps conventions.
- Per-directory CLAUDE.md with each stack's conventions.

### 13.7 Future

- Scheduled (weekly) GitHub Action running project-plan on projects and opening an issue on drift.

---

## 14. Where I run Claude Code

- I use Claude Code in the Windows app and on the web (cloud sessions), and I want to be able to use GitHub Codespaces.
- Infrastructure setup (creating repositories, gcloud auth login, Cloudflare OAuth, gh auth login) is done in the **WINDOWS APP** or in Google Cloud Shell ([section 14.3](#143-claude-code-in-google-cloud-shell)). Do not store admin-level credentials in Claude Code cloud sessions ([section 14.1](#141-claude-code-cloud-sessions-web-app-mobile-claude---cloud)): they are disposable machines. The Cloud Shell home directory is different: it belongs to my Google account.
- **From a browser only** (a computer where nothing can be installed): Claude Code runs inside **Google Cloud Shell**, the terminal of the Google Cloud console, which is already signed in to my Google account and has `gcloud`. The skills run there as in the Windows app, with no credential leaving Google and no new identity. Set-up, once: [section 14.3](#143-claude-code-in-google-cloud-shell). A cloud session ([section 14.1](#141-claude-code-cloud-sessions-web-app-mobile-claude---cloud)) cannot do this: its `gcloud` has no login, and the organization forbids the keys that would give it one.
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
  1. the `base` environment is the single base, common to every project;
  2. light project-specific needs are installed by a **SessionStart hook in the project repository** (only when `CLAUDE_CODE_REMOTE=true`), generated by the orchestrator from the declaration, with each `stack-*`/`platform-*` contributing its part — this is the layer that composes;
  3. an additional environment exists only for what the hook cannot provide: heavy toolchain (needs the setup script cache), different network or different network secrets.
- What ONLY the environment can provide: network access, network secrets, variables and the setup script cache. The repository hook runs on every session start, without that cache, and only reaches what the environment's network allows.
- **Default:** one environment per NEEDS PROFILE. An environment per project is accepted only as a last resort, for a heavy and rare combination of profiles.

#### `base` environment (default, the only one at first)

- Custom network: default package manager list + domains the sessions need to reach (e.g. the project addresses under `aleogr.dev`).
- Setup script: registers the `aleogr` marketplace and installs the orchestrator (`claude plugin marketplace add` + `claude plugin install`), and writes my personal `~/.claude/CLAUDE.md`. Same responsibility as the `base` Feature ([section 5](#5-dev-containers-and-codespaces)); keep them consistent. Test whether plugin installation works at this stage.
- Network secrets for APIs with a fixed token; variables only with non-sensitive values.

#### Additional environments

- ONLY when a truly different profile appears and the repository hook is not enough: heavy toolchain (e.g. `android` with the Android SDK, keeping the `base` script under the cache limit) or different network (e.g. one without network, for reviewing third-party code).
- A project that needs an additional profile PLUS something light uses that profile's environment and gets the rest from its SessionStart hook. Only a combination of two heavy profiles requires an environment of its own.

#### Canonical version

- Environments are configured in the claude.ai interface, not by file. The CANONICAL version (setup script, allowed domains, description of network secrets without values) is versioned in `docs/cloud-environments/<environment>.md` in `aleogr/aleogr`, without IDs or secrets, and copied to the interface when it changes.
- **Setup scripts are assembled from FRAGMENTS:** each profile is one fragment (e.g. base, Android SDK); an environment's script is the sum of the fragments it needs, with every additional environment starting from the base fragment. A combined environment reuses the fragments instead of duplicating script text.

---

### 14.3 Claude Code in Google Cloud Shell

For running the skills against real Google Cloud from a browser. Tested on 2026-11-17 ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)).

- Claude Code, the marketplace and the plugins are installed once in the Cloud Shell home directory, which Google keeps between sessions. The step-by-step instructions (set-up, daily use, updating) are in [`cloud-shell.md`](cloud-shell.md).
- The orchestrator reads its `defaults.json` from the plugin's folder, outside the working directory, and Claude Code asks to allow that read: allow that one read each time, never every read outside the working directory, because the home directory holds the Google credentials.
- It is slower than the Windows app (a small shared machine), and Cloud Shell disconnects after a while idle.
- Cloud Shell has `gh` preinstalled ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). The Google Cloud skills and the GitHub skills run here: `gh` is signed in once with `gh auth login`, with the scopes it asks for. The other families' CLIs are signed in here when their skills exist, with the least permissions each skill needs (Cloudflare: an API token limited to editing the DNS of the zone `aleogr.dev`).

---

## 15. Tests

> This section records the **DIRECTION** of the tests. Execution details are still open and will be defined before implementation; **do not implement anything from this section without confirmation**.

Tests test the **TOOLING** (`aleogr/aleogr`), not my products: "if I run `/aleogr:project-create` with this declaration, does a working project come out?". Not to be confused with the `hom` project environment, which tests a product. Tests use the **SHARED PLATFORM** (zero extra infrastructure cost and realism: they exercise the same sharing as real projects), and on GCP their projects live in the folder `tst` ([section 6.7](#67-gcp-organization-folders-and-billing)).

### 15.1 Layer 1 — in the repository itself (static, creating nothing outside), on every PR

- `self-validate-marketplace.yml`: validation of the marketplace and naming rules, and of the example declarations against the schema.
- `self-lint.yml`: static checks of workflows and hook scripts.
- `self-test-features.yml`: Feature tests with the dev containers CLI, using `.devcontainer/features/test/`.
- Skill tests (`.claude-plugin/tests/`): `run.sh <scenario>` runs the real skills headless (`claude -p`) against fake CLIs (a fake `gcloud` and a fake `gh` in `.claude-plugin/tests/bin/`, with numbered responses for calls that must answer differently before and after a change) and checks the logged calls and the final answer against the scenario's `expect.txt` (line types in `.claude-plugin/tests/README.md`). They create nothing outside the repository, are run by hand for now (no workflow), and each run costs model usage.
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
- Each test uses an `<id>` in ALL resources ([section 1](#1-names)): repository `test-<id>`, a GCP project per environment created like a real one but inside `tst` (`gcp_environment-create` with `root=tst`), services `test-<id>-<component>`, database `test_<id>` on the shared instance, `test-<id>-<environment>.aleogr.dev` (tenants: `<tenant>.test-<id>-<environment>.aleogr.dev`).
- **The test:** run `/aleogr:project-create` with a declaration from `.claude-plugin/schemas/examples/`; check:
  - green CI;
  - address responding (and tenants, if any);
  - codespace opening with the right tools;
  - a Claude Code cloud session in the `base` environment working on the created repository;
  - final `project-plan` saying "nothing to do".
- **Example scenarios:**
  - simple backend (1 component, 1 project environment);
  - multi-tenant monorepo (2 components, two tenants, CI running only the changed component's job);
  - two project environments (dev + hom, with promotion in cd.yml);
  - Android app (only repository, CI and devcontainer, no DNS or cloud).
- **Every test creates a new `test-<id>` repository**; there is no fixed, reused test repository. Skills that only touch files of a project are tested with a minimal declaration (repository only, no cloud or DNS).
- Initially run manually; automate later, if it makes sense.

### 15.4 Reference project

- **The tooling is driven by a reference project, `pilot`**, in the GitHub organization `aleogr-sandbox` and, on GCP, in the folder `tst` ([section 6.7](#67-gcp-organization-folders-and-billing)): a status page per tenant, multi-tenant from the start, with two components at first, `status` (public by nature) and `admin`.
- Everything is behind the login by default ([section 6.3](#63-protection-and-single-access-point)); `status` is opened to the public only during the test of that path, because a public address is found by bots and each visit wakes the service.
- Its repository, `aleogr-sandbox/pilot`, is born private and then made public, and stays public: one repository proves both behaviours of the free plan, a private repository whose protection is `pending` and a public one protected by the ruleset `main`.
- It stands in for the first real project (an identity provider: Go, monorepo, not multi-tenant; later products may be multi-tenant), so that the tooling is proven before a real project depends on it ([section 17](#17-implementation-strategy)).
- Small disposable `test-<id>` projects, one per scenario of [section 15.3](#153-layer-3--end-to-end), come after both creation AND removal work on `pilot`.

### 15.5 Payments

- Always in test mode.

### 15.6 Cleanup

The scheduled workflow `self-cleanup-tests.yml` deletes tests older than a few days, in this order:

1. Find the test's resources by its `<id>`, by the names and labels of the discovery rules ([section 7](#7-where-data-lives)).
2. Delete the external resources (cloud, also checking the label `aleogr-test=<id>`; on GCP, projects only inside the folder `tst`; DNS records/routes matching the pattern; databases `test_<id>`; codespaces).
3. Delete the repository LAST (it holds the test's declaration).

The destructive command guard has exceptions ONLY for these cases ([section 13.1](#131-hooks)).

---

## 16. Discarded decisions

- Dedicated marketplace repository (`aleogr-claude-plugins`): replaced by `aleogr/aleogr`.
- Tooling in a private repository (with everything): on the free plan it would lose branch protection, unlimited Actions minutes and use of the workflows by repositories of other owners (such as the test organization), and would complicate Features, schema and marketplace.
- A private repository only for the shared platform's data: replaced by secrets in the vault, identifiers by convention and Actions variables, and state discovered in the cloud.
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
- Test projects (with code) inside `aleogr/aleogr`; test repositories in the personal account; a separate cloud project only for tests (fixed "sandbox" on GCP). The reference project `pilot` gets its own cloud projects, created like a real project's inside the folder `tst` ([section 6.7](#67-gcp-organization-folders-and-billing)); whether each disposable test does too is provisional ([section 1](#tests)).
- A separate DNS tree for tests (`sandbox.aleogr.dev`): tests live directly under `aleogr.dev` with a reserved prefix, for the shorter URL.
- Path-based tests (`<host>/test-<id>`): would require a router, apps under a subpath (different from reality), origin shared between tests (cookies and storage leaking) and would not support tenants.
- Staging as `hom.<project>.aleogr.dev` (conflicts with tenants).
- Proxied tenant records in `dev` and `hom`, paying for Advanced Certificate Manager; and Cloudflare Access as the protection of `dev` and `hom` (requires proxied records).
- Terraform for the shared platform, applied by CI (alone, or mixed with skills for the projects): deterministic and reviewable, but a second way of working for five or six pieces created once, with a state bucket, an identity with many permissions and a pull request per change. It stays as the way out if the shared instance suffers unwanted changes.
- For the protection of `dev` and `hom`: no login, only cost ceilings (bots keep spending up to the ceiling, including on endpoints that call paid services); login only inside the application (the request reaches the service and costs before the login is checked). Chosen: a login in front of every service, plus the ceilings.
- For tenant addresses in `dev` and `hom`: a Cloudflare Worker routing every hostname outside production, with proxied records and flattened names (a format different from production, undoes the unproxied decision, and one piece whose failure takes down everything that is not production); a load balancer with a wildcard certificate (fixed cost); tenants by path or header only outside production (behaviour different from production). Chosen: one record and one mapping per tenant.
- In `dev`: dedicated instances per project, load balancer, static IP, NAT or any fixed cost per project.
- A single cloud environment holding the resources of every project outside production: each project has its own, and only fixed-cost resources are shared.
- For the shared database, a private address only (no address charge, about R$ 9 per month instead of about R$ 50): the database would be reachable only from inside Google Cloud, with no access from my computer or from GitHub Actions, and every project would have to be attached to a shared network.
- For the shared database: always on (fixed cost with nobody using it); sleeping only on weeknights (saves little); a serverless PostgreSQL outside GCP (another provider, and a connection different from production). Chosen: off by default, started on demand.
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
- Managed cache/search with fixed cost in `dev`: serverless or free tier instead.
- Versioned content in Portuguese: everything in the repository is in English (section 0).
- A subdomain for everything that is not production (`lab.aleogr.dev`, with addresses such as `<project>.lab.aleogr.dev`): its only purpose was to avoid collisions with other names of the domain, which the environment suffix already prevents ([section 6.1](#61-addresses-of-a-projects-environments)); it also gave the word "lab" two meanings (the umbrella and one environment).
- A second GCP organization for the tests: an organization is created automatically, one per Google account (or one per Workspace/Cloud Identity account with a domain), so a second one needs a second account or a domain ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)); it would also mean two sets of policies to keep equal and skills that must choose between organizations. The folder `tst` gives what matters: a cleanup limited to tests ([section 6.7](#67-gcp-organization-folders-and-billing)).
- `tst` as a fourth environment, or every test project flat inside `tst`: a test project must go through the real environments and the real "folder of its environment" rule.

---

## 17. Implementation strategy

- Build guided by the **NEXT REAL PROJECT**: only the plugins, workflows, actions and Features it requires (probably `aleogr`, `aleogr-repo-github`, `aleogr-cloud-gcp`, `aleogr-dns-cloudflare`, the `base` Feature, the `base` cloud environment and the reusable workflows for the project's stacks). **Goal:** the project comes out of nothing without me opening any dashboard.
- Before the first project: redesign and declare the shared platform, from scratch ([sections 6](#6-project-environments-the-shared-platform-and-minimum-cost), [7](#7-where-data-lives) and [18](#18-open-items)).
- **Orchestrator MVP:** `tools-check`, `project-declare`, `project-plan`, `project-apply`, plus the destructive command guard hook (already with the test exceptions) and read permissions in `allow`.
- The next real project's declaration, with fictitious values, becomes the first example in `.claude-plugin/schemas/examples/` and the first end-to-end test, before being applied to the real project.
- New families, providers, actions, workflows, Features and cloud environments come in when a real project needs them.
- **Until the first real project starts, the reference project `pilot` drives the tooling** ([section 15.4](#154-reference-project)). The first real project is an identity provider (Go, monorepo, not multi-tenant); later products may be multi-tenant, which is why `pilot` is multi-tenant from the start.
- **Stages after the shared platform** (stages 1 and 2 created it, [section 18](#18-open-items)); stages 3a and 3b are built, the rest is not:
  3. repository, in three parts, each with its own real run and pull request ([design of 3a](plans/2026-11-18-pilot-stage-3a-design.md)):
     - 3a: the GitHub plugin `aleogr-repo-github`, which creates, configures and protects the repository of `pilot`;
     - 3b: the declaration and `project-declare`, `project-plan` and `project-apply`, which drive the plugin from a file, and `github_checkout-setup`, which sends the declaration at the birth ([design of 3b](plans/2026-11-18-pilot-stage-3b-design.md));
     - 3c: a Go skeleton and CI;
  4. running in `dev`: the GCP project, a database on the shared instance, both services behind the login, CD;
  5. addresses and tenants: the Cloudflare plugin, certificates, `tenant-add`, and the test that opens `status` to the public and closes it again;
  6. the rest: a third component with scheduled checks, `hom`, removal with the destructive-command hook, and the disposable `test-<id>` scenarios.

---

## 18. Open items

- [x] **Create the shared platform, free part (stage 1):** the shared project, its APIs and the budget alert ([section 6.8](#68-shared-platform-resources)). Created on 2026-11-16 by `platform-apply`, in the Windows app.
- [x] **First real run of stage 1**, by me in the Windows app, on 2026-11-16, following [`plans/2026-11-16-shared-platform-stage-1-run.md`](plans/2026-11-16-shared-platform-stage-1-run.md). It ended with `nothing to do`; what it showed is in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [x] `platform-plan`, run without a project id, finds the existing shared project by its labels: confirmed on 2026-11-16, in a new session.
- [x] **Create the shared platform, database part (stage 2)** ([sections 6.1, 6.3 and 6.8](#68-shared-platform-resources)): created on 2026-11-17 by `platform-apply`, in the Windows app, on the first attempt. The night stop was proven at creation, and the manual workflow ran `status`, `start` and `stop`. What the run showed is in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [ ] Confirm on the first bill that the public address is charged only while the instance is stopped, and the real fixed cost of the stopped instance.
- [x] The `starting` state works in a real run (2026-11-17): the workflow showed `starting` after a start and `running` minutes later; the switch account may list the instance's operations.
- [x] Knowledge Catalog integration turned off on the shared instance (2026-11-17); new instances are created with it off.
- [x] The fields the budget comparison and the jobs' last run read are right (2026-11-17, `platform-plan` in Cloud Shell): the budget showed as compared and equal, the weeknight job's last run as succeeded, the weekend job as never run. Not exercised: `gcloud billing budgets update` (nothing differed) and a job whose last run failed.
- [ ] Build the destructive-command hook ([section 13.1](#131-hooks)) with the first `*-remove` skill (`database-remove`); until then the shared instance relies on the provider's deletion protection.
- [ ] Decide how a multi-tenant project is served in `prd` (own domain, proxied records), when the first one exists.
- [x] The real resources were moved to the new names on 2026-11-17, from Cloud Shell: the folder renamed to `dev`, `tst` and `tst/dev` created, the shared project created under its new id by `platform-apply` (the night stop proven at creation, the workflow `self-shared-database` green with the new secrets), and the old project, instance, budgets and secrets deleted. The DNS zone needed nothing.
- [ ] Before proxying any environment (`prd` included), test that the destination (a Cloud Run domain mapping) still issues and renews its certificate behind the Cloudflare proxy ([section 6.2](#62-https-and-certificates)).
- [ ] Test, on the first service in `dev`: that IAP enabled directly on Cloud Run also protects the address that arrives through a domain mapping (the documentation says "all ingress paths" but does not name domain mappings), and that it has no cost in this use.
- [ ] Create the Claude Code `base` cloud environment; test whether the setup script can register the marketplace and install plugins; define the allowed domains and network secrets (e.g. Cloudflare API token); version the canonical definition in `docs/cloud-environments/base.md`.
- [ ] Measure the project SessionStart hook in cloud sessions (it runs on every session start, without the setup script cache) to define the practical limit of a "light" need; above it, the need goes to an environment.
- [ ] Check how Claude Code cloud environments can be associated with repositories in the current product (section 14.2 says they do not belong to repositories) and whether that changes the naming rule.
- [ ] Define how FAMILY plugins reach cloud sessions. Options:
  - (a) the `base` setup script installs all marketplace plugins (no collision, thanks to the provider in skill names, but more skills in context);
  - (b) a project SessionStart hook, only when `CLAUDE_CODE_REMOTE=true`, installs the declaration's plugins (test whether they load without restarting the session).
- [ ] Define the test execution details ([section 15](#15-tests)) before implementing them.
- [ ] Define the shared platform identifiers that cannot be deduced and store them in `aleogr/aleogr`; configure budget alerts. The three values of stage 2 (`GCP_SHARED_PROJECT_ID`, `GCP_SHARED_WIF_PROVIDER` and `GCP_SHARED_SWITCH_ACCOUNT`: the shared project's id, the federation provider's name and the switch account's e-mail) are Actions **secrets**, not variables: the repository's logs are public and only secrets are masked.
- [x] Registration via `extraKnownMarketplaces` with `path`: tested on 2026-11-16 in the Windows app. The marketplace is downloaded, but the app lists no plugin from it. The catalog moved to the standard location ([section 2.2](#22-marketplace-structure-rules)).
- [x] Plugins install in the Windows app from the catalog at the standard location, with the plugin folders inside `.claude-plugin/`: confirmed on 2026-11-16.
- [ ] Test referencing a local Feature in a nested path (`./features/src/base`); if it doesn't work, move the Features up one level.
- [ ] Mark the Features as public on GHCR after the first publication.
- [ ] Configure the Codespaces spending limit and idle timeout; create the Codespaces secret for Claude Code authentication.
- [x] Can an installed plugin read files of the marketplace outside its own folder? No. `defaults.json` lives in the orchestrator plugin (`.claude-plugin/plugins/aleogr/`) and `contracts.json` (section 10.1) will live there too.
- [ ] Decide whether plugin-create/marketplace-validate live in `aleogr` or in `aleogr-dev`.
- [x] Evaluate, with the MVP, making projects' `state.json` lighter or just a cache of discovery: answered in stage 3b. A project's state is discovered from the provider; there is no state file ([section 7](#7-where-data-lives)).
- [x] Protection of `aleogr/aleogr`'s `main`: a branch ruleset named `main`, created by hand on 2026-11-17 (active, empty bypass list, default branch; restrict deletions, block force pushes, require a pull request with 0 approvals). Made by hand because the repository of the marketplace is not created by the skills; `github_branch-protect` ([`CONTRACTS.md`](CONTRACTS.md)) must find it and change nothing when it exists.
- [x] The GitHub account has two-factor authentication on (checked on 2026-11-17).
- [x] **First real run of stage 3a**, by me in Cloud Shell on 2026-11-18, following [`plans/2026-11-18-pilot-stage-3a-run.md`](plans/2026-11-18-pilot-stage-3a-run.md): `aleogr-sandbox/pilot` created private and configured, its protection `pending`, then made public and protected, and every skill `unchanged` at the end. Every step answered as expected on the first attempt; what it showed is in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [x] How GitHub answers a ruleset request on a private repository of a free organization: it refuses the read of the rulesets, so `plan` and `apply` both end `pending` without writing ([section 10.3](#103-extending-contracts)). Confirmed on 2026-11-18.
- [ ] The GitHub skills have not run in the Windows app (PowerShell): the quoting of the description and the path of the ruleset file are proven in bash only.
- [x] Make the skills that decide by a command's exit code also name the text that identifies each case ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)): done in stage 3b for the GitHub skills, `github_checkout-setup` included; when the two disagree, the text decides.
- [x] **First real run of stage 3b**, by me in Cloud Shell on 2026-11-18, following [`plans/2026-11-18-pilot-stage-3b-run.md`](plans/2026-11-18-pilot-stage-3b-run.md): `aleogr-sandbox/pilot` deleted by hand and born again from its declaration, then a change to the declaration applied after its pull request is merged. Every step answered as expected on the first attempt: the birth ended `nothing to do`, the birth commit carries GitHub's no-reply address, an unmerged change stopped on `merge first`, and after the merge the change was applied. What it showed is in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [ ] `project-declare` repeats "nothing is public until `project-apply` runs with `confirmVisibility=public`" when it edits the declaration of a repository that is already public; the sentence belongs only where it is true. Fix with the next change to the skill.
- [ ] The `project-*` skills and `github_checkout-setup` have not run in the Windows app (PowerShell).
- [ ] Start the first real project (an identity provider, [section 17](#17-implementation-strategy)) once the reference project `pilot` has gone through the stages there.
