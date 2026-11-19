---
description: Google Cloud Artifact Registry (gcp-artifact-registry) cleanup configure. Use to set the cleanup policy of a project's Docker image repository in Artifact Registry on Google Cloud, keeping the most recent versions of each image and deleting every other version, with dry-run off, and to check that the policy in the cloud is the declared one. Idempotent; plan by default. No fixed cost.
---

# gcp-artifact-registry_cleanup-configure

Owns the cleanup policy of the project's image repository (id `<project>`, in `region`): two rules, and nothing else.

- `keep-most-recent`: keep the `<keep>` most recent versions of each image.
- `delete-the-rest`: delete every version (any tag state). A version that matches a keep rule and a delete rule is kept, so this deletes every version but the `<keep>` most recent of each image.

Dry-run is off: a policy in dry-run deletes nothing, so it counts as different. The policy is the ceiling of what storage can cost. Google applies it in a background job, about once a day, so a run never sees it delete anything. Setting the policy replaces every cleanup policy of the repository. It never creates the repository: create it first with `gcp-artifact-registry_repository-create`.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the repository. |
| `project=<name>` | The aleogr project name, which is also the repository's id. |
| `region=<region>` | The region the repository is declared in, for example `us-central1`. |
| `keep=<n>` | How many of the most recent versions of each image to keep, 1 to 50 (the project default is 5). |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check the arguments, and never ask for anything. A missing required argument ends the skill with the result block, `status` `failed`, the one sentence `<argument> is missing.` and no `gcloud` call. Any invalid value ends it the same way, with the one sentence given below for the rule that failed.

- `projectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`. Otherwise: `projectId is not a GCP project id.`
- `project` has 1 to 14 characters, only lowercase letters, digits and `-`, starts with a letter and does not end with `-`. Otherwise: `project must have 1 to 14 lowercase letters, digits and hyphens, starting with a letter.`
- `region` is a Google Cloud region name: lowercase letters, then one or more `-<letters>` parts, then digits (`us-central1`, `southamerica-east1`). A multi-region (`us`, `europe`) or anything with an uppercase letter is invalid. Otherwise: `region is not a Google Cloud region name (such as us-central1).`
- `keep` is written with digits only, without a leading zero, and is a whole number from 1 to 50 (`0`, `abc`, `5.0`, `-1`, `051` and `51` are invalid). Otherwise: `keep must be a whole number from 1 to 50.`
- `mode` is `plan` or `apply`. Otherwise: `mode must be plan or apply.`

## The policy file

`gcloud` takes the policy as a JSON file: a list of rules. The rules for `keep=5` are a file of this plugin, `${CLAUDE_PLUGIN_ROOT}/files/cleanup-policy.json`:

```json
[
  {
    "name": "keep-most-recent",
    "action": { "type": "KEEP" },
    "mostRecentVersions": { "keepCount": 5 }
  },
  {
    "name": "delete-the-rest",
    "action": { "type": "DELETE" },
    "condition": { "tagState": "ANY" }
  }
]
```

Write `${CLAUDE_PLUGIN_ROOT}` as the real folder of this plugin, so the file is `<plugin folder>/files/cleanup-policy.json`. `<policy file>` below is:

- `keep` is 5: that file, as it is. Never copy or change it.
- any other `keep`: a file written for this run in the system's temporary folder, never in the working folder. Its name is `aleogr-cleanup-policy-keep-<keep>.json`, and its content is exactly the content above, with the number `5` replaced by `<keep>` and nothing else changed. Write it with the Write tool, not with a shell command, so it works the same in bash and in PowerShell. If the Write tool refuses because the file already exists and was not read, read it with the Read tool, then write it again: its whole content is replaced. Write it only in `apply`, right before step 3; it is left in the temporary folder afterwards, and nothing else is removed.
  - The temporary folder: on Linux and macOS it is `/tmp`, and no command is needed. On Windows it is the folder that the `TEMP` environment variable names; read it with this command, the only command besides those of the steps that this skill may run, and only on Windows, only when `keep` is not 5, in `apply`:

    ```
    $env:TEMP
    ```

    (in PowerShell; in `cmd`, `echo %TEMP%`).

