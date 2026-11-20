---
description: Google Cloud (GCP) deploy setup. Use to make each component of an aleogr project run, in the GCP project of an environment, as a Cloud Run service as declared - created with the placeholder image in one command that keeps it behind the login (IAP) and never public, with its own account, no instance always on and billing by request - and to let the CI account replace its image (roles on that service and that account only, never on the project) and the person running it get in. Repairs an existing service that differs without ever changing its image. Idempotent; plan by default.
---

# gcp_deploy-setup

Makes each component's Cloud Run service `<project>-<component>` exist as declared in one GCP project. A missing service is created with the placeholder image, behind the login from its first moment: one `gcloud run deploy` with `--no-allow-unauthenticated --iap`. An existing service that differs is repaired with only the settings that differ, and its image is never changed: replacing the image is CI's job. The CI account gets `roles/run.developer` on each service and `roles/iam.serviceAccountUser` on each service's account, never a role on the project, and the active `gcloud` account (the person running this) gets `roles/iap.httpsResourceAccessor` on each service, so that it can get in through the login.

Before it makes anything, a security pass closes every existing service that is open (to anyone through its login, or to anyone through its access policy) or without the login. It never passes `--allow-unauthenticated`, `--no-iap`, `--no-invoker-iam-check` or `--ingress`, never passes `--image` to an existing service, never adds `allUsers` or `allAuthenticatedUsers` to anything, never sets a minimum above 0, never deletes a service or an account, and never runs `set-iam-policy`. There is no fixed cost: with a minimum of 0 instances and billing by request, a service costs only while it answers requests.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project of the project and environment (from `gcp_environment-describe`). |
| `project=<name>` | The aleogr project name. |
| `environment=<name>` | The environment: `dev`, `hom` or `prd`. |
| `region=<region>` | The region of the services, for example `us-central1`. |
| `components=<name>[,<name>…]` | The components, in the declaration's order; each runs as the service `<project>-<name>`. |
| `maxInstances=<n>` | The maximum number of instances of each service. |
| `cpu=<n>` | The CPU of each service. |
| `memory=<size>` | The memory of each service, such as `512Mi`. |
| `ciAccount=<e-mail>` | The CI account (`<project>-ci@<projectId>.iam.gserviceaccount.com`, from `gcp_ci-identity-setup`). |
| `placeholderImage=<image>` | The image a new service starts with, until CI deploys the component's own: Google's hello sample. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check every argument, and never ask for anything. Each argument that is missing or breaks its rule gives its one sentence below, one per line; when there is at least one, the skill ends with the result block, `status` `failed`, those sentences and no `gcloud` call.

- A missing required argument: `<argument> is missing.`
- `projectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `projectId is not a GCP project id.`
- `project` has 1 to 14 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `project must have 1 to 14 lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen.`
- `environment` is `dev`, `hom` or `prd`. Otherwise: `environment must be dev, hom or prd.`
- `region` is a Google Cloud region name: lowercase letters, then one or more `-<letters>` parts, then digits (`us-central1`, `southamerica-east1`). Otherwise: `region is not a Google Cloud region name (such as us-central1).`
- `components` holds one or more names separated by `,`, with no space and no empty name. Each name has 1 to 20 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise, for each name that breaks it: `component <name> must have 1 to 20 lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen.` A name given twice: `component <name> is given twice.`
- For each component, `<project>-<name>` has 6 to 30 characters: it is the service's name and its account's id, and an account id has 6 to 30. Otherwise: `<project>-<name> has <n> characters: a service's name, which is also its account's, must have 6 to 30.`
- `maxInstances` is a whole number from 1 to 10, written without a leading `0` (a limit on what a mistake can cost). Otherwise: `maxInstances must be a whole number from 1 to 10.`
- `cpu` is `1` or `2`. Otherwise: `cpu must be 1 or 2.`
- `memory` is `512Mi`, `1Gi` or `2Gi`. Otherwise: `memory must be 512Mi, 1Gi or 2Gi.`
- `ciAccount` is `<id>@<projectId>.iam.gserviceaccount.com`, all lowercase, with no prefix such as `serviceAccount:`, where `<id>` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`, and `<projectId>` is exactly the argument `projectId`. Otherwise: `ciAccount must be a service account of the project <projectId> (<id>@<projectId>.iam.gserviceaccount.com).`
- `placeholderImage` is Google's hello sample: exactly `us-docker.pkg.dev/cloudrun/container/hello`, alone or followed by `:<tag>` (1 to 128 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`) or by `@sha256:<64 characters of 0-9 and a-f>`. Any other image (another registry, another path, the project's own repository) is refused, because "placeholder" means exactly that sample. Otherwise: `placeholderImage must be Google's hello sample, us-docker.pkg.dev/cloudrun/container/hello, with an optional :tag or @sha256 digest.`
- `mode` is `plan` or `apply`. Otherwise: `mode must be plan or apply.`

