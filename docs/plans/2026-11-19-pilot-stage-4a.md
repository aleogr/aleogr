# Reference project, stage 4a: the ground in `dev` — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A project that declares the environment `dev` gets from `project-apply` its own GCP project, its APIs, an image repository with a cleanup policy, and a keyless CI identity that only its repository's default branch can use and that can only push images.

**Architecture:** The declaration gains `cloud` and `environments`. `aleogr-cloud-gcp` gains `gcp_ci-identity-setup`; a new plugin `aleogr-registry-gcp-artifact-registry` has four skills. `project-plan` gains four rows after `protection`, read only when the declaration is merged; `project-apply` makes them in order with the existing skills `gcp_environment-create` and `gcp_services-enable`. Nothing is deployed and nothing reaches GitHub but the declaration.

**Tech Stack:** Claude Code plugin skills (Markdown), `gcloud`, `gh`, JSON Schema, the bash harness under `.claude-plugin/tests/` (fake `gcloud`, `gh`, `git`).

**Spec:** [`2026-11-19-pilot-stage-4-design.md`](2026-11-19-pilot-stage-4-design.md), "Part 4a: the ground". Models of style: `aleogr-cloud-gcp/skills/gcp_services-enable`, `aleogr-db-gcp-cloud-sql/skills/gcp-cloud-sql_instance-switch-setup` (workload identity federation, the single retry, a shipped file passed to `gcloud`), `aleogr/skills/project-plan` and `project-apply`.

## Global Constraints

- Everything versioned is in English. The repository is public: no organization, folder, billing account or project identifier, no e-mail, no secret. Fixtures use only: project `demo`, GCP project id `aleogr-dev-demo-ab12`, project number `123456789012`, region `us-central1`, repository `example-org/example-repo` with id `7654321`, owner id `2345678`, default branch `main`. `aleogr-sandbox` and `pilot` appear only under `docs/`.
- No `SKILL.md` has `name:` in its frontmatter; the folder is the name. Every skill validates before any command, shows each command before running it, runs only the commands (or invokes only the skills) its steps list, never waits for an answer, and ends with exactly one fenced `aleogr-result` block. Status `pending` means nothing was changed; once something was done the status says what (`created`, `updated`) and leftovers are items `{item, reason, how}` in `pending`.
- A command whose result decides a step is run alone; each decision names the identifying text as well as the exit code; raw error text is never quoted. Use the wording the existing GCP skills use for this.
- The orchestrator skills run no `gcloud`, `gh` or `git` command; they invoke skills.
- The declaration: `cloud` is `{ "provider": "gcp", "region": "<region>", "root": "tst" }`, `root` optional and only `tst`; `environments` is `{ "dev": {} }`, the only allowed key `dev`, its value an empty object. Both optional, after `components`, before `notes`. `environments` requires `cloud`.
- A declaration without `environments` behaves exactly as before this plan: not one more command, row or status (additive result keys aside). Every existing `project-*` scenario passes unchanged.
- Names: GCP project id `aleogr-dev-<project>-<random>` (existing skill); image repository id `<project>`, format Docker, in `cloud.region`, labels `aleogr-project=<project>` and `aleogr-environment=<environment>`; image path prefix `<region>-docker.pkg.dev/<projectId>/<project>`; CI service account `<project>-ci`; workload identity pool `github`, provider `github`, location `global`.
- The provider's condition is exactly `assertion.repository=='<owner>/<name>' && assertion.repository_id=='<repositoryId>' && assertion.repository_owner_id=='<ownerId>' && assertion.ref=='refs/heads/<branch>'`.
- The CI identity's only role in this plan is `roles/artifactregistry.writer`, on the one repository, never on the project.
- The cleanup policy is two rules: keep the `<keep>` most recent versions of each image; delete every other version. Dry-run is off. `keep` is `project.registry.keep` of `defaults.json` (5).
- Project APIs are `project.services` of `defaults.json`: `cloudresourcemanager.googleapis.com`, `artifactregistry.googleapis.com`, `iam.googleapis.com`, `iamcredentials.googleapis.com`, `sts.googleapis.com`.
- Nothing has a fixed cost: no confirmation of cost. `confirm=yes` confirms the plan.
- No service account key, ever. No skill creates a folder. No skill deploys or builds an image. No identifier is written to GitHub.
- "The declaration's rules" stay byte-identical in `project-declare` and `project-plan`: Task 1 changes the section in both, in the same commit, and proves it with a diff.
- Every `gcloud` command a skill issues is checked by its implementer against the current `gcloud` reference (`gcloud <group> --help` output or the public reference page) before it is written; a flag that could not be checked is listed in the task's report. What surprises goes to `docs/PROVIDER-FACTS.md` in Task 7.
- Do not change the root `README.md`; never create `.github/README.md`; no skill, plugin or workflow beyond this plan. `docs/DESIGN.md` states decisions in the present tense; its section 16 gets no entry.
- Commit messages end with the line the session gives; no model name anywhere. `.superpowers/` is never committed.
- Scenarios: `bash .claude-plugin/tests/run.sh <scenario>`; four at a time, two at a time for `project-apply-*`. Each run costs model usage. A thing that does not exist answers with an error and exit 1; expectations pin content (the command with its decisive flags), not only a status; failure scenarios pin a word of the sentence the skill prescribes.

