# Reference project, stage 4b: design of the deploy and of a fluid run

Status: waiting for the owner's approval. Source of truth after approval: [`DESIGN.md`](../DESIGN.md) and [`CONTRACTS.md`](../CONTRACTS.md); this document is what the implementation plans are written from. It follows [`2026-11-19-pilot-stage-4-design.md`](2026-11-19-pilot-stage-4-design.md), whose outline of part 4b it replaces.

## Intent

After stage 4a, `pilot` has its ground in `dev` and nothing runs. Stage 4b makes both services run on Cloud Run behind the login, deployed by CI at every merge.

The first real run of 4a also showed that the tooling is safe but not fluid: six commands and a merge, with waits by hand, to create a ground. The owner's premise, from now on a rule of the whole tooling: **using it is simple, fluid, automated and easy.** Stage 4b applies it to what exists before adding more steps.

## Goals

- After the owner merges a change to a component, its service runs the new code with no command.
- After the owner merges a declaration, **one** `project-apply` does everything that is left and ends with what the owner needs: the addresses.
- A run waits by itself where waiting is known to be needed, and stops only where an action cannot be undone, exposes something, or costs money.
- A service is reachable only by a logged-in person on its allowed list; a visit by anyone else does not wake it.
- The login works for the owner's personal Google account, with a preparation made once for the whole organization.
- Nothing with a fixed cost. Each service scales to zero and has a ceiling of instances.
- A declaration without environments, and a platform that has no login prepared, behave as today.

## Non-goals

- The addresses under `aleogr.dev`, tenants, DNS: stage 5.
- A component declared public, and opening `status`: stage 5.
- The database and the check in `admin`: part 4c.
- `hom` and `prd`, promotion between environments, rollbacks, previews per pull request.
- Removing a service or an environment: stage 6.
- Secrets in services (Secret Manager): no component needs one yet.
- Verification of the login's consent screen by Google (branding shown to users).

## Anti-goals

- A service reachable without the login, even for a moment (a service is never created public and then closed).
- A deploy path other than CI; a workflow that deploys from a pull request or from another repository's code.
- A long-lived cloud key; the login's client secret in the repository, in the conversation or in a skill's output.
- A step the owner repeats by hand for each project or each service.
- A run that stops and asks the owner to run another command when it could have waited or gone on.

## Constraints

- The organization is a standalone one, owned by a personal Google account: for the login, every account is "outside the organization". The login managed by Google refuses them; a custom OAuth client is needed, and Google offers no command that creates one (proven on 2026-11-19, see "What the spikes proved").
- The repository is public: identifiers and e-mail addresses are never versioned; the allowed list lives only in the cloud.
- Default service accounts have no roles: each service runs as its own account.
- A service account id has 6 to 30 characters.
- CI is the single deploy path, and the CI identity accepts only the default branch of the declared repository. A workflow triggered by `pull_request_target` or `workflow_run` would run on that branch's ref with other code: neither is ever used.
- Claude Code does not run a foreground wait; a wait runs in the background and the run goes on when it ends (seen in the first real run of 4a).

## What the spikes proved (2026-11-19, on throwaway services in the project of `pilot`)

- `gcloud run deploy … --no-allow-unauthenticated --iap` puts the login in front of a Cloud Run service with no load balancer. Not logged in: Google's sign-in. Logged in but not allowed: "You don't have access", before the service is reached.
- The login needs, per service: the IAP service agent as invoker of the service, and each person as `roles/iap.httpsResourceAccessor` on it.
- With Google's managed OAuth client, the owner's personal account is refused although it is on the allowed list. With a custom OAuth client it gets in.
- A custom client set **once on the organization** (`gcloud iap settings set <file> --organization=<id>`) is inherited by a service created afterwards in a project of that organization, with nothing configured on the service. Setting it needs the role `roles/iap.settingsAdmin` on the organization, which the organization's administrator does not have by default.
- The consent screen of audience "External" let the owner in without a warning, although the application is "in testing" and its list of test users is empty. Google's help says why: an application that asks only for the basic sign-in scopes (`openid`, `email`, `profile`), as this login does, needs no test-user list, shows no warning, and its authorizations do not expire; the cap of users and the verification apply to sensitive scopes. So the application **stays in testing and is never published**: the console does not offer to publish it until more branding is filled in, and nothing here needs it. To be confirmed in the real run of 4b-1 with a second Google account.
- `gcloud run deploy … --iap` created the IAP service agent of the project by itself ("Setting IAP service agent"), and the binding that makes it invoker of the service was accepted right after.