## Names

For each component `<name>`:

- `<service>` is `<project>-<name>`.
- `<account>` is `<project>-<name>@<projectId>.iam.gserviceaccount.com`.
- `<labels>` is exactly `aleogr-project=<project>,aleogr-environment=<environment>,aleogr-component=<name>`.
- `<agent>` is `serviceAccount:service-<number>@gcp-sa-iap.iam.gserviceaccount.com`, the login's (IAP's) service agent, with `<number>` the project number read in step 1.
- `<me>` is the member of the active `gcloud` account, read in step 2. It is used only as the `--member` of the command of step 6f: it is never written in the answer's text, a label, a file or the result block.

## As declared

A service that exists is as declared when none of these parts differs. Each part that differs adds its word to the service's `differences`, in this order:

| Word | The part is as declared when |
|---|---|
| `account` | `.spec.template.spec.serviceAccountName` is exactly `<account>`, and the account exists (its policy was read in step 3). |
| `scaling` | `.metadata.annotations["run.googleapis.com/maxScale"]` is exactly `maxInstances`; `.metadata.annotations["run.googleapis.com/minScale"]` is absent or `0`; `.metadata.annotations["run.googleapis.com/scalingMode"]` is not `manual`; and `.spec.template.metadata.annotations["autoscaling.knative.dev/minScale"]` is absent or `0`. Any minimum above 0 keeps an instance running, which has a fixed cost. |
| `size` | `.spec.template.spec.containers[0].resources.limits.cpu` is `cpu` (a value in thousandths reads as CPUs: `1000m` is `1`, `2000m` is `2`); `.spec.template.spec.containers[0].resources.limits.memory` is `memory` (`1Gi` is `1024Mi`); and `.spec.template.metadata.annotations["run.googleapis.com/cpu-throttling"]` is absent or `true` (billing by request). |
| `public` | No binding of the service's policy, whatever its role, lists `allUsers` or `allAuthenticatedUsers`, and `.metadata.annotations["run.googleapis.com/invoker-iam-disabled"]` is absent or not `true`. |
| `open` | No binding of the service's login policy (`gcloud iap web get-iam-policy`), whatever its role and whether or not it has a `condition`, lists `allUsers` or `allAuthenticatedUsers`. Either member there lets anyone on the internet who signs in with any Google account through the login: the service is open. |
| `login` | `.metadata.annotations["run.googleapis.com/iap-enabled"]` is exactly `true`. |
| `agent` | A binding of `roles/run.invoker` without a `condition` in the service's policy lists `<agent>`. |
| `ci` | A binding of `roles/run.developer` without a `condition` in the service's policy lists `serviceAccount:<ciAccount>`, and a binding of `roles/iam.serviceAccountUser` without a `condition` in the account's policy lists `serviceAccount:<ciAccount>` (when the account does not exist, `ci` differs too). |
| `labels` | `.metadata.labels` holds `aleogr-project` = `<project>`, `aleogr-environment` = `<environment>` and `aleogr-component` = `<name>`. Other labels do not count and are kept. |