The answer shows the content of `<policy file>` (in `plan`, the content it would have).

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone (its exit code and its text decide the next step). On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Read the repository and its policy:

   ```
   gcloud artifacts repositories describe <project> --location=<region> --project=<projectId> --format=json
   ```

   `gcloud` prints lines such as `Encryption: ...`, `Registry URL: ...` and `Repository Size: ...` before the JSON (on its error stream); they are not part of the JSON.

   - Exit non-zero and the text contains both `NOT_FOUND:` and `Requested entity was not found`: the repository does not exist in `region`. Say `The repository <project> does not exist in <region>: create it first with gcp-artifact-registry_repository-create.`, run nothing else and end with `status` `failed`. Never create the repository here. Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only the sentence above about the failure.
   - Any other non-zero exit is a failure of the check: the Artifact Registry API not enabled, permission denied (Artifact Registry answers `PERMISSION_DENIED` with the words "or it may not exist" when the account may not read the repository: that is still this failure), `gcloud` missing or not signed in. Say exactly `The repository could not be read; nothing was changed. Check that the GCP project <projectId> exists, that the Artifact Registry API is enabled in it, and that the active gcloud account is signed in and may read its repositories.` Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only the sentence above about the failure. Run nothing else and end with `status` `failed`.
   - Success: compare the policy, as in "Comparing the policy" below.

2. As declared: run nothing else and end with `status` `unchanged` (in `plan` and in `apply`). Differs: in `plan`, say what differs (a rule missing, a different count, a rule too many, dry-run on) and what would be set, show the content of `<policy file>`, and end with `status` `would-update`. In `apply`, continue.

3. `apply`: set both rules and turn dry-run off, in one command:

   ```
   gcloud artifacts repositories set-cleanup-policies <project> --location=<region> --project=<projectId> --policy="<policy file>" --no-dry-run
   ```

   `--no-dry-run` is required: without it `gcloud` keeps the dry-run setting the repository already has. Never pass `--dry-run`. A non-zero exit stops with `failed` and one sentence, `The cleanup policy could not be set`, with the likely cause and without raw error text. Run nothing else.

4. Read it back with step 1's command, alone. The policy was set in step 3, so the status is `updated` whatever this read shows. When the command succeeds and the policy compares as declared, nothing is pending. A non-zero exit, or a policy that differs, adds one `pending` item whose `item` is `cleanup policy of <project> read back`, `reason` `manual`, and `how` is `/aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_cleanup-configure projectId=<projectId> project=<project> region=<region> keep=<keep> mode=plan`, and the answer says what could not be confirmed.

Then answer in a few lines: the repository, the policy found (and, after a change, the policy read back), what was done, the content of `<policy file>` when it was used or would be, and the result block.

## Comparing the policy

From step 1's JSON. `cleanupPolicies` is an object whose keys are the policies' ids; read its values. Ids and letter case of the values do not matter.

The policy is as declared when all of these hold, and differs otherwise:

- `cleanupPolicies` has exactly two entries.
- One has `action` `KEEP`, a `mostRecentVersions` whose `keepCount` is `<keep>` and that has no `packageNamePrefixes`, and no `condition`.
- The other has `action` `DELETE` and a `condition` whose only field is `tagState`, with the value `ANY`, and no `mostRecentVersions`.
- `cleanupPolicyDryRun` is `false` or absent (absent means `false`).

No `cleanupPolicies` at all is a policy that differs (no rule). Outputs, from the last read (step 4's when it succeeded, else step 1's):

| Output | Source |
|---|---|
| `keep` | `mostRecentVersions.keepCount`, as a number, of the one entry whose `action` is `KEEP` and that has `mostRecentVersions` without `packageNamePrefixes`. `null` when there is no such entry, or more than one. |
| `dryRun` | `cleanupPolicyDryRun` (`false` when absent). |

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "registry",
  "provider": "gcp-artifact-registry",
  "action": "cleanup-configure",
  "mode": "apply",
  "status": "updated",
  "resources": [
    { "type": "cleanup-policy", "id": "<projectId>/<region>/<project>", "name": "<project>" }
  ],
  "outputs": { "keep": 5, "dryRun": false },
  "cost": { "fixed": false, "notes": "no cost of its own; it caps the storage the repository keeps" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `unchanged` (the policy is as declared), `would-update` (plan, the policy differs), `updated` (apply set it), `failed` (an invalid argument, a repository that does not exist, a read that failed, or a set that failed).
- `outputs` are the policy as read last: `keep` and `dryRun` as above. `failed`: `resources` is empty and `outputs` is `{ "keep": null, "dryRun": null }`.
- `unchanged`, `would-update` and `updated`: `resources` lists the repository's cleanup policy as above.
- Each `pending` item is `{ "item": "<what>", "reason": "manual", "how": "<text>" }`.
- Always `cost` as above.
