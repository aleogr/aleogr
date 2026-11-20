---
description: Google Cloud (GCP) CI identity setup. Use to create, in the GCP project of an aleogr project and environment, the keyless identity through which one GitHub repository's CI reaches that project - a service account `<project>-ci`, a workload identity federation pool `github` and provider `github` that accept only tokens of the declared repository (by name and by GitHub's numeric ids) on its default branch from a job of the declared reusable deploy workflow, and the binding that lets those tokens act as the account. Updates in place a provider whose condition, issuer or mapping differs (one made before the workflow clause existed included); refuses a deleted or disabled pool or provider, and a pool that holds another provider. Grants the account no project role. Idempotent; plan by default.
---

# gcp_ci-identity-setup

Sets up the identity GitHub Actions of one repository use to reach one GCP project, with no key: a service account (`<project>-ci`), a workload identity federation pool (`github`) with an OIDC provider (`github`) whose condition accepts only tokens of the declared repository, checked by its name, its numeric id and its owner's numeric id (a repository deleted and recreated under the same name does not pass), on the declared branch, and only in a job that runs the declared reusable workflow (another workflow of the same repository and branch does not pass), and the binding that lets those tokens act as the account. It grants the account no role on the project: what the account may do is granted elsewhere, on each resource. It never creates a GCP project, never creates a service account key, and writes nothing to GitHub. There is no cost: service accounts and workload identity federation are free.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project of the project and environment (from `gcp_environment-describe`). |
| `project=<name>` | The aleogr project name; the account is `<project>-ci`. |
| `repository=<owner>/<name>` | The GitHub repository whose CI may act as the account. |
| `repositoryId=<digits>` | GitHub's numeric id of that repository (`id` of `github_repo-describe`). |
| `ownerId=<digits>` | GitHub's numeric id of its owner (`ownerId` of `github_repo-describe`). |
| `branch=<name>` | The only branch whose runs are accepted: the repository's default branch. |
| `workflow=<owner>/<name>/.github/workflows/<file>.yml` | The reusable workflow whose jobs alone may act as the account: the deploy workflow, without `@` and what follows it. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

## Validate first

Before any command, check the arguments. A missing required argument, or any other failure, ends the skill with the result block, `status` `failed`, one sentence saying which argument is missing or which rule it broke, and no `gcloud` call. Never ask for a missing argument.

- `projectId` matches `^[a-z][a-z0-9-]{4,28}[a-z0-9]$` (6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter, not ending with `-`).
- `project` has 3 to 14 characters of `a-z`, `0-9` and `-`, starts with a letter and does not end with `-` (3 at least, because a service account id, `<project>-ci`, has 6 to 30 characters).
- `repository` is `<owner>/<name>` with exactly one `/`: `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, not starting or ending with `-`; `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `repositoryId` and `ownerId` each match `^[1-9][0-9]{0,19}$` (1 to 20 digits, not starting with `0`).
- `branch` has 1 to 255 characters of `A-Z`, `a-z`, `0-9`, `.`, `_`, `-` and `/`, does not start or end with `/` and does not contain `..` (so no space and no quote can reach the condition).
- `workflow` is `<owner>/<name>/.github/workflows/<file>.yml`: `<owner>` and `<name>` follow the rules of `repository` above, `<file>` has 1 to 60 characters of `a-z`, `0-9`, `-` and `_`, and nothing else is allowed (no `@`, no ref, no space, no quote).
- `mode` is `plan` or `apply`.

## Names

- `<account>` is `<project>-ci@<projectId>.iam.gserviceaccount.com`.
- `<number>` is the project number, read in step 1.
- `<provider name>` is `projects/<number>/locations/global/workloadIdentityPools/github/providers/github`.
- `<member>` is `principalSet://iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/github/attribute.repository/<repository>`.
- `<condition>` is exactly, with the arguments in place and nothing added or removed:

  ```
  assertion.repository=='<repository>' && assertion.repository_id=='<repositoryId>' && assertion.repository_owner_id=='<ownerId>' && assertion.ref=='refs/heads/<branch>' && assertion.job_workflow_ref.startsWith('<workflow>@')
  ```

  The last clause accepts only a token of a job that runs the reusable workflow `<workflow>`: GitHub sets `job_workflow_ref` to `<workflow>@<ref>`, and the clause stops at `@` because the form of `<ref>` for a workflow pinned by commit is not documented.
- `<mapping>` is exactly `google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.job_workflow_ref=assertion.job_workflow_ref`: six keys, `google.subject` → `assertion.sub`, `attribute.repository` → `assertion.repository`, `attribute.ref` → `assertion.ref`, `attribute.repository_id` → `assertion.repository_id`, `attribute.repository_owner_id` → `assertion.repository_owner_id`, `attribute.job_workflow_ref` → `assertion.job_workflow_ref` (every field the condition tests has its key).
- `<issuer>` is exactly `https://token.actions.githubusercontent.com`.

