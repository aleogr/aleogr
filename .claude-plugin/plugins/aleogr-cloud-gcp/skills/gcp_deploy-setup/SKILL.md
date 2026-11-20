---
description: Google Cloud (GCP) deploy setup. Use to make each component of an aleogr project run, in the GCP project of an environment, as a Cloud Run service as declared - created with the placeholder image in one command that keeps it behind the login (IAP) and never public, with its own account, no instance always on and billing by request - and to let the CI account replace its image (roles on that service and that account only, never on the project) and the person running it get in. Repairs an existing service that differs without ever changing its image. Idempotent; plan by default.
---

# gcp_deploy-setup

Makes each component's Cloud Run service `<project>-<component>` exist as declared in one GCP project. A missing service is created with the placeholder image, behind the login from its first moment: one `gcloud run deploy` with `--no-allow-unauthenticated --iap`. An existing service that differs is repaired with only the settings that differ, and its image is never changed: replacing the image is CI's job. The CI account gets `roles/run.developer` on each service and `roles/iam.serviceAccountUser` on each service's account, never a role on the project, and the active `gcloud` account (the person running this) gets `roles/iap.httpsResourceAccessor` on each service, so that it can get in through the login.

It never passes `--allow-unauthenticated`, `--no-iap` or `--image` to an existing service, never adds `allUsers` or `allAuthenticatedUsers` to anything, never sets a minimum above 0, never deletes a service or an account, and never runs `set-iam-policy`. There is no fixed cost: with a minimum of 0 instances and billing by request, a service costs only while it answers requests.

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
| `memory=<size>` | The memory of each service, such as `256Mi`. |
| `ciAccount=<e-mail>` | The CI account (`<project>-ci@<projectId>.iam.gserviceaccount.com`, from `gcp_ci-identity-setup`). |
| `placeholderImage=<image>` | The image a new service starts with, until CI deploys the component's own. |
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
- `maxInstances` is a whole number from 1 to 100, written without a leading `0`. Otherwise: `maxInstances must be a whole number from 1 to 100.`
- `cpu` is `1`, `2`, `4` or `8`. Otherwise: `cpu must be 1, 2, 4 or 8.`
- `memory` is a whole number without a leading `0` followed by `Mi` or `Gi` (`256Mi`, `1Gi`). Otherwise: `memory must be a size in Mi or Gi, such as 256Mi.`
- `ciAccount` is `<id>@<projectId>.iam.gserviceaccount.com`, all lowercase, with no prefix such as `serviceAccount:`, where `<id>` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`, and `<projectId>` is exactly the argument `projectId`. Otherwise: `ciAccount must be a service account of the project <projectId> (<id>@<projectId>.iam.gserviceaccount.com).`
- `placeholderImage` is an image address: a host of `a-z`, `0-9`, `.` and `-`, then one or more `/`-separated parts of `a-z`, `0-9`, `.`, `_` and `-`, then optionally `:<tag>` (`A-Z`, `a-z`, `0-9`, `.`, `_`, `-`) or `@sha256:<64 characters of 0-9 and a-f>`; no space, no quote, no comma. Otherwise: `placeholderImage must be an image address, such as us-docker.pkg.dev/cloudrun/container/hello:latest.`
- `mode` is `plan` or `apply`. Otherwise: `mode must be plan or apply.`

## Names

For each component `<name>`:

- `<service>` is `<project>-<name>`.
- `<account>` is `<project>-<name>@<projectId>.iam.gserviceaccount.com`.
- `<labels>` is exactly `aleogr-project=<project>,aleogr-environment=<environment>,aleogr-component=<name>`.
- `<agent>` is `serviceAccount:service-<number>@gcp-sa-iap.iam.gserviceaccount.com`, the login's (IAP's) service agent, with `<number>` the project number read in step 1.
- `<me>` is the member of the active `gcloud` account, read in step 2. It is used only as the `--member` of the command of step 5e: it is never written in the answer's text, a label, a file or the result block.

## As declared

A service that exists is as declared when none of these parts differs. Each part that differs adds its word to the service's `differences`, in this order:

| Word | The part is as declared when |
|---|---|
| `account` | `.spec.template.spec.serviceAccountName` is exactly `<account>`, and the account exists (its policy was read in step 3). |
| `scaling` | `.metadata.annotations["run.googleapis.com/maxScale"]` is exactly `maxInstances`; `.metadata.annotations["run.googleapis.com/minScale"]` is absent or `0`; `.metadata.annotations["run.googleapis.com/scalingMode"]` is not `manual`; and `.spec.template.metadata.annotations["autoscaling.knative.dev/minScale"]` is absent or `0`. Any minimum above 0 keeps an instance running, which has a fixed cost. |
| `size` | `.spec.template.spec.containers[0].resources.limits.cpu` is `cpu` (a value in thousandths reads as CPUs: `1000m` is `1`, `2000m` is `2`); `.spec.template.spec.containers[0].resources.limits.memory` is `memory` (`1Gi` is `1024Mi`); and `.spec.template.metadata.annotations["run.googleapis.com/cpu-throttling"]` is absent or `true` (billing by request). |
| `public` | No binding of the service's policy, whatever its role, lists `allUsers` or `allAuthenticatedUsers`, and `.metadata.annotations["run.googleapis.com/invoker-iam-disabled"]` is absent or not `true`. |
| `login` | `.metadata.annotations["run.googleapis.com/iap-enabled"]` is exactly `true`. |
| `agent` | A binding of `roles/run.invoker` in the service's policy lists `<agent>`. |
| `ci` | A binding of `roles/run.developer` without a `condition` in the service's policy lists `serviceAccount:<ciAccount>`, and a binding of `roles/iam.serviceAccountUser` without a `condition` in the account's policy lists `serviceAccount:<ciAccount>` (when the account does not exist, `ci` differs too). |
| `labels` | `.metadata.labels` holds `aleogr-project` = `<project>`, `aleogr-environment` = `<environment>` and `aleogr-component` = `<name>`. Other labels do not count and are kept. |

- `placeholder` is true when `.spec.template.spec.containers[0].image` is exactly `placeholderImage`, or is Google's hello sample `us-docker.pkg.dev/cloudrun/container/hello`, alone or followed by `:<tag>` or `@sha256:<digest>`. Any other image is one CI deployed, and this skill never replaces it.
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

   A component's work is: the account, when it does not exist; the service, when it does not exist; the repair, when it exists and differs; the CI bindings, when `ci` differs or the service does not exist; the access, when `access` is false or the service does not exist.

4. `plan` ends here, changing nothing. Say for each component whether its account and its service exist, which parts of the service differ, and whether the active account would be given access; end with `would-create` (some account or service is missing), `would-update` (nothing is missing and some component has work), or `unchanged` (no work).

5. `apply`: for each component, in the order of `components`, do its work in this order (a to e), each command only when its part needs it.

   a. The account, when it does not exist:

      ```
      gcloud iam service-accounts create <service> --project=<projectId> --display-name="<project> <name>" --quiet
      ```

      A non-zero exit whose text contains `already exists`: the account exists (made since the read); go on. Any other non-zero exit: a failure, with the sentence `The account <account> could not be created.`

   b. The service, when it does not exist, in this one command, with every flag below and nothing else:

      ```
      gcloud run deploy <service> --image=<placeholderImage> --no-allow-unauthenticated --iap --service-account=<account> --min=0 --max=<maxInstances> --cpu=<cpu> --memory=<memory> --cpu-throttling --labels="<labels>" --region=<region> --project=<projectId> --quiet
      ```

      - Exit 0: the service is created, as declared, with the login's agent bound by `--iap` itself; its CI bindings and the access are still to make (d and e).
      - A non-zero exit does not prove that nothing was created: the command creates the service, then sets its access. Read the service once, alone, with the first command of step 3:
        - It does not exist: a failure, with the sentence `The service <service> could not be created.`
        - It exists: the service was created by this run. Read its policy with the second command of step 3, decide its parts as "As declared" says, and go on with c for it (then d and e). Say `The command that creates the service <service> failed, but the service exists; this run went on to set it up as declared.`
        - The read fails: a failure, with the sentence `The command that creates the service <service> failed and the service could not be read: it may exist. Run this same skill again to check and repair it.`

   c. The repair of a service that exists and differs, in this order:

      1. `login` differs: turn the login on before anything else, alone:

         ```
         gcloud run services update <service> --iap --region=<region> --project=<projectId> --quiet
         ```

         Say `The service <service> was found without the login; the login was turned on before anything else.` Then read the service's policy again with the second command of step 3 (turning the login on binds the login's agent itself), and decide `public`, `agent` and `ci` from that read. A failure here has the sentence `The service <service> exists without the login, and the login could not be turned on. Run this same skill again as soon as possible.`

      2. `public` differs: for each binding of the service's policy that lists `allUsers` or `allAuthenticatedUsers`, for each of those two members it lists:

         ```
         gcloud run services remove-iam-policy-binding <service> --member=<allUsers or allAuthenticatedUsers> --role=<the binding's role> --region=<region> --project=<projectId> --all --quiet
         ```

         A failure has the sentence `Public access could not be removed from the service <service>.`

      3. Any of `account`, `scaling`, `size`, `labels` differs, or `invoker-iam-disabled` is `true`: one update with only the flags of what differs:

         ```
         gcloud run services update <service> <flags> --region=<region> --project=<projectId> --quiet
         ```

         - `account` (when `serviceAccountName` is not `<account>`): `--service-account=<account>`.
         - `scaling`: `--min=0 --max=<maxInstances>`; and `--scaling=auto` when `scalingMode` is `manual`; and `--min-instances=default` when the template's `autoscaling.knative.dev/minScale` is above 0.
         - `size`: `--cpu=<cpu>` when the CPU differs, `--memory=<memory>` when the memory differs, `--cpu-throttling` when billing is not by request.
         - `labels`: `--update-labels="<labels>"` (other labels are kept).
         - `invoker-iam-disabled` `true`: `--invoker-iam-check`.

         Never `--image`: the image stays the one the service runs, the placeholder or CI's. Never `--iap` (done in 1), `--no-iap`, `--allow-unauthenticated`, `--min=` above 0 or `--min-instances=` above 0. A failure has the sentence `The settings of the service <service> could not be changed.`

      4. `agent` differs (as of the last read of the policy):

         ```
         gcloud run services add-iam-policy-binding <service> --member="<agent>" --role="roles/run.invoker" --region=<region> --project=<projectId> --condition=None --quiet
         ```

         A failure has the sentence `The login's agent could not be allowed to call the service <service>.`

   d. The CI bindings, each only when it is missing (a new service has neither on the service; a new account has none):

      ```
      gcloud run services add-iam-policy-binding <service> --member="serviceAccount:<ciAccount>" --role="roles/run.developer" --region=<region> --project=<projectId> --condition=None --quiet
      gcloud iam service-accounts add-iam-policy-binding <account> --member="serviceAccount:<ciAccount>" --role="roles/iam.serviceAccountUser" --project=<projectId> --condition=None --quiet
      ```

      - CI gets these two roles, each on one resource, and nothing else: never run `gcloud projects add-iam-policy-binding`, and never give `<ciAccount>` any other role.
      - The binding on `<account>` made after this same run created that account can be refused for a while (seconds to minutes) while the new account is not yet visible: only then, a non-zero exit of that binding whose text says the account does not exist (`does not exist` or `NOT_FOUND`), or is `PERMISSION_DENIED`, is the refusal that waiting cures, and the binding is polled: wait 30 seconds, then run the same binding command again, alone; while it is refused that same way, wait and try again; at most 10 tries in all, the first one included (so at most 9 waits, about 5 minutes). A binding on an account this run did not create is never polled. Any other non-zero exit of the binding, on any try, ends the poll at once, with no further wait and no further try. The tenth refusal is a failure. The answer says only that the binding was refused, and after how many tries.
      - The wait is the command `sleep 30`, the one command of this skill that is not `gcloud`. Show it, then run it with the Bash tool in the background (`run_in_background`: Claude Code refuses a `sleep` in the foreground), run nothing else while it runs, and when its completion notice arrives go on with the next try in this same run. A pending wait is part of the run: while one is pending, never end the answer, never give the result block, and never tell the owner to run anything. A wait that cannot be run, or whose completion notice never comes, counts as the refusal that ends the poll: the skill ends as after the tenth refusal, never loops and never leaves the answer unfinished.
      - A failure of the first has the sentence `The CI account could not be given the deploy role on the service <service>.`; of the second, `The CI account could not be allowed to act as the account <account>.`

   e. The access, when `access` is false or the service was created by this run:

      ```
      gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=<service> --region=<region> --project=<projectId> --member="<me>" --role="roles/iap.httpsResourceAccessor" --condition=None --quiet
      ```

      A failure has the sentence `The active gcloud account could not be given access to the service <service> through the login.`

   A failure of any command of 5 stops the work at once: no later command of 5, for this component or the next ones, and no retry other than the poll of d. What was made stays (nothing is removed). Then step 6 runs, so that every service that exists is reported as it is.

