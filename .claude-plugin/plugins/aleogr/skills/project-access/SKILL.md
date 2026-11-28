---
description: aleogr project access. Use in a project's folder to let one person in, through the login of the organization, to the Cloud Run services of the project's components in each declared environment (person=<e-mail>), or to see how many people each service lets in (list=yes). Reads the declaration `.aleogr/project.json`, finds the GCP project of each environment and invokes gcp_access-grant. Grants only the role that passes the login, on each service, never on the project; never a group, a domain, a service account or everyone; removes nothing. No confirmation is needed: it costs nothing and one command undoes it.
---

# project-access

Lets one person in to the project's services. For each environment the declaration `.aleogr/project.json` (in the folder the skill runs in) declares, it finds the GCP project of that environment (`aleogr-cloud-gcp:gcp_environment-describe`) and invokes `aleogr-cloud-gcp:gcp_access-grant` with the declaration's components, which grants `user:<person>` the role that passes the login on each component's service, and never on the GCP project. With `list=yes` it only reads, and says how many people each service lets in.

No `confirm` is asked: letting a person through the login of a service costs nothing, exposes the service to that one person only, and is undone by one command, which the answer gives. The skill runs no `gh`, `git` or `gcloud` command itself, and it does not create a service: `/aleogr:project-apply confirm=yes` does.

## Arguments

Free text after the skill name, as `key=value` pairs. Exactly one of `person` and `list` is given.

| Argument | Meaning |
|---|---|
| `person=<e-mail>` | The e-mail address of the one person to let in: a person's Google account. |
| `list=yes` | In place of `person`: only read, and say how many people, and who, each service lets in. |

`person` is the e-mail address of one person, only ever granted as the member `user:<person>`: never a group, a domain, a service account or everyone. The address must be a person's Google account: a group's address is not supported and would let nobody in.

With `list=yes` the run changes nothing: for each environment it finds the GCP project, and `gcp_access-grant` only reads each service's login policy and says how many people, and who, it lets in.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr" project-access <arguments>
```

Write each argument inside single quotes, whatever it holds (`'person=name@example.com'`, `'list=yes'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr ended without an answer: it may have changed something before it stopped. Read the state (run /aleogr:project-access list=yes) before running it again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "project-access",
  "mode": "apply",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "the run may have changed something" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr, then try again" } ]
}
```