## The parts

Four parts, in this order. A part is read only when the part it depends on exists; a part whose dependency is missing is missing too, without a command.

| # | Part | Exists and as declared when | Depends on |
|---|---|---|---|
| 1 | `account` | the service account exists | - |
| 2 | `pool` | the pool exists, its state is `ACTIVE`, it is not disabled, and its only provider is `github` | - |
| 3 | `provider` | the provider exists, its state is `ACTIVE`, it is not disabled, and its attribute condition, its issuer and its attribute mapping are exactly the declared ones | `pool` |
| 4 | `binding` | the account's policy has a binding of `roles/iam.workloadIdentityUser` whose members include `<member>` | `account` |

The provider "differs" when any of these three is not exactly the declared value: `attributeCondition` is not exactly `<condition>` (another repository, another id, another branch, a missing or extra clause: anything but the exact text; spaces at the ends of the line do not count); `oidc.issuerUri` is not exactly `<issuer>`; `attributeMapping`, compared key by key, does not have exactly the six keys of `<mapping>` with their values (a missing key, an extra key or another value). A provider made before the argument `workflow` existed (its condition without the last clause, its mapping of three keys) differs, and is updated in place like any other. `condition` (an output) is `missing` when the provider does not exist, `as-declared` when none of the three differs, and `differs` otherwise.

These end the skill with `failed`, in `plan` and in `apply`, after the reads of step 2 and before any change, with one sentence each; no command here changes them, and the owner runs this skill again once they are fixed:

