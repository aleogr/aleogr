---
description: Google Cloud (GCP) access grant. Use to let one person in, through the login (IAP), to the Cloud Run services of an aleogr project's components in the GCP project of an environment - by granting that person's e-mail, as `user:<e-mail>` only, the role that passes the login on each service, never on the project - or to list how many people each service lets in. Never grants a group, a domain, a service account or everyone, and removes nothing. Idempotent; plan by default. No cost.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_access-grant), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_access-grant *)
---

# gcp_access-grant

Lets one person in to each component's Cloud Run service `<project>-<component>` through the login (IAP): it grants `user:<person>` the role `roles/iap.httpsResourceAccessor` on the login policy of each service, never on the GCP project, and reads each policy before and after. A service that already lets the person in is left alone. With `list=yes` instead of `person`, it only reads, and says who each service lets in.

The member is always `user:<person>`: never a group, a domain, a service account, `allUsers` or `allAuthenticatedUsers`. Nothing is ever removed here: the answer of `list=yes` gives the one command that removes a person. It never creates a service: create it first with `gcp_deploy-setup`. There is no cost: letting a person through the login costs nothing.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`; exactly one of `person` and `list` is given.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project of the project and environment (from `gcp_environment-describe`). |
| `project=<name>` | The aleogr project name. |
| `region=<region>` | The region of the services, for example `us-central1`. |
| `components=<name>[,<name>…]` | The components, in the declaration's order; each runs as the service `<project>-<name>`. |
| `person=<e-mail>` | The e-mail address of the one person to let in. |
| `list=yes` | In place of `person`: only read, and say how many people, and who, each service lets in. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. With `list=yes` nothing is changed in either mode. |

`person` is the e-mail address of one person, only ever granted as the member `user:<person>`: never a group, a domain, a service account or everyone. The address must be a person's Google account: a group's address is not supported and would let nobody in.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_access-grant <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_access-grant <arguments>
  ```

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
  "action": "access-grant",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-cloud-gcp, then try again" } ]
}
```
