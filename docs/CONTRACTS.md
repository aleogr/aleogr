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

- Every family has a `*-describe` action. It is the basis of `project-plan` (comparing declaration × state × reality) and of the final verification of every action.

### 1.2 Modes

- **`plan` / `apply`** (every action except `*-describe`): `plan` reports what would change, without changing anything; `apply` executes. Both share the same logic, so `project-plan` never diverges from `project-apply`.
- **`pending` may be a `plan` result** for a feature the provider's plan forbids (e.g. branch protection on a private repository of a free GitHub organization): `plan` and `apply` both answer `pending`, change nothing and list one `plan-limit` item, so that they do not diverge ([DESIGN.md section 10.3](DESIGN.md#103-extending-contracts)). Only an answer of the provider that names the plan is `pending`; any other refusal is `failed`.
- **`shared` / `dedicated`** (families that create runtime resources): `shared` = inside the shared platform; `dedicated` = own resources. Default: `shared` in the `dev` project environment, `dedicated` elsewhere. Each family states below what `shared` means for it, or "n/a".
- **`test` / `live`** (special-care families: payments, registrar, store, sms, publish): `test` by default; `live` only with explicit confirmation.

### 1.3 Inputs

- Provider-neutral field names (`owner`, `name`, `environment`, `component`...). Provider-specific options live in the family plugin's sub-schema, under `options`.
- Every action that creates runtime resources receives `project`, `environment` (`dev` | `hom` | `prd`) and, for component-scoped families, `component`.
- Names and labels follow [DESIGN.md section 1](DESIGN.md#1-names); the skill derives them, the user never types them.
- **Secret values never pass through the conversation.** A secret input is a `secretRef` (`{ "store": "<secrets provider>", "name": "<name>" }`). A secret produced by an action (API key, password, signing key) is piped directly from the producing command into the secrets-* store, never printed; the output carries only its `secretRef`. When a human must type a value, the skill shows the command for the user to run with `!` (e.g. `! gh secret set NAME`).

### 1.4 Output: the `aleogr-result` block

Every skill ends with one fenced JSON block tagged `aleogr-result`. `project-apply` parses it, writes `state.json` and routes **requests** to other families.

```json
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "database-create",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "database", "id": "aleogr-shared/project1", "name": "project1",
      "labels": { "aleogr-project": "project1" } }
  ],
  "outputs": { "host": "...", "port": 5432, "database": "project1" },
  "secretRefs": { "password": { "store": "gcp-secret-manager", "name": "project1-db-password" } },
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

- `status`: `created` | `updated` | `unchanged` | `pending` | `failed` (apply); `would-create` | `would-update` | `unchanged` (plan, with a `changes` list), and `pending` (plan, only for a feature the provider's plan forbids, [section 1.2](#12-modes)) or `failed`.
- `requests` is the glue between families: a family never calls another family's skill; it asks, and the orchestrator routes the request in the right apply step ([DESIGN.md section 12.2](DESIGN.md#122-apply-order)):
  - `dnsRecords` → dns-* in step 8;
  - `ciSecrets` / `ciVariables` → repo-* `ci-set-secret` / `ci-set-variable` in step 10;
  - `devcontainerFeatures` → orchestrator assembles `devcontainer.json` in step 7;
  - `checks` → repo-* `branch-protect` (required checks) in step 10.
- `cost.fixed: true` means the action needed (and got) explicit confirmation.
- `pending` items end up in the project checklist.

### 1.5 Removal

- `*-remove` / `*-archive` actions are blocked by the destructive-command hook unless invoked from a confirmed `component-remove` / `service-remove`, or for test resources ([DESIGN.md section 13.1](DESIGN.md#131-hooks)).
- In `shared` mode, removal only touches resources carrying the project's name/label; never the shared platform.

---

## 2. Source and delivery

### repo-* (exclusive, project) — github, gitlab, bitbucket

`shared`/`dedicated`: n/a.

| Action | Input | Output |
|---|---|---|
| `repo-describe` | owner, name | exists, visibility, default branch, merge settings, protection, topics, secret/variable **names** |
| `repo-create` | owner, name, visibility (default `private`; `public` needs its own confirmation), description, topics, local directory (from stage 3c) | creates the repository with a README; HTTPS/SSH URLs, default branch, remote configured (from stage 3c) |
| `repo-configure` | owner, name, and only the settings to change: description, topics, merge methods, delete branch on merge, features (issues, wiki, projects), visibility (a change needs its own confirmation) | applied settings |
| `branch-protect` | branch, require PR, approvals, required checks, block force push/deletion | applied rules, or `pending` (plan limit, in `plan` and in `apply`) |
| `ci-set-secret` | name, scope (`repo` \| `org` \| `environment`), value source | name and scope (never the value) |
| `ci-set-variable` | name, value, scope (`repo` \| `org` \| `environment`) | name, scope, value |
| `ci-setup` | components (directory, stack/platform CI parameters), project environments | generated files (`ci.yml`, `cd.yml`), `checks` (required check names) |
| `repo-archive` | owner, name | archived |

Notes:

- `branch-protect` runs twice in apply: step 1 (no checks yet) and step 10 (with `checks` from `ci-setup`).
- `repo-create` creates the repository with a README, so that the default branch exists from the start (a protection that requires pull requests could block the first commit of an empty repository). On an existing repository it changes nothing (`unchanged`) and lists what differs from its inputs; `repo-configure` is the only action that corrects an existing repository.
- `repo-configure` compares and changes only the settings it is given: a setting left out is left as it is.
- Visibility: nothing becomes public, at creation or by a change, without the confirmation `confirmVisibility=public`; a change to private needs `confirmVisibility=private`. Without it the action does not wait for an answer: it changes nothing of the visibility, asks the question and gives the exact command that confirms it.
- `pending` as a status means nothing was changed: the run waits for the visibility confirmation, or the provider's plan forbids the protection. Once something was done the status says what (`created`, `updated`) and anything left is an item in the `pending` list.
- `branch-protect` on a plan without branch protection (on GitHub, a private repository of a free organization): `pending` in `plan` and in `apply`, nothing changed, one `plan-limit` item; the default branch is then held by the working rule (the owner merges).
- On GitHub, a description may not contain `"`, a backtick, `$`, `\` or a line break: it is passed in double quotes on a command line.
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
| `ci-identity-setup` | repository (owner/name), allowed branches/environments, roles | keyless CI identity (OIDC / workload identity federation); `ciVariables` with its non-secret identifiers |
| `deploy-setup` | component, image or source, environment, hosts, access (login or public), scaling (min 0 and a maximum of instances in `dev`), env vars, `secretRef`s | service name, public hostname; `dnsRecords` |
| `access-grant` | component, environment, person (e-mail) | applied binding |
| `deploy-remove` | component, environment | removed |
| `budget-alert-setup` | display name, amount, currency, thresholds, quota project (scope: the whole billing account; per project and notification target planned) | display name (the alert id) |

Notes:

- On GCP the parent of an environment is the folder of its environment, under the organization or, with `root=tst`, inside the folder `tst`; the shared platform project (`platform=shared`) is the exception, created directly under the organization (DESIGN.md section 6.7). The skill never creates folders. The skill discovers the parent and the billing account; the owner never types them.
- Implemented: `environment-describe`, `environment-create`, `services-enable` and `budget-alert-setup` (skills in `.claude-plugin/plugins/aleogr-cloud-gcp/skills/`). The other actions are planned.
- CI never gets long-lived cloud keys: `ci-identity-setup` uses OIDC federation.
- `deploy-setup` maps every declared host to the service (the environment's host and one per tenant) and returns one `dnsRecords` request per host. There is no wildcard in `dev` and `hom` (DESIGN.md section 6.1).
- In `dev`, `deploy-setup` must scale to zero, use the smallest size and set a maximum of instances (DESIGN.md section 6.5).
- In `dev` and `hom`, `deploy-setup` puts the login in front of the service unless the component is declared public (DESIGN.md section 6.3); `access-grant` adds a person to the allowed list.
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

`shared`: database + user on the shared platform's single instance.

`instance-describe`, `instance-start`, `instance-stop` and `instance-switch-setup` are actions of providers whose instances do not scale to zero (`gcp-cloud-sql`): the instance stays stopped and is started on demand ([DESIGN.md](DESIGN.md) section 6.8).

| Action | Input | Output |
|---|---|---|
| `database-describe` | project, environment | instance, database, users, size tier, backups |
| `instance-create` | engine, version, tier, region; `platform` (`shared`: the shared platform's instance, passed only by the orchestrator's platform skills); optional `stopJob` (the scheduler job that stops the instance at night: run once to stop the new instance, which proves it works) | instance id, `cost.fixed: true` (`dedicated` only; refused in `dev`, except `platform=shared`) |
| `instance-describe` | project id, instance name | exists, state (`stopped`, `starting`, `running`, `creating`), settings, last backup |
| `instance-start` | project id, instance name | state seen after the change (`starting`, `running`, or briefly `stopped`) |
| `instance-stop` | project id, instance name | state (`stopped`) |
| `instance-switch-setup` | project id, instance name, region, time zone, stop schedules, repository, `mode` | `ready`, parts still missing; in the answer's prose, the values of the GitHub secrets |
| `database-create` | project, engine, environment | host/port/database, connection method, `secretRef` of the password (generated) |
| `access-grant` | identity (runtime, CI migrations), database | applied grants / connection permissions |
| `backup-configure` | schedule, retention, point-in-time | applied policy (`prd`) |
| `database-remove` | project, environment | removed (guarded; dump offered first) |

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

### registry-* (exclusive, project) — docker-hub, ghcr, aws-ecr

`shared`: a repository per project in the shared registry.

| Action | Input | Output |
|---|---|---|
| `registry-describe` | project | registry, repositories, retention, access |
| `repository-create` | project, component | image path |
| `access-grant` | identity, role (`push` for CI, `pull` for runtime) | applied bindings |
| `cleanup-configure` | keep last N / max age | applied retention policy |
| `repository-remove` | project, component | removed |

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
| `setup` | component directory, language version | contributions to shared files (marked sections), tool config (linter/formatter), `devcontainerFeatures`, CI parameters |

Notes:

- `setup` never creates application code; it prepares tooling around the component.
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
3. New repo-* actions: `repo-describe`, `ci-set-variable`, `repo-archive`.
4. New cloud-* actions: `ci-identity-setup`, `budget-alert-setup`, `deploy-remove`.
5. Project name `test` reserved, as well as the `test-` prefix.
6. sms-* and publish-* are special-care families.
7. hosting-*: deploys only from CI.
8. cache-* and search-* in `dev`: serverless or free tier.
9. dns-* in `dev` and `hom` is `record-add`: every hostname has its own record; there is no router and no `route-add`.
