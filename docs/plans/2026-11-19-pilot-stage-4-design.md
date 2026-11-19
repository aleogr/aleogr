# Reference project, stage 4: design of running in `dev`

Status: waiting for the owner's approval. Source of truth after approval: [`DESIGN.md`](../DESIGN.md) and [`CONTRACTS.md`](../CONTRACTS.md); this document is what the implementation plans are written from. It designs **part 4a in full** and parts 4b and 4c in outline; each of those gets its own short design before its plan.

## Intent

After stage 3, `pilot` is a protected repository with two Go components and CI. Nothing of it runs anywhere. Stage 4 makes it run in `dev`: both services on Google Cloud, behind the login, with a database on the shared instance, published by CI when the owner merges.

The purpose is the tooling, not the status page: every piece built here is what the first real project (an identity provider) will use to come out of nothing.

## Goals

- A project that declares the environment `dev` gets, from `project-apply`, its own GCP project, the APIs it needs, a place for its images and an identity through which its repository's CI reaches that GCP project without any key.
- CI is the single path of a deploy ([`DESIGN.md`](../DESIGN.md) section 4): no skill builds an image or deploys a service.
- Both services answer at the address Cloud Run gives them, only to a logged-in person on the allowed list.
- `admin` proves the path from a service to the shared database: it connects with the service's own identity, with no password.
- Nothing with a fixed cost is created, and what can grow has a ceiling.
- A declaration without environments behaves exactly as it does today.

## Non-goals

- The addresses `pilot-dev.aleogr.dev`, tenants, DNS, certificates: stage 5.
- `hom` and `prd`; promotion between environments.
- Tables, migrations, real status-page data.
- Removing anything (the GCP project, the registry, a service): stage 6.
- A deploy from a skill, from Cloud Shell, or from Cloud Build.
- Secrets (Secret Manager): no component needs one yet.
- PowerShell as a proven path.

## Anti-goals

- A long-lived cloud key anywhere (a service account key file, a key in a GitHub secret).
- An identifier of the organization, a folder, the billing account or a GCP project, or an e-mail address, in a versioned file.
- A service reachable without the login.
- A resource that costs money while idle, created without the owner seeing the amount.
- A CI identity that another repository, a fork or another branch can use.

## Constraints