6. Verify: when a command of 5 ran, run the first three commands of step 3 again, alone, for each component on which a command of 5 ran (not the project number, not the active account, not the login policy). Each such service must exist as declared. A component whose service is still missing or differs, or whose work was not done because of a stop, gets a `pending` item `{ "item": "<name>: <the words that differ, or service, or access>", "reason": "<one sentence, no raw error text>", "how": "/aleogr-cloud-gcp:gcp_deploy-setup <the same arguments> mode=apply" }`. A read that fails here adds the item `<name>: read` with the reason `The service could not be read after the change.` When no command of 5 ran, the reads of step 3 already are the verification: do not repeat them.

7. Status of `apply`: `created` (this run created an account or a service, even when the command that created the service failed), `updated` (this run changed something and created nothing), `unchanged` (no command of 5 ran and no component had work), `failed` (validation, a read of steps 1 to 3, or a stop at the first command of 5 with nothing changed). `created` and `updated` keep their name when `pending` has items: something was changed. A service found existing after its creating command failed counts as created by this run.

Then answer in a few lines: for each component, its service (created, repaired with the words that differed, or as declared), and its address; the sentence of each failure or found service said above; when a service still runs the placeholder, that the first deploy of CI replaces it; and the result block. The answer prints no identifier other than the project id, the service and account names and the services' addresses, and never the e-mail of the active account outside the commands shown before running them.

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
- `outputs.services` has one item per component, in the order of `components`, as of the last read of that component (step 6's when it ran, else step 3's or the read after a failed create), with the fields of `gcp_deploy-describe`: a service that does not exist has `exists` false, `asDeclared` false, `differences` `[]`, `placeholder` false and `url` `null`. `missing`, `differing` and `waiting` are built from it as `gcp_deploy-describe` builds them. `urls` maps each component whose service exists to its address. Lists are written on one line, as above.
- `outputs.created` names the components whose service this run created; `outputs.updated` those on which this run changed anything else (and whose service it did not create). Both are `[]` in `plan`.
- `resources` lists each service that exists as of the last read, with the labels it holds among the three `aleogr-*` ones.
- `failed` from validation or from steps 1 to 3: `resources` is empty and `outputs` is `{ "services": [], "missing": [], "differing": [], "waiting": [], "urls": {}, "created": [], "updated": [] }`, unless step 3 read some services, which are then reported as read.
- `pending` holds the items of step 6; it is empty otherwise.
- The result block holds no person's e-mail: never `<me>` and no member of a policy. The CI account, a service account, appears only inside a `how`, as an argument of the invocation.