- A pool or provider whose state is not `ACTIVE` was deleted, and stays reserved for 30 days: creating it again would fail. The sentence says which one was deleted and that the owner restores it by hand (`gcloud iam workload-identity-pools undelete github --project=<projectId> --location=global`, or `gcloud iam workload-identity-pools providers undelete github --project=<projectId> --location=global --workload-identity-pool=github`).
- A pool or provider that is disabled (`disabled` true, whatever its state) accepts no token. The sentence says which one is disabled and that the owner enables it by hand, in the Google Cloud console (IAM, Workload Identity Federation).
- The pool holds a provider other than `github`. The binding's member matches `attribute.repository` of a token from any provider of the pool, so another provider would let tokens in that do not pass `<condition>`. The sentence says that the pool `github` has another provider, names it by its id only (the last part of its name), and says the owner removes it by hand. It names no other resource.

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
   gcloud iam workload-identity-pools describe github --project=<projectId> --location=global --format=json
   gcloud iam workload-identity-pools providers list --workload-identity-pool=github --project=<projectId> --location=global --format="value(name)"
   gcloud iam workload-identity-pools providers describe github --project=<projectId> --location=global --workload-identity-pool=github --format=json
   gcloud iam service-accounts get-iam-policy <account> --project=<projectId> --format=json
   ```

   - The providers list and the provider are read only when the pool exists; the policy only when the account exists.
   - Exit 0: the part exists; read it as the table above says. The pool and the provider are read as JSON (the mapping is a map): the pool's `state` and `disabled`; the provider's `state`, `disabled`, `attributeCondition`, `oidc.issuerUri` and `attributeMapping`. `disabled` absent means false. The list prints one provider name per line (`projects/<number>/locations/global/workloadIdentityPools/github/providers/<id>`); soft-deleted providers are not listed. From the policy, `otherMembers` is the number of members of `roles/iam.workloadIdentityUser` other than `<member>`.
   - A non-zero exit whose text contains `NOT_FOUND`, `was not found` or `does not exist`: the part is missing. Both are needed: a non-zero exit without that text is not "missing".
   - Any other non-zero exit (permission denied, an API not enabled, a network error, anything else) is a failure of the read: stop with `failed` and one sentence of cause, without raw error text. Never treat it as missing.

   Then, before anything else, apply the cases of `failed` listed under "The parts" (deleted, disabled, another provider in the pool).

3. `plan` ends here, changing nothing. Say for each part whether it exists as declared, is missing, or (the provider) differs, and end with `would-create` (some part is missing), `would-update` (nothing is missing and the provider differs), or `unchanged` (nothing to do).

4. `apply`: run the command of each part that is missing, in the order account → pool → provider → binding, and the update of a provider that differs. A part that exists as declared is skipped.

   ```
   gcloud iam service-accounts create <project>-ci --project=<projectId> --display-name="<project> CI" --quiet
   gcloud iam workload-identity-pools create github --project=<projectId> --location=global --display-name="GitHub" --quiet
   gcloud iam workload-identity-pools providers create-oidc github --project=<projectId> --location=global --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="<mapping>" --attribute-condition="<condition>" --quiet
   gcloud iam workload-identity-pools providers update-oidc github --project=<projectId> --location=global --workload-identity-pool=github --issuer-uri="https://token.actions.githubusercontent.com" --attribute-mapping="<mapping>" --attribute-condition="<condition>" --quiet
   gcloud iam service-accounts add-iam-policy-binding <account> --project=<projectId> --member="<member>" --role="roles/iam.workloadIdentityUser" --quiet
   ```

   - `create-oidc` is for a missing provider; `update-oidc` is for a provider that differs (its condition, its issuer or its mapping), always with `<issuer>`, the whole `<mapping>` and the whole `<condition>`, never a part of it. A provider that exists is only ever updated, once per run: never deleted, never created again, and the update changes nothing else (not the account, the pool or the binding).
   - The binding made right after this same run created the account can be refused for a while (seconds to minutes) while the new account is not yet visible: only then, a non-zero exit of the binding whose text says the account does not exist (`does not exist` or `NOT_FOUND`), or is `PERMISSION_DENIED` (the answer the `gcloud` reference gives for an account that does not exist), is the refusal that waiting cures, and the binding is polled: wait 30 seconds, then run the same binding command again, alone; while it is refused that same way, wait and try again; at most 10 tries in all, the first one included (so at most 9 waits, about 5 minutes). `PERMISSION_DENIED` is polled too in this one case, so a real permission error right after this run created the account waits up to 5 minutes and then ends as the tenth refusal does (`created`, with the binding pending). A binding that was not made right after this run created the account is never polled. Any other non-zero exit of the binding, on any try, ends the poll at once, with no further wait and no further try. The tenth refusal stops the skill. Never explain which text decided a wait or the end of the poll, and repeat no word of `gcloud`'s answer (not even its status words, codes or reasons): the answer says only that the binding was refused, and after how many tries.
   - The wait is the command `sleep 30`, the one command of this skill that is not `gcloud`. Show it, then run it with the Bash tool in the background (`run_in_background`: Claude Code refuses a `sleep` in the foreground), run nothing else while it runs, and when its completion notice arrives go on with the next try in this same run. A pending wait is part of the run: while one is pending, never end the answer, never give the result block, and never tell the owner to run anything. A wait that cannot be run, or whose completion notice never comes, counts as the refusal that ends the poll: the skill ends as after the tenth refusal, never loops and never leaves the answer unfinished.
   - A failure of any other change command stops the skill at once, with no retry and no later command.
   - A stop after a change: what was made stays (nothing is removed). The status says what this run did (`created` or `updated`, below), and each part left goes to `pending` as an item `{ "item": "<part>", "reason": "<one sentence, no raw error text>", "how": "<this same invocation with mode=apply>" }`. A stop at the first change command of the run, with nothing changed: `failed`, one sentence saying which part failed, without raw error text.
   - The account gets no project role here: never run `gcloud projects add-iam-policy-binding`.
   - Other members of `roles/iam.workloadIdentityUser` on the account are never removed: no `remove-iam-policy-binding`, no `set-iam-policy`.

5. Verify: when a change command ran, run the reads of step 2 again (all of them, now that their dependencies exist; not the project number). Each part must exist as declared. A part still missing or differing goes to `pending`, as above, with its `how`. When no change command ran, the reads of step 2 already are the verification: do not repeat them.

6. Status of `apply`: `created` (something was created, the binding included, whether or not the provider was also updated), `updated` (only the provider was updated), `unchanged` (no change command ran and nothing is missing or differs), `failed`. `created` and `updated` keep their name when `pending` has items: something was changed.

Then answer in a few lines: each part's state, the condition (as declared, missing, or differs), what this run changed, when `otherMembers` is not 0, one sentence saying that that number of other members may also act as the account and that this skill does not remove them (their number only, never their text), and, when every part exists as declared, the three CI variables with their values (they are identifiers, not secrets; another skill writes them to the repository). The answer prints no identifier other than the project id, `<account>` and `<provider name>`.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

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
    "otherMembers": 0,
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
- `outputs.account` and `outputs.provider` are the names above, filled in once step 1 has read the project number, whether or not the parts exist yet. `outputs.condition` is the provider's state as of the last read (`as-declared`, `differs`, `missing`). `outputs.otherMembers` is the number of other members of `roles/iam.workloadIdentityUser` on the account, as of the last read of the policy (`0` when the policy was read and has none, `null` when it was not read).
- `outputs.ciVariables` is set only when every part exists as declared at the end (in `plan` too); otherwise it is `null`.
- `failed` from validation or from step 1: `resources` is empty and `outputs` is `{ "account": null, "provider": null, "condition": null, "otherMembers": null, "ciVariables": null }`. `failed` from a read of step 2 or from a deleted, disabled or shared pool or provider: `resources` lists what was read as existing, `outputs.account` and `outputs.provider` are set, `condition` and `otherMembers` are what was read (`null` if not read), and `ciVariables` is `null`.
- `pending` holds one item per part left after a stop or a failed verification in `apply`; it is empty otherwise.
