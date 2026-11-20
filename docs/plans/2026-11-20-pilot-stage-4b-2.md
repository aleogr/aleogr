# Reference project, stage 4b-2: the deploy — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** every component of a declaration with environments runs as a Cloud Run service behind the login, created by one `project-apply`, and CI replaces its image at every merge to the default branch.

**Architecture:** `aleogr-cloud-gcp` gains `gcp_deploy-describe`, `gcp_deploy-setup` and `gcp_access-grant`, and the CI identity's condition also requires the reusable deploy workflow. `go_setup` writes a `Dockerfile`. `aleogr-repo-github` gains `github_variables-set`, and `github_ci-setup` writes a deploy job per component (marker version 2). `aleogr/aleogr` gains the reusable workflow `deploy-cloud-run.yml`. `project-plan` / `project-apply` gain the rows `services` and `ci variables`, and a shortcut `project-access` lets a person in.

**Tech Stack:** Claude Code plugin skills (Markdown), `gcloud`, `gh`, GitHub Actions, Docker, the bash harness under `.claude-plugin/tests/`.

**Spec:** [`2026-11-19-pilot-stage-4b-design.md`](2026-11-19-pilot-stage-4b-design.md), "Part 4b-2". Facts checked against primary sources on 2026-11-20: `.superpowers/sdd/4b2-facts.md` (a scratch file, not versioned; every implementer reads the sections its task names, and what a task relies on goes into `docs/PROVIDER-FACTS.md` in Task 8, marked as read in the reference or seen in a real run). Models of style: `gcp_ci-identity-setup`, `gcp_login-setup`, `gcp-artifact-registry_access-grant`, `github_ci-setup`.

## Global Constraints

- **The premise: using the tooling is simple, fluid, automated and easy** (`docs/DESIGN.md` section 10.4): a run goes on by itself, waits are bounded polls (`sleep 30`, at most 10 tries), a stop only before something irreversible, exposing or with a cost, one command per thing left, short answers, one result block, never a question.
- **Nothing with a fixed cost.** Every service: minimum 0 instances, maximum 2, request-based billing. No load balancer, no reserved address, no minimum instance, ever.
- **A service is never reachable without the login, even for a moment.** It is created in one command with `--no-allow-unauthenticated --iap`. No skill and no workflow ever passes `--allow-unauthenticated`, `--no-iap`, or adds `allUsers` / `allAuthenticatedUsers` to anything.
- **CI is the only deploy path and only replaces the image.** The workflow runs `gcloud run services update <service> --image=<path>@sha256:<digest>` and nothing else on the service: never `gcloud run deploy`, never `--iap` (either would need a role CI must not have), never a create. A missing service is a failure.
- **The deploy never runs from a pull request or from other code.** Triggers of the project's `ci.yml` stay `pull_request` and `push` to the default branch. `pull_request_target` and `workflow_run` appear in no file this plan writes. The deploy job runs only on `push` to the default branch.
- Everything versioned is in English. The repository is public: no organization, folder, billing account or project identifier or number, no e-mail, no OAuth client id, no secret. Fixtures use only the fictitious values already in the scenarios (`demo`, `aleogr-dev-demo-ab12`, `123456789012`, `example-org/example-repo`, `demo-user@example.com`, `us-central1`). `aleogr-sandbox` and `pilot` only under `docs/`.
- A person's e-mail is an argument (`person=`) and is never written to a file, a label or a result block; a result block names how many people a list holds, never who.
- No `SKILL.md` has `name:` in its frontmatter. Every skill validates before any command, shows each command before running it, runs only the commands (or invokes only the skills) its steps list, and ends with exactly one fenced `aleogr-result` block. `pending` means nothing was changed. A missing argument is `failed`, never a question. Each failure has one prescribed sentence; no word of `gcloud`'s or `gh`'s answer is repeated.
- Every skill another skill invokes holds, as the first paragraph under `## Result block`, the paragraph "When another skill invoked this one …" byte-identical to the one in the 25 skills that have it. Orchestrators keep the sentence that names their answer as the next output on every end.
- "The declaration's rules" stay byte-identical in `project-declare` and `project-plan` (Task 6 changes both in the same commit and proves it).
- A declaration without environments, and a platform whose login is not prepared, behave as before this plan except for new rows and additive result keys. Every existing scenario passes, changed only where this plan changes the behaviour it pins.
- Names: service and its account `<project>-<component>`; labels `aleogr-project=<project>`, `aleogr-environment=<environment>`, `aleogr-component=<component>`; image `<image path>/<component>`; Actions variables `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT`, `GCP_REGION`, `GCP_IMAGE_PATH`.
- Values, read by the orchestrators from `defaults.json` key `project.deploy` and passed as arguments: `maxInstances` 2, `cpu` `1`, `memory` `256Mi`, `placeholderImage` `us-docker.pkg.dev/cloudrun/container/hello:latest`. (One CPU, not a fraction: below one CPU Cloud Run allows one request at a time per instance, so two in all; the cost is by use either way.)
- Roles, each on one resource, never on the project: CI account `roles/run.developer` on each service and `roles/iam.serviceAccountUser` on each service's account; the IAP service agent `roles/run.invoker` on each service (made by `--iap` itself); a person `roles/iap.httpsResourceAccessor` on each service. A service's own account has no role.
- Do not change the root `README.md`; never create `.github/README.md`; no skill, plugin or workflow beyond this plan. `docs/DESIGN.md` states decisions in the present tense; section 16 only gains real rejected alternatives.
- Commits: `git commit -m … -- <paths>` (a pathspec, always); messages end with the line the session gives; no model name anywhere. `.superpowers/` is never committed.
- Scenarios: `bash .claude-plugin/tests/run.sh <scenario>`; four at a time, two at a time for `project-apply-*` and `platform-apply-*`. Each run costs model usage. Expectations pin content; failure scenarios pin a word of the prescribed sentence. `COUNT` means "at least": a limit is pinned by an (N+1)th response that succeeds.

