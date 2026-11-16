---
description: Google Cloud (GCP) environment describe. Use to learn whether the GCP project of an aleogr project and environment exists and what state it is in (parent, billing, enabled services, labels). Read-only; other aleogr-cloud-gcp skills and the platform plan call it first.
---

# gcp_environment-describe

Reads the real state of the GCP project that belongs to a project and an environment, and reports it. It never creates, changes or deletes anything and has no `mode`.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `project=<name>` | The aleogr project name (for the shared platform project: `shared`). |
| `environment=lab\|hom\|prd` | The project environment. |

If either is missing, ask for it before running any command.

## Steps

The project is found by its labels, so the organization and the folder are not needed: do not run `gcloud organizations list` or `gcloud resource-manager folders list`. Show each command before running it. Run only the commands below, in this order.

1. Find the project:

   ```
   gcloud projects list --filter="labels.aleogr-project=<project> AND labels.aleogr-environment=<environment>" --format="value(projectId)"
   ```

   - If `gcloud` is not installed or the command fails (not authenticated, no access), say so in one sentence, with no raw error text, and end with the result block with `status` `failed`. Run nothing else.
   - No output: the project does not exist. Skip the next steps and report `exists` false.
   - More than one line: stop and report the project IDs found; do not pick one. End with `status` `failed`.
   - One line: that is the project ID. Continue.

2. Describe it (labels and parent):

   ```
   gcloud projects describe <projectId> --format=json
   ```

   Take `labels` from the output. Build `parent` from the `parent` object as `<type>s/<id>`: `folders/<id>` or `organizations/<id>`. If there is no parent, use `null`.

3. Billing:

   ```
   gcloud billing projects describe <projectId> --format="value(billingEnabled)"
   ```

   `billingLinked` is true when the output is `True`, and false only when the command succeeds with empty output (or `False`). A non-zero exit is not "not linked": it is a failure (see below).

4. Enabled services:

   ```
   gcloud services list --enabled --project=<projectId> --format="value(config.name)"
   ```

   `enabledServices` is the list of lines, sorted.

If any command in steps 2 to 4 exits non-zero (permission denied, API disabled, any error), stop at once: do not run the remaining steps and do not guess the missing values. Say the cause in one sentence, with no raw error text, and end with the result block with `status` `failed`.

Then answer in a few lines: the project ID, its parent, whether billing is linked, the number of enabled services, and the result block.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "environment-describe",
  "mode": "plan",
  "status": "unchanged",
  "resources": [
    { "type": "project", "id": "<projectId>", "name": "<project>", "labels": { "aleogr-project": "<project>", "aleogr-environment": "<environment>" } }
  ],
  "outputs": {
    "exists": true,
    "projectId": "<projectId>",
    "parent": "folders/<id> or organizations/<id>",
    "billingLinked": true,
    "enabledServices": ["<service>.googleapis.com"],
    "labels": { "aleogr-project": "<project>", "aleogr-environment": "<environment>" }
  },
  "cost": { "fixed": false, "notes": "read-only" },
  "pending": []
}
```

- `status` is `unchanged` whenever the state was read, whether or not the project exists. It is `failed` when any command exited non-zero or the project IDs were ambiguous (see steps 1 to 4); then `resources` is empty and `outputs` is `{ "exists": null }`.
- Project does not exist: `resources` is empty and `outputs` is `{ "exists": false, "projectId": null, "parent": null, "billingLinked": false, "enabledServices": [], "labels": {} }`.
- `mode` is always `plan`: the skill only reads.
