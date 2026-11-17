# Lab Platform, Stage 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first slice of the marketplace: the skills that create the free part of the lab platform on GCP (the shared project, with billing linked, and the budget alert).

**Architecture:** Two Claude Code plugins in `marketplace/`. The orchestrator `aleogr` reads the owner's choices from a `defaults.json` inside the plugin and calls the family skills of `aleogr-cloud-gcp`, which run `gcloud`. Identifiers (organization, folder, billing account, project ID) are never stored: every skill discovers them with `gcloud`. Skills are tested headless against a fake `gcloud` that records every call, so nothing is created outside the repository.

**Tech Stack:** Claude Code plugins (Markdown skills, JSON manifests), `gcloud` CLI, Bash for the test harness.

**Spec:** [`docs/DESIGN.md`](../DESIGN.md) (sections 1, 2, 6.5, 6.7, 6.8, 7, 10, 12) and [`docs/CONTRACTS.md`](../CONTRACTS.md) (section 1 and cloud-*). Provider behaviour: [`docs/PROVIDER-FACTS.md`](../PROVIDER-FACTS.md).

## Global Constraints

- Everything versioned is in English.
- Skill folder names: family skills `<provider>_<object>-<verb>` (one underscore), orchestrator skills `<object>-<verb>`. No `name:` in any `SKILL.md` frontmatter. The `description` names the provider and says when to use the skill.
- `marketplace.json` entry `name` equals the `plugin.json` `name`; every entry has `category` and `displayName`. No `dependencies` between the orchestrator and family plugins.
- Plugin `source` paths are relative to `marketplace/` and start with `./`, without `..`.
- The repository is public: no organization ID, folder ID, billing account ID, project ID, e-mail or secret in any file. Test fixtures use fictitious values.
- GCP project ID: `aleogr-<environment>-<project>-<random>`, `<random>` = 4 characters of `a-z0-9`; at most 30 characters, so a project name has at most 14.
- Labels on every created project: `aleogr-project=<project>`, `aleogr-environment=<environment>`; the shared project also `aleogr-platform=lab`.
- Every skill: checks before creating (idempotent), shows each command before running it, stops for confirmation before anything with a fixed cost, ends with a verification and with one fenced `aleogr-result` JSON block (CONTRACTS.md section 1.4).
- Modes: `plan` reports what would change and changes nothing; `apply` executes. Default is `plan`.
- Do not create plugin folders, skills, workflows or Features beyond the ones listed here.

## Decisions this plan makes (for the owner to confirm)

1. `defaults.json` lives inside the orchestrator plugin (`marketplace/plugins/aleogr/defaults.json`), not in `marketplace/`: an installed plugin is a copy of its own folder and cannot read files outside it. `DESIGN.md` is updated accordingly.
2. New orchestrator skills `platform-plan` and `platform-apply`; `project-plan`/`project-apply` come with the first real project.
3. Skill tests against fake CLIs live in `marketplace/tests/`. This is a new kind of test for the design (section 15.1 lists only static checks): it runs the real skills headless, creates nothing outside, and is run by hand for now, not by a workflow.
4. Budget alert: R$ 100 per month on the whole billing account, alerts at 50%, 90% and 100%. The amount is a value in `defaults.json`.
5. The destructive command guard hook is left for stage 2 (stage 1 only creates free resources).

## Review Focus

- More than one organization, more than one open billing account, or more than one folder named `lab`: the skill must stop and ask which one, never pick the first.
- The shared project already exists (second run, or created by hand): `apply` must report `unchanged` and create nothing.
- `gcloud` missing or not authenticated: `tools-check` and every family skill must say so in one sentence, not fail with a raw error.
- A project name longer than 14 characters, or the reserved names `test`/`shared` used for a real project: refused before any command runs.
- Billing link refused (no permission on the billing account): the project exists but is unusable; the skill must report `pending` with the command to run, not `created`.

## File Structure