## Review Focus

1. A declaration without `environments` must not touch the cloud. Tests: `project-plan-nothing-to-do` and `project-apply-nothing-to-do` gain `NOT_CALLED ^gcloud` (Tasks 5, 6); every existing `project-*` scenario passes unchanged.
2. The GCP project does not exist yet, or its folder is missing: nothing inside it is read, and the run says what the owner must do. Tests: `project-plan-environment-missing` (Task 5), `project-apply-environment-folder-missing` (Task 6).
3. An API is not enabled yet: no `gcloud artifacts` or `gcloud iam` command runs. Tests: `project-plan-environment-apis` (Task 5).
4. A provider that already exists with a condition for another repository or branch must end accepting only the declared one. Tests: `ci-identity-differs-plan`, `ci-identity-differs-apply` (Task 2), pinning the whole condition in the update command.
5. A cleanup policy left in dry-run deletes nothing: it reads as different. Test: `registry-cleanup-dry-run` (Task 4).
6. A binding refused right after the account is created is retried once, and a second refusal stops with what was created reported. Tests: `ci-identity-apply-retry` (Task 2), `registry-access-retry` (Task 4).
7. `gcloud` is not signed in although `gh` is: the plan fails before any row is read. Test: `project-plan-environment-no-gcloud` (Task 5).

---

## File map

| Path | Responsibility |
|---|---|
| `.claude-plugin/schemas/project.schema.json`, `examples/with-environment.json`, `schemas/README.md` | `cloud`, `environments` |
| `.claude-plugin/plugins/aleogr/defaults.json` | `project.services`, `project.registry.keep` |
| `.claude-plugin/plugins/aleogr/skills/project-declare`, `project-plan`, `project-apply` | the environment; four rows; the ground |
| `.claude-plugin/plugins/aleogr-cloud-gcp/skills/gcp_ci-identity-setup/SKILL.md` | the CI identity |
| `.claude-plugin/plugins/aleogr-repo-github/skills/github_repo-describe/SKILL.md` | outputs `id`, `ownerId` |
| `.claude-plugin/plugins/aleogr-registry-gcp-artifact-registry/` (`plugin.json`, four skills, `files/cleanup-policy.json`) | the image repository |
| `.claude-plugin/marketplace.json`, `plugin.json` files, `tests/run.sh`, `tests/README.md` | catalog, versions, the new plugin in the tests |
| `docs/…`, `docs/plans/2026-11-19-pilot-stage-4a-run.md` | documents |

Tasks 1, 2 and 3 touch disjoint paths and can run in parallel. Task 4 follows 3; Task 5 follows 1 to 4; then 6, then 7.

---

### Task 1: `cloud` and `environments` in the declaration

