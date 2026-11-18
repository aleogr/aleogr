# PROVIDER FACTS — how the providers behave

> **Facts, not decisions.** Each item describes how a provider behaves, whatever design is chosen. They were learned in practice in the previous lab, removed in November 2026 to start from scratch. Nothing here says how anything must be built: decisions live in [DESIGN.md](DESIGN.md). Measured values carry the date they were measured; check them again before relying on them.

## GCP — Cloud SQL

- **It does not scale to zero.** An instance is charged by the hour while it runs, whether or not anybody uses it. In the previous lab it was 96% of the bill (billing report of 21 August – 19 September 2026): about R$ 0.06 per instance-hour for `db-f1-micro` and about R$ 1 per GiB-month of disk; one instance running all month with 10 GiB cost about R$ 55.
- **A stopped instance costs its disk AND its public IPv4 address:** US$ 0.01 per hour "while idle" (pricing page read on 2026-11-17). That "idle" means "stopped" is a reading of the page, to confirm on the first bill. It runs no automated backup and keeps no transaction log for the stopped hours. A backup window that falls inside the stopped hours means no backups at all, with no error; point-in-time recovery can only target a moment the instance was running.
- **Starting a stopped instance is slow:** 686 seconds (about 11.5 minutes) from the start command to accepting connections, measured on 2026-09-21 on `db-f1-micro`.
- **Shared-core tiers (`db-f1-micro`) only exist in the `ENTERPRISE` edition.** When the edition is not stated, the API picks `ENTERPRISE_PLUS` and refuses the tier.
- **`db-f1-micro` allows 25 connections**, three of them reserved for superusers: 22 for applications, to be divided among everything that shares the instance.
- **Disks grow and never shrink.** Automatic growth without a limit turns one runaway write into a permanent cost.
- **IAM is per GCP project, not per database.** Any identity allowed to manage users or databases in the instance's project can do it to every database in the instance. Between databases of the same instance, the only separation is PostgreSQL's own grants (for example, `CONNECT` revoked from `PUBLIC`).
- **Users created through the API or `gcloud sql users create` belong to `cloudsqlsuperuser`** and can grant themselves back what was revoked. Grants inside a shared instance protect against accidents, not against deliberate action.
- **Roles are cluster-wide.** A generic role name (`migrator`) collides as soon as a second database shares the instance.
- **No predefined role fits "may create its own database and users, but cannot change the instance".** `roles/cloudsql.editor` cannot create users; `roles/cloudsql.admin` can also delete and reconfigure the instance. A custom role is needed for that boundary.
- **Starting and stopping an instance requires `cloudsql.instances.update`**, the same permission that resizes the disk and turns deletion protection off. There is nothing narrower.
- **A public IP with no authorized networks accepts no direct connection.** Access then goes through the Cloud SQL connector, authenticated by IAM (`roles/cloudsql.client`; IAM database users also need `roles/cloudsql.instanceUser` and the flag `cloudsql.iam_authentication`).
- **`gcloud sql instances create` and `patch` have no flag for the storage growth limit nor for labels** (SDK 570, checked on 2026-11-17). The disk size is the only bound, and the instance is found by its name.
- **The newest PostgreSQL major version of Cloud SQL is 18** (the documentation page lists it as the default, read on 2026-11-17). The API value `POSTGRES_18` is inferred from the naming pattern of the earlier versions (`POSTGRES_17`, ...): to confirm at the first creation.
- **Seen in the first real run (2026-11-17), instance `db-f1-micro`, PostgreSQL 18, `ENTERPRISE`, `us-central1`:** the tier exists for that version and edition, and `POSTGRES_18` is the API value; creating the instance took about 8.5 minutes; stopping it took about a minute; starting it took about 9 minutes; describing an instance that does not exist fails with a message that says so, which separates "missing" from "no permission".
- **Right after a start is accepted, the instance already reads as running** (activation policy `ALWAYS`, state `RUNNABLE`) while it still takes minutes to accept connections: the instance's own fields give no "starting" state. The unfinished `UPDATE` operation of the start (`gcloud sql operations list --filter="status!=DONE"`, or the API's `operations?instance=`) is what tells the two apart: on 2026-11-17 the workflow showed `starting` right after a start and `running` some minutes later. An identity with only `cloudsql.instances.get` and `cloudsql.instances.update` may list those operations.
- **A new instance is integrated with Knowledge Catalog by default** (seen in the console on 2026-11-17): technical metadata (names of databases and tables, not data) is extracted periodically. The documentation (read on 2026-11-17) says storing that metadata has no charge and that the extraction uses some CPU of the instance. It is turned off with `--no-enable-dataplex-integration` (the integration's former name), on `gcloud sql instances create` and `patch`; the patch was applied to the running shared instance on 2026-11-17 and took effect at once.

## GCP — Cloud Scheduler

- **Three jobs are free per billing account**, counted on the account and not on the project; each extra job costs US$ 0.10 per month (pricing page read on 2026-11-17).
- **A job can call a Google API with an OAuth token of a service account**, with no function in between, but only with the methods `DELETE`, `GET`, `HEAD`, `POST` and `PUT`: `gcloud scheduler jobs create http` and `update http` have no `PATCH` (SDK 570, checked on 2026-11-17). An API method that needs `PATCH` (such as the Cloud SQL Admin API's `instances.patch`, which starts and stops an instance) is called with `POST` and the header `X-HTTP-Method-Override: PATCH`; `PUT` would replace the whole resource. Not verified against the Cloud SQL Admin API until the first real run: `instance-create` proves it by stopping the new instance with the job.
- **`POST` with `X-HTTP-Method-Override: PATCH` is honoured by the Cloud SQL Admin API through Cloud Scheduler:** on 2026-11-17 a job created that way, run with `gcloud scheduler jobs run`, stopped a running instance.

## GCP — IAM and identities

- **IAM changes take a few minutes to propagate.** A command run right after a grant can still be refused.
- **An identity that creates a resource running as a service account needs `iam.serviceAccounts.actAs` on that account** (for example, a Cloud Scheduler job with an OAuth token). Administrator roles over service accounts do not include it.
- **A plan run by the project's owner hides missing permissions** of the identity that will really apply the change: the owner can read everything. Only a run as that identity shows what it lacks.
- **A project created seconds ago may refuse calls made on its behalf.** On 2026-11-16, `gcloud billing budgets list` with a new project as quota project (`--billing-project`) was denied right after the Budget API was enabled on it, and succeeded about a minute later.
- **Project IDs are permanent:** immutable, and a deleted ID is never available again. Limits: 6 to 30 characters, lowercase letters, digits and hyphens, starting with a letter.

## GCP — organizations

- **A standalone organization (no domain) is created automatically** when a Google account signs up to Google Cloud, and only one per user account; a user can be invited to own several. There is no way to create a second one from the same account without a domain (Google's documentation, read on 2026-11-17).
- **An organization's display name is not used by any API**, and an organization owner edits it on the "Organization details" page (documentation read on 2026-11-17). The IAM settings page of the console says an organization cannot be renamed (seen on 2026-11-17). My standalone organization was renamed that day, and nothing that had been built needed any change.
- **A folder is renamed with `gcloud resource-manager folders update <id> --display-name=<name>`** (its id does not change), and `gcloud resource-manager folders list --organization=<id>` lists only the folders directly under the organization, not the ones inside them (2026-11-17).
- **A deleted project stays recoverable for 30 days** (`gcloud projects undelete`), and its id is never available again. A Cloud SQL instance with deletion protection must have it turned off (`gcloud sql instances patch --no-deletion-protection`) before `gcloud sql instances delete` (2026-11-17).

## GCP — organization policies

A recent organization comes with a set of security policies already enforced. Seen in my organization on 2026-11-15 (25 active), the ones that affect how projects are built:

- **Service account keys cannot be created or uploaded** (`iam.disableServiceAccountKeyCreation`, `iam.disableServiceAccountKeyUpload`), nor API keys bound to service accounts. Anything outside GCP reaches it through identity federation, never with a key file.
- **Default service accounts get no automatic roles** (`iam.automaticIamGrantsForDefaultServiceAccounts`). A service that runs as the default account of Compute Engine or Cloud Run starts with no permissions: each service needs its own service account with explicit roles.
- **Cloud Build has no default service account of its own** and uses the Compute Engine one (`cloudbuild.disableCreateDefaultServiceAccount`, `cloudbuild.useComputeServiceAccount`), which, by the previous item, has no roles. A deploy from source (`gcloud run deploy --source`) builds through Cloud Build and fails until that is set up explicitly.
- **Buckets only accept uniform access** (`storage.uniformBucketLevelAccess`): permissions per bucket, no per-object ACLs.
- **Domain-restricted sharing was NOT active** (`iam.allowedPolicyMemberDomains` not in the list): a Cloud Run service can be made public (`allUsers`).
- A legacy constraint and its `managed` successor can coexist (for example, `iam.disableServiceAccountKeyCreation` active and `iam.managed.disableServiceAccountKeyCreation` inactive); one of them active is enough.
- Creating folders needs `roles/resourcemanager.folderCreator`, and changing policies needs `roles/orgpolicy.policyAdmin`; the organization administrator role includes neither.

## GCP — Terraform provider (google 8.x)

- **`activation_policy` of `google_sql_database_instance` is filled in with `ALWAYS` when absent.** An apply while the instance is stopped starts it again, unless the field is under `ignore_changes`.
- **`google_project_service` disables the API when the resource is removed**, unless `disable_on_destroy = false` and `deletion_policy = "ABANDON"` are both set.
- **Terraform cannot create the bucket that stores its own state**, nor grant itself the access it needs to that bucket: both exist before the first apply.

## GCP — Cloud Run

- **Domain mappings use one DNS record per hostname**, a `CNAME` to `ghs.googlehosted.com`, with a Google-managed certificate. In the previous lab every hostname was mapped explicitly; there was no wildcard.

- **IAP can be enabled directly on a Cloud Run service, without a load balancer** (documentation read on 2026-11-16). Requests are authenticated with a Google account before they reach the container; access is granted with the role `roles/iap.httpsResourceAccessor`. It replaces the caller's identity, so anything that calls the service with its own authentication (for example, Pub/Sub) may fail behind it.
- **Cloud Run charges only while a service is handling requests**, with a monthly free tier; any public address is found by bots (issued certificates are published in public logs) and every visit wakes the service.

## Cloudflare

- **An unproxied record lets the destination issue the certificate** (GitHub Pages and Cloud Run domain mappings both did).
- **Cloudflare accepts a `CNAME` beside other records at the same name** (for example, a `TXT`). The general DNS rule forbids it, so another DNS provider may refuse.

## GitHub

- **GitHub Pages with a custom subdomain uses a `CNAME` record** to `<owner>.github.io`; `A` records are for an apex domain. Certificate issuance usually takes minutes, sometimes hours, and needs the record to stay unproxied.
- **A GitHub Pages site of a public repository is public**, whatever the audience it was written for.
- **Scheduled workflows are delayed under load**, routinely by minutes. They are not suitable for anything that must happen at an exact time.
- **Workload identity federation works from a manually triggered workflow with no key:** with `google-github-actions/auth` and `token_format: access_token`, a workflow of `aleogr/aleogr` on `main` got a token as the switch service account and called the Cloud SQL Admin API (2026-11-17). A whole run takes 5 to 10 seconds, about a minute when it waits for a stop.
- **A private repository of an organization on the free plan has no rulesets: GitHub refuses even the read of them** (2026-11-18, `gh api repos/<owner>/<name>/rulesets` on a new private repository of a free organization). `github_branch-protect` took the refusal as the plan limit and ended `pending` in `plan` and in `apply`, writing nothing. The same repository, made public, accepted the ruleset at once.
- **A new repository of a free organization is born with** merge commit, squash and rebase on, delete branch on merge off, issues and projects on, and — while private — **wiki off** (the free plan has no wiki on private repositories). The wiki stayed off after the repository was made public.
- **`gh repo create <owner>/<name> --private --add-readme` gives a repository whose default branch `main` exists**, so a ruleset that requires pull requests never meets an empty repository (2026-11-18).
- **A ruleset made by hand in the web page and one sent through the API from a file compare as equal** on target, enforcement, bypass actors, the `~DEFAULT_BRANCH` condition and the three rules; the web page adds parameters the file does not have (`required_reviewers`, `require_extra_approval_for_unattributed_changes`), which the comparison ignores (2026-11-18, `aleogr/aleogr`).
- **`gh auth login --web` in Cloud Shell cannot open the browser or copy the code**: it prints the one-time code and the address `https://github.com/login/device`, which is opened by hand; the terminal waits and finishes by itself once the code is typed in the browser (2026-11-18).
- **Each GitHub skill took 5 to 20 seconds in Cloud Shell** (2026-11-18), against about two minutes for a full `platform-plan`.

## Claude Code

- **The desktop app (Windows, version 5.1231.2, seen on 2026-11-16) lists no plugin from a marketplace whose catalog is in a subfolder.** A marketplace declared in `extraKnownMarketplaces` with `path` is registered and downloaded (the catalog and the plugin folders are on disk), but the plugin browser shows it empty, "check for updates" fails, and installing a plugin from it reports that the plugin cannot be found.
- **`enabledPlugins` in settings does not install a plugin.** It only marks it as enabled; the plugin is installed from the plugin browser or with `claude plugin install`.
- **The `claude plugin` commands of the CLI ignore a marketplace declared only in settings**: `claude plugin marketplace list` does not show it and `claude plugin install` cannot find its plugins. Only a marketplace added with `claude plugin marketplace add` is usable from the CLI.
- **Plugin folders may live inside `.claude-plugin/`**, beside the catalog (`"source": "./.claude-plugin/plugins/<name>"`): the CLI (2.1.325) validates and installs them.
- **The desktop app does not register again a marketplace that was removed from its plugin browser**, even while `extraKnownMarketplaces` in settings still declares it (seen on 2026-11-16). It is added back in the plugin browser: the **+** button, "add from a repository".
- **"Add from a repository" in the desktop app accepts a branch** as `<owner>/<repo>#<branch>`, and a marketplace at the standard location with its plugin folders inside `.claude-plugin/` lists and installs its plugins there. Skill folders with an underscore in the name (`gcp_environment-create`) load on Windows.
- **In the desktop app on Windows, commands run in PowerShell, which splits an unquoted argument at its commas**: `--labels=a=1,b=2` reaches `gcloud` as separate arguments and is rejected; `--labels="a=1,b=2"` works.
- **The desktop app does not install the `claude` command-line tool**, and in PowerShell `gcloud` is a script (`gcloud.ps1`) that the default execution policy blocks; `gcloud.cmd` is not affected.
- **Google Cloud Shell has `gh` preinstalled** (version 2.104.0, seen on 2026-11-17), not signed in.
- **Claude Code runs inside Google Cloud Shell** (2026-11-17, version 2.1.326, default machine): the native installer puts it in `~/.local/bin`, which is not on the `PATH` until added to `~/.bashrc`; the login is the usual browser flow with a code pasted in the terminal; `claude plugin marketplace add` and `claude plugin install` work; the skills ran `gcloud` with the account Cloud Shell is signed in to. A full `platform-plan` took about two minutes, noticeably slower than the desktop app. `claude plugin marketplace update` and `claude plugin update` work there. During a full `platform-apply`, Claude Code put the wait for the new instance in a background shell, ended its turn, and resumed by itself when the instance was ready; the whole run took about half an hour. Reading a file of a plugin (`defaults.json`) counts as a read outside the working directory and asks for permission.
- **In the desktop app, a marketplace is updated from its `···` menu in the plugin browser**; after that the new plugins of the catalog appear with a `+`, and an installed plugin whose version changed asks to be updated (seen on 2026-11-17). A new session is needed to use them.
- **A later layout of the desktop app moved those controls** (seen on the evening of 2026-11-17): the plugins are under **Plugins** in the sidebar; the marketplaces are under **Add → Manage marketplaces**, and each one has a `···` menu with "Check for updates" and "Delete". The page of an installed plugin shows its version and an "Update" button, which stays disabled until the marketplace has been checked for updates; the `···` menu of an installed plugin only offers "Delete". Deleting the plugins, checking the marketplace for updates and installing them again brought the new versions.
- **In Cloud Shell, an installed plugin's files are under `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`** (2026-11-18): that is the folder a skill writes in place of `${CLAUDE_PLUGIN_ROOT}`, and a new version gets a new folder.
- **A model following a skill does not always capture a command's exit code reliably**: in one run of `github_repo-create` it reported that its own capture printed 0 for a failed `gh api` call and relied on the `HTTP 404` line instead (2026-11-18). The conclusion was right; skills that decide by exit code should also name the text that identifies the case.
- **The PowerShell quoting of a value with `&&` and single quotes inside double quotes** (`--attribute-condition="assertion.repository=='<owner>/<repo>' && assertion.ref=='refs/heads/main'"`) reached `gcloud` intact in the desktop app (2026-11-17).