```
marketplace/
├── .claude-plugin/marketplace.json            catalog: aleogr, aleogr-cloud-gcp
├── plugins/
│   ├── aleogr/
│   │   ├── .claude-plugin/plugin.json
│   │   ├── defaults.json                      owner's choices, no identifiers
│   │   └── skills/
│   │       ├── tools-check/SKILL.md           CLIs installed and authenticated
│   │       ├── platform-plan/SKILL.md         compares defaults × cloud, changes nothing
│   │       └── platform-apply/SKILL.md        creates what platform-plan lists
│   └── aleogr-cloud-gcp/
│       ├── .claude-plugin/plugin.json
│       └── skills/
│           ├── gcp_environment-describe/SKILL.md
│           ├── gcp_environment-create/SKILL.md
│           ├── gcp_services-enable/SKILL.md
│           └── gcp_budget-alert-setup/SKILL.md
└── tests/
    ├── README.md
    ├── bin/gcloud                             fake: logs argv, prints the scenario's canned output
    ├── run.sh                                 runs one scenario headless and checks the call log
    └── scenarios/<name>/                      prompt.txt, responses/, expect.txt
```

## Shared interfaces

**Skill arguments** (free text after the skill name, `key=value` pairs): `mode=plan|apply` (default `plan`), `project=<name>`, `environment=lab|hom|prd`. Platform skills take only `mode`.

**Discovery commands** (used by every `aleogr-cloud-gcp` skill; never stored):

| What | Command | More than one result |
|---|---|---|
| Organization | `gcloud organizations list --format="value(name)"` | stop and ask |
| Folder of an environment | `gcloud resource-manager folders list --organization=<id> --filter="displayName=<environment>" --format="value(name)"` | stop and ask |
| Billing account | `gcloud billing accounts list --filter="open=true" --format="value(name)"` | stop and ask |
| A project's environment | `gcloud projects list --filter="labels.aleogr-project=<project> AND labels.aleogr-environment=<environment>" --format="value(projectId)"` | stop and report |

**`defaults.json`** (Task 1):

```json
{
  "version": 1,
  "cloud": { "provider": "gcp", "region": "us-central1" },
  "lab": { "domain": "lab.aleogr.dev" },
  "platform": {
    "shared": { "project": "shared", "environment": "lab", "services": ["cloudresourcemanager.googleapis.com", "billingbudgets.googleapis.com"] },
    "budget": { "displayName": "aleogr-lab", "amount": 100, "currency": "BRL", "thresholds": [0.5, 0.9, 1.0] }
  }
}
```

