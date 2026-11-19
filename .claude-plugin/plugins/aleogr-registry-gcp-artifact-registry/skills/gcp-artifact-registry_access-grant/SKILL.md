---
description: Google Cloud Artifact Registry (gcp-artifact-registry) access grant. Use to let a CI service account push images to a project's Docker image repository in Artifact Registry on Google Cloud, by granting it the writer role on that one repository (never on the GCP project), and to check whether it already may push. Idempotent; plan by default. No fixed cost.
---

# gcp-artifact-registry_access-grant

Lets one service account push to the project's image repository (id `<project>`, in `region`): it grants the role `roles/artifactregistry.writer` on that repository, never on the GCP project, and reads the repository's policy before and after. A binding that already exists is left alone; nothing is ever removed. Only push is granted: pull access is not needed, because Cloud Run's own agent pulls from a repository of its own project. It never creates the repository: create it first with `gcp-artifact-registry_repository-create`.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the repository. |
| `project=<name>` | The aleogr project name, which is also the repository's id. |
| `region=<region>` | The region the repository is declared in, for example `us-central1`. |
| `identity=<e-mail>` | The service account that may push, as its e-mail: an account of the project's own GCP project (`<id>@<projectId>.iam.gserviceaccount.com`), for example the CI account `<project>-ci@<projectId>.iam.gserviceaccount.com`. |
| `role=push` | The access granted. `push` is the only one. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check the arguments, and never ask for anything. A missing required argument ends the skill with the result block, `status` `failed`, the one sentence `<argument> is missing.` and no `gcloud` call. Any invalid value ends it the same way, with the one sentence given below for the rule that failed.

- `projectId` has 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`. Otherwise: `projectId is not a GCP project id.`
- `project` has 1 to 14 characters, only lowercase letters, digits and `-`, starts with a letter and does not end with `-`. Otherwise: `project must have 1 to 14 lowercase letters, digits and hyphens, starting with a letter.`
- `region` is a Google Cloud region name: lowercase letters, then one or more `-<letters>` parts, then digits (`us-central1`, `southamerica-east1`). A multi-region (`us`, `europe`) or anything with an uppercase letter is invalid. Otherwise: `region is not a Google Cloud region name (such as us-central1).`
- `identity` is a service account e-mail: `<id>@<project id>.iam.gserviceaccount.com`, where `<id>` has 6 to 30 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-`, and `<project id>` follows the rule of `projectId`. All lowercase, with no prefix such as `serviceAccount:`. A user's or a group's e-mail, or any other text, is invalid. Otherwise: `identity must be a service account e-mail (<id>@<project id>.iam.gserviceaccount.com).`
- `identity` belongs to the project: its `<project id>` is exactly `projectId`. An account of another GCP project, well formed or not, is refused. Otherwise: `identity must be a service account of the project <projectId>.`
- `role` is `push`. `role=pull`: `role=pull is not needed: Cloud Run's own agent pulls from a repository of its own project, so only push is granted.` Any other value: `role must be push.`
- `mode` is `plan` or `apply`. Otherwise: `mode must be plan or apply.`

In the steps, `<member>` is `serviceAccount:<identity>`.

## Steps

Show each command before running it. Run only the commands below, in this order, each one alone (its exit code and its text decide the next step). On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place.

