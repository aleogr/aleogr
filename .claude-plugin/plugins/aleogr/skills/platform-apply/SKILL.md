---
description: aleogr platform apply. Use to create the free part of the owner's shared platform on Google Cloud (shared project with billing, required APIs, one budget alert), then the shared Cloud SQL instance with the switch that stops it at night, from the owner's defaults, and prepares the login of the organization as far as a command can (the few clicks and the one command left are printed for the owner). Shows the plan and, without confirm=yes, changes nothing and ends with the command that confirms.
---

# platform-apply

Creates what `platform-plan` lists as missing, in order: the shared project, its APIs, the budget alert, the database switch, the database instance; last, it prepares the login of the organization as far as a command can. Everything but the instance is free; the instance has a fixed cost of `about R$ 50 per month while stopped`. Then it plans again to prove nothing is left.

The instance's fixed cost starts with its creation, and only a run given `confirm=yes` creates anything: without it, the run changes nothing, says what a confirmed run would create and what it costs, and ends `pending` with the command that confirms. While the instance is being created it runs and is charged by the hour; the run stops it and tests the night stop before it ends, also when that takes more than one command.

Its answer may hold two sections for the owner, both part of the answer and given as printed:

- `GitHub secrets`: the three secrets of the database switch, with their values and where to paste them in the repository on GitHub, once, by hand.
- `Login`: the few clicks left in the console and one command for the owner to paste in a terminal. Never run that command, never fill a value into it and never ask for one. Never ask for a client id or a secret in the conversation; if the owner pastes one, do not use, repeat or store it: point to the command of the list instead.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `confirm=yes` | Makes the changes. Without it, the run shows the plan and its cost, changes nothing and ends `pending` with the command that confirms. Any other value of `confirm` fails validation. |

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr" platform-apply <arguments>
```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds: never in the background.

Write each argument inside single quotes, whatever it holds (`'confirm=yes'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is its answer, ending with one fenced `aleogr-result` block.

A run may take more than one command. After a command ends, look at the `status` in its `aleogr-result` block. When it is `continue`, show the owner only the first line of that answer (the line that says what the run waits for, such as `Waiting for the database instance created in this run: it is creating.`), then run, with the Bash tool, again in the foreground with the same `timeout` of 600000 milliseconds, exactly the command written after `next: ` in that answer, character for character (it begins with the full path of this plugin's command, in double quotes: keep it as it is written), and look at its status in the same way; repeat. Never change, reorder, re-quote or drop an argument of the `next:` command, never add `confirm=yes` or any other argument yourself, never run anything else between two commands (no other command, no file read), never answer the owner or stop while the status is `continue`, and never run a `next:` command more than once. A run has at most eight commands: the command itself ends the run at that bound.

When the status is anything else, that command's answer is this skill's answer: give it exactly as printed, character for character, from its very first line to the fenced block, which comes last. Its first lines are usually one line per skill that made something (`gcp_services-enable: updated`, `gcp-cloud-sql_instance-create: created`, …), and in a run of several commands the last command prints them for the whole run: they are part of the answer, never leave them out. Only the answers whose status was `continue` (their one line, their `next:` line and their block) are left out. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command again, whatever it printed.

Only when a command (the first or a `next:` one) printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr ended without an answer: it may have changed something before it stopped. Read the state (run /aleogr:platform-plan) before running it again. An instance that runs is charged by the hour: stop it with /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "platform-apply",
  "mode": "apply",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "the run may have changed something" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr, then try again" } ]
}
```
