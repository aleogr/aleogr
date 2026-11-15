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
- **`shared` / `dedicated`** (families that create runtime resources): `shared` = inside the lab platform; `dedicated` = own resources. Default: `shared` in the `lab` project environment, `dedicated` elsewhere. Each family states below what `shared` means for it, or "n/a".
- **`test` / `live`** (special-care families: payments, registrar, store, sms, publish): `test` by default; `live` only with explicit confirmation.

### 1.3 Inputs

- Provider-neutral field names (`owner`, `name`, `environment`, `component`...). Provider-specific options live in the family plugin's sub-schema, under `options`.
- Every action that creates runtime resources receives `project`, `environment` (`lab` | `hom` | `prod`) and, for component-scoped families, `component`.
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
  - `ciSecrets` / `ciVariables` → repo-* `ci-set-secret` / `ci-set-variable` in step 10;
  - `devcontainerFeatures` → orchestrator assembles `devcontainer.json` in step 7;
  - `checks` → repo-* `protect-branch` (required checks) in step 10.
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
| `repo-create` | owner, name, visibility, description, topics, local directory | HTTPS/SSH URLs, default branch, remote configured |
| `repo-configure` | merge methods, delete branch on merge, features (issues, wiki, projects) | applied settings |
| `protect-branch` | branch, require PR, approvals, required checks, block force push/deletion | applied rules, or `pending` (plan limit) |
| `ci-set-secret` | name, scope (`repo` \| `org` \| `environment`), value source | name and scope (never the value) |
| `ci-set-variable` | name, value, scope (`repo` \| `org` \| `environment`) | name, scope, value |
| `ci-setup` | components (directory, stack/platform CI parameters), project environments | generated files (`ci.yml`, `cd.yml`), `checks` (required check names) |
| `repo-archive` | owner, name | archived |

Notes:

- `protect-branch` runs twice in apply: step 1 (no checks yet) and step 10 (with `checks` from `ci-setup`).
- Project environments (`lab`/`hom`/`prod`) map to the provider's deployment environments; covered by the `environment` scope.
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

`shared`: records in the `aleogr.dev` zone under `lab.aleogr.dev` (or a route in the single access point — **pending**, DESIGN.md section 18).

| Action | Input | Output |
|---|---|---|
| `zone-describe` | zone | exists, nameservers, records (filterable by name pattern) |
| `zone-create` | zone | zone id, nameservers (request to registrar-* `nameservers-set`) |
| `record-add` | name, type, target, TTL, proxied (if supported; off in `lab` and `hom`, on in `prod`) | record id; upsert (idempotent) |
| `record-remove` | name, type | removed |

Notes:

- `record-add` consumes the `dnsRecords` requests of every other family (deploy hostnames, tenant wildcards, e-mail SPF/DKIM/DMARC, domain verification TXT).
- If the lab single access point is a router, a sibling action `route-add` replaces `record-add` in `shared` mode (decided after the investigation).

### cdn-* (exclusive per domain, domain) — cloudflare, akamai, aws-cloudfront

`shared`: n/a. Records in `lab` and `hom` are unproxied (DESIGN.md section 6.2), so there is no CDN in front of them; cdn-* applies to `prod`.

| Action | Input | Output |
|---|---|---|
| `cdn-describe` | host(s) | CDN on/off, origin, cache rules, TLS coverage |
| `cdn-setup` | host, origin, cache profile (`static` \| `dynamic` \| `off`) | distribution/proxy enabled, `dnsRecords` if the CDN needs its own target |
| `cache-configure` | host, rules (paths, TTLs, bypass) | applied rules |
| `tls-setup` | hosts (incl. wildcards) | coverage per host, or `pending` (plan limit) |
| `cache-purge` | host, paths (or all) | purged |
| `cdn-remove` | host | removed |

Notes: `tls-setup` covers proxied hosts, that is, `prod` (a multi-tenant project needs its own domain to be covered by the free certificate). In `lab` and `hom` the certificate is issued by the destination (DESIGN.md section 6.2).

---

## 4. Cloud base

### cloud-* (combinable with exactly one primary, project) — aws, azure, gcp

`shared`: the lab's cloud environment already exists; `environment-create` only verifies it and returns its id.

