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

- **A deleted workload identity pool or provider is only soft-deleted: it keeps its id for 30 days** (`state` `DELETED`), and creating one with the same id fails until it is restored (`gcloud iam workload-identity-pools undelete`, `gcloud iam workload-identity-pools providers undelete`) (SDK 570 reference and API definitions, read on 2026-11-19; not yet seen in a real run). `providers list` leaves soft-deleted providers out unless `--show-deleted` is given.
- **A pool or provider can be disabled without being deleted**: the API has a separate field `disabled`, so a disabled provider is expected to keep the state `ACTIVE` while it accepts no token. The `update` and `update-oidc` commands show only `--disabled`, with no flag to enable again in their help (SDK 570, read on 2026-11-19; not yet seen in a real run).
- **`add-iam-policy-binding` on a service account that does not exist answers `PERMISSION_DENIED`**, by the command's reference (SDK 570, read on 2026-11-19).
- **A binding made seconds after its service account was created is refused, and works about a minute later** (2026-11-19, the CI account of `pilot`: `gcp_ci-identity-setup` retried once after its wait and the binding was made). The skills that make such a binding now wait for it by a bounded poll (every 30 seconds, 10 tries at most).
- **A project is found by the search by labels some minutes after its creation, and by the search filtered by parent** (`parent.type=folder AND parent.id=<number> AND labels…`), which printed the one project (2026-11-19). How soon after the creation each search sees it was not measured: the first search made after the creation ran about nine minutes later.
- **The first Artifact Registry command in a new project, seconds after its API was enabled, is refused**; some minutes later it works (2026-11-19). `project-apply` stopped there with the item `apis`, as designed then; it now waits for it by a bounded poll (every 30 seconds, 10 tries at most). How long a just-enabled API refuses was not measured: only that it worked "some minutes later".
- **Creating the ground of a project took three commands and about eight minutes of runs in Cloud Shell** (2026-11-19): the run that creates the project and enables the APIs about 2 minutes, a plan about 1 minute, the run that makes the repository, the policy, the identity and the grant about 4 minutes with its one wait, and a last plan under a minute.

## GCP — Artifact Registry

Read in the `gcloud` reference (`--help` of SDK 570), its command definitions and the generated API messages, and on the public cleanup policy page, on 2026-11-19. The first real run (2026-11-19, the repository of `pilot`) created a repository, set the two rules with `--no-dry-run` and read them back as declared, and read a repository that does not exist as missing; the skills decided rightly on each, but the raw answers were not looked at, and the policy's deletions were not observed. The console showed the two rules by the names of the policy file (`delete-the-rest`, `keep-most-recent`) and the mode as the one that deletes artifacts:

- **A cleanup policy file is a JSON list of rules.** Each rule has `name`, `action` as an object, `{"type": "KEEP"}` or `{"type": "DELETE"}`, and either `condition` (for example `{"tagState": "ANY"}`, which matches every version) or `mostRecentVersions` (`{"keepCount": 5}`; without `packageNamePrefixes` it applies to every image). The values are in upper case: the SDK decodes `KEEP`, `DELETE` and `ANY`, and sends the mixed case of the public page's examples (`"Keep"`) as an unrecognised field.
- **A version that matches a KEEP rule and a DELETE rule is kept** (public page). Keep the 5 most recent versions plus delete any version therefore deletes all but the 5 most recent of each image.
- **`gcloud artifacts repositories set-cleanup-policies` replaces every cleanup policy of the repository**, and **keeps the repository's dry-run setting unless `--no-dry-run` is passed**: the command updates only the fields of the flags given. `--no-dry-run` works although its help shows only `--dry-run`.
- **`describe --format=json` gives `cleanupPolicies` as a map from a policy's id to the policy**, and **an absent `cleanupPolicyDryRun` means false**: the field is omitted when false. `describe` also prints `Encryption:`, `Registry URL:` and `Repository Size:` lines on its error stream, apart from the JSON.
- **The policy is applied by a background job, about once a day**: a run that sets it never sees it delete.
- **A repository that does not exist answers `NOT_FOUND: Requested entity was not found.`**, while one the account may not read answers `PERMISSION_DENIED` with the words "or it may not exist": the second is not "missing".
- **`repositories list --location=all`** lists the repositories of every location (as `projects/<p>/locations/<location>/repositories/<id>`), after a line `Listing items under project ...` on its error stream.
- **Storage is free up to 0.5 GB, then about US$ 0.10 per GB a month** (pricing, as read for the design of stage 4 on 2026-11-19).

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

