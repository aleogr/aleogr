# Reference project, stage 4b-2: checklist for the real run

For the owner, in Google Cloud Shell ([`cloud-shell.md`](../cloud-shell.md)), in the folder `~/pilot` that stage 4a left. It proves that `pilot`'s two components run on Cloud Run behind Google's login and that a merge deploys them: one `project-apply` creates the two services (with Google's sample page), the CI variables and a pull request; you merge it; CI builds and deploys each component; the services then show their own pages. Nothing of this has run against real Google Cloud or GitHub before: this run is the proof ([`DESIGN.md`](../DESIGN.md) section 18).

**Cost: none expected.** A service has no instance always on (minimum 0) and is billed by request; nobody but you uses these two, and requests the login refuses are not billed. There is no load balancer, and the login itself costs nothing. Images in the image repository stay far below the free 0.5 GB. CI runs on GitHub Actions, free on a public repository.

Source of truth: [`2026-11-19-pilot-stage-4b-design.md`](2026-11-19-pilot-stage-4b-design.md) (part 4b-2) and [`DESIGN.md`](../DESIGN.md) sections 4, 6.3, 6.4 and 12.

**Never paste in the conversation with Claude, nor in what you send back:** a service's address (it holds the project's number), the project's id or number, an e-mail, the CI account, a client id, a code, or what `gcloud auth list` or `gh auth status` print. Write `<id>` in their place. Send a screenshot only where a step asks for one, and only of what it names.

## What to have ready

- The pull request of stage 4b-2 is merged into `main` of `aleogr/aleogr`.
- `gcloud` and `gh` are signed in (`gcloud auth list` shows an active account; `gh auth status` a logged-in one, with `workflow` in its `Token scopes`: this run changes `.github/workflows/ci.yml`. Without it: `gh auth refresh -h github.com -s workflow`). Do not paste what they print.
- `~/pilot` is on `main` with no change of its own: `cd ~/pilot && git status` says `On branch main` and lists nothing as modified.
- For the terminal steps, paste this once in the Cloud Shell terminal, outside Claude Code (it prints nothing; paste it again if Cloud Shell reconnects):

  ```bash
  P=$(gcloud projects list --filter="labels.aleogr-project=pilot AND labels.aleogr-environment=dev" --format="value(projectId)")
  ```

- Optional, for step 9: a second Google account and a browser where you can open a private window.

When Claude Code asks for permission: allow the `gh`, `git` and `gcloud` commands it shows, `gh variable set` included, and `sleep 30` in the background (a skill waiting by itself); answer **"Yes, but ask again next time"** to the read of `defaults.json`. **Never allow**, and send the answer if it is proposed: anything with `--allow-unauthenticated`, `--no-iap`, `allUsers` or `allAuthenticatedUsers`; `gcloud projects add-iam-policy-binding`; `set-iam-policy`; any `delete` or `remove-iam-policy-binding`; `gh secret set`; `gh pr merge`; a push to `main`.

## Where you stop, and why

- **Step 4, before the merge:** the merge starts the first deploy, and its logs are public. Check the table first.
- **Step 5, before anything else:** the first deploy log is checked for the project's id and number. If either is there, everything stops: the repository is public.
- **Steps 5 and 9 are yours:** you merge on GitHub (never Claude Code), and the e-mail of step 9 is typed only in the Claude Code session in Cloud Shell, never in what you send back.

## 1. Update the plugins

In the terminal, outside Claude Code:

```bash
claude plugin marketplace update aleogr
```

```bash
for p in aleogr aleogr-cloud-gcp aleogr-db-gcp-cloud-sql aleogr-registry-gcp-artifact-registry aleogr-repo-github aleogr-stack-go; do claude plugin update "$p@aleogr"; done
```

Expected: `claude plugin list` shows, all enabled: `aleogr` 0.11.0, `aleogr-cloud-gcp` 0.6.0, `aleogr-db-gcp-cloud-sql` 0.4.1, `aleogr-registry-gcp-artifact-registry` 0.1.2, `aleogr-repo-github` 0.6.0, `aleogr-stack-go` 0.2.0.

## 2. The plan

```bash
cd ~/pilot && claude
```

```
/aleogr:project-plan
```

