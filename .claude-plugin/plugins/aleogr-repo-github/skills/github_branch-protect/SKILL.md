---
description: GitHub branch protect, with the gh CLI. Use to protect the default branch of a GitHub repository with the repository ruleset `main` (no deletion, no force push, changes through a pull request, 0 approvals), creating or updating it from the plugin's ruleset-main.json, or with checks=ci from ruleset-main-ci.json (the same ruleset plus the required status check `ci`), then verify it. Idempotent; plan by default; reports pending when the GitHub plan does not allow rulesets on the repository. Never touches a ruleset with another name.
---

# github_branch-protect

Protects the default branch of a GitHub repository with the `gh` CLI: the repository ruleset named `main` is made equal to `${CLAUDE_PLUGIN_ROOT}/files/ruleset-main.json`, or, with `checks=ci`, to `${CLAUDE_PLUGIN_ROOT}/files/ruleset-main-ci.json`, which also requires the status check `ci`. It creates the ruleset when there is none, updates it when it differs, and verifies it. When the GitHub plan does not allow rulesets on the repository (a private repository on the free plan), it changes nothing and reports `pending`. A ruleset with any other name is never changed or deleted.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` creates or updates the ruleset `main`. |
| `checks=<ci\|none>` | `none` (default): the ruleset file is `ruleset-main.json`. `ci`: the ruleset file is `ruleset-main-ci.json`, the same ruleset plus the rule that requires the status check `ci`. |

`owner` and `name` are required: a missing `owner` or `name` ends with the result block with `status` `failed` and one sentence saying which is missing, with no command (do not ask for it). Validate before any command; a value that breaks a rule ends with the result block with `status` `failed`, one sentence saying which rule failed, and no command:

- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `mode`, when given, is `plan` or `apply`.
- `checks`, when given, is `ci` or `none`.

## Steps

Show each command before running it. Run only the commands below, in this order, each step's command at most once (the read of step 4 runs again as the verification of step 7): no `gh auth status`, no `gh repo view`, no other `gh` command, no `--method DELETE`, no `--method PATCH`, no retry. Never print the account name or the token. The ruleset file is `ruleset-main-ci.json` when `checks=ci` and `ruleset-main.json` otherwise (`checks` absent or `none`); `<ruleset file>` below stands for its name, and no other file is read, compared with or sent. The body of a write is always that file, passed as `--input "${CLAUDE_PLUGIN_ROOT}/files/<ruleset file>"` (with the quotes), never inline. Write `${CLAUDE_PLUGIN_ROOT}` as the real folder of this plugin, so the file is `<plugin folder>/files/<ruleset file>`.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree (an `exit 0` reported next to an error line such as `gh: Not Found (HTTP 404)`), the text decides and the answer says that the exit code could not be trusted. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

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

   - Exit 0 and the output is a JSON list of rulesets (it may be `[]`): look for rulesets whose `name` is exactly `main` (case-sensitive: `Main` or `main-2` is not `main`). Exactly one: take its `id`. None: there is no ruleset `main`. More than one: `failed` (say in one sentence that two rulesets are named `main`); run nothing else. In the first two cases go to step 3.
   - Exit 0 but the output is not a JSON list: `failed`. Say so in one sentence; run nothing else.
   - Non-zero exit and the output contains `HTTP 403` and a message containing `Upgrade`: the plan does not allow rulesets on this repository. End with `status` `pending`, in `plan` and in `apply`: write nothing, run nothing else. Say in one sentence that branch protection needs a paid plan or a public repository.
   - Any other non-zero exit (for example `HTTP 403` without `Upgrade`, such as missing admin rights): `failed`. Say the cause in one sentence, with no raw error text. This is never `pending`. Run nothing else.

   `otherRulesets` is the sorted list of the names of the other rulesets in the list (every ruleset whose `name` is not exactly `main`). They are only reported, never read, changed or deleted. When it is not empty, the answer says in one sentence that these rulesets exist and were left as they are.

3. Read `${CLAUDE_PLUGIN_ROOT}/files/<ruleset file>` once, with the Read tool (not a shell command), on every path that reaches this step. If it cannot be read or is not valid JSON: `failed`; say so in one sentence and run nothing else. Go to step 4 when step 2 found a ruleset `main`, otherwise to step 5.

4. Only when step 2 listed a ruleset named `main`, read it with its `id`:

   ```
   gh api repos/<owner>/<name>/rulesets/<id>
   ```

   A non-zero exit is `failed` (one sentence, no raw error text); run nothing else. On exit 0, compare it with the file of step 3 by this rule, the same one the other aleogr-repo-github skills use:

   - Compare only the keys the file has: `target`, `enforcement`, `bypass_actors`, `conditions` and `rules`, and inside them only the keys the file has. Keys the read ruleset has and the file does not (`id`, `source`, `source_type`, `created_at`, `updated_at`, `_links`, `current_user_can_bypass`, `node_id`, extra rule parameters such as `required_reviewers` or `require_extra_approval_for_unattributed_changes`, and any other) are ignored.
   - Scalars and objects are compared by deep equality.
   - These lists are compared as sets, order ignored: `rules`, `allowed_merge_methods`, `conditions.ref_name.include`, `conditions.ref_name.exclude`, `bypass_actors` and, in `ruleset-main-ci.json`, the `required_status_checks` list of the `required_status_checks` rule, which is compared as the set of its `context` values (other keys of its items are ignored). There is no other list in the file.
   - `rules` is matched by `type`: it must have exactly the file's rule types (`deletion`, `non_fast_forward`, `pull_request`, and `required_status_checks` in `ruleset-main-ci.json`), each once, no more and no fewer, so a ruleset that requires status checks differs from `ruleset-main.json` and one that does not differs from `ruleset-main-ci.json`; each rule is then compared on the keys the file gives it (for `pull_request` and `required_status_checks`, every key of its `parameters` in the file).
   - `bypass_actors` absent, `null` and `[]` all count as "none", and are equal to each other.

   Every compared key equal: `status` `unchanged`, in `plan` and in `apply`; run nothing else. Otherwise note each difference (a missing or extra rule type, or a key with the value found and the value of the file) and go to step 5.

5. Decide.

   - `plan`, no ruleset `main`: `status` `would-create`. Show the `POST` command of step 6 without running it. Run nothing else.
   - `plan`, ruleset `main` differs: `status` `would-update`. List what differs, and show the `PUT` command of step 6 without running it. Run nothing else.
   - `apply`: go to step 6.

6. Write the ruleset from the file.

   No ruleset `main`, create it:

   ```
   gh api --method POST repos/<owner>/<name>/rulesets --input "${CLAUDE_PLUGIN_ROOT}/files/<ruleset file>"
   ```

   Ruleset `main` differs, update it with its `id` (only that `id`):

   ```
   gh api --method PUT repos/<owner>/<name>/rulesets/<id> --input "${CLAUDE_PLUGIN_ROOT}/files/<ruleset file>"
   ```

   - Non-zero exit and the output contains `HTTP 403` and a message containing `Upgrade`: `status` `pending`, the same plan-limit ending as in step 2. Nothing was changed; run nothing else.
   - Any other non-zero exit: `failed`. Nothing was changed. Say the cause in one sentence, with no raw error text (no HTTP code, no API message). Run nothing else.
   - Exit 0: the status is `created` (POST) or `updated` (PUT), whatever happens in step 7. For POST, take the new ruleset's `id` from the answer. Go to step 7.

7. Verify, once, with the `id` of step 2 (PUT) or of the POST answer:

   ```
   gh api repos/<owner>/<name>/rulesets/<id>
   ```

   The status stays `created` or `updated`. Compare with the file by the rule of step 4. Anything that does not hold is said in one sentence and becomes one item in `pending`:

   - The POST answer has no `id`, or the read fails: one item `verify` whose `how` is `/aleogr-repo-github:github_repo-describe owner=<owner> name=<name>`.
   - The read ruleset differs from the file: one item `branch protection differs` whose `how` is `/aleogr-repo-github:github_branch-protect owner=<owner> name=<name> mode=apply`.

   With `checks=ci`, each `how` of this skill's `pending` items (these two and the plan-limit item below) ends with ` checks=ci`, so that it names the same ruleset file.

Then answer in a few lines: what was done (or would be done), what differs when the ruleset was or would be updated, the other rulesets left as they are (when there are any), anything left in `pending`, and the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill's lines and its block are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). Its answer never contains this block and never ends with it.

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
    "requiredChecks": [],
    "otherRulesets": []
  },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of:
  - `would-create`: `plan`, no ruleset `main`.
  - `would-update`: `plan`, the ruleset `main` differs from the file.
  - `created`: `apply`, the POST of step 6 succeeded in this run, whatever happened after it.
  - `updated`: `apply`, the PUT of step 6 succeeded in this run, whatever happened after it.
  - `unchanged`: the ruleset `main` already matches the file (`plan` or `apply`); nothing was done.
  - `pending`: the plan does not allow rulesets on this repository (the read of step 2, or the write of step 6, refused with `HTTP 403` and `Upgrade`), in `plan` or `apply`. Nothing was changed.
  - `failed`: an argument missing or broke a rule, `gh` missing or not logged in, the repository does not exist or its read refused, the rulesets read refused for any other reason or not a JSON list, two rulesets named `main`, the ruleset file unreadable, the read of step 4 refused, or the write refused for any other reason. Nothing was changed.
- `pending` items are `{ "item": "<what>", "reason": "<reason>", "how": "<text>" }`:
  - With the status `pending`: exactly one item `{ "item": "branch protection needs a paid plan or a public repository", "reason": "plan-limit", "how": "make <owner>/<name> public (/aleogr-repo-github:github_repo-configure owner=<owner> name=<name> visibility=public mode=apply) or move the owner to a paid plan, then run /aleogr-repo-github:github_branch-protect owner=<owner> name=<name> mode=apply" }`.
  - With `created` or `updated`: the item of step 7 (`verify` or `branch protection differs`), with `"reason": "manual"`, when there is one; `[]` otherwise. `created` or `updated` with a non-empty `pending` is allowed.
  - With every other status: `[]`.
- `outputs` and `resources` describe the ruleset `main` as it is at the end of the run. One rule for every ending: when a ruleset `main` exists and its `id` is known, `outputs.rulesetId` is that `id` (a number) and `resources` is `[{ "type": "ruleset", "id": "<id>", "name": "main" }]` (the `id` as a string); otherwise `rulesetId` is `null` and `resources` is `[]`. `outputs.rules` is the sorted list of the ruleset's rule types, `outputs.requiredApprovals` its `pull_request` rule's `required_approving_review_count` (`null` when there is no `pull_request` rule), and `outputs.requiredChecks` the sorted list of the `context` values of its `required_status_checks` rule (`[]` when there is no such rule). Their source, per ending:
  - `unchanged`, `would-update`: the read of step 4 (the ruleset as it is now).
  - `would-create`: no ruleset exists, so `rulesetId` is `null` and `resources` `[]`; `rules`, `requiredApprovals` and `requiredChecks` come from the file read in step 3 (what `apply` would create).
  - `created`, `updated`: `rulesetId` from the POST answer or step 2. After a write, `rules`, `requiredApprovals` and `requiredChecks` come from the verification read of step 7, not from the file; only when that read failed do they come from the file.
  - `pending` and `failed`: nothing was changed. When step 4 read a ruleset `main` (for example a refused PUT), `rulesetId`, `resources`, `rules`, `requiredApprovals` and `requiredChecks` are those of the read of step 4: the ruleset exists, unchanged. Otherwise (the step 2 refusal, a refused POST, any failure before step 4 read a ruleset) `rulesetId` is `null`, `resources` `[]`, `rules` `[]`, `requiredApprovals` `null` and `requiredChecks` `[]`.
  - `otherRulesets` is the list of step 2 in every ending where step 2 gave a JSON list (`[]` when there are none), and `[]` otherwise.
- `cost` is always `{ "fixed": false, "notes": "no cost" }`: rulesets cost nothing by themselves.
