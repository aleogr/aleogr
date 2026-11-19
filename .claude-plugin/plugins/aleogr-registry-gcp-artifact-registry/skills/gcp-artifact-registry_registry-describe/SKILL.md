---
description: Google Cloud Artifact Registry (gcp-artifact-registry) registry describe. Use to learn whether a project's Docker image repository exists in Artifact Registry on Google Cloud, in which region, with which format and labels, its cleanup policy (how many versions it keeps, whether it deletes the rest, dry-run) and who may push to it. Read-only; the other Artifact Registry skills and the project plan call it first.
---

# gcp-artifact-registry_registry-describe

Reads the real state of a project's image repository in Artifact Registry and reports it. The repository's id is the project's name, and it lives in the project's own GCP project. It never creates, changes or deletes anything and has no `mode`.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the repository. |
| `project=<name>` | The aleogr project name, which is also the repository's id. |
| `region=<region>` | The region the repository is declared in, for example `us-central1`. |

Validate before any command, and never ask for anything. A missing argument ends the skill with the result block, `status` `failed`, the one sentence `<argument> is missing.` and no `gcloud` call; an invalid value ends it the same way, with one sentence saying which argument is wrong.

- `projectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`.
- `project` has 1 to 14 characters, only lowercase letters, digits and `-`, starts with a letter and does not end with `-`.
- `region` is a Google Cloud region name: lowercase letters, then one or more `-<letters>` parts, then digits (`us-central1`, `southamerica-east1`). A multi-region (`us`, `europe`) or anything with an uppercase letter is invalid.

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone (its exit code and its text decide the next step). On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Describe the repository in the declared region:

   ```
   gcloud artifacts repositories describe <project> --location=<region> --project=<projectId> --format=json
   ```

   `gcloud` prints lines such as `Encryption: ...`, `Registry URL: ...` and `Repository Size: ...` before the JSON (on its error stream); they are not part of the JSON.

   - Exit non-zero and the text contains both `NOT_FOUND:` and the sentence `Requested entity was not found`: the repository does not exist in `region`. This is a normal answer, not a failure. Go to step 2.
   - Any other non-zero exit is a failure of the check, never "missing", even when its text has `NOT_FOUND` or another word ending in `_NOT_FOUND` (a GCP project or a location that does not exist): the Artifact Registry API not enabled (`SERVICE_DISABLED`), permission denied (Artifact Registry answers `PERMISSION_DENIED` with the words "or it may not exist" when the account may not read the repository: that is still a failure, not "missing"), `gcloud` missing or not signed in. Say exactly `The repository could not be read; nothing was changed. Check that the GCP project <projectId> exists, that the Artifact Registry API is enabled in it, and that the active gcloud account is signed in and may read its repositories.` Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only the sentence above about the failure. Run nothing else and end with `status` `failed`.
   - Success: take the values listed under "Reading the JSON" below and go to step 3. Step 2 is not run.

2. Only when step 1 said the repository does not exist: list the GCP project's repositories in every location, to learn whether one with the same id exists in another region:

   ```
   gcloud artifacts repositories list --location=all --project=<projectId> --format="value(name)"
   ```

   Each printed line that starts with `projects/` is `projects/<projectId>/locations/<location>/repositories/<id>` (ignore any other line, such as `Listing items under project ...`). `otherRegions` is the `<location>` of every line whose `<id>` is exactly `<project>` (not merely starting with it), without `region`. A non-zero exit is a failure: say exactly `The repository could not be read; nothing was changed. Check that the GCP project <projectId> exists, that the Artifact Registry API is enabled in it, and that the active gcloud account is signed in and may read its repositories.` Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only the sentence above about the failure. End with `status` `failed` (`exists` `null`, as for any failure). On success run nothing else and end with `status` `unchanged` and `exists` `false`.

