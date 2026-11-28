---
description: Google Cloud (GCP) budget alert setup. Use to create one budget alert, with threshold rules, on the whole billing account, or to bring an existing budget of the same display name to the amount and thresholds asked. Plan by default.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_budget-alert-setup), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_budget-alert-setup *)
---

# gcp_budget-alert-setup

Creates one budget alert on the owner's billing account (the whole account, not one project). A budget whose display name already equals `displayName` is compared with the amount, currency and thresholds asked, and updated when it differs. A budget only alerts; it does not cap spending, and it has no fixed cost.

The budget commands need the Budget API (`billingbudgets.googleapis.com`) enabled on the quota project. A project created seconds ago may still refuse them: that is what the single retry in step 2 is for.

## Arguments

Free text after the skill name, as `key=value` pairs. All five are required: every argument but `mode`.

| Argument | Meaning |
|---|---|
| `displayName=<name>` | The budget's display name; it identifies the budget. Letters, digits, `.`, `_`, `-` only. |
| `amount=<number>` | The budget amount, for example `100`. |
| `currency=<code>` | The currency code, for example `BRL`. |
| `thresholds=<list>` | Comma-separated fractions of the amount, for example `0.5,0.9,1.0`. |
| `quotaProject=<project id>` | The GCP project id that is billed for the Budget API calls. |
| `mode=plan\|apply` | `plan` (default) reports what would change and changes nothing; `apply` executes. |

A budget only alerts: it never caps spending.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_budget-alert-setup <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_budget-alert-setup <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp could not be run: update the plugin aleogr-cloud-gcp, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "budget-alert-setup",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-cloud-gcp, then try again" } ]
}
```

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