- **IAP can be enabled directly on a Cloud Run service, without a load balancer** (documentation read on 2026-11-16). Requests are authenticated with a Google account before they reach the container; access is granted with the role `roles/iap.httpsResourceAccessor`. It replaces the caller's identity, so anything that calls the service with its own authentication (for example, Pub/Sub) may fail behind it. Seen in a real run on 2026-11-19: see [GCP — Identity-Aware Proxy](#gcp--identity-aware-proxy-the-login) below.
- **Cloud Run charges only while a service is handling requests**, with a monthly free tier; any public address is found by bots (issued certificates are published in public logs) and every visit wakes the service.

## GCP — Identity-Aware Proxy (the login)

**Seen in a real run** on 2026-11-19, in spikes on two throwaway Cloud Run services, `spike-iap` and `spike-iap2`, in the project of `pilot`, in an organization owned by a personal Google account:

- **`gcloud run deploy … --no-allow-unauthenticated --iap` puts Google's login in front of a Cloud Run service, with no load balancer.** Not signed in: Google's sign-in page. Signed in but not allowed: "You don't have access", before the request reaches the service.
- **The project's IAP service agent needs `roles/run.invoker` on the service.** `--iap` created the agent by itself ("Setting IAP service agent"), and the binding was accepted right after.
- **A person is let in with `roles/iap.httpsResourceAccessor` on the service**, granted with `gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=<service> --region=<region> --member=user:<e-mail> --role=roles/iap.httpsResourceAccessor`.
- **In an organization owned by a personal Google account, Google's managed OAuth client refuses the login**, also for an account on the allowed list (every account is outside such an organization). **A custom OAuth client works:** a consent screen of audience External, left in testing, and an OAuth client of type web application.
- **A custom client set once on the organization is inherited by a new service** of a project of that organization, with nothing configured on the service. It is set with `gcloud iap settings set <file> --organization=<id>`, where the file holds the keys `accessSettings.oauthSettings.clientId` and `accessSettings.oauthSettings.clientSecret`. **Setting it needs `roles/iap.settingsAdmin` on the organization**, which the organization's administrator does not have by default: the set was refused until the role was granted.
- **The consent screen of audience External, in testing with an empty list of test users, let the owner's account in with no warning.**

**From Google's help, not yet seen in a real run:**

- With only the basic sign-in scopes (`openid`, `email`, `profile`), as IAP asks, an application in testing needs no publishing and no list of test users, shows no warning, and its authorizations do not expire; the cap of test users and the verification apply to sensitive scopes. Whether a second Google account gets in that way is what the run of stage 4b-1 checks.
- Uploading a logo to the consent screen starts Google's verification of the brand: no logo is uploaded.
- Google offers no command that creates a consent screen or an OAuth client: the `gcloud iap oauth-brands` and `oauth-clients` commands were discontinued, so both are made in the console (Google Auth Platform: Branding, Clients).

**From the installed SDK's source, read on 2026-11-19:** `gcloud iap settings get --organization=<id>` returns the stored settings as they are; in them `accessSettings.oauthSettings` has `clientId`, `clientSecret` (input only, never returned) and `clientSecretSha256` (output only). `set` reads its file as YAML (or JSON) in that same camelCase shape, and sends the whole message with no update mask (`SetIapSetting` in `lib/googlecloudsdk/api_lib/iap/util.py`, SDK 570). A refused call prints `PERMISSION_DENIED: …`, with a reason such as `IAM_PERMISSION_DENIED` or `SERVICE_DISABLED` in the details below it.

**Unverified:**