3. Only when the repository exists: read who may push to it, from the repository's IAM policy:

   ```
   gcloud artifacts repositories get-iam-policy <project> --location=<region> --project=<projectId> --format=json
   ```

   `push` is every member of every binding whose `role` is exactly `roles/artifactregistry.writer` and that has no `condition`, in the order printed, without duplicates (`[]` when there is no such binding, or no `bindings` at all). Members of other roles (reader, administrator) are not listed. A non-zero exit is a failure: say exactly `The repository's access could not be read; nothing was changed. Check that the active gcloud account may read the repository's access.` Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only the sentence above about the failure. End with `status` `failed`.

Then answer in a few lines: whether the repository exists and where (and, when it exists only elsewhere, in which region), its format, the cleanup policy (keep how many, deletes the rest or not, dry-run on or off, how many rules), who may push, the image path, and the result block.

## Reading the JSON

From step 1's JSON:

| Output | Source |
|---|---|
| `region` | The `<location>` of `name` (`projects/<projectId>/locations/<location>/repositories/<project>`): the region it was read in. |
| `format` | `format`, as printed (`DOCKER`). |
| `labels` | `labels` (`{}` when absent). |
| `cleanup.keep` | `mostRecentVersions.keepCount`, as a number, of the one entry of `cleanupPolicies` whose `action` is `KEEP` and that has `mostRecentVersions` without `packageNamePrefixes`. `null` when there is no such entry, or more than one. |
| `cleanup.deletesTheRest` | `true` when an entry of `cleanupPolicies` has `action` `DELETE` and a `condition` whose only field is `tagState` with the value `ANY` (any letter case): it matches every version, and a keep rule takes precedence over it. Otherwise `false`. |
| `cleanup.dryRun` | `cleanupPolicyDryRun` (`false` when absent). |
| `cleanup.rules` | The number of entries of `cleanupPolicies`, as a number, whatever they hold (`0` when it is absent). The declared policy has `2`. |
| `imagePath` | `<region>-docker.pkg.dev/<projectId>/<project>` when `format` is `DOCKER`; `null` for any other format. |

`cleanupPolicies` is an object whose keys are the policies' ids; read its values. When it is absent there is no policy: `keep` `null`, `deletesTheRest` `false`, `rules` `0`.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "registry",
  "provider": "gcp-artifact-registry",
  "action": "registry-describe",
  "mode": "plan",
  "status": "unchanged",
  "resources": [
    { "type": "repository", "id": "<projectId>/<region>/<project>", "name": "<project>", "labels": { "aleogr-project": "<project>", "aleogr-environment": "dev" } }
  ],
  "outputs": {
    "exists": true,
    "region": "us-central1",
    "otherRegions": [],
    "format": "DOCKER",
    "labels": { "aleogr-project": "<project>", "aleogr-environment": "dev" },
    "cleanup": { "keep": 5, "deletesTheRest": true, "dryRun": false, "rules": 2 },
    "push": ["serviceAccount:<project>-ci@<projectId>.iam.gserviceaccount.com"],
    "imagePath": "us-central1-docker.pkg.dev/<projectId>/<project>"
  },
  "cost": { "fixed": false, "notes": "read-only" },
  "pending": []
}
```

- `status` is `unchanged` whenever the state was read, whether or not the repository exists. It is `failed` when an argument is invalid or any step failed for a reason other than "does not exist"; then `resources` is empty and `outputs` is `{ "exists": null }`.
- `exists` and `region` speak of the declared region only. Repository does not exist in `region`: `resources` is empty and `outputs` is `{ "exists": false, "region": null, "otherRegions": [<locations from step 2>], "format": null, "labels": {}, "cleanup": { "keep": null, "deletesTheRest": false, "dryRun": false, "rules": 0 }, "push": [], "imagePath": null }`. `otherRegions` is `[]` when no repository of that id exists anywhere.
- Repository exists: `otherRegions` is `[]` (other regions are not read), `labels` in `resources` are the repository's labels.
- `mode` is always `plan`: the skill only reads.
