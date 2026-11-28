---
description: Google Cloud Artifact Registry (gcp-artifact-registry) registry describe. Use to learn whether a project's Docker image repository exists in Artifact Registry on Google Cloud, in which region, with which format and labels, its cleanup policy (how many versions it keeps, whether it deletes the rest, dry-run) and who may push to it. Read-only; the other Artifact Registry skills and the project plan call it first.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" gcp-artifact-registry_registry-describe), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" gcp-artifact-registry_registry-describe *)
---

# gcp-artifact-registry_registry-describe

Reads the real state of a project's image repository in Artifact Registry and reports it. The repository's id is the project's name, and it lives in the project's own GCP project. It never creates, changes or deletes anything and has no `mode`.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the repository. |
| `project=<name>` | The aleogr project name, which is also the repository's id. |
| `region=<region>` | The region the repository is declared in, for example `us-central1`. |

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" gcp-artifact-registry_registry-describe <arguments>
```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry could not be run: update the plugin aleogr-registry-gcp-artifact-registry, then try again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "registry",
  "provider": "gcp-artifact-registry",
  "action": "registry-describe",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-registry-gcp-artifact-registry, then try again" } ]
}
```

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
