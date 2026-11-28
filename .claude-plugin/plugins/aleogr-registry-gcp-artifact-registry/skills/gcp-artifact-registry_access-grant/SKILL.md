---
description: Google Cloud Artifact Registry (gcp-artifact-registry) access grant. Use to let a CI service account push images to a project's Docker image repository in Artifact Registry on Google Cloud, by granting it the writer role on that one repository (never on the GCP project), and to check whether it already may push. Idempotent; plan by default. No fixed cost.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" --read-only gcp-artifact-registry_access-grant), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" --read-only gcp-artifact-registry_access-grant *)
---

# gcp-artifact-registry_access-grant

Lets one service account push to the project's image repository (id `<project>`, in `region`): it grants the role `roles/artifactregistry.writer` on that repository, never on the GCP project, and reads the repository's policy before and after. A binding that already exists is left alone; nothing is ever removed. Only push is granted: pull access is not needed, because Cloud Run's own agent pulls from a repository of its own project. It never creates the repository: create it first with `gcp-artifact-registry_repository-create`.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that holds the repository. |
| `project=<name>` | The aleogr project name, which is also the repository's id. |
| `region=<region>` | The region the repository is declared in, for example `us-central1`. |
| `identity=<e-mail>` | The service account that may push, as its e-mail: an account of the project's own GCP project (`<id>@<projectId>.iam.gserviceaccount.com`), for example the CI account `<project>-ci@<projectId>.iam.gserviceaccount.com`. |
| `role=push` | The access granted. `push` is the only one. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

`role=push` is the only access granted.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" gcp-artifact-registry_access-grant <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-registry-gcp-artifact-registry" --read-only gcp-artifact-registry_access-grant <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

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
  "action": "access-grant",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-registry-gcp-artifact-registry, then try again" } ]
}
```
