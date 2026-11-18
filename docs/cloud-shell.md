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
claude plugin install aleogr-repo-github@aleogr
```

Check with `claude plugin list`: the four plugins, enabled.

`gh` (the GitHub command-line tool) is preinstalled but not signed in. Sign it in once, for the GitHub repository skills:

```bash
gh auth login --hostname github.com --git-protocol https --web
```

If it asks whether to authenticate Git with your GitHub credentials, answer yes. It shows a one-time code and an address: open the address, sign in to GitHub and **type the code in the browser**. The code is never pasted in the conversation with Claude. `gh auth status` then says an account is logged in.

## Daily use

1. Open Cloud Shell.
2. Start Claude Code in the work folder:

   ```bash
   cd ~/aleogr && claude
   ```

3. Type the skill, for example `/aleogr:platform-plan`.
4. When it asks to "allow this read outside the working directories" (the orchestrator reading its own `defaults.json`), choose **"Yes, but ask again next time"**. Do not choose the option that allows every read outside the working directory: the home directory holds the Google credentials.
5. `/exit` to leave.

The skills:

| Skill | What it does |
|---|---|
| `/aleogr:tools-check` | Checks that `gcloud` is installed and signed in. With `command=gh`, checks `gh` instead. Read-only. |
| `/aleogr:platform-plan` | Shows what the shared platform is missing. Read-only. |
| `/aleogr:platform-apply` | Creates what the plan lists. Asks once, stating any fixed cost. |
| `/aleogr-repo-github:github_repo-describe` | Shows a GitHub repository: visibility, settings, topics and whether `main` is protected. Read-only. |
| `/aleogr-repo-github:github_repo-create` | Creates a GitHub repository with a README, private unless told otherwise. Plan by default; `mode=apply` creates. An existing repository is never changed. |
| `/aleogr-repo-github:github_repo-configure` | Corrects the given settings of an existing repository, its visibility included. Plan by default; `mode=apply` changes. |
| `/aleogr-repo-github:github_branch-protect` | Protects `main` with the ruleset `main`. Plan by default; `mode=apply` writes. Says `pending` when the GitHub plan does not allow it (a private repository of a free organization). |

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
claude plugin update aleogr-repo-github@aleogr
```

A plugin that is new in the catalog is installed instead (`claude plugin install <plugin>@aleogr`, as in "Set-up, once"). Each update says "Restart to apply changes": start a new `claude` session afterwards. `claude plugin list` shows the versions.

## What to expect

- It is slower than the Windows app: a full `platform-plan` took about two minutes.
- Cloud Shell disconnects after a while idle; open it again and repeat "Daily use". Nothing installed is lost.
- The Google Cloud skills and the GitHub repository skills work here. `gh` is preinstalled (2.104.0, seen on 2026-11-17) and signed in once with `gh auth login` (above). When the skills of another family exist, its command-line tool is signed in here with only the permissions those skills need (Cloudflare: an API token limited to editing the DNS of the zone `aleogr.dev`).