1. Read who may push, from the repository's IAM policy:

   ```
   gcloud artifacts repositories get-iam-policy <project> --location=<region> --project=<projectId> --format=json
   ```

   - Exit non-zero and the text contains both `NOT_FOUND:` and `Requested entity was not found`: the repository does not exist in `region`. Say `The repository <project> does not exist in <region>: create it first with gcp-artifact-registry_repository-create.`, run nothing else and end with `status` `failed`. Never create the repository here. Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only the sentence above about the failure.
   - Any other non-zero exit is a failure of the check: the Artifact Registry API not enabled, permission denied (Artifact Registry answers `PERMISSION_DENIED` with the words "or it may not exist" when the account may not read the repository: that is still this failure), `gcloud` missing or not signed in. Say exactly `The repository's access could not be read; nothing was changed. Check that the GCP project <projectId> exists, that the Artifact Registry API is enabled in it, and that the active gcloud account is signed in and may read its repositories.` Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only the sentence above about the failure. Run nothing else and end with `status` `failed`.
   - Success: `granted` is `true` when a binding whose `role` is exactly `roles/artifactregistry.writer` and that has no `condition` lists `<member>` in its `members`; otherwise `false` (also when there are no `bindings` at all). A binding of another role (reader, administrator) does not count.

2. `granted` true: run nothing else and end with `status` `unchanged` (in `plan` and in `apply`). `granted` false: in `plan`, say that `<identity>` would get the writer role on the repository `<project>` and end with `status` `would-update`. In `apply`, continue.

3. `apply`: grant the writer role on the repository:

   ```
   gcloud artifacts repositories add-iam-policy-binding <project> --location=<region> --project=<projectId> --member="<member>" --role="roles/artifactregistry.writer" --condition=None --quiet
   ```

   - Never grant it on the GCP project: never run `gcloud projects add-iam-policy-binding`.
   - A binding made right after the account is created can be refused for a while (seconds to minutes) while the new account is not yet visible: a non-zero exit whose text says the account does not exist (`does not exist`, or `NOT_FOUND`) is the refusal that waiting cures, and the binding is polled: wait 30 seconds, then run the same command again, alone; while it is refused that same way, wait and try again; at most 10 tries in all, the first one included (so at most 9 waits, about 5 minutes). Any other non-zero exit, on any try, ends the poll at once, with no further wait and no further try. The tenth refusal stops the skill.
   - The wait is the command `sleep 30`, the one command of this skill that is not `gcloud`. Show it, then run it with the Bash tool in the background (`run_in_background`: Claude Code refuses a `sleep` in the foreground), run nothing else while it runs, and when its completion notice arrives go on with the next try in this same run. A pending wait is part of the run: while one is pending, never end the answer, never give the result block, and never tell the owner to run anything.
   - A failure (not polled, or the tenth refusal) stops with `failed` and exactly the sentence `The push access could not be granted; nothing was changed. Check that the account <identity> exists and that the active gcloud account may change the repository's access.` Never explain which text decided this, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only that sentence about the failure. Run nothing else.

4. Read it back with step 1's command, alone. The binding was added in step 3, so the status is `updated` whatever this read shows. When the command succeeds and `granted` is true, nothing is pending. A non-zero exit, or `granted` still false, adds one `pending` item whose `item` is `push access of <identity> read back`, `reason` `manual`, and `how` is `/aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_access-grant projectId=<projectId> project=<project> region=<region> identity=<identity> role=push mode=plan`, and the answer says what could not be confirmed.

Then answer in a few lines: the repository, the account, whether it may push (before and, after a change, after), what was done, and the result block.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "registry",
  "provider": "gcp-artifact-registry",
  "action": "access-grant",
  "mode": "apply",
  "status": "updated",
  "resources": [
    { "type": "repository-binding", "id": "<projectId>/<region>/<project>", "name": "<project>", "member": "serviceAccount:<identity>", "role": "roles/artifactregistry.writer" }
  ],
  "outputs": { "granted": true },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `unchanged` (the account already may push), `would-update` (plan, it may not), `updated` (apply granted it), `failed` (an invalid argument, a repository that does not exist, a read that failed, or a grant that failed).
- `granted` is from the last read (step 4's when it succeeded, else step 1's). `failed`: `resources` is empty and `outputs` is `{ "granted": null }`.
- `unchanged` and `updated`: `resources` lists the binding as above. `would-update`: `resources` is empty.
- Each `pending` item is `{ "item": "<what>", "reason": "manual", "how": "<text>" }`.
- Always `cost` as above.
