---
description: Google Cloud (GCP) services enable. Use to enable the Google APIs a GCP project of an aleogr project and environment (or the shared platform project) needs, enabling only the ones still missing. Idempotent; plan by default.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_services-enable), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_services-enable *)
---

# gcp_services-enable

Enables Google Cloud APIs on the GCP project that belongs to a project and an environment (or on the shared platform project). It compares the requested APIs with the enabled ones and enables only the missing ones. It never creates a project and has no fixed cost.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `project=<name>` | The aleogr project name (for the shared platform project: `shared`). |
| `environment=dev\|hom\|prd` | The project environment. |
| `platform=shared` | Instead of `environment`, with `project=shared`: the shared platform project, which has no environment. |
| `projectId=<id>` | Instead of the others: the GCP project id, when the caller already knows it. |
| `services=<list>` | Comma-separated API names, for example `a.googleapis.com,b.googleapis.com`. |
| `mode=plan\|apply` | `plan` (default) reports what would change and changes nothing; `apply` executes. |

`services` is required, and the project is named in one of three ways: `projectId`, `project=<name> environment=<environment>`, or `project=shared platform=shared`.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_services-enable <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_services-enable <arguments>
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
  "action": "services-enable",
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
