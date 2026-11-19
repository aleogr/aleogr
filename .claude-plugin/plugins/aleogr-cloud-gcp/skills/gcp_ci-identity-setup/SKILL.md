---
description: Google Cloud (GCP) CI identity setup. Use to create, in the GCP project of an aleogr project and environment, the keyless identity through which one GitHub repository's CI reaches that project - a service account `<project>-ci`, a workload identity federation pool `github` and provider `github` that accept only tokens of the declared repository (by name and by GitHub's numeric ids) on its default branch, and the binding that lets those tokens act as the account. Updates a provider whose condition differs. Grants the account no project role. Idempotent; plan by default.
---

# gcp_ci-identity-setup

Sets up the identity GitHub Actions of one repository use to reach one GCP project, with no key: a service account (`<project>-ci`), a workload identity federation pool (`github`) with an OIDC provider (`github`) whose condition accepts only tokens of the declared repository, checked by its name, its numeric id and its owner's numeric id (a repository deleted and recreated under the same name does not pass), on the declared branch, and the binding that lets those tokens act as the account. It grants the account no role on the project: what the account may do is granted elsewhere, on each resource. It never creates a GCP project, never creates a service account key, and writes nothing to GitHub. There is no cost: service accounts and workload identity federation are free.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`. If one required argument is missing, ask for it.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project of the project and environment (from `gcp_environment-describe`). |
| `project=<name>` | The aleogr project name; the account is `<project>-ci`. |
| `repository=<owner>/<name>` | The GitHub repository whose CI may act as the account. |
| `repositoryId=<digits>` | GitHub's numeric id of that repository (`id` of `github_repo-describe`). |
| `ownerId=<digits>` | GitHub's numeric id of its owner (`ownerId` of `github_repo-describe`). |
| `branch=<name>` | The only branch whose runs are accepted: the repository's default branch. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check the arguments. Any failure ends the skill with the result block, `status` `failed`, one sentence saying which argument broke which rule, and no `gcloud` call.

- `projectId` matches `^[a-z][a-z0-9-]{4,28}[a-z0-9]$` (6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter, not ending with `-`).
- `project` has 3 to 14 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-` (3 at least, because a service account id, `<project>-ci`, has 6 to 30 characters).
- `repository` is `<owner>/<name>` with exactly one `/`: `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, not starting or ending with `-`; `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `repositoryId` and `ownerId` are each 1 to 20 digits (`0-9`) and nothing else.
- `branch` has 1 to 255 characters of `A-Z`, `a-z`, `0-9`, `.`, `_`, `-` and `/`, does not start or end with `/` and does not contain `..` (so no space and no quote can reach the condition).
- `mode` is `plan` or `apply`.

## Names

- `<account>` is `<project>-ci@<projectId>.iam.gserviceaccount.com`.
- `<number>` is the project number, read in step 1.
- `<provider name>` is `projects/<number>/locations/global/workloadIdentityPools/github/providers/github`.
- `<member>` is `principalSet://iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/github/attribute.repository/<repository>`.
- `<condition>` is exactly, with the arguments in place and nothing added or removed:

  ```
  assertion.repository=='<repository>' && assertion.repository_id=='<repositoryId>' && assertion.repository_owner_id=='<ownerId>' && assertion.ref=='refs/heads/<branch>'
  ```

- `<mapping>` is exactly `google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref`.

## The parts

Four parts, in this order. A part is read only when the part it depends on exists; a part whose dependency is missing is missing too, without a command.

| # | Part | Exists and as declared when | Depends on |
|---|---|---|---|
| 1 | `account` | the service account exists | - |
| 2 | `pool` | the pool exists and its state is `ACTIVE` | - |
| 3 | `provider` | the provider exists, its state is `ACTIVE`, and its attribute condition is exactly `<condition>` | `pool` |
| 4 | `binding` | the account's policy has a binding of `roles/iam.workloadIdentityUser` whose members include `<member>` | `account` |

`condition` (an output) is `missing` when the provider does not exist, `as-declared` when its condition is exactly `<condition>`, and `differs` otherwise (another repository, another id, another branch, a missing or extra clause: anything but the exact text; spaces at the ends of the line do not count).

A pool or provider whose state is not `ACTIVE` was deleted, and stays reserved for 30 days: creating it again would fail. No command here restores it. In `plan` and in `apply`, before any change, end with `failed` and one sentence saying which one was deleted and that the owner restores it by hand (`gcloud iam workload-identity-pools undelete github --project=<projectId> --location=global`, or `gcloud iam workload-identity-pools providers undelete github --project=<projectId> --location=global --workload-identity-pool=github`), then runs this skill again.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. Every value with a comma, a space, a quote or `&` is double-quoted, as below.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

1. Read the project number (both modes):

   ```
   gcloud projects describe <projectId> --format="value(projectNumber)"
   ```

   Exit 0 with a number: that is `<number>`. A non-zero exit or an empty output stops with `failed`: say in one sentence that the GCP project could not be read (it must exist, created by `gcp_environment-create`, and this account must be able to read it). Never create a project.

