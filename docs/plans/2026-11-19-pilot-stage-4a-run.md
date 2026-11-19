# Reference project, stage 4a: checklist for the first real run

For the owner. Run this in Google Cloud Shell ([`cloud-shell.md`](../cloud-shell.md)), in the project folder `~/pilot` that stage 3c-2 left. It gives `pilot` the environment `dev` and its ground on Google Cloud: you declare the environment, `project-apply` proposes the declaration in a pull request, you merge it, and the next `project-apply` creates the GCP project of `pilot` in the folder `dev` inside the folder `tst`, enables its APIs, creates its Docker image repository with a cleanup policy, and creates the keyless identity that the repository's CI will use to push images. Nothing is deployed and nothing but the declaration reaches GitHub. The last steps are a plan that says `nothing to do` and a look at the result in the Google Cloud console.

**Nothing here costs money.** A GCP project, its APIs, a service account, a workload identity pool and an empty image repository are free (Artifact Registry charges only for storage above 0.5 GB, and nothing is pushed). The shared database is not touched and stays stopped. The pull request runs the project's CI on GitHub Actions, free on a public repository.

Source of truth: [`2026-11-19-pilot-stage-4-design.md`](2026-11-19-pilot-stage-4-design.md) (part 4a), [`2026-11-19-pilot-stage-4a.md`](2026-11-19-pilot-stage-4a.md) and [`DESIGN.md`](../DESIGN.md) sections 4, 6.4, 11.6 and 12.