- `placeholder` is true when `.spec.template.spec.containers[0].image` is Google's hello sample, `us-docker.pkg.dev/cloudrun/container/hello`, alone or followed by `:<tag>` or `@sha256:<digest>` (the same rule as `gcp_deploy-describe`). Any other image is one CI deployed, and this skill never replaces it.
- `url` is `.status.url`, or `null` when it is absent.
- `access` (not a part of "as declared") is true when a binding of `roles/iap.httpsResourceAccessor` in the service's login policy (step 3) lists `<me>`.

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. A value written in double quotes below keeps its quotes. The text of a non-zero exit is read to decide and is never quoted: never explain which text decided, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons). Each failure is said with its sentence below and nothing else about it.

1. The project number (both modes):

   ```
   gcloud projects describe <projectId> --format="value(projectNumber)"
   ```

   Exit 0 with a number: that is `<number>`. A non-zero exit or an empty output: say `The GCP project <projectId> could not be read. Check that it exists and that the active gcloud account may read it.` and end with `failed`.

2. The active account (both modes):

   ```
   gcloud config get-value account
   ```

   A non-zero exit, or empty output: say `The active gcloud account could not be read. Run gcloud auth login.` and end with `failed`. Otherwise `<me>` is `serviceAccount:<account>` when the account ends with `.gserviceaccount.com`, and `user:<account>` otherwise.

3. Read each component, in the order of `components`, each command alone (both modes):

   ```
   gcloud run services describe <service> --project=<projectId> --region=<region> --format=json
   gcloud run services get-iam-policy <service> --project=<projectId> --region=<region> --format=json
   gcloud iam service-accounts get-iam-policy <account> --project=<projectId> --format=json
   gcloud iap web get-iam-policy --resource-type=cloud-run --service=<service> --region=<region> --project=<projectId> --format=json
   ```

   - The service's policy and its login policy are read only when the service exists; the account's policy always.
   - The service: exit 0, it exists; read it as "As declared" says. A non-zero exit whose text contains `Cannot find service`, `NOT_FOUND` or `could not be found`: it does not exist. Both are needed: a non-zero exit without that text is not "missing".
   - The account's policy: exit 0, the account exists. A non-zero exit whose text contains `NOT_FOUND` or `does not exist`: the account does not exist.
   - Any other non-zero exit of a read (permission denied, an API not enabled, a network error, anything else): say `The service <service> or its access could not be read; nothing was changed. Check that the Cloud Run and IAP APIs are enabled in <projectId> and that the active gcloud account may read its services and their access.` and end with `failed`. Never treat it as missing.

   A component's work is: the security pass of step 5, when `open`, `public` or `login` differs; the account, when it does not exist; the service, when it does not exist; the repair, when it exists and differs; the CI bindings, when `ci` differs or the service does not exist; the access, when `access` is false or the service does not exist.

4. `plan` ends here, changing nothing. Say for each component whether its account and its service exist, which parts of the service differ, and whether the active account would be given access; end with `would-create` (some account or service is missing), `would-update` (nothing is missing and some component has work), or `unchanged` (no work).

