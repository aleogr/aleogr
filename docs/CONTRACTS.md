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

- Tables below list **actions**; the skill is `<provider>-<action>` (e.g. action `create-repo` → skill `github-create-repo`). For stack-* and platform-* the "provider" is the technology/platform (`go-setup`, `android-setup`).
- Standard verbs, used consistently across families:

| Verb | Meaning | Changes anything? |
|---|---|---|
| `describe-*` | Reads the real state and returns it normalized | no |
| `create-*` | Creates a resource (idempotent: existing and matching = `unchanged`) | yes |
| `configure-*` | Brings settings of an existing resource to the declared values | yes |
| `setup-*` | Composite preparation (several resources/files for one purpose) | yes |
| `grant-*` | Gives an identity access to a resource | yes |
| `remove-*` / `archive-*` | Removes or archives; always guarded (destructive hook + confirmation) | yes |

- Every family has a `describe-*` action. It is the basis of `plan-project` (comparing declaration × state × reality) and of the final verification of every action.

### 1.2 Modes

- **`plan` / `apply`** (every action except `describe-*`): `plan` reports what would change, without changing anything; `apply` executes. Both share the same logic, so `plan-project` never diverges from `apply-project`.
- **`shared` / `dedicated`** (families that create runtime resources): `shared` = inside the lab platform; `dedicated` = own resources. Default: `shared` in the `lab` project environment, `dedicated` elsewhere. Each family states below what `shared` means for it, or "n/a".
- **`test` / `live`** (special-care families: payments, registrar, store, sms, publish): `test` by default; `live` only with explicit confirmation.

### 1.3 Inputs