**Test harness** (Task 2): `marketplace/tests/run.sh <scenario>` exits 0 when every line of `expect.txt` holds. `expect.txt` lines: `CALLED <regex>` (some logged `gcloud` call matches), `NOT_CALLED <regex>` (none matches), `OUTPUT <regex>` (Claude's final answer matches).

---

### Task 1: Catalog, orchestrator manifest and defaults

**Files:**
- Create: `marketplace/.claude-plugin/marketplace.json`, `marketplace/plugins/aleogr/.claude-plugin/plugin.json`, `marketplace/plugins/aleogr/defaults.json`, `marketplace/plugins/aleogr-cloud-gcp/.claude-plugin/plugin.json`
- Modify: `docs/DESIGN.md` (sections 2 tree, 2.2, 6.6, 7, 18), `marketplace/README.md`

**Interfaces:**
- Produces: marketplace `aleogr`; plugins `aleogr` (category `orchestrator`, displayName "aleogr (orchestrator)") and `aleogr-cloud-gcp` (category `cloud`, displayName "Google Cloud (cloud)"); `defaults.json` as in Shared interfaces, referenced by skills as `${CLAUDE_PLUGIN_ROOT}/defaults.json`.

- [ ] **Step 1:** Run `claude plugin validate ./marketplace`. Expected: fails, no marketplace file.
- [ ] **Step 2:** Write the four files. `marketplace.json`: `name` `aleogr`, `owner.name` `aleogr`, a `description`, two entries with `source` `./plugins/aleogr` and `./plugins/aleogr-cloud-gcp`. Each `plugin.json`: `name`, `version` `0.1.0`, `description`, `author.name` `aleogr`. No `license` field: no license decision exists yet.
- [ ] **Step 3:** Run `claude plugin validate ./marketplace`. Expected: `Validation passed` (warnings about plugin directory listing are acceptable; unknown-field warnings are not).
- [ ] **Step 4:** Update `DESIGN.md`: `defaults.json` moves to `marketplace/plugins/aleogr/defaults.json` (tree, section 6.6, section 7); section 12 lists `platform-plan`/`platform-apply`; section 18 closes the item about reading files outside the plugin folder (answer: it cannot; `contracts.json` will live in the orchestrator plugin too). Update `marketplace/README.md` to match.
- [ ] **Step 5:** Commit: `feat: add the marketplace catalog and the orchestrator manifest`.

### Task 2: Skill test harness with a fake gcloud

**Files:**
- Create: `marketplace/tests/bin/gcloud`, `marketplace/tests/run.sh`, `marketplace/tests/README.md`, `marketplace/tests/scenarios/harness-selftest/{prompt.txt,expect.txt,responses/default.txt}`
- Modify: `docs/DESIGN.md` (section 15.1: add this kind of test)

**Interfaces:**
- Produces: `run.sh <scenario>` as in Shared interfaces. The fake `gcloud` appends its arguments as one line to `$FAKE_LOG`, then prints the first file in `$FAKE_RESPONSES` whose name (with `_` for spaces, e.g. `projects_list.txt`) is a prefix of the arguments, else `default.txt`, else nothing; a response file ending in `.exit1` makes it exit 1 after printing.
- `run.sh` runs `claude -p "$(cat prompt.txt)" --plugin-dir marketplace/plugins/aleogr --plugin-dir marketplace/plugins/aleogr-cloud-gcp --allowedTools Bash Skill Read` from an empty temporary directory, with `marketplace/tests/bin` first on `PATH`, and prints which `expect.txt` lines failed.

- [ ] **Step 1:** Write the `harness-selftest` scenario: prompt asks Claude to run `gcloud projects list`; `expect.txt` has `CALLED ^projects list` and `NOT_CALLED ^projects create`.
- [ ] **Step 2:** Run `bash marketplace/tests/run.sh harness-selftest`. Expected: fails, `run.sh` does not exist.
- [ ] **Step 3:** Write `bin/gcloud` and `run.sh`.
- [ ] **Step 4:** Run the scenario. Expected: exit 0. Then change `expect.txt` to `CALLED ^projects create`, run again, expect a non-zero exit naming that line, and restore it.
- [ ] **Step 5:** Write `README.md` (what the harness is, how to add a scenario, that it needs an authenticated `claude` CLI and costs model usage) and the paragraph in `DESIGN.md` section 15.1.
- [ ] **Step 6:** Commit: `test: add a headless skill test harness with a fake gcloud`.

### Task 3: `gcp_environment-describe`

**Files:**
- Create: `marketplace/plugins/aleogr-cloud-gcp/skills/gcp_environment-describe/SKILL.md`
- Test: `marketplace/tests/scenarios/describe-missing/`, `marketplace/tests/scenarios/describe-existing/`

**Interfaces:**
- Consumes: discovery commands.
- Produces: read-only skill. `aleogr-result` with `status` `unchanged`, `outputs`: `exists` (boolean), `projectId`, `folder`, `billingLinked` (boolean), `enabledServices` (list), `labels`. Uses `gcloud projects describe`, `gcloud billing projects describe <id>`, `gcloud services list --enabled --project=<id>`.

- [ ] **Step 1:** Write both scenarios. `describe-missing`: `projects list` returns nothing; expect `OUTPUT "exists": false` and `NOT_CALLED ^projects create`. `describe-existing`: canned output for a fictitious `aleogr-lab-shared-zz99`; expect `OUTPUT aleogr-lab-shared-zz99`, `OUTPUT "billingLinked": true`, `CALLED ^services list`.
- [ ] **Step 2:** Run both. Expected: fail (skill not found).
- [ ] **Step 3:** Write the skill: frontmatter `description` only; body = purpose, arguments, the discovery and describe commands, the "more than one" rule, the result block.
- [ ] **Step 4:** Run both scenarios. Expected: exit 0. Run `claude plugin validate ./marketplace`.
- [ ] **Step 5:** Commit: `feat: add gcp_environment-describe`.

### Task 4: `gcp_environment-create`

**Files:**
- Create: `marketplace/plugins/aleogr-cloud-gcp/skills/gcp_environment-create/SKILL.md`
- Test: scenarios `create-plan`, `create-apply`, `create-existing`, `create-ambiguous-billing`, `create-name-too-long`, `create-billing-refused`

**Interfaces:**
- Consumes: discovery commands; the describe logic of Task 3 (the skill tells Claude to run `gcp_environment-describe` first).
- Produces: in `apply`, `gcloud projects create aleogr-<environment>-<project>-<random> --folder=<id> --name="<environment> <project>" --labels=...` then `gcloud billing projects link <id> --billing-account=<id>`; verification by `gcloud projects describe`. `status`: `would-create` (plan), `created`, `unchanged` (already exists), `pending` (created but billing not linked, with the command in `pending[].how`). `outputs.projectId`. `cost.fixed` false.

- [ ] **Step 1:** Write the six scenarios with their expectations: plan → `NOT_CALLED ^projects create`, `OUTPUT would-create`; apply → `CALLED ^projects create aleogr-lab-shared-[a-z0-9]{4} .*--folder=`, `CALLED ^billing projects link`, `OUTPUT "status": "created"`; existing → `NOT_CALLED ^projects create`, `OUTPUT unchanged`; ambiguous billing (two open accounts) → `NOT_CALLED ^projects create` and the answer asks which account; name too long (`project=averyveryverylongname`) → no `gcloud` call at all; billing refused (`billing_projects_link.exit1`) → `OUTPUT "status": "pending"`.
- [ ] **Step 2:** Run them. Expected: fail.
- [ ] **Step 3:** Write the skill, including the validation of the project name (length, `test`/`shared` reserved unless the caller is the platform), the random suffix, and the labels from Global Constraints.
- [ ] **Step 4:** Run all scenarios of Tasks 3 and 4. Expected: exit 0.
- [ ] **Step 5:** Commit: `feat: add gcp_environment-create`.

### Task 5: `gcp_services-enable`

**Files:**
- Create: `marketplace/plugins/aleogr-cloud-gcp/skills/gcp_services-enable/SKILL.md`
- Test: scenarios `services-plan`, `services-apply-partial`

**Interfaces:**
- Produces: arguments `project=`, `environment=`, `services=<comma list>`. Compares with `gcloud services list --enabled`; in `apply` runs one `gcloud services enable <missing...> --project=<id>` with only the missing ones. `status`: `would-update`, `updated`, `unchanged`.

- [ ] **Step 1:** Write the scenarios: partial (one of two already enabled) → `CALLED ^services enable billingbudgets.googleapis.com --project=` and `NOT_CALLED ^services enable .*cloudresourcemanager`.
- [ ] **Step 2:** Run. Expected: fail.
- [ ] **Step 3:** Write the skill.
- [ ] **Step 4:** Run. Expected: exit 0.
- [ ] **Step 5:** Commit: `feat: add gcp_services-enable`.

### Task 6: `gcp_budget-alert-setup`

**Files:**
- Create: `marketplace/plugins/aleogr-cloud-gcp/skills/gcp_budget-alert-setup/SKILL.md`
- Test: scenarios `budget-plan`, `budget-apply`, `budget-existing`

**Interfaces:**
- Produces: arguments `displayName=`, `amount=`, `currency=`, `thresholds=`, `quotaProject=<project id>`. Lists with `gcloud billing budgets list --billing-account=<id> --billing-project=<quotaProject>`; in `apply` creates with `gcloud billing budgets create --billing-account=<id> --display-name=<name> --budget-amount=<amount><currency> --threshold-rule=percent=<t>` (one rule per threshold) `--billing-project=<quotaProject>`. Matches an existing budget by display name. `status`: `would-create`, `created`, `unchanged`. `cost.fixed` false.

- [ ] **Step 1:** Write the scenarios: apply → `CALLED ^billing budgets create .*--budget-amount=100BRL .*--threshold-rule=percent=0.5`; existing → `NOT_CALLED ^billing budgets create`.
- [ ] **Step 2:** Run. Expected: fail.
- [ ] **Step 3:** Write the skill. State in the skill that the budget commands need the Budget API enabled on the quota project, and that this is unverified against real GCP until the first real run.
- [ ] **Step 4:** Run. Expected: exit 0.
- [ ] **Step 5:** Commit: `feat: add gcp_budget-alert-setup`.

### Task 7: `tools-check`

**Files:**
- Create: `marketplace/plugins/aleogr/skills/tools-check/SKILL.md`
- Test: scenarios `tools-ok`, `tools-not-authenticated`

**Interfaces:**
- Produces: read-only. Checks `gcloud --version`, `gcloud auth list --filter=status:ACTIVE --format="value(account)"`, and where it runs (`CLAUDE_CODE_REMOTE`, `CODESPACES`). Answers with one line per tool: ok, missing or not authenticated, and what cannot be done here. Never prints the account e-mail in the `aleogr-result` block.

- [ ] **Step 1:** Write the scenarios: not authenticated (`auth list` returns nothing) → `OUTPUT not authenticated` and `OUTPUT gcloud auth login`.
- [ ] **Step 2:** Run. Expected: fail.
- [ ] **Step 3:** Write the skill.
- [ ] **Step 4:** Run. Expected: exit 0.
- [ ] **Step 5:** Commit: `feat: add tools-check`.

### Task 8: `platform-plan` and `platform-apply`

**Files:**
- Create: `marketplace/plugins/aleogr/skills/platform-plan/SKILL.md`, `marketplace/plugins/aleogr/skills/platform-apply/SKILL.md`
- Test: scenarios `platform-plan-empty`, `platform-apply-empty`, `platform-apply-done`

**Interfaces:**
- Consumes: `${CLAUDE_PLUGIN_ROOT}/defaults.json`; the skills of Tasks 3 to 7, invoked as `aleogr-cloud-gcp:<skill>`.
- Produces: `platform-plan` runs `tools-check`, then `gcp_environment-describe` for the shared environment and the budget listing, and prints a table: item, current state, action. `platform-apply` runs the same plan, asks for one confirmation, then in order: `gcp_environment-create` (project `shared`, environment `lab`, label `aleogr-platform=lab`), `gcp_services-enable`, `gcp_budget-alert-setup`; ends by running `platform-plan` again, which must say "nothing to do". If the provider in `defaults.json` is not `gcp`, it stops and says only GCP is implemented.

- [ ] **Step 1:** Write the scenarios: plan-empty → no create call, the answer lists the three items as to create; apply-empty (prompt includes the confirmation) → project create, services enable and budget create called, in that order; apply-done → no create call and `OUTPUT nothing to do`.
- [ ] **Step 2:** Run. Expected: fail.
- [ ] **Step 3:** Write both skills.
- [ ] **Step 4:** Run every scenario in `marketplace/tests/scenarios/`. Expected: all exit 0. Run `claude plugin validate ./marketplace`.
- [ ] **Step 5:** Commit: `feat: add platform-plan and platform-apply`.

### Task 9: Documentation and hand-off

**Files:**
- Modify: `docs/DESIGN.md` (section 2 tree marks what now exists; section 18), `docs/CONTRACTS.md` (cloud-* table if an input or output changed while implementing), `marketplace/plugins/README.md`
- Create: `docs/plans/2026-11-16-shared-platform-stage-1-run.md` (the owner's checklist for the first real run)

- [ ] **Step 1:** Update the docs to what was built; remove nothing that is still planned.
- [ ] **Step 2:** Write the run checklist: register the marketplace in the Windows app (`extraKnownMarketplaces` block of DESIGN.md section 2.3, with `"ref": "<branch>"` before the merge), enable `aleogr@aleogr` and `aleogr-cloud-gcp@aleogr`, run `/aleogr:tools-check`, `/aleogr:platform-plan`, `/aleogr:platform-apply`, and what to send back (the final plan output and any error).
- [ ] **Step 3:** Run `claude plugin validate ./marketplace` and every scenario one last time. Expected: all pass.
- [ ] **Step 4:** Commit: `docs: record stage 1 of the lab platform and the first-run checklist`. Push the branch.

## Not verified by this plan

The fake `gcloud` proves which commands the skills run and in which order, not that Google accepts them. The first real run, by the owner in the Windows app, is the actual verification of: the exact flags of `gcloud billing budgets`, the need for a quota project, the folder filter syntax, and the registration of the marketplace through `extraKnownMarketplaces` with `path`. Whatever it shows becomes a fix here and, when it is provider behaviour, a line in `PROVIDER-FACTS.md`.