- The repository is public. Identifiers are discovered by name and label, never written down ([`DESIGN.md`](../DESIGN.md) section 7).
- Default service accounts have no roles in this organization, and Cloud Build has no account of its own ([`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md)): every identity is created and granted explicitly.
- The organization forbids service account keys.
- The skills never create folders: `pilot` is a test project, so its GCP project goes in the folder `dev` inside `tst`; if that folder is missing, the run stops and says so, and the owner creates it by hand.
- A GCP project id is permanent and has 30 characters at most: `aleogr-dev-pilot-<4 random>`.
- The owner runs the real runs in Cloud Shell, where `gcloud` and `gh` are both signed in.
- The owner does not write code: every step is a command to type and an output to compare.

## Approaches

1. **Deploy by hand first, automate later.** Skills build the image and deploy from Cloud Shell; CD comes in a later part. A service is up sooner, but there are two deploy paths to build and keep, `DESIGN.md` already decides that CI is the only one, and building an image on GCP meets the accounts-without-roles constraint.
2. **Skills prepare the ground, CI deploys (chosen).** Skills create only what is permanent: the GCP project, the registry, the identities. `cd.yml` builds the image on GitHub Actions (free for a public repository) and deploys. One path, the same one real projects will use. The first service is up later, because everything must fit first.
3. **Everything in one part.** Too many pieces to review and prove at once.

The owner chose 2, in three parts, each with its own plan, pull request and real run:

| Part | Delivers | Real proof |
|---|---|---|
| **4a**, the ground | `environments` and `cloud` in the declaration; the GCP project of `pilot` in `dev`, its APIs, its image repository with a cleanup policy, the CI identity | the plan shows everything created and then `nothing to do`; nothing runs yet |
| **4b**, the deploy | a `Dockerfile` per component, the reusable deploy workflow and the project's `cd.yml`, the Cloud Run services each with its own identity, the login in front | a merge deploys; the owner opens the address and gets in only when logged in |
| **4c**, the database | the database and the user of `pilot` on the shared instance, the check in `admin` | the check answers with the instance running and says so when it is stopped |

## Part 4a: the ground

### The declaration gains `cloud` and `environments`

```json
"cloud": { "provider": "gcp", "region": "us-central1", "root": "tst" },
"environments": { "dev": {} }
```

- Both are optional, and come after `components` and before `notes`. A declaration with `environments` must have `cloud`; `cloud` without `environments` is valid and does nothing.
- `cloud.provider` is `gcp` (the only value); `cloud.region` is a GCP region name (`^[a-z]+-[a-z]+[0-9]+$`); `cloud.root` is optional and its only value is `tst`: a project that tests the tooling, created inside the folder `tst`. A real project has no `root`.
- `environments` is an object whose only allowed key for now is `dev`, and whose value is an empty object. `hom` and `prd`, and the keys `host` and `tenants` of [`DESIGN.md`](../DESIGN.md) section 6.1, come with the stages that build them; the schema refuses them until then, so that nothing is declared that the tooling would ignore.
- `project-declare environment=dev` adds the environment. When it adds the first one it also writes `cloud`, with the provider and the region of `defaults.json`; `cloudRoot=tst` sets the root (accepted with `environment=`, or alone on a declaration that has `cloud`). Changing the region or the root of a declaration whose environment already exists in the cloud is not built: `project-declare` writes it; `project-plan` reports a registry found in another region as something to fix by hand (a registry has one region), and does not detect a changed root (a GCP project does not move by itself): an open item.
- "The declaration's rules" changes identically in `project-declare` and `project-plan`.

### What exists in the cloud, and its names

All in the project's own GCP project, none with a cost while idle:

| Thing | Name | Notes |
|---|---|---|
| GCP project | id `aleogr-dev-<project>-<random>`, labels `aleogr-project`, `aleogr-environment` | existing skill `gcp_environment-create`, with `root=tst` when the declaration says so |
| APIs | the list `project.services` of `defaults.json` (a new key, read by the orchestrator and passed to the skill) | existing skill `gcp_services-enable`; in 4a: Artifact Registry, IAM, IAM Credentials, Security Token Service, Resource Manager. 4b and 4c add theirs |
| Image repository | Artifact Registry, format Docker, id `<project>`, in `cloud.region`, labels as above | one per project and environment; an image is `<region>-docker.pkg.dev/<projectId>/<project>/<component>` |
| Cleanup policy | two rules: keep the 5 most recent versions of each image, and delete every other version; not in dry-run | the ceiling of what storage can cost; the number is `project.registry.keep` in `defaults.json` (a new key). Google applies it about once a day, so one run cannot see it delete |
| CI identity | service account `<project>-ci`; workload identity pool `github` with a provider `github` | the provider's condition accepts only tokens of the declared repository, by its name and by GitHub's numeric ids of the repository and of its owner (a repository deleted and recreated under the same name does not pass), on its default branch; `<project>-ci` may be impersonated only through it |
| Push access | `<project>-ci` has the role of writer on that one repository | granted on the repository, not on the project |

- **Cost.** A GCP project, its APIs, the identities and an empty repository cost nothing. Artifact Registry is free up to 0.5 GB and then about US$ 0.10 per GB a month; two small Go images with five versions each stay far below that, and the cleanup policy keeps it so. No confirmation of cost is asked in 4a, because nothing here has a fixed cost.
- **The CI identity can do nothing but push images in 4a.** The roles that deploy come with 4b, on the resources they deploy to.
- **No identifier goes to GitHub in 4a.** The identifiers CI needs (project id, provider name, account e-mail) are outputs of the skills (`ciVariables`), and reach the repository as Actions variables in 4b, with the workflow that reads them.

### New skills

Each follows [`DESIGN.md`](../DESIGN.md) section 10.4: `mode=plan|apply`, validation first, every command shown, one `aleogr-result` block, `pending` meaning nothing changed, raw error text never quoted.

- **`aleogr-cloud-gcp`** (0.4.0) gains `gcp_ci-identity-setup` (contract `ci-identity-setup`): arguments `project`, `environment`, `repository=<owner>/<name>`, `branch=<default branch>`, `mode`. It creates, each only when missing, the service account `<project>-ci`, the pool, the provider with the condition on repository and branch, and the binding that lets that repository's tokens impersonate the account. An existing provider whose condition differs is reported and, in `apply`, updated (unlike the shared platform's switch, whose provider is never changed: here the condition follows the declaration, and a renamed default branch must be repairable by a run). The numeric ids are arguments too (`repositoryId`, `ownerId`), read by the orchestrator from `github_repo-describe`, which gains them as outputs; they are public on GitHub and are never versioned. A binding made right after the account is created can be refused for some seconds: the skill waits and tries once more, as the switch skill does. Outputs: `account`, `provider`, `ciVariables` (`GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT`).
- **New plugin `aleogr-registry-gcp-artifact-registry`** (0.1.0, family `registry-*`), skills named `gcp-artifact-registry_<action>` like the database plugin's:
  - `gcp-artifact-registry_registry-describe`: whether the repository exists, its region and format, its cleanup policy, who may push (the orchestrator compares that list with the account `gcp_ci-identity-setup` reports, for the state `cannot push`);
  - `gcp-artifact-registry_repository-create`: creates the repository `<project>` when missing; output `imagePath` (the prefix every component's image starts with);
  - `gcp-artifact-registry_cleanup-configure`: `keep=<n>`; owns both rules, from a policy file the plugin ships, sets them when either differs or when the policy is in dry-run, and reads the result back;
  - `gcp-artifact-registry_access-grant`: `identity=<service account e-mail>`, `role=push`, with the same single retry; `pull` is refused as not needed (Cloud Run's own agent pulls from a repository of its own project).

### The orchestrator

- `project-plan`, when the declaration has `environments`, also runs `tools-check` for `gcloud` and prints, after the `protection` row, one row per item below. Like `settings` and `protection`, they are `not checked until the change is merged` while the declaration's action is not `none`, and `follows the creation` while the repository does not exist.

  | Item | States | Action |
  |---|---|---|
  | `environment dev` | `exists` / `missing` / `billing not linked` | `none` / `create` / `repair` |
  | `apis` | `enabled` / `to enable: <n>` | `none` / `enable` |
  | `registry` | `as declared` / `missing` / `cleanup differs` / `in another region` | `none` / `create` / `configure` / `fix by hand` |
  | `ci identity` | `as declared` / `missing` / `differs` / `cannot push` | `none` / `create` / `update` / `grant` |

  When the GCP project is missing, the three rows after it are `follows the environment` / `none`: nothing can be read inside a project that does not exist. When an API is still to enable, `registry` and `ci identity` are `follows the apis` / `none`: their commands are refused until the APIs are on. The branch the CI identity accepts is the repository's default branch, read by `github_repo-describe`.
- `project-apply` makes them in that order, after the repository's steps ([`DESIGN.md`](../DESIGN.md) section 12.2, steps 3, 5 and the identity of step 10): `gcp_environment-create` → `gcp_services-enable` → `repository-create` → `cleanup-configure` → `gcp_ci-identity-setup` → `access-grant`. The APIs are enabled in one call, before any command that needs them, and a just-enabled API that is still refused is waited for once. They need only `confirm=yes`: they expose nothing and have no fixed cost. A failure stops the run; what was created stays, and the next plan shows what is left.
- The declaration reaches the repository by the existing cycle: `project-declare environment=dev` → `project-apply` proposes → the owner merges → `project-apply` updates the folder and creates the ground.
- A stopped shared database is irrelevant to 4a: nothing here touches it.

### What 4a does not prove

That the CI identity really works from GitHub Actions: nothing uses it until 4b. The skill verifies the condition and the binding by reading them back; the first deploy is the proof.

### Tests

Scenario tests with the fake `gcloud`, as for the existing GCP skills: each new skill in `plan` and `apply`, missing / existing / differing; `project-declare` with `environment` and `cloudRoot`; `project-plan` and `project-apply` with and without environments, including the rule that a declaration without them issues not one `gcloud` command. Fixtures use fictitious ids (`aleogr-dev-demo-ab12`, `example-org/example-repo`).

## Part 4b in outline: the deploy

- `go_setup` gains a `Dockerfile` per component (multi-stage, a static binary on a minimal base image), written once and only when missing, for components that already exist too.
- A reusable workflow `cd-go-cloud-run.yml` in `aleogr/aleogr`: authenticates through the CI identity, builds, pushes, deploys one component. The project's `cd.yml`, generated like `ci.yml`, runs it on a push to the default branch, only for the components that changed, after their CI.
- `gcp_deploy-setup` prepares each service once: its own service account `<project>-<component>`, the Cloud Run service with scale to zero, the smallest size and at most two instances, the login (IAP) on, and the roles that let `<project>-ci` deploy to it. CI only replaces the image.
- `gcp_access-grant person=<e-mail>` adds a person to the allowed list. **The list lives only in the cloud** (an IAM binding): the e-mail is typed by the owner in the terminal and is never in the declaration.
- A service account id has 30 characters at most: `<project>-<component>` is checked against it, and the declaration's limits are tightened if needed.
- The Actions variables that `cd.yml` reads are set by a new GitHub skill from `ciVariables`.
- **Risk to settle first in 4b:** the login directly on a Cloud Run service, without a load balancer, is known from documentation only. 4b starts by proving it by hand on a throwaway service; if it does not work as described, the design of 4b changes before anything is built.

## Part 4c in outline: the database

- The database `pilot_dev` and a user that is the service account of `admin` (IAM authentication, no password) on the instance `aleogr-shared`, created by new skills of `aleogr-db-gcp-cloud-sql` in the `shared` mode; they check that the instance is running and say so instead of failing.
- `admin` gains one endpoint that connects through the Cloud SQL connector and answers whether the database is reachable, with a short timeout and a plain answer when the instance is stopped.
- No table, no migration.

## Decisions made by the designer, for the owner to check

- `cloud.root: "tst"` in the declaration is how a test project is told apart, rather than a rule on the project's name.
- `environments` accepts only `dev`, with an empty value, until later stages give the rest a meaning.
- The image repository is in the project's own GCP project, one per project and environment, not a shared one: it costs nothing while small, and it keeps a project's removal simple.
- Five versions of each image are kept.
- The CI identity accepts only the default branch of the declared repository, checked by name and by GitHub's numeric ids; pull requests cannot deploy.
- A provider whose condition differs is updated by `project-apply`, not only reported.
- The cleanup policy is two rules (keep five, delete the rest), owned by one skill.
- The identifiers CI needs go to Actions variables (not secrets), in 4b.

## Left to the builder

- The exact `gcloud` commands of each skill, checked against the current documentation and recorded in `PROVIDER-FACTS.md` when they surprise.
- The scenario list of each skill and the fixtures.
- The wording of each row's explanation under the plan's table.