- Provider-neutral field names (`owner`, `name`, `environment`, `component`...). Provider-specific options live in the family plugin's sub-schema, under `options`.
- Every action that creates runtime resources receives `project`, `environment` (`lab` | `homolog` | `prod`) and, for component-scoped families, `component`.
- Names and labels follow [DESIGN.md section 1](DESIGN.md#1-names); the skill derives them, the user never types them.
- **Secret values never pass through the conversation.** A secret input is a `secretRef` (`{ "store": "<secrets provider>", "name": "<name>" }`). A secret produced by an action (API key, password, signing key) is piped directly from the producing command into the secrets-* store, never printed; the output carries only its `secretRef`. When a human must type a value, the skill shows the command for the user to run with `!` (e.g. `! gh secret set NAME`).

### 1.4 Output: the `aleogr-result` block

Every skill ends with one fenced JSON block tagged `aleogr-result`. `apply-project` parses it, writes `state.json` and routes **requests** to other families.

```json
{
  "aleogr-result": 1,
  "family": "db",
  "provider": "gcp-cloud-sql",
  "action": "create-database",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "database", "id": "lab-instance/project1", "name": "project1",
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

- `status`: `created` | `updated` | `unchanged` | `pending` | `failed` (apply); `would-create` | `would-update` | `unchanged` (plan, with a `changes` list).
- `requests` is the glue between families: a family never calls another family's skill; it asks, and the orchestrator routes the request in the right apply step ([DESIGN.md section 12.2](DESIGN.md#122-apply-order)):
  - `dnsRecords` → dns-* (or the lab single access point) in step 8;
  - `ciSecrets` / `ciVariables` → repo-* `set-ci-secret` / `set-ci-variable` in step 10;
  - `devcontainerFeatures` → orchestrator assembles `devcontainer.json` in step 7;
  - `checks` → repo-* `protect-branch` (required checks) in step 10.
- `cost.fixed: true` means the action needed (and got) explicit confirmation.
- `pending` items end up in the project checklist.

### 1.5 Removal

- `remove-*` / `archive-*` actions are blocked by the destructive-command hook unless invoked from a confirmed `remove-component` / `remove-service`, or for test resources ([DESIGN.md section 13.1](DESIGN.md#131-hooks)).
- In `shared` mode, removal only touches resources carrying the project's name/label; never the shared platform.

---

## 2. Source and delivery

### repo-* (exclusive, project) — github, gitlab, bitbucket

`shared`/`dedicated`: n/a.

| Action | Input | Output |
|---|---|---|
| `describe-repo` | owner, name | exists, visibility, default branch, merge settings, protection, topics, secret/variable **names** |
| `create-repo` | owner, name, visibility, description, topics, local directory | HTTPS/SSH URLs, default branch, remote configured |
| `configure-repo` | merge methods, delete branch on merge, features (issues, wiki, projects) | applied settings |
| `protect-branch` | branch, require PR, approvals, required checks, block force push/deletion | applied rules, or `pending` (plan limit) |
| `set-ci-secret` | name, scope (`repo` \| `org` \| `environment`), value source | name and scope (never the value) |
| `set-ci-variable` | name, value, scope (`repo` \| `org` \| `environment`) | name, scope, value |
| `setup-ci` | components (directory, stack/platform CI parameters), project environments | generated files (`ci.yml`, `cd.yml`), `checks` (required check names) |
| `archive-repo` | owner, name | archived |

Notes:

- `protect-branch` runs twice in apply: step 1 (no checks yet) and step 10 (with `checks` from `setup-ci`).
- Project environments (`lab`/`homolog`/`prod`) map to the provider's deployment environments; covered by the `environment` scope.
- Repository deletion is not in the contract: only the test cleanup deletes repositories.
- Bitbucket has no topics; the federated layout and tests depend on topics (recorded limitation).
- Topic `aleogr-<project>` would collide with `aleogr-test` for a project named `test`: that is why the name `test` is reserved as well as the `test-` prefix ([DESIGN.md section 1](DESIGN.md#tests)).

---

## 3. Domain

### registrar-* (exclusive per domain, domain) — godaddy, namecheap, cloudflare

Special care. `shared`/`dedicated`: n/a.

| Action | Input | Output |
|---|---|---|
| `describe-domain` | domain | registered?, owner account, expiry, auto-renew, lock, privacy, nameservers |
| `check-availability` | domain(s) | available?, price (registration and renewal) |
| `register-domain` | domain, years, contact profile | registered, expiry, `cost.fixed: true` (always confirmed) |
| `set-nameservers` | domain, nameservers (from dns-* `create-zone`) | applied nameservers |
| `configure-domain` | auto-renew, transfer lock, WHOIS privacy | applied settings |

Notes: no transfer or deletion in the contract. Renewal price is always shown before registration.

### dns-* (exclusive per domain, domain) — cloudflare, aws-route53, gcp-cloud-dns

`shared`: records in the `aleogr.dev` zone under `lab.aleogr.dev` (or a route in the single access point — **pending**, DESIGN.md section 18).

| Action | Input | Output |
|---|---|---|
| `describe-zone` | zone | exists, nameservers, records (filterable by name pattern) |
| `create-zone` | zone | zone id, nameservers (request to registrar-* `set-nameservers`) |
| `add-record` | name, type, target, TTL, proxied (if supported) | record id; upsert (idempotent) |
| `remove-record` | name, type | removed |

Notes:

- `add-record` consumes the `dnsRecords` requests of every other family (deploy hostnames, tenant wildcards, e-mail SPF/DKIM/DMARC, domain verification TXT).
- If the lab single access point is a router, a sibling action `add-route` replaces `add-record` in `shared` mode (decided after the investigation).

### cdn-* (exclusive per domain, domain) — cloudflare, akamai, aws-cloudfront

`shared`: the lab's edge configuration (proxy, Access, certificates) is platform-level; projects only get cache rules if needed.

| Action | Input | Output |
|---|---|---|
| `describe-cdn` | host(s) | CDN on/off, origin, cache rules, TLS coverage |
| `setup-cdn` | host, origin, cache profile (`static` \| `dynamic` \| `off`) | distribution/proxy enabled, `dnsRecords` if the CDN needs its own target |
| `configure-cache` | host, rules (paths, TTLs, bypass) | applied rules |
| `setup-tls` | hosts (incl. wildcards) | coverage per host, or `pending` (plan limit) |
| `purge-cache` | host, paths (or all) | purged |
| `remove-cdn` | host | removed |

Notes: `setup-tls` is where the certificate decision lands (DESIGN.md section 6.2, pending investigation).

---

## 4. Cloud base

### cloud-* (combinable with exactly one primary, project) — aws, azure, gcp

`shared`: the lab's cloud environment already exists; `create-environment` only verifies it and returns its id.

| Action | Input | Output |
|---|---|---|
| `describe-environment` | environment id or project | exists, enabled services, identities, budget alerts |
| `create-environment` | project, billing reference, region | environment id (GCP project / AWS account / Azure subscription + resource group) |
| `enable-services` | capabilities (neutral list: `run`, `sql`, `secrets`, `storage`, `registry`...) | enabled provider APIs/services |
| `setup-ci-identity` | repository (owner/name), allowed branches/environments, roles | keyless CI identity (OIDC / workload identity federation); `ciVariables` with its non-secret identifiers |
| `setup-deploy` | component, image or source, environment, scaling (min 0 in lab), env vars, `secretRef`s | service name, public hostname; `dnsRecords` |
| `remove-deploy` | component, environment | removed |
| `setup-budget-alert` | scope (lab platform or project), amount, thresholds, notification target | alert id |

Notes:

- CI never gets long-lived cloud keys: `setup-ci-identity` uses OIDC federation.
- In `lab`, `setup-deploy` must scale to zero and use the smallest size (DESIGN.md section 6.5).
- Only the primary cloud receives secrets-* by default.

### secrets-* (exclusive, project) — aws-secrets-manager, gcp-secret-manager, azure-key-vault

`shared`: the lab platform's vault, names prefixed with the project.

| Action | Input | Output |
|---|---|---|
| `describe-store` | project | store exists, secret **names** (prefix-filtered), versions, accessors |
| `create-store` | project, region | store id (in `shared`: verification only) |
| `store-secret` | name, value source (`generate` \| `pipe` from a command \| `user` via `!`) | `secretRef`, version (never the value) |
| `grant-access` | identity, secret names or prefix, role (read) | applied bindings |
| `remove-secret` | name | removed (versions destroyed only with confirmation) |

Notes: `generate` covers database passwords and similar; `pipe` covers keys produced by other providers' CLIs.

---

## 5. Infrastructure

### db-* (combinable, project) — aws-rds, gcp-cloud-sql, azure-sql

`shared`: database + user on the lab's single instance.

| Action | Input | Output |
|---|---|---|
| `describe-database` | project, environment | instance, database, users, size tier, backups |
| `create-instance` | engine, version, tier, region | instance id, `cost.fixed: true` (`dedicated` only; refused in `lab`) |
| `create-database` | project, engine, environment | host/port/database, connection method, `secretRef` of the password (generated) |
| `grant-access` | identity (runtime, CI migrations), database | applied grants / connection permissions |
| `configure-backup` | schedule, retention, point-in-time | applied policy (`prod`) |
| `remove-database` | project, environment | removed (guarded; dump offered first) |

### cache-* (exclusive, project) — aws-elasticache, gcp-memorystore, redis-cloud

`shared`: a key namespace (prefix + ACL user) per project. Managed caches usually have fixed cost: in `lab`, use a serverless or free-tier provider (e.g. Upstash, Redis Cloud free); `create-instance` is `dedicated` only.

| Action | Input | Output |
|---|---|---|
| `describe-cache` | project, environment | instance, namespace, ACL users, tier |
| `create-instance` | tier, region | instance id, `cost.fixed: true` (`dedicated` only) |
| `create-namespace` | project, environment | endpoint, key prefix, `secretRef` of the credentials |
| `remove-namespace` | project, environment | removed |

### storage-* (combinable, project) — aws-s3, gcp-storage, azure-blob

`shared`: a prefix in the lab bucket. `dedicated`: own bucket (names are global: convention + short suffix).

| Action | Input | Output |
|---|---|---|
| `describe-bucket` | project, environment, purpose | bucket/prefix, access, lifecycle, CORS |
| `create-bucket` | project, environment, purpose, region | bucket name (or prefix in `shared`) |
| `configure-bucket` | public access (default off), versioning, lifecycle, CORS | applied settings |
| `grant-access` | identity, role (read/write) | applied bindings |
| `remove-bucket` | project, environment, purpose | removed (empty first, with confirmation) |

### registry-* (exclusive, project) — docker-hub, ghcr, aws-ecr

`shared`: a repository per project in the lab registry.

| Action | Input | Output |
|---|---|---|
| `describe-registry` | project | registry, repositories, retention, access |
| `create-repository` | project, component | image path |
| `grant-access` | identity, role (`push` for CI, `pull` for runtime) | applied bindings |
| `configure-cleanup` | keep last N / max age | applied retention policy |
| `remove-repository` | project, component | removed |

### search-* (exclusive, project) — elastic, algolia, aws-opensearch

`shared`: indexes prefixed with the project. Clusters usually have fixed cost: in `lab`, use a serverless or free-tier provider (e.g. Algolia free); `create-cluster` is `dedicated` only.

| Action | Input | Output |
|---|---|---|
| `describe-search` | project, environment | cluster/app, indexes, keys (names) |
| `create-cluster` | tier, region | cluster id, `cost.fixed: true` (`dedicated` only) |
| `create-index` | project, environment, index | index name |
| `create-api-key` | scope (search-only / admin), indexes | `secretRef` |
| `remove-index` | project, environment, index | removed |

---

## 6. Services

### auth-* (exclusive, project) — auth0, firebase-auth, aws-cognito

`shared`: one application per project in a lab-wide tenant/pool.

| Action | Input | Output |
|---|---|---|
| `describe-auth` | project, environment | tenant, application, callback URLs, providers |
| `create-application` | project, environment, type (web/SPA/native/API) | client id, `secretRef` of the client secret |
| `configure-application` | callback/logout/origin URLs (derived from the environment hosts, tenant wildcards included) | applied settings |
| `configure-providers` | social/enterprise providers, `secretRef`s of their credentials | enabled providers |
| `remove-application` | project, environment | removed |

### email-* (exclusive, project) — sendgrid, aws-ses, mailgun

`shared`: lab sending domain with per-project keys; sandbox/test mode (only verified recipients).

| Action | Input | Output |
|---|---|---|
| `describe-email` | domain, project | domain verified?, senders, keys (names), sandbox? |
| `verify-domain` | sending domain | `dnsRecords` (SPF, DKIM, DMARC, verification), status |
| `create-api-key` | project, environment, scope (send only) | `secretRef` |
| `configure-sender` | from address, reply-to | applied |
| `send-test` | recipient | delivered? |
| `remove-api-key` | project, environment | revoked |

### sms-* (exclusive, project) — twilio, vonage, sinch

Treated as special care (numbers and messages cost money). `test` mode by default.

| Action | Input | Output |
|---|---|---|
| `describe-sms` | project | numbers/senders, compliance status, keys (names) |
| `setup-sender` | country, type (number / alphanumeric / messaging service) | sender id, `cost.fixed: true` if a number is bought |
| `register-compliance` | use case, business data | status, usually `pending` (manual review) |
| `create-api-key` | project, environment | `secretRef` (test credentials in `test`) |
| `send-test` | recipient | delivered? |
| `remove-sender` | sender id | released (confirmed) |

### push-* (combinable, component) — fcm, apns, onesignal

`shared`: n/a (registrations are per app).

| Action | Input | Output |
|---|---|---|
| `describe-push` | component | registered platforms, credentials present (names) |
| `register-app` | component, platform (android/ios/web), app id / bundle id | app registration id, config file reference |
| `upload-credentials` | platform, `secretRef` (APNs key, FCM service account) | uploaded |
| `create-server-key` | component, environment | `secretRef` |
| `send-test` | device token / topic | delivered? |

### payments-* (combinable, project) — stripe, paypal, adyen

Special care. `test` mode by default; `shared`: n/a (one account, test mode in lab).

| Action | Input | Output |
|---|---|---|
| `describe-payments` | project | account, mode, products, webhooks, keys (names) |
| `configure-account` | mode, business profile | applied; KYC items as `pending` |
| `create-catalog` | products/prices from the declaration | product and price ids |
| `setup-webhook` | endpoint (derived from the environment host), events | webhook id, `secretRef` of the signing secret |
| `create-api-key` | scope (restricted), environment | `secretRef` |
| `go-live` | — | live mode enabled (explicit confirmation; checklist) |
| `remove-webhook` | webhook id | removed |

### llm-* (combinable, project) — anthropic, openai, google-gemini

`shared`: one key per project in the lab workspace/organization.

| Action | Input | Output |
|---|---|---|
| `describe-llm` | project | workspace/project, keys (names), limits |
| `create-api-key` | project, environment | `secretRef` |
| `configure-limits` | spend limit, rate limits | applied (or `pending` if the plan doesn't allow) |
| `remove-api-key` | project, environment | revoked |

### flags-* (exclusive, project) — launchdarkly, unleash, flagsmith

`shared`: one project per lab project in a lab-wide account.

| Action | Input | Output |
|---|---|---|
| `describe-flags` | project | project, environments, SDK keys (names) |
| `create-project` | project, environments (`lab`/`homolog`/`prod`) | project id, environments |
| `create-sdk-key` | environment, type (server/client) | `secretRef` (client keys may go to `ciVariables` — not secret) |
| `remove-project` | project | removed |

Notes: flags themselves are defined by the application code, not by the contract.

---

## 7. Components

### stack-* (combinable, component) — typescript, python, java, go...

`shared`/`dedicated`: n/a. The "provider" is the technology.

| Action | Input | Output |
|---|---|---|
| `describe-component` | component directory | detected version; build/test/lint/format commands; CI parameters (reusable workflow + inputs); `devcontainerFeatures` (official + preferences layer); LSP server |
| `setup` | component directory, language version | contributions to shared files (marked sections), tool config (linter/formatter), `devcontainerFeatures`, CI parameters |

Notes:

- `setup` never creates application code; it prepares tooling around the component.
- The language version comes from the declaration and feeds both CI and devcontainer ([DESIGN.md section 10.6](DESIGN.md#106-whathow-split)).

### platform-* (combinable, component) — mobile, desktop, embedded, wearable

`shared`/`dedicated`: n/a. The "provider" is the platform (`android`, `ios`, `windows`, `zephyr`, `wearos`...).

| Action | Input | Output |
|---|---|---|
| `check-environment` | — | OS, SDK/toolchain, connected devices; what is not possible here |
| `describe-component` | component directory | toolchain version, required CI runner (e.g. macOS), build/test commands, limits (e.g. "no codespace build"), `devcontainerFeatures` |
| `setup` | component directory, toolchain version, app id / bundle id | toolchain config, contributions to shared files, `devcontainerFeatures`, CI parameters |
| `setup-signing` | component, environment, `secretRef` of the signing material | signing configured in CI (`ciSecrets` requests); special care |

Notes: embedded/wearable platforms may add extras such as `flash-device`.

### hosting-* (combinable, component) — vercel, netlify, cloudflare-pages

`shared`: one site per component in the lab account; deploys come from CI (thin workflow), not from the provider's Git integration, so CI stays the single path.

| Action | Input | Output |
|---|---|---|
| `describe-site` | component, environment | site, domains, env vars (names), last deploy |
| `create-site` | component, build command, output directory | site id; `ciSecrets` (deploy token) and `ciVariables` (site id) |
| `configure-env` | env vars, `secretRef`s | applied (names only) |
| `add-domain` | host (from the environment) | `dnsRecords`, TLS status |
| `remove-site` | component, environment | removed |

---

## 8. Operations

### monitoring-* (combinable, project) — sentry, datadog, new-relic

`shared`: one project per component in the lab organization.

| Action | Input | Output |
|---|---|---|
| `describe-monitoring` | project | projects per component, alert rules, keys (names) |
| `create-project` | component, platform | DSN/key (`secretRef`, or `ciVariables` when public by design) |
| `configure-alerts` | rules, target (notify-* channel) | applied rules |
| `setup-releases` | component | `ciSecrets` (release/source-map upload token) |
| `remove-project` | component | removed |

### analytics-* (combinable, component) — google-analytics, mixpanel, amplitude

`shared`: one property/stream per component and environment in the lab account.

| Action | Input | Output |
|---|---|---|
| `describe-analytics` | component | property/stream, measurement id, retention |
| `create-property` | component, environment, platform | measurement/project id (public: `ciVariables`), `secretRef` for server-side keys |
| `configure-privacy` | data retention, IP anonymization, consent mode | applied |
| `remove-property` | component, environment | removed |

### notify-* (combinable, project) — slack, microsoft-teams, discord

`shared`: n/a (channels are per project).

| Action | Input | Output |
|---|---|---|
| `describe-channel` | project | channel(s), connected sources |
| `create-channel` | project, purpose (`ci`, `alerts`, `general`) | channel id |
| `connect-source` | source (repo events, CI, monitoring), channel | applied integration; webhook as `secretRef` |
| `send-test` | channel | delivered? |
| `archive-channel` | channel | archived |

---

## 9. Collaboration

### tracker-* (exclusive, project) — jira, linear, asana

`shared`: n/a.

| Action | Input | Output |
|---|---|---|
| `describe-tracker` | project | tracker project/team, workflow, labels, repo link |
| `create-project` | project, key, template | project id, URL |
| `configure-project` | workflow states, labels/components (from the declaration's components) | applied |
| `link-repo` | repository | integration enabled (often `pending`: manual app install) |
| `archive-project` | project | archived |

### wiki-* (exclusive, project) — confluence, notion, gitbook

`shared`: n/a.

| Action | Input | Output |
|---|---|---|
| `describe-wiki` | project | space, root page, repo link |
| `create-space` | project | space id, URL |
| `publish-page` | title, source (file in the repo) | page id, URL |
| `archive-space` | project | archived |

---

## 10. Distribution

### store-* (combinable, component) — google-play, apple-app-store, microsoft-store

Special care. `test` mode = internal/test tracks only.

| Action | Input | Output |
|---|---|---|
| `describe-app` | component | app listing, tracks/releases, CI access |
| `create-app` | component, app id / bundle id, name | app record (often partially `pending`: manual console steps) |
| `configure-listing` | metadata source (files in the repo) | applied |
| `setup-ci-access` | component | `ciSecrets` (service account / API key), via secrets-* |
| `upload-build` | component, artifact, track (`internal` / `test`) | build id |
| `promote-release` | build id, target track (`production`) | promoted (explicit confirmation) |

### publish-* (combinable, component) — npm, pypi, maven-central

Special care. Dry-run by default.

| Action | Input | Output |
|---|---|---|
| `describe-package` | package name | exists?, owners, latest version, trusted publishing |
| `configure-package` | package name, repository, workflow | trusted publishing (OIDC) when supported; otherwise `ciSecrets` (token/signing key via secrets-*) |
| `publish-release` | component, version | published (explicit confirmation; dry-run shown first) |

Notes: package name reservation/namespace verification (e.g. Maven Central) is usually `pending` (manual).

---

## 11. Decisions and open items

Decided (reflected in DESIGN.md):

1. `aleogr-result` block with `requests` routing ([section 1.4](#14-output-the-aleogr-result-block)).
2. `describe-*` mandatory in every family.
3. New repo-* actions: `describe-repo`, `set-ci-variable`, `archive-repo`.
4. New cloud-* actions: `setup-ci-identity`, `setup-budget-alert`, `remove-deploy`.
5. Project name `test` reserved, as well as the `test-` prefix.
6. sms-* and publish-* are special-care families.
7. hosting-*: deploys only from CI.
8. cache-* and search-* in `lab`: serverless or free tier.

Open:

9. dns-* in `lab`: `add-record` vs `add-route` — depends on the lab investigation ([DESIGN.md section 18](DESIGN.md#18-open-items)).