5. `apply`, first the security pass, over every component whose service exists, in the order of `components`, before any account, any service, any binding and any wait. For each such service, in this order, each command alone and only when its part needs it:

   1. `open`: for each binding of the service's login policy that lists `allUsers` or `allAuthenticatedUsers`, for each of those two members it lists, remove it:

      ```
      gcloud iap web remove-iam-policy-binding --resource-type=cloud-run --service=<service> --region=<region> --project=<projectId> --member=<allUsers or allAuthenticatedUsers> --role=<the binding's role> --all --quiet
      ```

   2. `public` because a binding of the service's policy lists `allUsers` or `allAuthenticatedUsers`: for each such binding, for each of those two members it lists, remove it:

      ```
      gcloud run services remove-iam-policy-binding <service> --member=<allUsers or allAuthenticatedUsers> --role=<the binding's role> --region=<region> --project=<projectId> --all --quiet
      ```

      The members come before the login: a service that no public member may call is private even while its login is off.

   3. `login` differs: turn the login on, with this flag alone:

      ```
      gcloud run services update <service> --iap --region=<region> --project=<projectId> --quiet
      ```

      Turning the login on binds the login's agent itself: when this ran, read the service's policy again, alone, with the second command of step 3, and decide `agent` and `ci` from that read.

   4. `invoker-iam-disabled` is `true`: turn the invoker check back on, with this flag alone:

      ```
      gcloud run services update <service> --invoker-iam-check --region=<region> --project=<projectId> --quiet
      ```

   A failure of one of these commands does not skip any other command of the pass, for this service or for the next ones: the pass always runs to its end. When a command of the pass failed, nothing else is made: no account, no service, no other update, no binding, no wait; the run goes to the reads of step 7 and ends `failed`. The answer then says, in plain words, which services are still open (an `allUsers` or `allAuthenticatedUsers` member of the login policy or of the access policy could not be removed, or the invoker check could not be turned back on) and which are still without the login (the login could not be turned on), naming each, for example `The service <service> is still open: anyone on the internet who signs in with any Google account gets through its login. The service <other> is still without the login. Run this same skill again as soon as possible.`, and what the pass did change.

