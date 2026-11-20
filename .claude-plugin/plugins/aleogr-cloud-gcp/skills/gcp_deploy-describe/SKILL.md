---
description: Google Cloud (GCP) deploy describe. Use to learn whether each component of an aleogr project runs, in the GCP project of an environment, as a Cloud Run service as declared - its own account, the login (IAP) on, never public, no instance always on, its size, its labels, the login's agent allowed to call it, and the CI account allowed to replace its image - and whether it still runs the placeholder image. Read-only; a service that does not exist is not a failure.
---

# gcp_deploy-describe

Reads, for each component, the Cloud Run service `<project>-<component>` in one GCP project, its access policy and its account's access policy, and says whether the service exists, whether it is as declared and, when it is not, which parts differ. It never creates, changes or deletes anything and has no `mode`. It does not read who may get in through the login: `gcp_access-grant` does.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `environment`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project of the project and environment (from `gcp_environment-describe`). |
| `project=<name>` | The aleogr project name. |
| `region=<region>` | The region of the services, for example `us-central1`. |
| `components=<name>[,<name>…]` | The components, in the declaration's order; each runs as the service `<project>-<name>`. |
| `maxInstances=<n>` | The declared maximum number of instances of each service. |
| `cpu=<n>` | The declared CPU of each service. |
| `memory=<size>` | The declared memory of each service, such as `512Mi`. |
| `ciAccount=<e-mail>` | The CI account (`<project>-ci@<projectId>.iam.gserviceaccount.com`, from `gcp_ci-identity-setup`). |
| `environment=<name>` | Optional: the environment, `dev`, `hom` or `prd`. Given, the service's `aleogr-environment` label must equal it. Orchestrators always give it. |

## Validate first

Before any command, check every argument, and never ask for anything. Each argument that is missing or breaks its rule gives its one sentence below, one per line; when there is at least one, the skill ends with the result block, `status` `failed`, those sentences and no `gcloud` call.

