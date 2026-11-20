# Using the skills from a browser (Google Cloud Shell)

How to run the `aleogr` skills against real Google Cloud from a computer where nothing can be installed. Why this path was chosen: [`DESIGN.md`](DESIGN.md) section 14.3. Tested on 2026-11-17.

Cloud Shell is the terminal of the Google Cloud console. It runs in the browser, is already signed in to the Google account, has `gcloud`, and is free.

## Set-up, once

Open <https://console.cloud.google.com> and click the terminal icon at the top right. Then paste, one command at a time:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

```bash
mkdir -p ~/aleogr && cd ~/aleogr
```

```bash
claude
```

Claude Code asks for a theme and a login: choose the Claude account with a subscription, open the address it shows, authorize, and paste the code back **in the terminal**. Then type `/exit`.

```bash
claude plugin marketplace add aleogr/aleogr
```

```bash
claude plugin install aleogr@aleogr
```

```bash
claude plugin install aleogr-cloud-gcp@aleogr
```

```bash
claude plugin install aleogr-db-gcp-cloud-sql@aleogr
```

```bash
claude plugin install aleogr-registry-gcp-artifact-registry@aleogr
```

```bash
claude plugin install aleogr-repo-github@aleogr
```

```bash
claude plugin install aleogr-stack-go@aleogr
```

Check with `claude plugin list`: the six plugins, enabled.

`gh` (the GitHub command-line tool) is preinstalled but not signed in. Sign it in once, for the GitHub repository skills:

```bash
gh auth login --hostname github.com --git-protocol https --web
```

If it asks whether to authenticate Git with your GitHub credentials, answer yes. It shows a one-time code and an address: open the address, sign in to GitHub and **type the code in the browser**. The code is never pasted in the conversation with Claude. `gh auth status` then says an account is logged in.

A push that adds a GitHub Actions workflow (`.github/workflows/ci.yml`, written when a project declares components) may be refused when the token lacks the scope `workflow` (a precaution, not yet confirmed by a real run): if `gh auth status` does not list `workflow` among the `Token scopes`, run `gh auth refresh -h github.com -s workflow` and type the code in the browser as above.

## Daily use

1. Open Cloud Shell.
2. Start Claude Code in the work folder:

   ```bash
   cd ~/aleogr && claude
   ```

3. Type the skill, for example `/aleogr:platform-plan`.
4. When it asks to "allow this read outside the working directories" (the orchestrator reading its own `defaults.json`), choose **"Yes, but ask again next time"**. Do not choose the option that allows every read outside the working directory: the home directory holds the Google credentials.
5. When it asks to run `sleep 30` in the background, allow it: it is a skill waiting by itself for something Google has just changed (an API just enabled, an account just created, a role just granted). It tries again every 30 seconds, 10 times at most, and the run goes on by itself.
6. `/exit` to leave.

## Preparing the login of the organization, once

Every service of every project is behind Google's login. The organization is owned by a personal Google account, so the login needs a custom OAuth client of the organization ([`DESIGN.md`](DESIGN.md) section 6.3). It is prepared once, for every project, and the platform's plan shows it as the row `login`:

1. Run `/aleogr:platform-apply confirm=yes` in `~/aleogr`. When the row `login` says `prepare`, it grants your account the role that changes the organization's login (`roles/iap.settingsAdmin`), turns on the IAP API in the shared project (both free), and ends with a `Login` section: a short list of what is left.
2. Do the two console steps of the list, in the shared project, with the values it gives: the consent screen `aleogr` (audience External; no logo; publish nothing) and the client `iap` of type Web application, with its redirect address. When the console shows the client's id and secret, copy both: the secret is shown only once.
3. Paste the list's one command in the Cloud Shell terminal, **outside Claude Code**. It asks for the client's id and then, without showing it, the secret: type them there. **Never paste the secret, or the client's id, in the conversation with Claude**: no skill needs it, and the command is the only place it goes. Google keeps it; nothing else does.
4. Run `/aleogr:platform-plan`: the row `login` says `prepared` (and, when nothing else is missing, the plan says `nothing to do`).