**Files:**
- Modify: `.claude-plugin/schemas/project.schema.json`, `.claude-plugin/schemas/README.md`, `.claude-plugin/plugins/aleogr/defaults.json`, `.claude-plugin/plugins/aleogr/skills/project-declare/SKILL.md`, `.claude-plugin/plugins/aleogr/skills/project-plan/SKILL.md` (only "The declaration's rules")
- Create: `.claude-plugin/schemas/examples/with-environment.json`
- Test: scenarios `project-declare-environment-*`

**Interfaces:**
- Produces: the declaration keys of Global Constraints; `defaults.json` keys `project.services` (the five APIs, in the order above) and `project.registry.keep` (`5`); `project-declare` arguments `environment=dev` and `cloudRoot=tst`; `outputs.changes` entries `environments.dev`, `cloud`, `cloud.root`.

- [ ] **Step 1: Scenarios first.** Seed from the existing `project-declare-*` fixtures (a declaration with components).
  - `project-declare-environment-add`: `environment=dev` → `"status": "updated"`; `FILE` pins `"environments": { "dev": {} }` and `"cloud": { "provider": "gcp", "region": "us-central1" }`; changes hold `environments.dev` and `cloud`; `NOT_CALLED .`
  - `project-declare-environment-root`: `environment=dev cloudRoot=tst` → the file has `"root": "tst"`.
  - `project-declare-environment-unchanged`: seeded with both keys, `environment=dev` → `"status": "unchanged"`.
  - `project-declare-environment-unknown`: `environment=hom` → `"status": "failed"`, file unchanged, `OUTPUT` a word of the prescribed sentence.
  - `project-declare-cloudroot-alone`: `cloudRoot=tst` on a declaration without `cloud` → `failed`, pinned sentence.
  - `project-declare-cloudroot-invalid`: `environment=dev cloudRoot=prod` → `failed`.
  - `project-declare-environment-keeps`: an unrelated edit (`description=`) on a declaration with both keys keeps them, in the canonical order.
- [ ] **Step 2: Run them; they fail** (the first four at least; say which already pass and why).
- [ ] **Step 3: Schema, example, README, defaults.** `cloud` and `environments` as in Global Constraints, `additionalProperties: false` at each level; `environments` requires `cloud` (`dependentRequired`). `with-environment.json`: the `with-components.json` example plus both keys, with `root`. Validate both examples and these invalid cases with a JSON Schema 2020-12 validator kept outside the repository: `environments` without `cloud`; key `hom`; `dev` with a key inside; `root` `prod`; `provider` `aws`; region `US`.
- [ ] **Step 4: `project-declare` and "The declaration's rules"** (identical text in both skills). `environment=dev` adds `environments.dev`; adding the first environment writes `cloud` from `defaults.json` (`cloud.provider`, `cloud.region`) when the file has none; `cloudRoot=tst` sets `cloud.root` and needs `cloud` to exist or `environment=` in the same call; an unknown environment or root fails with one prescribed sentence each; a run without these arguments keeps both keys as they are. Canonical order: `cloud`, then `environments`, after `components`.
- [ ] **Step 5: Run the new scenarios and `project-declare-new`, `project-declare-edit`, `project-declare-component-add`, `project-plan-nothing-to-do`; prove the rules sections are identical with a diff.**
- [ ] **Step 6: Commit** — scenarios first, then `Add cloud and environments to the project declaration`.

### Task 2: `gcp_ci-identity-setup`, and the repository's numeric ids

**Files:**
- Create: `.claude-plugin/plugins/aleogr-cloud-gcp/skills/gcp_ci-identity-setup/SKILL.md`
- Modify: `.claude-plugin/plugins/aleogr-cloud-gcp/.claude-plugin/plugin.json` (0.4.0), `.claude-plugin/plugins/aleogr-repo-github/skills/github_repo-describe/SKILL.md`, `.claude-plugin/plugins/aleogr-repo-github/.claude-plugin/plugin.json` (0.5.0)
- Test: scenarios `ci-identity-*`, `gh-describe-ids`