How to read each step: type the text in the box exactly as it is, in the Claude Code session of the folder `~/pilot` (you may write to Claude in Portuguese, but the skill text is typed as written). Every skill ends with an `aleogr-result` block; its `status` line, and the table the `project-*` skills print (item, state, action), are what to compare with **Expected**. Write what you saw in the table of [section 6](#6-results) as you go.

**The identifiers this run prints are not pasted anywhere.** The new GCP project's id and number, the CI account's e-mail, the organization's, the folders' and the billing account's ids appear on the screen while the skills run. They are not secrets, but the repository is public and they are never written in it: in what you send back, replace each one with `<projectId>`, `<number>` or `<id>`, and the CI account with `pilot-ci@<projectId>`.

When Claude Code asks for permission:

- to edit `.aleogr/project.json`: allow it (**Yes**);
- to run a `gh` or `git` command it shows: allow it (**Yes**), except the ones listed under "Never allow" below;
- to run a `gcloud` command it shows (reads such as `describe`, `list`, `get-iam-policy`, `auth list`, `--version`; and, in step 9 only, `projects create`, `billing projects link`, `services enable`, `artifacts repositories create`, `artifacts repositories set-cleanup-policies`, `iam service-accounts create`, `iam workload-identity-pools create`, `iam workload-identity-pools providers create-oidc`, `iam service-accounts add-iam-policy-binding` and `artifacts repositories add-iam-policy-binding`): allow it (**Yes**);
- to run `ls -1Ap -- admin/` or `ls -1Ap -- status/` (the Go skill looking into a component's folder), the short command that makes the 6 random characters of a branch name (in bash, it starts with `LC_ALL=C tr -dc 'a-z0-9'`), or the one that makes the 4 random characters of the GCP project's id: allow it (**Yes**);
- to wait about a minute (`sleep 60` or similar) before trying a binding once more, in step 9: allow it (**Yes**);
- to read a file outside the working directory (the orchestrator reading its own `defaults.json`, or the registry skill reading its `cleanup-policy.json`): choose **"Yes, but ask again next time"**.

**Never allow**, and send the answer if Claude Code proposes it: `gcloud iam service-accounts keys create` (no key ever exists), `gcloud projects add-iam-policy-binding` (the CI account gets no role on the project), `gcloud resource-manager folders create` (the skills never create folders), any `gcloud … delete`, `remove-iam-policy-binding` or `set-iam-policy`, `set-cleanup-policies` with `--dry-run`, `gh variable set`, `gh secret set`, `gh pr merge`, `gh auth setup-git`, a `git config` without `--local`, a commit on `main`, or a push to `main`.

The skills never wait for an answer: when one needs a confirmation, it ends `pending`, changes nothing, and shows the exact text that confirms it. You confirm by running that text. **You merge the pull request yourself, on GitHub, with the normal button. Never ask Claude Code to merge it.**

## Before you start

- The pull request of stage 4a is **merged into `main`** of `aleogr/aleogr`.
- **`gcloud` is signed in.** In the Cloud Shell terminal (outside Claude Code), `gcloud auth list` shows one account marked as active (`*`). Do not paste what it prints anywhere. If none is active, run `gcloud auth login` and follow what it says.
- **`gh` is signed in.** In the same terminal, `gh auth status` says an account is logged in to `github.com`. Do not paste what it prints anywhere. If it is not, sign in again as in "Set-up, once" of [`cloud-shell.md`](../cloud-shell.md). This run pushes no workflow file, so the scope `workflow` is not needed this time.
- **The folder `dev` exists inside the folder `tst`.** The skills never create folders: when it is missing, step 9 stops and says which folder to create. It was created on 2026-11-17, so it is expected to be there. To look:
  1. Open <https://console.cloud.google.com/cloud-resource-manager> (the menu **IAM & Admin**, then **Manage resources**).
  2. In the resource picker at the top of the page, choose the organization. The page lists the folders directly under it: `dev` and `tst`, and the shared project outside them.
  3. Click the arrow next to `tst`: it has a folder `dev`. (A project of `pilot` should not be in it yet. If one whose name is `dev pilot` is there already, stop and say so.)

  If `tst` has no folder `dev`, create it:
  1. On the same page, click **Create folder**.
  2. **Folder name**: `dev`.
  3. **Location** (or **Destination**): click **Browse** and choose the folder `tst` (not the organization: a folder `dev` directly under the organization already exists, for real projects).
  4. Click **Create**. Look again: `tst` now has `dev`.

  If **Create folder** is not offered or the creation is refused, your account lacks the role **Folder Creator** on the organization (the organization's administrator role does not include it): in **IAM & Admin**, **IAM**, with the organization chosen, grant yourself that role, then try again.
- **The folder `~/pilot` is on `main` with no change of its own.** In the terminal (outside Claude Code):

  ```bash
  cd ~/pilot && git status
  ```

  Expected: the first line is `On branch main`, and nothing is listed as modified (a list under `Untracked files:` is fine, as long as `.aleogr/project.json` and nothing under `admin/`, `status/` or `.github/` is in it).

  - If the first line names another branch: run `git switch main`, then `git status` again.
  - If `.aleogr/project.json` is listed as modified, or `git status` says the folder is ahead of `origin/main`, or anything else is unclear: stop and send what it printed (it holds no secret).

## 1. Update the plugins

In the Cloud Shell terminal, outside Claude Code (type `/exit` first if a session is open), run one command at a time:

```bash
claude plugin marketplace update aleogr
```

```bash
claude plugin update aleogr@aleogr
```

```bash
claude plugin update aleogr-cloud-gcp@aleogr
```

```bash
claude plugin update aleogr-repo-github@aleogr
```

The Artifact Registry plugin is new, so it is installed, not updated:

```bash
claude plugin install aleogr-registry-gcp-artifact-registry@aleogr
```

Then `claude plugin list` shows, all enabled: `aleogr` at version `0.9.0`, `aleogr-cloud-gcp` at `0.4.0`, `aleogr-registry-gcp-artifact-registry` at `0.1.0`, `aleogr-repo-github` at `0.5.0`, `aleogr-stack-go` at `0.1.0`, and `aleogr-db-gcp-cloud-sql` as it was. Plugins are loaded when a session starts: the session of the next section is new, so nothing else is needed.

## 2. The run

Do the steps in order, in one Claude Code session. If a status or a table differs from **Expected**, stop there and send the whole answer of that skill (see [section 5](#5-what-to-send-back)). The plans that read Google Cloud are slower than before: a minute or two each.

### Step 1. Start in the project folder

In the terminal:

```bash
cd ~/pilot && claude
```

Expected: Claude Code starts in `~/pilot`.

### Step 2. Plan: nothing to do

```
/aleogr:project-plan
```

Expected: `status` `unchanged`, the line `nothing to do`, and the table of the end of stage 3c-2, seven items:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `as declared` | `none` |
| `visibility` | `as declared` | `none` |
| `declaration` | `in the repository` | `none` |
| `components` | `as declared` | `none` |
| `ci` | `as declared` | `none` |
| `protection` | `protected, requires ci` | `none` |

The declaration has no environment yet, so no `gcloud` command runs: if Claude Code asks to run one in this step, answer **No** and send the answer.

### Step 3. Declare the environment `dev`

```
/aleogr:project-declare environment=dev cloudRoot=tst
```

Expected: `status` `updated`, the changed keys `cloud` and `environments.dev`, and the file it shows now ends with:

```json
    { "name": "status", "stack": "go", "path": "status", "version": "1.27" }
  ],
  "cloud": { "provider": "gcp", "region": "us-central1", "root": "tst" },
  "environments": { "dev": {} }
}
```

The provider and the region come from `defaults.json`; `"root": "tst"` says that `pilot` tests the tooling, so its GCP project goes inside the folder `tst`. Everything else in the file is as before. No command runs, and nothing happens on GitHub or in Google Cloud.

### Step 4. Plan: the declaration to propose

```
/aleogr:project-plan
```

It now also invokes `tools-check` for `gcloud` (`gcloud --version` and `gcloud auth list …`), right after the one for `gh`. Nothing else is read in Google Cloud: the declaration with the environment is not in the repository yet.

Expected: `status` `would-update` and this table, eleven items:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `not checked until the change is merged` | `none` |
| `visibility` | `not checked until the change is merged` | `none` |
| `declaration` | `changed here` | `propose` |
| `components` | `as declared` | `none` |
| `ci` | `as declared` | `none` |
| `protection` | `not checked until the change is merged` | `none` |
| `environment dev` | `not checked until the change is merged` | `none` |
| `apis` | `not checked until the change is merged` | `none` |
| `registry` | `not checked until the change is merged` | `none` |
| `ci identity` | `not checked until the change is merged` | `none` |

Under the table: one item has an action, and `project-apply` makes it.

### Step 5. Apply without the confirmation

```
/aleogr:project-apply
```

Expected: `status` `pending`, nothing changed, the table of step 4, and one `pending` item, `confirm`, whose text is `/aleogr:project-apply confirm=yes`. No pull request exists: <https://github.com/aleogr-sandbox/pilot/pulls> shows none open. If one was opened, stop and send the answer.

### Step 6. Apply, confirmed: propose the declaration

```
/aleogr:project-apply confirm=yes
```

It shows the first plan (the table of step 4), then `aleogr-repo-github:github_pull-request-open` with the eight tooling paths (`.aleogr/project.json`, `.github/workflows/ci.yml` and the three files of each component) and the title `Change the project declaration`. Only the declaration changed, so only it is committed. As before, it sets this folder's commit identity, brings `main` up to date, creates a branch `aleogr/change-` followed by 6 random characters, commits, pushes that branch, opens the pull request and returns the folder to `main`.

Expected: `status` `updated`, a pull request address `https://github.com/aleogr-sandbox/pilot/pull/<N>`, and one `pending` item, `pull request #<N> is open`, whose text is `merge https://github.com/aleogr-sandbox/pilot/pull/<N>, then run /aleogr:project-apply confirm=yes`. No `gcloud` command beyond the `tools-check` of the plan runs, and there is no last plan in this run.

Check that the folder is back on `main`, in Claude Code (a line that starts with `!` runs in the terminal):

```
!git branch --show-current
```

Expected: `main`. `.aleogr/project.json` has no `cloud` and no `environments` again: that is the merged state; the change is in the pull request.

### Step 7. Look at the proposal

Open the pull request's address in the browser: **Files changed** shows one file, `.aleogr/project.json`, with the two lines `cloud` and `environments` added (and a comma after the `]` of `components`); **Commits** shows one commit, `Change the project declaration`.

### Step 8. CI, then merge on GitHub

On the pull request's page, within a few minutes the workflow `ci` shows:

- `changes` green;
- `admin / go` and `status / go` **skipped** (the pull request touches neither component's folder nor `ci.yml`);
- `ci` green, marked **Required**.

When `ci` is green: **Merge pull request** (or **Squash and merge**), then **Confirm merge**. Do this on GitHub only; never ask Claude Code to merge. The merge is a push to `main`, so `ci` runs once more there, with the same jobs skipped and `ci` green.

### Step 9. Apply after the merge: the ground

```
/aleogr:project-apply confirm=yes
```

This run takes several minutes. It prints four plans (five if a just-enabled API keeps refusing for a moment, see [section 4](#4-if-something-goes-wrong)): the first one, the one after the folder's update, the one after the APIs are on, and the last one. Expected, in this order:

1. The first plan, seven items (this folder's declaration has no environment yet: the merge is not in the folder):

   | Item | State | Action |
   |---|---|---|
   | `repository` | `exists` | `none` |
   | `settings` | `not checked until the change is merged` | `none` |
   | `visibility` | `not checked until the change is merged` | `none` |
   | `declaration` | `this folder is behind` | `update` |
   | `components` | `not checked until the change is merged` | `none` |
   | `ci` | `not checked until the change is merged` | `none` |
   | `protection` | `not checked until the change is merged` | `none` |

2. `aleogr-repo-github:github_checkout-setup owner=aleogr-sandbox name=pilot mode=apply head=check` updates the folder (`git … pull --ff-only origin main`): expected `updated`.
3. A new plan, from the merged declaration, eleven items: the seven of step 2 as they were there, then:

   | Item | State | Action |
   |---|---|---|
   | `environment dev` | `missing` | `create` |
   | `apis` | `follows the environment` | `none` |
   | `registry` | `follows the environment` | `none` |
   | `ci identity` | `follows the environment` | `none` |

   It looked the GCP project up by its labels (`gcloud projects list --filter=…`) and found none; nothing else is read in Google Cloud.
4. `aleogr-cloud-gcp:gcp_environment-create project=pilot environment=dev mode=apply root=tst`: it finds the organization, the folder `tst`, the folder `dev` inside it and the billing account, creates the project `aleogr-dev-pilot-` followed by 4 random characters, named `dev pilot`, with the labels `aleogr-project=pilot` and `aleogr-environment=dev`, in that folder, links billing and checks both. Expected `created`.
5. `aleogr-cloud-gcp:gcp_services-enable projectId=<projectId> services=cloudresourcemanager.googleapis.com,artifactregistry.googleapis.com,iam.googleapis.com,iamcredentials.googleapis.com,sts.googleapis.com mode=apply`: one `gcloud services enable …` with the APIs that are off (normally all five), then the list of enabled APIs. Expected `updated`.
6. A plan again, eleven items, now reading inside the new project: `environment dev` `exists` / `none`, `apis` `enabled` / `none`, `registry` `missing` / `create`, `ci identity` `missing` / `create` (the rows above them as in the plan of 3).
7. `aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_repository-create projectId=<projectId> project=pilot environment=dev region=us-central1 mode=apply`: creates the repository `pilot` (`--repository-format=docker`, `--location=us-central1`, the two labels) and reads it back. Expected `created`, with the image path `us-central1-docker.pkg.dev/<projectId>/pilot`.
8. `aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_cleanup-configure projectId=<projectId> project=pilot region=us-central1 keep=5 mode=apply`: `gcloud artifacts repositories set-cleanup-policies pilot … --policy=<plugin folder>/files/cleanup-policy.json --no-dry-run`, then reads it back. Expected `updated`, with `keep` `5` and `dryRun` `false`.
9. `aleogr-repo-github:github_repo-describe owner=aleogr-sandbox name=pilot`: reads the repository's numeric ids and its default branch. Expected `unchanged`.
10. `aleogr-cloud-gcp:gcp_ci-identity-setup projectId=<projectId> project=pilot repository=aleogr-sandbox/pilot repositoryId=<number> ownerId=<number> branch=main mode=apply`: reads the project number, then creates the service account `pilot-ci`, the pool `github`, the provider `github` (`create-oidc` with the issuer `https://token.actions.githubusercontent.com` and the condition on `aleogr-sandbox/pilot`, its two numeric ids and `refs/heads/main`) and the binding that lets the repository's tokens act as the account, in that order, then reads everything back. The binding may be refused once right after the account's creation: the skill then waits about a minute and tries once more. Expected `created`, condition `as-declared`, no other member, and the three CI variables (`GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT`) with their values: identifiers, not secrets, written nowhere in this stage.
11. `aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_access-grant projectId=<projectId> project=pilot region=us-central1 identity=pilot-ci@<projectId>.iam.gserviceaccount.com role=push mode=apply`: grants `roles/artifactregistry.writer` on the repository `pilot` (never on the project) and reads it back. Expected `updated`, `granted` `true`.
12. The last plan: the table of step 10 and the line `nothing to do`, then the line `Nothing is deployed yet: the CI identity can only push images to the image repository.`

The run ends with `status` `updated` and `pending` `[]`. Note how long it took.

### Step 10. Everything is as declared

```
/aleogr:project-plan
```

Expected: `status` `unchanged`, the line `nothing to do`, and eleven items:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `as declared` | `none` |
| `visibility` | `as declared` | `none` |
| `declaration` | `in the repository` | `none` |
| `components` | `as declared` | `none` |
| `ci` | `as declared` | `none` |
| `protection` | `protected, requires ci` | `none` |
| `environment dev` | `exists` | `none` |
| `apis` | `enabled` | `none` |
| `registry` | `as declared` | `none` |
| `ci identity` | `as declared` | `none` |

Its result block has `environment` with the name `dev` and the project's id, and `ciVariables` with the three values.

### Step 11. Look at it in the Google Cloud console

Look only; change nothing. Write yes or no for each point in the results; do not paste any id, number or e-mail you see there.

1. **The project in its folder.** <https://console.cloud.google.com/cloud-resource-manager>, the organization chosen: under `tst`, then `dev`, a project named `dev pilot` whose id starts with `aleogr-dev-pilot-`. Choose it in the resource picker; on its **Dashboard** or in **IAM & Admin**, **Settings**, its labels are `aleogr-project: pilot` and `aleogr-environment: dev`; in **Billing**, it is linked to the billing account.
2. **The image repository.** With that project chosen, **Artifact Registry**, **Repositories**: one repository, `pilot`, format **Docker**, location `us-central1`, empty. Open it, then **Edit repository** (or its details): the cleanup policies are two, `keep-most-recent` (keep the 5 most recent versions) and `delete-the-rest` (delete, tag state any), and the policy is **not in dry run** (the console offers a choice like "Dry run" or "Delete artifacts": the second is selected). Leave the page without saving. On the repository's **Permissions** (the info panel or the **Permissions** tab), `pilot-ci` has **Artifact Registry Writer**.
3. **The CI identity.** **IAM & Admin**, **Workload Identity Federation**: one pool, `GitHub` (id `github`), enabled, with one provider, `github`, of type OIDC, enabled. Open the provider: the issuer is `https://token.actions.githubusercontent.com`, and the attribute condition reads `assertion.repository=='aleogr-sandbox/pilot' && assertion.repository_id=='…' && assertion.repository_owner_id=='…' && assertion.ref=='refs/heads/main'` (two numbers in place of `…`). **IAM & Admin**, **Service Accounts**: `pilot-ci`, whose **Keys** tab lists no key. **IAM & Admin**, **IAM**, for the project: `pilot-ci` has no role there.

## 3. What the new rows mean

The plan has four more rows, after `protection`, only while the declaration in this folder has `environments`: eleven rows then (with components), seven otherwise. After the proposing run of step 6 the folder is back on `main`, whose declaration has no environment until the merge reaches the folder, so the first plan of step 9 shows seven rows.

- **`environment dev`**: the GCP project of `pilot` in `dev`. `exists` / `none`; `missing` / `create`; `billing not linked` / `repair` (`project-apply` links it).
- **`apis`**: the five APIs of `project.services` in `defaults.json`. `enabled` / `none`; `to enable: <n>` / `enable`.
- **`registry`**: the image repository `pilot` in `us-central1`. `as declared` / `none`; `missing` / `create`; `cleanup differs` / `configure` (the policy is not the two rules with 5, or is in dry run); `in another region` / `fix by hand` (a repository `pilot` exists in another region only: a repository has one region, and the tooling never deletes it).
- **`ci identity`**: the service account `pilot-ci`, the pool `github` and its provider. `as declared` / `none`; `missing` / `create`; `differs` / `update` (the provider's condition names another repository, id or branch: `project-apply` replaces it whole); `cannot push` / `grant` (the account is not a writer of the repository); `needs attention` / `fix by hand` (a pool or provider deleted or disabled, or a pool that holds another provider: the sentence under the table says what to do).
- Shared states: `not checked until the change is merged` while the declaration is being changed (nothing is read in Google Cloud), `follows the environment` while the GCP project is missing or has no billing (nothing can be read inside it), and `follows the apis` while an API is off (Artifact Registry and IAM refuse every command until then).
- **`fix by hand`** is never made by `project-apply` and is never `nothing to do`: the owner does what the line under the table says, then plans again.

## 4. If something goes wrong

- Nothing in this run costs money (see the top). If a skill states a fixed cost or asks to confirm one, stop and send the answer.
- **The folder is missing** (step 9.4: `gcp_environment-create` ends `failed`, saying that the folder `dev` inside `tst`, or `tst` itself, must be created first): nothing was created in Google Cloud. The run ends `updated` (the folder was updated) with the item `environment dev`. Create the folder as in "Before you start", then run `/aleogr:project-apply confirm=yes` again: its first plan shows `environment dev` `missing` / `create` and the run goes on from there.
- **An API is still refused right after it was enabled**: a just-enabled API can refuse calls for about a minute. The plan after the APIs reads GitHub first, which is usually wait enough; if that plan fails, the run plans once more (the fifth plan). If it still fails, the run ends `updated` with an item `verify` or `registry` or `ci identity`: wait a minute and run `/aleogr:project-apply confirm=yes` again. What was created stays, and the next plan shows what is left.
- **The new GCP project is not found yet** (the plan after the APIs still says `environment dev` `missing`, or `apis` `to enable`): the run ends `updated` with an item whose text is `/aleogr:project-apply confirm=yes`. Wait a minute and run it.
- **The binding of the CI identity is refused twice** (step 9.10 ends `created` with a `pending` item `binding`): the account, the pool and the provider stay. Wait a few minutes and run `/aleogr:project-apply confirm=yes` again; the next plan shows `ci identity` `missing` / `create`, and only the binding is made.
- **A run prints a plan and stops without going on** (a table, sometimes with a skill's `aleogr-result` block, and nothing after it), or **a nested skill's block is printed before a plan's table**: run the same command again. The plan reads what exists, so the run goes on from where things are. A plan that prints another skill's block before its table, with the right rows and status after it, is a known defect of the answer's form (about one plan in five that read Google Cloud): note it in the results and go on.
- **`gcloud` is not signed in** (the plan ends `failed` with the item `gcloud`, before any row): run `gcloud auth login` in the terminal, or open a new Cloud Shell tab, then run the step again.
- **A row says `fix by hand` or `needs attention`**: the skills never act on it, and neither should Claude Code. Send the whole answer before doing anything by hand; the line under the table says what is to be done.
- **`gcp_environment-create` ends `pending`** (the project was created, but its billing could not be linked or checked): the run ends `updated`, and the item's text is the command that finishes it. Send the answer (with the identifiers replaced) before running it.
- **A second `project-apply` while the pull request is open** changes nothing: it ends `pending`, with `proposed in pull request #N` / `merge it`. Merge it (step 8), then run `/aleogr:project-apply confirm=yes`. If it still says `merge it` right after the merge, wait a few seconds and run it again.
- **The Cloud Shell session closes in the middle of step 9**: open it again, `cd ~/pilot && claude --continue`, and run `/aleogr:project-apply confirm=yes`: the plan shows where things are.
- If a skill says `gh` is not logged in, sign it in again as in "Set-up, once" of [`cloud-shell.md`](../cloud-shell.md) and run the step again.

## 5. What to send back

Replace every identifier as said at the top (`<projectId>`, `<number>`, `<id>`, `pilot-ci@<projectId>`) before sending.

- The table of [section 6](#6-results), filled in.
- The answer of every step whose status or table differed from **Expected** (the text and the `aleogr-result` block).
- The whole answer of step 9, whatever it said: it shows each part of the ground created, and how the plans read it.
- Whether step 9.10 retried the binding (yes or no), and how long step 9 took.
- The yes or no of each point of step 11.
- The full text of any error, from any step. Never paste the code of `gh auth login`, a token, or what `gh auth status` and `gcloud auth list` print.

What the run shows goes into [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md) (above all the answers of `gcloud` that were written from its reference: [`DESIGN.md`](../DESIGN.md) section 18), and whatever failed becomes a fix in the skills.

## 6. Results

| Step | What you should see | Result |
|---|---|---|
| Before you start | stage 4a merged; `gcloud` and `gh` signed in; the folder `dev` inside `tst`; `~/pilot` on `main`, clean | |
| 1. Update the plugins | `aleogr` 0.9.0, `aleogr-cloud-gcp` 0.4.0, `aleogr-registry-gcp-artifact-registry` 0.1.0, `aleogr-repo-github` 0.5.0 | |
| 2. Plan | `unchanged`, `nothing to do`, seven items, no `gcloud` | |
| 3. Declare the environment | `updated`, `cloud` and `environments.dev`, `"root": "tst"` | |
| 4. Plan | `would-update`; `changed here` / `propose`; the four new rows `not checked until the change is merged` | |
| 5. Apply, no confirmation | `pending`, item `confirm`, no pull request | |
| 6. Apply, confirmed | one pull request with the declaration only, `updated`, folder on `main` | |
| 7. Look at the proposal | one file, one commit `Change the project declaration` | |
| 8. CI and merge | `changes` and `ci` green, `admin / go` and `status / go` skipped; merged | |
| 9. Apply after the merge | folder updated; `created`, `updated`, `created`, `updated`, `unchanged`, `created`, `updated`; four plans; `nothing to do`; `updated` | |
| 10. Plan | `unchanged`, `nothing to do`, eleven items | |
| 11. Console | project `dev pilot` in `tst/dev` with its labels; repository `pilot` with the two cleanup rules, not in dry run, `pilot-ci` writer; pool and provider with the condition; no key; no project role | |