On the owner's organization this was done by hand on 2026-11-19, during the spikes of stage 4b. The plan's read of the login is counted against the shared project, whose IAP API may still be off: the row `login` can then read `not prepared` / `prepare`. In that case `/aleogr:platform-apply confirm=yes` turns that API on (and grants your account the role when it lacks it; both free), reads the login again, finds it, and ends with `login` `prepared` and no `Login` section: there is nothing to click. The run of stage 4b-1 checks which of the two the owner sees.

## Working in a project folder

The `project-*` skills work on the declaration `.aleogr/project.json` of the folder Claude Code was started in. Each project has its own folder, created once, new and empty:

```bash
mkdir ~/<project> && cd ~/<project> && claude
```

On later days: `cd ~/<project> && claude`. Claude Code asks once whether to trust the folder: yes. Writing `.aleogr/project.json` and the `gh` and `git` commands the skills show are allowed when asked; the read of the orchestrator's `defaults.json` is answered **"Yes, but ask again next time"**, as above. The folder becomes a git checkout of the project's repository when `project-apply` sends the declaration; it never changes the machine's git configuration.

Once the repository exists, a change to the project takes three steps:

1. Edit the declaration with `/aleogr:project-declare`, then run `/aleogr:project-apply confirm=yes`: it proposes the change as a pull request and shows its address. The folder is back on `main` and shows the merged state again; the change lives in the pull request.
2. Merge the pull request on GitHub, with the normal button. Claude Code is never asked to merge, and the skills never merge. Do not declare another change while the pull request is open: after the merge, the folder could not be updated over it.
3. Run `/aleogr:project-apply confirm=yes` again: it brings the folder up to date and applies the merged change.

Claude Code is not asked to open the pull request or to update the folder by hand: `project-apply` does both.

A component (a folder of the repository with its own program) is declared the same way, one per call, for example `/aleogr:project-declare component=status stack=go` (its folder is `status`, its Go version the default; `path=` and `version=` change them). The next `/aleogr:project-apply confirm=yes` writes its starting point (`status/go.mod`, `status/main.go`, `status/main_test.go`) and the project's CI file `.github/workflows/ci.yml` in the folder, and proposes them with the declaration in one pull request; the project's CI runs on that pull request. The starting point is written once: a folder that already has a `go.mod` is never touched. After the merge, the next `/aleogr:project-apply confirm=yes` updates the folder and makes the protection of `main` require the check `ci`: from then on, a pull request whose CI fails cannot be merged. CI needs the organization to allow actions and reusable workflows from other repositories: on GitHub, the organization's `Settings`, `Actions`, `General`, `Policies`, where the default, `Allow all actions and reusable workflows`, is enough. A repository has one open pull request of the tooling at a time; while it is open, `project-apply` only says to merge it. To drop a proposal, close its pull request on GitHub; to make it again, declare the change again.

The environment `dev` (the project's own GCP project, its APIs, its Docker image repository and the keyless identity its CI will use) is declared the same way, once: `/aleogr:project-declare environment=dev`, plus `cloudRoot=tst` for a project that tests the tooling, whose GCP project goes in the folder `dev` inside the folder `tst` (the skills never create folders: a missing one stops the run, which says which folder to create). The next `/aleogr:project-apply confirm=yes` proposes the declaration by pull request, whose description says that applying it after the merge creates a Google Cloud project, whose id is permanent; after the merge, one more `/aleogr:project-apply confirm=yes` updates the folder, says `This run creates the GCP project of dev, whose id is permanent.`, creates the ground, waits by itself while the APIs it has just enabled still refuse, and ends with `nothing to do`. Nothing is deployed, nothing is written to GitHub, and nothing of it has a cost. These skills need `gcloud` signed in as well as `gh`: Cloud Shell is, and a declaration without `environments` never runs `gcloud`. The identifiers they print (the GCP project id and number, the CI account's e-mail) are not secrets, but are not pasted anywhere either.

