---
description: Google Cloud (GCP) deploy describe. Use to learn whether each component of an aleogr project runs, in the GCP project of an environment, as a Cloud Run service as declared - its own account, the login (IAP) on, never public, no instance always on, its size, its labels, the login's agent allowed to call it, and the CI account allowed to replace its image - whether it holds the settings it was given, and whether it still runs the placeholder image. Read-only; a service that does not exist is not a failure.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_deploy-describe), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_deploy-describe *)
---

# gcp_deploy-describe

Reads, for each component, the Cloud Run service `<project>-<component>` in one GCP project, its access policy, its login policy and its account's access policy, and says whether the service exists, whether it is as declared and, when it is not, which parts differ. It never creates, changes or deletes anything and has no `mode`. Of the login policy it only looks for `allUsers` and `allAuthenticatedUsers` (an open service); which people may get in is `gcp_access-grant`'s, and is never compared.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `environment` and `env`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project of the project and environment (from `gcp_environment-describe`). |
| `project=<name>` | The aleogr project name. |
| `region=<region>` | The region of the services, for example `us-central1`. |
| `components=<name>[,<name>…]` | The components, in the declaration's order; each runs as the service `<project>-<name>`. |
| `maxInstances=<n>` | The declared maximum number of instances of each service. |
| `cpu=<n>` | The declared CPU of each service. |
| `memory=<size>` | The declared memory of each service, such as `512Mi`. |
| `ciAccount=<e-mail>` | The CI account (`<project>-ci@<projectId>.iam.gserviceaccount.com`, from `gcp_ci-identity-setup`). |
| `environment=<name>` | Optional: the environment, `dev`, `hom` or `prd`. Given, the service's `aleogr-environment` label must equal it. Orchestrators always give it. |
| `env=<component>:<NAME>=<value>[;<component>:<NAME>=<value>…]` | Optional: settings (environment variables) a service must hold, each for one component, `;` between them. Given, each one is part of that service's "as declared". Without it, no setting is read or compared. It may be written in double quotes (`env="…"`); the quotes are not part of it. |

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_deploy-describe <arguments>
```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp could not be run: update the plugin aleogr-cloud-gcp, then try again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "deploy-describe",
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
