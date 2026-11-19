# Reference project, stage 4b-1: a fluid run and the login of the organization — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `project-apply` waits and goes on by itself instead of stopping, one run after a merge makes everything, answers are short, and the login that lets a personal Google account into a Cloud Run service is a row of the platform's plan, prepared once with the tooling doing all that a command can do.

**Architecture:** `aleogr-cloud-gcp` gains `gcp_login-describe` and `gcp_login-setup`; `platform-plan`/`platform-apply` gain the row `login`. `project-apply` loses the stop after the folder update (the warning moves to the proposal) and replaces its stops on a just-enabled API by a bounded poll; the two skills with a single retry get the same poll. The test harness gains a fake `sleep`. The premise becomes a rule in `DESIGN.md` section 10.4.

**Tech Stack:** Claude Code plugin skills (Markdown), `gcloud`, `gh`, the bash harness under `.claude-plugin/tests/`.

**Spec:** [`2026-11-19-pilot-stage-4b-design.md`](2026-11-19-pilot-stage-4b-design.md), "Part 4b-1". Models of style: `aleogr-cloud-gcp/skills/gcp_ci-identity-setup`, `aleogr-registry-gcp-artifact-registry/skills/*` (prescribed failure sentences, no word of `gcloud`'s answer repeated), `aleogr/skills/platform-plan` and `platform-apply`.

## Global Constraints

- **The premise: using the tooling is simple, fluid, automated and easy.** A run goes as far as it safely can; it stops only before an action that cannot be undone, that exposes something, or that has a cost. Where a wait is known to be needed the skill waits and tries again by itself. A stop says what was done, what is left and the one command that goes on. An answer is short and has one result block.
- Everything versioned is in English. The repository is public: no organization, folder, billing account or project identifier or number, no e-mail, no OAuth client id, no secret. Fixtures use only the fictitious values already in the scenarios (`demo`, `aleogr-dev-demo-ab12`, `123456789012`, organization `111111111111`, `example-org/example-repo`, `demo-user@example.com`), plus the client id `123456789012-abc.apps.googleusercontent.com`. `aleogr-sandbox` and `pilot` only under `docs/`.
- **The login's client secret never passes through a skill, a skill's output, a fixture or the conversation.** No skill reads it, asks for it or builds a file with it; the one command that takes it is printed for the owner to paste in a terminal.
- No `SKILL.md` has `name:` in its frontmatter. Every skill validates before any command, shows each command before running it, runs only the commands (or invokes only the skills) its steps list, and ends with exactly one fenced `aleogr-result` block. Status `pending` means nothing was changed. A missing argument is `failed`, never a question. Each failure has one prescribed sentence; no word of `gcloud`'s or `gh`'s answer is repeated.
- The orchestrator skills run no `gcloud`, `gh` or `git` command; they invoke skills. (The wait is the one exception this plan introduces: see Task 3.)
- The bounded poll, wherever this plan says "waits": try; while the answer is the refusal that waiting cures, wait 30 seconds and try again; at most 10 tries (5 minutes); then stop with the skill's item. The wait is the command `sleep 30`, run so that the run goes on after it.
- After a GCP project was created or found in a run, no stop says to apply again on a guess (stage 4a's rule): the `how` is to wait a minute, run `/aleogr:project-plan`, and apply only when it shows `environment dev` as `exists`.
- The login: consent screen `aleogr` (audience External, left in testing: with the basic scopes only it lets any allowed account in) and OAuth client `iap` (web application) in the shared project; redirect address `https://iap.googleapis.com/v1/oauth/clientIds/<client id>:handleRedirect`; the organization's IAP setting names that client; the role is `roles/iap.settingsAdmin` on the organization.
- A platform whose login is not prepared, and a declaration without environments, behave as before this plan except for the new row and additive result keys. Every existing scenario passes, changed only where this plan changes the behaviour it pins.
- "The declaration's rules" in `project-declare` and `project-plan` are not touched.
- Do not change the root `README.md`; never create `.github/README.md`; no skill, plugin or workflow beyond this plan. `docs/DESIGN.md` states decisions in the present tense; section 16 gets no entry.
- Commit messages end with the line the session gives; no model name anywhere. `.superpowers/` is never committed.
- Scenarios: `bash .claude-plugin/tests/run.sh <scenario>`; four at a time, two at a time for `project-apply-*` and `platform-apply-*`. Each run costs model usage. Expectations pin content; failure scenarios pin a word of the prescribed sentence.

## Review Focus

1. The secret can reach a skill only by a mistake in wording: no skill may ask for it, echo the command with a value in it, or read a file that holds it. Tests: `login-setup-apply` pins `OUTPUT_NOT clientSecret: [^<$%]` and that the printed command contains `read -s` (Task 1).
2. A run that waits must end: the poll stops at 10 tries and reports. Tests: `project-apply-environment-apis-wait-limit` (Task 3), `ci-identity-apply-wait-limit` (Task 2).
3. Removing the stop before creating a GCP project must not remove the warning: the proposal says it. Tests: `project-apply-environment-propose-warns` (Task 3).
4. After a merge, one run goes from `this folder is behind` to `nothing to do` with a project to create. Test: `project-apply-environment-update-then-create` (Task 3), replacing `-update-then-confirm`.
5. A platform with no login prepared still plans and applies everything else. Tests: `platform-plan-login-missing`, `platform-apply-login-missing` (Task 4).
6. A fake `sleep` must not hide a real command or make an old scenario pass falsely. Test: the harness self-tests plus `harness-selftest-sleep` (Task 2).

---

## File map

| Path | Responsibility |
|---|---|
| `.claude-plugin/plugins/aleogr-cloud-gcp/skills/gcp_login-describe`, `gcp_login-setup`, `plugin.json` (0.5.0), the plugin's entry in `marketplace.json` | the login |
| `.claude-plugin/tests/bin/sleep`, `bin/fake-cli`, `tests/README.md` | a fake wait |
| `.../aleogr-cloud-gcp/skills/gcp_ci-identity-setup`, `.../aleogr-registry-gcp-artifact-registry/skills/gcp-artifact-registry_access-grant` (plugin 0.1.1) | the bounded poll |
| `.../aleogr/skills/project-apply`, `.../aleogr-repo-github/skills/github_pull-request-open` (0.5.1) | one run after a merge; waits; the note of a proposal |
| `.../aleogr/skills/platform-plan`, `platform-apply`, `plugin.json` (0.10.0) | the row `login` |
| `.../aleogr/skills/project-plan`, `project-apply`, `platform-plan`, `platform-apply` | the form of the answer |
| `docs/DESIGN.md`, `CONTRACTS.md`, `PROVIDER-FACTS.md`, `cloud-shell.md`, `docs/plans/2026-11-19-pilot-stage-4b-1-run.md` | documents |

Tasks 1 and 2 touch disjoint paths and can run in parallel. Task 3 follows 2. Task 4 follows 1. Task 5 follows 3 and 4. Task 6 last.

---

### Task 1: The login skills

**Files:**
- Create: `.claude-plugin/plugins/aleogr-cloud-gcp/skills/gcp_login-describe/SKILL.md`, `gcp_login-setup/SKILL.md`
- Modify: that plugin's `plugin.json` (0.5.0, description naming the login) and its entry in `.claude-plugin/marketplace.json` (same description)
- Test: scenarios `login-describe-*`, `login-setup-*`

**Interfaces:**
- Produces: `gcp_login-describe` (no argument). It finds the organization as the other GCP skills do, then reads `gcloud iap settings get --organization=<id> --format=json`. Outputs `prepared` (true when `accessSettings.oauthSettings.clientId` is a non-empty string), `organization` (true when one organization was found). Status `unchanged` or `failed`. A setting with no client, or an empty answer, is `prepared` false, not a failure; a refused read is `failed`.
- Produces: `gcp_login-setup projectId=<shared project id> mode=plan|apply`. In `apply`: grants the active account `roles/iap.settingsAdmin` on the organization when it lacks it, enables `iap.googleapis.com` in the project when it is off, and prints the list of what is left. Outputs `prepared`, `roleGranted`, `apiEnabled`, `steps` (the list, as text lines). Statuses: `unchanged` (already prepared: nothing done, no list), `would-update`, `updated` (something was granted or enabled), `pending` (role and API were already right and the clicks are left: nothing changed), `failed`. Whenever the login is not prepared, `pending` holds one item `{ "item": "login", "reason": "manual", "how": "<the steps in one line>, then run /aleogr:platform-apply" }`.

- [ ] **Step 1: Scenarios first.** `login-describe-prepared`, `-not-prepared` (settings without a client), `-empty` (no settings at all), `-refused` (`failed`, raw text not quoted), `-no-organization`; `login-setup-plan`, `login-setup-apply` (role granted and API enabled, in that order; the list holds the two console addresses with `?project=aleogr-shared-ab12`, the names `aleogr` and `iap`, `External`, the redirect address pattern, and the one command containing `read -r -s` and `gcloud iap settings set`; `OUTPUT_NOT clientSecret: [^<$%]`; `NOT_CALLED iap settings set`), `login-setup-already-prepared` (`unchanged`, `NOT_CALLED add-iam-policy-binding|services enable`), `login-setup-role-present` (only the API), `login-setup-invalid` (a `projectId` that fails the id rule).
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Write the two skills.** Check every command against `gcloud … --help` first (`gcloud iap settings get`, `gcloud organizations get-iam-policy` with a filter on the member and the role, `gcloud organizations add-iam-policy-binding … --condition=None`, `gcloud services list --enabled --filter`, `gcloud services enable`). The one command the list prints is, exactly:

  ```bash
  ( read -r -p "Client id: " CID; read -r -s -p "Client secret: " CSEC; echo; O=$(gcloud organizations list --format="value(name)" | sed 's#.*/##'); F=$(mktemp); trap 'rm -f "$F"' EXIT; printf 'accessSettings:\n  oauthSettings:\n    clientId: %s\n    clientSecret: %s\n' "$CID" "$CSEC" > "$F"; gcloud iap settings set "$F" --organization="$O" --billing-project=<projectId> )
  ```

  It runs in a subshell of bash (Cloud Shell): the secret is read without being shown, lives in a variable and a temporary file that the subshell removes when it ends, however it ends. `<projectId>` is the shared project's id, the only value the skill fills in.

  The skill prints it as text for the owner; it never runs it and never fills it in.
- [ ] **Step 4: Run the scenarios and four existing GCP scenarios.**
- [ ] **Step 5: Commit** — scenarios first, then `Add the login skills of the organization`.

### Task 2: A fake wait, and the bounded poll in the two skills that retry

**Files:**
- Create: `.claude-plugin/tests/bin/sleep`; scenario `harness-selftest-sleep`
- Modify: `.claude-plugin/tests/bin/fake-cli` (only if the wrapper needs it), `.claude-plugin/tests/README.md`, `gcp_ci-identity-setup/SKILL.md`, `gcp-artifact-registry_access-grant/SKILL.md`, the registry plugin's `plugin.json` (0.1.1)
- Test: `ci-identity-apply-retry`, `-apply-partial`, `registry-access-retry`, `-retry-fail`, plus new `ci-identity-apply-wait-limit`, `registry-access-wait-limit`

**Interfaces:**
- Produces: in the harness, `sleep <n>` returns at once and is logged as `sleep <n>` (a line that starts with `sleep `, so `NOT_CALLED ^([a-fi-z-]|g[^hi])`-style pins must be checked: adjust the two "no cloud call" pins to exclude `sleep ` only if they would now fail, and say so).
- Produces: both skills replace "wait about a minute and try once more" by the bounded poll of Global Constraints, for the refusal that follows a just-created account only.

- [ ] **Step 1: Scenarios first**: the limit scenarios (10 refusals → the skill's existing end for a refusal; `COUNT 10` attempts; `COUNT 9 ^sleep 30`), and the existing retry scenarios rewritten to the poll (one refusal → `COUNT 1 ^sleep 30`).
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: The fake `sleep` and the README; then the two skills.** Word the wait so that the run goes on after it (the first real run of 4a showed a background wait resuming by itself): say what was learned and what wording was chosen in the report.
- [ ] **Step 4: Run every `ci-identity-*`, `registry-access-*` and `harness-selftest-*`.**
- [ ] **Step 5: Commit** — `Add a fake wait to the tests and poll instead of one retry`.

### Task 3: `project-apply` goes on by itself

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-apply/SKILL.md`; `.claude-plugin/plugins/aleogr-repo-github/skills/github_pull-request-open/SKILL.md` and that plugin's `plugin.json` (0.5.1)
- Test: scenarios `project-apply-environment-*`, `gh-pr-open-note`

**Interfaces:**
- Consumes: Task 2's fake `sleep` and poll.
- Produces: `github_pull-request-open` gains the optional argument `note=<one sentence>`: appended to the pull request's body after `Proposed by aleogr.`; same character rules as `title`.
- Produces: `project-apply`:
  - when the proposal carries a declaration that adds an environment, the answer and `note=` say that applying it after the merge creates a Google Cloud project, whose id is permanent;
  - after the folder update the run goes on with the new plan under the confirmation given, also when that plan creates the GCP project (the stop of stage 4a is removed);
  - after `gcp_services-enable` enabled something, the next skill is tried, and while it ends with the refusal of a just-enabled API the run waits and tries again by the bounded poll; when the limit passes, today's stop;
  - no plan in the middle unless the project already existed and was repaired.

- [ ] **Step 1: Scenarios first.** `gh-pr-open-note`; `project-apply-environment-propose-warns` (declaration with a new environment → the note in `gh pr create --body` and a pinned word in the answer); `project-apply-environment-update-then-create` (replaces `-update-then-confirm`: folder behind, project missing → pull, then the six skills, `nothing to do`, `updated`, no item `confirm`); `project-apply-environment-apis-wait` (the registry read refused twice then accepted → `COUNT 2 ^sleep 30`, the run ends `nothing to do`); `project-apply-environment-apis-wait-limit` (refused ten times → `updated`, the item `apis` with the creation's wait wording, `COUNT 9 ^sleep 30`); `project-apply-environment-apis-refused` is rewritten or removed accordingly.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Change the two skills.** `project-apply` may run exactly one command of its own, `sleep 30`, and nothing else: say so where the skill says it runs no command.
- [ ] **Step 4: Run every `project-apply-*` (two at a time) and every `gh-pr-open-*`; report each with its run count.**
- [ ] **Step 5: Commit** — scenarios first, then `Let project-apply wait and go on after a merge`.

### Task 4: The row `login` of the platform

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/platform-plan/SKILL.md`, `platform-apply/SKILL.md`, the `aleogr` plugin's `plugin.json` (0.10.0, with the same description in `marketplace.json`)
- Test: scenarios `platform-plan-login-*`, `platform-apply-login-*`

**Interfaces:**
- Consumes: Task 1.
- Produces: `platform-plan` item `login`, after the existing ones: `prepared` / `none`; `not prepared` / `prepare`; `not checked, will be checked after the project exists` / `prepare` while the shared project is missing. A failed read of the login makes the row `not checked` / `none` with one sentence, not a failed plan.
- Produces: `platform-apply` invokes `gcp_login-setup projectId=<shared> mode=apply` for the action `prepare`, last, and carries its `pending` item. A run in which only the login's clicks are left ends with the status the other steps give and that one item; `nothing to do` only when the login is `prepared` too.

- [ ] **Step 1: Scenarios first**: `platform-plan-login-prepared` (every row `none`, `nothing to do`), `platform-plan-login-missing` (the other rows as declared, `login` `not prepared` / `prepare`, status `would-update`), `platform-apply-login-missing` (role and API made, the list printed, item `login`, no `iap settings set`), `platform-apply-login-clicks-left` (role and API already right → `pending`, nothing changed). Every existing `platform-*` scenario gets the login's read in its fixtures (prepared) so that its expectations stand.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Change the two skills.**
- [ ] **Step 4: Run every `platform-*`.**
- [ ] **Step 5: Commit** — scenarios first, then `Give the platform's plan the row login`.

### Task 5: The form of the answer

**Files:**
- Modify: `project-plan/SKILL.md` (not "The declaration's rules"), `project-apply/SKILL.md`, `platform-plan/SKILL.md`, `platform-apply/SKILL.md`; nested skills only if the measurement shows it is needed, and then only their closing instructions
- Test: no new behaviour; a measurement

**Interfaces:**
- Produces: a measured rate of the defect "a nested skill's result block is printed before the plan's table, or the run ends at it", before and after, and skills changed until it is under one run in twenty, or a written account of why it cannot be.

- [ ] **Step 1: Measure.** Run `project-plan-environment-as-declared` and `project-apply-environment-create` 20 times each (four and two at a time), counting runs that print a nested block before the table or end at one. Record the two rates.
- [ ] **Step 2: Form one hypothesis at a time and test it on 20 runs**: for example, where in the answer the nested block lands (is it text between tool calls, or part of the last message?); whether naming the result block of nested skills "input, never output" at each invocation changes it; whether asking nested skills, through an argument such as `quiet=yes`, to end with the block alone and no sentence changes it. Keep what lowers the rate; revert what does not.
- [ ] **Step 3: Shorten the orchestrators' answers** to: one line per skill made (name and status), the last plan's table, what is left with its one command, the addresses when there are any, one result block. Update scenarios that pin removed sentences.
- [ ] **Step 4: Measure again, the same 40 runs.** Report both rates and every change kept.
- [ ] **Step 5: Run every `project-plan-*`, `project-apply-*`, `platform-*` once.**
- [ ] **Step 6: Commit** — `Shorten the orchestrators' answers and keep nested blocks out of them`.

### Task 6: Documents and the run checklist

**Files:**
- Modify: `docs/DESIGN.md` (10.4 the premise and its rules; 6.3 the login as built: IAP on the service, the organization's client, why a personal account needs it; 6.8 the login as a platform resource; 12 and 12.2 `project-apply` as built; 17; 18), `docs/CONTRACTS.md`, `docs/PROVIDER-FACTS.md` (the spikes of 2026-11-19, marked as seen in a real run), `docs/cloud-shell.md` (the login's preparation), `.claude-plugin/plugins/README.md`
- Create: `docs/plans/2026-11-19-pilot-stage-4b-1-run.md`

- [ ] **Step 1: Documents**, from the built files. Section 18 gains what stays open: the rate measured in Task 5; whether an application in testing lets a second Google account in without a warning, as Google's help says for the basic scopes; the wait seen only in Cloud Shell.
- [ ] **Step 2: The run checklist**, short (the premise applies to it too): update the plugins; `/aleogr:platform-plan` → the row `login` `prepared`, `nothing to do`; with a second Google account, one `gcloud iap web add-iam-policy-binding` on `spike-iap2` and that account gets in (the proof that a person is let in by a command); remove the spike (`gcloud run services delete spike-iap`, `spike-iap2`, `gcloud iam service-accounts delete spike-iap@…`, and the client of `aleogr dev` in the console); `/aleogr:project-plan` in `~/pilot` → `nothing to do`. A results table.
- [ ] **Step 3: Check every relative link, and that no identifier, e-mail or client id was written.**
- [ ] **Step 4: Commit** — `Document the premise, the login and the fluid run` and `Add the stage 4b-1 run checklist`.
