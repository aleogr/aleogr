---
description: Google Cloud (GCP) services enable. Use to enable the Google APIs a GCP project of an aleogr project and environment (or the shared platform project) needs, enabling only the ones still missing. Idempotent; plan by default.
---

# gcp_services-enable

Enables Google Cloud APIs on the GCP project that belongs to a project and an environment (or on the shared platform project). It compares the requested APIs with the enabled ones and enables only the missing ones. It never creates a project and has no fixed cost.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `project=<name>` | The aleogr project name (for the shared platform project: `shared`). |
| `environment=dev\|hom\|prd` | The project environment. |
| `platform=shared` | Instead of `environment`, with `project=shared`: the shared platform project, which has no environment. |
| `projectId=<id>` | Instead of the others: the GCP project id, when the caller already knows it. |
| `services=<list>` | Comma-separated API names, for example `a.googleapis.com,b.googleapis.com`. |
| `mode=plan\|apply` | `plan` (default) reports what would change and changes nothing; `apply` executes. |

## Validate first

Before running any command, check the arguments. Any failure ends the skill with the result block, `status` `failed`, one sentence saying which rule failed, and no `gcloud` call.

- `services` is required, and the project is named in one of three ways: `projectId`, `project=<name> environment=<environment>`, or `project=shared platform=shared` (if `services`, `project` or `environment` is missing, the sentence names it: `<argument> is missing.`; never ask for it, nobody may answer in an automated run); `environment` is one of `dev`, `hom`, `prd`; `platform` is absent or `shared`; `mode` is `plan` or `apply`.
- `platform=shared` needs `project=shared` and no `environment`; `project=shared` needs `platform=shared`.
- `projectId`, when given, has 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`.
- Every entry of `services` ends with `.googleapis.com` and has only `a-z`, `0-9`, `-` and `.` before that suffix. Remove duplicates.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Find the project and the enabled services: invoke `aleogr-cloud-gcp:gcp_environment-describe` with `projectId=<projectId>` when it was given, otherwise with `project=shared platform=shared` (shared platform project) or `project=<project> environment=<environment>`. Use its result only as input and do not repeat it; this skill's answer ends with exactly one `aleogr-result` block, its own.
   - `status` `failed`: stop with `failed`.
   - `exists` false: stop with `failed`, saying the environment must be created first (`gcp_environment-create`). Never create a project.
   - Otherwise take `projectId` and `enabledServices`.

2. Compare. `alreadyEnabled` is the requested services present in `enabledServices`; `missing` is the rest.
   - `missing` empty: run nothing else and end with `status` `unchanged`.
   - `plan` mode: run nothing else and end with `status` `would-update`, listing `missing`.

3. `apply` mode: enable all the missing services with one command:

   ```
   gcloud services enable <missing...> --project=<projectId>
   ```

   A non-zero exit stops with `failed` and one sentence of cause, without raw error text (nothing was enabled that needs to be kept).

4. Verify:

   ```
   gcloud services list --enabled --project=<projectId> --format="value(config.name)"
   ```

   Every requested service must be in the output. A non-zero exit, or a requested service missing, ends with `pending`: say which one could not be confirmed, and set `pending[].how` to this same command.

Then answer in a few lines: the project ID, which services were enabled, which already were, and the result block.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "services-enable",
  "mode": "apply",
  "status": "updated",
  "resources": [
    { "type": "project", "id": "<projectId>", "name": "<project>", "labels": { "aleogr-project": "<project>", "aleogr-environment": "<environment>" } }
  ],
  "outputs": {
    "projectId": "<projectId>",
    "enabled": ["<service>.googleapis.com"],
    "alreadyEnabled": ["<service>.googleapis.com"]
  },
  "cost": { "fixed": false, "notes": "enabling APIs is free" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-update` (plan: some are missing), `updated`, `unchanged`, `pending` (enabled, but not confirmed by step 4), `failed`.
- `enabled` lists the services this run enabled (in `plan`, the ones it would enable); `alreadyEnabled` the requested ones that were on.
- `failed`: `resources` is empty and `outputs` is `{ "projectId": null, "enabled": [], "alreadyEnabled": [] }`.
- `pending`: `resources` and `outputs.projectId` are set as usual.
