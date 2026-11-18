---
description: GitHub branch protect, with the gh CLI. Use to protect the default branch of a GitHub repository with the repository ruleset `main` (no deletion, no force push, changes through a pull request, 0 approvals), creating or updating it from the plugin's ruleset-main.json, then verify it. Idempotent; plan by default; reports pending when the GitHub plan does not allow rulesets on the repository. Never touches a ruleset with another name.
---

# github_branch-protect

Protects the default branch of a GitHub repository with the `gh` CLI: the repository ruleset named `main` is made equal to `${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json`. It creates the ruleset when there is none, updates it when it differs, and verifies it. When the GitHub plan does not allow rulesets on the repository (a private repository on the free plan), it changes nothing and reports `pending`. A ruleset with any other name is never changed or deleted.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` creates or updates the ruleset `main`. |

`owner` and `name` are required: a missing `owner` or `name` ends with the result block with `status` `failed` and one sentence saying which is missing, with no command (do not ask for it). Validate before any command; a value that breaks a rule ends with the result block with `status` `failed`, one sentence saying which rule failed, and no command:

- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `mode`, when given, is `plan` or `apply`.

## Steps

Show each command before running it. Run only the commands below, in this order, each step's command at most once (the read of step 3 runs again as the verification of step 6): no `gh auth status`, no `gh repo view`, no other `gh` command, no `--method DELETE`, no `--method PATCH`, no retry. Never print the account name or the token. The body of a write is always the file, passed as `--input "${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json"` (with the quotes), never inline.

1. Read the repository:

   ```
   gh api repos/<owner>/<name>
   ```

   Read the exit code and the output, then take the first case that applies:

   - `gh` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `gh` must be installed. Run nothing else.
   - The output names authentication (`gh auth login`, not logged in, bad credentials, HTTP 401): `failed`. Say in one sentence that `gh` is not logged in and that the fix is `gh auth login`. Run nothing else.
   - Non-zero exit and the output contains `HTTP 404`: the repository does not exist (or this account cannot see it). Here this is `failed`: there is nothing to protect. Say so in one sentence, pointing to `github_repo-create`. Run nothing else.
   - Any other non-zero exit (HTTP 403, 5xx, network error, anything else): `failed`. The state is unknown: never report it as "does not exist". Say the cause in one sentence, with no raw error text. Run nothing else.
   - Exit 0: the repository exists. Continue.

2. Read its rulesets:

   ```
   gh api repos/<owner>/<name>/rulesets
   ```

   - Exit 0 and the output is a JSON list of rulesets (it may be `[]`): look for rulesets whose `name` is exactly `main` (case-sensitive: `Main` or `main-2` is not `main`). Exactly one: take its `id` and go to step 3. None: go to step 4. More than one: `failed` (say in one sentence that two rulesets are named `main`); run nothing else.
   - Exit 0 but the output is not a JSON list: `failed`. Say so in one sentence; run nothing else.
   - Non-zero exit and the output contains `HTTP 403` and a message containing `Upgrade`: the plan does not allow rulesets on this repository. End with `status` `pending`, in `plan` and in `apply`: write nothing, run nothing else. Say in one sentence that branch protection needs a paid plan or a public repository.
   - Any other non-zero exit (for example `HTTP 403` without `Upgrade`, such as missing admin rights): `failed`. Say the cause in one sentence, with no raw error text. This is never `pending`. Run nothing else.

   `otherRulesets` is the sorted list of the names of the other rulesets in the list (every ruleset whose `name` is not exactly `main`). They are only reported, never read, changed or deleted. When it is not empty, the answer says in one sentence that these rulesets exist and were left as they are.

3. Only when step 2 listed a ruleset named `main`, read it with its `id`:

   ```
   gh api repos/<owner>/<name>/rulesets/<id>
   ```

   A non-zero exit is `failed` (one sentence, no raw error text); run nothing else. On exit 0, read `${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json` with the Read tool (not a shell command); if it cannot be read or is not valid JSON, `failed`. Then compare by this rule, the same one the other aleogr-repo-github skills use:

   - Compare only the keys the file has: `target`, `enforcement`, `bypass_actors`, `conditions` and `rules`, and inside them only the keys the file has. Keys the read ruleset has and the file does not (`id`, `source`, `source_type`, `created_at`, `updated_at`, `_links`, `current_user_can_bypass`, `node_id`, extra rule parameters such as `required_reviewers` or `require_extra_approval_for_unattributed_changes`, and any other) are ignored.
   - Scalars and objects are compared by deep equality.
   - These lists are compared as sets, order ignored: `rules`, `allowed_merge_methods`, `conditions.ref_name.include`, `conditions.ref_name.exclude` and `bypass_actors`. There is no other list in the file.
   - `rules` is matched by `type`: it must have exactly the file's rule types (`deletion`, `non_fast_forward`, `pull_request`), each once, no more and no fewer; each rule is then compared on the keys the file gives it (for `pull_request`, every key of its `parameters` in the file).
   - `bypass_actors` absent, `null` and `[]` all count as "none", and are equal to each other.

   Every compared key equal: `status` `unchanged`, in `plan` and in `apply`; run nothing else. Otherwise note each difference (a missing or extra rule type, or a key with the value found and the value of the file) and go to step 4.

4. Decide.

   - `plan`, no ruleset `main`: `status` `would-create`. Show the `POST` command of step 5 without running it. Run nothing else.
   - `plan`, ruleset `main` differs: `status` `would-update`. List what differs, and show the `PUT` command of step 5 without running it. Run nothing else.
   - `apply`: go to step 5.

5. Write the ruleset from the file. Before the first write, read `${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json` with the Read tool if step 3 did not; if it cannot be read or is not valid JSON, `failed` and write nothing.

   No ruleset `main`, create it:

   ```
   gh api --method POST repos/<owner>/<name>/rulesets --input "${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json"
   ```

   Ruleset `main` differs, update it with its `id` (only that `id`):

   ```
   gh api --method PUT repos/<owner>/<name>/rulesets/<id> --input "${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json"
   ```

   - Non-zero exit and the output contains `HTTP 403` and a message containing `Upgrade`: `pending` exactly as in step 2. Nothing was changed; run nothing else.
   - Any other non-zero exit: `failed`. Nothing was changed. Say the cause in one sentence, with no raw error text. Run nothing else.
   - Exit 0: the status is `created` (POST) or `updated` (PUT), whatever happens in step 6. For POST, take the new ruleset's `id` from the answer. Go to step 6.

6. Verify, once, with the `id` of step 3 (PUT) or of the POST answer:

   ```
   gh api repos/<owner>/<name>/rulesets/<id>
   ```

   The status stays `created` or `updated`. Compare with the file by the rule of step 3. Anything that does not hold is said in one sentence and becomes one item in `pending`:

   - The POST answer has no `id`, or the read fails: one item `verify` whose `how` is `/aleogr-repo-github:github_repo-describe owner=<owner> name=<name>`.
   - The read ruleset differs from the file: one item `branch protection differs` whose `how` is `/aleogr-repo-github:github_branch-protect owner=<owner> name=<name> mode=apply`.

Then answer in a few lines: what was done (or would be done), what differs when the ruleset was or would be updated, the other rulesets left as they are (when there are any), anything left in `pending`, and the result block.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "branch-protect",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "ruleset", "id": "123", "name": "main" }
  ],
  "outputs": {
    "rulesetId": 123,
    "rules": ["deletion", "non_fast_forward", "pull_request"],
    "requiredApprovals": 0,
    "otherRulesets": []
  },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of:
  - `would-create`: `plan`, no ruleset `main`.
  - `would-update`: `plan`, the ruleset `main` differs from the file.
  - `created`: `apply`, the POST of step 5 succeeded in this run, whatever happened after it.
  - `updated`: `apply`, the PUT of step 5 succeeded in this run, whatever happened after it.
  - `unchanged`: the ruleset `main` already matches the file (`plan` or `apply`); nothing was done.
  - `pending`: the plan does not allow rulesets on this repository (the read of step 2, or the write of step 5, refused with `HTTP 403` and `Upgrade`), in `plan` or `apply`. Nothing was changed.
  - `failed`: an argument missing or broke a rule, `gh` missing or not logged in, the repository does not exist or its read refused, the rulesets read refused for any other reason or not a JSON list, two rulesets named `main`, the read of step 3 refused, `ruleset-main.json` unreadable, or the write refused for any other reason. Nothing was changed.
- `pending` items are `{ "item": "<what>", "reason": "<reason>", "how": "<text>" }`:
  - With the status `pending`: exactly one item `{ "item": "branch protection needs a paid plan or a public repository", "reason": "plan-limit", "how": "make <owner>/<name> public (/aleogr-repo-github:github_repo-configure owner=<owner> name=<name> visibility=public confirmVisibility=public mode=apply) or move the owner to a paid plan, then run /aleogr-repo-github:github_branch-protect owner=<owner> name=<name> mode=apply" }`.
  - With `created` or `updated`: the item of step 6 (`verify` or `branch protection differs`), with `"reason": "manual"`, when there is one; `[]` otherwise. `created` or `updated` with a non-empty `pending` is allowed.
  - With every other status: `[]`.
- `outputs.rulesetId` is the `id` of the ruleset `main` (a number) and `resources` is `[{ "type": "ruleset", "id": "<id>", "name": "main" }]` (the `id` as a string) whenever a ruleset `main` exists at the end of the run and its `id` is known; otherwise `rulesetId` is `null` and `resources` is `[]`.
- `outputs.rules` is the sorted list of rule types and `outputs.requiredApprovals` is the `pull_request` rule's `required_approving_review_count` (`null` when there is no `pull_request` rule). Values come only from the commands' output or the file. The shape for each ending:
  - `unchanged`, `would-update`: `rulesetId` from step 2; `rules` and `requiredApprovals` from the read of step 3 (the ruleset as it is now).
  - `would-create`: `rulesetId` `null`, `resources` `[]`; `rules` and `requiredApprovals` from the file (what `apply` would create).
  - `created`, `updated`: `rulesetId` from the POST answer or step 2; `rules` and `requiredApprovals` from the read of step 6 when it exited 0, otherwise from the file.
  - `pending`: `rulesetId` `null`, `resources` `[]`, `rules` `[]`, `requiredApprovals` `null`.
  - `failed`: `rules` `[]` and `requiredApprovals` `null`; `rulesetId` and `resources` as above (set only when step 2 listed exactly one ruleset `main`).
  - `otherRulesets` is the list of step 2 in every ending where step 2 gave a JSON list (`[]` when there are none), and `[]` otherwise.
- `cost` is always `{ "fixed": false, "notes": "no cost" }`: rulesets cost nothing by themselves.
