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
mkdir -p ~/lab && cd ~/lab
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

Check with `claude plugin list`: the three plugins, enabled.

## Daily use

1. Open Cloud Shell.
2. Start Claude Code in the work folder:

   ```bash
   cd ~/lab && claude
   ```

3. Type the skill, for example `/aleogr:platform-plan`.
4. When it asks to "allow this read outside the working directories" (the orchestrator reading its own `defaults.json`), choose **"Yes, but ask again next time"**. Do not choose the option that allows every read outside the working directory: the home directory holds the Google credentials.
5. `/exit` to leave.

The skills:

| Skill | What it does |
|---|---|
| `/aleogr:tools-check` | Checks that `gcloud` is installed and signed in. Read-only. |
| `/aleogr:platform-plan` | Shows what the lab platform is missing. Read-only. |
| `/aleogr:platform-apply` | Creates what the plan lists. Asks once, stating any fixed cost. |

To start, stop or check the database, the workflow is quicker and needs no terminal: repository `aleogr/aleogr`, `Actions`, `self-lab-database`, `Run workflow`, then `start`, `stop` or `status`.

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

These update commands exist in Claude Code 2.1.326 but were not run in Cloud Shell yet.

## What to expect

- It is slower than the Windows app: a full `platform-plan` took about two minutes.
- Cloud Shell disconnects after a while idle; open it again and repeat "Daily use". Nothing installed is lost.
- Only the Google Cloud skills work here: other tools (`gh`, the Cloudflare one) are not signed in.