- A missing required argument: `<argument> is missing.`
- `environment`, when given, is `dev`, `hom` or `prd`. Otherwise: `environment must be dev, hom or prd.`
- `projectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `projectId is not a GCP project id.`
- `project` has 1 to 14 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise: `project must have 1 to 14 lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen.`
- `region` is a Google Cloud region name: lowercase letters, then one or more `-<letters>` parts, then digits (`us-central1`, `southamerica-east1`). Otherwise: `region is not a Google Cloud region name (such as us-central1).`
- `components` holds one or more names separated by `,`, with no space and no empty name. Each name has 1 to 20 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`. Otherwise, for each name that breaks it: `component <name> must have 1 to 20 lowercase letters, digits and hyphens, starting with a letter and not ending with a hyphen.` A name given twice: `component <name> is given twice.`
- For each component, `<project>-<name>` has 6 to 30 characters: it is the service's name and its account's id, and an account id has 6 to 30. Otherwise: `<project>-<name> has <n> characters: a service's name, which is also its account's, must have 6 to 30.`
- `maxInstances` is a whole number from 1 to 100, written without a leading `0`. Otherwise: `maxInstances must be a whole number from 1 to 100.`
- `cpu` is `1`, `2`, `4` or `8`. Otherwise: `cpu must be 1, 2, 4 or 8.`
- `memory` is a whole number without a leading `0` followed by `Mi` or `Gi` (`512Mi`, `1Gi`). Otherwise: `memory must be a size in Mi or Gi, such as 512Mi.`
- `ciAccount` is `<id>@<projectId>.iam.gserviceaccount.com`, all lowercase, with no prefix such as `serviceAccount:`, where `<id>` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`, and `<projectId>` is exactly the argument `projectId`. Otherwise: `ciAccount must be a service account of the project <projectId> (<id>@<projectId>.iam.gserviceaccount.com).`

## Names

For each component `<name>`:

- `<service>` is `<project>-<name>`.
- `<account>` is `<project>-<name>@<projectId>.iam.gserviceaccount.com`.
- `<agent>` is `serviceAccount:service-<number>@gcp-sa-iap.iam.gserviceaccount.com`, the login's (IAP's) service agent, with `<number>` the project number read in step 1.
- The labels are `aleogr-project=<project>`, `aleogr-component=<name>`, and `aleogr-environment=<environment>` when `environment` is given (without it, any of `dev`, `hom` or `prd`).

## As declared

A service that exists is as declared when none of these parts differs. Each part that differs adds its word to the service's `differences`, in this order:

| Word | The part is as declared when |
|---|---|
| `account` | `.spec.template.spec.serviceAccountName` is exactly `<account>`, and the account exists (its policy was read in step 3). |
| `scaling` | `.metadata.annotations["run.googleapis.com/maxScale"]` is exactly `maxInstances`; `.metadata.annotations["run.googleapis.com/minScale"]` is absent or `0`; `.metadata.annotations["run.googleapis.com/scalingMode"]` is not `manual`; and `.spec.template.metadata.annotations["autoscaling.knative.dev/minScale"]` is absent or `0`. Any minimum above 0 keeps an instance running, which has a fixed cost. |
| `size` | `.spec.template.spec.containers[0].resources.limits.cpu` is `cpu` (a value in thousandths reads as CPUs: `1000m` is `1`, `2000m` is `2`); `.spec.template.spec.containers[0].resources.limits.memory` is `memory` (`1Gi` is `1024Mi`); and `.spec.template.metadata.annotations["run.googleapis.com/cpu-throttling"]` is absent or `true` (billing by request). |
| `public` | No binding of the service's policy, whatever its role, lists `allUsers` or `allAuthenticatedUsers`, and `.metadata.annotations["run.googleapis.com/invoker-iam-disabled"]` is absent or not `true`. |
| `login` | `.metadata.annotations["run.googleapis.com/iap-enabled"]` is exactly `true`. |
| `agent` | A binding of `roles/run.invoker` without a `condition` in the service's policy lists `<agent>`. |
| `ci` | A binding of `roles/run.developer` without a `condition` in the service's policy lists `serviceAccount:<ciAccount>`, and a binding of `roles/iam.serviceAccountUser` without a `condition` in the account's policy lists `serviceAccount:<ciAccount>` (when the account does not exist, `ci` differs too). |
| `labels` | `.metadata.labels` holds `aleogr-project` = `<project>`, `aleogr-component` = `<name>` and `aleogr-environment` = `environment` (when it is not given: `dev`, `hom` or `prd`). Other labels do not count. |

- `placeholder` is true when `.spec.template.spec.containers[0].image` is the placeholder, Google's hello sample: `us-docker.pkg.dev/cloudrun/container/hello`, alone or followed by `:<tag>` or `@sha256:<digest>`. Any other image is one CI deployed.
- `url` is `.status.url`, or `null` when it is absent.

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. The text of a non-zero exit is read to decide and is never quoted: never explain which text decided, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons). Each failure is said with its sentence below and nothing else about it.

1. The project number:

   ```
   gcloud projects describe <projectId> --format="value(projectNumber)"
   ```

   Exit 0 with a number: that is `<number>`. A non-zero exit or an empty output: say `The GCP project <projectId> could not be read. Check that it exists and that the active gcloud account may read it.` and end with `failed`.

2. Each service, in the order of `components`:

   ```
   gcloud run services describe <service> --project=<projectId> --region=<region> --format=json
   ```

   - Exit 0: the service exists; read it as "As declared" says.
   - A non-zero exit whose text contains `Cannot find service`, `NOT_FOUND` or `could not be found`: the service does not exist. That is not a failure: `exists` false, and no other read for this component. Both are needed: a non-zero exit without that text is not "missing".
   - Any other non-zero exit (permission denied, the Cloud Run API not enabled, a network error, anything else): say `The service <service> could not be read. Check that the Cloud Run API is enabled in <projectId> and that the active gcloud account may read its services.` and end with `failed`. Never treat it as missing.

3. For each service that exists, in the same order, its policy, then its account's policy:

   ```
   gcloud run services get-iam-policy <service> --project=<projectId> --region=<region> --format=json
   gcloud iam service-accounts get-iam-policy <account> --project=<projectId> --format=json
   ```

   - Exit 0: read the `bindings` (none at all is an empty policy).
   - A non-zero exit of the account's policy whose text contains `NOT_FOUND` or `does not exist`: the account does not exist (`account` and `ci` differ).
   - Any other non-zero exit: say `The access of the service <service> could not be read. Check that the active gcloud account may read the access of its services and accounts.` and end with `failed`.

Then answer in a few lines: for each component, whether its service exists, is as declared or differs (naming the words), and whether it still runs the placeholder; then the result block. The answer prints no identifier other than the project id, the service names and their addresses, and no word of a policy's members other than `<ciAccount>`.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "deploy-describe",
  "mode": "plan",
  "status": "unchanged",
  "resources": [
    { "type": "run-service", "id": "<projectId>/<region>/<project>-web", "name": "<project>-web", "labels": { "aleogr-project": "<project>", "aleogr-environment": "dev", "aleogr-component": "web" } }
  ],
  "outputs": {
    "services": [
      { "component": "web", "exists": true, "asDeclared": true, "differences": [], "placeholder": true, "url": "https://<project>-web-<number>.<region>.run.app" },
      { "component": "api", "exists": false, "asDeclared": false, "differences": [], "placeholder": false, "url": null }
    ],
    "missing": ["api"],
    "differing": [],
    "waiting": ["web"]
  },
  "cost": { "fixed": false, "notes": "read-only" },
  "pending": []
}
```

- `mode` is always `plan`: the skill only reads. `status` is `unchanged` whenever every read answered, whatever it found (missing or differing services included), and `failed` otherwise. `pending` is always empty.
- `resources` lists each service that exists, with the labels it holds among the three `aleogr-*` ones.
- `outputs.services` has one item per component, in the order of `components`. A service that does not exist has `exists` false, `asDeclared` false, `differences` `[]`, `placeholder` false and `url` `null`. Lists are written on one line, as above.
- `outputs.missing` names the components whose service does not exist; `outputs.differing` those whose service exists and is not as declared; `outputs.waiting` those whose service is as declared and still runs the placeholder (the first deploy of CI has not replaced it). Each in the order of `components`.
- `failed`: `resources` is empty and `outputs` is `{ "services": [], "missing": [], "differing": [], "waiting": [] }`.
- The result block holds no e-mail at all: no member of a policy, not the login's agent, not `<ciAccount>`.
