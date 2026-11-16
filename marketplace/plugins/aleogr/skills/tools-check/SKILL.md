---
description: aleogr tools check. Use before planning or applying platform changes, to confirm the Google Cloud CLI (gcloud) is installed and authenticated and to see where Claude is running. Read-only; takes no arguments.
---

# tools-check

Checks that the command-line tools aleogr needs are ready, and where this session runs. It changes nothing and has no cost. In this stage the only required tool is `gcloud`. Other skills run it first and stop if it reports a problem.

## Arguments

None.

## Steps

Show each command before running it. Run only the commands below, in this order.

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

   - Command not found, or a non-zero exit: `gcloud` state is `missing` and `fix` is the official install instructions at https://cloud.google.com/sdk/docs/install. Skip step 3 and end with `failed`.

3. Is `gcloud` authenticated:

   ```
   gcloud auth list --filter=status:ACTIVE --format="value(account)"
   ```

   Read the exit code first; when it is non-zero, ignore any output, which is an error message and not an account.

   - Non-zero exit: the state could not be confirmed. Report it as `not-authenticated` with `fix` `gcloud auth login`, and say in one sentence that the check itself failed. Do not show the raw error text.
   - Exit 0 and empty output: state is `not-authenticated` and `fix` is `gcloud auth login`.
   - Exit 0 and an account listed: state is `ok` and `fix` is `null`.

   The account e-mail is never printed: not in the result block and not in the prose of the answer. Say only that an account is active.

## Answer

One line per tool: its name and `ok`, `missing` or `not authenticated`, and the fix when it is not ok. Then one line with where it runs.

- If any tool is not `ok`, say what cannot be done until it is fixed (every platform skill needs `gcloud`).
- If `where` is `cloud-session`, add one sentence: infrastructure setup is done from the local app, where the CLIs are authenticated. Still report what was found.

Then the result block.

## Result block

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
      { "name": "gcloud", "state": "ok", "fix": null }
    ]
  },
  "cost": { "fixed": false, "notes": "read-only check" },
  "pending": []
}
```

- `mode` is always `plan`. `status` is `unchanged` when every tool is `ok`, otherwise `failed`.
- `state` is `ok`, `missing` or `not-authenticated`. `fix` is a command or a URL, or `null` when `ok`.
- `resources` is empty. The block never contains an account e-mail.
