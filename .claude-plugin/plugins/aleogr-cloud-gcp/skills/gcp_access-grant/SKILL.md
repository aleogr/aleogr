---
description: Google Cloud (GCP) access grant. Use to let one person in, through the login (IAP), to the Cloud Run services of an aleogr project's components in the GCP project of an environment - by granting that person's e-mail, as `user:<e-mail>` only, the role that passes the login on each service, never on the project - or to list how many people each service lets in. Never grants a group, a domain, a service account or everyone, and removes nothing. Idempotent; plan by default. No cost.
allowed-tools: Bash(aleogr-cloud-gcp --read-only gcp_access-grant), Bash(aleogr-cloud-gcp --read-only gcp_access-grant *)
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
  aleogr-cloud-gcp gcp_access-grant <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-cloud-gcp --read-only gcp_access-grant <arguments>
  ```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command aleogr-cloud-gcp could not be run: update the plugin aleogr-cloud-gcp, then try again.` followed by this block, and nothing else (with `"mode": "apply"` in place of `"mode": "plan"` when the command was the one for `mode=apply`):

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

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
