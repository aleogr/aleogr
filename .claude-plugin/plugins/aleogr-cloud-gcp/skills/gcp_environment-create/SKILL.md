---
description: Google Cloud (GCP) environment create. Use to create the GCP project of an aleogr project and environment (in the environment's folder, under the organization or, for test projects, inside the tst folder; or directly under the organization for the shared platform project), link its billing account and verify it. Idempotent; plan by default.
---

# gcp_environment-create

Creates the GCP project that belongs to a project and an environment (or the shared platform project), links billing to it and verifies the result. If the project already exists and has billing, it changes nothing; if its billing is not linked, it links it. It has no fixed cost.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `project=<name>` | The aleogr project name. |
| `environment=dev\|hom\|prd` | The project environment. |
| `mode=plan\|apply` | `plan` (default) reports what would change and changes nothing; `apply` executes. |
| `platform=shared` | Only the aleogr platform passes it, with `project=shared` and no `environment`, to create the shared platform project. |
| `root=tst` | Optional. A project that tests the tooling: the environment's folder is looked up inside the folder `tst` instead of under the organization. |

## Validate first

Before running any command, check the arguments. Any failure ends the skill with the result block, `status` `failed`, one sentence saying which rule failed, and no `gcloud` call.

- `mode` is `plan` or `apply`; `platform` is absent or `shared`; `root` is absent or `tst` (any other value of `root` fails).
- With `platform=shared`: `project` must be `shared`, `environment` must be absent, and `root` is not allowed.
- Without `platform`: `project` and `environment` are required (if one is missing, the sentence names it: `<argument> is missing.`; never ask for it, nobody may answer in an automated run); `environment` is one of `dev`, `hom`, `prd`; `test` and `shared` are refused as project names.
- `project` has 1 to 14 characters (the project ID is limited to 30 characters), only `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. In `plan` mode the discovery commands (steps 1 to 4, the search by parent of step 3 included) are allowed because they only read; never run `projects create` or `billing projects link` in `plan`.

1. Check whether the project exists: invoke `aleogr-cloud-gcp:gcp_environment-describe` with `project=shared platform=shared` when `platform=shared` was given, otherwise with `project=<project> environment=<environment>`. The describe skill ends with its own `aleogr-result` block: use it only as input and do not repeat it; this skill's answer ends with exactly one `aleogr-result` block, its own. If the describe result has `status` `failed`, stop with `failed`. If `exists` is true:
   - `billingLinked` true: run nothing else and end with `status` `unchanged`, reporting its `projectId`.
   - `billingLinked` false (a project left without billing): do not create anything. Run step 4 only, and no other discovery command. In `plan`, end with `status` `would-update` (billing link missing). In `apply`, go to the repair in step 7 with the existing `projectId`, and end with `updated` instead of `created`.

2. Organization (needed to find the parent; run it in either mode):

   ```
   gcloud organizations list --format="value(name)"
   ```

3. Parent. This skill never creates folders.
   - With `platform=shared`: the parent is the organization from step 2. Run no folder command.
   - Without `root`: find the folder whose display name equals the environment, under the organization:

     ```
     gcloud resource-manager folders list --organization=<organizationId> --filter="displayName=<environment>" --format="value(name)"
     ```

     No output: stop with `failed`, saying that the folder `<environment>` must be created first.
   - With `root=tst`: first find the folder `tst` under the organization, then the folder of the environment inside it:

     ```
     gcloud resource-manager folders list --organization=<organizationId> --filter="displayName=tst" --format="value(name)"
     gcloud resource-manager folders list --folder=<tstFolderId> --filter="displayName=<environment>" --format="value(name)"
     ```

     No output from the first: stop with `failed`, saying that the folder `tst` must be created first, and run no other command. No output from the second: stop with `failed`, saying that the folder `<environment>` inside `tst` must be created first. The parent is the folder found by the second command.

   Then, in either mode, search the parent once more, alone, before step 4. The search by labels of step 1 is eventually consistent and may not show a project created a minute ago; a search that names the parent reads a more consistent index. With `platform=shared` (the parent is the organization):

   ```
   gcloud projects list --filter="parent.type=organization AND parent.id=<organizationId> AND labels.aleogr-project=shared AND labels.aleogr-platform=shared" --format="value(projectId)"
   ```

   Otherwise (the parent is the environment's folder; with `root=tst`, the folder inside `tst`):

   ```
   gcloud projects list --filter="parent.type=folder AND parent.id=<folderId> AND labels.aleogr-project=<project> AND labels.aleogr-environment=<environment>" --format="value(projectId)"
   ```

   - Non-zero exit (not `0`): stop with `failed` and one sentence of cause, without raw error text. Create nothing.
   - No output: the project does not exist. Continue with step 4.
   - One line: that is the project's ID, and the project exists. Never create a project then. Say so in this one sentence: `The first search had not seen project <projectId> yet; the search by parent found it.` Then check its billing, alone:

     ```
     gcloud billing projects describe <projectId> --format="value(billingEnabled)"
     ```

     A non-zero exit stops with `failed` and one sentence of cause. `True`: run nothing else and end with `status` `unchanged`, reporting this `projectId`. Empty output or `False`: billing is not linked; run step 4, then in `plan` end with `status` `would-update`, and in `apply` go to the repair in step 7 with this `projectId` and end with `updated` instead of `created`, exactly as for an existing project found in step 1.
   - More than one line: stop with `failed`, saying in one sentence that `<n>` projects with these labels were found in the parent and none was picked. Create nothing.

4. Billing account:

   ```
   gcloud billing accounts list --filter="open=true" --format="value(name)"
   ```

`gcloud` returns names as `organizations/<id>`, `folders/<id>` and `billingAccounts/<id>`. The flags below take the bare id, the part after the slash: `--organization=<id>`, `--folder=<id>`, `--billing-account=<id>`.

For steps 2 to 4 (except the search by parent at the end of step 3, whose outcomes are listed there): a non-zero exit, or empty output, stops the skill with `failed` and one sentence of cause, without raw error text. More than one line means more than one organization, folder (`tst` or the environment's) or billing account: stop with `failed`, say how many were found and ask which one to use (organization, folder or billing account), without printing any identifier in the answer or in the result block. Do not pick one; nobody may answer in an automated run, so run no create command.

5. `plan` mode ends here: report what would be created (project ID with a placeholder suffix such as `aleogr-<environment>-<project>-xxxx`, or `aleogr-shared-xxxx` for the shared project, parent type, billing link) and end with `status` `would-create`.

6. `apply` mode (a repair of an existing project, found in step 1 or by the search by parent of step 3, skips to step 7). Build the project ID: `aleogr-shared-<random>` with `platform=shared`, otherwise `aleogr-<environment>-<project>-<random>`, where `<random>` is 4 random characters of `a-z0-9` (pick the means that works in the current shell). Create the project with one of these two commands:
   - With `platform=shared` (the shared project, under the organization, with the platform label and no environment):

     ```
     gcloud projects create <projectId> --organization=<id> --name="shared" --labels="aleogr-project=shared,aleogr-platform=shared"
     ```

   - Otherwise (in the environment's folder found in step 3, without the platform label; with `root=tst` that is the folder inside `tst`):

     ```
     gcloud projects create <projectId> --folder=<id> --name="<environment> <project>" --labels="aleogr-project=<project>,aleogr-environment=<environment>"
     ```

   Keep the quotes around the `--labels` value: PowerShell splits an unquoted value at its commas, and `gcloud` then rejects the arguments.

   A non-zero exit stops with `failed` (nothing was created). From here on the project exists: any later failure ends with `pending`, never `failed`, with `outputs.projectId` set to the project ID, `resources` listing the project, and `pending[].how` holding the next command to run.

7. Link billing:

   ```
   gcloud billing projects link <projectId> --billing-account=<id>
   ```

   If it exits non-zero the project has no billing: stop with `status` `pending`, name the project ID, and set `pending` to one item whose `how` is the exact command `gcloud billing projects link <projectId> --billing-account=<id>` (with the real bare id, so the owner can run it). This also holds when repairing an existing project.

8. Verify:

   ```
   gcloud projects describe <projectId> --format="value(lifecycleState)"
   gcloud billing projects describe <projectId> --format="value(billingEnabled)"
   ```

   Expect `ACTIVE` and `True`, also when repairing an existing project (a non-empty `billingAccountName` is not enough). A non-zero exit, or any other value, ends with `pending` (the project exists) and a sentence saying what could not be verified; `pending[].how` is the command that checks it, for example `gcloud billing projects describe <projectId> --format="value(billingEnabled)"`.

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

- `mode` echoes the mode used. `status` is one of `would-create` (plan), `created`, `would-update` (plan: the project exists, billing not linked), `updated` (billing linked on an existing project), `unchanged` (the project exists with billing), `pending` (the project exists, a step after creation or the billing link failed), `failed` (nothing was created).
- `would-create`: `resources` lists the project with the planned ID, `outputs.projectId` is `null`.
- `would-update` and `updated`: `resources` lists the project; `outputs.projectId` is its ID.
- `failed`: `resources` is empty, `outputs` is `{ "projectId": null }`, and nothing but the one-sentence cause is added to the answer.
- `pending`: `resources` lists the project and `outputs.projectId` is its ID, always.
- With `platform=shared`, the labels in `resources` are `{ "aleogr-project": "shared", "aleogr-platform": "shared" }`.
- Never put organization, folder or billing identifiers in the result block, except inside `pending[].how`.