Expected: `status` `would-update`, thirteen rows. The first seven and `environment dev`:

| Item | State | Action |
|---|---|---|
| `repository` | `exists` | `none` |
| `settings` | `as declared` | `none` |
| `visibility` | `as declared` | `none` |
| `declaration` | `in the repository` | `none` |
| `components` | `to generate: admin, status` (no `Dockerfile` yet) | `generate` |
| `ci` | `as declared` (no service yet, so no deploy job is expected) | `none` |
| `protection` | `protected, requires ci` | `none` |
| `environment dev` | `exists` | `none` |

The last five, in one of two forms (both are right):

| Item | A: the spike's APIs are still on (most likely) | B: two APIs are off |
|---|---|---|
| `apis` | `enabled` / `none` | `to enable: 2` / `enable` (Cloud Run and IAP) |
| `registry` | `as declared` / `none` | `follows the apis` / `none` |
| `ci identity` | `differs` / `update` (the new workflow clause) | `follows the apis` / `none` |
| `services` | `missing: admin, status` / `create` | `follows the apis` / `none` |
| `ci variables` | `follows the ci identity` / `none` | `follows the apis` / `none` |

**Stop and send the answer** if `services` says `waits for the login` (the login of the organization reads as not prepared), or if any row says `fix by hand` or `needs attention`.

## 3. Apply

```
/aleogr:project-apply confirm=yes
```

It makes, in this order: (form B: the two APIs, then a plan); the CI identity's update (`update-oidc`, once); the two services `pilot-admin` and `pilot-status`, each with its own account, behind the login from its first command, with Google's sample page (two services, no fixed cost); the five CI variables; then a plan, then the two `Dockerfile`s and `ci.yml` with two deploy jobs, in one pull request titled `Add the Dockerfiles of admin, status and CI`. Some minutes; a `sleep 30` in the background may come (an account just created); allow it.

Expected answer, `status` `updated`:

- one line per skill, as `gcp_ci-identity-setup: updated`, `gcp-artifact-registry_access-grant: unchanged`, `gcp_deploy-setup: created`, `github_variables-set: updated`, two `go_setup: created`, `github_ci-setup: updated`, `github_pull-request-open: created` (form B adds `gcp_services-enable: updated`, and may add `Waited for the APIs enabled in this run: …`);
- the table of the plan made after the cloud: `components` `to generate: admin, status` / `generate`, `ci` `differs` / `generate`, `ci identity` `as declared` / `none`, `services` `waiting for the first deploy: admin, status` / `none`, `ci variables` `as declared` / `none`, the others `none`;
- the pull request's number and address, the item `pull request #<n> is open`;
- two lines `admin: https://…run.app` and `status: https://…run.app`, and the line that the first merge deploys them.

Then open each address in your browser, signed in as yourself: **Google's sample page, "It's running!"**. Then open one of them in a **private window**, not signed in: **Google's sign-in page**, not the page. Close the private window.

**Stop and send the answer** if the run stopped before the pull request, if it names a service "still open to anyone" or "still without the login", or if a page opens without the sign-in.

## 4. Before merging: check the table of step 3

The plan you would run now only says `proposed in pull request #<n>` / `merge it`, with every other row `not checked until the change is merged`: so the check is the table in step 3's answer, which was read after the cloud was made.

- `ci identity` must be `as declared`. **If it is `differs`, stop and send the answer, and do not merge:** Google may store the condition in another form than the one sent, and every plan would try to update it again.
- `services` must be `waiting for the first deploy: admin, status`, and `ci variables` `as declared`.

## 5. Merge, and check the first deploy's log

On GitHub, the pull request of step 3: its checks `ci / ci` green (the deploy jobs show as skipped on a pull request). **Squash and merge.**

Then open the repository's **Actions** tab, the run of `ci` on `main`. Expected: `changes`, `admin / go`, `status / go`, `deploy-admin-dev / deploy`, `deploy-status-dev / deploy`, `ci`, all green; the two deploy jobs take a few minutes.

