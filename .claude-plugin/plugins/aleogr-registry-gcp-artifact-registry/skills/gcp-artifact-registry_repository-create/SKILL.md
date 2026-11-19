---
description: Google Cloud Artifact Registry (gcp-artifact-registry) repository create. Use to create a project's Docker image repository in Artifact Registry on Google Cloud, in the project's own GCP project and declared region, labelled with the project and the environment, and to learn the image path every component's image starts with. Idempotent (an existing repository is never touched); plan by default. No fixed cost.
---

# gcp-artifact-registry_repository-create

Creates the project's image repository in Artifact Registry when it is missing: id `<project>`, format Docker, in `region`, with the labels `aleogr-project=<project>` and `aleogr-environment=<environment>`, and reads it back. An existing repository is never changed. A repository of that id that exists in another region is left alone and reported as something to fix by hand: a repository has one region. Nothing here has a fixed cost: an empty repository costs nothing, and storage is free up to 0.5 GB.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that will hold the repository (the project's own, for that environment). |
| `project=<name>` | The aleogr project name, which is also the repository's id. |
| `environment=dev\|hom\|prd` | The project environment, written as a label. |
| `region=<region>` | The declared region, for example `us-central1`. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check the arguments. A missing required argument is a validation failure, with the sentence `<argument> is missing.`: do not ask for it. Any failure ends the skill with the result block, `status` `failed`, the one sentence given below for the rule that failed, and no `gcloud` call.

- `projectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`. Otherwise: `projectId is not a GCP project id.`
- `project` has 1 to 14 characters, only lowercase letters, digits and `-`, starts with a letter and does not end with `-`. Otherwise: `project must have 1 to 14 lowercase letters, digits and hyphens, starting with a letter.`
- `environment` is one of `dev`, `hom`, `prd`. Otherwise: `environment must be dev, hom or prd.`
- `region` is a Google Cloud region name: lowercase letters, then one or more `-<letters>` parts, then digits (`us-central1`, `southamerica-east1`). A multi-region (`us`, `europe`) or anything with an uppercase letter is invalid. Otherwise: `region is not a Google Cloud region name (such as us-central1).`
- `mode` is `plan` or `apply`. Otherwise: `mode must be plan or apply.`

## Steps

Show each command before running it. Run only the commands below (and the one skill invoked), in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Check whether the repository exists: invoke `aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_registry-describe` with `projectId=<projectId> project=<project> region=<region>`. Its `aleogr-result` block is only input: do not repeat it; this skill's answer ends with exactly one block, its own.
   - Describe `status` `failed`: stop with `failed` and its one-sentence cause, without raw error text. Run nothing else.
   - `exists` true and `format` `DOCKER`: run nothing else and end with `status` `unchanged` and the describe's `imagePath`. Never change an existing repository.
   - `exists` true with another `format`: a repository's format cannot be changed. Run nothing else and end with `status` `pending`, one item whose `item` is `repository <project>`, `reason` `manual`, and `how` `fix by hand: the repository <project> in <region> is not a Docker repository; delete it, then run this skill again`.
   - `exists` false and `otherRegions` not empty: run nothing else and end with `status` `pending` (in `plan` and in `apply`; nothing is changed). One item whose `item` is `repository <project> in <otherRegions>`, `reason` `manual`, and `how` `fix by hand: the repository <project> exists in <otherRegions>, not in <region>, and a repository has one region; delete it there (moving the images it holds first, if they are needed), or declare the region <otherRegions>`. The answer says the same in one sentence.
   - `exists` false and `otherRegions` empty: continue.

2. `plan` ends here: say what would be created (the repository `<project>`, format Docker, in `<region>`, its two labels, and the image path) and end with `status` `would-create`.

3. `apply`: create the repository. The command waits until the repository exists (no `--async`):

   ```
   gcloud artifacts repositories create <project> --project=<projectId> --location=<region> --repository-format=docker --labels="aleogr-project=<project>,aleogr-environment=<environment>"
   ```

   Keep the quotes around the `--labels` value: PowerShell splits an unquoted value at its commas, and `gcloud` then rejects the arguments.

   - Exit zero: go to step 4.
   - Exit non-zero and the text contains `ALREADY_EXISTS`: the repository appeared since step 1 (another run made it). Run the read of step 4 once, and only it. It succeeds, `format` is `DOCKER` and `name` has `locations/<region>`: end with `status` `unchanged` and the `imagePath`, with the sentence `The repository was created by another run between the check and the create.` and nothing quoted from `gcloud`'s answer (not even its status word). Anything else (a non-zero exit, another format or region): end with `failed`, one sentence saying the repository exists but could not be confirmed as a Docker repository in `<region>`, without raw error text.
   - Any other non-zero exit stops with `failed` and one sentence, `The repository could not be created`, with the likely cause and without raw error text. Run nothing else.

4. Read it back, with this command alone (not the describe skill; the projection keeps only what is checked):

   ```
   gcloud artifacts repositories describe <project> --location=<region> --project=<projectId> --format="json(name,format,labels)"
   ```

   `gcloud` prints lines such as `Encryption: ...` and `Registry URL: ...` before the JSON; they are not part of it. After a create that exited zero, the repository was created in step 3, so the status is `created` whatever this read shows. When the command succeeds, `format` is `DOCKER` and `labels` has both labels with the values above, nothing is pending. A non-zero exit, or a JSON that differs, adds one `pending` item whose `item` is `repository <project> read back`, `reason` `manual`, and `how` is `/aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_registry-describe projectId=<projectId> project=<project> region=<region>`, and the answer says what could not be confirmed.

Then answer in a few lines: the repository, its region, what was done (created, already there, or what to fix by hand), the image path, and the result block.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "registry",
  "provider": "gcp-artifact-registry",
  "action": "repository-create",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "repository", "id": "<projectId>/<region>/<project>", "name": "<project>", "labels": { "aleogr-project": "<project>", "aleogr-environment": "<environment>" } }
  ],
  "outputs": { "imagePath": "<region>-docker.pkg.dev/<projectId>/<project>" },
  "cost": { "fixed": false, "notes": "free up to 0.5 GB of storage, then about US$ 0.10 per GB a month" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-create` (plan), `created`, `unchanged` (the repository already existed), `pending` (it exists in another region, or with another format: nothing was changed), `failed`.
- `imagePath` is `<region>-docker.pkg.dev/<projectId>/<project>`, the prefix every component's image starts with (`<imagePath>/<component>`), for `would-create`, `created` and `unchanged`. It is `null` for `pending` and `failed`.
- `would-create`, `pending` and `failed`: `resources` is empty. `created` and `unchanged`: `resources` lists the repository (with its labels as read; for `created`, the labels it was created with).
- Each `pending` item is `{ "item": "<what>", "reason": "manual", "how": "<text>" }`.
- Always `cost` as above.