**Interfaces:**
- Produces: `gcp_ci-identity-setup projectId=<id> project=<name> repository=<owner>/<name> repositoryId=<digits> ownerId=<digits> branch=<name> mode=plan|apply`. Outputs: `account` (`<project>-ci@<projectId>.iam.gserviceaccount.com`), `provider` (`projects/<number>/locations/global/workloadIdentityPools/github/providers/github`), `condition` (`as-declared` | `differs` | `missing`), `ciVariables` `{ "GCP_PROJECT_ID", "GCP_WIF_PROVIDER", "GCP_CI_ACCOUNT" }`. Statuses: `unchanged`, `would-create`, `would-update`, `created`, `updated`, `failed`.
- Produces: `github_repo-describe` outputs `id` (the repository's numeric id) and `ownerId`, from the read it already makes (`.id`, `.owner.id`); `null` when the repository does not exist. No new command.

- [ ] **Step 1: Scenarios first.**
  - `ci-identity-plan-missing`: nothing exists → `would-create`; `NOT_CALLED create|add-iam-policy-binding|update-oidc`.
  - `ci-identity-apply`: creates the account, the pool, the provider and the binding, in that order (`ORDER`), reads them back, `created`; the `create-oidc` command is pinned with `--issuer-uri=https://token.actions.githubusercontent.com` and the whole condition of Global Constraints; the binding's member is `principalSet://iam.googleapis.com/projects/123456789012/locations/global/workloadIdentityPools/github/attribute.repository/example-org/example-repo` with `roles/iam.workloadIdentityUser`; outputs pin the three `ciVariables`.
  - `ci-identity-unchanged`: everything exists as declared → `unchanged`, no change command.
  - `ci-identity-differs-plan` / `ci-identity-differs-apply`: the provider's condition names another branch → `would-update` / an `update-oidc` with the whole declared condition, `updated`.
  - `ci-identity-apply-retry`: the binding fails once with the "does not exist" answer, then succeeds → `created`; `COUNT` two binding attempts.
  - `ci-identity-apply-partial`: the binding fails twice → status `created` (things were created), one `pending` item naming the binding and how to rerun; the provider is not removed.
  - `ci-identity-invalid`: `repositoryId=abc`, a `repository` without `/`, a `branch` with a space, `projectId` not matching `^[a-z][a-z0-9-]{4,28}[a-z0-9]$` → `failed`, `NOT_CALLED ^gcloud`.
  - `gh-describe-ids`: `github_repo-describe` outputs `"id": 7654321` and `"ownerId": 2345678`; the existing `gh-describe-*` scenarios pass unchanged.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Write the skill.** Reads first, each alone: the project (for its number), the account, the pool, the provider, the account's policy. Creates only what is missing, in the order account → pool → provider → binding. The attribute mapping is `google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref`. The single retry of the binding waits about one minute, as `gcp-cloud-sql_instance-switch-setup` does. `mode=plan` runs only reads. The answer never prints anything but the identifiers above.
- [ ] **Step 4: `github_repo-describe`.** Add the two outputs and one sentence; nothing else changes.
- [ ] **Step 5: Run the new scenarios, every `gh-describe-*`, and a sample of four other GCP scenarios.**
- [ ] **Step 6: Commit** — scenarios first, then `Add gcp_ci-identity-setup and the repository's ids`.

### Task 3: The registry plugin — describe and create

**Files:**
- Create: `.claude-plugin/plugins/aleogr-registry-gcp-artifact-registry/.claude-plugin/plugin.json` (0.1.0), `skills/gcp-artifact-registry_registry-describe/SKILL.md`, `skills/gcp-artifact-registry_repository-create/SKILL.md`
- Modify: `.claude-plugin/marketplace.json` (entry with `category` `registry`, `displayName` `Artifact Registry (GCP)`), `.claude-plugin/tests/run.sh` (one `--plugin-dir`), `.claude-plugin/tests/README.md`
- Test: scenarios `registry-describe-*`, `registry-create-*`

**Interfaces:**
- Produces: `gcp-artifact-registry_registry-describe projectId= project= region=`. Outputs: `exists` (bool), `region` (the region it was found in, or `null`), `otherRegions` (list, when a repository of that id exists elsewhere), `format`, `labels`, `cleanup` `{ "keep": <n>|null, "deletesTheRest": bool, "dryRun": bool }`, `push` (list of members with the writer role on the repository), `imagePath` (`<region>-docker.pkg.dev/<projectId>/<project>` or `null`). Status `unchanged` always, or `failed`.
- Produces: `gcp-artifact-registry_repository-create projectId= project= environment= region= mode=`. Outputs `imagePath`. Statuses `unchanged`, `would-create`, `created`, `failed`; a repository of that id in another region is `pending` with an item `fix by hand` (nothing changed).

- [ ] **Step 1: Scenarios first.** `registry-describe-missing` (not found is `exists` false, not `failed`), `registry-describe-exists` (pins `keep`, `dryRun`, `push`, `imagePath`), `registry-describe-other-region`, `registry-describe-refused` (the API is off or permission denied → `failed`, raw text not quoted), `registry-create-plan`, `registry-create-apply` (the create command pinned with `--repository-format=docker`, `--location=us-central1` and both labels; read back), `registry-create-existing` (`unchanged`), `registry-create-other-region` (`pending`, no create), `registry-create-invalid` (a region `US`, a project name with an uppercase letter → `failed`, no command).
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Plugin skeleton, then the two skills.** Create `plugin.json` and the skill folders before adding the `--plugin-dir` line, and commit those together. `registry-describe` reads the repository, then (only when it exists) its policy; when it is not found in `region`, one list of the project's repositories tells whether the id exists elsewhere.
- [ ] **Step 4: Run the scenarios.**
- [ ] **Step 5: Commit** — `Add the Artifact Registry plugin: describe and create`.

### Task 4: The registry plugin — cleanup and push access

**Files:**
- Create: `skills/gcp-artifact-registry_cleanup-configure/SKILL.md`, `skills/gcp-artifact-registry_access-grant/SKILL.md`, `files/cleanup-policy.json` (all under the registry plugin)
- Test: scenarios `registry-cleanup-*`, `registry-access-*`

**Interfaces:**
- Consumes: the plugin of Task 3.
- Produces: `gcp-artifact-registry_cleanup-configure projectId= project= region= keep=<1..50> mode=`. Statuses `unchanged`, `would-update`, `updated`, `failed`. Outputs `keep`, `dryRun`.
- Produces: `gcp-artifact-registry_access-grant projectId= project= region= identity=<service account e-mail> role=push mode=`. Statuses `unchanged`, `would-update`, `updated`, `failed`. Output `granted` (bool).

- [ ] **Step 1: Scenarios first.**
  - `registry-cleanup-plan` (no policy → `would-update`), `registry-cleanup-apply` (the set command pinned with the policy file and dry-run off; read back; `updated`), `registry-cleanup-unchanged`, `registry-cleanup-differs` (keep 3 in the cloud, 5 asked), `registry-cleanup-dry-run` (rules right, dry-run on → `would-update` in plan), `registry-cleanup-keep-only` (the keep rule alone, no delete rule → differs), `registry-cleanup-invalid` (`keep=0`, `keep=abc` → `failed`, no command).
  - `registry-access-plan`, `registry-access-apply` (binding pinned with `--role=roles/artifactregistry.writer` and `serviceAccount:demo-ci@aleogr-dev-demo-ab12.iam.gserviceaccount.com`, on the repository), `registry-access-unchanged`, `registry-access-retry` (first attempt refused as "does not exist", second succeeds), `registry-access-pull` (`role=pull` → `failed`, the sentence says it is not needed), `registry-access-invalid` (an identity that is not a service account e-mail).
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: The policy file and `cleanup-configure`.** `files/cleanup-policy.json` holds the two rules with the keep count 5. For another `keep`, the skill must hand `gcloud` a file with that count without leaving a file in the project folder and in a way that works in bash and in PowerShell: the implementer chooses how, shows the file's content in the answer, and says in the report what was chosen. The skill compares both rules and the dry-run flag with what `gcloud` reads back.
- [ ] **Step 4: `access-grant`**, with the single retry of Task 2's wording.
- [ ] **Step 5: Run the scenarios and every `registry-*` of Task 3.**
- [ ] **Step 6: Commit** — `Add the cleanup policy and push access to the registry plugin`.

### Task 5: `project-plan` reads the ground

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-plan/SKILL.md` (not "The declaration's rules")
- Test: scenarios `project-plan-environment-*`; `project-plan-nothing-to-do/expect.txt`

**Interfaces:**
- Consumes: Tasks 1 to 4, and the existing `gcp_environment-describe project= environment=` (outputs `exists`, `projectId`, `billingLinked`, `enabledServices`), `tools-check` (with no argument it checks `gcloud`).
- Produces: four items after `protection`, in this order, only when the declaration has `environments`:

  | Item | States | Action |
  |---|---|---|
  | `environment dev` | `exists` / `missing` / `billing not linked` | `none` / `create` / `repair` |
  | `apis` | `enabled` / `to enable: <n>` | `none` / `enable` |
  | `registry` | `as declared` / `missing` / `cleanup differs` / `in another region` | `none` / `create` / `configure` / `fix by hand` |
  | `ci identity` | `as declared` / `missing` / `differs` / `cannot push` | `none` / `create` / `update` / `grant` |

  Shared states: `not checked until the change is merged` / `none` while the declaration's action is not `none`; `follows the creation` / `none` while the repository does not exist; `follows the environment` / `none` for the last three when the GCP project is missing or its billing is not linked; `follows the apis` / `none` for `registry` and `ci identity` when an API is to enable.
- Produces: `outputs.environment` `{ "name": "dev", "projectId": <id>|null }`, `outputs.ciVariables` (from `gcp_ci-identity-setup`, or `null`). `fix by hand` blocks `nothing to do` and is never an action `project-apply` makes.

- [ ] **Step 1: Scenarios first.**
  - `project-plan-environment-missing`: declaration merged, GCP project missing → `environment dev` `missing` / `create`, the three others `follows the environment`; `CALLED gcloud projects` (the describe); `NOT_CALLED gcloud (artifacts|iam)`; status `would-update`.
  - `project-plan-environment-apis`: project exists, one API off → `apis` `to enable: 1`, the two others `follows the apis`; `NOT_CALLED gcloud (artifacts|iam)`.
  - `project-plan-environment-ground-missing`: APIs on, no repository, no identity → `registry` `missing` / `create`, `ci identity` `missing` / `create`.
  - `project-plan-environment-cannot-push`: everything exists, the account is not a writer → `ci identity` `cannot push` / `grant`.
  - `project-plan-environment-as-declared`: everything as declared → status `unchanged`, `nothing to do`, nine items (with components), `ciVariables` pinned.
  - `project-plan-environment-other-region`: `registry` `in another region` / `fix by hand`; status not `unchanged`.
  - `project-plan-environment-proposed`: the declaration is `changed here` → the four rows `not checked until the change is merged`; `NOT_CALLED ^gcloud (projects|services|artifacts|iam)`.
  - `project-plan-environment-no-gcloud`: `gcloud` not signed in → `failed`, a pinned word, no row read.
  - `project-plan-nothing-to-do`: add `NOT_CALLED ^gcloud`.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Change the skill.** After the existing steps: `tools-check` (no argument) → `gcp_environment-describe project=<name> environment=dev` → when the project exists with billing, compare `enabledServices` with `project.services` of `defaults.json` → when all are on, `gcp-artifact-registry_registry-describe` and `gcp_ci-identity-setup mode=plan` (with `repository`, `repositoryId`, `ownerId` and `branch` from the `github_repo-describe` already made). `cannot push` is decided here: the identity's `account` is not in the registry's `push`. Keep the wording that stops the model from ending at a nested skill's block, applied to the new calls.
- [ ] **Step 4: Run the new scenarios and every existing `project-plan-*`; report each.**
- [ ] **Step 5: Commit** — scenarios first, then `Give project-plan the rows of the environment`.

### Task 6: `project-apply` makes the ground

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-apply/SKILL.md`, `.claude-plugin/plugins/aleogr/.claude-plugin/plugin.json` (0.9.0, and its description, the same text in `marketplace.json`)
- Test: scenarios `project-apply-environment-*`; `project-apply-nothing-to-do/expect.txt`

**Interfaces:**
- Consumes: the items of Task 5 and the skills of Tasks 2 to 4, plus `gcp_environment-create project= environment=dev [root=tst] mode=apply` and `gcp_services-enable projectId= services=<list> mode=apply`.
- Produces: after the repository's steps of a run whose declaration action is `none`, in this order and only for rows with an action: `gcp_environment-create` (`create`, `repair`) → `gcp_services-enable` (`enable`) → `gcp-artifact-registry_repository-create` (`create`) → `gcp-artifact-registry_cleanup-configure keep=<project.registry.keep>` (`create`, `configure`) → `gcp_ci-identity-setup` (`create`, `update`) → `gcp-artifact-registry_access-grant identity=<account> role=push` (`create`, `grant`). When the environment was created or an API enabled in this run, the rows that were `follows …` are read by planning again before going on (one more `project-plan`), so that one run reaches `nothing to do`.

- [ ] **Step 1: Scenarios first** (two at a time).
  - `project-apply-environment-unconfirmed`: plan with `create` rows, no `confirm` → `pending`, `NOT_CALLED gcloud .*(create|enable|add-iam|set-cleanup)`.
  - `project-apply-environment-create`: nothing exists → the six skills in order (`ORDER` on their decisive commands), `root=tst` passed when declared (`CALLED` the folder lookup inside `tst`), last plan `nothing to do`, status `updated`.
  - `project-apply-environment-folder-missing`: `gcp_environment-create` stops because the folder is missing → status and pending item as the skill prescribes, a pinned word saying which folder to create, nothing after it called.
  - `project-apply-environment-resume`: project and APIs exist, registry and identity missing → only the last four skills run.
  - `project-apply-environment-grant`: only `cannot push` → only `access-grant`.
  - `project-apply-environment-fix-by-hand`: registry in another region → the run makes the other rows, ends with the item in `pending`, never calls a create for the registry.
  - `project-apply-nothing-to-do`: add `NOT_CALLED ^gcloud`.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Change the skill**, keeping one confirmation per run and the rule that a failure stops the run with what was done reported. The answer says, in one line under the last plan, that nothing is deployed yet and that the CI identity can only push images.
- [ ] **Step 4: Run the new scenarios and every existing `project-apply-*`; report each, with run counts.**
- [ ] **Step 5: Commit** — scenarios first, then `Let project-apply create the ground of an environment`.

### Task 7: Documents and the run checklist

**Files:**
- Modify: `docs/DESIGN.md` (sections 1, 2, 6.4, 7, 9 or the plugin list, 11.1, 12, 12.2, 15, 17, 18), `docs/CONTRACTS.md` (cloud-*: `ci-identity-setup` implemented; registry-*: the four actions as built, `access-grant` with `push` only), `docs/PROVIDER-FACTS.md`, `docs/cloud-shell.md`, `.claude-plugin/plugins/README.md`, `.claude-plugin/tests/README.md`
- Create: `docs/plans/2026-11-19-pilot-stage-4a-run.md`

- [ ] **Step 1: Documents**, describing what was built (read the built files), as decisions in the present tense. Section 18 gains: 4a does not prove the CI identity from GitHub Actions; the cleanup policy's deletions are not observed in a run; changing the region or the root of an existing environment is not built; removal is stage 6.
- [ ] **Step 2: The run checklist**, in the form of `2026-11-19-pilot-stage-3c-2-run.md`: before you start (`gcloud` and `gh` signed in, in Cloud Shell; the folder `dev` inside `tst` exists, with the console steps to create it when it does not; plugins updated and the new one installed); `project-plan` (nothing to do); `project-declare environment=dev cloudRoot=tst`; plan; apply (pull request); merge; apply (the ground, with each skill's expected status); plan (`nothing to do`); what to look at in the Google Cloud console (the project in the folder, the repository with its cleanup policy, the pool and its provider); "if something goes wrong"; a results table. It says that nothing here costs money and why.
- [ ] **Step 3: Check every relative link, and that no identifier or e-mail was written.**
- [ ] **Step 4: Commit** — `Document the ground of an environment` and `Add the stage 4a run checklist`.
