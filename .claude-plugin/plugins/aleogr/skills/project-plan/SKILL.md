---
description: aleogr project plan. Use in a project's folder to see what the project's GitHub repository is missing or has different from the declaration `.aleogr/project.json` (the repository, its settings and topics, its visibility, the declaration in the repository, the branch protection, when components are declared, their Go starting points and the CI file, and, when environments are declared, the GCP environment dev: its project, its APIs, the image repository and the CI identity, and, with components, the login of the organization, the Cloud Run services and the repository's CI secrets, and, when a component uses the database, its database on the shared instance). Prints a table of items, state and action. Read-only; changes nothing.
allowed-tools: Bash(aleogr project-plan), Bash(aleogr project-plan *)
---

# project-plan

Compares the project's declaration, `.aleogr/project.json` in the folder the skill runs in, with the real GitHub repository and prints a table: item, state, action. The plan only reads: it runs no `gh`, `git` or `gcloud` command itself, it invokes `aleogr:tools-check`, the read-only skills of `aleogr-repo-github` and, when components are declared, `github_ci-setup` and `aleogr-stack-go:go_setup` in `mode=plan` (and `aleogr:tools-check command=go` when the database modules of a component are to be added), and, when environments are declared, `aleogr:tools-check` for `gcloud`, `aleogr-cloud-gcp:gcp_environment-describe`, `aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_registry-describe` and `aleogr-cloud-gcp:gcp_ci-identity-setup` in `mode=plan`, and, when both are declared, `aleogr-cloud-gcp:gcp_login-describe`, `aleogr-cloud-gcp:gcp_deploy-describe` and `aleogr-repo-github:github_variables-set` with `kind=secrets` in `mode=plan`, and, when a component uses the database, `aleogr-cloud-gcp:gcp_environment-describe` for the shared project and `aleogr-db-gcp-cloud-sql:gcp-cloud-sql_database-describe` (and `gcp-cloud-sql_instance-describe` when that read of the instance fails), and running it changes nothing anywhere: it never starts the shared instance. `project-apply` runs it first and acts on its items.

## Arguments

Free text after the skill name, as `key=value` pairs. Everything else comes from the declaration, and any other text is ignored.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | Optional. The GCP project id of `dev`, when the caller already knows it (`project-apply` passes it after it created or found the project in its run): the plan reads that project by its id instead of searching by labels, which can lag behind a creation. |
| `readCloud=yes` | Optional. Passed only by `project-apply`, in its last plan after it wrote the database check's files in this folder in the same run: the declaration in the repository is this one and only generated files changed here, so the environment's items are read all the same (see "The declaration counts as in the repository", below). |

A `projectId` or `readCloud` given for a declaration without `environments` is not used.

**The declaration counts as in the repository** when the `declaration` item has the action `none`, or when `readCloud=yes` was given and the item is `changed here` / `propose` with the checkout `equal` (the declaration is the repository's, and only generated files changed in this folder). Without `readCloud=yes`, only the action `none` counts.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
aleogr project-plan <arguments>
```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command aleogr could not be run: update the plugin aleogr, then try again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "project-plan",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr, then try again" } ]
}
```

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