| Action | Input | Output |
|---|---|---|
| `environment-describe` | environment id or project | exists, enabled services, identities, budget alerts |
| `environment-create` | project, billing reference, region | environment id (GCP project / AWS account / Azure subscription + resource group) |
| `services-enable` | capabilities (neutral list: `run`, `sql`, `secrets`, `storage`, `registry`...) | enabled provider APIs/services |
| `ci-identity-setup` | repository (owner/name), allowed branches/environments, roles | keyless CI identity (OIDC / workload identity federation); `ciVariables` with its non-secret identifiers |
| `deploy-setup` | component, image or source, environment, scaling (min 0 in lab), env vars, `secretRef`s | service name, public hostname; `dnsRecords` |
| `deploy-remove` | component, environment | removed |
| `budget-alert-setup` | scope (lab platform or project), amount, thresholds, notification target | alert id |

Notes:

- CI never gets long-lived cloud keys: `ci-identity-setup` uses OIDC federation.
- In `lab`, `deploy-setup` must scale to zero and use the smallest size (DESIGN.md section 6.5).
- Only the primary cloud receives secrets-* by default.

### secrets-* (exclusive, project) — aws-secrets-manager, gcp-secret-manager, azure-key-vault

`shared`: the lab platform's vault, names prefixed with the project.

| Action | Input | Output |
|---|---|---|
| `store-describe` | project | store exists, secret **names** (prefix-filtered), versions, accessors |
| `store-create` | project, region | store id (in `shared`: verification only) |
| `secret-store` | name, value source (`generate` \| `pipe` from a command \| `user` via `!`) | `secretRef`, version (never the value) |
| `access-grant` | identity, secret names or prefix, role (read) | applied bindings |
| `secret-remove` | name | removed (versions destroyed only with confirmation) |

Notes: `generate` covers database passwords and similar; `pipe` covers keys produced by other providers' CLIs.

---

## 5. Infrastructure

### db-* (combinable, project) — aws-rds, gcp-cloud-sql, azure-sql

`shared`: database + user on the lab's single instance.

| Action | Input | Output |
|---|---|---|
| `database-describe` | project, environment | instance, database, users, size tier, backups |
| `instance-create` | engine, version, tier, region | instance id, `cost.fixed: true` (`dedicated` only; refused in `lab`) |
| `database-create` | project, engine, environment | host/port/database, connection method, `secretRef` of the password (generated) |
| `access-grant` | identity (runtime, CI migrations), database | applied grants / connection permissions |
| `backup-configure` | schedule, retention, point-in-time | applied policy (`prod`) |
| `database-remove` | project, environment | removed (guarded; dump offered first) |

### cache-* (exclusive, project) — aws-elasticache, gcp-memorystore, redis-cloud

`shared`: a key namespace (prefix + ACL user) per project. Managed caches usually have fixed cost: in `lab`, use a serverless or free-tier provider (e.g. Upstash, Redis Cloud free); `instance-create` is `dedicated` only.

| Action | Input | Output |
|---|---|---|
| `cache-describe` | project, environment | instance, namespace, ACL users, tier |
| `instance-create` | tier, region | instance id, `cost.fixed: true` (`dedicated` only) |
| `namespace-create` | project, environment | endpoint, key prefix, `secretRef` of the credentials |
| `namespace-remove` | project, environment | removed |

### storage-* (combinable, project) — aws-s3, gcp-storage, azure-blob

`shared`: a prefix in the lab bucket. `dedicated`: own bucket (names are global: convention + short suffix).

| Action | Input | Output |
|---|---|---|
| `bucket-describe` | project, environment, purpose | bucket/prefix, access, lifecycle, CORS |
| `bucket-create` | project, environment, purpose, region | bucket name (or prefix in `shared`) |
| `bucket-configure` | public access (default off), versioning, lifecycle, CORS | applied settings |
| `access-grant` | identity, role (read/write) | applied bindings |
| `bucket-remove` | project, environment, purpose | removed (empty first, with confirmation) |

### registry-* (exclusive, project) — docker-hub, ghcr, aws-ecr

`shared`: a repository per project in the lab registry.

| Action | Input | Output |
|---|---|---|
| `registry-describe` | project | registry, repositories, retention, access |
| `repository-create` | project, component | image path |
| `access-grant` | identity, role (`push` for CI, `pull` for runtime) | applied bindings |
| `cleanup-configure` | keep last N / max age | applied retention policy |
| `repository-remove` | project, component | removed |

### search-* (exclusive, project) — elastic, algolia, aws-opensearch

