---
description: GitHub repository configure, with the gh CLI. Use to correct the settings of an existing GitHub repository (description, topics, merge methods, delete branch on merge, issues, wiki, projects) and its visibility. Only the given settings are touched; plan by default; a visibility change needs confirmVisibility equal to the requested visibility.
---

# github_repo-configure

Corrects the settings and the visibility of an existing GitHub repository with the `gh` CLI, and verifies them. Only the settings given as arguments are compared and changed: an argument left out is not read as a wish and is never changed. It never creates a repository (that is `github_repo-create`).

## Arguments

Free text after the skill name, as `key=value` pairs. A value with spaces or commas is written in quotes (`description="Status pages, per tenant"`, `topics="a,b"`).

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `description=<text>` | The wanted description. |
| `topics=<t1>,<t2>` | The complete wanted list of topics, comma-separated. `topics=` (empty) means no topics. |
| `mergeCommit=<true\|false>` | Allow merge commits. |
| `squash=<true\|false>` | Allow squash merging. |
| `rebase=<true\|false>` | Allow rebase merging. |
| `deleteBranchOnMerge=<true\|false>` | Delete the head branch when a pull request is merged. |
| `issues=<true\|false>` | Issues on or off. |
| `wiki=<true\|false>` | Wiki on or off. |
| `projects=<true\|false>` | Projects on or off. |
| `visibility=<public\|private>` | The wanted visibility. |
| `confirmVisibility=<public\|private>` | Confirms the visibility change. Needed by `apply` when the visibility changes. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` changes. |

The settings are `description`, `topics`, `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects` and `visibility`. Validate before any command, in this order; the first rule broken ends with the result block with `status` `failed`, one sentence saying which rule failed, and no command (do not ask for anything):

- `owner` and `name` are given (a missing one is named in the sentence).
- At least one setting is given (`topics=` with an empty value counts as a given setting); otherwise the sentence is "nothing to configure was given".
- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `description`, when given, is not empty and has no line break, no `"`, no `“`, no `”`, no `„`, no backtick, no `$` and no `\` (they could break out of the quotes of the command).
- `topics`, when given and not empty, is split on `,`; each topic has 1 to 50 characters of `a-z`, `0-9` and `-`, and starts with a letter or a digit (no capitals, no `_`, no spaces, no empty item). Repeated topics count once.
- `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki` and `projects`, when given, are `true` or `false`.
- `visibility`, when given, is `public` or `private`.
- `confirmVisibility`, when given, is `public` or `private`, `visibility` is given, and `confirmVisibility` equals `visibility`. `confirmVisibility` without `visibility`, or different from it, fails.
- `mergeCommit`, `squash` and `rebase` are not all three given as `false` (at least one merge method must stay on; the same rule is checked again in step 2 with the values read).
- `mode`, when given, is `plan` or `apply`.

## Steps

Show each command before running it. Run only the commands below, in this order, each at most once (the read of step 1 runs again as the verification of step 6): no `gh auth status`, no `gh repo view`, no other `gh` command, no retry. Never print the account name or the token. In commands, the description is always in double quotes.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree (an `exit 0` reported next to an error line such as `gh: Not Found (HTTP 404)`), the text decides and the answer says that the exit code could not be trusted.

1. Read the repository:

   ```
   gh api repos/<owner>/<name>
   ```

   Read the exit code and the output, then take the first case that applies:

   - `gh` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `gh` must be installed. Run nothing else.
   - The output names authentication (`gh auth login`, not logged in, bad credentials, HTTP 401): `failed`. Say in one sentence that `gh` is not logged in and that the fix is `gh auth login`. Run nothing else.
   - Non-zero exit and the output contains `HTTP 404`: the repository does not exist (or this account cannot see it). `failed`: say in one sentence that the repository does not exist and that `github_repo-create` creates it first. Run nothing else.
   - Any other non-zero exit (HTTP 403, 5xx, network error, anything else): `failed`. The state is unknown: never report it as "does not exist". Say the cause in one sentence, with no raw error text. Run nothing else.
   - Exit 0: the repository exists. From the JSON take `visibility`, `description`, `topics`, `allow_merge_commit`, `allow_squash_merge`, `allow_rebase_merge`, `delete_branch_on_merge`, `has_issues`, `has_wiki`, `has_projects`. Continue.

