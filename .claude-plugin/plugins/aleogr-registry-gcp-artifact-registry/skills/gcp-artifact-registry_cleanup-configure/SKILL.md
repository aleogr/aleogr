---
description: Google Cloud Artifact Registry (gcp-artifact-registry) cleanup configure. Use to set the cleanup policy of a project's Docker image repository in Artifact Registry on Google Cloud, keeping the most recent versions of each image and deleting every other version, with dry-run off, and to check that the policy in the cloud is the declared one. Idempotent; plan by default. No fixed cost.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" --read-only gcp-artifact-registry_cleanup-configure), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" --read-only gcp-artifact-registry_cleanup-configure *)
---

# gcp-artifact-registry_cleanup-configure

Owns the cleanup policy of the project's image repository (id `<project>`, in `region`): two rules, and nothing else.

- `keep-most-recent`: keep the `<keep>` most recent versions of each image.
- `delete-the-rest`: delete every version (any tag state). A version that matches a keep rule and a delete rule is kept, so this deletes every version but the `<keep>` most recent of each image.

Dry-run is off: a policy in dry-run deletes nothing, so it counts as different. The policy is the ceiling of what storage can cost. Google applies it in a background job, about once a day, so a run never sees it delete anything. Setting the policy replaces every cleanup policy of the repository. It never creates the repository: create it first with `gcp-artifact-registry_repository-create`.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the repository. |
| `project=<name>` | The aleogr project name, which is also the repository's id. |
| `region=<region>` | The region the repository is declared in, for example `us-central1`. |
| `keep=<n>` | How many of the most recent versions of each image to keep, 1 to 50 (the project default is 5). |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

It never creates the repository, and setting the policy replaces every cleanup policy of the repository.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" gcp-artifact-registry_cleanup-configure <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" --read-only gcp-artifact-registry_cleanup-configure <arguments>
  ```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry could not be run: update the plugin aleogr-registry-gcp-artifact-registry, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "registry",
  "provider": "gcp-artifact-registry",
  "action": "cleanup-configure",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-registry-gcp-artifact-registry, then try again" } ]
}
```
