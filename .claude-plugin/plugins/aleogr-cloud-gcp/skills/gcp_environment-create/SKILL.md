---
description: Google Cloud (GCP) environment create. Use to create the GCP project of an aleogr project and environment (in the environment's folder, under the organization or, for test projects, inside the tst folder; or directly under the organization for the shared platform project), link its billing account and verify it. Idempotent; plan by default.
allowed-tools: Bash(aleogr-cloud-gcp --read-only gcp_environment-create), Bash(aleogr-cloud-gcp --read-only gcp_environment-create *)
---

# gcp_environment-create

Creates the GCP project that belongs to a project and an environment (or the shared platform project), links billing to it and verifies the result. If the project already exists and has billing, it changes nothing; if its billing is not linked, it links it. It has no fixed cost.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `project=<name>` | The aleogr project name. |
| `environment=dev\|hom\|prd` | The project environment. |
| `mode=plan\|apply` | `plan` (default) reports what would change and changes nothing; `apply` executes. |
| `platform=shared` | Only the aleogr platform passes it, with `project=shared` and no `environment`, to create the shared platform project. |
| `root=tst` | Optional. A project that tests the tooling: the environment's folder is looked up inside the folder `tst` instead of under the organization. |

`project` and `environment` are required. The shared platform's project is the one exception: `project=shared platform=shared`, with no `environment` and no `root`.

A GCP project's id is permanent. The result gives the project's id in `outputs.projectId`.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-cloud-gcp gcp_environment-create <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-cloud-gcp --read-only gcp_environment-create <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command aleogr-cloud-gcp ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command aleogr-cloud-gcp could not be run: update the plugin aleogr-cloud-gcp, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "environment-create",
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