## Review Focus

1. A service created public, or left without the login after a partial failure. Tests: `deploy-setup-create` pins `--no-allow-unauthenticated` and `--iap` in the one creating command and `NOT_CALLED allow-unauthenticated[^-]|allUsers|no-iap`; `deploy-setup-create-failed-then-read` (the create fails after creating: the skill reads the service and repairs, never leaves it without reporting) (Task 3).
2. CI gaining more than "replace the image": a role on the project, or `setIamPolicy`. Tests: `deploy-setup-create` pins the two bindings' resources; the workflow's static check refuses `run deploy`, `--iap`, `add-iam-policy-binding` (Tasks 2, 3).
3. Another workflow on the default branch acting as the CI account. Tests: `ci-identity-apply-workflow-condition` pins the `job_workflow_ref` clause; `ci-identity-apply-update-4a-provider` (a provider with the 4a condition is updated, not recreated) (Task 4).
4. A person's e-mail leaking into output, or a typo letting the wrong person in. Tests: `access-grant-apply` pins `RESULT_NOT demo-user@example.com`; `access-grant-invalid` (not an e-mail; a group or `allUsers` given as `person`) (Task 4).
5. An identifier in the public logs of a deploy. Test: the static check requires the masking step to be the first step of the job and to cover the project id, the project number and the account (Task 2).
6. A deploy from a pull request. Tests: `gh-ci-setup-deploy-jobs` pins the `if:` of each deploy job and `OUTPUT_NOT pull_request_target|workflow_run` on the written file (Task 5).
7. An existing project of stage 4a (marker version 1, no `Dockerfile`, a provider without the new clause, five APIs) reaching `nothing to do` in one `project-apply` and one merge. Test: `project-apply-deploy-from-4a` (Task 7).
8. The run that creates services while the login is not prepared. Tests: `project-plan-services-wait-login`, `project-apply-services-wait-login` (no service created) (Tasks 6, 7).

---

## File map