The skills:

| Skill | What it does |
|---|---|
| `/aleogr:tools-check` | Checks that `gcloud` is installed and signed in. With `command=gh`, checks `gh` instead. Read-only. |
| `/aleogr:platform-plan` | Shows what the shared platform is missing, and whether the login of the organization is prepared (the row `login`). Read-only. |
| `/aleogr:platform-apply` | Creates what the plan lists, then prepares the login as far as a command can and prints what is left of it (see "Preparing the login of the organization, once"). Without `confirm=yes` it changes nothing and shows the command that confirms, stating any fixed cost. |
| `/aleogr:project-declare` | Writes or edits the project's declaration, `.aleogr/project.json` in the current folder. A new one needs `name`, `owner` and `description`, for example `/aleogr:project-declare name=pilot owner=aleogr-sandbox visibility=public description="Reference project of aleogr: status pages per tenant"`. `component=<name> stack=go` adds a component; `environment=dev` adds the environment `dev` (and the cloud, from the defaults), `cloudRoot=tst` marks a project that tests the tooling. Changes nothing on GitHub. |
| `/aleogr:project-plan` | Compares the declaration with GitHub: a table of `repository`, `settings`, `visibility`, `declaration` and `protection`, each with its state and action, plus `components` and `ci` when components are declared (`generate` when a starting point or `ci.yml` is to be written). The `declaration` row also says whether a change is waiting in this folder (`propose`), in a pull request (`merge it`), or on GitHub while this folder is behind (`update`), and whether the folder needs attention (`fix the folder`). With the environment `dev` declared, four more rows: `environment dev`, `apis`, `registry` and `ci identity`, read in Google Cloud once the declaration is merged; `fix by hand` there is the owner's to do. Read-only. |
| `/aleogr:project-apply` | Does what the plan lists, then plans again and says `nothing to do`. A change in this folder, and the files it generates, are proposed as one pull request instead; after the merge, the next run updates the folder and applies it. One confirmation for the whole run: `confirm=yes`, or `confirmVisibility=public` when the plan makes the repository public. Without it, it changes nothing and shows the text that confirms. With the environment `dev` merged, the same `confirm=yes` creates its ground in Google Cloud (GCP project, APIs, image repository and its cleanup policy, CI identity and its push access), in the run that updates the folder, announcing the GCP project before it creates it; where an API it has just enabled still refuses, it waits and tries again by itself. Nothing with a cost, nothing deployed. |
| `/aleogr-repo-github:github_repo-describe` | Shows a GitHub repository: visibility, settings, topics and whether `main` is protected. Read-only. |
| `/aleogr-repo-github:github_repo-create` | Creates a GitHub repository with a README, private unless told otherwise. Plan by default; `mode=apply` creates. An existing repository is never changed. |
| `/aleogr-repo-github:github_repo-configure` | Corrects the given settings of an existing repository, its visibility included. Plan by default; `mode=apply` changes. |
| `/aleogr-repo-github:github_branch-protect` | Protects `main` with the ruleset `main`; with `checks=ci` the ruleset also requires the check `ci`. Plan by default; `mode=apply` writes. Says `pending` when the GitHub plan does not allow it (a private repository of a free organization). |
| `/aleogr-repo-github:github_checkout-setup` | Makes the current folder a checkout of the repository and sends the declaration as its first content after the README, only while the repository has that one commit; after a merge, brings a folder that is behind up to date. Plan by default; `project-apply` calls it. |
| `/aleogr-repo-github:github_pull-request-open` | Proposes named files by pull request: commits only them on a new branch `aleogr/change-<random>`, pushes it, opens the pull request and returns the folder to `main`. One open at a time per repository; never merges. Plan by default; `project-apply` calls it. |
| `/aleogr-repo-github:github_ci-setup` | Writes the project's CI file, `.github/workflows/ci.yml`, from the declared components: one job per component and a last job `ci`. Never commits or pushes. Plan by default; `project-apply` calls it. |
| `/aleogr-cloud-gcp:gcp_login-describe` | Says whether the login of the organization is prepared. Read-only; shows no client id. `platform-plan` calls it. |
| `/aleogr-cloud-gcp:gcp_login-setup` | Prepares the login as far as a command can (the role, the IAP API) and prints the console steps and the one command left. Never sees the client's secret. Plan by default; `platform-apply` calls it. |
| `/aleogr-cloud-gcp:gcp_ci-identity-setup` | Creates the keyless identity a repository's CI uses in a project's GCP project: the service account `<project>-ci`, the pool `github` and its provider `github`, which accept only that repository's default branch. No key, no project role. Plan by default; `project-apply` calls it. |
| `/aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_registry-describe` | Shows the project's image repository: where it is, its cleanup policy and who may push. Read-only. |
| `/aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_repository-create` | Creates the project's Docker image repository in its GCP project, in the declared region. Plan by default; `project-apply` calls it. |
| `/aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_cleanup-configure` | Sets the repository's cleanup policy: keep the 5 most recent versions of each image, delete the rest, dry-run off. Plan by default; `project-apply` calls it. |
| `/aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_access-grant` | Lets the CI account push to the repository (writer on that repository only). Plan by default; `project-apply` calls it. |
| `/aleogr-stack-go:go_setup` | Writes the starting point of a Go component (`go.mod`, `main.go`, `main_test.go`) in its folder, once, only when the folder has no `go.mod` and no Go file. Plan by default; `project-apply` calls it. |