- Whether the server, given no update mask, replaces the other settings stored on the organization when `gcloud iap settings set` sends a file that holds only `oauthSettings`.
- The exact permission names in the refusals of `get` and `set` at the organization (the SDK names only `iap.projects.getSettings`).
- What `get` answers on an organization with no setting: an object with only `name`, an empty one, or `NOT_FOUND`.
- That a second Google account gets in after one `add-iam-policy-binding`, with no other step: the run checklist of stage 4b-1 proves it or not.

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
- **`git` authenticates through `gh` for one command in Cloud Shell**: `git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull` and `push` worked from a folder made with `git init`, with no global git configuration (2026-11-18, the birth of `aleogr-sandbox/pilot`). The same form pushed the branch of a pull request.
- **A repository created with `gh repo create --add-readme` in an organization has exactly one commit**, so the declaration could be sent as its second commit before the ruleset existed (2026-11-18).
- **A commit made with GitHub's no-reply address is attributed to the account** (the page shows the account's name and picture) and is marked "Unverified", which only means it is not signed. Adding `.patch` to a commit's address shows the address the commit carries.
- **A repository that is born public has its wiki on**; one born private in a free organization has it off (the note above). `github_repo-configure` turned it off after the creation (2026-11-18).
- **A birth through `project-apply` took about two minutes in Cloud Shell** (create, configure, send the declaration, protect, and two plans); applying one changed topic took 48 seconds and a plan about 17 (2026-11-18).
- **`gh pr create --head <branch>` works right after the push of that branch**, with no wait, and prints the pull request's address (2026-11-19, the first pull request opened by `github_pull-request-open`, on `aleogr-sandbox/pilot`).
- **After a merge on GitHub, the next reads already showed it**: `project-apply`, started within three minutes of the merge, found the folder behind, fast-forwarded it and applied the merged change in the same run (2026-11-19). The local branch of the proposal is kept in the folder; GitHub deleted its own copy at the merge.
- **A proposal through `project-apply` took about 1 minute 40 seconds in Cloud Shell, and the run after the merge (update the folder, plan again, apply one topic, final plan) about 3 minutes 15 seconds** (2026-11-19): the second is three plans in one run.
- **A Cloud Shell session closed between two steps of the run was resumed with `claude --continue`** in the project folder, and the plan showed where the run had stopped (2026-11-19).
- **A push that adds a file under `.github/workflows/` was accepted from a token of `gh` with the scope `workflow`** (2026-11-19, the first push of `.github/workflows/ci.yml`, to `aleogr-sandbox/pilot`). That GitHub refuses it without the scope is not confirmed by a real run: the check stays as a precaution. The scopes are the line `Token scopes` of `gh auth status`; `gh auth refresh -h github.com -s workflow` adds the scope.
- **A public repository of another organization can call a reusable workflow of a public repository**, pinned by commit SHA, with the organization's Actions policy at **Allow all actions and reusable workflows** (2026-11-19: `aleogr-sandbox/pilot` calling `ci-go.yml` of `aleogr/aleogr`).
- **GitHub accepts a ruleset rule `required_status_checks` with `[{"context": "ci"}]` and `strict_required_status_checks_policy: false`, sent with `PUT` to an existing ruleset**, and the required check is the job named `ci`: the pull request page shows it as `ci / ci` (workflow, then job) with the mark **Required**, and a called job as `ci / status / go` (2026-11-19).
- **With a required check red, the merge button of the pull request is disabled**, for the organization's owner too, since the ruleset has no bypass (2026-11-19).
- **`dorny/paths-filter` works on a push to the default branch with the default checkout** (depth 1, credentials kept): the job `changes` was green on the merge commit and both components ran (2026-11-19). On a pull request that touched one component, the other component's job was skipped and `ci` still reported.
- **The project's CI took under a minute** on a pull request and on `main` (each Go job about 30 seconds); a proposal that generates two components took about 2 minutes 30 seconds in Cloud Shell, and the run after the merge about 3 minutes (2026-11-19).
- **Cloud Shell restarted in the middle of the run and nothing was lost**: the project folder, its git checkout and the installed plugins were there when it came back (2026-11-18).

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
- **Claude Code refuses a `sleep` run in the foreground before it runs** ("Blocked: standalone sleep …"), and suggests running it in the background. Run with `run_in_background`, the wait returns a completion notice, and a headless `claude -p` run goes on in the same turn after it, also with a real 30-second wait (Claude Code 2.1.328, in the scenarios of the skills, 2026-11-19). In Cloud Shell, in stage 4a, a wait in the background ended the turn and the run went on by itself when it finished.
- **`claude -p` prints only the final message**: text a skill writes between two tool calls is not in its output (seen in the scenarios of the skills, 2026-11-19).
- **A model following an orchestrator tends to write the answer and the result block of the last skill it invoked at the start of its own final message** (13 of 40 runs of two scenarios that read the cloud, 2026-11-19). A sentence after that last invocation saying that the next output is the orchestrator's own answer, and nothing of the invoked skill, reduced it: on the final text of stage 4b-1, 1 of 40 runs (1 of 20 on the plan, 0 of 20 on the apply), and once more in a full run of the scenarios. Reduced, not eliminated.
- **The PowerShell quoting of a value with `&&` and single quotes inside double quotes** (`--attribute-condition="assertion.repository=='<owner>/<repo>' && assertion.ref=='refs/heads/main'"`) reached `gcloud` intact in the desktop app (2026-11-17).