| Path | Responsibility |
|---|---|
| `.claude-plugin/plugins/aleogr-stack-go/skills/go_setup`, `plugin.json` (0.2.0) | the `Dockerfile` |
| `.github/workflows/deploy-cloud-run.yml`, `self-test-deploy-cloud-run.yml`, `.github/testdata/deploy-cloud-run/check.sh`, `.github/workflows/README.md` | the reusable deploy and its static check |
| `.../aleogr-cloud-gcp/skills/gcp_deploy-describe`, `gcp_deploy-setup` | a service as declared |
| `.../aleogr-cloud-gcp/skills/gcp_access-grant`, `gcp_ci-identity-setup`, `plugin.json` (0.6.0) | who gets in; which workflow may act as CI |
| `.../aleogr-repo-github/skills/github_variables-set`, `github_ci-setup`, `plugin.json` (0.6.0) | Actions variables; the deploy jobs |
| `.../aleogr/defaults.json`, `skills/project-declare`, `project-plan` | the rule on names, the APIs, the rows |
| `.../aleogr/skills/project-apply`, `project-access`, `plugin.json` (0.11.0) | the run; the shortcut |
| `docs/DESIGN.md`, `CONTRACTS.md`, `PROVIDER-FACTS.md`, `cloud-shell.md`, `.claude-plugin/plugins/README.md`, `marketplace.json` descriptions, `docs/plans/2026-11-20-pilot-stage-4b-2-run.md` | documents |

Tasks 1, 2, 3 and 5 touch disjoint paths and can run in parallel. Task 4 follows 3 (same plugin). Task 6 follows 1, 3 and 5. Task 7 follows 4 and 6. Task 8 last.

---

### Task 1: `go_setup` writes the `Dockerfile`

**Files:**
- Modify: `.claude-plugin/plugins/aleogr-stack-go/skills/go_setup/SKILL.md`, that plugin's `plugin.json` (0.2.0) and its description in `marketplace.json`
- Test: scenarios `go-setup-*`

