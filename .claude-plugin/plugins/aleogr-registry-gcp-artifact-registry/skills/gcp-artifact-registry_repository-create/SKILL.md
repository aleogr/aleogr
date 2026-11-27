---
description: Google Cloud Artifact Registry (gcp-artifact-registry) repository create. Use to create a project's Docker image repository in Artifact Registry on Google Cloud, in the project's own GCP project and declared region, labelled with the project and the environment, and to learn the image path every component's image starts with. Idempotent (an existing repository is never touched); plan by default. No fixed cost.
allowed-tools: Bash(aleogr-registry-gcp-artifact-registry --read-only gcp-artifact-registry_repository-create), Bash(aleogr-registry-gcp-artifact-registry --read-only gcp-artifact-registry_repository-create *)
---

# gcp-artifact-registry_repository-create

Creates the project's image repository in Artifact Registry when it is missing: id `<project>`, format Docker, in `region`, with the labels `aleogr-project=<project>` and `aleogr-environment=<environment>`, and reads it back. An existing repository is never changed. A repository of that id that exists in another region is left alone and reported as something to fix by hand: a repository has one region. Nothing here has a fixed cost: an empty repository costs nothing, and storage is free up to 0.5 GB.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project that will hold the repository (the project's own, for that environment). |
| `project=<name>` | The aleogr project name, which is also the repository's id. |
| `environment=dev\|hom\|prd` | The project environment, written as a label. |
| `region=<region>` | The declared region, for example `us-central1`. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

An existing repository is never changed: one in another region, or not a Docker repository, is left for the owner to fix by hand.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-registry-gcp-artifact-registry gcp-artifact-registry_repository-create <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-registry-gcp-artifact-registry --read-only gcp-artifact-registry_repository-create <arguments>
  ```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command aleogr-registry-gcp-artifact-registry could not be run: update the plugin aleogr-registry-gcp-artifact-registry, then try again.` followed by this block, and nothing else (with `"mode": "apply"` in place of `"mode": "plan"` when the command was the one for `mode=apply`):

```aleogr-result
{
  "aleogr-result": 1,
  "family": "registry",
  "provider": "gcp-artifact-registry",
  "action": "repository-create",
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
