# PROVIDER FACTS — how the providers behave

> **Facts, not decisions.** Each item describes how a provider behaves, whatever design is chosen. They were learned in practice in the previous lab, removed in November 2026 to start from scratch. Nothing here says how the lab must be built: decisions live in [DESIGN.md](DESIGN.md). Measured values carry the date they were measured; check them again before relying on them.

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

## GCP — Cloud Scheduler

- **Three jobs are free per billing account**, counted on the account and not on the project; each extra job costs US$ 0.10 per month (pricing page read on 2026-11-17).
- **A job can call a Google API with an OAuth token of a service account**, with no function in between, but only with the methods `DELETE`, `GET`, `HEAD`, `POST` and `PUT`: `gcloud scheduler jobs create http` and `update http` have no `PATCH` (SDK 570, checked on 2026-11-17). An API method that needs `PATCH` (such as the Cloud SQL Admin API's `instances.patch`, which starts and stops an instance) is called with `POST` and the header `X-HTTP-Method-Override: PATCH`; `PUT` would replace the whole resource. Not verified against the Cloud SQL Admin API until the first real run: `instance-create` proves it by stopping the new instance with the job.

## GCP — IAM and identities

- **IAM changes take a few minutes to propagate.** A command run right after a grant can still be refused.
- **An identity that creates a resource running as a service account needs `iam.serviceAccounts.actAs` on that account** (for example, a Cloud Scheduler job with an OAuth token). Administrator roles over service accounts do not include it.
- **A plan run by the project's owner hides missing permissions** of the identity that will really apply the change: the owner can read everything. Only a run as that identity shows what it lacks.
- **A project created seconds ago may refuse calls made on its behalf.** On 2026-11-16, `gcloud billing budgets list` with a new project as quota project (`--billing-project`) was denied right after the Budget API was enabled on it, and succeeded about a minute later.
- **Project IDs are permanent:** immutable, and a deleted ID is never available again. Limits: 6 to 30 characters, lowercase letters, digits and hyphens, starting with a letter.

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

## Claude Code

- **The desktop app (Windows, version 5.1231.2, seen on 2026-11-16) lists no plugin from a marketplace whose catalog is in a subfolder.** A marketplace declared in `extraKnownMarketplaces` with `path` is registered and downloaded (the catalog and the plugin folders are on disk), but the plugin browser shows it empty, "check for updates" fails, and installing a plugin from it reports that the plugin cannot be found.
- **`enabledPlugins` in settings does not install a plugin.** It only marks it as enabled; the plugin is installed from the plugin browser or with `claude plugin install`.
- **The `claude plugin` commands of the CLI ignore a marketplace declared only in settings**: `claude plugin marketplace list` does not show it and `claude plugin install` cannot find its plugins. Only a marketplace added with `claude plugin marketplace add` is usable from the CLI.
- **Plugin folders may live inside `.claude-plugin/`**, beside the catalog (`"source": "./.claude-plugin/plugins/<name>"`): the CLI (2.1.325) validates and installs them.
- **The desktop app does not register again a marketplace that was removed from its plugin browser**, even while `extraKnownMarketplaces` in settings still declares it (seen on 2026-11-16). It is added back in the plugin browser: the **+** button, "add from a repository".
- **"Add from a repository" in the desktop app accepts a branch** as `<owner>/<repo>#<branch>`, and a marketplace at the standard location with its plugin folders inside `.claude-plugin/` lists and installs its plugins there. Skill folders with an underscore in the name (`gcp_environment-create`) load on Windows.
- **In the desktop app on Windows, commands run in PowerShell, which splits an unquoted argument at its commas**: `--labels=a=1,b=2` reaches `gcloud` as separate arguments and is rejected; `--labels="a=1,b=2"` works.
- **The desktop app does not install the `claude` command-line tool**, and in PowerShell `gcloud` is a script (`gcloud.ps1`) that the default execution policy blocks; `gcloud.cmd` is not affected.