**First thing**, open one deploy job's log. In the terminal, `echo "$P"` shows the project's id, and `gcloud projects describe "$P" --format="value(projectNumber)"` its number (do not paste either). Search the log (the search box at the top of the log) for the id, then for the number. **Neither must appear** (`***` is where they were masked). If either appears: **stop**, say so (without the value), and delete that run's logs at once: on the run's page, the `···` menu, **Delete all logs**; or in the terminal `gh run list --repo aleogr-sandbox/pilot --limit 3`, then `gh run delete <run id> --repo aleogr-sandbox/pilot`.

If a deploy job is red: send the name of the failed step and its error lines, with `<id>` in place of any identifier.

## 6. The components' own pages

Open the two addresses again, signed in. Expected: `admin: ok` and `status: ok` (each component's own page, not "It's running!"). If one still shows "It's running!" a minute after its deploy job ended green, send it.

## 7. Nothing to do

```
/aleogr:project-apply confirm=yes
```

Expected: `github_checkout-setup: updated` (the folder catches up with the merge), thirteen rows all `none` (`components`, `ci`, `services`, `ci variables` `as declared`; `protection` `protected, requires ci`), the line `nothing to do`, the two addresses, `status` `updated`. Then:

```
/aleogr:project-apply
```

Expected: `nothing to do`, `status` `unchanged`. If `services` says `waiting for the first deploy`, the deploy did not reach a service: stop and send.

## 8. A change to one component deploys only that one

On GitHub, in `aleogr-sandbox/pilot`: **Add file → Create new file**, name `status/NOTES.md`, any text; **Commit changes…**, choose **Create a new branch … and start a pull request**, then **Create pull request**.

Expected on the pull request: `status / go` runs, `admin / go` is skipped, no deploy job runs, `ci` green. **Squash and merge.** Expected on `main`: `deploy-status-dev / deploy` runs and is green, `deploy-admin-dev / deploy` is skipped. (The folder is now behind; the next `/aleogr:project-apply confirm=yes` updates it.)

## 9. A second person gets in (optional)

Skip it if no second Google account is at hand, and write "skipped" in the results.

1. In a private window, signed in with the second account, open the address of `admin`. Expected: "You don't have access".
2. In the Claude Code session in `~/pilot` (only there), type the second account's e-mail in place of `<e-mail>`:

   ```
   /aleogr:project-access person=<e-mail>
   ```

   Expected: `dev: updated`, both components let in, the sentence that the address must be a person's Google account, and the command that undoes it.
3. Wait a minute and reload the private window. Expected: `admin: ok`.

## 10. Cost check

In the terminal:

```bash
gcloud run services list --project="$P"
```

Expected: two services, `pilot-admin` and `pilot-status`, in `us-central1` (do not paste the URLs or the "deployed by" column). Then, for each:

```bash
for s in pilot-admin pilot-status; do echo "$s"; gcloud run services describe "$s" --region=us-central1 --project="$P" --format=json | grep -E 'minScale|maxScale|scalingMode|cpu-throttling'; done
```

Expected for each: `run.googleapis.com/maxScale` `"2"`; no `minScale` other than `"0"`; no `scalingMode` `manual`; `cpu-throttling` absent or `"true"`. Anything else: send these lines (they hold no identifier).

## If something differs

Stop at that step and send its whole answer (or the terminal's text), with every id, number, e-mail and address replaced by `<id>`.

## Results

| Step | Expected | Result |
|---|---|---|
| Ready | 4b-2 merged; `gcloud` and `gh` signed in, `workflow` scope; `~/pilot` clean on `main` | |
| 1. Plugins | the six versions above | |
| 2. Plan | thirteen rows, form A or B; `services` not `waits for the login` | |
| 3. Apply | `updated`; services created; variables set; one pull request; two addresses; "It's running!" signed in; sign-in page in a private window | |
| 4. Table of step 3 | `ci identity` `as declared`; `services` `waiting for the first deploy: admin, status`; `ci variables` `as declared` | |
| 5. Merge and log | all jobs green; the project's id and number absent from a deploy log | |
| 6. Pages | `admin: ok`, `status: ok` | |
| 7. Nothing to do | `updated` then `unchanged`, `nothing to do`, `services` `as declared` | |
| 8. One component | no deploy on the pull request; only `deploy-status-dev` after the merge | |
| 9. Second person | "You don't have access", then `admin: ok` (or skipped) | |
| 10. Cost | two services; maximum 2, minimum 0, billing by request | |
