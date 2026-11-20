---
description: aleogr tools check. Use before planning or applying platform changes, to confirm the Google Cloud CLI (gcloud) is installed and authenticated and to see where Claude is running. With the opt-in argument command=gh it checks the GitHub CLI (gh) instead, for the GitHub repository skills. Read-only.
---

# tools-check

Checks that the command-line tools aleogr needs are ready, and where this session runs. It changes nothing and has no cost. By default the only tool it checks is `gcloud`. The opt-in `command=gh` checks the GitHub CLI (`gh`) instead. Other skills run it first and stop if it reports a problem.

## Arguments

`command` (optional): `gcloud` (default) or `gh`. Without it the skill checks `gcloud`, exactly as before. Any other value: end with `failed`, one sentence, and run no command.

## Steps

Show each command before running it. Run only the commands below, in this order. With `command=gh`, step 1 is the same, then follow "With `command=gh`" below instead of steps 2 and 3.

1. Where it runs. Check the environment variables `CLAUDE_CODE_REMOTE` and `CODESPACES` (use whatever means works in the current shell). Then set `where`:

   | Found | `where` |
   |---|---|
   | `CLAUDE_CODE_REMOTE` is `true` | `cloud-session` |
   | else `CODESPACES` is `true` | `codespace` |
   | neither | `local` |

2. Is `gcloud` installed:

   ```
   gcloud --version
   ```

   - Exit 0: `command` is `gcloud`. Go on.
   - Command not found (the shell does not know the command: `command not found` or exit code 127 in bash, `not recognized` in PowerShell): state `missing`, `fix` is the official install instructions at https://cloud.google.com/sdk/docs/install. Skip step 3 and end with `failed`.
   - Found but exits non-zero (it failed to start, as can happen under Git Bash on Windows): run once

     ```
     gcloud.cmd --version
     ```

     Exit 0: `command` is `gcloud.cmd`; go on, and use `gcloud.cmd` in place of `gcloud` in step 3. Otherwise the state is `missing` with the same `fix`, the answer shows the first line of the `gcloud --version` error, and the skill skips step 3 and ends with `failed`.

3. Is `gcloud` authenticated:

   ```
   gcloud auth list --filter=status:ACTIVE --format="value(account)"
   ```

   Read the exit code first; when it is non-zero, ignore any output, which is an error message and not an account.

   - Non-zero exit: the state could not be confirmed. Report it as `not-authenticated` with `fix` `gcloud auth login`, and say in one sentence that the check itself failed. Do not show the raw error text.
   - Exit 0 and empty output: state is `not-authenticated` and `fix` is `gcloud auth login`.
   - Exit 0 and an account listed: state is `ok` and `fix` is `null`.

   The account e-mail is never printed: not in the result block and not in the prose of the answer. Say only that an account is active.

## With `command=gh`

After step 1:

1. Is `gh` installed:

   ```
   gh --version
   ```

   - Exit 0: go on.
   - Command not found (`command not found` or exit code 127 in bash, `not recognized` in PowerShell): state `missing`, `fix` is `https://cli.github.com`. Skip the next check and end with `failed`.
   - Any other non-zero exit: state `missing`, the same `fix`. Skip the next check and end with `failed`.

   In no case show the raw error text.

2. Is `gh` logged in:

   ```
   gh auth status
   ```

   Read the exit code only; never repeat its output, which names the account.

   - Non-zero exit: state `not-authenticated`, `fix` `gh auth login`.
   - Exit 0: state `ok`, `fix` `null`.

   The account name is never printed: not in the result block and not in the prose. Say only that an account is logged in.

`outputs.tools` has the one entry `{ "name": "gh", "command": "gh", "state": "...", "fix": "..." }`; `status` is `unchanged` when `ok`, otherwise `failed`. Answer with one line for `gh` and one for where it runs. If it is not `ok`, say that the GitHub repository skills cannot run until it is fixed.

## Answer

One line per tool: its name and `ok`, `missing` or `not authenticated`, and the fix when it is not ok. In the default check, if the command name is `gcloud.cmd`, say that every `gcloud` command must be run as `gcloud.cmd`. Then one line with where it runs.

- If any tool is not `ok`, say what cannot be done until it is fixed: in the default check, every platform skill needs `gcloud`; with `command=gh`, the GitHub skills.
- If `where` is `cloud-session`, add one sentence: infrastructure setup is done from the local app, where the CLIs are authenticated. Still report what was found.

Then the result block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). Its answer never contains this block and never ends with it.

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "tools-check",
  "mode": "plan",
  "status": "unchanged",
  "resources": [],
  "outputs": {
    "where": "local",
    "tools": [
      { "name": "gcloud", "command": "gcloud", "state": "ok", "fix": null }
    ]
  },
  "cost": { "fixed": false, "notes": "read-only check" },
  "pending": []
}
```

- `mode` is always `plan`. `status` is `unchanged` when every tool is `ok`, otherwise `failed`.
- `state` is `ok`, `missing` or `not-authenticated`. `fix` is a command or a URL, or `null` when `ok`.
- `command` is the command name to run the tool with. In the default check: `gcloud.cmd` when only `gcloud.cmd --version` worked, otherwise `gcloud`. With `command=gh`: `gh`.
- `resources` is empty. The block never contains an account e-mail.