2. Read the parts, each command alone, in this order:

   ```
   gcloud iam service-accounts describe <account> --project=<projectId> --format="value(email)"
   gcloud iam workload-identity-pools describe github --project=<projectId> --location=global --format="value(state)"
   gcloud iam workload-identity-pools providers describe github --project=<projectId> --location=global --workload-identity-pool=github --format="value(state,attributeCondition)"
   gcloud iam service-accounts get-iam-policy <account> --project=<projectId> --format=json
   ```

   - The provider is read only when the pool exists; the policy only when the account exists.
   - Exit 0: the part exists; read it as the table above says. The provider's output is its state, a tab, then its condition.
   - A non-zero exit whose text contains `NOT_FOUND` (or `404`, or says the resource does not exist): the part is missing.
   - Any other non-zero exit (permission denied, an API not enabled, a network error, anything else) is a failure of the read: stop with `failed` and one sentence of cause, without raw error text. Never treat it as missing.

3. `plan` ends here, changing nothing. Say for each part whether it exists as declared, is missing, or (the provider) differs, and end with `would-create` (some part is missing), `would-update` (nothing is missing and the provider's condition differs), or `unchanged` (nothing to do).

4. `apply`: run the command of each part that is missing, in the order account → pool → provider → binding, and the update of a provider whose condition differs. A part that exists as declared is skipped.

   ```
   gcloud iam service-accounts create <project>-ci --project=<projectId> --display-name="<project> CI" --quiet
   gcloud iam workload-identity-pools create github --project=<projectId> --location=global --display-name="GitHub" --quiet
   gcloud iam workload-identity-pools providers create-oidc github --project=<projectId> --location=global --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="<mapping>" --attribute-condition="<condition>" --quiet
   gcloud iam workload-identity-pools providers update-oidc github --project=<projectId> --location=global --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="<mapping>" --attribute-condition="<condition>" --quiet
   gcloud iam service-accounts add-iam-policy-binding <account> --project=<projectId> --member="<member>" --role="roles/iam.workloadIdentityUser" --quiet
   ```

   - `create-oidc` is for a missing provider; `update-oidc` is for a provider whose condition differs, always with the issuer, the mapping and the whole `<condition>`, never a part of it. A provider is never deleted.
   - The binding made right after the account is created can be refused for some seconds while the new account is not yet visible: a non-zero exit of the binding whose text says the account does not exist (`does not exist` or `NOT_FOUND`), or is `PERMISSION_DENIED` (the answer the `gcloud` reference gives for an account that does not exist), is retried once, after waiting about one minute. Any other non-zero exit of the binding is not retried. A second failure stops the skill.
   - A failure of any other change command stops the skill at once, with no retry and no later command.
   - A stop after a change: what was made stays (nothing is removed). The status says what this run did (`created` or `updated`, below), and each part left goes to `pending` as an item `{ "item": "<part>", "reason": "<one sentence, no raw error text>", "how": "<this same invocation with mode=apply>" }`. A stop at the first change command of the run, with nothing changed: `failed`, one sentence saying which part failed, without raw error text.
   - The account gets no project role here: never run `gcloud projects add-iam-policy-binding`.

5. Verify: when a change command ran, run the reads of step 2 again (all four, now that their dependencies exist; not the project number). Each part must exist as declared. A part still missing or differing goes to `pending`, as above, with its `how`. When no change command ran, the reads of step 2 already are the verification: do not repeat them.

6. Status of `apply`: `created` (something was created, the binding included, whether or not the provider was also updated), `updated` (only the provider's condition was updated), `unchanged` (no change command ran and nothing is missing or differs), `failed`. `created` and `updated` keep their name when `pending` has items: something was changed.

Then answer in a few lines: each part's state, the condition (as declared, missing, or differs), what this run changed, and, when every part exists as declared, the three CI variables with their values (they are identifiers, not secrets; another skill writes them to the repository). The answer prints no identifier other than the project id, `<account>` and `<provider name>`.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "ci-identity-setup",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "service-account", "id": "<project>-ci", "name": "<project>-ci", "labels": {} },
    { "type": "workload-identity-pool", "id": "github", "name": "github", "labels": {} },
    { "type": "workload-identity-provider", "id": "github/github", "name": "github", "labels": {} }
  ],
  "outputs": {
    "account": "<project>-ci@<projectId>.iam.gserviceaccount.com",
    "provider": "projects/<number>/locations/global/workloadIdentityPools/github/providers/github",
    "condition": "as-declared",
    "ciVariables": {
      "GCP_PROJECT_ID": "<projectId>",
      "GCP_WIF_PROVIDER": "projects/<number>/locations/global/workloadIdentityPools/github/providers/github",
      "GCP_CI_ACCOUNT": "<project>-ci@<projectId>.iam.gserviceaccount.com"
    }
  },
  "cost": { "fixed": false, "notes": "service accounts and workload identity federation are free" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-create`, `would-update` (plan), `created`, `updated`, `unchanged`, `failed`.
- `resources` lists only the parts that exist at the end (as of the last read): the account, the pool and the provider, with the ids above.
- `outputs.account` and `outputs.provider` are the names above, filled in once step 1 has read the project number, whether or not the parts exist yet. `outputs.condition` is the provider's condition as of the last read (`as-declared`, `differs`, `missing`).
- `outputs.ciVariables` is set only when every part exists as declared at the end (in `plan` too); otherwise it is `null`.
- `failed` from validation or from step 1: `resources` is empty and `outputs` is `{ "account": null, "provider": null, "condition": null, "ciVariables": null }`. `failed` from a read of step 2 or a deleted pool or provider: `resources` lists what was read as existing, `outputs.account` and `outputs.provider` are set, `condition` is what was read (`null` if the provider was not read), and `ciVariables` is `null`.
- `pending` holds one item per part left after a stop or a failed verification in `apply`; it is empty otherwise.