## Approaches

Where the login's configuration lives:

1. **Once for the organization (chosen).** A consent screen and one OAuth client in the shared project, applied to the organization. Every service of every project inherits it. One preparation by hand, ever.
2. **Once per project.** The same clicks for each new project: against "the project comes out of nothing without opening a dashboard".
3. **Per service, in the console.** What the first spike did: clicks for each service.

Where a deploy job lives:

1. **Inside the project's one `ci.yml` (chosen).** A deploy job per component, after that component's check, only on a push to the default branch. One workflow, one trigger list, and `needs:` gives "after its CI" without `workflow_run`.
2. **A separate `cd.yml` triggered by `workflow_run`.** Runs with the default branch's ref whatever started it: the trigger the CI identity must never meet.
3. **A separate `cd.yml` on `push`.** Would deploy without waiting for the check, or repeat the check.

The work is done in **two parts, each with its own plan, pull request and real run**:

| Part | Delivers | Real proof |
|---|---|---|
| **4b-1**, a fluid run and the login | the premise as a rule; `project-apply` that waits and goes on by itself; the login of the organization as a row of the platform's plan | `platform-plan` shows the login prepared; the two spike services are removed |
| **4b-2**, the deploy | a `Dockerfile` per component, the deploy jobs, the services, access | a merge deploys; the owner opens each address and gets in |

## Part 4b-1: a fluid run, and the login of the organization

### The premise

`DESIGN.md` section 10.4 gains the rule and what follows from it, for every skill:

- A run goes as far as it safely can. It stops only before an action that cannot be undone, that exposes something, or that has a cost, and then with one confirmation that covers the whole run.
- Where a wait is known to be needed (an API just enabled, an account just created), the skill waits and tries again by itself, once, and only then stops.
- A stop says what was done, what is left and the one command that goes on. It never asks the owner to check something a command can check.
- An answer is short: what was done, what is left, the addresses when there are any. One result block.

### `project-apply`

