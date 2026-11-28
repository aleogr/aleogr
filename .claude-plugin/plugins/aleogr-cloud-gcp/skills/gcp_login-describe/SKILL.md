---
description: Google Cloud (GCP) login describe. Use to learn whether the login of the organization is prepared - whether the organization's Identity-Aware Proxy (IAP) setting names a custom OAuth client, which the services of a standalone organization owned by a personal Google account need to let anyone in. Read-only; the platform's plan calls it.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_login-describe), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_login-describe *)
---

# gcp_login-describe

Reads the organization's IAP setting and says whether the login is prepared: the setting names an OAuth client. A service behind IAP inherits that client; without it, Google's managed client refuses a personal Google account. It never creates, changes or deletes anything and has no `mode`. The client's secret is never read: the setting shows only the client's id and a hash of the secret, and the answer repeats neither.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | Optional. The shared platform project: the read is counted against it (`--billing-project`), so that its IAP API, which `gcp_login-setup` enables, is the one used. The platform's plan passes it. Without it, the read is counted against the terminal's current project. |

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_login-describe <arguments>
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
  "action": "login-describe",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-cloud-gcp, then try again" } ]
}
```
