---
description: GitHub repository describe, with the gh CLI. Use to learn whether a GitHub repository exists and what state it is in (visibility, default branch, description, topics, merge settings, features, and whether the branch protection ruleset `main` exists and matches the plugin's ruleset-main.json, or with checks=ci ruleset-main-ci.json, which also requires the status check `ci`). Read-only; the other aleogr-repo-github skills call it first.
---

# github_repo-describe

Reads the real state of a GitHub repository with the `gh` CLI and reports it. It never creates, changes or deletes anything and has no `mode`.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. |
| `name=<name>` | The repository name. |
| `checks=<ci\|none>` | `none` (default): the ruleset file is `ruleset-main.json`. `ci`: the ruleset file is `ruleset-main-ci.json`, the same ruleset plus the rule that requires the status check `ci`. |

`owner` and `name` are required: a missing `owner` or `name` ends with the result block with `status` `failed` and one sentence saying which is missing, with no command (do not ask for it). Validate before any command; a value that breaks a rule ends with the result block with `status` `failed`, one sentence saying which rule failed, and no command:

- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `checks`, when given, is `ci` or `none`.

## Steps

Show each command before running it. Run only the commands below, in this order, each at most once: no `gh auth status`, no `gh repo view`, no other `gh` command, no retry. Never print the account name or the token. The ruleset file is `ruleset-main-ci.json` when `checks=ci` and `ruleset-main.json` otherwise (`checks` absent or `none`); `<ruleset file>` below stands for its name, and no other file is read, compared with or sent.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree (an `exit 0` reported next to an error line such as `gh: Not Found (HTTP 404)`), the text decides and the answer says that the exit code could not be trusted. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

1. Read the repository:

   ```
   gh api repos/<owner>/<name>
   ```

   Read the exit code and the output, then take the first case that applies:

   - `gh` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `gh` must be installed. Run nothing else.
   - The output names authentication (`gh auth login`, not logged in, bad credentials, HTTP 401): `failed`. Say in one sentence that `gh` is not logged in and that the fix is `gh auth login`. Run nothing else.
   - Non-zero exit and the output contains `HTTP 404`: the repository does not exist (or this account cannot see it). This is the only answer that means "does not exist". Run nothing else and report `exists` false with `status` `unchanged`.
   - Any other non-zero exit (HTTP 403, 5xx, network error, anything else): `failed`. The state is unknown: never report it as "does not exist". Say the cause in one sentence, with no raw error text. Run nothing else.
   - Exit 0: the repository exists. From the JSON take `html_url`, `visibility`, `default_branch`, `description`, `topics`, `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`, `delete_branch_on_merge`, `has_issues`, `has_wiki`, `has_projects`. Continue.

2. Read its rulesets:

   ```
   gh api repos/<owner>/<name>/rulesets
   ```

   - Exit 0 and the output is a JSON list of rulesets (it may be `[]`): look for rulesets whose `name` is exactly `main` (case-sensitive: `Main` or `main-2` is not `main`). Exactly one: take its `id` and go to step 3. None: `protection.state` is `unprotected`; skip step 3. More than one: `failed` (say in one sentence that two rulesets are named `main`); run nothing else.
   - Exit 0 but the output is not a JSON list: `failed`. Say so in one sentence; run nothing else.
   - Non-zero exit and the output contains `HTTP 403` and a message containing `Upgrade`: the plan does not allow rulesets on this repository. `protection.state` is `unavailable` (branch protection needs a paid plan or a public repository). This is a known notice, not a failure: `status` stays `unchanged`. Skip step 3.
   - Any other non-zero exit: `failed`. Say the cause in one sentence, with no raw error text. Run nothing else.

   `protection.otherRulesets` is the sorted list of the names of the other rulesets in the list (empty when there are none or the read gave `unavailable`).

3. Only when step 2 listed a ruleset named `main`, read it with its `id`:

   ```
   gh api repos/<owner>/<name>/rulesets/<id>
   ```

   A non-zero exit is `failed` (one sentence, no raw error text). On exit 0, `protection.state` is `protected` and `protection.rulesetId` is the `id`. Read `${CLAUDE_PLUGIN_ROOT}/files/<ruleset file>` with the Read tool (not a shell command); if it cannot be read or is not valid JSON, `failed`. Then set `protection.matches` by this rule, the same one the other aleogr-repo-github skills use:

   - Compare only the keys the file has: `target`, `enforcement`, `bypass_actors`, `conditions` and `rules`, and inside them only the keys the file has. Keys the read ruleset has and the file does not (`id`, `source`, `source_type`, `created_at`, `updated_at`, `_links`, `current_user_can_bypass`, `node_id`, extra rule parameters such as `required_reviewers` or `require_extra_approval_for_unattributed_changes`, and any other) are ignored.
   - Scalars and objects are compared by deep equality.
   - These lists are compared as sets, order ignored: `rules`, `allowed_merge_methods`, `conditions.ref_name.include`, `conditions.ref_name.exclude`, `bypass_actors` and, in `ruleset-main-ci.json`, the `required_status_checks` list of the `required_status_checks` rule, which is compared as the set of its `context` values (other keys of its items are ignored). There is no other list in the file.
   - `rules` is matched by `type`: it must have exactly the file's rule types (`deletion`, `non_fast_forward`, `pull_request`, and `required_status_checks` in `ruleset-main-ci.json`), each once, no more and no fewer, so a ruleset that requires status checks differs from `ruleset-main.json` and one that does not differs from `ruleset-main-ci.json`; each rule is then compared on the keys the file gives it (for `pull_request` and `required_status_checks`, every key of its `parameters` in the file).
   - `bypass_actors` absent, `null` and `[]` all count as "none", and are equal to each other.

   `matches` is true when every compared key is equal, false otherwise. `protection.requiredChecks` is the sorted list of the `context` values of the read ruleset's `required_status_checks` rule (`[]` when it has none), whatever the ruleset file.

Then answer in a few lines: whether the repository exists, its URL, visibility and default branch, the protection state (and, when `protected`, whether it matches the ruleset file), and the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill's lines and its block are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). Its answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "repo-describe",
  "mode": "plan",
  "status": "unchanged",
  "resources": [
    { "type": "repository", "id": "<owner>/<name>", "name": "<name>" }
  ],
  "outputs": {
    "exists": true,
    "id": 7654321,
    "ownerId": 2345678,
    "url": "https://github.com/<owner>/<name>",
    "visibility": "public",
    "defaultBranch": "main",
    "description": "<text>",
    "topics": ["<topic>"],
    "settings": { "mergeCommit": true, "squash": true, "rebase": false, "deleteBranchOnMerge": true, "issues": true, "wiki": false, "projects": false },
    "protection": { "state": "protected", "rulesetId": 123, "matches": true, "requiredChecks": [], "otherRulesets": ["<name>"] }
  },
  "cost": { "fixed": false, "notes": "read-only" },
  "pending": []
}
```

- Values come only from the commands' output: `url` from `html_url`, `visibility` from `visibility` (`public`, `private` or `internal`), `defaultBranch` from `default_branch`, `description` from `description` (`null` when it has none), `topics` from `topics` (sorted), and `settings` from `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`, `delete_branch_on_merge`, `has_issues`, `has_wiki`, `has_projects`, in that order. `id` and `ownerId` are GitHub's numeric ids of the repository and of its owner, numbers taken from `id` and `owner.id` of the same read (`null` when the read does not have one).
- `protection.state` is `protected` (a ruleset named `main` exists), `unprotected` (none is named `main`) or `unavailable` (the plan does not allow rulesets). `rulesetId` and `matches` are `null` and `requiredChecks` is `[]` unless `protected`.
- `status` is `unchanged` whenever every step that ran succeeded, whether or not the repository exists (`HTTP 404` in step 1 and `unavailable` in step 2 are successful answers); it is `failed` otherwise.
- Repository does not exist (HTTP 404 in step 1): `resources` is empty and `outputs` is `{ "exists": false, "id": null, "ownerId": null, "url": null, "visibility": null, "defaultBranch": null, "description": null, "topics": [], "settings": null, "protection": null }`.
- `status` is `failed` when an argument is missing or broke a rule, `gh` is missing or not logged in, a command exited non-zero in a way the steps do not name as a known answer, step 2 did not give a JSON list, two rulesets are named `main`, or the ruleset file could not be read. A failed read never says the repository does not exist. The shape depends on where it failed:
  - Before or at step 1 (arguments, `gh`, the repository read): `resources` is empty and `outputs` is `{ "exists": null, "id": null, "ownerId": null, "url": null, "visibility": null, "defaultBranch": null, "description": null, "topics": [], "settings": null, "protection": null }`.
  - At step 2 or 3 (step 1 proved the repository exists): `resources` has the repository, and `outputs` keeps `exists` true and everything step 1 read (`id`, `ownerId`, `url`, `visibility`, `defaultBranch`, `description`, `topics`, `settings`), with `protection` `{ "state": null, "rulesetId": null, "matches": null, "requiredChecks": [], "otherRulesets": [] }`.
- `mode` is always `plan`: the skill only reads.
