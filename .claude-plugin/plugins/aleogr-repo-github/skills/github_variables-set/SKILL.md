---
description: GitHub Actions variables set, with the gh CLI. Use to make a repository's Actions variables hold the given values (such as the identifiers a deploy job reads through `vars`), or, in plan mode, to learn which of them differ. One read of the repository's variables, then one set per variable that is missing or differs. Only the given variables are touched: none is ever deleted. Variable values never appear in the result block, only their names. Plan by default.
---

# github_variables-set

Makes the repository's Actions variables (repository level, read by a workflow as `${{ vars.<NAME> }}`) hold the given values, with the `gh` CLI. It reads the repository's variables once, and sets each given variable that is missing or holds another value. A variable that was not given is never read as a wish, never changed and never deleted; this skill deletes no variable at all. A variable is not a secret, but its value is still kept out of the result block: the block names variables, never their values.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `variables=<NAME>=<value>[,...]` | The wanted variables, comma-separated, each its name, `=` and its value. Required. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` sets the variables that are missing or differ. |

Validate before any command, in this order; the first rule broken ends with the result block with `status` `failed`, one sentence saying which rule failed (naming the variable, never its value), and no command (do not ask for anything):

- `owner`, `name` and `variables` are given and not empty (a missing one is named in the sentence).
- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `variables` is one or more entries separated by `,`, with no empty entry. Each entry is split at its first `=` into the variable's name and its value; an entry without `=` breaks this rule.
  - The name matches `^[A-Z][A-Z0-9_]{0,63}$` and does not start with `GITHUB_` (GitHub reserves that prefix). No two entries have the same name.
  - The value is not empty and has no `,`, no line break, no `"`, no backtick, no `$` and no `\` (the value is written in the double quotes of the command and must not break out of them).
- `mode`, when given, is `plan` or `apply`.

Below, the given variables are always taken **sorted by name**, in byte order (ASCII).

## Steps

Show each command before running it. Run only the commands below, in this order: the read of step 1 once, and the set of step 3 at most once per variable: no `gh auth status`, no `gh repo view`, no `gh variable get`, no `gh variable delete`, no `gh api` call, no other command, no retry. Never print the account name or the token. In commands, the value is always in double quotes.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree (an `exit 0` reported next to an error line such as `gh: Not Found (HTTP 404)`), the text decides and the answer says that the exit code could not be trusted. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

1. Read the repository's variables:

   ```
   gh variable list --repo <owner>/<name> --json name,value
   ```

   Read the exit code and the output, then take the first case that applies:

   - `gh` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `gh` must be installed. Run nothing else.
   - The output names authentication (`gh auth login`, not logged in, bad credentials, HTTP 401): `failed`. Say in one sentence that `gh` is not logged in and that the fix is `gh auth login`. Run nothing else.
   - Non-zero exit and the output contains `HTTP 404`: `failed`. Say exactly `The repository <owner>/<name> was not found, or this account cannot see it; nothing was set.` Run nothing else.
   - Any other non-zero exit (HTTP 403, 5xx, network error, anything else), or exit 0 with an output that is not a JSON array of objects with `name` and `value`: `failed`. Say exactly `The repository's Actions variables could not be read; nothing was set. Check that gh is signed in, may read the repository's variables, and that GitHub answers, then run this skill again.` Repeat no word of `gh`'s answer. Run nothing else.
   - Exit 0 with a JSON array (`[]` when the repository has no variable): continue.

2. Compare each given variable with the array, by name:

   - A given variable whose name is in the array with exactly the given value (byte for byte) is **already**.
   - A given variable whose name is not in the array, or whose value differs, is **to set**.
   - A variable in the array that was not given is ignored: it is not compared, not reported and never changed.

   - Nothing to set: `status` `unchanged`, in `plan` and in `apply`. Run nothing else.
   - `plan`: `status` `would-update`. Name the variables `apply` would set (names only) and run nothing else.
   - `apply`: go to step 3.

3. `apply` only: for each variable to set, in order (sorted by name), one command:

   ```
   gh variable set <NAME> --repo <owner>/<name> --body "<value>"
   ```

   - Exit 0: the variable is set. Go on with the next one.
   - Non-zero exit (any reason): stop here; run no further `gh variable set`. When no variable was set before it in this run: `failed`; say exactly `GitHub refused to set the variable <NAME>; nothing was set. Check that gh may change the repository's Actions variables (it needs write access to the repository), then run this skill again.` When at least one was set before it: `updated`; say exactly `GitHub refused to set the variable <NAME>; the variables before it were set and the rest were not. Check that gh may change the repository's Actions variables (it needs write access to the repository), then run this skill again with the same arguments.` and add the `pending` item `variables` below. Either way, repeat no word of `gh`'s answer.

   Every set succeeded: `status` `updated`.

Then answer in a few lines: which variables were set (or would be set) and which already held the given value, by name only (never a value), anything left in `pending`, and the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "variables-set",
  "mode": "apply",
  "status": "updated",
  "resources": [
    { "type": "repository", "id": "<owner>/<name>", "name": "<name>" }
  ],
  "outputs": {
    "set": ["GCP_IMAGE_PATH", "GCP_REGION"],
    "already": ["GCP_CI_ACCOUNT", "GCP_PROJECT_ID", "GCP_WIF_PROVIDER"]
  },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of:
  - `would-update`: `plan`, at least one given variable is missing or differs.
  - `updated`: `apply`, at least one `gh variable set` of this run succeeded, whatever happened after it. A set refused after others succeeded is the `pending` item `variables`: `updated` with a non-empty `pending` is allowed.
  - `unchanged`: every given variable already holds the given value (`plan` or `apply`); nothing was set.
  - `failed`: an argument missing or broke a rule, `gh` missing or not logged in, the read of step 1 refused, or the first `gh variable set` of this run refused. Nothing was set.
- `outputs` holds names only, sorted, each array written on one line; never a value:
  - `set`: `would-update`: the variables `apply` would set; `updated`: the variables set in this run; `unchanged` and `failed`: `[]`.
  - `already`: the given variables that already held the given value, as read by step 1; `[]` when step 1 did not succeed or did not run.
- `pending` is `[]`, except with `updated` after a refused set: exactly one item `{ "item": "variables", "reason": "manual", "how": "run github_variables-set again with the same arguments and mode=apply once gh may change the repository's Actions variables" }` (the `how` names no value).
- `resources` has the repository once the read of step 1 exited 0; `[]` when the run ended before that.
- `cost` is always `{ "fixed": false, "notes": "no cost" }`.
