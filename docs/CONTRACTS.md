# CONTRACTS — family plugin contracts

> Contracts for every family in [DESIGN.md section 9](DESIGN.md#9-family-map-direction-not-a-task-list). The **common rules (section 1) are decided**. The per-family tables are **PROVISIONAL**: per [DESIGN.md section 10.3](DESIGN.md#103-extending-contracts), a family contract is only frozen once a second real provider exists; until then it is written with the listed representatives in mind and revised when the second provider arrives.

## Contents

- [1. Common rules](#1-common-rules)
- [2. Source and delivery](#2-source-and-delivery): repo
- [3. Domain](#3-domain): registrar, dns, cdn
- [4. Cloud base](#4-cloud-base): cloud, secrets
- [5. Infrastructure](#5-infrastructure): db, cache, storage, registry, search
- [6. Services](#6-services): auth, email, sms, push, payments, llm, flags
- [7. Components](#7-components): stack, platform, hosting
- [8. Operations](#8-operations): monitoring, analytics, notify
- [9. Collaboration](#9-collaboration): tracker, wiki
- [10. Distribution](#10-distribution): store, publish
- [11. Decisions and open items](#11-decisions-and-open-items)

---

## 1. Common rules

These rules apply to every action of every family, in addition to [DESIGN.md section 10](DESIGN.md#10-contract-rules-apply-to-all-families).

### 1.1 Naming

- Tables below list **actions**; the skill is `<provider>_<action>` (e.g. action `repo-create` → skill `github_repo-create`). For stack-* and platform-* the "provider" is the technology/platform (`go_setup`, `android_setup`).
- Actions are `<object>-<verb>`, object first; the verb may carry a complement (`ci-set-secret`), and an action without an object is just the verb (`setup`). See [DESIGN.md section 1](DESIGN.md#skills).
- Standard verbs, used consistently across families:

| Verb | Meaning | Changes anything? |
|---|---|---|
| `*-describe` | Reads the real state and returns it normalized | no |
| `*-create` | Creates a resource (idempotent: existing and matching = `unchanged`) | yes |
| `*-configure` | Brings settings of an existing resource to the declared values | yes |
| `*-setup` | Composite preparation (several resources/files for one purpose) | yes |
| `*-grant` | Gives an identity access to a resource | yes |
| `*-remove` / `*-archive` | Removes or archives; always guarded (destructive hook + confirmation) | yes |

- Every family has a `*-describe` action. It is the basis of `project-plan` (comparing the declaration with reality, which is discovered, not stored) and of the final verification of every action.

### 1.2 Modes

- **`plan` / `apply`** (every action except `*-describe`): `plan` reports what would change, without changing anything; `apply` executes. Both share the same logic, so `project-plan` never diverges from `project-apply`. Every skill is a shell over its plugin's command, which runs both modes in one module, the plan's reads shared by the apply, so no skill holds that logic twice ([DESIGN.md section 18](DESIGN.md#18-open-items)). A command writes only in `apply`, through an allowlist of the writes its skill names ([DESIGN.md section 10.4](DESIGN.md#104-behavior-of-every-skill)).
- **`pending` may be a `plan` result** for a feature the provider's plan forbids (e.g. branch protection on a private repository of a free GitHub organization), or for a step only the owner can take (reason `manual`, [section 1.4](#14-output-the-aleogr-result-block)): `plan` and `apply` both answer `pending`, change nothing and list one item (`plan-limit` or `manual`), so that they do not diverge ([DESIGN.md section 10.3](DESIGN.md#103-extending-contracts)). Only an answer of the provider that names the plan is `pending`; any other refusal is `failed`.
- **`shared` / `dedicated`** (families that create runtime resources): `shared` = inside the shared platform; `dedicated` = own resources. Default: `shared` in the `dev` project environment, `dedicated` elsewhere. Each family states below what `shared` means for it, or "n/a".
- **`test` / `live`** (special-care families: payments, registrar, store, sms, publish): `test` by default; `live` only with explicit confirmation.

### 1.3 Inputs

- Provider-neutral field names (`owner`, `name`, `environment`, `component`...). Provider-specific options live in the family plugin's sub-schema, under `options`.
- Every action that creates runtime resources receives `project`, `environment` (`dev` | `hom` | `prd`) and, for component-scoped families, `component`.
- Names and labels follow [DESIGN.md section 1](DESIGN.md#1-names); the skill derives them, the user never types them.
- **Secret values never pass through the conversation.** A secret input is a `secretRef` (`{ "store": "<secrets provider>", "name": "<name>" }`). A secret produced by an action (API key, password, signing key) is piped directly from the producing command into the secrets-* store, never printed; the output carries only its `secretRef`. When a human must type a value, the skill shows the command for the user to run with `!` (e.g. `! gh secret set NAME`).

### 1.4 Output: the `aleogr-result` block

Every skill ends with one fenced JSON block tagged `aleogr-result`, printed by its plugin's command last on stdout, for the owner (the shell relays it with the answer). One command reads another's result through `--json`: the command then prints only the result object, with the answer's lines under `answer` (and, where a caller needs more than the block, a `data` object that never reaches the block). The orchestrator's commands read it this way, as input (never repeating it), and route **requests** to other families; no skill reads another skill's fenced block ([DESIGN.md section 10.4](DESIGN.md#104-behavior-of-every-skill)).

```json
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "database-create",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "database", "id": "<shared project id>/aleogr-shared/project1_dev", "name": "project1_dev", "labels": {} }
  ],
  "outputs": { "instanceState": "running", "database": "project1_dev", "exists": true },
  "secretRefs": {},
  "requests": {
    "dnsRecords":   [],
    "ciSecrets":    [],
    "ciVariables":  [],
    "devcontainerFeatures": [],
    "checks":       []
  },
  "cost": { "fixed": false, "notes": "shared instance, no extra fixed cost" },
  "pending": [
    { "item": "...", "reason": "plan-limit | manual | provider-unsupported", "how": "..." }
  ]
}
```

- `status`: `created` | `updated` | `unchanged` | `pending` | `failed` (apply); `would-create` | `would-update` | `unchanged` (plan, with a `changes` list), and `pending` or `failed`. A `plan` is `pending` for a feature the provider's plan forbids ([section 1.2](#12-modes)), or for a step only the owner can take: it changes nothing and lists that step as an item with the reason `manual` (for example, a change to the declaration that must be merged first).
- `pending` as a status means nothing was changed. Once something was done the status says what (`created`, `updated`) and what is left is an item of the `pending` list.
- `requests` is the glue between families: a family never calls another family's skill; it asks, and the orchestrator routes the request in the right apply step ([DESIGN.md section 12.2](DESIGN.md#122-apply-order)):
  - `dnsRecords` → dns-* in step 8;
  - `ciSecrets` / `ciVariables` → repo-* `ci-set-secret` / `ci-set-variable` in step 10;
  - `devcontainerFeatures` → orchestrator assembles `devcontainer.json` in step 7;
  - `checks` → repo-* `branch-protect` (required checks) in step 10, once the file that reports them is on the default branch. On GitHub, `ci-setup` gives its check names in `outputs.checks`, and the orchestrator passes `checks=ci` to `branch-protect` exactly when `ci.yml` is on the default branch.
- `secretRefs` holds the references of the secrets an action produced (secrets-* and the families that make keys); it is empty or absent for an action that produces none, such as every action of the db family in `shared` mode on Cloud SQL, which creates no password.
- `cost.fixed: true` means the action needed (and got) explicit confirmation.
- `pending` items end up in the project checklist.

### 1.5 Removal

- `*-remove` / `*-archive` actions are blocked by the destructive-command hook unless invoked from a confirmed `component-remove` / `service-remove`, or for test resources ([DESIGN.md section 13.1](DESIGN.md#131-hooks)).
- In `shared` mode, removal only touches resources carrying the project's name/label; never the shared platform.

### 1.6 Waits

- Where a provider is known to refuse for a while after a change (an API just enabled, an identity just created, a role just granted), the action waits and tries again by itself, as a bounded poll: wait 30 seconds, try the same command again, alone, while it is refused that same way, at most 10 tries in all, the first one included (at most 9 waits, about 5 minutes). The one longer wait is the orchestrator's wait for the shared Cloud SQL instance it has just started, or found already starting: `db-*` `database-describe` polled until the databases can be read, at most 30 tries (about 15 minutes), where a read that fails counts as a try instead of ending the wait. Elsewhere, any other answer ends the poll at once and is read as usual. After the tenth refusal the action ends as its own rules say for that refusal (a `pending` item, or `failed` when it changed nothing), never with an eleventh try ([DESIGN.md section 10.4](DESIGN.md#104-behavior-of-every-skill)).
- The wait is the command `sleep 30`, the one command of such an action that is not the provider's CLI. A skill's command runs it itself, in its own process, and waits at most eight minutes in one run; when that is spent, the run ends as the action's own rules end that poll's limit, or, where they have none, `pending` with the item that says to run it again ([DESIGN.md section 10.4](DESIGN.md#104-behavior-of-every-skill)). An orchestrator's command runs its own waits the same way; a wait that does not fit in one command goes on in the next command of the run, the count of its tries carried, so the limit stays the action's for the whole run ([DESIGN.md section 10.4](DESIGN.md#104-behavior-of-every-skill)). No skill runs the wait with the Bash tool. While a wait is pending the action never ends its answer, never gives its result block and never tells the owner to run anything. The poll explains nothing of the refusal and repeats no word of the provider's answer.
- An orchestrator that enabled APIs polls the first skill that needs them the same way, when that skill ends `failed` having changed nothing ([DESIGN.md section 12](DESIGN.md#12-skills-of-the-aleogr-orchestrator)).

---

## 2. Source and delivery

### repo-* (exclusive, project) — github, gitlab, bitbucket

`shared`/`dedicated`: n/a.

| Action | Input | Output |
|---|---|---|
| `repo-describe` | owner, name, checks (the required checks the protection is compared with: `ci` or `none`, default `none`) | exists, the numeric ids of the repository and of its owner (public, read at each run, never versioned), visibility, description, default branch, merge settings, features (issues, wiki, projects), protection (state, whether it matches, the required checks it has), topics, secret/variable **names** (from stage 4) |
| `repo-create` | owner, name, visibility (default `private`; `public` needs its own confirmation), description, topics | creates the repository with a README; HTTPS/SSH URLs, default branch |
| `repo-configure` | owner, name, and only the settings to change: description, topics, merge methods, delete branch on merge, features (issues, wiki, projects), visibility (a change needs its own confirmation) | applied settings |
| `checkout-setup` | owner, name, path (default `.aleogr/project.json`), commit message, `head=check` | ties the current folder to the repository (a git checkout with the remote `origin`) and sends the file as the first content after the README, or brings a folder that is behind the repository up to date (a fast-forward); output: the file's state in the repository (`equal`, `not-sent`, `differs`, `behind`, `needs-attention`, `missing`), default branch, path, whether it pushed, whether it updated the folder, the reason of `needs-attention`. `plan` reads the repository's copy through the provider's API and, when it differs, the folder with read-only commands; it changes nothing |
| `pull-request-open` | owner, name, paths (the files to propose, never a folder), title, body, note (optional: up to 300 characters on one line, added to the body: the warnings that applying the change creates something permanent or starts something charged by the hour, one or both) | commits only those files on a new branch, pushes it, opens a pull request into the default branch and returns the folder to the default branch; output: the folder's state (`ready`, `not-a-checkout`, `other-remote`, `other-branch`, `local-commits`), the changed files, the open tooling pull request (number, address, branch), the pull request opened (number, address, branch), default branch. `plan` reports the open tooling pull request and which files changed, and changes nothing |
| `branch-protect` | owner, name, checks (`ci` or `none`, default `none`); the default branch and the rules are fixed (no deletion, no force push, a pull request with 0 approvals, and with `checks=ci` the required status check `ci`) | applied rules and required checks, or `pending` (plan limit, in `plan` and in `apply`) |
| `ci-set-secret` | name, scope (`repo` \| `org` \| `environment`), value source | name and scope (never the value) |
| `variables-set` | owner, name, variables (`<NAME>=<value>`, comma-separated), `kind` (`variables`, the default, or `secrets`), `replace` (`yes` or `no`, the default; `kind=secrets` only), `mode` | the repository-level Actions variables hold the given values (one read, then one set per variable that is missing or differs), or, with `kind=secrets`, the given Actions secrets exist (one read of their names, then one set per secret that is missing, or per given secret with `replace=yes`); output: `set` and `already`, **names only**, never a value |
| `ci-setup` | owner, name, components (name, path, stack, version of each), the repository of the reusable workflows, ref (`keep` the pinned commit, default, or `latest`), default branch, `deploy` (the environment CI deploys to; exactly one in this version), `deployComponents` (the components that get a deploy job: those whose service exists), `project` and `region` (the three needed with `deploy`) | writes `ci.yml` in the folder; output: its state here (`as-declared`, `missing`, `differs`, `not-needed`), whether the repository's default branch has it and whether that copy is as declared, the marker, the commit pinned, whether it wrote, `checks` (required check names: `["ci"]` with components; never a deploy job), `deploy` (the environments of the deploy jobs), `deployComponents` (the components given a deploy job, sorted) |
| `repo-archive` | owner, name | archived |

Notes:

- `branch-protect` requires a check only once the workflow that reports it is on the default branch: a required check that nothing reports would block every pull request, including the one that adds the workflow. On GitHub, `checks=ci` compares and sends a second ruleset file, `ruleset-main-ci.json`, equal to `ruleset-main.json` plus the rule that requires the status check `ci`; the required checks are compared as a set of names, so a ruleset with the check differs from `checks=none` and one without it differs from `checks=ci`. No JSON is built at run time.
- `ci-setup` writes the project's single CI file and never commits or pushes it: the pull request that proposes the change carries it. On GitHub the file is `.github/workflows/ci.yml`; its first line is a marker built from the components sorted by name (`# aleogr-ci 1 <name>:<path>:<stack>:<version>,…`), and "as declared" is decided by comparing that line, never the YAML; a file whose marker differs is rewritten whole. It has a job `changes` that detects the changed folders, one job per component that calls the stack's reusable workflow (pinned by commit, kept when the file is regenerated unless `ref=latest`), and a last job `ci`, the required check, which passes only when the detection succeeded and every component job passed or was skipped ([DESIGN.md section 4](DESIGN.md#4-cicd)). With no component and no file it is `unchanged` (`not-needed`); with no component and a file it is `pending`, to remove by hand.
- `ci-setup` with `deploy=<environment> deployComponents=<names> project=<project> region=<region>`: the marker is of version 2, `# aleogr-ci 2 <entries> deploy=<environment>:<names joined by +> project=<project> branch=<default branch> region=<region>`, and the job of each component named in `deployComponents` (sorted by name) is followed by `deploy-<component>-<environment>`, which needs that job, runs only when the event is a push to the default branch and that job succeeded, grants itself `contents: read` and `id-token: write`, and calls the reusable deploy workflow at the same commit as the check, with the component's folder, its service `<project>-<component>`, its image name and the region, written literally, as inputs, and the four identifiers as `secrets:` from the repository's secrets (`${{ secrets.GCP_PROJECT_ID }}`, and likewise `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT` and `GCP_IMAGE_PATH`), never `secrets: inherit`; no `vars.` is written. The deploy jobs are not part of the job `ci`. The triggers stay `pull_request` and `push`. `ref=keep` keeps the pinned commit only when the existing file is of version 2 and pins the deploy workflow at the same commit; a version 1 file is pinned again at the head of `main` of the workflows repository. Each name of `deployComponents` is a declared component; with `deploy`, a service name `<project>-<component>` of a listed component outside 6 to 30 characters, or a listed component's name ending with `-`, is `failed` before any command, and so are a missing `region` and more than one environment (the repository's secrets would clash). A component whose name starts with `deploy-` is refused with or without `deploy` (its job could take the id of a deploy job). The caller decides the list: the orchestrator names exactly the components whose service exists (the plan's output `ciDeployComponents`, passed as `deployComponents`; an empty list is the version 1 file) ([DESIGN.md section 4](DESIGN.md#4-cicd)).
- `variables-set` (GitHub: `github_variables-set`): `gh variable list --repo <owner>/<name> --json name,value`, then `gh variable set <NAME> --repo <owner>/<name> --body "<value>"` per variable that is missing or differs, sorted by name. A variable that was not given is never compared, changed or deleted; nothing is ever deleted. A value has no `,`, no whitespace, no `"`, backtick, `$` or `\`; a name matches `^[A-Z][A-Z0-9_]{0,63}$` and does not start with `GITHUB_`. Statuses: `would-update`, `unchanged` (plan); `updated`, `unchanged`, `failed` (apply). A set refused after others succeeded is `updated` with one `pending` item `variables`; the first set refused is `failed`. The result block never holds a value. With `kind=secrets`: `gh secret list --repo <owner>/<name> --json name`, then `gh secret set <NAME> --repo <owner>/<name> --body "<value>"`; a secret's value cannot be read back, so a given secret whose name exists is `already` and left alone, unless `replace=yes`, which sets every given secret; the `pending` item of a refused set is `secrets`, and a value appears in no answer, block or failure sentence. The orchestrator sets the four CI secrets `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT` and `GCP_IMAGE_PATH` (there is no `GCP_REGION`: the region is written in `ci.yml`), with `replace=yes` when its run created or changed the GCP project, the image repository or the CI identity; its plan's row `ci secrets` compares their names only.
- `repo-create` creates the repository with a README, so that the default branch exists from the start (a protection that requires pull requests could block the first commit of an empty repository). On an existing repository it changes nothing (`unchanged`) and lists what differs from its inputs; `repo-configure` is the only action that corrects an existing repository.
- `repo-configure` compares and changes only the settings it is given: a setting left out is left as it is.
- `checkout-setup` sends only at a birth: the file is pushed to the default branch only when that branch has exactly one commit (the README of `repo-create`) and does not have the file. A repository with any other history is never pushed to. Its states: `equal` (`unchanged`); `not-sent`, a birth (`would-create` in `plan`, `created` in `apply`); `differs`, a local change the repository does not have, and `missing`, a repository with history and no file, are `pending` in `plan` and in `apply`, with one item of reason `manual` (propose the change with a pull request; open a pull request that adds the file). A push the repository's rules refuse is the same `pending` as `missing`, not a failure. The two files are compared as JSON values, not byte by byte.
- `checkout-setup` tells a stale folder from a local change. When the two files differ it reads the folder, read-only (never a fetch): `behind` is a folder on the default branch, with no local change to the file, whose last commit is in the repository while the repository's default branch is at a newer commit (the case right after a merge); `needs-attention` is a folder that is not a checkout of the repository, has another `origin`, is on another branch, has commits the repository does not have, or whose file differs where git sees no change. **The head check:** with `head=check`, an equal file is not the end: the folder's last commit is compared with the head of the default branch, by the same reads (the file's own change is not read), so a merge that left the file unchanged still makes the folder `behind`; a folder that is not a checkout stays `equal`, and another `origin`, another branch or local commits are `needs-attention`. Without `head=check` an equal file is `equal` with no command run. **The folder update:** `behind` is `would-update` in `plan`; in `apply` the folder is fast-forwarded from the default branch (the pull authenticates through `gh` for that command only) and the result is `updated`; nothing is committed, pushed or configured. `needs-attention` is `pending` in `plan` and in `apply`, nothing done, with one item of reason `manual` that says what to fix by hand.
- `checkout-setup` and `pull-request-open` commit identity: always set in that checkout only (local configuration), before every commit, whatever the machine's global identity is: on GitHub, the account's login and its no-reply address (`<id>+<login>@users.noreply.github.com`). A real e-mail address is never used, the login is not repeated in the answer or the result block, and no global configuration is changed (the push authenticates through `gh` for that command only).
- `pull-request-open` never commits on, or pushes to, the default branch, and **never merges**, closes or deletes a pull request or a branch: the owner merges. It requires a folder that is a checkout of the repository, on the default branch, with no commit the repository does not have; otherwise `pending`, nothing done, with the item `this folder needs attention`. In `apply` it brings the default branch up to date first (a fast-forward; a conflict with what the repository now has is `failed`, nothing committed), creates the branch `aleogr/change-<6 random characters of a-z0-9>`, commits only the named files that changed (anything else in the folder is neither committed nor discarded), pushes that branch, opens the pull request (`created`) and returns the folder to the default branch, keeping the local branch. No named file changed: `unchanged`. The branch pushed but no pull request opened: `updated`, with the item that opens it.
- **One open tooling pull request at a time per repository.** A tooling pull request is one whose branch is in the repository itself and named `aleogr/change-…`; a pull request from a fork is never taken for one. While one is open, `pull-request-open` creates nothing, in `plan` and in `apply`: `pending`, with the item `pull request #<n> is open` ("merge or close" it). Pull requests on other branches are ignored.
- Visibility: nothing becomes public, at creation or by a change, without the confirmation `confirmVisibility=public`; a change to private needs `confirmVisibility=private`. Without it the action does not wait for an answer: it changes nothing of the visibility, asks the question and gives the exact command that confirms it.
- `pending` as a status means nothing was changed: the run waits for the visibility confirmation, the provider's plan forbids the protection, the declaration must go in by pull request or the folder needs attention (`checkout-setup`), or a tooling pull request is already open (`pull-request-open`). Once something was done the status says what (`created`, `updated`) and anything left is an item in the `pending` list.
- `branch-protect` on a plan without branch protection (on GitHub, a private repository of a free organization): `pending` in `plan` and in `apply`, nothing changed, one `plan-limit` item; the default branch is then held by the working rule (the owner merges).
- On GitHub, a description may not contain `"`, `“`, `”`, `„`, a backtick, `$`, `\` or a line break: the skills write it in double quotes on a command line, and the command passes it as one argument, never through a shell.
- Project environments (`dev`/`hom`/`prd`) map to the provider's deployment environments; covered by the `environment` scope.
- Repository deletion is not in the contract: only the test cleanup deletes repositories.
- Bitbucket has no topics; the federated layout and tests depend on topics (recorded limitation).
- Topic `aleogr-<project>` would collide with `aleogr-test` for a project named `test`: that is why the name `test` is reserved as well as the `test-` prefix ([DESIGN.md section 1](DESIGN.md#tests)).

---

## 3. Domain

### registrar-* (exclusive per domain, domain) — godaddy, namecheap, cloudflare

Special care. `shared`/`dedicated`: n/a.

| Action | Input | Output |
|---|---|---|
| `domain-describe` | domain | registered?, owner account, expiry, auto-renew, lock, privacy, nameservers |
| `availability-check` | domain(s) | available?, price (registration and renewal) |
| `domain-register` | domain, years, contact profile | registered, expiry, `cost.fixed: true` (always confirmed) |
| `nameservers-set` | domain, nameservers (from dns-* `zone-create`) | applied nameservers |
| `domain-configure` | auto-renew, transfer lock, WHOIS privacy | applied settings |

Notes: no transfer or deletion in the contract. Renewal price is always shown before registration.

### dns-* (exclusive per domain, domain) — cloudflare, aws-route53, gcp-cloud-dns

`shared`: records in the `aleogr.dev` zone, directly under it (`<project>-<environment>.aleogr.dev` and its tenants, DESIGN.md section 6.1).

| Action | Input | Output |
|---|---|---|
| `zone-describe` | zone | exists, nameservers, records (filterable by name pattern) |
| `zone-create` | zone | zone id, nameservers (request to registrar-* `nameservers-set`) |
| `record-add` | name, type, target, TTL, proxied (if supported; off in `dev` and `hom` by choice, always off for tenants there; on in `prd`) | record id; upsert (idempotent) |
| `record-remove` | name, type | removed |

Notes:

- `record-add` consumes the `dnsRecords` requests of every other family (deploy hostnames, one per tenant, e-mail SPF/DKIM/DMARC, domain verification TXT).

### cdn-* (exclusive per domain, domain) — cloudflare, akamai, aws-cloudfront

`shared`: n/a. Records in `dev` and `hom` are unproxied (a choice for the project's address, a limit for tenants: DESIGN.md section 6.2), so there is no CDN in front of them; cdn-* applies to `prd`.

| Action | Input | Output |
|---|---|---|
| `cdn-describe` | host(s) | CDN on/off, origin, cache rules, TLS coverage |
| `cdn-setup` | host, origin, cache profile (`static` \| `dynamic` \| `off`) | distribution/proxy enabled, `dnsRecords` if the CDN needs its own target |
| `cache-configure` | host, rules (paths, TTLs, bypass) | applied rules |
| `tls-setup` | hosts (incl. wildcards) | coverage per host, or `pending` (plan limit) |
| `cache-purge` | host, paths (or all) | purged |
| `cdn-remove` | host | removed |

Notes: `tls-setup` covers proxied hosts, that is, `prd` (a multi-tenant project needs its own domain to be covered by the free certificate). In `dev` and `hom` the certificate is issued by the destination (DESIGN.md section 6.2).

---

## 4. Cloud base

### cloud-* (combinable with exactly one primary, project) — aws, azure, gcp

`shared`/`dedicated`: n/a. Every project has its own environment per project environment; `environment-create` always creates it (idempotent). The shared platform project is part of the shared platform (DESIGN.md section 6.8).

| Action | Input | Output |
|---|---|---|
| `environment-describe` | project and environment, the shared platform project (`project=shared platform=shared` on GCP), or the environment id (`projectId` on GCP) | exists, parent, billing linked, enabled services, labels; identities and budget alerts (planned) |
| `environment-create` | project, environment, `platform` (`shared`: the shared platform project, with no environment), `root` (`tst`: a project that tests the tooling, created inside the folder `tst`), parent and billing reference (discovered by the skill), region (planned) | environment id (GCP project / AWS account / Azure subscription + resource group); repairs an existing environment whose billing is not linked |
| `services-enable` | project and environment, the shared platform project (`project=shared platform=shared` on GCP), or the environment id (`projectId` on GCP); provider API names (neutral capabilities `run`, `sql`, `secrets`, `storage`, `registry`... planned) | enabled and already enabled provider APIs/services |
| `ci-identity-setup` | the environment id (`projectId` on GCP), project, repository (`owner/name`), the repository's and its owner's numeric ids (`repositoryId`, `ownerId`, read by the orchestrator from repo-* `repo-describe`), branch (the repository's default branch), workflow (the reusable deploy workflow, `<owner>/<name>/.github/workflows/<file>.yml`), `mode` | keyless CI identity (OIDC / workload identity federation) that only a job of that repository's default branch running that workflow can use, with no role on the environment; output: the account, the provider's name, the condition (`as-declared`, `differs`, `missing`), the number of other members that may act as the account, and `ciVariables` with its identifiers, which the orchestrator stores as repository secrets (set only when every part exists as declared) |
| `deploy-describe` | the environment id (`projectId` on GCP), project, region, components, the declared maximum of instances (1 to 10), CPU (1 or 2) and memory (`512Mi`, `1Gi` or `2Gi`), the CI account, environment; optional `env` (each component's settings, `<component>:<NAME>=<value>` joined by `;`) | per component: whether its service exists, whether it is as declared and which parts differ (`account`, `scaling`, `size`, `public`, `open`, `login`, `agent`, `ci`, `labels`, and `env` when a given setting is missing or holds another value), whether it still runs the placeholder image, its address; the lists `missing`, `differing`, `waiting`. Read-only; a missing service is an answer, not a failure; of the login policy only `allUsers` and `allAuthenticatedUsers` are looked for (`open`), and the people on the allowed list are not compared |
| `deploy-setup` | the environment id, project, environment, region, components, the maximum of instances, CPU, memory, the CI account, the placeholder image, `mode`; optional `env` (as `deploy-describe`); planned: hosts, access (login or public), `secretRef`s | each component's service as declared: created behind the login with the placeholder image, repaired where it differs (never its image), CI allowed to replace its image, the account that runs it allowed in, and, with `env`, the given settings set; output: as `deploy-describe`, plus `urls`, `created`, `updated`, and with `env` `envSet` (the names set, never a value); planned: `dnsRecords` |
| `access-grant` | the environment id, project, region, components, person (one e-mail) or `list=yes`, `mode` | the person let in through the login on each component's service, never on the environment; output: `granted`, `already`, with `list=yes` the number of people each service lets in (`people`, numbers only), and `open` (the services whose login lets in everyone) |
| `deploy-remove` | component, environment | removed |
| `budget-alert-setup` | display name, amount, currency, thresholds, quota project (scope: the whole billing account; per project and notification target planned) | display name (the alert id) |
| `login-describe` | optional: the shared platform project the read is counted against (`projectId` on GCP) | whether the login of the organization is prepared (`prepared`), whether its setting could be read (`readable`), whether one organization was found; read-only, and never the client's id nor anything of its secret |
| `login-setup` | the shared platform project (`projectId` on GCP), `mode` | what a command can do to prepare the login of the organization (the role that changes the organization's login setting, granted to the account that runs it; the API, enabled in the shared project); output: `prepared`, `roleGranted`, `apiEnabled`, and `steps`, the list of what is left to the owner (the console's clicks and one command to paste in a terminal); never sees the client's secret |

Notes:

- On GCP the parent of an environment is the folder of its environment, under the organization or, with `root=tst`, inside the folder `tst`; the shared platform project (`platform=shared`) is the exception, created directly under the organization (DESIGN.md section 6.7). The skill never creates folders. The skill discovers the parent and the billing account; the owner never types them.
- Implemented: `environment-describe`, `environment-create`, `services-enable`, `budget-alert-setup`, `ci-identity-setup`, `login-describe`, `login-setup`, `deploy-describe`, `deploy-setup` and `access-grant` (skills in `.claude-plugin/plugins/aleogr-cloud-gcp/skills/`). The other actions are planned.
- CI never gets long-lived cloud keys: `ci-identity-setup` uses OIDC federation, and no key is ever created.
- `ci-identity-setup` on GCP (`gcp_ci-identity-setup`): in the environment's GCP project, the service account `<project>-ci`, the workload identity pool `github` and its OIDC provider `github` (issuer `https://token.actions.githubusercontent.com`, location `global`), and the binding that lets the tokens of the repository act as the account (`roles/iam.workloadIdentityUser` for the member `principalSet://…/attribute.repository/<owner>/<name>`), each created only when missing, in that order. The provider's condition is exactly `assertion.repository=='<owner>/<name>' && assertion.repository_id=='<repositoryId>' && assertion.repository_owner_id=='<ownerId>' && assertion.ref=='refs/heads/<branch>' && assertion.job_workflow_ref.startsWith('<workflow>@')`, and its attribute mapping has exactly six keys, one per field the condition tests (`google.subject=assertion.sub`, `attribute.repository`, `attribute.ref`, `attribute.repository_id`, `attribute.repository_owner_id`, `attribute.job_workflow_ref`, each from the claim of the same name), always sent whole. The last clause accepts only a job that runs the reusable workflow `<workflow>`; it stops at `@` because what GitHub puts after it for a workflow pinned by commit is not documented. It stops another workflow file of the same repository and branch, not someone who can change the default branch (DESIGN.md section 18). A provider whose condition, issuer or attribute mapping differs (one made before the clause existed included) is `would-update` in `plan` and updated whole in `apply` (never deleted). Refused before any change, as `failed`, to be fixed by hand: a deleted or disabled pool or provider, and a pool that holds a provider other than `github`. Other members of the binding are counted (`otherMembers`) and never removed. The account gets no project role: its roles are granted on each resource (registry-* `access-grant`). A binding refused right after the account was created in the same run is tried again by the bounded wait ([section 1.6](#16-waits)); after the tenth refusal the account, pool and provider stay and the binding is a `pending` item. Statuses: `would-create`, `would-update`, `unchanged` (plan); `created`, `updated`, `unchanged`, `failed` (apply). `ciVariables` are `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER` and `GCP_CI_ACCOUNT`.
- `login-describe` and `login-setup` on GCP (`gcp_login-describe`, `gcp_login-setup`): the login is the organization's IAP setting, which names one custom OAuth client that every service of the organization inherits ([DESIGN.md section 6.3](DESIGN.md#63-protection-and-single-access-point)). `login-describe` reads it (`gcloud iap settings get --organization=<id>`, with `--billing-project=<projectId>` when given): `prepared` when it names a client; a setting without a client, `NOT_FOUND`, and a read refused for lack of permission or because the IAP API is off are `prepared` false and `unchanged`, not failures (`readable` false for the two refusals); any other failed read is `failed`. `login-setup` reads the setting first and grants nothing when it names a client (`unchanged`); otherwise, in `apply`, it grants the active account `roles/iap.settingsAdmin` on the organization (`--condition=None`) and enables `iap.googleapis.com` in the shared project, each only when missing, then reads again, waiting by the bounded wait while the new role has not reached the read. When the login is known not to be prepared it prints the list of what is left: the consent screen `aleogr` (audience External, no logo, nothing published) and the web application client `iap` with its redirect address, as console links in the shared project, and one command that asks for the client's id and secret, sets them on the organization through a temporary file and removes the file. It never runs that command, never asks for the id or the secret and never reads a file that could hold them. Statuses: `would-update`, `pending` (the role and the API present, only the clicks left), `unchanged`, `failed` (plan); `updated`, `pending`, `unchanged`, `failed` (apply). Its `pending` item `login` (reason `manual`) says what the owner does, ending with `/aleogr:platform-plan`.
- `deploy-describe` and `deploy-setup` on GCP (`gcp_deploy-describe`, `gcp_deploy-setup`): each component is the Cloud Run service `<project>-<component>` (6 to 30 characters, so it can also be its account's id) in the declared region, running as its own service account `<project>-<component>`, which has no role. A service is as declared when, in this order of the words that differ: it runs as that account and the account exists (`account`); its service-level maximum is the declared one, no minimum is above 0 at the service or in the template and its scaling is not manual (`scaling`); its CPU and memory are the declared ones (`1000m` reads as `1`, `1Gi` as `1024Mi`) and its billing is by request (`size`); no binding of its policy, whatever the role, lists `allUsers` or `allAuthenticatedUsers`, and its invoker check is on (`public`); no binding of its login policy, whatever the role and with or without a condition, lists `allUsers` or `allAuthenticatedUsers` (`open`: either lets anyone on the internet who signs in with any Google account through the login); the login is on, the annotation `run.googleapis.com/iap-enabled` `true` (`login`); the login's service agent `service-<project number>@gcp-sa-iap.iam.gserviceaccount.com` has `roles/run.invoker` on it (`agent`); the CI account has `roles/run.developer` on it and `roles/iam.serviceAccountUser` on its account, both without a condition (`ci`); and it has the three labels (`labels`). `placeholder` is true while its image is Google's sample `us-docker.pkg.dev/cloudrun/container/hello` (with or without a tag or digest), which is the only placeholder `deploy-setup` accepts.
- `deploy-setup` in `apply`, after reading the project number, the active account and each component (its service, its policy, its account's policy and its login policy): first a **security pass** over every service that exists (each `allUsers` or `allAuthenticatedUsers` member removed from its login policy, then from its access policy, whatever the role, the login turned on with `--iap` alone, the invoker check turned back on); when a command of the pass fails, nothing else is made and the run ends `failed`, naming each service still open or still without the login. Then, per component: the account when missing; the CI binding on the account (it proves the new account visible; a refusal right after the account's creation is polled, [section 1.6](#16-waits)); the service when missing, in one command, `gcloud run deploy <service> --image=<placeholder> --no-allow-unauthenticated --iap --service-account=<account> --min=0 --max=<n> --cpu=<cpu> --memory=<memory> --cpu-throttling --labels=… --region --project --quiet`; for a service that differs, one `gcloud run services update` with only the differing settings and never `--image` or a security flag, and the agent's binding when missing; the CI binding on the service; and the active account's `roles/iap.httpsResourceAccessor` on the service through the login (`gcloud iap web add-iam-policy-binding --resource-type=cloud-run`). A refused grant of that access stops nothing: the result carries, once, the `pending` item `access`, whose `how` is `/aleogr:project-access person=<e-mail>` with the placeholder as written, and the orchestrator carries it to the end of its run (no plan compares a person's access). The maximum of instances is 1 to 10, the CPU 1 or 2 and the memory `512Mi`, `1Gi` or `2Gi`; anything else is `failed` before any command. A failed create is followed by one read: a service found is set up as declared, with the security pass first. It never passes `--allow-unauthenticated`, `--no-iap`, `--no-invoker-iam-check` or `--ingress`, never sets a minimum above 0, never deletes, never runs `set-iam-policy` or `gcloud projects add-iam-policy-binding`, and never gives the CI account another role. Then it reads again what it changed. Statuses: `would-create`, `would-update`, `unchanged` (plan); `created`, `updated`, `unchanged`, `failed` (apply). The result block holds no e-mail at all.
- `access-grant` on GCP (`gcp_access-grant`): the member is always `user:<person>`; `person` is one address of a person (one `@`, a domain with a letters-only last part, no space, `:`, `,` or quote, not `allUsers` or `allAuthenticatedUsers`, not a `gserviceaccount.com` address), so a group, a domain, a service account or everyone is refused, and a group's address that passes the rule would let nobody in. It reads every service first (a missing one is `failed`, naming each, nothing granted), then each login policy, and grants `roles/iap.httpsResourceAccessor` with `gcloud iap web add-iam-policy-binding --resource-type=cloud-run` where the person has no unconditional binding; then it reads each one back. Nothing is removed: a login that lets in `allUsers` or `allAuthenticatedUsers` is reported (`open`) with its remove command as a `pending` item for the owner, and the answer of `list=yes` gives the command that removes a person. The person's address never reaches a label, a file or the result block, also not inside a `how`. Statuses: `would-update`, `unchanged` (plan); `updated`, `unchanged`, `failed` (apply). No cost.
- `env` on GCP (both service skills): entries `<component>:<NAME>=<value>` joined by `;`; a name is 1 to 64 characters of `A-Z`, `0-9` and `_`, starting with a letter; a value 1 to 200 characters of `a-z`, `A-Z`, `0-9`, `-`, `_`, `.`, `:` and `@` (no space, never `#`); each component one of `components`. A setting not given is never compared, changed or reported. `deploy-setup` writes the settings that are missing or hold another value (all of them for a service it created) last for the component, after every other repair, in their own `gcloud run services update <service> --update-env-vars="^##^<NAME>=<value>##…"` (`^##^` makes `##` the separator, so a value may hold `:` and `@`): never with `--image` or a security flag, never `--set-env-vars`, `--remove-env-vars`, `--clear-env-vars` or `--env-vars-file`, so every other setting of the service is kept. A value is never written in a sentence, the answer or the result block: a difference of settings is the word `env`, and `envSet` names settings only. Without `env`, both skills behave as before and say nothing of settings. The orchestrator passes the three database settings of a component that uses the database (`DB_INSTANCE`, `DB_NAME`, `DB_USER`; [db-*](#db--combinable-project--aws-rds-gcp-cloud-sql-azure-sql)).
- Planned for `deploy-setup`: every declared host mapped to the service (the environment's host and one per tenant), with one `dnsRecords` request per host (no wildcard in `dev` and `hom`, DESIGN.md section 6.1), and a component declared public, which has no login (DESIGN.md section 6.3).
- In `dev`, `deploy-setup` scales to zero, uses the smallest practical size and sets a maximum of instances (DESIGN.md section 6.5): on GCP a minimum of 0, a maximum of 2, 1 CPU, 512 MiB and billing by request (`project.deploy` of the orchestrator's `defaults.json`).
- Only the primary cloud receives secrets-* by default.

### secrets-* (exclusive, project) — aws-secrets-manager, gcp-secret-manager, azure-key-vault

`shared`: the shared platform's vault, names prefixed with the project.

| Action | Input | Output |
|---|---|---|
| `store-describe` | project | store exists, secret **names** (prefix-filtered), versions, accessors |
| `store-create` | project, region | store id (in `shared`: verification only) |
| `secret-set` | name, value source (`generate` \| `pipe` from a command \| `user` via `!`) | `secretRef`, version (never the value) |
| `access-grant` | identity, secret names or prefix, role (read) | applied bindings |
| `secret-remove` | name | removed (versions destroyed only with confirmation) |

Notes: `generate` covers database passwords and similar; `pipe` covers keys produced by other providers' CLIs.

---

## 5. Infrastructure

### db-* (combinable, project) — aws-rds, gcp-cloud-sql, azure-sql

`shared`: a database per project and environment, and a database user per component, on the shared platform's single instance; each user is the component's own service account, connecting with IAM authentication and no password. No action of this mode produces a secret or a `secretRef`.

`instance-describe`, `instance-start`, `instance-stop` and `instance-switch-setup` are actions of providers whose instances do not scale to zero (`gcp-cloud-sql`): the instance stays stopped and is started on demand ([DESIGN.md](DESIGN.md) section 6.8).

| Action | Input | Output |
|---|---|---|
| `database-describe` | the shared project, the instance, project, environment, the components' service accounts | the instance's state; the database's name and whether it exists (or not read); for each account (by its position), whether it is a user (or not read) and holds each connection role; whether the database and the users were read. Read-only; a stopped or starting instance is a normal state, never a failure. Planned: size tier, backups |
| `instance-create` | engine, version, tier, region; `platform` (`shared`: the shared platform's instance, passed only by the orchestrator's platform skills); optional `stopJob` (the scheduler job that stops the instance at night: run once to stop the new instance, which proves it works); optional `resume=yes` (passed only by the platform's apply when its own run asked for the creation in an earlier command: the creation is skipped and the run goes on with the wait, the stop and the check; an instance this action did not just create is never stopped by it) | instance id, `cost.fixed: true` (`dedicated` only; refused in `dev`, except `platform=shared`) |
| `instance-describe` | project id, instance name | exists, state (`stopped`, `starting`, `running`, `creating`), settings, last backup |
| `instance-start` | project id, instance name | state seen after the change (`starting`, `running`, or briefly `stopped`); after a start command that fails, one read of the instance says whether it was started after all, is still stopped, or cannot be told, so the answer says whether it costs. It does not read the night stop: its caller does |
| `instance-stop` | project id, instance name | state (`stopped`) |
| `instance-switch-setup` | project id, instance name, region, time zone, stop schedules, repository, `mode` | `ready`, parts still missing; in the answer's prose, the values of the GitHub secrets |
| `database-create` | the shared project, the instance, project, environment, `mode` (planned: engine) | the database, made when missing with the instance's defaults; the instance's state, its name, whether it exists. No password, no `secretRef` |
| `access-grant` | the shared project, the instance, one identity (a component's service account), `mode` (planned: CI migrations, grants inside the database) | the identity's database user (IAM type, no password, no database role) and its connection roles; output: whether it is a user, which roles it holds, which this run granted, whether it made the user |
| `backup-configure` | schedule, retention, point-in-time | applied policy (`prd`) |
| `database-remove` | project, environment | removed (guarded; dump offered first) |

Notes:

- Implemented on GCP (`aleogr-db-gcp-cloud-sql`, skills `gcp-cloud-sql_<action>`): `instance-describe`, `instance-create`, `instance-start`, `instance-stop`, `instance-switch-setup`, and, in `shared` mode, `database-describe`, `database-create` and `access-grant`. The others are planned.
- The `shared` actions on GCP read the instance with the read and the state rule of `instance-describe` (`stopped`, `starting` while the start's `UPDATE` operation is unfinished, `running`, `creating`, `unknown`), and never start, stop or change it. A database and a user are made through the Cloud SQL Admin API, which needs the instance running, and what it answers on a stopped one is not documented: on any state but `running` they read nothing more and end `pending` with the item `instance`, whose `how` depends on the state (`stopped`: `/aleogr:project-apply confirm=yes`, which starts it when something must be made in it; `starting` or `creating`: wait some minutes, then `/aleogr:project-plan`; `unknown`: `/aleogr:platform-plan`). `database-describe` instead ends `unchanged` with the database and the users `null` (not read). Whether something exists is decided by a list after a failed create, never by an error's text.
- Names: the database is `<project>_<environment>` (every `-` written `_`; at most 18 characters); a user is the service account's address without `.gserviceaccount.com` (`<id>@<project id>.iam`, at most 63 characters, PostgreSQL's limit, refused before any command when longer).
- `access-grant` on GCP, in this order and only while the instance runs: the user, when missing, `gcloud sql users create <user> --type=cloud_iam_service_account` (never `--password` or `--database-roles`), then each missing role of `roles/cloudsql.client` and `roles/cloudsql.instanceUser`, `gcloud projects add-iam-policy-binding <shared project> --member=serviceAccount:<account> --role=<role> --condition=None` (`--condition=None` adds a binding without a condition, and `gcloud` refuses a grant without it on a policy that holds any conditional binding). Only these two roles, only on the shared project, only to `serviceAccount:<account>`; never `set-iam-policy`. A binding of either role counts as held with or without a condition. A grant refused for an account just created is waited for by the bounded wait ([section 1.6](#16-waits)). The result block holds no e-mail at all.
- The roles are on the project because Cloud SQL grants them there, not on an instance; a condition narrowing them to the one instance is not used yet ([DESIGN.md section 18](DESIGN.md#18-open-items)).

### cache-* (exclusive, project) — aws-elasticache, gcp-memorystore, redis-cloud

`shared`: a key namespace (prefix + ACL user) per project. Managed caches usually have fixed cost: in `dev`, use a serverless or free-tier provider (e.g. Upstash, Redis Cloud free); `instance-create` is `dedicated` only.

| Action | Input | Output |
|---|---|---|
| `cache-describe` | project, environment | instance, namespace, ACL users, tier |
| `instance-create` | tier, region | instance id, `cost.fixed: true` (`dedicated` only) |
| `namespace-create` | project, environment | endpoint, key prefix, `secretRef` of the credentials |
| `namespace-remove` | project, environment | removed |

### storage-* (combinable, project) — aws-s3, gcp-storage, azure-blob

`shared`: a prefix in the shared bucket. `dedicated`: own bucket (names are global: convention + short suffix).

| Action | Input | Output |
|---|---|---|
| `bucket-describe` | project, environment, purpose | bucket/prefix, access, lifecycle, CORS |
| `bucket-create` | project, environment, purpose, region | bucket name (or prefix in `shared`) |
| `bucket-configure` | public access (default off), versioning, lifecycle, CORS | applied settings |
| `access-grant` | identity, role (read/write) | applied bindings |
| `bucket-remove` | project, environment, purpose | removed (empty first, with confirmation) |

### registry-* (exclusive, project) — gcp-artifact-registry, docker-hub, ghcr, aws-ecr

`shared`/`dedicated`: n/a. The image repository is the project's own, in the project's own cloud environment: one per project and environment, never a repository in a shared registry ([DESIGN.md section 6.4](DESIGN.md#64-shared-platform--project-resources)). Each component's image is a path inside it.

| Action | Input | Output |
|---|---|---|
| `registry-describe` | environment id (`projectId` on GCP), project, region | exists (in the declared region), the region it was read in, other regions holding a repository of that id, format, labels, cleanup policy (how many versions it keeps, whether it deletes the rest, dry-run), who may push, image path |
| `repository-create` | environment id, project, environment, region, `mode` | creates the repository `<project>` when missing, never changes an existing one; output: the image path, the prefix of every component's image (`<imagePath>/<component>`) |
| `cleanup-configure` | environment id, project, region, keep (1 to 50), `mode` | the cleanup policy, two rules (keep the `keep` most recent versions of each image, delete every other version), dry-run off; output: keep and dry-run as read back |
| `access-grant` | environment id, project, region, identity (a service account of the same environment), role (`push` only), `mode` | the role that lets the identity push, on the repository and never on the environment; output: whether it is granted |
| `repository-remove` | environment id, project | removed (planned, stage 6) |

Notes:

- Implemented on GCP: the four actions above, in `.claude-plugin/plugins/aleogr-registry-gcp-artifact-registry/` (skills `gcp-artifact-registry_<action>`); `repository-remove` is planned.
- On GCP the repository is an Artifact Registry repository, id `<project>`, format Docker, in the declared region, with the labels `aleogr-project` and `aleogr-environment`; the image path is `<region>-docker.pkg.dev/<projectId>/<project>`. A repository of that id found only in another region is `pending` with an item to fix by hand (a repository has one region), and so is one of another format; nothing is changed.
- `cleanup-configure` owns both rules, from a policy file the plugin ships (`files/cleanup-policy.json`, for 5; another `keep` is written to a temporary file outside the project's folder). The policy is as declared only with exactly those two rules and dry-run off: a policy in dry-run deletes nothing, so it counts as different. Setting it replaces every policy of the repository and turns dry-run off in the same command. The provider applies it later (on GCP about once a day): a run never sees it delete.
- `access-grant` grants only `push` (on GCP, `roles/artifactregistry.writer` on the repository). `pull` is refused as not needed: the runtime that pulls (on GCP, Cloud Run's own agent) reads a repository of its own environment. A binding refused right after the identity was created is tried again by the bounded wait ([section 1.6](#16-waits)); after the tenth refusal it is `failed`, nothing changed. Nothing is ever removed.
- The statuses: `registry-describe` is `unchanged` whenever it read the state (a repository that does not exist is an answer, not a failure) and `failed` otherwise; `repository-create` is `would-create`, `created`, `unchanged`, `pending` or `failed`; `cleanup-configure` and `access-grant` are `would-update`, `updated`, `unchanged` or `failed`.

### search-* (exclusive, project) — elastic, algolia, aws-opensearch

`shared`: indexes prefixed with the project. Clusters usually have fixed cost: in `dev`, use a serverless or free-tier provider (e.g. Algolia free); `cluster-create` is `dedicated` only.

| Action | Input | Output |
|---|---|---|
| `search-describe` | project, environment | cluster/app, indexes, keys (names) |
| `cluster-create` | tier, region | cluster id, `cost.fixed: true` (`dedicated` only) |
| `index-create` | project, environment, index | index name |
| `api-key-create` | scope (search-only / admin), indexes | `secretRef` |
| `index-remove` | project, environment, index | removed |

---

## 6. Services

### auth-* (exclusive, project) — auth0, firebase-auth, aws-cognito

`shared`: one application per project in a shared tenant/pool.

| Action | Input | Output |
|---|---|---|
| `auth-describe` | project, environment | tenant, application, callback URLs, providers |
| `application-create` | project, environment, type (web/SPA/native/API) | client id, `secretRef` of the client secret |
| `application-configure` | callback/logout/origin URLs (derived from the environment hosts, each tenant's included) | applied settings |
| `providers-configure` | social/enterprise providers, `secretRef`s of their credentials | enabled providers |
| `application-remove` | project, environment | removed |

### email-* (exclusive, project) — sendgrid, aws-ses, mailgun

`shared`: a shared sending domain with per-project keys; sandbox/test mode (only verified recipients).

| Action | Input | Output |
|---|---|---|
| `email-describe` | domain, project | domain verified?, senders, keys (names), sandbox? |
| `domain-verify` | sending domain | `dnsRecords` (SPF, DKIM, DMARC, verification), status |
| `api-key-create` | project, environment, scope (send only) | `secretRef` |
| `sender-configure` | from address, reply-to | applied |
| `test-message-send` | recipient | delivered? |
| `api-key-remove` | project, environment | revoked |

### sms-* (exclusive, project) — twilio, vonage, sinch

Treated as special care (numbers and messages cost money). `test` mode by default.

| Action | Input | Output |
|---|---|---|
| `sms-describe` | project | numbers/senders, compliance status, keys (names) |
| `sender-setup` | country, type (number / alphanumeric / messaging service) | sender id, `cost.fixed: true` if a number is bought |
| `compliance-register` | use case, business data | status, usually `pending` (manual review) |
| `api-key-create` | project, environment | `secretRef` (test credentials in `test`) |
| `test-message-send` | recipient | delivered? |
| `sender-remove` | sender id | released (confirmed) |

### push-* (combinable, component) — fcm, apns, onesignal

`shared`: n/a (registrations are per app).

| Action | Input | Output |
|---|---|---|
| `push-describe` | component | registered platforms, credentials present (names) |
| `app-register` | component, platform (android/ios/web), app id / bundle id | app registration id, config file reference |
| `credentials-upload` | platform, `secretRef` (APNs key, FCM service account) | uploaded |
| `server-key-create` | component, environment | `secretRef` |
| `test-message-send` | device token / topic | delivered? |

### payments-* (combinable, project) — stripe, paypal, adyen

Special care. `test` mode by default; `shared`: n/a (one account, test mode in `dev` and `hom`).

| Action | Input | Output |
|---|---|---|
| `payments-describe` | project | account, mode, products, webhooks, keys (names) |
| `account-configure` | mode, business profile | applied; KYC items as `pending` |
| `catalog-create` | products/prices from the declaration | product and price ids |
| `webhook-setup` | endpoint (derived from the environment host), events | webhook id, `secretRef` of the signing secret |
| `api-key-create` | scope (restricted), environment | `secretRef` |
| `go-live` | — | live mode enabled (explicit confirmation; checklist) |
| `webhook-remove` | webhook id | removed |

### llm-* (combinable, project) — anthropic, openai, google-gemini

`shared`: one key per project in the shared workspace/organization.

| Action | Input | Output |
|---|---|---|
| `llm-describe` | project | workspace/project, keys (names), limits |
| `api-key-create` | project, environment | `secretRef` |
| `limits-configure` | spend limit, rate limits | applied (or `pending` if the plan doesn't allow) |
| `api-key-remove` | project, environment | revoked |

### flags-* (exclusive, project) — launchdarkly, unleash, flagsmith

`shared`: one project per aleogr project in a shared account.

| Action | Input | Output |
|---|---|---|
| `flags-describe` | project | project, environments, SDK keys (names) |
| `project-create` | project, environments (`dev`/`hom`/`prd`) | project id, environments |
| `sdk-key-create` | environment, type (server/client) | `secretRef` (client keys may go to `ciVariables` — not secret) |
| `project-remove` | project | removed |

Notes: flags themselves are defined by the application code, not by the contract.

---

## 7. Components

### stack-* (combinable, component) — typescript, python, java, go...

`shared`/`dedicated`: n/a. The "provider" is the technology.

| Action | Input | Output |
|---|---|---|
| `component-describe` | component directory | detected version; build/test/lint/format commands; CI parameters (reusable workflow + inputs); `devcontainerFeatures` (official + preferences layer); LSP server |
| `setup` | component name, component directory, language version, the module or package name the stack needs (Go: `github.com/<owner>/<repository>/<path>`), `dockerfile` (`yes` also writes the component's `Dockerfile`), `database` (`yes` also writes the component's database check, with `modules` and `minVersion`) | the starting point's files (`files`: the paths expected, whether this run wrote them), `dockerfile` (`written`, `would-write`, `present`, `not-asked`), with `database`: `database` (`written`, `would-write`, `present`, `not-asked`), `route` (`added`, `would-add`, `present`, `manual`, `not-asked`), `modules` (`added`, `would-add`, `present`, `not-needed`, `not-asked`), CI parameters (`ci`: the reusable workflow and its inputs); planned: contributions to shared files (marked sections), tool config (linter/formatter), `devcontainerFeatures` |

Notes:

- `setup` creates at most a minimal starting point, once, and never changes existing code. It writes its files only when the component has none (Go: when `<path>/go.mod` is missing), never overwrites one, and leaves a folder that holds code without the stack's manifest (Go: `.go` files and no `go.mod`) as it is, with `pending` and one `manual` item. `plan` reports `would-create` or `unchanged` and writes nothing.
- Go (`go_setup`): the files are exactly `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, filled from templates the plugin ships (an HTTP server with `GET /` and `GET /healthz` and one test per handler, standard library only). The version is `major.minor`, 1.22 or later. Without `database=yes` it needs no Go toolchain, writes with Claude Code's file tools and runs one read-only listing of the folder. `ci` is `{ "workflow": "ci-go.yml", "inputs": { "working-directory": "<path>", "go-version": "<version>" } }`.
- Go with `dockerfile=yes` (the orchestrator passes it when the declaration has environments): `<path>/Dockerfile` is written when missing, also for a component whose module exists (its other files untouched), and a `Dockerfile` that is there is never read or overwritten; whether it exists is learned from the one listing. Two stages: `golang:<version>` builds a static binary (`CGO_ENABLED=0`, `-trimpath`, `COPY go.mod go.sum* ./`), copied onto `gcr.io/distroless/static-debian13:nonroot`, run as `nonroot:nonroot`; base images by tag. A module that exists with no `Dockerfile` is `created` (`would-create` in `plan`); the files to commit are the three of `files` when `written` is true, plus the `Dockerfile` when `dockerfile` is `written`. Nothing is written (the `Dockerfile` neither) while the folder has Go files and no `go.mod`.
- Go with `database=yes modules=<module>@<version>,… minVersion=<major.minor>` (the orchestrator passes the modules and the minimum from `stacks.go.database` of its `defaults.json` for a component that declares the database): a `version` below `minVersion` fails before anything is written. `<path>/db.go` and `<path>/db_test.go` are written when missing; `main.go` gets the route `GET /db` only when it is byte for byte (`cmp`) the plugin's own `main.go` with the component's name filled in (a new component gets the variant with the route at once); otherwise it is left, `route` is `manual` and `pending` has the item `route` with the one line to add, which does not change the status. The modules are added, when `go.mod` lacks them and the component's code uses them, by `go -C <path> get <module>@<version> …` then `go -C <path> mod tidy`; the `go` line must stay the declared one (or the same followed by `.0`) and the `toolchain` line as it was, otherwise `go.mod` and `go.sum` are put back from `cp -p` copies and the run is `failed`. This is the only path of `go_setup` that runs `go`, and only in `apply`: Go must run where the skill runs (`go version` first; `failed` with one sentence otherwise, nothing written). The orchestrator checks it before any change with `aleogr:tools-check command=go` (`ok`, or `missing` with the install page), and its plan stops a run on a machine without Go when the modules are to be added. `files` gains `<path>/go.sum`, `<path>/db.go` and `<path>/db_test.go` after the three. No password and no connection string is ever written.
- The language version comes from the declaration and feeds both CI and devcontainer ([DESIGN.md section 10.6](DESIGN.md#106-whathow-split)).

### platform-* (combinable, component) — mobile, desktop, embedded, wearable

`shared`/`dedicated`: n/a. The "provider" is the platform (`android`, `ios`, `windows`, `zephyr`, `wearos`...).

| Action | Input | Output |
|---|---|---|
| `tools-check` | — | OS, SDK/toolchain, connected devices; what is not possible here |
| `component-describe` | component directory | toolchain version, required CI runner (e.g. macOS), build/test commands, limits (e.g. "no codespace build"), `devcontainerFeatures` |
| `setup` | component directory, toolchain version, app id / bundle id | toolchain config, contributions to shared files, `devcontainerFeatures`, CI parameters |
| `signing-setup` | component, environment, `secretRef` of the signing material | signing configured in CI (`ciSecrets` requests); special care |

Notes: embedded/wearable platforms may add extras such as `device-flash`.

### hosting-* (combinable, component) — vercel, netlify, cloudflare-pages

`shared`: one site per component in the shared account; deploys come from CI (thin workflow), not from the provider's Git integration, so CI stays the single path.

| Action | Input | Output |
|---|---|---|
| `site-describe` | component, environment | site, domains, env vars (names), last deploy |
| `site-create` | component, build command, output directory | site id; `ciSecrets` (deploy token) and `ciVariables` (site id) |
| `env-configure` | env vars, `secretRef`s | applied (names only) |
| `domain-add` | host (from the environment) | `dnsRecords`, TLS status |
| `site-remove` | component, environment | removed |

---

## 8. Operations

### monitoring-* (combinable, project) — sentry, datadog, new-relic

`shared`: one project per component in the shared organization.

| Action | Input | Output |
|---|---|---|
| `monitoring-describe` | project | projects per component, alert rules, keys (names) |
| `project-create` | component, platform | DSN/key (`secretRef`, or `ciVariables` when public by design) |
| `alerts-configure` | rules, target (notify-* channel) | applied rules |
| `releases-setup` | component | `ciSecrets` (release/source-map upload token) |
| `project-remove` | component | removed |

### analytics-* (combinable, component) — google-analytics, mixpanel, amplitude

`shared`: one property/stream per component and environment in the shared account.

| Action | Input | Output |
|---|---|---|
| `analytics-describe` | component | property/stream, measurement id, retention |
| `property-create` | component, environment, platform | measurement/project id (public: `ciVariables`), `secretRef` for server-side keys |
| `privacy-configure` | data retention, IP anonymization, consent mode | applied |
| `property-remove` | component, environment | removed |

### notify-* (combinable, project) — slack, microsoft-teams, discord

`shared`: n/a (channels are per project).

| Action | Input | Output |
|---|---|---|
| `channel-describe` | project | channel(s), connected sources |
| `channel-create` | project, purpose (`ci`, `alerts`, `general`) | channel id |
| `source-connect` | source (repo events, CI, monitoring), channel | applied integration; webhook as `secretRef` |
| `test-message-send` | channel | delivered? |
| `channel-archive` | channel | archived |

---

## 9. Collaboration

### tracker-* (exclusive, project) — jira, linear, asana

`shared`: n/a.

| Action | Input | Output |
|---|---|---|
| `tracker-describe` | project | tracker project/team, workflow, labels, repo link |
| `project-create` | project, key, template | project id, URL |
| `project-configure` | workflow states, labels/components (from the declaration's components) | applied |
| `repo-link` | repository | integration enabled (often `pending`: manual app install) |
| `project-archive` | project | archived |

### wiki-* (exclusive, project) — confluence, notion, gitbook

`shared`: n/a.

| Action | Input | Output |
|---|---|---|
| `wiki-describe` | project | space, root page, repo link |
| `space-create` | project | space id, URL |
| `page-publish` | title, source (file in the repo) | page id, URL |
| `space-archive` | project | archived |

---

## 10. Distribution

### store-* (combinable, component) — google-play, apple-app-store, microsoft-store

Special care. `test` mode = internal/test tracks only.

| Action | Input | Output |
|---|---|---|
| `app-describe` | component | app listing, tracks/releases, CI access |
| `app-create` | component, app id / bundle id, name | app record (often partially `pending`: manual console steps) |
| `listing-configure` | metadata source (files in the repo) | applied |
| `ci-access-setup` | component | `ciSecrets` (service account / API key), via secrets-* |
| `build-upload` | component, artifact, track (`internal` / `test`) | build id |
| `release-promote` | build id, target track (`production`) | promoted (explicit confirmation) |

### publish-* (combinable, component) — npm, pypi, maven-central

Special care. Dry-run by default.

| Action | Input | Output |
|---|---|---|
| `package-describe` | package name | exists?, owners, latest version, trusted publishing |
| `package-configure` | package name, repository, workflow | trusted publishing (OIDC) when supported; otherwise `ciSecrets` (token/signing key via secrets-*) |
| `release-publish` | component, version | published (explicit confirmation; dry-run shown first) |

Notes: package name reservation/namespace verification (e.g. Maven Central) is usually `pending` (manual).

---

## 11. Decisions and open items

Decided (reflected in DESIGN.md):

1. `aleogr-result` block with `requests` routing ([section 1.4](#14-output-the-aleogr-result-block)).
2. `*-describe` mandatory in every family.
3. New repo-* actions: `repo-describe`, `variables-set` (first planned as `ci-set-variable`), `repo-archive`.
4. New cloud-* actions: `ci-identity-setup`, `budget-alert-setup`, `deploy-remove`.
5. Project name `test` reserved, as well as the `test-` prefix.
6. sms-* and publish-* are special-care families.
7. hosting-*: deploys only from CI.
8. cache-* and search-* in `dev`: serverless or free tier.
9. dns-* in `dev` and `hom` is `record-add`: every hostname has its own record; there is no router and no `route-add`.
10. stack-* `setup` creates at most a minimal starting point, once, and never changes existing code.
11. repo-* `branch-protect` requires the check `ci` exactly when the project's `ci.yml` is on the default branch.
12. registry-*: the image repository is the project's own, one per project and environment, in its own cloud environment (no `shared` mode); `access-grant` grants `push` only; `cleanup-configure` owns the whole cleanup policy.
13. cloud-* `ci-identity-setup` accepts only the declared repository, checked by name and by numeric ids, on its default branch, and grants its account no role on the environment.
14. cloud-* `login-describe` and `login-setup`: the login of the organization is prepared once, as far as a command can; what is left (the console's clicks and the one command that takes the client's secret) is the owner's, and the secret never passes through a skill, its output or the conversation.
15. A refusal known to pass by itself is waited for by a bounded poll ([section 1.6](#16-waits)), never by a fixed pause or a stop.
16. cloud-* `deploy-setup` creates a service behind the login in the one command that creates it, with the placeholder image; it never changes an existing service's image (CI's job) and closes any open service before making anything.
17. cloud-* `ci-identity-setup` also requires the job to run the declared reusable deploy workflow; CI's roles are on each service and each service's account, never on the environment.
18. repo-* `ci-setup` writes a deploy job only for a component whose service exists, on push to the default branch only, with the four identifiers read from repository secrets (set by `variables-set kind=secrets`, which names them, never their values, in its result) and the region written in the file.
19. cloud-* `access-grant` lets in one person (`user:` only), on each service, and removes nothing.
20. db-* in `shared` mode on Cloud SQL creates no password and no `secretRef`: each component's user is its own service account, with IAM authentication; its connection roles are on the shared project, without a condition, and a binding under a condition counts as held.
21. db-* `database-create` and `access-grant` never start, stop or change the instance: on an instance that is not running they make nothing and end `pending`; only the orchestrator starts it, under `confirm=yes`.
22. cloud-* `deploy-describe` and `deploy-setup` carry a service's settings (`env`), compared and set by name, never removed or replaced, never with the image; values never reach a result block.
23. stack-* `setup` with `database=yes` replaces `main.go` only while it is the tooling's own file, and changes `go.mod`/`go.sum` only by the pinned `go get` and `go mod tidy`, putting them back from copies when the `go` line moves.
24. The orchestrator starts a shared instance that does not scale to zero only under `confirm=yes`, only when something must be made in it, after the code that uses it is written and right after a read that says its night stop is ready; the cost is said before (at the proposal, and in every plan that may lead to the start) and after the start.