**Interfaces:**
- Produces: `go_setup` gains the optional argument `dockerfile=yes|no` (default `no`: today's behaviour, byte for byte). With `yes` it also handles `<path>/Dockerfile`: missing → written (`created`, or `would-create` in plan); present → never read for comparison, never overwritten. This holds for a component whose module already exists (the other files are still not touched). Output gains `dockerfile`: `written`, `would-write`, `present` or `not-asked`.

The file, exactly (`<version>` is the component's Go version, `major.minor`):

```dockerfile
# Generated by aleogr. Written once and never overwritten: it is yours to change.
FROM golang:<version> AS build
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /out/app .

FROM gcr.io/distroless/static-debian13:nonroot
COPY --from=build /out/app /app
USER nonroot:nonroot
ENTRYPOINT ["/app"]
```

(`go.sum*`: a module with no dependency has no `go.sum`. Base images are named by tag, not by digest: a pinned digest would stop security fixes, and nothing here updates pins. Facts, section 10.)

- [ ] **Step 1: Scenarios first**: `go-setup-dockerfile-new` (new component, `dockerfile=yes`: the four files, `FILE` pins the two `FROM` lines and `USER nonroot:nonroot`), `go-setup-dockerfile-existing-module` (module present, no `Dockerfile` → only the `Dockerfile` written), `go-setup-dockerfile-present` (a `Dockerfile` with other content → untouched, `present`), `go-setup-dockerfile-plan`. Existing `go-setup-*` unchanged and passing (`not-asked`).
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Change the skill.** Check that the generated `main.go` of today listens on `PORT`; if it does not, say so in the report and change nothing else (Task 8 records it).
- [ ] **Step 4: Run every `go-setup-*`.** If Docker is available, build the file once against a throwaway module and report the result; if not, say so.
- [ ] **Step 5: Commit** — scenarios first, then `Let go_setup write a component's Dockerfile`.

### Task 2: The reusable deploy workflow

**Files:**
- Create: `.github/workflows/deploy-cloud-run.yml`, `.github/workflows/self-test-deploy-cloud-run.yml`, `.github/testdata/deploy-cloud-run/check.sh`
- Modify: `.github/workflows/README.md`

**Interfaces:**
- Produces: a workflow called as `uses: <workflows>/.github/workflows/deploy-cloud-run.yml@<sha>` with inputs, all required strings: `working-directory`, `service`, `region`, `image` (`<image path>/<component>`, no tag), `project-id`, `workload-identity-provider`, `service-account`. No secrets, no outputs.

Requirements (facts, sections 5 to 8):
- `on: workflow_call` only. Top-level `permissions: contents: read, id-token: write`. One job, `runs-on: ubuntu-latest`, `timeout-minutes: 20`, `concurrency: { group: deploy-${{ inputs.service }}, cancel-in-progress: false }`.
- **First step: masks.** Inputs reach it through `env:`, never interpolated into a script. It registers `::add-mask::` for the project id, the service account, and the project number (the digits after `projects/` in the provider's path). No step before it; no step prints an input.
- Then: checkout (`persist-credentials: false`); `google-github-actions/auth` with `token_format: access_token`; `docker/login-action` on `<region>-docker.pkg.dev` as `oauth2accesstoken`; `docker/setup-buildx-action`; `docker/build-push-action` with `context` the working directory, `push: true`, the tag `<image>:<github.sha>`; `google-github-actions/setup-gcloud`; then one command, `gcloud run services update "$SERVICE" --project="$PROJECT" --region="$REGION" --image="$IMAGE@$DIGEST" --quiet`, with `DIGEST` the build step's `digest` output, refused by the script unless it matches `^sha256:[0-9a-f]{64}$`.
- Every action pinned by full commit SHA with its version in a comment (the five SHAs of the facts, section 6; confirm each resolves before using it).
- `check.sh` (bash, no dependency beyond `grep`) fails unless the file: has `workflow_call` as its only trigger; contains none of `pull_request_target`, `workflow_run`, `run deploy`, `--iap`, `allow-unauthenticated`, `add-iam-policy-binding`, `secrets.`; has every `uses:` pinned by 40 hexadecimal characters; has `::add-mask::` in the job's first step; contains `@$DIGEST` or the equivalent digest form and no `--image` with a tag. `self-test-deploy-cloud-run.yml` runs it on pull requests that touch these three files (trigger `pull_request` with `paths`, `permissions: contents: read`), as `self-test-ci-go.yml` does for its workflow.

- [ ] **Step 1: Write `check.sh` and run it against an empty file and against `ci-go.yml`: it fails on both.**
- [ ] **Step 2: Write the workflow; `check.sh` passes.** Run `actionlint` on both workflows if it can be installed; say if it cannot.
- [ ] **Step 3: Mutate the workflow five ways in a temporary copy (add `--iap`; unpin an action; move the mask to the second step; add `pull_request_target`; deploy by tag) and show `check.sh` failing on each.**
- [ ] **Step 4: README of the workflows folder: what the workflow does, its inputs, what its caller must grant.**
- [ ] **Step 5: Commit** — `Add the reusable workflow that deploys an image to Cloud Run`.

### Task 3: A service as declared

**Files:**
- Create: `.claude-plugin/plugins/aleogr-cloud-gcp/skills/gcp_deploy-describe/SKILL.md`, `gcp_deploy-setup/SKILL.md`
- Test: scenarios `deploy-describe-*`, `deploy-setup-*`

**Interfaces:**
- Produces: `gcp_deploy-describe projectId= project= region= components=<name>[,<name>…] maxInstances= cpu= memory= ciAccount=<e-mail of the CI account>`. Reads, per component, the service (`gcloud run services describe <project>-<name> --project --region --format=json`), and for an existing one its IAM policy and its account's IAM policy. Outputs `services`: a list of `{ "component", "exists", "asDeclared", "differences": [words from: account, scaling, size, public, login, agent, ci, labels], "placeholder" (the image is the hello sample), "url" }`; `missing`, `differing`, `waiting` (lists of component names; `waiting` = as declared and still the placeholder). A service that does not exist is not a failure. Status `unchanged` or `failed`. The allowed list is not read. "As declared" (facts, section 2): account `<project>-<name>@<projectId>.iam.gserviceaccount.com`; annotation `run.googleapis.com/iap-enabled` `true`; service-level maximum `maxInstances` and no minimum above 0; limits `cpu`/`memory`; no `allUsers` or `allAuthenticatedUsers` in the policy; the IAP agent as `roles/run.invoker`; the CI account as `roles/run.developer` on the service and `roles/iam.serviceAccountUser` on the account; the three labels.
- Produces: `gcp_deploy-setup` with the same arguments plus `environment=`, `placeholderImage=`, `mode=plan|apply`. Per component, in order, each only when missing or different: the account (`gcloud iam service-accounts create`); the service (one `gcloud run deploy <service> --image=<placeholderImage> --no-allow-unauthenticated --iap --service-account=… --min=0 --max=<maxInstances> --cpu= --memory= --cpu-throttling --labels=… --region --project --quiet`); for an existing service that differs, `gcloud run services update` with only the differing settings and **never `--image`**, `gcloud run services remove-iam-policy-binding` for a public member, `--iap` when the login is off; the two CI bindings; the active account as `roles/iap.httpsResourceAccessor` on the service (`gcloud iap web add-iam-policy-binding --resource-type=cloud-run`), when it is not there. A binding refused right after its account's creation is retried by the bounded poll. Outputs: `services` as in describe (after the changes), `urls` (`component` → address), `created`, `updated` (lists). Statuses `would-create`, `would-update`, `created`, `updated`, `unchanged`, `failed`.
- A failed `run deploy` is followed by one `describe`: the service may exist. If it exists, the run goes on repairing it (it was created with the login flags or not at all: the read decides; a service found without the login gets it before anything else and the answer says so). The skill never ends leaving an existing service unreported.

- [ ] **Step 1: Read facts sections 1 to 5 and 12; check every flag against `gcloud run deploy --help`, `gcloud run services update --help`, `gcloud iap web add-iam-policy-binding --help` on this machine.** Anything that differs from this plan is reported before writing.
- [ ] **Step 2: Scenarios first.** `deploy-describe-missing`, `-as-declared`, `-placeholder`, `-differs-public` (an `allUsers` invoker), `-differs-login-off`, `-differs-scaling`, `-refused`, `-invalid`; `deploy-setup-plan`, `-create` (two components: order account → service → bindings; pins of Review Focus 1 and 2; `NOT_CALLED projects add-iam-policy-binding`), `-create-failed-then-read`, `-existing-differs` (`NOT_CALLED --image`), `-public-closed`, `-unchanged` (no mutating call), `-binding-wait` (two refusals then accepted, `COUNT 2 ^sleep 30`), `-binding-wait-limit`, `-invalid` (a `<project>-<component>` longer than 30; a component ending with `-`).
- [ ] **Step 3: Run them; they fail.**
- [ ] **Step 4: Write the two skills.**
- [ ] **Step 5: Run the new scenarios and four existing GCP ones.**
- [ ] **Step 6: Commit** — scenarios first, then `Add the skills that describe and set up a project's services`.

### Task 4: Who gets in, and which workflow may act as CI

**Files:**
- Create: `.claude-plugin/plugins/aleogr-cloud-gcp/skills/gcp_access-grant/SKILL.md`
- Modify: `gcp_ci-identity-setup/SKILL.md`, the plugin's `plugin.json` (0.6.0) and its description in `marketplace.json`
- Test: scenarios `access-grant-*`, `ci-identity-*`

**Interfaces:**
- Produces: `gcp_access-grant projectId= project= region= components= person=<e-mail> mode=plan|apply`, or `list=yes` instead of `person`. `person` is one e-mail address of a person (validated: one `@`, no space, no `:`, not `allUsers`/`allAuthenticatedUsers`, not a `group:`/`serviceAccount:`/`domain:` form); the member is always `user:<person>`. For each component's service: read the policy (`gcloud iap web get-iam-policy --resource-type=cloud-run --service --region --project --format=json`), add `roles/iap.httpsResourceAccessor` when missing. Outputs `granted` (component names), `already` (names), and with `list=yes` `people` as a **count per component**, the addresses shown only in the answer's text, never in the result block. A missing service is `failed` naming the component. Statuses `would-update`, `updated`, `unchanged`, `failed`. There is no removal in this stage (the answer of `list=yes` gives the one `gcloud` command that removes a person).
- Produces: `gcp_ci-identity-setup` gains the required argument `workflow=<owner>/<name>/.github/workflows/<file>.yml`. The condition becomes the existing four clauses plus `&& assertion.job_workflow_ref.startsWith('<workflow>@')`; the mapping becomes `google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.job_workflow_ref=assertion.job_workflow_ref`, always sent whole. A provider that differs (the one of stage 4a does) is updated by the existing update path. (Facts, section 7: the text after `@` is not known for a workflow pinned by commit, so the clause stops at `@`.)

- [ ] **Step 1: Scenarios first.** `access-grant-plan`, `-apply` (two services, one already has the person → `granted` one, `already` one; `RESULT_NOT demo-user@example.com`), `-list` (counts in the block), `-invalid` (four bad `person` values, no command), `-service-missing`, `-refused`. `ci-identity-apply-workflow-condition` (new project: the clause and the mapping pinned in the create), `ci-identity-apply-update-4a-provider` (`update-oidc` called once with both, `NOT_CALLED providers create-oidc|providers delete`), `ci-identity-invalid-workflow`. Every existing `ci-identity-*` gets the argument and fixtures with the new condition so its expectations stand.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Write the skill; change the identity skill.**
- [ ] **Step 4: Run every `access-grant-*` and `ci-identity-*`.**
- [ ] **Step 5: Commit** — scenarios first, then `Add the grant of access to a person and bind the CI identity to the deploy workflow`.

### Task 5: Actions variables and the deploy jobs

**Files:**
- Create: `.claude-plugin/plugins/aleogr-repo-github/skills/github_variables-set/SKILL.md`
- Modify: `github_ci-setup/SKILL.md`, the plugin's `plugin.json` (0.6.0) and its description in `marketplace.json`
- Test: scenarios `gh-variables-*`, `gh-ci-setup-*`

**Interfaces:**
- Produces: `github_variables-set owner= name= variables=<NAME>=<value>[,…] mode=plan|apply`. Names match `^[A-Z][A-Z0-9_]{0,63}$`; values have no `,`, no line break and no `"`. One read (`gh variable list --repo <owner>/<name> --json name,value`), then one `gh variable set <NAME> --repo … --body "<value>"` per variable that is missing or differs. Outputs `set`, `already` (names only, never values in the result block). Statuses `would-update`, `updated`, `unchanged`, `failed`. It never deletes a variable and never touches one it was not given.
- Produces: `github_ci-setup` gains the optional argument `deploy=<environment>[,…]` (lowercase names; empty or absent: today's file and marker, byte for byte). With it:
  - the marker is `# aleogr-ci 2 <entries> deploy=<environments joined by ,>`;
  - after each component's job, one job per environment, exactly:

    ```yaml
      deploy-<name>-<environment>:
        needs: [<name>]
        if: github.event_name == 'push' && github.ref == 'refs/heads/<branch>' && needs.<name>.result == 'success'
        permissions:
          contents: read
          id-token: write
        uses: <workflows>/.github/workflows/deploy-cloud-run.yml@<sha>
        with:
          working-directory: "<path>"
          service: "<project>-<name>"
          region: ${{ vars.GCP_REGION }}
          image: ${{ vars.GCP_IMAGE_PATH }}/<name>
          project-id: ${{ vars.GCP_PROJECT_ID }}
          workload-identity-provider: ${{ vars.GCP_WIF_PROVIDER }}
          service-account: ${{ vars.GCP_CI_ACCOUNT }}
    ```

    `<project>` is a new required argument `project=` when `deploy` is given; the job `ci` and its `needs` are unchanged (deploy jobs are not part of the required check);
  - `<sha>` is one commit for every `uses:` line of the file. `ref=keep` keeps the pinned commit only when the existing file's marker is already of version 2; a version 1 file is pinned again at the head of `main` (its commit is older than the deploy workflow).
- With more than one environment the variables would clash: this stage accepts exactly one environment in `deploy` and fails on more, with one sentence.

- [ ] **Step 1: Scenarios first.** `gh-variables-plan`, `-apply` (five given, two differ → two `gh variable set`; `RESULT_NOT aleogr-dev-demo-ab12`), `-unchanged`, `-invalid`, `-refused`. `gh-ci-setup-deploy-jobs` (two components: the marker of version 2, both deploy jobs pinned by `FILE`, the `if:` line, `OUTPUT_NOT`/`FILE_NOT`-style pin that `pull_request_target|workflow_run` is absent, the `ci` job's `needs` without deploy jobs), `gh-ci-setup-deploy-from-v1` (a version 1 file with `ref=keep` → the head of `main` is read and pinned), `gh-ci-setup-deploy-keep-v2` (no read of the head), `gh-ci-setup-deploy-two-environments` (`failed`), `gh-ci-setup-deploy-plan`. Every existing `gh-ci-setup-*` passes unchanged.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Write the skill; change `github_ci-setup`.** Validate the YAML of one generated file (`python3 -c 'import yaml,sys; yaml.safe_load(open(sys.argv[1]))'` on a scenario's output, and `actionlint` if available).
- [ ] **Step 4: Run every `gh-variables-*` and `gh-ci-setup-*`.**
- [ ] **Step 5: Commit** — scenarios first, then `Add the Actions variables skill and the deploy jobs of ci.yml`.

### Task 6: The declaration's rule on names, and the plan's rows

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/defaults.json`, `skills/project-declare/SKILL.md`, `skills/project-plan/SKILL.md`
- Test: scenarios `project-declare-*`, `project-plan-*`

**Interfaces:**
- Consumes: Tasks 1, 3, 5.
- Produces: `defaults.json`: `project.services` gains `run.googleapis.com` and `iap.googleapis.com`; `project.deploy` is `{ "maxInstances": 2, "cpu": "1", "memory": "256Mi", "placeholderImage": "us-docker.pkg.dev/cloudrun/container/hello:latest" }`; `ci.deployWorkflow` is `deploy-cloud-run.yml`.
- Produces: "The declaration's rules" (both skills, identical): with environments, no component's name ends with `-`, and `<name of the project>-<name of the component>` has at most 30 characters.
- Produces: `project-plan`, when the declaration has environments:
  - `components`: `to generate` also when a component's `Dockerfile` is missing (`go_setup … dockerfile=yes mode=plan`);
  - `ci`: `github_ci-setup … deploy=<environment> project=<name>`; a version 1 file `differs`;
  - `ci identity`: passes `workflow=<workflowsRepository>/.github/workflows/<deployWorkflow>`;
  - after `ci identity`, the row `services`, from `gcp_login-describe projectId=<projectId>` then `gcp_deploy-describe`: `waits for the login` / `prepare the login` (the line under the table says `/aleogr:platform-plan`) when the login is not prepared or could not be read, and then `gcp_deploy-describe` is not invoked; `missing: <names>` / `create`; `differs: <names>` / `update`; `waiting for the first deploy: <names>` / `none` with a line under the table saying to merge the pull request or run the workflow again; `as declared` / `none`. While the environment or its APIs are missing: `follows the environment` / `follows the apis`, as the rows of stage 4a;
  - then the row `ci variables`, from `github_variables-set … mode=plan` with the five values built from the reads already made: `as declared` / `none`, `missing` or `differs` / `set`; `follows the ci identity` while that row has an action;
  - outputs gain `urls` (component → address, for existing services) and `ciVariables` extended to the five names.
- Without environments: no new row, no new read; every existing scenario of that kind passes unchanged.

- [ ] **Step 1: Scenarios first.** `project-declare-component-name-too-long`, `-component-ends-with-dash`; `project-plan-services-missing`, `-services-as-declared` (thirteen rows, `nothing to do`), `-services-waiting-first-deploy` (`unchanged`, action `none`, the line pinned), `-services-differs`, `-services-wait-login`, `-ci-version-1` (`ci` `differs`), `-dockerfile-missing`, `-variables-differ`. Existing `project-plan-environment-*` get the new fixtures (login prepared, services as declared, variables as declared, a version 2 file) so their expectations stand, each changed line listed in the report.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Change `defaults.json` and the two skills; prove "The declaration's rules" identical with a script.**
- [ ] **Step 4: Run every `project-declare-*` and `project-plan-*`; report each with its run count, and the form defect (a nested block before the table) if it shows.**
- [ ] **Step 5: Commit** — scenarios first, then `Give the project's plan its services and CI variables`.

### Task 7: The run, and the shortcut that lets a person in

**Files:**
- Modify: `.claude-plugin/plugins/aleogr/skills/project-apply/SKILL.md`, the plugin's `plugin.json` (0.11.0) and its description in `marketplace.json`
- Create: `.claude-plugin/plugins/aleogr/skills/project-access/SKILL.md`
- Test: scenarios `project-apply-*`, `project-access-*`

**Interfaces:**
- Consumes: Tasks 4 and 6.
- Produces: `project-apply`, in the environment part of a confirmed run, after the steps of stage 4a and in this order: APIs (existing step, now seven names, with the existing wait) → `gcp_ci-identity-setup` with `workflow=` → `gcp_deploy-setup` for all components in one invocation (skipped, with the pending item `login` whose `how` is `/aleogr:platform-plan`, when the plan's row is `waits for the login`) → `github_variables-set`. The files (`Dockerfile`s, `ci.yml` of version 2) go in the proposal the run already opens, made **after** the cloud steps when both are needed in the same run, so that a merge finds everything it needs. The answer adds, last before the result block, the address of each service, and, when a service still runs the placeholder, the line that the first merge deploys it.
- `project-apply` runs no command of its own beyond `sleep 30` (unchanged).
- Produces: `project-access person=<e-mail>` or `list=yes`, run in the project's folder: reads `.aleogr/project.json`, finds the project of each environment (`gcp_environment-describe`), invokes `gcp_access-grant … mode=apply` with the declaration's components. No `confirm`: granting a person access to a service behind the login costs nothing and is undone by one command, which its answer gives. It validates `person` itself before any skill. A declaration without environments: `failed`, one sentence.

- [ ] **Step 1: Scenarios first.** `project-apply-deploy-create` (ground of 4a present, nothing of 4b-2: `ORDER` services enable → identity update → deploy-setup → variables → the proposal; the two addresses in the answer; `updated`; the item saying to merge), `project-apply-deploy-from-4a` (Review Focus 7: marker version 1, no `Dockerfile`, provider without the clause, five APIs), `project-apply-deploy-after-merge` (services still on the placeholder, files merged → `unchanged`, `waiting for the first deploy` line), `project-apply-deploy-nothing` (`nothing to do`, addresses shown), `project-apply-services-wait-login` (`NOT_CALLED run deploy`), `project-apply-deploy-setup-failed` (the run stops, the proposal is not opened, no "apply again" on a guess). `project-access-grant`, `-list`, `-invalid`, `-no-environment`.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Change `project-apply`; write `project-access`.**
- [ ] **Step 4: Run every `project-apply-*` (two at a time) and `project-access-*`; report each with its run count and any form defect.**
- [ ] **Step 5: Commit** — scenarios first, then `Create the services in project-apply and add project-access`.

### Task 8: Documents and the run checklist

**Files:**
- Modify: `docs/DESIGN.md` (6.3 the service and its login as built; 6.x CI as the only deploy path and what it may do; 12 the plan's rows and the run; the declaration's rule; 17; 18), `docs/CONTRACTS.md` (`deploy-describe`, `deploy-setup`, `access-grant`, `variables-set`, the changed `ci-setup`, `ci-identity-setup`, `stack setup`), `docs/PROVIDER-FACTS.md` (from the facts file: each fact used, marked "read in the reference on 2026-11-20" or "seen in a real run"; what could not be verified, as such), `docs/cloud-shell.md`, `.claude-plugin/plugins/README.md`
- Create: `docs/plans/2026-11-20-pilot-stage-4b-2-run.md`

- [ ] **Step 1: Documents**, from the built files. Section 16 gains only real rejected alternatives (a fraction of a CPU; a separate `cd.yml`; a base image pinned by digest). Section 18 gains what stays open: whether service-level roles are enough for CI's update (proven or not by the first deploy); the form of `job_workflow_ref` for a workflow pinned by commit; that a service's settings changed by hand are repaired but its allowed list is never compared.
- [ ] **Step 2: The run checklist**, short: update the plugins; `/aleogr:project-plan` (expected rows); `/aleogr:project-apply confirm=yes` (expected: two services created, variables set, one pull request; the two addresses open "It's running" for the owner only); merge; watch the two deploy jobs; open the two addresses (each component's own page); `/aleogr:project-apply` → `nothing to do`; a pull request that changes one component deploys only that one after its merge and deploys nothing before it; `/aleogr:project-access person=<e-mail>` lets a second account in; cost check (`gcloud run services list`, minimum 0). Where the owner stops and why; what to send back without identifiers; a results table.
- [ ] **Step 3: Check every relative link, and that no identifier, e-mail or client id was written.**
- [ ] **Step 4: Commit** — `Document the deploy` and `Add the stage 4b-2 run checklist`.