`shared`: indexes prefixed with the project. Clusters usually have fixed cost: in `lab`, use a serverless or free-tier provider (e.g. Algolia free); `cluster-create` is `dedicated` only.

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

`shared`: one application per project in a lab-wide tenant/pool.

| Action | Input | Output |
|---|---|---|
| `auth-describe` | project, environment | tenant, application, callback URLs, providers |
| `application-create` | project, environment, type (web/SPA/native/API) | client id, `secretRef` of the client secret |
| `application-configure` | callback/logout/origin URLs (derived from the environment hosts, tenant wildcards included) | applied settings |
| `providers-configure` | social/enterprise providers, `secretRef`s of their credentials | enabled providers |
| `application-remove` | project, environment | removed |

### email-* (exclusive, project) — sendgrid, aws-ses, mailgun

`shared`: lab sending domain with per-project keys; sandbox/test mode (only verified recipients).

| Action | Input | Output |
|---|---|---|
| `email-describe` | domain, project | domain verified?, senders, keys (names), sandbox? |
| `domain-verify` | sending domain | `dnsRecords` (SPF, DKIM, DMARC, verification), status |
| `api-key-create` | project, environment, scope (send only) | `secretRef` |
| `sender-configure` | from address, reply-to | applied |
| `test-send` | recipient | delivered? |
| `api-key-remove` | project, environment | revoked |

### sms-* (exclusive, project) — twilio, vonage, sinch

Treated as special care (numbers and messages cost money). `test` mode by default.

| Action | Input | Output |
|---|---|---|
| `sms-describe` | project | numbers/senders, compliance status, keys (names) |
| `sender-setup` | country, type (number / alphanumeric / messaging service) | sender id, `cost.fixed: true` if a number is bought |
| `compliance-register` | use case, business data | status, usually `pending` (manual review) |
| `api-key-create` | project, environment | `secretRef` (test credentials in `test`) |
| `test-send` | recipient | delivered? |
| `sender-remove` | sender id | released (confirmed) |

### push-* (combinable, component) — fcm, apns, onesignal

`shared`: n/a (registrations are per app).

| Action | Input | Output |
|---|---|---|
| `push-describe` | component | registered platforms, credentials present (names) |
| `app-register` | component, platform (android/ios/web), app id / bundle id | app registration id, config file reference |
| `credentials-upload` | platform, `secretRef` (APNs key, FCM service account) | uploaded |
| `server-key-create` | component, environment | `secretRef` |
| `test-send` | device token / topic | delivered? |

### payments-* (combinable, project) — stripe, paypal, adyen

Special care. `test` mode by default; `shared`: n/a (one account, test mode in lab).

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

`shared`: one key per project in the lab workspace/organization.

| Action | Input | Output |
|---|---|---|
| `llm-describe` | project | workspace/project, keys (names), limits |
| `api-key-create` | project, environment | `secretRef` |
| `limits-configure` | spend limit, rate limits | applied (or `pending` if the plan doesn't allow) |
| `api-key-remove` | project, environment | revoked |

### flags-* (exclusive, project) — launchdarkly, unleash, flagsmith

`shared`: one project per lab project in a lab-wide account.

| Action | Input | Output |
|---|---|---|
| `flags-describe` | project | project, environments, SDK keys (names) |
| `project-create` | project, environments (`lab`/`hom`/`prod`) | project id, environments |
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

`shared`: one site per component in the lab account; deploys come from CI (thin workflow), not from the provider's Git integration, so CI stays the single path.

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

`shared`: one project per component in the lab organization.

| Action | Input | Output |
|---|---|---|
| `monitoring-describe` | project | projects per component, alert rules, keys (names) |
| `project-create` | component, platform | DSN/key (`secretRef`, or `ciVariables` when public by design) |
| `alerts-configure` | rules, target (notify-* channel) | applied rules |
| `releases-setup` | component | `ciSecrets` (release/source-map upload token) |
| `project-remove` | component | removed |

### analytics-* (combinable, component) — google-analytics, mixpanel, amplitude

`shared`: one property/stream per component and environment in the lab account.

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
| `test-send` | channel | delivered? |
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
8. cache-* and search-* in `lab`: serverless or free tier.

Open:

9. dns-* in `lab`: `record-add` vs `route-add` — depends on the lab investigation ([DESIGN.md section 18](DESIGN.md#18-open-items)).