2. Compare each given setting with the value read; a setting that was not given is not compared:

   | Setting | Read from | Differs when |
   |---|---|---|
   | `description` | `description` | the given text is not exactly the read one (`null` differs from any text) |
   | `topics` | `topics` | the set of given topics is not the set read (order does not matter) |
   | `mergeCommit` | `allow_merge_commit` | the booleans differ |
   | `squash` | `allow_squash_merge` | the booleans differ |
   | `rebase` | `allow_rebase_merge` | the booleans differ |
   | `deleteBranchOnMerge` | `delete_branch_on_merge` | the booleans differ |
   | `issues` | `has_issues` | the booleans differ |
   | `wiki` | `has_wiki` | the booleans differ |
   | `projects` | `has_projects` | the booleans differ |
   | `visibility` | `visibility` | the given value is not the read one |

   Each difference is a change `{ "setting": "<setting>", "from": <read value>, "to": <given value> }`, listed in the order of the table (topics as sorted lists).

   - The merge methods that would result (the given value, or the read value when not given) are all three `false`: `failed`. Say in one sentence that at least one merge method must stay on. Run nothing else.
   - No difference: `unchanged`. Run nothing else.
   - Otherwise, go on with the mode.

3. `plan`: `status` `would-update`; `outputs.changes` lists every difference, the visibility included. Show the commands of steps 4 and 5 that `apply` would run, without running them. When the visibility differs, say that `apply` will need `confirmVisibility=<value>` (or the owner's answer), and, for a change to `private`, that branch protection stops being enforced on the free plan. Run nothing else.

4. `apply`, only when a setting other than `visibility` differs: change them in one command that has only the flags of the settings that differ:

   ```
   gh repo edit <owner>/<name> --description "<description>" --enable-merge-commit=<bool> --enable-squash-merge=<bool> --enable-rebase-merge=<bool> --delete-branch-on-merge=<bool> --enable-issues=<bool> --enable-wiki=<bool> --enable-projects=<bool> --add-topic <t> --remove-topic <t>
   ```

   - The flags map to `description`, `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki` and `projects`. Boolean flags are always written `=true` or `=false`.
   - For topics: one `--add-topic <t>` for each given topic the repository does not have, and one `--remove-topic <t>` for each topic the repository has that was not given. A topic both given and present gets no flag.
   - Never put `--visibility` in this command.
   - A non-zero exit: `failed`; nothing was changed. Say the cause in one sentence, with no raw error text. Run nothing else (not the visibility change either).

5. `apply`, only when `visibility` differs:

   - Without `confirmVisibility` equal to `visibility`: ask the owner "Make `<owner>/<name>` PUBLIC? Its whole history becomes visible." (for `public`) or "Make `<owner>/<name>` PRIVATE? Branch protection stops being enforced on the free plan." (for `private`), and do not wait for an answer. Leave the visibility as it is and add one `pending` item `confirm visibility <value>`, whose `how` is `/aleogr-repo-github:github_repo-configure owner=<owner> name=<name> visibility=<value> confirmVisibility=<value> mode=apply`. If step 4 ran, go to step 6; otherwise end the run here with `status` `pending`. If the owner answers yes later in this conversation, run the skill again with that `how`; any other answer changes nothing.
   - With `confirmVisibility` equal to `visibility`: change it in its own command, always after step 4:

     ```
     gh repo edit <owner>/<name> --visibility <value> --accept-visibility-change-consequences
     ```

     A non-zero exit: say the cause in one sentence, with no raw error text. When step 4 ran, the status is `updated` and the visibility becomes one `pending` item `visibility`, whose `how` is the same command as the `confirm visibility` item above; go to step 6. When step 4 did not run, `failed`: nothing was changed; run nothing else.

6. Verify, once, when a `gh repo edit` of this run succeeded:

   ```
   gh api repos/<owner>/<name>
   ```

   The status is `updated`: a change was made in this run, whatever this read shows. Compare again every given setting as in step 2, except `visibility` when it was not changed in this run (unconfirmed or refused). Anything that does not hold is said in one sentence and becomes items in `pending`, each problem once:

   - The read fails: one item `verify` whose `how` is `/aleogr-repo-github:github_repo-describe owner=<owner> name=<name>`.
   - A given setting still differs: one item `configure` whose `how` is `/aleogr-repo-github:github_repo-configure owner=<owner> name=<name>` plus each setting that still differs as `<setting>=<value>` (`description="<description>"`, `topics="<t1>,<t2>"`, `visibility=<value>` without `confirmVisibility`, so that the run asks again), plus `mode=apply`.

Then answer in a few lines: what was changed (or would be changed), what is waiting for the visibility confirmation (with the question), anything left in `pending`, and the result block. When the answer suggests a follow-up command, a value with a comma or a space is in double quotes (`topics="a,b"`).

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "repo-configure",
  "mode": "apply",
  "status": "updated",
  "resources": [
    { "type": "repository", "id": "<owner>/<name>", "name": "<name>" }
  ],
  "outputs": {
    "changes": [
      { "setting": "rebase", "from": true, "to": false }
    ],
    "settings": { "mergeCommit": true, "squash": true, "rebase": false, "deleteBranchOnMerge": true, "issues": true, "wiki": false, "projects": false },
    "visibility": "private",
    "description": "<text>",
    "topics": ["<topic>"]
  },
  "cost": { "fixed": false, "notes": "private repositories of a free organization use the 2,000 Actions minutes a month" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of:
  - `would-update`: `plan`, at least one given setting differs (an unconfirmed visibility change included).
  - `updated`: `apply`, at least one `gh repo edit` of this run succeeded, whatever happened after it. An unconfirmed or refused visibility change, a failed verification or a setting that still differs is an item in `pending`: `updated` with a non-empty `pending` is allowed.
  - `unchanged`: every given setting already has the given value (`plan` or `apply`); nothing was done.
  - `pending`: `apply`, nothing was changed, and the run waits for the visibility confirmation (only `visibility` differs and it was not confirmed).
  - `failed`: an argument missing or broke a rule, no setting given, `gh` missing or not logged in, the repository does not exist, the read of step 1 refused, the merge methods would all be off, or the first `gh repo edit` of this run refused. Nothing was changed.
- `outputs.changes` holds `{ "setting", "from", "to" }` items with the setting names of the table in step 2, in that order:
  - `would-update`: every difference.
  - `updated`: the differences a `gh repo edit` of this run changed (an unconfirmed or refused visibility is not in it). A setting that was sent but still differs after the verification of step 6 is not in it either: it is a `pending` item.
  - `unchanged`, `pending`, `failed`: `[]`.
- `outputs.settings` uses the keys of `github_repo-describe`, in this order: `mergeCommit` (`allow_merge_commit`), `squash` (`allow_squash_merge`), `rebase` (`allow_rebase_merge`), `deleteBranchOnMerge` (`delete_branch_on_merge`), `issues` (`has_issues`), `wiki` (`has_wiki`), `projects` (`has_projects`). `outputs.visibility` (`public`, `private` or `internal`), `outputs.description` (`null` when it has none) and `outputs.topics` (sorted) are read the same way. Values come only from the commands' output.
- Each `pending` item is `{ "item": "<what>", "reason": "manual", "how": "<text>" }`. `pending` has items only with `updated` (the items of steps 5 and 6) and with the status `pending` (the one item `confirm visibility <value>`); it is `[]` otherwise.
- The shape for each ending:
  - `updated`: `resources` has the repository; `outputs.settings`, `visibility`, `description` and `topics` come from the read of step 6 when it exited 0, otherwise from the read of step 1 with each item of `changes` set to its `to`.
  - `would-update`, `unchanged`, `pending`: `resources` has the repository; `outputs.settings`, `visibility`, `description` and `topics` come from the read of step 1 (nothing was changed).
  - `failed` before the read of step 1 exited 0 (arguments, `gh`, a missing or refused repository): `resources` is empty and `outputs` is `{ "changes": [], "settings": null, "visibility": null, "description": null, "topics": [] }`. A failed read never says the repository does not exist.
  - `failed` after the read of step 1 exited 0 (merge methods all off, the first `gh repo edit` refused): `resources` has the repository; `outputs` comes from the read of step 1, with `changes` `[]`.
- `cost` is always `"fixed": false`. `notes` is `"no cost: nothing was changed"` when `outputs.visibility` is `null`; otherwise `"no cost"` when `outputs.visibility` is `public`, and `"private repositories of a free organization use the 2,000 Actions minutes a month"` when it is `private` or `internal`.