The GitHub skills take `key=value` arguments after the name, for example `/aleogr-repo-github:github_repo-describe owner=aleogr-sandbox name=pilot`. A value with spaces or commas goes in double quotes. Nothing becomes public without `confirmVisibility=public`: without it the skill changes nothing, says so and shows the command that confirms.

To start, stop or check the database, the workflow is quicker and needs no terminal: repository `aleogr/aleogr`, `Actions`, `self-shared-database`, `Run workflow`, then `start`, `stop` or `status`.

The workflow reads three repository secrets: `GCP_SHARED_PROJECT_ID`, `GCP_SHARED_WIF_PROVIDER` and `GCP_SHARED_SWITCH_ACCOUNT`. `/aleogr:platform-apply` prints their values in its `GitHub secrets` section whenever the database switch is ready (running it again shows them again and changes nothing). Paste each one in the repository on GitHub: `Settings`, `Secrets and variables`, `Actions`, `New repository secret`. When the workflow says a secret is missing, this is the step to repeat.

## After a change is merged

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
claude plugin update aleogr-db-gcp-cloud-sql@aleogr
```

```bash
claude plugin update aleogr-registry-gcp-artifact-registry@aleogr
```

```bash
claude plugin update aleogr-repo-github@aleogr
```

```bash
claude plugin update aleogr-stack-go@aleogr
```

A change to the project skills needs only the first command and the updates of `aleogr@aleogr`, `aleogr-cloud-gcp@aleogr`, `aleogr-registry-gcp-artifact-registry@aleogr`, `aleogr-repo-github@aleogr` and `aleogr-stack-go@aleogr`; updating the others as well does no harm. A plugin that is new in the catalog is installed instead (`claude plugin install <plugin>@aleogr`, as in "Set-up, once"). Each update says "Restart to apply changes": start a new `claude` session afterwards. `claude plugin list` shows the versions.

## What to expect

- It is slower than the Windows app: a full `platform-plan` took about two minutes.
- Cloud Shell disconnects after a while idle; open it again and repeat "Daily use". Nothing installed is lost.
- The Google Cloud skills, the Artifact Registry skills and the GitHub repository skills work here. `gh` is preinstalled (2.104.0, seen on 2026-11-17) and signed in once with `gh auth login` (above). When the skills of another family exist, its command-line tool is signed in here with only the permissions those skills need (Cloudflare: an API token limited to editing the DNS of the zone `aleogr.dev`).
