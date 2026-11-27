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

- Reusable workflows: prefix by purpose (`ci-` checks, `deploy-` deploys, `release-`), then the stack or the destination (`ci-go.yml`, `deploy-cloud-run.yml`).
- Workflows that run in this repository itself: prefix `self-`.
- The purpose comes first because the workflows folder is flat (the prefix is the only grouping). A project calls both kinds from its one `ci.yml` ([section 4](#4-cicd)).

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

- Project resources: services `<project>-<component>`, database `<project>_<environment>` on the shared instance (every `-` of the project's name written `_`: `pilot_dev`), with one database user per component that uses it, named as Cloud SQL names that component's service account (`<project>-<component>@<project id>.iam`, [section 6.4](#64-shared-platform--project-resources)), record `<project>-<environment>.aleogr.dev` ([section 6.1](#61-addresses-of-a-projects-environments)), labels `aleogr-project=<project>` and `aleogr-environment=<environment>`.
- Inside a project's own GCP project ([section 6.4](#64-shared-platform--project-resources)):
  - the image repository is `<project>` (Artifact Registry, format Docker, in the declared `cloud.region`, with the two labels above), and the image of a component is `<region>-docker.pkg.dev/<projectId>/<project>/<component>`;
  - the CI identity is the service account `<project>-ci` and the workload identity pool `github` with its provider `github` (location `global`). A service account id has 6 to 30 characters, so a project with environments needs a name of at least 3 characters (the declaration's rules check it, [section 11.6](#116-cloud-and-environments));
  - each component is the Cloud Run service `<project>-<component>`, in `cloud.region`, running as its own service account of the same id, with the labels `aleogr-project=<project>`, `aleogr-environment=<environment>` and `aleogr-component=<component>`; its address is the one Cloud Run gives it (`https://<service>-<project number>.<region>.run.app`). The name is also the account's id, so it has 6 to 30 characters, and no component's name ends with `-` (the declaration's rules check both, [section 11.6](#116-cloud-and-environments));
  - the repository's Actions secrets are `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT` and `GCP_IMAGE_PATH`; the region is not one of them: it is written in the project's `ci.yml` ([section 4](#4-cicd)).
- Shared platform resources: names starting with `aleogr-shared` (project `aleogr-shared-<random>`, instance `aleogr-shared`, jobs `aleogr-shared-stop-weeknight` and `aleogr-shared-stop-weekend`, service account `aleogr-shared-sql-switch`; the custom role is `aleogrSharedSqlSwitch`, since role ids take no hyphen; the budget alert is `aleogr`, on the whole billing account) and label `aleogr-platform=shared` ([section 6.8](#68-shared-platform-resources)).

### Tests

- Separate GitHub organization: `aleogr-sandbox`. It may also hold my own experiments, which never use the `test-` prefix or the `aleogr-test` topic.
- One short random `<id>` per test, used in **ALL** of the test's resources:
  - repository `test-<id>`;
  - topic `aleogr-test`;
  - services `test-<id>-<component>`;
  - database `test_<id>_<environment>`;
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
│   ├── dependabot.yml                         ← updates action references of this repo, weekly (built)
│   ├── actions/                               ← composite actions (subfolders allowed)
│   │   ├── README.md                          ← how to reference, actions-v1, SHA (skeleton)
│   │   ├── detect-changes/action.yml          (future)
│   │   ├── go-setup/action.yml                (future)
│   │   └── java-setup/action.yml              (future)
│   ├── testdata/
│   │   ├── ci-go/                             ← Go module the self-test of ci-go.yml checks: the starting point of a component `sample` (built)
│   │   └── deploy-cloud-run/check.sh          ← static check of deploy-cloud-run.yml (built)
│   └── workflows/                             ← flat folder (GitHub requirement), organized by prefix
│       ├── README.md                          ← prefixes, workflow_call only, workflows-v1 (skeleton)
│       ├── self-validate-marketplace.yml      ← validates marketplace and example declarations on every PR
│       ├── self-lint.yml                      ← static checks of workflows and scripts on every PR
│       ├── self-test-features.yml             ← tests the Features (test/ folder) on every PR
│       ├── self-publish-features.yml          ← publishes the Features to GHCR
│       ├── self-cleanup-tests.yml             ← scheduled: deletes resources of old tests
│       ├── self-shared-database.yml           ← manually triggered: starts, stops or shows the state of the shared platform's database
│       ├── ci-go.yml                          ← reusable: checks one Go component (built)
│       ├── self-test-ci-go.yml                ← runs ci-go.yml on .github/testdata/ci-go, on PRs that touch them (built)
│       ├── deploy-cloud-run.yml               ← reusable: builds, pushes and deploys one component to its existing Cloud Run service, by digest (built)
│       ├── self-test-deploy-cloud-run.yml     ← runs check.sh on deploy-cloud-run.yml, on PRs that touch them (built)
│       └── ci-java.yml                        (future, reusable)
└── .claude-plugin/                            ← the whole marketplace; the repository root is the marketplace root
    ├── README.md                              ← how to register the marketplace (skeleton)
    ├── marketplace.json                       (built: aleogr, aleogr-cloud-gcp, aleogr-db-gcp-cloud-sql, aleogr-registry-gcp-artifact-registry, aleogr-repo-github, aleogr-stack-go)
    ├── tests/                             ← skill tests: run.sh, fake gcloud, gh, git and sleep in bin/, scenarios/ (built, section 15.1)
    ├── schemas/
    │   ├── README.md                          ← purpose, versioning and examples of the schema (built)
    │   ├── project.schema.json                ← the declaration, version 1: the project name, its repository, its components, its cloud and its environments (built)
    │   └── examples/                          ← example declarations (JSON only, fictitious values)
    │       ├── repo-only.json                 ← a version 1 declaration (built)
    │       ├── with-components.json           ← the same with two Go components (built)
    │       ├── with-environment.json          ← the same with the cloud and the environment `dev` (built)
    │       └── go-gcp-cloudflare.json         (future)
    └── plugins/
        ├── README.md                          ← names, family types, plugin skeleton (skeleton)
        ├── aleogr/                            ← orchestrator (MVP; built: manifest, defaults.json, the three platform skills and the four project skills)
        │   ├── .claude-plugin/plugin.json
        │   ├── defaults.json              ← my personal defaults (choices only, no IDs)
        │   ├── skills/
        │   │   ├── tools-check/SKILL.md           (built)
        │   │   ├── platform-plan/SKILL.md         (built)
        │   │   ├── platform-apply/SKILL.md        (built)
        │   │   ├── project-declare/SKILL.md       (built)
        │   │   ├── project-plan/SKILL.md          (built)
        │   │   ├── project-apply/SKILL.md         (built)
│   │   └── project-access/SKILL.md        (built)
        │   ├── hooks/hooks.json               ← destructive command guard
        │   └── scripts/guard-destructive.sh
        ├── aleogr-repo-github/                (MVP; built: manifest, the two ruleset files and the eight skills marked built)
        │   ├── .claude-plugin/plugin.json
        │   ├── files/ruleset-main.json        ← the ruleset `main` that github_branch-protect sends (same rules as aleogr/aleogr's)
        │   ├── files/ruleset-main-ci.json     ← the same plus the required status check `ci` (sent with checks=ci)
        │   └── skills/
        │       ├── github_repo-describe/SKILL.md      ← contract (built)
        │       ├── github_repo-create/SKILL.md        ← contract (built)
        │       ├── github_repo-configure/SKILL.md     ← contract (built)
        │       ├── github_branch-protect/SKILL.md     ← contract (built)
        │       ├── github_checkout-setup/SKILL.md     ← contract: the folder's checkout, the declaration sent at the birth and the folder's update after a merge (built)
        │       ├── github_pull-request-open/SKILL.md  ← contract: proposes named files by pull request (built)
        │       ├── github_ci-set-secret/SKILL.md      ← contract
        │       ├── github_ci-setup/SKILL.md           ← contract: writes the project's ci.yml from the declared components, with the deploy jobs (built)
        │       ├── github_variables-set/SKILL.md      ← contract action variables-set: the repository's Actions variables, or with `kind=secrets` its Actions secrets (built)
        │       └── github_claude-app-install/SKILL.md ← extra (future)
        ├── aleogr-cloud-gcp/                  (MVP; built: manifest and the ten skills marked built)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/ gcp_environment-describe (built), gcp_environment-create (built), gcp_services-enable (built), gcp_budget-alert-setup (built), gcp_ci-identity-setup (built), gcp_login-describe (built), gcp_login-setup (built), gcp_deploy-describe (built), gcp_deploy-setup (built), gcp_access-grant (built)
        ├── aleogr-db-gcp-cloud-sql/           ← the shared platform's database: instance skills (describe, create, start, stop, switch-setup)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/ gcp-cloud-sql_instance-describe, gcp-cloud-sql_instance-create, gcp-cloud-sql_instance-start, gcp-cloud-sql_instance-stop, gcp-cloud-sql_instance-switch-setup
        ├── aleogr-registry-gcp-artifact-registry/ ← a project's image repository in its own GCP project (built: manifest, the policy file and the four skills)
        │   ├── .claude-plugin/plugin.json
        │   ├── files/cleanup-policy.json      ← the two rules of the cleanup policy (keep the 5 most recent versions, delete the rest)
        │   └── skills/ gcp-artifact-registry_registry-describe, gcp-artifact-registry_repository-create, gcp-artifact-registry_cleanup-configure, gcp-artifact-registry_access-grant
        ├── aleogr-dns-cloudflare/             (MVP)
        │   ├── .claude-plugin/plugin.json
        │   ├── .mcp.json                      ← official Cloudflare MCP (https://mcp.cloudflare.com/mcp)
        │   └── skills/ cloudflare_record-add
        └── aleogr-stack-go/                   (built: manifest, the templates and go_setup)
            ├── .claude-plugin/plugin.json
            ├── files/                         ← go.mod.tmpl, main.go.tmpl, main_test.go.tmpl: the starting point of a Go component
            └── skills/go_setup/SKILL.md       ← contract action setup: writes the starting point and the Dockerfile once (built)
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
  - in projects, `uses:` are pinned by commit SHA; a project's `ci.yml` pins the reusable workflow to a commit of this repository ([section 4](#4-cicd)), and how projects receive updates of their pins (Dependabot, Renovate or a regenerated file) is open ([section 18](#18-open-items)).
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
- **A single `.github/workflows/ci.yml` per project**, generated from the components of the declaration ([section 11.5](#115-components)) and written in the project's folder; it reaches the repository in the tooling's pull request, like every other change ([section 11.4](#114-the-declaration-in-its-repository)):
  - **its first line is a marker**, `# aleogr-ci 1 <name>:<path>:<stack>:<version>,…`, with the components sorted by name, and the second line says that the file is generated and not edited. With deploy jobs (below) the marker is of version 2, `# aleogr-ci 2 <entries> deploy=<environment>:<components joined by +> project=<project> branch=<default branch> region=<region>`, so that a change of the environment, of which components are deployed, of the project, of the default branch or of the region, all written into the deploy jobs, also rewrites the file. Whether `ci.yml` is as declared is decided by comparing that line, never the YAML. The file is owned by the tooling: when the marker differs it is rewritten whole;
  - it runs on `pull_request` and on `push` to the default branch;
  - a `changes` job detects what changed (`dorny/paths-filter` pinned by SHA; candidate to become the composite action `aleogr/aleogr/.github/actions/detect-changes`, which receives the list of components), with one output per component: the component's folder (`<path>/**`) or `ci.yml` itself, so a change to `ci.yml` runs every component;
  - one job per component, named after it, with `needs: changes` and `if:` on its output, calling its stack's reusable workflow (`<workflows repository>/.github/workflows/ci-go.yml@<sha>` with `working-directory` and `go-version`); the workflows repository is `ci.workflowsRepository` of `defaults.json` (`aleogr/aleogr`). Two components of the same stack are two jobs calling the same reusable workflow;
  - **a last job `ci`**, which needs `changes` and every component job and runs `if: always()`: it passes only when `changes` succeeded and every component job passed or was skipped. If the change detection failed, every component job would be skipped, and a skip must not read as a pass. `ci` is the one status check the protection requires (below). Because the jobs are named after the components, a component is never named `changes` or `ci`, nor `true`, `false`, `null`, `yes`, `no`, `on` or `off`, words YAML does not read as names.
- **The reusable workflow is pinned by commit.** `ci.yml` pins it to the commit of the head of `main` of the workflows repository when the file is first generated, and keeps that commit when it is regenerated, so that a plan does not differ every time `aleogr/aleogr` moves; `github_ci-setup ref=latest` moves it. The tags `workflows-v1` are not used yet, and how projects get updates of the pinned commit and of the actions inside `ci.yml` is open ([section 18](#18-open-items)).
- **Third-party actions are pinned by full commit SHA**, with the version in a comment (`actions/checkout`, `actions/setup-go`, `dorny/paths-filter`). In this repository `.github/dependabot.yml` proposes their updates weekly; the ones a project's `ci.yml` uses are written by `github_ci-setup` from its own text.
- **The check `ci` is required exactly when `.github/workflows/ci.yml` is on the repository's default branch**, never because components are merely declared: a required check that no workflow reports would block every pull request, the one that adds `ci.yml` included. So the pull request that adds `ci.yml` is merged without the check, and the run after the merge makes the protection require it ([section 12](#12-skills-of-the-aleogr-orchestrator)). The protection then refuses the merge of a pull request whose job `ci` fails.
- **`ci-go.yml`**, the reusable check of one Go component (one module in one folder): `on: workflow_call` only, inputs `working-directory` and `go-version` (both required), `permissions: contents: read`, no secrets. One job `go` on `ubuntu-latest`, limited to 15 minutes: checkout without persisting credentials, set up Go with no cache, `gofmt -l` (fails and lists the files that are not formatted), `go vet ./...`, `go test ./...`, `go build ./...`. The inputs reach the scripts only through `defaults` or `env`, never written into a script.
- **A reusable workflow is tested here before a project uses it:** `self-test-ci-go.yml` calls `ci-go.yml` on the module in `.github/testdata/ci-go/` (the starting point of `go_setup` filled for a component `sample`), on pull requests that change the workflow, the self-test or the fixture.
- **Do NOT use one workflow per component with `on.push.paths`:** the native filter applies to the whole workflow, and a workflow that didn't trigger leaves the required check pending forever, blocking the PR. A job skipped by `if:` counts as success.
- Secrets are passed explicitly by name to reusable workflows (**do not use `secrets: inherit`**), making visible in the project what each one receives.
- **The deploy jobs live in the same `ci.yml`**, one per component and environment, after the component's job: `deploy-<component>-<environment>`, with `needs: [<component>]` and `if: github.event_name == 'push' && github.ref == 'refs/heads/<default branch>' && needs.<component>.result == 'success'`. So a deploy runs only on a push to the default branch, never on a pull request, and only for a component whose check ran and passed: a push that did not touch a component skips its check and therefore its deploy. The deploy jobs are not part of the job `ci`, so a pull request never waits for a deploy. Each declares its own `permissions: contents: read, id-token: write` (a called workflow cannot raise its caller's) and calls the reusable `deploy-cloud-run.yml` of the workflows repository, at the same commit as `ci-go.yml`. The triggers stay `pull_request` and `push`: no file the tooling writes has `pull_request_target` or `workflow_run`, whose tokens run with the default branch as their ref while other code is at hand. `github_ci-setup` writes them when it is given `deploy=dev deployComponents=<names> project=<project> region=<region>`, for exactly the components named. Each passes the component's folder, its service `<project>-<component>`, its image name and the region as inputs (the region written literally: it is in the public declaration), and the four identifiers as `secrets:` from the repository's secrets (`project-id: ${{ secrets.GCP_PROJECT_ID }}`, and likewise `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT` and `GCP_IMAGE_PATH`); no `vars.` is written. This version accepts exactly one environment (the repository's secrets the jobs read would clash with two). A version 1 file is pinned again at the head of `main` of the workflows repository when it becomes version 2, because its commit is older than the deploy workflow.
- **A deploy job exists for exactly the components whose service exists.** `project-plan` decides the list in one place: when it read the services, the components whose service is not missing; when it could not read them, the components of the local `ci.yml`'s version 2 marker that are still declared (a deploy job that exists is never dropped, and none is added before its service exists). An empty list is the version 1 file. `project-apply` writes the file with the same list. So when `project-apply` creates the services and proposes the files in the same run, that one proposal carries their deploy jobs (a new project whose login is prepared gets them in the first proposal of its code); a CI file proposed before the services exist (while the login is not prepared) is the version 1 file, and the deploy jobs come in the proposal of the run that creates the services; a component added to a deployed project comes in a proposal that keeps the other components' deploy jobs and has none for it, and the run after its merge creates its service and proposes its deploy job ([section 12](#12-skills-of-the-aleogr-orchestrator)). No run goes red for a service that does not exist.
- **`deploy-cloud-run.yml`**, the reusable deploy of one component: `on: workflow_call` only; inputs `working-directory` (the component's folder, which holds its `Dockerfile`; never `.`, absolute or outside the repository), `service`, `region` and `image-name`; the four identifiers `project-id`, `workload-identity-provider`, `service-account` and `image-path` arrive as required **secrets**, which the caller passes from its repository secrets (`project-id: ${{ secrets.GCP_PROJECT_ID }}`), never with `secrets: inherit`; the caller writes `region` literally. One job, 20 minutes at most, one deploy at a time per service (`concurrency: deploy-<service>`, never cancelled). Its steps: the first masks the identifiers and the project number (read from the provider's path) and validates the inputs, before anything else runs; then checkout, `google-github-actions/auth` (workload identity federation, no key), `docker/login-action` on `<region>-docker.pkg.dev`, `docker/setup-buildx-action`, `docker/build-push-action` (the image `<image path>/<component>:<commit SHA>`, no provenance or SBOM so that the digest is the image's own, no job summary, no build record, no annotations), `google-github-actions/setup-gcloud`, and one command, `gcloud run services update <service> --image=<image path>/<component>@sha256:<digest>`, with the digest the push returned (refused unless it is `sha256:` and 64 hexadecimal characters). **That is all it does to a service:** never `gcloud run deploy`, never `--iap`, never a create, never a change of who may reach it; a missing service is a failure. A service never runs "a tag": the CI identity can push a new image under an existing tag, so it is deployed by digest.
- **No workflow prints an identifier.** A project's repository may be public, and then so are its logs. GitHub prints a step's `env` in the log before the step runs, so a value passed as a plain input would be printed in clear by the very step that masks it; passed as a secret, it is masked by the runner from the job's start. Values reach the scripts only through `env`, never written into a script.
- **The four identifiers are repository secrets, not variables**: `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT` and `GCP_IMAGE_PATH`, set by `github_variables-set kind=secrets`. A project's repository may be public: GitHub masks a secret in every log and never gives one to a pull request from a fork, and neither is certain for a variable. A secret's value cannot be read back, so the plan compares their names only ([section 12](#12-skills-of-the-aleogr-orchestrator)). There is no `GCP_REGION`: the region is in the public declaration and is written in `ci.yml` itself.
- **The deploy workflow is checked here before a project uses it:** `self-test-deploy-cloud-run.yml` runs `.github/testdata/deploy-cloud-run/check.sh` on pull requests that change the workflow, the self-test or the check. The check parses the YAML (with the runner's system Python and PyYAML; a missing PyYAML fails, never skips) and proves the file's text: the only trigger, the inputs and secrets, the permissions, the eight steps in order, each action pinned by a 40-character SHA, the masking step first, the two scripts exactly as reviewed, one `gcloud` command in all, and none of the forbidden strings (another privileged trigger, a create, a change of access, `secrets: inherit`). It proves nothing about run time ([section 18](#18-open-items)).
- CI is the **single deploy path**, hosting-* included: no provider Git integration deploying on its own on every push (previews per PR, when wanted, are also made by CI). No skill builds an image or deploys one: the skills create a service with Google's sample image, and CI replaces it.
- CI reaches clouds without long-lived keys: cloud-* `ci-identity-setup` sets up OIDC federation. No key exists, anywhere. On GCP (`gcp_ci-identity-setup`) the identity of a project's CI is the service account `<project>-ci` of its own GCP project, reached only through the workload identity pool `github` and its provider `github`, whose condition accepts only tokens of the declared repository, checked by its name and by GitHub's numeric ids of the repository and of its owner (a repository deleted and recreated under the same name does not pass), on its default branch, **and only in a job that runs the reusable deploy workflow** (`assertion.job_workflow_ref.startsWith('<workflows repository>/.github/workflows/deploy-cloud-run.yml@')`): pull requests, forks, other branches, other repositories and another workflow file of the same repository and branch (a second workflow, or a job written in `ci.yml` itself) cannot use it. The clause stops at `@` because the form of the reference after it, for a workflow pinned by commit, is not documented. It does not stop someone who can change the default branch: they can edit the calling workflow, or point it at another commit of the workflows repository, and its jobs still pass; the protection of the default branch guards that ([section 18](#18-open-items)). The provider's attribute mapping has six keys, one for every field the condition tests (`google.subject`, `attribute.repository`, `attribute.ref`, `attribute.repository_id`, `attribute.repository_owner_id`, `attribute.job_workflow_ref`), always sent whole; a provider made before the clause existed differs and is updated in place. The account has no role on the project; each role is granted on the one resource it concerns ([section 6.4](#64-shared-platform--project-resources)): writer on the image repository, and, on each service, the role that replaces its image and the right to act as its account.
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
- **The login on a service** (on GCP): the service is deployed with no unauthenticated access and IAP on (`gcloud run deploy … --no-allow-unauthenticated --iap`). Two bindings on the service make it work: the project's IAP service agent is an invoker of the service (`roles/run.invoker`), and each person let in has `roles/iap.httpsResourceAccessor` on it. Someone not signed in gets Google's sign-in page; someone signed in but not on the list gets "You don't have access"; in both cases the request never reaches the service. Letting a person in is one command; nothing is clicked per service ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)).
- **A service is never reachable without the login, not even for a moment.** It is created in one command that already carries both flags, `gcloud run deploy <service> --image=<Google's sample> --no-allow-unauthenticated --iap …`, by `gcp_deploy-setup`. No skill and no workflow ever passes `--allow-unauthenticated`, `--no-iap` or `--no-invoker-iam-check`, or adds `allUsers` or `allAuthenticatedUsers` to anything. Before it makes anything, `gcp_deploy-setup` runs a security pass over every service of the project that already exists: a public member is removed from any role, a login that is off is turned on (`--iap`, alone), and the invoker check is turned back on; when a command of the pass fails, nothing else is made and the answer names each service still open or still without the login. A failed create is followed by a read of the service, because the command can fail after creating it; a service found that way gets the security pass at once.
- **Who gets in.** `gcp_deploy-setup` puts the account that runs it (the owner, in Cloud Shell) on the allowed list of each service, so the owner gets in with no further command. Anyone else is let in by `/aleogr:project-access person=<e-mail>` ([section 12](#12-skills-of-the-aleogr-orchestrator)), which grants `user:<e-mail>` the role `roles/iap.httpsResourceAccessor` on each service of the project, never on the GCP project. The member is always `user:`: never a group, a domain, a service account or everyone, and a group's address would let nobody in. An e-mail is an argument only: it is never written to a file, a label or a result block, and a result block says how many people a service lets in, never who. Nothing removes a person yet: the answer gives the one `gcloud` command that does, for the owner to run.
- **The login of the organization: one OAuth client for every service.** The organization is a standalone one, owned by a personal Google account, so for the login every account, the owner's included, is outside the organization. Google's managed OAuth client refuses such an account even when it is on the allowed list; a custom OAuth client lets it in. That client is set once, on the organization's IAP setting, and every service of every project of the organization inherits it with nothing configured on the service. It lives in the shared project ([section 6.8](#68-shared-platform-resources)):
  - a consent screen named `aleogr`, audience External, **left in testing and never published**: the login asks only for the basic sign-in scopes, for which Google needs no list of test users and shows no warning (by Google's help; a second Google account, on no list of test users, got in during the run of stage 4b-1). No logo is uploaded: a logo starts Google's verification;
  - one OAuth client named `iap`, of type web application, whose authorized redirect URI is `https://iap.googleapis.com/v1/oauth/clientIds/<client id>:handleRedirect`;
  - on the organization, the IAP setting that names that client (`accessSettings.oauthSettings`).

  **The client's secret is stored only by Google.** It never passes through a skill, a skill's output, a test fixture or the conversation: the owner copies it from the console and types it only at the prompt of the one command that sets it, in a terminal. How it is prepared: [section 6.8](#68-shared-platform-resources).
- **A component that must stay open is declared public** in `project.json` (e.g. an API that receives webhooks from a payment provider, an API called by a mobile app), and only that one has no login. Everything that calls a service without a logged-in person stops working behind the login.
- **Cost ceilings are always on**, with or without login ([section 6.5](#65-minimum-cost-contract-rule-in-the-dev-project-environment)); they are what protects the components declared public.
- In `prd` none of this applies: production is public by definition.
- **No single access point:** every hostname has its own DNS record pointing to its destination. The dns-* contract in `dev` and `hom` is `record-add`; there is no router and no route.

### 6.4 Shared platform × project resources

- **Each project has its own cloud environment per project environment** (on GCP, its own project: [section 1](#cloud-environments-gcp-project-ids)). Whatever costs nothing while idle belongs to the project: services that scale to zero, secrets, storage, image registry.
- **The ground of a project's environment** (on GCP, built for `dev`): created by `project-apply` when the declaration has the environment ([section 11.6](#116-cloud-and-environments)), all inside the project's own GCP project, none with a cost while idle:
  - the GCP project itself, `aleogr-dev-<project>-<random>`, in the folder of its environment (inside `tst` for a project that tests the tooling, [section 6.7](#67-gcp-organization-folders-and-billing));
  - its APIs: the list `project.services` of `defaults.json` (in `dev` now: Resource Manager, Artifact Registry, IAM, IAM Credentials, Security Token Service, Cloud Run and IAP), and, only when a component uses the database, the Cloud SQL Admin API (`sqladmin.googleapis.com`), which the connector of a service calls as the service's own account, in its own GCP project;
  - **the image repository, the project's own:** one per project and environment, never a shared registry, which keeps it free while small and keeps a project's removal simple. Id `<project>`, format Docker, in `cloud.region` ([section 1](#project-and-shared-platform-resources));
  - **its cleanup policy, the ceiling of what storage can cost:** two rules, keep the 5 most recent versions of each image (`project.registry.keep` of `defaults.json`) and delete every other version. A version that matches both is kept. The policy is never in dry-run (a policy in dry-run deletes nothing, so it counts as different), and it is replaced whole when it differs: one skill owns both rules;
  - **the CI identity** ([section 4](#4-cicd)): writer on that one image repository, and, once the services exist, on each service `roles/run.developer` (which may deploy a new revision but not change who may call the service) and on each service's own account `roles/iam.serviceAccountUser` (so that a new revision may run as it). So in `dev` it can push images and update its services, and nothing else: no role on the project, none that creates a service or changes its access. The deploy workflow only replaces a service's image; the role itself would also let a job change the service's other settings, never its access, which the next plan shows as `differs` and the next run repairs ([section 18](#18-open-items)). Members that something else added to the account's impersonation are counted and reported, never removed. A pool that holds a provider other than `github`, or a pool or provider that is disabled or deleted, is refused and fixed by hand;
  - **with components, one Cloud Run service per component** (`gcp_deploy-setup`, created by `project-apply` once the login of the organization is prepared, [section 6.3](#63-protection-and-single-access-point)): the service `<project>-<component>` in `cloud.region`, running as its own service account of the same id, which has no role; labels `aleogr-project`, `aleogr-environment` and `aleogr-component`; Google's sample image `us-docker.pkg.dev/cloudrun/container/hello:latest` until CI deploys the component's own (`project.deploy.placeholderImage`); minimum 0 and maximum 2 instances (`project.deploy.maxInstances`), set on the service; 1 CPU and 512 MiB (`project.deploy.cpu`, `project.deploy.memory`); billing by request (`--cpu-throttling`); no unauthenticated access and the login on; the login's service agent allowed to call it (`roles/run.invoker`, bound by `--iap` itself). The service skills accept only 1 to 10 instances, 1 or 2 CPUs and `512Mi`, `1Gi` or `2Gi` of memory. A service that exists is as declared when its account, its scaling, its size, its labels, the absence of any public member, a login that lets in neither `allUsers` nor `allAuthenticatedUsers` (otherwise the service is open: the difference `open`), the login, the agent's binding and the CI's two bindings all hold; one that differs is repaired with only the settings that differ (an open or public member is removed first, by the security pass), and its image is never changed. Which people are on its allowed list is not declared and never compared. A component that uses the database also has three settings (below); a setting the tooling was not given is never compared, changed or reported;
  - **the repository's four CI secrets** (`github_variables-set kind=secrets`): `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT` and `GCP_IMAGE_PATH`, read by the deploy jobs. They are identifiers, kept as secrets of the repository because GitHub masks a secret in every log and never gives one to a pull request from a fork ([section 4](#4-cicd)); there is no `GCP_REGION`, since the region is written in `ci.yml`. A missing secret is set; one that exists is left alone (its value cannot be read back), except that all four are set again in a run that created or changed the GCP project, the image repository or the CI identity. None is ever deleted.
- **Cost of the ground:** a GCP project, its APIs, the identities and an empty repository cost nothing; Artifact Registry is free up to 0.5 GB and then about US$ 0.10 per GB a month, and the cleanup policy keeps a project's images far below that. Nothing of it asks for a confirmation of cost.
- **Cost of the services:** no charge while idle. With a minimum of 0 instances and billing by request, Cloud Run charges only while a service handles requests; idle instances that are not minimum instances are not charged, and requests the login refuses never reach the service. At the time of reading (Cloud Run's pricing page, 2026-11-20), the monthly free tier of request-based billing was 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests, counted per billing account across its projects, at the prices of `us-central1`: a statement of that day, not a promise. The login itself has no charge (IAP's pricing page, the same day), and with IAP on the service there is no load balancer, the piece that would have a fixed cost. The maximum of 2 instances is the ceiling of what a burst can cost ([section 6.5](#65-minimum-cost-contract-rule-in-the-dev-project-environment)). Nothing of it asks for a confirmation of cost.
- **Shared platform:** only what has a FIXED cost is shared, created ONCE ([section 6.8](#68-shared-platform-resources)). Each cloud provider (GCP, AWS, Azure) has its own version of the shared platform, with the same logic.
- **Project resources in the platform:** created INSIDE the shared resource. Built: a project's database on the shared instance (below).
- **The database of a project** (built for `dev`): a component declared with `"database": true` ([section 11.5](#115-components)) reaches its own database on the shared instance as its own service account, with no password anywhere. One database per project and environment, shared by the project's components that use it; one database user per such component. `project-apply` makes, after the services and before the CI secrets:
  - the database `<project>_<environment>` (every `-` of the project's name written `_`; `pilot_dev`), on the instance `aleogr-shared`, with the instance's defaults (`gcp-cloud-sql_database-create`);
  - for each such component, its database user, of the IAM service-account type, named as Cloud SQL names that account on PostgreSQL: its address without `.gserviceaccount.com` (`<project>-<component>@<project id>.iam`), at most 63 characters (a longer one is `user name too long` / `fix by hand` in the plan, which says to choose a shorter component name). It is made with no password and no database role; then the account's two connection roles, `roles/cloudsql.client` (connect) and `roles/cloudsql.instanceUser` (log in), on the shared project, without a condition (`--condition=None`). The user comes first and the roles after, both only while the instance runs: on an instance that is not running nothing is made and nothing is granted, and the skill ends `pending` (`gcp-cloud-sql_access-grant`): so roles that are right always mean that the user exists. Cloud SQL grants these roles on a project, not on an instance; a role held under any condition counts as held, so narrowing a binding later never makes it missing ([section 18](#18-open-items));
  - the Cloud SQL Admin API in the project's own GCP project (above);
  - last, three settings of the component's Cloud Run service, `DB_INSTANCE` (the instance's connection name, `<shared project id>:<region>:aleogr-shared`), `DB_NAME` and `DB_USER`, set by `gcp_deploy-setup env=…` in their own `gcloud run services update --update-env-vars`, never with the image: the shared project's id reaches a service only as one of its settings, never a versioned file. Being last, they mark that the rest was made, so a plan is useful while the instance is stopped: it reads the settings and the roles, and a row whose settings and roles are right is `as declared`, with a line saying that the database itself was not read; the database and the users are read only while the instance runs;
  - the component's code: the check `db.go`, the route `GET /db` and the two modules, written by `go_setup database=yes` ([section 11.5](#115-components)) and proposed by pull request like any code; `project-apply` writes them before it starts the instance, so a failure there costs nothing.

  No secret exists: no password is generated, stored or read, no connection string carries a credential, and nothing goes to Secret Manager, to an Actions secret or to a skill's output.
- **When the instance is stopped and something must be made in it**, `project-apply confirm=yes` starts it (`gcp-cloud-sql_instance-start`), waits until it accepts calls (the one wait longer than the usual five minutes: 30 tries of 30 seconds, about 15 minutes, as a start was measured at 11.5 minutes), makes what is missing, and leaves it running until the night stop. It starts it only under `confirm=yes` itself, only when a database, a user or roles are missing (missing roles mean the user is not known and must be made); settings alone are written with the instance stopped. Around the start:
  - **The code first.** The run writes the check's code (`go_setup database=yes`, when the plan lists it) before anything that costs: a `go_setup` that fails stops the run before the start, with that skill's own sentence.
  - **The night stop is read before the start.** Right before `gcp-cloud-sql_instance-start`, the run reads the switch with `gcp-cloud-sql_instance-switch-setup … mode=plan` (the read the platform's plan makes of the stop jobs and their identity, with the arguments of `defaults.json`). Unless it says the switch is ready, the instance is not started: the run stops with the item `database` (`how`: `/aleogr:platform-plan`, then apply again) and one sentence saying that the night stop could not be confirmed, so the instance was not started. "Until the night stop" is therefore never said of a start whose night stop was not read.
  - **A failed start is read back.** When the start command fails, `gcp-cloud-sql_instance-start` reads the instance once and decides by its activation policy: the start went through after all (the run goes on, as after a start), the instance is still stopped and costs nothing, or the read cannot tell, and the answer says it may be charged by the hour and names the read that shows it.
  - **The wait tolerates a failed read.** Each try of the wait is a full `gcp-cloud-sql_database-describe`; a try that ends `failed` counts as a try, like one that has not read the databases yet. Only the limit of 30 tries stops the run, with the instance started and the start's sentence.
  - **A run that finds the instance starting waits.** When the plan shows the instance `starting` (started by someone else, or by an earlier run whose session dropped) and the row `database` has something to make, `project-apply confirm=yes` enters the same wait, with no start and no start's sentence, and one line saying that it waited for an instance that was already starting, then goes on. An instance that is `creating`, or in a state the skills do not know, still stops the run.

  **The cost is said before every start, and again after it**, as the creation of a GCP project is ([section 12](#12-skills-of-the-aleogr-orchestrator)). The notices, each word for word:
  - at the proposal: a run after a merge may update the folder, enable the API and start the instance under one `confirm=yes` before any plan could show the row, so the proposal that adds `"database": true` to a component says, in the pull request's body and in the run's answer, `Applying this after the merge starts the shared database instance when it is stopped: it then runs, charged by the hour, until the night stop.`;
  - in a plan that read the instance stopped while something must be made in it (`start` true), the cost line `project-apply starts the shared instance (about twelve minutes); it then runs, charged by the hour, until the night stop.`;
  - in a plan whose row `database` did not read the instance (one of the `follows …` states: a row before it has an action, or the service of a database component is missing, and the run makes those first, then plans again and may start it in the same run), the conditional line `If parts of the database are missing and the shared instance is stopped, project-apply starts it: it then runs, charged by the hour, until the night stop.` So every plan, and every `project-apply` without `confirm=yes`, has said it before a confirmed run can start the instance for a need that only shows up inside the run;
  - after the start, in every ending of the run that started it: `This run started the shared database instance: it runs, charged by the hour, until the night stop. To stop it sooner: /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop, or the workflow self-shared-database of aleogr/aleogr (action stop).`

  They are announcements, not a second confirmation: the merge and the run's `confirm=yes` are the consent. The plan never starts the instance, and nothing in the tooling stops it: the night stop or the owner does ([section 6.8](#68-shared-platform-resources)).
- **Cost of a project's database:** no new fixed cost. A database, a user, the roles, the settings and the connector cost nothing, and the instance already costs its disk and its address while stopped ([section 6.8](#68-shared-platform-resources)). The one cost a run can add is the instance's running hours, from a start made by the run until the night stop or an earlier stop: about R$ 0.06 an hour for `db-f1-micro`, as read on the bill of the previous lab ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)), a statement of what was read, not a promise; under R$ 1.50 for a whole day.
- The family contract gains the `shared` or `dedicated` mode; in the `dev` project environment the default is `shared`. E.g. db-* in `dev` creates database + user on the single instance; in production, its own instance.
- Isolation within shared resources by name and labels ([section 1](#1-names)); a project's `project-plan` sees only what is its own; `*-remove` never touches what belongs to another.

### 6.5 Minimum cost (contract rule in the `dev` project environment)

- Scale to zero whenever possible.
- Smallest tier/size available.
- Nothing with fixed cost per project (load balancer, static IP, NAT, dedicated instances).
- **Ceilings:** every service has a maximum number of instances (one or two), and every paid service the project uses (LLM, SMS, e-mail...) gets its own spending limit, so that the worst case has a known cost.
- State the cost and require `confirm=yes` before creating anything with a fixed cost.
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
- **`gcp_environment-create` searches twice before it creates a project:** by its labels, then by its parent (the organization for the shared project, the environment's folder otherwise) with the same labels. The search by labels is eventually consistent: a project created a minute ago may not appear in it, and a project id is permanent, so a second project created by a run that did not see the first would stay. Only when both searches find nothing is a project created; one found by the parent is used as found (its billing checked and, when missing, linked). A create command that fails is followed by a read of the project, because the command can fail after creating it.
- **Preferred region: `us-central1`**, for every project and for the shared platform (same region as the shared database; Cloud Run domain mappings exist there). It is the default in `defaults.json` ([section 6.6](#66-personal-defaults)).
- **The billing account belongs to the organization**, with a budget alert on the whole account ([section 6.5](#65-minimum-cost-contract-rule-in-the-dev-project-environment)).
- **Few organization policies, chosen one by one.** The organization already comes with a set enforced by default, which stays as it is ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)); it includes the one that matters most here, forbidding the creation of service account keys, because CI reaches the cloud without long-lived keys ([section 4](#4-cicd)). Consequence for every project: each service runs as its own service account with explicit roles, since default service accounts get none.
- Not used: deeper folder hierarchies than the environment folders and `tst`, more than one organization ([section 16](#16-discarded-decisions)), separate administrative roles per person.
- The identifiers of the organization, the folders and the billing account are not versioned (the repository is public); they follow [section 7](#7-where-data-lives).

### 6.8 Shared platform resources

- **One shared cloud environment for everything that is not production**, with a generic name so that it can hold any shared resource that appears: on GCP, the project `aleogr-shared-<random>`, display name `shared`, labels `aleogr-project=shared` and `aleogr-platform=shared` (no environment in the id and no `aleogr-environment` label). It serves `dev`, `hom` and the tests, so on GCP it is created directly under the organization, not in the folder of an environment ([section 6.7](#67-gcp-organization-folders-and-billing)). `prd` never uses it. The skills address it as `project=shared platform=shared`, never with an environment (`gcp_environment-describe`, `gcp_environment-create`, `gcp_services-enable`; the orchestrator's `platform-plan` and `platform-apply` pass it so).
- `shared` is a **RESERVED** project name ([section 11.1](#111-json-schema)).
- Accepted trade: `dev` and `hom` of every project share performance and availability, and the separation between them protects against accidents only ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). A project that needs an isolated `hom` uses the `dedicated` mode.
- **Shared database:** one Cloud SQL PostgreSQL instance, `aleogr-shared`, the smallest tier, with one database per project and environment, the environment always in the name as in the addresses (`<project>_dev`, `<project>_hom`). It has a public address with no authorized networks, so nothing connects to it directly: access goes through the Cloud SQL connector, authenticated by IAM. The disk is 10 GiB with automatic growth off (disks never shrink, and `gcloud` has no flag for a growth limit); a full disk is a visible failure and I grow it by hand. Deletion protection is on. Inside it, each project has one database per environment, and each of its components that uses the database one IAM database user, with no password; on the shared project, those components' accounts hold the two connection roles ([section 6.4](#64-shared-platform--project-resources)). A project adds nothing else to the shared platform.
- **The instance is OFF by default** (it does not scale to zero, and it is the only fixed cost of the shared platform). Stopped, it still costs its disk and its idle public address: about R$ 50 per month while stopped ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). Nothing with that cost is created without my seeing the amount and saying yes:
  - **started on demand**, when I am going to work: by the skill `gcp-cloud-sql_instance-start` (where `gcloud` is authenticated) or by a manually triggered workflow of `aleogr/aleogr` (from anywhere, including the phone); and by `project-apply confirm=yes` when a project's database needs something made in it ([section 6.4](#64-shared-platform--project-resources));
  - **stopped by a scheduler inside GCP**, so that stopping never depends on me remembering: two Cloud Scheduler jobs in the shared project (`aleogr-shared-stop-weeknight` and `aleogr-shared-stop-weekend`) call the Cloud SQL Admin API, with no function in between (Cloud Scheduler cannot send the API's HTTP `PATCH`, so each job sends a `POST` with the header `X-HTTP-Method-Override: PATCH`), in `America/Sao_Paulo` time, at 22:30 from Sunday to Thursday and at 04:00 on Saturday and Sunday (Friday and Saturday nights have no fixed end). It can also be stopped by hand, by the skill `gcp-cloud-sql_instance-stop` or by the same manually triggered workflow (`self-shared-database.yml`, which offers `start`, `stop` and `status`);
  - starting takes minutes ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)): the skills that need the instance read its state and say so (a stopped instance is a normal state of the plan, never a failure), and a component's check answers `database: not reachable (the shared instance may be stopped)` instead of failing with a connection error;
  - the backup window starts at 20:00 (`America/Sao_Paulo`), an hour when the instance is usually running; a window that falls while it is stopped produces no backup and no error.
- **What the platform is made of** (on GCP): the shared project, the database instance, the scheduler that stops it, the identity that starts and stops it, the budget alert (`aleogr`, on the whole billing account) and the login of the organization ([section 6.3](#63-protection-and-single-access-point)).
- **The login of the organization is a row of the platform's plan**, `login`, listed last. `platform-plan` reads it, once the shared project exists, with `gcp_login-describe projectId=<shared project id>` (`gcloud iap settings get --organization=<id>`, counted against the shared project with `--billing-project`; the answer shows the client's id and a hash of the secret, never the secret, and the skill repeats neither):
  - `prepared` / `none` when the organization's setting names a client;
  - `not prepared` / `prepare` otherwise, also when the read is refused because the role that reads the setting is not granted yet, or because the IAP API is off in the shared project (both are normal on an organization never prepared);
  - `not checked` / `prepare` when the read failed for any other reason (an unknown login is never `none`: the apply reads it again);
  - `not checked, will be checked after the project exists` / `prepare` while the shared project is missing.
- **It is prepared once, and the tooling does all of it that Google lets a command do.** Google has no command that creates a consent screen or an OAuth client, so those are a few clicks in the console; everything else is the tooling's. `platform-apply`, last, after every other step, invokes `gcp_login-setup projectId=<shared project id> mode=apply` when the row says `prepare`. That skill reads the setting first and changes nothing when it already names a client; otherwise it grants the account that runs it `roles/iap.settingsAdmin` on the organization (the organization's administrator does not have it by default, and it is what reads and changes the setting), enables `iap.googleapis.com` in the shared project, reads again (waiting by itself while the new role has not reached the read, [section 10.4](#104-behavior-of-every-skill)), and, when the login is known not to be prepared, prints the short list of what is left: the two console pages, as links that open in the shared project, with the value of each field (the names `aleogr` and `iap`, audience External, the redirect address to build from the client's id, no logo, nothing published), and **one command to paste in a terminal**. That command asks for the client's id and, without showing it, the secret; writes them to a temporary file; sets them on the organization (`gcloud iap settings set <file> --organization=<id>`); and removes the file however it ends. The skill never runs it, never fills in a value other than the shared project's id, and never asks for the id or the secret; a client id or a secret pasted into the conversation is not used, repeated or stored. Both changes are free, and the run is not stopped by what is left: it ends with the list in a `Login` section and the item `login` (`created` or `updated` when something was changed, `pending` when only the clicks were left). After the clicks and the command, `platform-plan` reads the setting and the row says `prepared`. The login skills, when they answer the owner, name `platform-plan` as the next command, never `platform-apply`: the plan states what would be made and its cost first. The same steps, for reference: [`cloud-shell.md`](cloud-shell.md).
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
- **The identifiers CI needs** (a project's GCP project id, the name of its federation provider and its CI account's e-mail) are found by name and label and handed out by the skills as `ciVariables`; with the image path, they reach the project's repository as its four Actions secrets, written by `github_variables-set kind=secrets` as soon as the CI identity and the image repository are as declared, before the pull request that adds the deploy jobs that read them ([section 6.4](#64-shared-platform--project-resources)). No workflow prints them: GitHub masks a secret in every log ([section 4](#4-cicd)). GitHub's numeric ids of a repository and of its owner, which the CI identity's condition names, are public on GitHub, read from it at each run and never versioned.
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
| registry-* | gcp-artifact-registry, docker-hub, ghcr, aws-ecr | exclusive | project |
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

**The premise: using the tooling is simple, fluid, automated and easy.** It is a rule of every skill, and these rules follow from it:

- **A run goes on by itself** as far as it safely can. Once the owner has merged a change, one `project-apply confirm=yes` makes everything the merged declaration asks for, in the same run that updates the folder ([section 12](#12-skills-of-the-aleogr-orchestrator)).
- **A stop is kept only where the owner is needed:** before what cannot be undone, what exposes something or what has a cost (one confirmation, given in the command, covers the whole run: `confirm=yes`, or `confirmVisibility=<value>` for a change of visibility; a fixed cost is stated before it is confirmed), and where a secret is the owner's to type (in a terminal, never in the conversation, [section 6.3](#63-protection-and-single-access-point)). An irreversible step that the run's confirmation already covers is **announced**, not asked again: before the GCP project of an environment is created, the proposal that adds it says so in its pull request and in its answer, and the run that creates it says so before it is made. The announcement is not a consent gate: the owner's consent is the merge and the `confirm=yes` of the run.
- **Waits are automatic and bounded.** Where a refusal is known to be cured by time (an API just enabled, an account just created, a role just granted), the skill waits 30 seconds and tries again, while that same refusal comes back, at most 10 tries in all (about 5 minutes), and only then stops, with its item. The one longer wait is the shared instance's start: 30 tries, about 15 minutes, in which a read that fails counts as a try instead of ending the wait, and which a run also enters when it finds the instance already starting ([section 6.4](#64-shared-platform--project-resources)). The wait is the command `sleep 30`, run in the background (Claude Code refuses a `sleep` in the foreground); the run goes on in the same turn when it ends. A wait ends at the first try that is not refused that way: it is never a fixed pause, and never left to the owner.
- **One command per thing left to do.** A stop says what was done, what is left and, for each thing left, the one command that goes on. It never asks the owner to check what a command can check, and a missing argument fails with one sentence; no skill asks a question and waits for the answer.
- **Answers are short:** one line per skill that made something, with its status; the table of the last plan; the sentences the skill prescribes, once each; what is left; the addresses when there are any; and exactly one result block, the skill's own. The lines and blocks of the skills it invoked are its input, never part of the answer.

And, for every skill:

- Checks before creating (idempotent).
- Shows each command before running it.
- Follows the MINIMUM COST rule in `dev` ([section 6.5](#65-minimum-cost-contract-rule-in-the-dev-project-environment)).
- Ends with a verification (e.g. `gh repo view`, `gcloud ... describe`, DNS lookup).
- What cannot be automated becomes a checklist.
- platform-* skills start by checking the environment (OS, SDK, connected device).

### 10.5 Tools and dependencies between families

- CLI first (gh, glab, gcloud, aws, az); MCP when there is no good CLI or the official MCP is better. The MCP goes in the family plugin's `.mcp.json`.
- cloud-* provides the base (account/project, identities, permissions, APIs, deploy); service families assume the base exists. The orchestrator guarantees the order.
- secrets-* is unique per project, usually on the primary cloud; credentials for other clouds also live there. In `dev` and `hom`, project secrets live in the shared platform's vault, prefixed with the project.

### 10.6 "What/how" split

- **stack-\*** provides the language version, build/test/lint commands, cache and devcontainer Features (the official one and, if it exists, my preferences layer), and the component's CI parameters (its reusable workflow and inputs). Its `setup` also writes a minimal starting point, once ([section 11.5](#115-components)).
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
- `environments` field: its target shape, with each environment's host and tenants, is in [section 6.1](#61-addresses-of-a-projects-environments); version 1 accepts only what is built ([section 11.6](#116-cloud-and-environments)).
- Plugin name derived from family + provider.
- Each family plugin may publish a sub-schema for its options.
- Optional `notes` field (JSON does not accept comments).
- A repository's visibility is declared, `public` or `private`, with the default `private`: making a repository public later is easy, the opposite does not undo what was seen.
- Nothing becomes public without its own confirmation, whether at creation or by a change (`confirmVisibility=public`); a change to private needs `confirmVisibility=private`. A skill does not wait for the answer: without the confirmation it changes nothing of the visibility, ends with the question and the exact command that confirms it.
- In a free organization, a private repository has no branch protection (the plan forbids rulesets there): `branch-protect` reports `pending`, and `main` is held by the working rule (Claude Code opens the pull request, the owner merges), not by GitHub.
- **Version 1** of the declaration holds only what has been built: `version` (`1`), `name`, `repo` and the optional `components`, `cloud`, `environments` and `notes`. `repo` has `provider` (`github`, the only one implemented), `owner`, `name`, `visibility`, `description`, `topics` (extra topics only) and `settings`, which is complete in the file (the seven keys `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects`), so the file says everything about the repository without the defaults. The schema is strict (no unknown key at any level); the skills check a declaration by the same rules written in their own text, so no validator is needed where they run. The declaration grows by stage: each key enters with the stage that builds it (the cloud and the environment `dev` with stage 4a; a component's database with stage 4c; DNS later), and the schema refuses what is not built yet, so that nothing is declared that the tooling would ignore ([section 17](#17-implementation-strategy)). Examples: `examples/repo-only.json`, `examples/with-components.json`, `examples/with-environment.json`, `examples/with-database.json`.
- **`components`** is a list, possibly empty or absent (both mean none), of objects with `name`, `stack`, `path` and `version`, and an optional `database` (a boolean, [section 11.5](#115-components)); a file without it stays valid, so adding components needed no new version. `name` has 1 to 20 characters of `a-z`, `0-9` and `-` and starts with a letter; it is not `changes`, `ci`, `true`, `false`, `null`, `yes`, `no`, `on` or `off`, and does not start with `deploy-`, the prefix of the CI file's deploy jobs ([section 4](#4-cicd)). `stack` is `go`, the only one implemented. `path` is the component's folder, relative to the repository root, default the name: parts separated by `/`, each of `a-z`, `0-9`, `-`, `_` and `.` only, never `.` or `..`, never starting with `-` or `.` and never ending with `.`, so a component's folder is never `.aleogr`, `.github` or under them. `version` is the language version, `major.minor`, default `stacks.<stack>.version` of `defaults.json`; for `go` it is `1.22` or later, compared as numbers (the starting point's routes need it). Each name and each path is unique, and **a component's folder is never inside another's** (one module per component folder). The file lists the components sorted by name, one per line.
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
- **After the birth, a change is proposed by pull request and applied after the merge.** A change goes: edit the declaration (`project-declare`); `project-apply` proposes it as a pull request; the owner merges it on GitHub; `project-apply` updates the folder and applies it ([section 12](#12-skills-of-the-aleogr-orchestrator)). The tooling never merges, closes or deletes a pull request or a branch.
- **Only the merged declaration is applied.** This concerns the provider: the settings, the visibility and the protection follow the declaration on the default branch, never a local one. While the declaration is changed in the folder, proposed in an open pull request, or newer in the repository than in the folder (compared as JSON values, not byte by byte), `project-plan` compares nothing else (`not checked until the change is merged`). Files the tooling generates in the folder are not a change to the provider: they follow the local declaration ([section 11.5](#115-components)).
- **A tooling pull request.** It is one whose branch is in the repository itself and named `aleogr/change-…`; a pull request from a fork is never taken for one. It is opened from a new branch `aleogr/change-<6 random characters of a-z0-9>`, never by a commit on the default branch, and carries only the files the tooling names (never a folder). Its commit has the checkout's identity (above), set again before every commit. **A repository has at most one open tooling pull request:** while one is open, the plan shows `proposed in pull request #N` / `merge it`, whatever the folder holds, and nothing else is proposed.
- **After a proposal the folder shows the merged state again.** The folder is back on the default branch; the proposed declaration lives in the pull request and in the local branch, which is kept. To drop a proposal the owner closes the pull request; to make it again, the change is declared again.
- **A folder that needs attention** (not a checkout of the repository, another `origin`, on another branch, with commits the repository does not have, or with a declaration that differs where git sees no change) is never changed by the tooling: the plan shows `this folder needs attention` / `fix the folder`, and the owner fixes it by hand.
- **Adoption.** A repository with any other history and no declaration is never pushed to directly: the plan shows `not in the repository` / `propose`, the declaration enters by a tooling pull request, and from its merge the repository is applied like any other.

### 11.5 Components

- A component is a folder of the project's repository with one stack ([section 11.1](#111-json-schema)). It is declared with `project-declare component=<name> stack=<stack>` (and `path=`, `version=` when they are not the defaults), one per call. A component never changes folder or stack (that is another component); only its `version` changes. Removing a component is not built ([section 18](#18-open-items)).
- **The starting point is generated once and never overwritten.** The stack's `setup` (`aleogr-stack-go:go_setup` for Go) writes a minimal program in the component's folder from files shipped with the plugin, only when the folder has none: for Go, exactly `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, written only when `<path>/go.mod` is missing. A folder that already has a `go.mod` is left as it is (`unchanged`); a folder with Go files and no `go.mod` (code started by hand) is left as it is too, and the plan shows `needs attention` until the owner adds a `go.mod` or empties the folder. Whatever the owner writes after that is the component's code; the tooling never changes it.
- **The Go starting point:** the module `github.com/<owner>/<repository>/<path>`, one module per component folder (no `go.work`), the `go` line the declared version. `main.go` is an HTTP server on the port in `PORT` (default `8080`): `GET /` answers `<name>: ok` and `GET /healthz` answers `ok`, both plain text. `main_test.go` tests each handler with `net/http/httptest`, with no network. Standard library only, so there is no `go.sum` (until the database check adds its modules, below). Its routes need Go 1.22 or later, so `go_setup` refuses an earlier version. Without the database check `go_setup` needs no Go toolchain: CI is where the code is compiled and tested. It writes with Claude Code's file tools and runs one command, a read-only listing of the folder.
- **With environments, each component also gets its `Dockerfile`, written once and never overwritten.** `go_setup dockerfile=yes` writes `<path>/Dockerfile` when it is missing, also for a component whose module already exists (its other files are not touched); a `Dockerfile` that is there is never read and never changed: it is the owner's. It has two stages: the binary built with `golang:<the component's version>` (`CGO_ENABLED=0`, `-trimpath`; `COPY go.mod go.sum* ./` so that a module with no dependency, which has no `go.sum`, builds), then copied onto `gcr.io/distroless/static-debian13:nonroot`, run as `nonroot:nonroot`, with the binary as the entrypoint. The program listens on `PORT`, which Cloud Run sets. Its first line says it is generated once and is the owner's to change. The base images are named by tag, not pinned by digest ([section 16](#16-discarded-decisions)). The plan's `components` row is `to generate` while a component's `Dockerfile` is missing, and the proposal names it with the component's other files.
- **A component that uses the database is declared with one key**, `"database": true` (`project-declare component=<name> database=yes`; `database=no` removes the key; absent equals `false`, and `false` is not written). It needs `cloud` and `environments` (a database lives in an environment), and the component's `version` is `stacks.<stack>.database.minVersion` of `defaults.json` or later (`1.26`: the pinned connector needs Go 1.26). "The declaration's rules", identical in `project-declare` and `project-plan`, check both; the schema holds the first and states the second in prose. The key is additive: no new version of the declaration. What it makes is in [section 6.4](#64-shared-platform--project-resources).
- **The database check is written by `go_setup database=yes`** (with `modules=` and `minVersion=` from `stacks.go.database` of `defaults.json`: `cloud.google.com/go/cloudsqlconn@v1.27.1` and `github.com/jackc/pgx/v5@v5.13.0`, minimum `1.26`), by the same rule as the starting point: nothing someone changed is overwritten.
  - `<path>/db.go` and `<path>/db_test.go` are written only when missing, from templates the plugin ships.
  - The route `GET /db` needs a line in `main.go` (the server builds its own router, so a new file cannot add a route by itself). A new component gets the variant of `main.go` that has it. An existing component's `main.go` is replaced by that variant only when it is, byte for byte (`cmp`), the plugin's own `main.go` with the component's name filled in; anything else is someone's code and is left as it is: the result carries the item `route`, whose `how` is the one line to add, and the plan shows it as a line under the table (until it is added, the tests of `db_test.go` fail).
  - The two modules are added only when `go.mod` lacks them and the component's code uses them: one `go get` of the pinned versions, then `go mod tidy`, which also write `go.sum`. After them the `go` line must be the declared one, or the same followed by `.0` (the Go command writes `go 1.26` as `go 1.26.0` when a module it adds declares `go 1.26.0`), and the `toolchain` line as it was; otherwise `go.mod` and `go.sum` are put back from copies taken before (`cp -p`) and the run fails with one sentence. This is the one part of `go_setup` that needs Go where it runs (Cloud Shell has it), and the Go command may download the toolchain the module declares. The plan runs no `go` command: when the modules are to be added it checks Go with `tools-check command=go`, and without Go the row `components` is `needs Go on this machine` / `fix by hand`, which stops `project-apply` before anything is made or started.
  - **What the check answers**, behind the login like every route: `DB_INSTANCE`, `DB_NAME` or `DB_USER` empty → `503`, `database: not configured`; otherwise one connection through Google's Cloud SQL connector for Go with automatic IAM authentication as the service's own account (lazy refresh, since Cloud Run throttles the CPU outside a request; the connector's built-in metrics off, whose export would need a role the service lacks) and `pgx`, one `SELECT 1`, all under one 5-second deadline, the connection and the dialer closed → `200`, `database: ok`; anything else → `503`, `database: not reachable (the shared instance may be stopped)`, the cause written to the service's log only, never to the page. No password, no connection string with a credential, no pool kept between requests.
  - The check reaches the repository like any code: with the declaration that adds the key, in one pull request (generation follows the local declaration, below), whose title is `Add the database check of <names>`; the cloud is made by the run after its merge.
- **Changing a component's `version` regenerates `ci.yml` only.** The marker of `ci.yml` changes, so the plan's `ci` row is `differs` / `generate` and the new `go-version` is proposed; the component's `go.mod` keeps its `go` line, because `go_setup` never rewrites a file (the folder has a `go.mod`, so it is `unchanged`). That line is the owner's to change, as the rest of the component's code.
- **Generation follows the local declaration; application follows the merged one.** Writing the starting points and `ci.yml` in the folder and proposing them changes nothing on the provider, so the plan computes the rows `components` and `ci` from the declaration in the folder, even while it is `changed here`. Settings, visibility and protection still follow only the merged declaration ([section 11.4](#114-the-declaration-in-its-repository)).
- **Generated files reach the repository with the declaration, in one pull request.** The proposal names files only, never a folder: the declaration, `.github/workflows/ci.yml` and the three files of each component (four with environments, its `Dockerfile` last), and, for a component that uses the database, `<path>/go.sum`, `<path>/db.go` and `<path>/db_test.go`, of which it commits those that changed. The project's CI runs on that pull request ([section 4](#4-cicd)).

### 11.6 Cloud and environments

- **`cloud`** says where the project's environments run: `{ "provider": "gcp", "region": "<region>" }`, with an optional `"root": "tst"`. `provider` is `gcp`, the only cloud built; `region` is a GCP region name (`^[a-z]+-[a-z]+[0-9]+$`, such as `us-central1`); `root`, whose only value is `tst`, marks a project that tests the tooling, whose GCP projects are created inside the folder `tst` ([section 6.7](#67-gcp-organization-folders-and-billing)). A real project has no `root`. `cloud` without `environments` is valid and asks for nothing in the cloud.
- **`environments`** is an object with at least one key; its only allowed key is `dev`, whose value is an empty object: `{ "dev": {} }`. `hom`, `prd` and the keys inside an environment (its host and tenants, [section 6.1](#61-addresses-of-a-projects-environments)) come with the stages that build them. **A declaration with `environments` has `cloud`, and a `name` of at least three characters** (the CI identity's service account id is `<name>-ci`, and a service account id has 6 to 30 characters). **With `environments`, each component runs as a service named `<name>-<component>`**, which is also its account's id: no component's name ends with `-`, and `<name>-<component>` has 6 to 30 characters (`project-declare` refuses a declaration that breaks it; "The declaration's rules" are the same text in `project-declare` and `project-plan`).
- Both are optional and come after `components` and before `notes`, each on one line in the canonical file. Example: `examples/with-environment.json`.
- `project-declare environment=dev` adds the environment and, when the declaration has no `cloud`, writes it with the provider and region of `defaults.json` (an existing `cloud` is kept). `cloudRoot=tst` sets the root, with `environment=dev` in the same call or on a declaration that has `cloud`. Removing an environment, the cloud or the root, and changing the region, are not done by `project-declare`.
- **The declaration reaches the cloud by the cycle of a change** ([section 11.4](#114-the-declaration-in-its-repository)): `project-declare environment=dev` → `project-apply` proposes it by pull request (its pull request and its answer say that applying it after the merge creates a Google Cloud project, whose id is permanent) → the owner merges → one `project-apply confirm=yes` updates the folder and, in the same run, creates the ground of the environment ([section 6.4](#64-shared-platform--project-resources)), announcing the GCP project before it creates it. Only the merged declaration is applied: while it is being changed, the environment's rows are `not checked until the change is merged` and no cloud command runs.
- **A declaration without `environments` touches no cloud**: `project-plan` and `project-apply` run not one `gcloud` command for it and print the same rows as before environments existed.
- Changing the region or the root of an environment that already exists in the cloud is not built: `project-plan` reports an image repository found in another region as something to fix by hand (a repository has one region), and does not detect a changed root (a GCP project does not move by itself) ([section 18](#18-open-items)).

---

## 12. Skills of the `aleogr` orchestrator

- **Core:**
  - `platform-plan`: compares the shared platform choices in `defaults.json` with the cloud and reads whether the login of the organization is prepared; changes nothing (implemented: shared project, APIs, budget alert, database switch, database instance and the row `login`, [section 6.8](#68-shared-platform-resources));
  - `platform-apply`: creates and changes the shared platform ([section 6.8](#68-shared-platform-resources)) as `platform-plan` lists, and last prepares the login of the organization as far as a command can (`gcp_login-setup`), printing what is left to the owner in a `Login` section; without `confirm=yes` it asks nothing and changes nothing: it shows the plan, with the fixed cost of the instance when it would create it, and ends `pending` with the one command `/aleogr:platform-apply confirm=yes`;
  - `project-declare` (implemented for version 1 of the declaration): writes or edits `.aleogr/project.json` in the current folder from `key=value` arguments. A new declaration needs `name`, `owner` and `description` and takes the rest from `defaults.json`; an existing one keeps everything the arguments do not change, and its `name`, owner and repository name are never changed (that is another project). `component=<name>` with `stack=`, `path=` and `version=` adds a component or changes the version of an existing one ([section 11.5](#115-components)); `environment=dev` adds the environment and, with it, the `cloud` of the defaults, and `cloudRoot=tst` sets the root ([section 11.6](#116-cloud-and-environments)); `component=<name> database=yes|no` sets or removes a component's `database` key, refusing `yes` without an environment or with a Go version below the database's minimum ([section 11.5](#115-components)). It writes the file in its canonical form, runs no command and changes nothing on GitHub; `created`, `updated`, `unchanged` or `failed`;
  - `project-plan` (implemented for the repository, the components and the environment `dev`): validates the declaration, runs `tools-check command=gh`, `github_repo-describe`, `github_checkout-setup mode=plan` and `github_pull-request-open mode=plan`, and prints five items with their state and action: `repository`, `settings` (description, topics and the seven settings), `visibility`, `declaration` and `protection`. A declaration with components also runs `github_ci-setup mode=plan` and, when the declaration's action is `none` or `propose`, `go_setup mode=plan` for each component, and prints seven items: `components` (`as declared`; `to generate: <names>` / `generate`; `needs attention: <names>` / `fix the folder`) and `ci` (`as declared`; `missing` or `differs` / `generate`) come after `declaration`. While the declaration's action is `merge it`, `update` or `fix the folder` they are `not checked until the change is merged` (and `not checked until the declaration is sent` before the birth's send). The protection is compared with the check `ci` exactly when `ci.yml` is on the default branch, and then reads `protected, requires ci`. With components it runs `github_checkout-setup` with `head=check`, so a merged pull request that added code or `ci.yml` without changing the declaration still makes the folder `this folder is behind` / `update` (and nothing is generated again); it also returns `changed`, the tooling paths the pull request skill found changed in the folder. It changes nothing and ends with `nothing to do` only when every action is `none`. The `declaration` item is one of: `in the repository` / `none`; `not sent yet` / `send` (the birth); `changed here` / `propose`; `not in the repository` / `propose`; `proposed in pull request #N` / `merge it`; `this folder is behind` / `update`; `this folder needs attention` / `fix the folder`. `merge it` and `fix the folder` are the owner's to do;
  - `project-plan` with environments ([section 11.6](#116-cloud-and-environments)): a declaration with `environments` also runs `tools-check` for `gcloud`, right after the one for `gh` and before anything is read (a `gcloud` that is not signed in fails the plan before any row), and prints four more items after `protection`: `environment dev` (`exists`; `missing` / `create`; `billing not linked` / `repair`), `apis` (`enabled`; `to enable: <n>` / `enable`), `registry` (`as declared`; `missing` / `create`; `cleanup differs` / `configure`, also when the policy has a rule the tooling does not own, such as a third rule added by hand; `in another region` / `fix by hand`; `not a Docker repository` / `fix by hand`, a repository of the declared id and region whose format is not Docker, which is never acted on) and `ci identity` (`as declared`; `missing` / `create`; `differs` / `update`; `cannot push` / `grant`; `needs attention` / `fix by hand`): nine items without components, eleven with. They are read only while the declaration's action is `none`, by `gcp_environment-describe`, then `gcp-artifact-registry_registry-describe` and `gcp_ci-identity-setup mode=plan` (with the repository's numeric ids and default branch from `github_repo-describe`); otherwise they are `not checked until the change is merged`, or `follows the creation` while the repository does not exist. Nothing is read inside a GCP project that is missing or has no billing (the three others `follows the environment`), nor in Artifact Registry or IAM while an API is still off (`registry` and `ci identity` `follows the apis`). `cannot push` is decided by the plan: the CI account is not among the writers of the image repository. `fix by hand` is the owner's to do: it is never `nothing to do`, and `project-apply` never acts on it, nor on `needs attention`. The plan also returns `environment` (`{ name, projectId }`), `ciVariables` and `repositoryEnvironments` (the environments the repository's copy of the declaration has, from what the checkout already read: `project-apply` uses it to know whether a proposal adds an environment). With `projectId=<id>` it reads the GCP project of `dev` by its id instead of searching by labels, which can lag behind a creation;
  - `project-plan` with components and environments: two more items after `ci identity`, thirteen in all. **`services`**: `waits for the login` / `prepare the login` while the login of the organization is not prepared or could not be read (`gcp_login-describe`, counted against the project of `dev`; the line under the table names `/aleogr:platform-plan`, and no service is read; a read refused because the IAP API was enabled a moment ago, which the plan sees among the enabled APIs, ends the plan `failed` with the item `services` instead, and `project-apply` waits for it); otherwise, from `gcp_deploy-describe`, `missing: <names>` / `create`, `differs: <names>` / `update` (a service whose login lets in `allUsers` or `allAuthenticatedUsers`, the difference `open`, included), `waiting for the first deploy: <names>` / `none` (each as declared and still on Google's sample image; the line under the table says to merge the pull request that carries the deploy jobs, or, once it is merged, to merge a change to the component), or `as declared` / `none`. **`ci secrets`**, from `github_variables-set kind=secrets mode=plan` with the four values built from the reads the plan already made, which compares names only (a secret's value cannot be read back, so a value changed by hand is not seen, and a deploy then fails visibly): `as declared` / `none`, `missing: <names>` / `set` (with one line under the table saying that the secrets are compared by name only), or `follows the ci identity` / `none` while that row has an action (its values are known once the identity is as declared), `follows the registry` / `none` while the registry is `fix by hand`. Both follow the environment and the APIs as the rows of the ground do. With environments, `components` is also `to generate` while a component's `Dockerfile` is missing, and `ci` is judged with the deploy jobs of exactly the components whose service exists ([section 4](#4-cicd)): a version 1 file then `differs`. `prepare the login` is the owner's to do (on the platform), never `nothing to do`, and `project-apply` makes the other actions meanwhile. The plan also returns `urls` (each existing service's address), `ciVariables` with the four names (no `GCP_REGION`), `ciDeployComponents` (the components given deploy jobs; `[]` for the version 1 file) and `defaultBranch` (the arguments it judged the CI file with, which `project-apply` writes it with). The plan never prints the signed-in login;
  - `project-apply` (implemented for the repository, the components, the ground of the environment `dev` and its services): runs `project-plan`, takes the plan's confirmation, invokes the `aleogr-repo-github` and `aleogr-stack-go` skills in the order of [section 12.2](#122-apply-order) and runs `project-plan` again; `nothing to do` comes only from that last plan. `propose` and `generate` are one step and one pull request: it writes the starting point of each component to generate (`go_setup mode=apply`) and `ci.yml` when the `ci` row says `generate` (`github_ci-setup mode=apply`), then opens the tooling pull request (`github_pull-request-open`) with the declaration and those files, and ends the run `updated`, with the item that names the pull request; the pull request's title follows what it carries (the plan's `changed` plus the files this run wrote): a component's `go.mod` among them gives `Add the components <names> and CI` (`Add the components and CI` past 100 characters), otherwise `ci.yml` gives `Update CI`, otherwise `Change the project declaration`; actions on GitHub listed next to `generate` wait for the run after the merge; a stop after files were written ends the run `updated`, the files kept in the folder for the next run to propose (when the pull request skill had already committed them, as after a refused push, they are in the local branch it names, and the item says so); `update` fast-forwards the folder (`github_checkout-setup`, with `head=check` when there are components) and plans again. It stops, changing nothing, on `merge it` or `fix the folder`, and stops at the first step that ends `failed` or `pending` (except the protection's plan limit on a private repository, the expected end there).
  - `project-apply` with environments: after the repository's steps of a run whose declaration's action is `none`, it makes the environment's items in the order of [section 12.2](#122-apply-order), each skill only for an item whose action calls for it, under the same `confirm=yes` (nothing of it exposes anything or has a fixed cost).
    - **The GCP project is announced, not confirmed a second time.** Its id is permanent, so the owner is told before the merge and again before it is made, and the `confirm=yes` of the run covers it. When the proposal adds an environment (the plan's `repositoryEnvironments` lacks one of the folder's environments, or is not known), `github_pull-request-open` gets `note=`, so the pull request's body says `Applying this change after the merge creates a Google Cloud project, whose id is permanent.`, and the answer says it too. A proposal that also adds the database to a component gets the database's warning ([section 6.4](#64-shared-platform--project-resources)) in the same `note`, after this one and a space: the `note` holds up to 300 characters, enough for both. After the merge, one run updates the folder, plans again and goes on under the same confirmation; right before `gcp_environment-create` it writes `This run creates the GCP project of dev, whose id is permanent.`, and the answer repeats it. A merged declaration that did not come through the tooling's proposal (edited by hand, or in another folder) is therefore still announced before the creation, in the run itself. A plan whose `environment dev` is `create` and whose run reaches the environment also says, without the confirmation, `With confirm=yes, this run makes in Google Cloud: …`. Only a merged change of visibility still takes one more run, with its own `confirmVisibility`.
    - **A project created in the run has its id carried through**: every later skill gets the id `gcp_environment-create` returned, with no plan in the middle (the project has nothing inside it, and a search by labels may not show it yet), and the last plan is `project-plan projectId=<id>`, which reads the project by its id.
    - **A project that already existed is planned again** after its billing was repaired or APIs were enabled, so that the rows that could not be read are read and one run ends with `nothing to do`.
    - **The wait for just-enabled APIs.** When `gcp_services-enable` enabled something in the run and the first Google Cloud skill after it (that middle plan, or the first of the registry and identity skills) ends `failed` having changed nothing, the run takes it as the refusal of a just-enabled API and polls that skill: 30 seconds, then the same skill again, in full, at most 10 tries ([section 10.4](#104-behavior-of-every-skill)). Only skills that read before they change are tried again, so a try never repeats a change; one skill is polled, once per run. When it answers, the run goes on and the answer says `Waited for the APIs enabled in this run: <skill> answered on try <n>.`; when the limit passes, the run stops, `updated`, with the item `apis` (`The APIs enabled in this run were still refused after 10 tries, about 5 minutes of waits; nothing after them was made.`). A binding refused right after its account's creation is polled the same way inside `gcp_ci-identity-setup` and `gcp-artifact-registry_access-grant`.
    - **After a project created in the run (or found by the search by parent when the plan had missed it), no stop and no item of the last plan says "apply again"**: the item names the project's id and says to wait a minute, run `project-plan`, and run `project-apply confirm=yes` only when that plan shows `environment dev` `exists`. The waits above make such a stop rare, not different. A created project that the last plan cannot see (no id known) ends the same way, `updated`, never with `nothing to do`. A run whose plan does not see the project would plan to create a second one, which the search by parent of `gcp_environment-create` guards against as well ([section 6.7](#67-gcp-organization-folders-and-billing)).
    - **With components, the cloud first.** When the plan has `generate` and an item of the environment has an action, the files are not written yet: the run makes the ground, then the services (`gcp_deploy-setup`, all the components in one invocation, which first closes any existing service that is open or without the login, then creates each missing one behind the login with Google's sample image, repairs one that differs, grants CI its two roles on each service and puts the account that runs it on the allowed list), then the four CI secrets (`github_variables-set kind=secrets`, with `replace=yes` when the run created or changed the GCP project, the image repository or the CI identity), then plans again, and only from that plan writes the files a merge needs (each component's `Dockerfile`, and `ci.yml` with its deploy jobs) and proposes them in one pull request, titled `Add the Dockerfiles of <names> and CI` (`Add the components <names> and CI` when the components' code is generated in the same pull request). So when the owner merges, everything the deploy job needs exists. A project of stage 4a goes from its state to "merge this pull request" in one confirmed run. No service is created while the services wait for the login; a project that already has its CI file then gets no file in that run (the files go in the run that creates the services), while one with no CI file yet still gets its Go starting points, its `Dockerfile`s and the version 1 CI file. Nor is a service created, nor a file proposed, in the run that creates the GCP project (no plan read the login or the services of that project: the next run creates them, [section 18](#18-open-items)). The wait for just-enabled APIs also covers a plan that ends `failed` on the services' read, or on the login's read, right after the run enabled the APIs (a just-enabled Cloud Run or IAP API). A stop of `gcp_deploy-setup` stops the run with no proposal, its item never a bare `/aleogr:project-apply confirm=yes` (a second run on a guess would fail the same way), and its answer repeats, word for word, `gcp_deploy-setup`'s sentence naming any service still open or still without the login. A refused grant of the owner's own access through the login does not stop the run: the services are made all the same, and the item `access` (`/aleogr:project-access person=<e-mail>`) is carried to the end, since no plan compares a person's access. Creating a service is not confirmed apart: it is behind the login and has no fixed cost, so the run's `confirm=yes` covers it.
    - After the merge, CI checks, builds, pushes and deploys each component; the next `project-apply confirm=yes` updates the folder and ends with `nothing to do`. The answer gives each service's address, last before the result block, from the last plan's `urls`; while a service still runs Google's sample image it adds that the first merge with its deploy jobs deploys it.
    - A failure stops the run; what was created stays, and the next plan shows what is left. When the last plan has the environment and no service, the answer says that nothing is deployed yet and that the CI identity can only push images. A run that creates the repository never makes the environment: its rows `follow the creation`, and the next run makes them.
    - **The answer is short** ([section 10.4](#104-behavior-of-every-skill)): one line per skill of the run that made something (none for a skill that ended `unchanged`), the table of the last plan only, the prescribed sentences, what is left, the pull request's address, and one result block. After a proposal it has a fixed short form: those lines, the table with its lines, the proposal's warning when it applies, the pull request's address on its own line, the `how` of each item, the services' addresses and the result block; the invocation of the pull request skill is not repeated (it was shown when it was made, and the pull request lists its files). The plan runs at the start and at the end, and in the middle only when its rows could not be known before (after the folder's update, and for a project that existed and had its billing linked or APIs enabled).
  - **The cycle of a change:** `project-apply` → the owner merges → `project-apply`. The first run proposes the change, with the files it generates; the owner reviews and merges the pull request on GitHub; the next run updates the folder and goes on, under the same `confirm=yes`, with the plan of the merged declaration, when that plan exposes nothing (a GCP project to create included: it is announced, above). When the merge put `ci.yml` on the default branch, that plan finds the protection without the check `ci` and the same run updates it (`github_branch-protect checks=ci`): from then on a pull request whose job `ci` fails cannot be merged. **A merged change of exposure takes one more run:** when the plan after the update would make the repository public (or private), the run stops there, `updated`, with the item that names `confirmVisibility=<value>`, and the next run applies it. So from a local change to `nothing to do`, a declared environment takes two commands and a merge: `project-apply confirm=yes`, the merge, `project-apply confirm=yes`.
  - **A new project, from nothing to its first deploy** (components and the environment `dev` declared from the start, the login of the organization prepared): after `project-declare`, four `project-apply confirm=yes`, one `project-plan` and one merge. The first run is the birth (the repository, its settings, the declaration, the protection). The second makes the ground (the GCP project, announced before it is made, its APIs, the image repository, the CI identity) and the four CI secrets; having created the GCP project, it creates no service and proposes no file. After a minute, `project-plan` shows `environment dev` `exists`. The third creates the services and proposes the Go starting points, the `Dockerfile`s and `ci.yml` with its deploy jobs in one pull request, whose merge deploys. The fourth updates the folder, makes the protection require the check `ci` and ends with `nothing to do`. While the login is not prepared, the third run proposes the code with a version 1 CI file instead, and a later run, once the login is prepared, creates the services and proposes the deploy jobs: two merges.
  - `project-plan` with a component that uses the database ([section 6.4](#64-shared-platform--project-resources)): the row `apis` counts `sqladmin.googleapis.com` among the project's APIs; `go_setup` runs with `database=yes`, so `components` is `to generate` while the check, its route or a module is missing (and `needs Go on this machine` / `fix by hand` when the modules are to be added and `tools-check command=go` finds no Go); and the row **`database`** comes after `services` and before `ci secrets`, fourteen rows in all. It finds the shared project by its labels (`gcp_environment-describe project=shared platform=shared`), passes the three settings to `gcp_deploy-describe` (`env=`) and reads `gcp-cloud-sql_database-describe`, which never starts the instance. Its states: `follows the services` / `none` (a row before it has an action, or a database component's service is missing: `project-apply` makes those first and plans again), the `follows …` and `not checked …` states of the other rows, `user name too long` / `fix by hand`, `needs the shared platform` / `none` (no shared project, its Cloud SQL Admin API off, or no instance in it: when the read of the instance fails, the plan reads it once more with `gcp-cloud-sql_instance-describe`, and an instance that does not exist is this state; any other failure of that read fails the plan with a sentence that names no project id), which is never `nothing to do`: the plan ends `pending` with the item `database`, whose `how` names `/aleogr:platform-plan`, and, when no other row has an action, its last line is `Nothing can be made for the database until the shared platform is ready.`; `missing: <database, user, roles, settings>` / `create`, `differs: settings` / `update` (only the settings: written without the instance), and `as declared` / `none`. While the instance is not running only the roles and the settings are judged, and an `as declared` row has the line `The database itself was not read: the shared instance is stopped.` A `create` on a stopped instance has the cost line of [section 6.4](#64-shared-platform--project-resources), and a `follows …` row its conditional line; a `create` on an instance that is `starting` has the line `The shared instance is starting: project-apply confirm=yes waits until it accepts calls, then makes what is missing.` The plan's output `database` is `{ name, instanceState, start, components }` (no e-mail, no user name, not the shared project's id); `start` is true exactly when the instance is stopped and a database, a user or roles are missing. A `route` left to the owner (a `main.go` changed by hand) is a line and a `pending` item, and the plan still says `nothing to do` for the tooling's part ([section 18](#18-open-items)). A declaration in which no component uses the database has no such row, read or argument.
  - `project-apply` with a component that uses the database: the proposal that adds the key carries the check's code in the same pull request, and its body and answer announce the cost of a start (above). After the merge one `project-apply confirm=yes` updates the folder, enables the API (with the wait for just-enabled APIs), and, after the services (in the same run when it creates them: it plans again after them), makes the database by the row: when the instance is stopped and something must be made in it, under `confirm=yes` itself only, it reads the night stop (`gcp-cloud-sql_instance-switch-setup … mode=plan`) and starts the instance only when that read says the switch is ready, waits for it (30 tries, a failed read counting as a try) with `gcp-cloud-sql_database-describe`, then `gcp-cloud-sql_database-create`, `gcp-cloud-sql_access-grant` for each such component, and last `gcp_deploy-setup env=…` with the settings; with the instance already starting, the same wait with no start; with the instance running, the same without the start or the wait; with only the settings to write, only the last. `go_setup database=yes` runs before any start, so a failure there costs nothing, and a start command that fails is read back once, so the answer says whether the instance runs. A plan whose row `database` is `needs the shared platform` with nothing else to do ends the run `pending` with the item `database` (`/aleogr:platform-plan`), never `nothing to do`. A stop of these steps has one item `database` and the stopping skill's own fixed sentence; it never says "apply again" on a guess. The answer has the start's sentence when the run started the instance and, after the services' addresses, one line per database component, `<component>: <address>/db`. The run never stops the instance. It runs no command of its own beyond `sleep 30`.
  - `project-access` (implemented): run in a project's folder, `person=<e-mail>` lets one person in to every service of the project in each declared environment (it finds the GCP project with `gcp_environment-describe` and invokes `gcp_access-grant` with the declaration's components); `list=yes` instead says how many people each service lets in, and who, in the answer's text only. It validates the address before invoking anything, by the same rule as `gcp_access-grant`. It asks no confirmation: letting one person through the login costs nothing and one command undoes it, which its answer gives. It flags a service whose login lets in `allUsers` or `allAuthenticatedUsers` (anyone on the internet who signs in with any Google account), with the command that removes that, and says that `project-apply confirm=yes` also closes it. It removes nobody and creates no service.
  - **Confirmation:** one per run, for the whole plan, and a run is all or nothing. A plan that changes no visibility is confirmed by `confirm=yes` (generating files, proposing a change by pull request and updating the folder expose nothing); a plan that creates a public repository or makes one public only by `confirmVisibility=public`, and one that makes a repository private only by `confirmVisibility=private`, which then confirm the whole plan. Without the confirmation its plan needs, the run ends `pending`, changes nothing and shows the text that confirms; a `confirmVisibility` the plan does not need is `failed`, so a confirmation never applies to another plan.
  - Status rule: `pending` as a status means nothing was changed. Once something was done the status says what (`created`, `updated`) and what is left is an item of the `pending` list.
  - The `project-*` and `platform-*` skills run no `gh`, `git` or `gcloud` command themselves and never wait for an answer: they invoke skills. The one command an orchestrator runs is the wait `sleep 30` of `project-apply`'s wait for just-enabled APIs and of its wait for the shared instance's start.
  - `platform-*` act on the shared platform (they address its project as `project=shared platform=shared`); `project-*` remain for projects.
- **Shortcuts:** `project-create`, `component-add`, `service-add`, `tenant-add` (declares a tenant in an environment and applies it).
- **Maintenance:**
  - `tools-check` (implemented for `gcloud` and where Claude runs, for `gh` when called with `command=gh`, and for `go` with `command=go`, which `project-plan` calls when a component's database modules are to be added; with no argument it checks only `gcloud`, so the platform skills do not depend on `gh`): CLIs, authentication, MCPs, devices; identifies whether it runs locally, in a codespace or in a cloud session and warns about what is not possible there;
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

1. Repositories: create → configure (settings, then visibility) → send the declaration (only at the birth, [section 11.4](#114-the-declaration-in-its-repository)) → protect (with the check `ci` once `ci.yml` is on the default branch). After the birth, a `propose` or `update` of the declaration comes first: `propose` ends the run, `update` plans again. The files of steps 7 and 10 (the components' starting points and `ci.yml`) are generated here, in the folder, and proposed with the declaration in the same pull request; the birth generates nothing, and its last plan lists `generate` for the next run.
2. Domain registration.
3. Cloud base (or verification of the shared platform): the environment's GCP project (`gcp_environment-create`, with `root=tst` when the declaration has it), then its APIs (`gcp_services-enable`, all the missing ones in one call).
4. Secrets.
5. Infrastructure (db, cache, storage, registry, search): the image repository (`gcp-artifact-registry_repository-create`), then its cleanup policy (`gcp-artifact-registry_cleanup-configure`).
6. Services (auth, email, sms, payments, llm, flags).
7. Components (stack, platform, hosting, push), including devcontainer.json.
8. DNS, routes and CDN (collects records from previous steps).
9. Operations (monitoring, analytics, notify).
10. CI/CD (the thin `ci.yml` with its deploy jobs, the CI secrets): the CI identity (`gcp_ci-identity-setup`), then its push access to the image repository (`gcp-artifact-registry_access-grant role=push`), then, with components, the services (`gcp_deploy-setup`), then the CI secrets (`github_variables-set kind=secrets`); the `Dockerfile`s and `ci.yml` come last, in the pull request.
11. Distribution (store, publish).
12. Final `project-plan` must say "nothing to do".

In stage 4a, steps 3, 5 and the identity of step 10 make the ground of the environment `dev` ([section 6.4](#64-shared-platform--project-resources)), in this order: GCP project → APIs → image repository → cleanup policy → CI identity → push access. Each is invoked only for a plan row whose action calls for it (the GCP project announced before it is made, [section 12](#12-skills-of-the-aleogr-orchestrator)), and a skill's commands are refused until the step before it is done (nothing is read inside a missing GCP project, and Artifact Registry and IAM refuse every command until their APIs are on, and for a while after they are enabled: the first skill after the APIs is then polled, [section 12](#12-skills-of-the-aleogr-orchestrator)). The image repository and the CI identity are independent: a repository found in another region (`fix by hand`) does not stop the identity, but its push access waits until the repository is in the declared region.

In stage 4b-2, with components, the same run goes on: services → CI secrets → a plan → the `Dockerfile`s and `ci.yml` with its deploy jobs, proposed in one pull request. The cloud comes before the files because the files depend on it: a deploy job is written only for a service that exists, and a merge must find the services, the CI identity's roles and the secrets in place. The CI secrets are set also when no service is made (the login not prepared, a GCP project created in the run): they do not depend on the services.


In stage 4c, with a component that uses the database, the same run goes on after the services: (the read of the night stop, the instance's start and its wait, only when needed; the wait alone when the instance is already starting) → the database → each component's user and roles → the services' settings → the CI secrets → a plan. The code of the check went with the declaration's pull request; `go_setup database=yes` runs before any start.

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
- `self-test-ci-go.yml` (built): runs the reusable `ci-go.yml` on the fixture module `.github/testdata/ci-go/`, on pull requests that change either of them ([section 4](#4-cicd)).
- `self-test-deploy-cloud-run.yml` (built): runs the static check `.github/testdata/deploy-cloud-run/check.sh` on `deploy-cloud-run.yml`, on pull requests that change either of them ([section 4](#4-cicd)). The deploy itself needs a cloud and is not run here.
- Skill tests (`.claude-plugin/tests/`): `run.sh <scenario>` runs the real skills headless (`claude -p`) against fake CLIs (a fake `gcloud`, `gh`, `git` and `go` in `.claude-plugin/tests/bin/`, with numbered responses for calls that must answer differently before and after a change, and a fake `sleep` that logs the wait and returns at once, so a scenario pins how many times a skill waited and tried) and checks the logged calls and the final answer against the scenario's `expect.txt` (line types in `.claude-plugin/tests/README.md`). They create nothing outside the repository, are run by hand for now (no workflow), and each run costs model usage. Every skill of the Google Cloud and Artifact Registry plugins has scenarios in `plan` and `apply`, missing, existing and differing, with fictitious ids (GCP project `aleogr-dev-demo-ab12`, repository `example-org/example-repo`); the orchestrator's scenarios include the rule that a declaration without `environments` runs no `gcloud` command (the fake logs a `gcloud` call without the word `gcloud`, so that rule pins the subcommands).
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
- Each test uses an `<id>` in ALL resources ([section 1](#1-names)): repository `test-<id>`, a GCP project per environment created like a real one but inside `tst` (`gcp_environment-create` with `root=tst`), services `test-<id>-<component>`, database `test_<id>_<environment>` on the shared instance, `test-<id>-<environment>.aleogr.dev` (tenants: `<tenant>.test-<id>-<environment>.aleogr.dev`).
- **The test:** run `/aleogr:project-create` with a declaration from `.claude-plugin/schemas/examples/`; check:
  - green CI;
  - address responding (and tenants, if any);
  - codespace opening with the right tools;
  - a Claude Code cloud session in the `base` environment working on the created repository;
  - final `project-plan` saying "nothing to do".
- **Example scenarios:**
  - simple backend (1 component, 1 project environment);
  - multi-tenant monorepo (2 components, two tenants, CI running only the changed component's job);
  - two project environments (dev + hom, with promotion from one to the other);
  - Android app (only repository, CI and devcontainer, no DNS or cloud).
- **Every test creates a new `test-<id>` repository**; there is no fixed, reused test repository. Skills that only touch files of a project are tested with a minimal declaration (repository only, no cloud or DNS).
- Initially run manually; automate later, if it makes sense.

### 15.4 Reference project

- **The tooling is driven by a reference project, `pilot`**, in the GitHub organization `aleogr-sandbox` and, on GCP, in the folder `tst` ([section 6.7](#67-gcp-organization-folders-and-billing)): a status page per tenant, multi-tenant from the start, with two components at first, `status` (public by nature) and `admin`.
- Everything is behind the login by default ([section 6.3](#63-protection-and-single-access-point)); `status` is opened to the public only during the test of that path, because a public address is found by bots and each visit wakes the service.
- Its repository, `aleogr-sandbox/pilot`, is born private and then made public, and stays public: one repository proves both behaviours of the free plan, a private repository whose protection is `pending` and a public one protected by the ruleset `main`.
- Its environment `dev` is a GCP project of its own, `aleogr-dev-pilot-<random>`, in the folder `dev` inside `tst` (its declaration has `"root": "tst"`), with its image repository and its CI identity (stage 4a), and, from stage 4b-2, the services `pilot-admin` and `pilot-status` behind the login, deployed by its CI.
- It stands in for the first real project (an identity provider: Go, monorepo, not multi-tenant; later products may be multi-tenant), so that the tooling is proven before a real project depends on it ([section 17](#17-implementation-strategy)).
- Small disposable `test-<id>` projects, one per scenario of [section 15.3](#153-layer-3--end-to-end), come after both creation AND removal work on `pilot`.

### 15.5 Payments

- Always in test mode.

### 15.6 Cleanup

The scheduled workflow `self-cleanup-tests.yml` deletes tests older than a few days, in this order:

1. Find the test's resources by its `<id>`, by the names and labels of the discovery rules ([section 7](#7-where-data-lives)).
2. Delete the external resources (cloud, also checking the label `aleogr-test=<id>`; on GCP, projects only inside the folder `tst`; DNS records/routes matching the pattern; databases `test_<id>_<environment>`; codespaces).
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
- A stop for a second confirmation before creating a GCP project, after the merge (the run updated the folder, showed the plan and ended with the item `confirm`; the next run created it): one more command for something the owner had already decided by merging. Replaced by a warning at the proposal, in the pull request and in its answer, and an announcement in the run before the creation. It is an announcement, not a consent gate: a declaration merged without the tooling's proposal is announced in the run that creates its project, under that run's `confirm=yes`.
- Stopping when an API just enabled refuses a command, with the owner waiting a minute and running the apply again by hand (one wait, one retry): the refusal is known to pass by itself. Replaced by the bounded wait ([section 10.4](#104-behavior-of-every-skill)): the run tries again every 30 seconds, for 5 minutes at most, and stops only after that.
- Google's managed OAuth client for the login: in an organization owned by a personal Google account it refuses every account, the owner's included, even when it is on the allowed list ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). Replaced by one custom OAuth client set on the organization. Also discarded: a client per project or per service, set in the console each time (the same clicks for every new project).
- A fraction of a CPU for a service (Cloud Run accepts from 0.08): below one CPU an instance serves one request at a time (and needs the first-generation environment), so with the maximum of 2 instances a service would serve two requests at a time in all. The cost is by use either way, so the saving is small and the limit is felt at once. Chosen: 1 CPU and 512 MiB.
- A separate `cd.yml` that deploys after the CI workflow, triggered by `workflow_run`: such a run has the default branch as its ref after a workflow that a pull request may have started, so its token passes the CI identity's condition, which checks the ref, not the code; and it would repeat the change detection that `ci.yml` already makes. Chosen: the deploy jobs in `ci.yml`, after each component's check, on `push` to the default branch only ([section 4](#4-cicd)).
- Base images of the `Dockerfile` pinned by digest: reproducible, but it opts out of the base images' security fixes, and nothing here would move the pins (the file is the owner's once written). Chosen: named by tag (`golang:<version>`, `gcr.io/distroless/static-debian13:nonroot`).
- The identifiers passed to the deploy workflow as plain inputs, with a first step that masks them: GitHub prints a step's `env` in the log before the step runs, so the masking step itself would print them in clear in a public log. Chosen: they are passed as secrets, which the runner masks from the job's start, and the first step masks them again with the project number.
- The four identifiers as repository **variables**: a variable can be read back, so the plan could compare its value, but it is neither masked in every log for certain nor withheld from a pull request from a fork for certain, and a project's repository may be public. Chosen: repository secrets, compared by name only ([section 4](#4-cicd)).
- Deploy jobs proposed before their services exist (for a new project, in the first proposal of its code): the merge would run a deploy against services that do not exist yet, and go red. Chosen: the services first, then the files, in the same run; a CI file proposed before the services exist has no deploy job, and the deploy jobs come in the proposal made by the run that creates the services ([section 12](#12-skills-of-the-aleogr-orchestrator)).
- Deploy jobs for every declared component whenever the file has any: a component just added to a deployed project would get a deploy job before its service exists, and the merge that adds it would run red. Chosen: a deploy job per component whose service exists ([section 4](#4-cicd)).
- A database password kept in Secret Manager, with Cloud Run's built-in Cloud SQL socket and a built-in database user: a password to generate, store, rotate and never leak, through a skill's output or a service's settings. Chosen: Google's Cloud SQL connector for Go with IAM authentication, as the service's own account, and no password anywhere ([section 6.4](#64-shared-platform--project-resources)).
- A proxy container (the Cloud SQL Auth Proxy) beside each service: no dependency in the code, but a second container in every service, with its own memory and its own settings to keep as declared. Chosen: the connector inside the component's code.
- The tooling regenerating `main.go` whenever the declaration changes, to add the route of the check: it would overwrite code that is the project's. Chosen: `main.go` is replaced only while it is byte for byte the tooling's own file; otherwise the one line is left to the owner ([section 11.5](#115-components)).
- When the shared instance is stopped and something must be made in it, a run that stops and names the command that starts it (two commands and a wait in the middle, against the premise of [section 10.4](#104-behavior-of-every-skill)), or one that starts it, makes what is missing and stops it again (cheapest, but the owner's next step is to see the check answer, which needs the instance running). Chosen: the run starts it, waits, makes what is missing and leaves it running until the night stop, saying so.
- A separate confirmation for the start of the shared instance (the run after the merge stopping on the cost, and one more command to start it): two commands and a wait in the middle for a cost of cents with a ceiling. Chosen: the cost is announced at the proposal, in the pull request and in its answer, and said again in the answer of the run that starts it; the merge and the run's `confirm=yes` are the consent.
- The cost line only in a plan that read the instance stopped: a run whose first plan has the row `database` as `follows the services` (or `follows the apis`, or any `follows …`) makes the rows before it, plans again and may start the instance in the same run, with no line shown before. Chosen: the conditional line under every plan whose row `database` is a `follows …` state ([section 6.4](#64-shared-platform--project-resources)).
- The roles granted before the user, whatever the instance's state (as first planned: roles cost nothing and need no running instance): a run cut short, or a refused create, would leave the roles right and the user missing, and the roles would no longer mean that the user exists. Chosen: the user first, the roles after, both only while the instance runs.
- Trusting "until the night stop" without reading it: the stop jobs can be paused, deleted or changed, and a start would then run until someone noticed (about R$ 43 a month at the rate read), with the budget alert as the only net. Chosen: the run reads the switch right before the start and does not start the instance unless it is ready.
- Stopping the wait for the instance on the first failed read: each try is a full read of the instance, its operations, the shared project's policy and the two lists, about 24 tries in a start of twelve minutes, and one passing failure would leave the instance started and charged with nothing made. Chosen: a failed read counts as a try; only the limit of 30 tries ends the wait.
- A run that finds the instance starting stopping there, and leaving the owner to plan, wait and plan again by hand (the recovery after a session that dropped during the wait): a bounded wait for exactly that state exists. Chosen: the run enters the same wait, with no start.
- The row `needs the shared platform` counted as `nothing to do`, its action being `none`: a declared database that does not exist would read as done. Chosen: the plan and the run end `pending` with the item `database`, which names `/aleogr:platform-plan`.
- The two connection roles narrowed by an IAM condition to the one instance: Google documents a condition only for `roles/cloudsql.client` and its connect permission, and an untested condition on `roles/cloudsql.instanceUser` (the login) could stop the connector. Chosen: no condition for now, on a shared project that holds one instance; a binding under a condition counts as granted, so narrowing later needs no change of the plan ([section 18](#18-open-items)).
- Putting `go.mod` and `go.sum` back, after a refused `go get` or a moved `go` line, by writing them again from what was read: a long `go.sum` rewritten from a read can differ by one byte. Chosen: copies taken with `cp -p` before the commands, put back with `cp -p`.

---

## 17. Implementation strategy

- Build guided by the **NEXT REAL PROJECT**: only the plugins, workflows, actions and Features it requires (probably `aleogr`, `aleogr-repo-github`, `aleogr-cloud-gcp`, `aleogr-dns-cloudflare`, the `base` Feature, the `base` cloud environment and the reusable workflows for the project's stacks). **Goal:** the project comes out of nothing without me opening any dashboard.
- Before the first project: redesign and declare the shared platform, from scratch ([sections 6](#6-project-environments-the-shared-platform-and-minimum-cost), [7](#7-where-data-lives) and [18](#18-open-items)).
- **Orchestrator MVP:** `tools-check`, `project-declare`, `project-plan`, `project-apply`, plus the destructive command guard hook (already with the test exceptions) and read permissions in `allow`.
- The next real project's declaration, with fictitious values, becomes the first example in `.claude-plugin/schemas/examples/` and the first end-to-end test, before being applied to the real project.
- New families, providers, actions, workflows, Features and cloud environments come in when a real project needs them.
- **Until the first real project starts, the reference project `pilot` drives the tooling** ([section 15.4](#154-reference-project)). The first real project is an identity provider (Go, monorepo, not multi-tenant); later products may be multi-tenant, which is why `pilot` is multi-tenant from the start.
- **Stages after the shared platform** (stages 1 and 2 created it, [section 18](#18-open-items)); stage 3 (3a, 3b and both parts of 3c), stage 4a, both parts of 4b and 4c are built (4c not run yet against real Google Cloud and GitHub), the rest is not:
  3. repository, in three parts, each with its own real run and pull request ([design of 3a](plans/2026-11-18-pilot-stage-3a-design.md)):
     - 3a: the GitHub plugin `aleogr-repo-github`, which creates, configures and protects the repository of `pilot`;
     - 3b: the declaration and `project-declare`, `project-plan` and `project-apply`, which drive the plugin from a file, and `github_checkout-setup`, which sends the declaration at the birth ([design of 3b](plans/2026-11-18-pilot-stage-3b-design.md));
     - 3c: the pull-request cycle, a Go starting point and CI, in two parts, each with its own plan, pull request and real run ([design of 3c](plans/2026-11-19-pilot-stage-3c-design.md)):
       - 3c-1 (built): `project-apply` proposes a change by pull request (`github_pull-request-open`) and, after the owner merges it, updates the folder and applies it;
       - 3c-2 (built): components in the declaration, the Go starting point that `go_setup` generates once, the reusable workflow `ci-go.yml` and its self-test, the project's `ci.yml` written by `github_ci-setup`, and the protection that requires the check `ci` once `ci.yml` is on the default branch;
  4. running in `dev`, in three parts, each with its own plan, pull request and real run ([design of stage 4](plans/2026-11-19-pilot-stage-4-design.md)). Skills prepare only what is permanent; CI is the single deploy path, and no skill builds an image or deploys:
     - 4a (built), the ground: `cloud` and `environments` in the declaration, and, from `project-apply`, the GCP project of `pilot` in `dev`, its APIs, its image repository with the cleanup policy and the keyless CI identity that may push to it ([section 6.4](#64-shared-platform--project-resources)). Nothing is deployed and nothing reaches GitHub but the declaration;
     - 4b, in two parts, each with its own plan, pull request and real run ([design of 4b](plans/2026-11-19-pilot-stage-4b-design.md)):
       - 4b-1 (built), a fluid run and the login: the premise as a rule of every skill ([section 10.4](#104-behavior-of-every-skill)); `project-apply` that goes on by itself after a merge, announces the GCP project instead of stopping before it, and waits for just-enabled APIs; the bounded wait in the skills that make a binding; the short answer; and the login of the organization as a row of the platform's plan, with `gcp_login-describe` and `gcp_login-setup` ([sections 6.3](#63-protection-and-single-access-point) and [6.8](#68-shared-platform-resources));
       - 4b-2 (built and run, [section 18](#18-open-items)), the deploy: a `Dockerfile` per component, the reusable deploy workflow `deploy-cloud-run.yml` and the deploy jobs in the project's `ci.yml`, the Cloud Run services each with its own identity and the login in front, the CI identity bound to the deploy workflow, the four CI secrets, and `project-access`, which lets a person in ([sections 4](#4-cicd), [6.3](#63-protection-and-single-access-point) and [6.4](#64-shared-platform--project-resources));
     - 4c (built, not run yet, [section 18](#18-open-items)), the database ([design of 4c](plans/2026-11-26-pilot-stage-4c-design.md), changed during the build where section 6.4 says otherwise): the key `database` of a component; the `shared` actions of the db family on Cloud SQL (`gcp-cloud-sql_database-describe`, `gcp-cloud-sql_database-create`, `gcp-cloud-sql_access-grant`); a service's settings in the service skills (`env=`); the check `GET /db`, its route and its modules from `go_setup database=yes`; `tools-check command=go`; the row `database` of the plan; and `project-apply`, which starts a stopped instance when something must be made in it, after reading that the night stop is set up, and leaves it running until the night stop ([sections 6.4](#64-shared-platform--project-resources) and [11.5](#115-components)). It ends stage 4: with it, "running in `dev`" is complete;
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
- [ ] The GitHub skills have not run in the Windows app (PowerShell): the quoting of the description and the path of the ruleset files are proven in bash only. Nor have `github_ci-setup` and `go_setup`.
- [x] Make the skills that decide by a command's exit code also name the text that identifies each case ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)): done in stage 3b for the GitHub skills, `github_checkout-setup` included; when the two disagree, the text decides.
- [x] **First real run of stage 3b**, by me in Cloud Shell on 2026-11-18, following [`plans/2026-11-18-pilot-stage-3b-run.md`](plans/2026-11-18-pilot-stage-3b-run.md): `aleogr-sandbox/pilot` deleted by hand and born again from its declaration, then a change to the declaration applied after its pull request is merged. Every step answered as expected on the first attempt: the birth ended `nothing to do`, the birth commit carries GitHub's no-reply address, an unmerged change stopped the apply before any change, and after the merge the change was applied. What it showed is in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [x] `project-declare` repeated "nothing is public until `project-apply` runs with `confirmVisibility=public`" when it edited the declaration of a repository that is already public: fixed in stage 3c-1; the sentence is said only when the file is created public or the run changes the visibility to `public`.
- [x] **First real run of stage 3c-1**, by me in Cloud Shell on 2026-11-19, following [`plans/2026-11-19-pilot-stage-3c-1-run.md`](plans/2026-11-19-pilot-stage-3c-1-run.md): a change to the declaration of `aleogr-sandbox/pilot` (the topic `demo`) proposed by `project-apply` as a pull request, merged by me, then applied by `project-apply` after it updates the folder; the proposal's commit carries GitHub's no-reply address. Every step answered as expected on the first attempt: the proposal carried only the declaration, on a branch of its own, in a commit with GitHub's no-reply address; the folder went back to `main`; after the merge one run updated the folder, applied the topic and ended `nothing to do`, and a last plan said `unchanged`. What it showed is in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [ ] The `project-*` skills and `github_checkout-setup` have not run in the Windows app (PowerShell).
- [x] **First real run of stage 3c-2**, by me in Cloud Shell on 2026-11-19, following [`plans/2026-11-19-pilot-stage-3c-2-run.md`](plans/2026-11-19-pilot-stage-3c-2-run.md): the components `status` and `admin` of `aleogr-sandbox/pilot` declared, generated and proposed in one pull request, the project's CI green on it, merged by me, then `ci` required by the protection, and a pull request with a failing test blocked. Every step answered as expected on the first attempt: the push that carried `ci.yml` was accepted, the four checks ran green on the pull request and again on the push to `main`, one run after the merge updated the folder, generated nothing again and made the ruleset require `ci`, a last plan said `unchanged` with `protected, requires ci`, and on a pull request that broke a test the check `ci` was red, marked required, and the merge button was disabled. Before it, the self-test of `ci-go.yml` ran green on the pull request of stage 3c-2. What it showed is in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [x] **First real run of stage 4a**, by me in Cloud Shell on 2026-11-19, following [`plans/2026-11-19-pilot-stage-4a-run.md`](plans/2026-11-19-pilot-stage-4a-run.md): the environment `dev` declared for `pilot` with the root `tst`, proposed and merged; one `project-apply` updated the folder and stopped for the confirmation of the GCP project; the next created the project in the folder `dev` inside `tst` and enabled its APIs, and stopped with the item `apis` because the first read of the registry was refused; a plan some minutes later found the project and showed what was left, and one more run made the repository, its cleanup policy, the CI identity and the push access and ended with `nothing to do`. Every skill answered as designed; the search by parent sees the project. What it showed is in [`PROVIDER-FACTS.md`](PROVIDER-FACTS.md).
- [ ] **Stage 4a does not prove the CI identity from GitHub Actions**: nothing uses it before 4b-2. `gcp_ci-identity-setup` verifies the condition and the binding by reading them back; the first deploy of stage 4b-2 is the proof.
- [x] **The deploy uses no trigger that runs on the default branch's ref with other code**: `pull_request_target` (it runs with the default branch as its ref while the pull request's code is at hand) and `workflow_run` (it runs with the default branch as its ref after a workflow that a pull request may have started). Either one's token would pass the CI identity's condition, which checks the ref, not the code. Built in stage 4b-2: the project's `ci.yml` has only `pull_request` and `push`, its deploy jobs run only on a push to the default branch, and the static check of `deploy-cloud-run.yml` refuses any other privileged trigger ([section 4](#4-cicd)).
- [x] **The CI identity can re-point an existing image tag**: `roles/artifactregistry.writer` lets it push a new image under a tag that already exists (tags are mutable), though not delete one. Decided in stage 4b-2: a service is deployed by digest, never by tag ([section 4](#4-cicd)).
- [x] **First real run of stage 4b-2**, by me in Cloud Shell on 2026-11-21 and 2026-11-26, following [`plans/2026-11-20-pilot-stage-4b-2-run.md`](plans/2026-11-20-pilot-stage-4b-2-run.md) (results in it): one `project-apply` created the two services of `aleogr-sandbox/pilot` behind the login, set the four CI secrets and opened one pull request; its merge deployed both components on the first run. The run proved what only it could: the deploy's log shows neither the project's id nor its number; Google accepts the condition with `startsWith` and the six-key mapping and returns it as sent (`ci identity` reads `as declared` afterwards); the roles on the service and on its account alone let CI update the image, by digest; the fields `gcp_deploy-describe` reads are the ones a real service shows; 512 MiB and 1 CPU are accepted; PyYAML is on the GitHub runner; a change to one component deploys only that component, and nothing is deployed from a pull request. Not done: `project-access` with a second account.
- [ ] **A run after a merge takes about ten minutes to say `nothing to do`** (9m43s in the first real run of stage 4b-2: the folder's update and one full plan of fourteen invocations). It is correct and too slow for the premise of [section 10.4](#104-behavior-of-every-skill).
- [ ] **The answer of a long `project-apply` is lost when the terminal's session expires** (seen in the first real run of stage 4b-2): the run finished, but with its pull request open the plan checks nothing until the merge, so what was made had to be read with `gcloud` and `gh` by hand. Nothing shows the state of the cloud while a proposal is open.
- [ ] **The workflow clause of the CI identity stops another workflow file, not someone who can change the default branch**: a second workflow, or a job written in `ci.yml` itself, does not pass; but whoever can change the default branch can edit the calling workflow, or point it at another commit of the workflows repository, and its jobs still pass. What guards that is the protection of the default branch (the ruleset `main` and the owner's merge).
- [ ] **CI's role on a service is wider than what the workflow does**: `roles/run.developer` on a service lets a job of the deploy workflow change the service's other settings (its scaling or size included, never its access), so whoever can change the default branch can raise a service's minimum of instances through CI. The next plan shows it as `differs: <names>` and the next `project-apply` repairs it.
- [ ] **The people on a service's allowed list are never compared**: they are not declared. `gcp_deploy-setup` repairs a service's settings changed by hand (account, scaling, size, labels, a public member, a login that lets in `allUsers` or `allAuthenticatedUsers`, which `gcp_deploy-describe` reports as `open`, the login, the invoker check, the agent's and CI's bindings) and never its image; which people may get in is only read, by `project-access list=yes`. The owner's own access is not compared either: a grant refused in a run is carried as the item `access` (`/aleogr:project-access person=<e-mail>`), and a later plan does not see it.
- [ ] **No removal in stage 4b-2**: not of a person (the answer of `project-access` gives the `gcloud` command for the owner to run), not of a service or its account, not of an environment's ground (stage 6).
- [ ] **A default branch other than `main` is supported by the CI file but never run**: `github_ci-setup` writes it in the marker, the `push` trigger and each deploy job's `if:`, and `project-plan` passes the branch it read; no real repository with another default branch has gone through it.
- [ ] **Two merges where a service comes after its code**: a component added to a deployed project, and a new project whose login is not prepared when its code is proposed. The first proposal carries no deploy job for a service that does not exist yet; the run after its merge (for a new project, once the login is prepared) creates the service and proposes its deploy job; the second merge deploys. A new project whose login is prepared needs one merge ([section 12](#12-skills-of-the-aleogr-orchestrator)).
- [x] **A just-enabled IAP API that refuses the read of the login is waited for**: when `iap.googleapis.com` is among the enabled APIs and the login's read is refused because that API is off, `project-plan` ends `failed` with the item `services` instead of `waits for the login`, and `project-apply` waits for that plan by the same bounded wait as for any plan refused by just-enabled APIs. Proven in the scenarios only, not seen in a run.
- [ ] **A run that creates the GCP project creates no service**: no plan has read the login or the services of a project made seconds ago, so a new project with components needs one more `project-apply confirm=yes` after that run (which then creates the services and proposes the files).
- [ ] **One environment per deploy**: `github_ci-setup` accepts exactly one environment in `deploy`, because the four CI secrets are the repository's and two environments would clash; `hom` needs environment-scoped secrets or other names.
- [ ] **Existing CI secrets are `as declared` whatever they hold**: a secret's value cannot be read, so the plan compares names only. `project-apply` sets all four again when the GCP project, the registry or the CI identity was created or changed in the run; if that run is cut or refused after the first set, the next plan shows nothing and the old values stay until a deploy fails. It matters only when the values really change (a GCP project made anew), which nothing builds yet.
- [ ] **A repository transferred, or declared with another letter case, reads `ci identity` `differs`**, and the update writes a condition whose `assertion.repository` is the declared `<owner>/<name>` as written, which no token of GitHub matches (GitHub's token carries the repository's own name). It fails closed: nothing gets in, and nothing works either. Fix before 4b by comparing, and writing, the full name `github_repo-describe` returns.
- [ ] **`oidc.allowedAudiences` of the provider is not compared** by `gcp_ci-identity-setup`: a value set by hand on the provider is not reported, and a token must then carry that audience.
- [ ] **The harness pins the shape of a new project's id, not its identity**: the scenarios of a GCP project created in a run match `aleogr-dev-demo-[a-z0-9]{4}` in each command, so a run that used two different made-up ids would still pass. Proving that every command used the same id needs a harness check that compares captured values.
- [ ] **"Ask for it" wording remains** in one leaf skill, `gcp_budget-alert-setup`, which says to ask for a missing required argument, so the rule of [section 10.4](#104-behavior-of-every-skill) that a missing argument fails with one sentence does not hold for it yet (the orchestrators always pass every argument). Reword it as the other skills do: a missing argument fails with one sentence naming it, and nothing runs. The four instance skills of Cloud SQL were reworded in stage 4c.
- [ ] **The cleanup policy's deletions are not observed in a run**: Google applies the policy in a background job about once a day, so a run only reads back the two rules and dry-run off. Seeing the sixth version of an image deleted needs 4b's pushes and a day.
- [ ] **Changing the region or the root of an existing environment is not built**: `project-declare` writes neither change, a region changed by hand is reported for the image repository only (`in another region` / `fix by hand`, nothing else is compared with the region), and a changed root is not detected (the GCP project stays in the folder it was created in) ([section 11.6](#116-cloud-and-environments)).
- [ ] **Removing an environment's ground** (the GCP project, the image repository, the CI identity) is not built: stage 6, with the destructive-command hook ([section 13.1](#131-hooks)).
- [ ] **Some of `gcloud`'s answers in the stage 4a skills are still known only from its reference (`--help` of SDK 570) and the SDK's API definitions** ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)). The first real run exercised, with the skills deciding rightly: a repository, an account, a pool and a provider that do not exist, a binding refused right after its account's creation, and a cleanup policy read back as declared. Not yet met in a real run: a failed create that left a project, a repository in another region, permission denied on a read, what the list of a pool's providers prints when it holds another provider, and a disabled or deleted pool or provider.
- [ ] **A nested skill's result block printed before the plan's table, or a run that ends at one** (the form of the answer, [section 10.4](#104-behavior-of-every-skill)). Measured in stage 4b-1 on two scenarios that read the cloud, `project-plan-environment-as-declared` and `project-apply-environment-create`, 20 runs each: a nested block before the table in 13 of 40 runs before the change (5 of 20 and 8 of 20). On the final text of the stage: 1 of 40 (1 of 20 on the plan, 0 of 20 on the apply), and once more on the plan in a full run of the scenarios. Every invoked skill reads that its lines and block are the invoking skill's input, and every path of the orchestrators says, after its last invocation, that the next output is its own answer. The defect is reduced, not eliminated. A run that **ends** at a nested block was never reproduced in this stage (0 in every measurement), so that case is not proven fixed: it was seen earlier on another path, twice in the scenario of the wait for just-enabled APIs.
- [x] **`project-plan-ci-not-merged` failed 2 runs in 5** on the skills of stage 4b-1 (0 in 3 before): the plan gave `settings`, `visibility` and `protection` their compared states instead of `not checked until the change is merged` while the declaration is `changed here`. After the rule was restated in `project-plan` (outside the declaration's rules), it passed 10 runs in 10.
- [ ] **`project-apply-propose` fails 2 runs in 4** on the final text of stage 4b-1 (2 of 2 passed on the skills before the stage's form changes): `github_pull-request-open` found the folder still on `main` after `git switch -c` and stopped. Cause unknown; the fixture always answers `main` to a read of the branch, so a model that reads the branch once more than the skill lists also stops there.
- [ ] **`project-apply-visibility-public` fails some runs**, also before the stage's form changes (0 of 2 on the skills before them; on the final text it failed once in a full run and passed 2 of 3 reruns): the read after `gh repo edit` still says `private` and the run stops before the protection. Cause not established.
- [x] **`platform-apply` without `confirm=yes` sometimes ended at its question with no result block** (2 runs in 4 of `platform-apply-database-unconfirmed` in the last full run of stage 4b-1). It no longer asks: without `confirm=yes` it shows the plan and the cost line, changes nothing and ends `pending` with the item `confirm` and the command `/aleogr:platform-apply confirm=yes`. Its two unconfirmed scenarios pin that ending; they passed 2 runs in 2 each after the change.
- [x] **First real run of stage 4b-1** (2026-11-20, results in the checklist), following [`plans/2026-11-19-pilot-stage-4b-1-run.md`](plans/2026-11-19-pilot-stage-4b-1-run.md): the row `login` reads `prepared` on the owner's organization (prepared by hand during the spikes of 2026-11-19), a second Google account gets into a spike service after one command, and the spike is removed.
- [x] **Does an application in testing let a second Google account in?** Yes: in the run of stage 4b-1 a Google account created for the test, on no list of test users, reached the service's page after one `add-iam-policy-binding`, within about a minute. The owner reported Google's sign-in and no other screen; the page before the grant ("You don't have access") was not observed, and the absence of a warning rests on the owner's report, not on a capture.
- [ ] **The login's reads and refusals are known from the SDK, not from a real run**: what `gcloud iap settings get --organization` answers on an organization with no setting (an object with only `name`, an empty one, or `NOT_FOUND`: all three are read as not prepared), the exact permission names in its refusals (the skills decide on `PERMISSION_DENIED`, `SERVICE_DISABLED` and `NOT_FOUND` only), and whether `gcloud iap settings set` with a file that holds only `oauthSettings` replaces other settings stored on the organization. The owner's organization was set by hand during the spikes, so the first preparation from scratch by `gcp_login-setup` has not run.
- [ ] **The command that sets the login does not refuse empty answers**: pressing Enter at both of its prompts still calls `gcloud iap settings set` with an empty client id and secret, which may overwrite a working login. A guard in the command (stop when either answer is empty) is not there yet.
- [ ] **A just-enabled IAP API that still refuses the read is not waited for**: `gcp_login-setup` waits only for the new role to reach the read; when the API it has just enabled refuses, it ends telling the owner to wait a few minutes and run the plan again, one command more than the premise allows.
- [ ] **`platform-apply` does not wait for the APIs it enables**: `gcp_budget-alert-setup` runs right after `gcp_services-enable`, so on a fresh organization a just-enabled Budget API that still refuses ends the run `failed`, and the owner runs the same command again. The owner's platform exists, so this bites only a first installation; the wait of `project-apply` is the model when it is built.
- [ ] **The bounded wait has run only in the harness, headless** (Claude Code 2.1.328: a foreground `sleep` is refused before it runs, and the background wait goes on in the same turn, also with a real 30 seconds). In a real run, a wait in the background was seen only in Cloud Shell, once, in stage 4a (the run ended its turn during the wait and went on by itself). A poll of several waits in Cloud Shell, and any wait in the Windows app, are not seen yet, nor the permission prompt Claude Code shows for `sleep 30`.
- [ ] **Removing a component** is not built: `project-declare` cannot remove one, and a `ci.yml` left in the repository after the last component is removed from the declaration is not reported by `project-plan` (`github_ci-setup` alone reports a local `ci.yml` with no component as `pending`, to remove by hand). The component's folder is never deleted by the tooling.
- [ ] **Versions of the reusable workflows in projects:** the tags `workflows-v1` are not used yet (a project's `ci.yml` pins `ci-go.yml` and `deploy-cloud-run.yml` at one commit SHA, kept when the file is regenerated), and nothing moves that pin or the actions' pins of a project's `ci.yml` (`github_ci-setup ref=latest` moves the first by hand; the second are fixed in the text of `github_ci-setup`, where Dependabot does not see them). Decide with a release step for this repository: tags, Dependabot or Renovate in projects, or a regenerated `ci.yml`.
- [ ] `ci-go.yml` has a fixed limit of 15 minutes per component job: make it an input when a component needs longer.
- [ ] Start the first real project (an identity provider, [section 17](#17-implementation-strategy)) once the reference project `pilot` has gone through the stages there.
- [ ] **First real run of stage 4c**, following [`plans/2026-11-26-pilot-stage-4c-run.md`](plans/2026-11-26-pilot-stage-4c-run.md). Nothing of this stage has run against real Google Cloud: its commands and answers are known from the `gcloud` reference (`--help` of SDK 570), the SDK's source, Google's documentation and the connector's source ([`PROVIDER-FACTS.md`](PROVIDER-FACTS.md)), and the skills from the scenarios. The run must prove:
  - what the Cloud SQL Admin API answers to the database and user commands on a stopped and on a starting instance (the skills never send them unless the instance reads as running, and decide by its state; whether a starting instance refuses them, and how, is not documented);
  - that the connector reaches the instance across two projects, with the Cloud SQL Admin API enabled in both (Google's pages say both; the connector's README names only the caller's);
  - that a service account's database user with no database role runs `SELECT 1` in its database;
  - that the check answers its sentence `database: not reachable (the shared instance may be stopped)` within its 5-second deadline when the instance is stopped (what the connector meets on a stopped instance is not documented);
  - that the Go command in Cloud Shell downloads the toolchain the module declares, and that `go get` of the pinned modules leaves the `go` line as declared or with `.0` (seen for real on a local machine only);
  - that the settings' update (`--update-env-vars` alone) keeps the service's image (Google's page implies it, no sentence states it);
  - the start's duration against the 15-minute wait (measured at 11.5 and about 9 minutes before).
  - that the read of the night stop that `project-apply` makes right before the start (`gcp-cloud-sql_instance-switch-setup … mode=plan`, as the owner's account) says the switch is ready, as `/aleogr:platform-plan` does;
  - how often a read fails while the instance starts (a failed read counts as a try of the wait, so it no longer stops the run; how often it happens is not known);
  - that one turn holding up to four full plans and up to 30 nested reads of the database keeps the prescribed sentences and ends with its own result block (no scenario runs that whole composition);
  - that the real outputs of `gcloud sql databases list`, `gcloud sql users list` and `gcloud run services describe` have the shapes the skills read (a settings' shape that differs would show `differs: settings` after every write);
  - that Claude Code in Cloud Shell runs `go_setup`'s comparison `cmp … <(sed …)` with no prompt beyond those the checklist lists;
  - that the shared instance has IAM database authentication on (`cloudsql.iam_authentication`), which no skill reads back: the checklist reads it before the first run.
- [ ] **Inside the shared instance, a project's database user can connect to another project's database.** PostgreSQL grants `CONNECT` on every database to `PUBLIC` unless a statement revokes it, and no command of the tooling runs SQL. By Google's documentation a service account's user gets no database role by default (the administrative role goes only to built-in users), so connecting is all it can do, and with no table anywhere this exposes nothing. It must be closed in the stage that creates the first table (with migrations, which need a way to run SQL anyway).
- [ ] **A component's user can create nothing in its own database yet** (no role, no grant on the schema `public`): the same stage gives it what it needs.
- [ ] **The two connection roles are on the shared project without a condition**: they let a project's account connect to, and log in to, any instance of the shared project (it holds one). Narrowing them by an IAM condition to the one instance is not tested; Google documents a condition only for `roles/cloudsql.client`.
- [ ] **A role held under any condition counts as held**: when such a condition does not cover the shared instance, the connection is refused and the plan does not see it (the check `/db` does).
- [ ] **A `main.go` changed by hand leaves the route to the owner**: the plan shows the line to add and the item `route`, and still says `nothing to do` for the tooling's part, while `GET /db` does not exist and the tests of `db_test.go` fail.
- [ ] **A long wait in a terminal that can expire**: the run that starts the instance waits about twelve minutes, and its answer is lost if the Cloud Shell session drops (as in the run of stage 4b-2). After reconnecting, `project-apply confirm=yes` again finds the instance starting and waits by itself, or finds it running and makes what is missing; the first run's own sentences, its start's sentence included, are not shown again.
- [ ] **A confirmed run given without an earlier plan can start the instance with no notice before it**: a role removed by hand, or a declaration with the database merged without the tooling's proposal (so without its warning), then a direct `project-apply confirm=yes`: the plan inside the run reads the instance stopped and the run starts it, and the owner reads the cost line and the start's sentence only in that run's answer. Accepted: cents, bounded by the night stop, which the run reads first.
- [ ] **A role removed by hand on a stopped instance starts it** for about twelve minutes, to grant a role that itself needs no running instance: with the user made first, a missing role means the user is not known. Accepted.
- [ ] **The rights on the shared project are first tried after the start**: nothing reads beforehand whether the active account may create a database user on the instance and change the shared project's policy, so a run that lacks them starts the instance, waits, and stops at the database or the grant, the instance running until the night stop.
- [ ] **The night stop is read as set up, not as working**: the switch's read says ready when its parts exist and match; a job whose last run failed still counts as ready (the platform's plan has a line for it), so a run can start the instance after a night stop that failed.
- [ ] **Taking the database away removes nothing**: `project-declare component=<c> database=no` removes the key only. The component's database user, its two roles on the shared project, the three settings of its service, the project's Cloud SQL Admin API, the database and the check's code stay, and no plan shows them (without a database component there is no row `database`). Removing them comes with `database-remove`.
- [ ] **No skill reads the instance's IAM database authentication back**: `gcp-cloud-sql_instance-create` creates the instance with `cloudsql.iam_authentication` on; a flag turned off by hand is not seen by any plan, and the connection is refused (the check `/db` says `not reachable`).
- [x] **A shared platform without its instance** (the instance is created by `platform-apply` under its own confirmation, so the shared project can exist, with its API on, and no instance): the plan reads the instance once more after a failed read, and an instance that does not exist is `needs the shared platform`; a read that fails for another reason fails the plan with a sentence that names no project id.
- [ ] **Each request to `/db` builds a dialer**, whose calls count against the Cloud SQL Admin API's quota of the project's own GCP project: behind the login, with at most two instances, a signed-in person could exhaust that quota and nothing else. A dialer kept between requests comes when a component uses the database for real.
- [ ] **A database or a user deleted by hand is not seen while the instance is stopped**: the settings and the roles are the marker, and the database and the users are read only while the instance runs.
- [ ] **Nothing validates the schema's examples in CI**: the schemas README said that `self-validate-marketplace.yml` validates them on every pull request, but that workflow does not exist (corrected in stage 4c). The examples were validated by hand with a JSON Schema validator when the schema last changed; the check comes with `marketplace-validate` ([section 12.1](#121-what-marketplace-validate-checks)).
