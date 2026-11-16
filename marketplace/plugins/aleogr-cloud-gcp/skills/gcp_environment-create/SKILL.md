---
description: Google Cloud (GCP) environment create. Use to create the GCP project of an aleogr project and environment (under the environment's folder, or under the organization for the shared platform project), link its billing account and verify it. Idempotent; plan by default.
---

# gcp_environment-create

Creates the GCP project that belongs to a project and an environment, links billing to it and verifies the result. If the project already exists it changes nothing. It has no fixed cost.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `project=<name>` | The aleogr project name. |
| `environment=lab\|hom\|prd` | The project environment. |
| `mode=plan\|apply` | `plan` (default) reports what would change and changes nothing; `apply` executes. |
| `platform=lab` | Only the aleogr platform passes it, to create the shared project. |

## Validate first

Before running any command, check the arguments. Any failure ends the skill with the result block, `status` `failed`, one sentence saying which rule failed, and no `gcloud` call.

- `project` and `environment` are required; `environment` is one of `lab`, `hom`, `prd`; `mode` is `plan` or `apply`; `platform` is absent or `lab`. If `project` or `environment` is missing, ask for it instead.
- `project` has 1 to 14 characters (the project ID is limited to 30 characters), only `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`.
- Without `platform=lab`, `test` and `shared` are refused as project names. With it, `shared` is allowed.

## Steps

Show each command before running it. Run only the commands below, in this order. In `plan` mode the discovery commands (steps 1 to 4) are allowed because they only read; never run `projects create` or `billing projects link` in `plan`.

1. Check whether the project exists: invoke `aleogr-cloud-gcp:gcp_environment-describe` with `project=<project> environment=<environment>`. If its result has `status` `failed`, stop with `failed`. If `exists` is true, run nothing else and end with `status` `unchanged`, reporting its `projectId`.

2. Organization (needed to find the parent; run it in either mode):

   ```
   gcloud organizations list --format="value(name)"
   ```

3. Parent:
   - With `platform=lab`: the parent is the organization from step 2. Run no folder command.
   - Otherwise: find the folder whose display name equals the environment:

     ```
     gcloud resource-manager folders list --organization=<organizationId> --filter="displayName=<environment>" --format="value(name)"
     ```

     No output: stop with `failed`, saying that the folder for this environment must be created first. Do not create folders.

4. Billing account:

   ```
   gcloud billing accounts list --filter="open=true" --format="value(name)"
   ```

`gcloud` returns names as `organizations/<id>`, `folders/<id>` and `billingAccounts/<id>`. The flags below take the bare id, the part after the slash: `--organization=<id>`, `--folder=<id>`, `--billing-account=<id>`.

For steps 2 to 4: a non-zero exit, or empty output, stops the skill with `failed` and one sentence of cause, without raw error text. More than one line means more than one organization, folder or billing account: stop with `failed`, say how many were found and ask which one to use (organization, folder or billing account), without printing any identifier in the answer or in the result block. Do not pick one; nobody may answer in an automated run, so run no create command.

5. `plan` mode ends here: report what would be created (project ID with a placeholder suffix such as `aleogr-<environment>-<project>-xxxx`, parent type, billing link) and end with `status` `would-create`.

6. `apply` mode. Build the project ID `aleogr-<environment>-<project>-<random>` where `<random>` is 4 random characters of `a-z0-9` (pick the means that works in the current shell). Create the project:

   ```
   gcloud projects create <projectId> --organization=<id> --name="<environment> <project>" --labels=aleogr-project=<project>,aleogr-environment=<environment>,aleogr-platform=lab
   ```

   Use `--folder=<id>` instead of `--organization=<id>` unless `platform=lab`, and add the label `aleogr-platform=lab` only with `platform=lab`. A non-zero exit stops with `failed` (nothing was created).

7. Link billing:

   ```
   gcloud billing projects link <projectId> --billing-account=<id>
   ```

   If it exits non-zero the project exists but has no billing: stop with `status` `pending`, name the project ID, and set `pending` to one item whose `how` is the exact command `gcloud billing projects link <projectId> --billing-account=<id>` (with the real bare id, so the owner can run it).

8. Verify:

   ```
   gcloud projects describe <projectId> --format="value(lifecycleState)"
   gcloud billing projects describe <projectId> --format="value(billingEnabled)"
   ```

   Expect `ACTIVE` and `True`. A non-zero exit, or any other value, ends with `failed` and a sentence saying what could not be verified.

Then answer in a few lines: the project ID, its parent type, whether billing is linked, and the result block.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "environment-create",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "project", "id": "<projectId>", "name": "<project>", "labels": { "aleogr-project": "<project>", "aleogr-environment": "<environment>" } }
  ],
  "outputs": { "projectId": "<projectId>" },
  "cost": { "fixed": false, "notes": "project creation is free" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-create` (plan), `created`, `unchanged` (the project already existed), `pending` (created, billing not linked), `failed`.
- `would-create`: `resources` lists the project with the planned ID, `outputs.projectId` is `null`.
- `failed`: `resources` is empty, `outputs` is `{ "projectId": null }`, and nothing but the one-sentence cause is added to the answer.
- `pending`: `resources` lists the project and `outputs.projectId` is its ID.
- Never put organization, folder or billing identifiers in the result block, except inside `pending[].how`.