6. `apply`, then for each component, in the order of `components`, its other work in this order (a to f), each command only when its part needs it.

   a. The account, when it does not exist:

      ```
      gcloud iam service-accounts create <service> --project=<projectId> --display-name="<project> <name>" --quiet
      ```

      A non-zero exit whose text contains `already exists`: the account exists (made since the read); go on. Any other non-zero exit: a failure, with the sentence `The account <account> could not be created.`

   b. The CI binding on the account, when it is missing (a new account has none). It comes before the service: accepted, it proves that the account is visible, which the creating deploy needs.

      ```
      gcloud iam service-accounts add-iam-policy-binding <account> --member="serviceAccount:<ciAccount>" --role="roles/iam.serviceAccountUser" --project=<projectId> --condition=None --quiet
      ```

      - When this same run created `<account>` in a, the binding can be refused for a while (seconds to minutes) while the new account is not yet visible: only then, a non-zero exit whose text says the account does not exist (`does not exist` or `NOT_FOUND`) is the refusal that waiting cures, and the binding is polled: wait 30 seconds, then run the same binding command again, alone; while it is refused that same way, wait and try again; at most 10 tries in all, the first one included (so at most 9 waits, about 5 minutes). A refusal of any other kind (a permission denied included) is never waited on, and a binding on an account this run did not create is never polled. Any other non-zero exit of the binding, on any try, ends the poll at once, with no further wait and no further try. The tenth refusal is a failure. The answer says only that the binding was refused, and after how many tries.
      - The wait is the command `sleep 30`, the one command of this skill that is not `gcloud`. Show it, then run it with the Bash tool in the background (`run_in_background`: Claude Code refuses a `sleep` in the foreground), run nothing else while it runs, and when its completion notice arrives go on with the next try in this same run. A pending wait is part of the run: while one is pending, never end the answer, never give the result block, and never tell the owner to run anything. A wait that cannot be run, or whose completion notice never comes, counts as the refusal that ends the poll: the skill ends as after the tenth refusal, never loops and never leaves the answer unfinished.
      - A failure has the sentence `The CI account could not be allowed to act as the account <account>.`

   c. The service, when it does not exist, in this one command, with every flag below and nothing else:

      ```
      gcloud run deploy <service> --image=<placeholderImage> --no-allow-unauthenticated --iap --service-account=<account> --min=0 --max=<maxInstances> --cpu=<cpu> --memory=<memory> --cpu-throttling --labels="<labels>" --region=<region> --project=<projectId> --quiet
      ```

      - Exit 0: the service is created, as declared, with the login's agent bound by `--iap` itself; its CI binding on the service and the access are still to make (e and f).
      - A non-zero exit does not prove that nothing was created: the command creates the service, then sets its access. Read the service once, alone, with the first command of step 3. The deploy is never run again in this run.
        - It does not exist: a failure, with the sentence `The service <service> could not be created.`
        - It exists: the service was created by this run. Read its policy with the second command of step 3 and decide its parts as "As declared" says. Say `The command that creates the service <service> failed, but the service exists; this run went on to set it up as declared.` Then, before anything else for it, run the security pass of step 5 for this one service (each command alone, in that order; its login policy is not read, so its part 1 does not apply). When one of them fails, nothing else is made and the run goes to the reads of step 7 and ends `failed` (a service is left open or without the login, even though this run created it), with the sentence of step 5 naming this service. Otherwise go on with d.
        - The read fails: a failure, with the sentence `The command that creates the service <service> failed and the service could not be read: it may exist. Run this same skill again to check and repair it.`

   d. The rest of a service that exists and differs:

      1. Any of `account`, `scaling`, `size`, `labels` differs: one update with only the flags of what differs:

         ```
         gcloud run services update <service> <flags> --region=<region> --project=<projectId> --quiet
         ```

         - `account` (when `serviceAccountName` is not `<account>`): `--service-account=<account>`.
         - `scaling`: `--min=0 --max=<maxInstances>`; and `--scaling=auto` when `scalingMode` is `manual`; and `--min-instances=default` when the template's `autoscaling.knative.dev/minScale` is above 0.
         - `size`: `--cpu=<cpu>` when the CPU differs, `--memory=<memory>` when the memory differs, `--cpu-throttling` when billing is not by request.
         - `labels`: `--update-labels="<labels>"` (other labels are kept).

         This update never carries a security flag (`--iap`, `--no-iap`, `--invoker-iam-check`, `--no-invoker-iam-check`, `--ingress`, `--allow-unauthenticated`: those are the security pass's, or never used) and never `--image`: the image stays the one the service runs, the placeholder or CI's. Never `--min=` or `--min-instances=` above 0. A failure has the sentence `The settings of the service <service> could not be changed.`

      2. `agent` differs (as of the last read of the policy):

         ```
         gcloud run services add-iam-policy-binding <service> --member="<agent>" --role="roles/run.invoker" --region=<region> --project=<projectId> --condition=None --quiet
         ```

         A failure has the sentence `The login's agent could not be allowed to call the service <service>.`

   e. The CI binding on the service, when it is missing (a new service has none):

      ```
      gcloud run services add-iam-policy-binding <service> --member="serviceAccount:<ciAccount>" --role="roles/run.developer" --region=<region> --project=<projectId> --condition=None --quiet
      ```

      CI gets this role and the one of b, each on one resource, and nothing else: never run `gcloud projects add-iam-policy-binding`, and never give `<ciAccount>` any other role. A failure has the sentence `The CI account could not be given the deploy role on the service <service>.`

   f. The access, when `access` is false or the service was created by this run:

      ```
      gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=<service> --region=<region> --project=<projectId> --member="<me>" --role="roles/iap.httpsResourceAccessor" --condition=None --quiet
      ```

      A refusal does not stop the run: say `The active gcloud account could not be given access to the service <service> through the login.`, and go on with the next component; every other piece of work stands. The result then carries, once however many grants were refused, the `pending` item `{ "item": "access", "reason": "manual", "how": "/aleogr:project-access person=<e-mail>" }`, with `<e-mail>` written exactly so, as a placeholder: never an address. The item stays whatever a later read of the login policy shows: a grant refused in this run is carried.

   A failure of any other command of 6 stops the work at once: no later command of 6, for this component or the next ones, and no retry other than the poll of b. What was made stays (nothing is removed). Then step 7 runs, so that every service that exists is reported as it is.

7. Verify: when a command of 5 or 6 ran, run the commands of step 3 again, alone, for each component on which one of them ran (not the project number and not the active account; the login policy too, so that a removed `open` member is read back). Each such service must exist as declared. A component whose service is still missing or differs, or whose work was not done because of a stop, gets a `pending` item (a stop does not add the item `access`: the next run grants it with the rest) `{ "item": "<name>: <the words that differ, or service, or access>", "reason": "<one sentence, no raw error text>", "how": "Run gcp_deploy-setup again with the same arguments and mode=apply." }`. The `reason` names no e-mail and no account address: it says "the service's account" or "the CI account", never the address (the sentences of steps 5 and 6 are for the answer's text, not for the block). A read that fails here adds the item `<name>: read` with the reason `The service could not be read after the change.` When no command of 5 or 6 ran, the reads of step 3 already are the verification: do not repeat them.

8. Status of `apply`: `failed` when a command of the security pass of step 5 failed (whatever else the pass changed), when a read of steps 1 to 3 failed, and when a stop came at the first command of 6 with nothing changed; otherwise `created` (this run created an account or a service, even when the command that created the service failed and the read found it), `updated` (this run changed something and created nothing), `unchanged` (no command of 5 or 6 ran, or the only one that ran was a refused grant of access, whose item `access` is then in `pending`). `created` and `updated` keep their name when `pending` has items: something was changed. A service created by this run that then fails the security pass ends the run `failed`: something is left open.

Then answer in a few lines: for each component, its service (created, repaired with the words that differed, or as declared), and its address; the sentence of each failure or found service said above; when a service still runs the placeholder, that the first deploy of CI replaces it; and the result block. The answer prints no identifier other than the project id, the service and account names (the CI account's included) and the services' addresses, and never the e-mail of the active account outside the commands shown before running them.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "deploy-setup",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "run-service", "id": "<projectId>/<region>/<project>-web", "name": "<project>-web", "labels": { "aleogr-project": "<project>", "aleogr-environment": "<environment>", "aleogr-component": "web" } }
  ],
  "outputs": {
    "services": [
      { "component": "web", "exists": true, "asDeclared": true, "differences": [], "placeholder": true, "url": "https://<project>-web-<number>.<region>.run.app" }
    ],
    "missing": [],
    "differing": [],
    "waiting": ["web"],
    "urls": { "web": "https://<project>-web-<number>.<region>.run.app" },
    "created": ["web"],
    "updated": []
  },
  "cost": { "fixed": false, "notes": "minimum 0 instances and billing by request: a service costs only while it answers requests" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-create`, `would-update` (plan), `created`, `updated`, `unchanged`, `failed`.
- `outputs.services` has one item per component, in the order of `components`, as of the last read of that component (step 7's when it ran, else step 3's or the read after a failed create), with the fields of `gcp_deploy-describe`: a service that does not exist has `exists` false, `asDeclared` false, `differences` `[]`, `placeholder` false and `url` `null`. `missing`, `differing` and `waiting` are built from it as `gcp_deploy-describe` builds them. `urls` maps each component whose service exists to its address. Lists are written on one line, as above.
- `outputs.created` names the components whose service this run created; `outputs.updated` those on which this run changed anything else (and whose service it did not create). Both are `[]` in `plan`.
- `resources` lists each service that exists as of the last read, with the labels it holds among the three `aleogr-*` ones.
- `failed` from validation or from steps 1 to 3: `resources` is empty and `outputs` is `{ "services": [], "missing": [], "differing": [], "waiting": [], "urls": {}, "created": [], "updated": [] }`, unless step 3 read some services, which are then reported as read.
- `pending` holds the items of step 7 and the item `access` of step 6f; it is empty otherwise. No `how` names an e-mail: the item `access` carries the placeholder `<e-mail>` as written.
- The result block holds no e-mail at all: not `<me>`, not the login's agent, not `<ciAccount>`, not `<account>`, no member of a policy, not even inside a `how`. The answer's text may name the CI account.