- **One run after a merge.** The stop added in 4a after the folder update is removed. Its purpose moves earlier: when the proposal a run opens carries a declaration that adds an environment, the answer of that run (and the pull request's body) says that applying it after the merge creates a Google Cloud project, whose id is permanent. The owner merges knowing it; the next `project-apply confirm=yes` updates the folder and makes everything.
- **Waits instead of stopping.** After `gcp_services-enable` enabled something, the first skill that needs those APIs is tried, and while it is refused the run waits and tries again: every 30 seconds, for 5 minutes at most (background waits; how long an API takes was never measured, only that "some minutes later it works"). The same bounded wait covers a binding refused right after its account was created. Only when the limit passes does the run stop, with today's item.
- **After a project it created, the run still never says "apply again" on a guess** (4a's rule stands): the wait above makes that stop rare, not different.
- **The plan is not repeated without need.** A run prints the first plan and the last one; a plan in the middle is made only when the rows could not be known (an existing project repaired).
- **The form of the answer.** The nested skills' result blocks are not part of the answer. The known defect (a nested block printed before the table, or the run ending at it: about one plan in five that read the cloud) is treated as a defect of fluidity: 4b-1 measures it on the scenarios and changes the skills until it is under one run in twenty, or says why it cannot.

### The login of the organization

- **What it is:** in the shared project, a consent screen of audience External named `aleogr`, and one OAuth client of type web application named `iap`, with the redirect address `https://iap.googleapis.com/v1/oauth/clientIds/<client id>:handleRedirect`; on the organization, the IAP setting that names that client. Google stores the client's secret; nothing else does.
- **It is prepared once, and the tooling does all of it that Google lets a command do.** Google has no command that creates a consent screen or an OAuth client (the `gcloud iap oauth-*` commands were discontinued), so those are clicks; everything else is the tooling's:
  - a new skill `gcp_login-setup` grants the account that runs it `roles/iap.settingsAdmin` on the organization, enables the IAP API in the shared project, and prints the short list of what is left: the two console pages as links that open in the shared project, the exact value of each field (audience External, the names `aleogr` and `iap`, the redirect address to build from the client's id), and the one command to paste in a terminal. Nothing is published and no logo is uploaded (a logo would start Google's verification). It never sees the secret;
  - that command asks for the client's id and, without showing it, its secret, writes a temporary file, applies it to the organization and deletes the file. The secret passes through no skill and no conversation, which is why this one step is the owner's;
  - `platform-apply` invokes `gcp_login-setup` when the row says `not prepared`, and ends with the list as its `pending` item; run again after the clicks, it reads the organization's setting and says `prepared`. `docs/cloud-shell.md` holds the same steps for reference.
- **`platform-plan` gains the row `login`**: `prepared` / `none` when the organization's IAP setting names a client; `not prepared` / `prepare` otherwise. It is read with `gcloud iap settings get --organization=<id>`, which shows the client's id and a hash of the secret, never the secret.
- A new skill of `aleogr-cloud-gcp`, `gcp_login-describe`, makes that read (output `prepared`, never the client id in the result block's text beyond what the orchestrator needs: none).
- `project-plan` reads the same thing when the declaration has environments (the organization's id comes from the discovery the GCP skills already make): while the login is `not prepared`, the row `services` of 4b-2 is `waits for the login` / `prepare by hand`, and `project-apply` creates no service. A service with the login on and no client would be unreachable for a personal account.
- On this organization the preparation was made during the spike: the real proof of 4b-1 is the row reading `prepared`, and a second Google account getting in after one command.

### Clean-up

The spike left two services (`spike-iap`, `spike-iap2`), one service account (`spike-iap`) and, in the project of `pilot`, a consent screen named `aleogr dev` with a client that one of them used. The run checklist of 4b-1 removes the services and the account by commands, and says how to remove that client in the console; the consent screen of a project cannot be removed and is harmless.

## Part 4b-2: the deploy

### What a deployed component is

Every component of a declaration that has environments is a service, deployed to each declared environment. No new key in the declaration: a component that is not a service has no meaning yet, and `public` comes with stage 5.

### What exists, and its names

| Thing | Name | Notes |
|---|---|---|
| APIs | `run.googleapis.com`, `iap.googleapis.com` added to `project.services` | |
| Service account of a service | `<project>-<component>` | no role in 4b-2. The id has 6 to 30 characters and does not end with `-`: with environments, the declaration's rules refuse a component whose name ends with `-` or makes `<project>-<component>` longer than 30 characters (`project-declare` fails; "The declaration's rules" in both skills) |
| Cloud Run service | `<project>-<component>`, in `cloud.region`, labels as the project's | created with a placeholder image; minimum 0 and maximum 2 instances, the smallest CPU and memory, no unauthenticated access, the login on |
| Login of a service | IAP service agent as invoker; the allowed list on the service | inherits the organization's client |
| What CI may do | on each service, deploy a new revision; act as that service's account | granted on the service and on the account, never on the project |
| Image | `<image path>/<component>`, pushed with the commit as its tag, **deployed by digest** | the repository of 4a. The CI account can re-point a tag, so a service never runs "a tag" |
| `Dockerfile` | `<path>/Dockerfile` | written once, never overwritten |
| Actions variables | `GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `GCP_CI_ACCOUNT`, `GCP_REGION`, `GCP_IMAGE_PATH` | variables of the repository, not secrets; no workflow prints them |

### Skills

- `aleogr-cloud-gcp`: `gcp_deploy-setup` (contract `deploy-setup`: the account, the service with the placeholder image, the login, the agent's binding, what CI may do; it changes an existing service only where it differs from the declaration, and never its image), `gcp_deploy-describe`, and `gcp_access-grant person=<e-mail>` (contract `access-grant`: adds the person to the allowed list of every service of the project and environment; `list=yes` shows it). `gcp_deploy-setup` puts the account that runs it on the allowed list, so the owner gets in without one more command.
- `aleogr-stack-go`: `go_setup` also writes `<path>/Dockerfile` when it is missing, for a component that already exists too: two stages, a static binary built with the component's Go version, on a minimal base image, running as a non-root user, listening on `PORT`.
- `aleogr-repo-github`: `github_variables-set` (sets the repository's Actions variables from the values the orchestrator passes; reads them first and changes only what differs); `github_ci-setup` writes the deploy jobs.
- `.github/workflows/deploy-cloud-run.yml` in `aleogr/aleogr`: reusable, `workflow_call` only; inputs for the folder, the service, the region, the image and the three identity values; `permissions: contents: read, id-token: write`; it authenticates through workload identity federation, builds the image from the component's `Dockerfile`, pushes it, and updates the existing service to that image's digest (it never creates a service: a missing one is a failure). It receives no secret. The repository is public and so are its logs: the workflow masks the project's id and number and the account's e-mail before any step can print them. One deploy at a time per service (a `concurrency` group).

### The project's `ci.yml`

The marker becomes version 2 and carries the environments. For each component there is, after its check job, a job `deploy-<component>-dev` with `needs: [<component>]` that runs only when the event is a push to the default branch and the component's check passed, and calls the reusable deploy workflow pinned by commit. The job `ci`, the required check, is as today: deploy jobs are not part of it, so a pull request never waits for a deploy. Triggers stay `pull_request` and `push` to the default branch. Each deploy job declares its own `permissions: contents: read, id-token: write` (a called workflow cannot raise its caller's). A component whose check was skipped (the push did not touch it) is not deployed. The change of the marker to version 2 pins the reusable workflows to the head of `aleogr/aleogr` again (`ref=latest`): the commit pinned by a version 1 file is older than the deploy workflow.

### The orchestrator

- `project-plan` gains, after `ci identity`: `services` (`as declared` / `missing: <names>` / `differs: <names>` / `waiting for the first deploy: <names>` while a service still runs the placeholder, with action `none` and the line that says to merge the pull request or run the workflow again), `ci variables` (`as declared` / `missing` / `differs`). "As declared" for a service is: it exists in the region with its account, its scaling and size, no unauthenticated access, the login on, and the agent's binding; the allowed list is not compared (it is not declared); `components` also reports a missing `Dockerfile` as `to generate`; `ci` differs when the marker is of version 1.
- `project-apply`, in one confirmed run, in this order: the cloud first (APIs, then `gcp_deploy-setup` for each component, then `github_variables-set`), then the files (`Dockerfile`s, `ci.yml`) proposed in one pull request. So when the owner merges, everything the deploy job needs already exists. The answer ends with the pull request and each service's address.
- After the merge: CI checks, builds, pushes and deploys. The next `project-apply` only updates the folder and says `nothing to do`.

### The owner's run, on `pilot`

`project-apply confirm=yes` → merge the pull request → open the two addresses. To let someone else in: `gcp_access-grant person=<e-mail>` (through a shortcut of the orchestrator, `project-access`, so the owner types the project's name and the e-mail, nothing else).

### What 4b-2 proves that 4a could not

The CI identity from GitHub Actions: the first deploy pushes an image and deploys with it.

## Decisions made by the designer, for the owner to check

- The stop before creating a GCP project is replaced by a warning at the proposal, before the merge.
- The login's client secret is typed once by the owner in a terminal command and is stored only by Google.
- The preparation of the login is driven by `platform-apply`: the tooling grants the role, enables the API, hands over links, values and the one command, and verifies; only the console's clicks and the secret are the owner's.
- Every component is a service; no `kind` in the declaration yet.
- Deploy jobs live in `ci.yml`, after each component's check, and are not part of the required check.
- A service is created by a skill with a placeholder image and the login already on; CI only replaces the image.
- Whoever runs `project-apply` is put on the allowed list of the services it creates.
- Two instances at most per service, and the smallest size.
- A service is deployed by digest; the logs of the deploy mask the project's identifiers.
- The CI identity's condition also requires that the job runs the reusable deploy workflow of `aleogr/aleogr` (the token's `job_workflow_ref`), so that no other workflow on the default branch can act as the CI account; `gcp_ci-identity-setup` gains it and updates the provider of 4a. To be proven by the first deploy.
- The login's application stays "in testing": with the basic scopes only, any allowed Google account gets in, so a person is let in by a command.
- Waits are bounded polls (30 seconds, 5 minutes at most), not fixed sleeps.

## Left to the builder

- The exact commands, flags and roles, checked against the current reference and, where they surprise, recorded in `PROVIDER-FACTS.md`; in particular the smallest role that lets CI deploy a revision to one service.
- The placeholder image and the `Dockerfile`'s base images, and how their versions are pinned.
- How the wait in the background is worded so that a run always goes on after it, and the permission rule that lets it run without a prompt in Cloud Shell.
- The smallest CPU and memory Cloud Run accepts for the Go binary, and the smallest role that lets CI update one service's image (expected: a role on the service plus acting as its account), both recorded in `PROVIDER-FACTS.md`.
- The scenario lists and fixtures.
