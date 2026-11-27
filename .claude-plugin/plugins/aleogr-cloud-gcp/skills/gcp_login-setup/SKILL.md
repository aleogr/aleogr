---
description: Google Cloud (GCP) login setup. Use to prepare the login of the organization - the custom OAuth client that the organization's Identity-Aware Proxy (IAP) setting names, so that a personal Google account can get into the services. Does what a command can do (grants the active account the role that changes the organization's IAP setting, enables the IAP API in the shared project) and prints the short list of what is left to the owner - the consent screen and the client in the console, and one command to paste in a terminal. Never sees the client's secret. Idempotent; plan by default.
allowed-tools: Bash(aleogr-cloud-gcp --read-only gcp_login-setup), Bash(aleogr-cloud-gcp --read-only gcp_login-setup *)
---

# gcp_login-setup

Prepares the login of the organization as far as a command can. Google has no command that creates a consent screen or an OAuth client, so those are a few clicks in the console; this skill does everything else: it grants the active `gcloud` account `roles/iap.settingsAdmin` on the organization when it lacks it, enables `iap.googleapis.com` in the shared project when it is off, and prints the list of what is left. It has no cost.

The client's secret never passes through this skill. The skill prints the one command that takes the secret as text for the owner to paste in a terminal; it never runs that command, never fills a value into it other than the shared project's id, never asks for the client id or the secret, and never reads a file that could hold them.

If the owner pastes a client id or a secret into the conversation, the skill does not use, repeat or store it, and points to the command of the list instead.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | Required. The shared platform project, which holds the consent screen and the client, and against which the reads of the organization's IAP setting are counted. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

`projectId` is required.

When the login is not prepared, the answer holds the list of what is left to the owner: the consent screen and the client, made by hand in the Google Cloud console, and one command that the owner pastes in a bash terminal, where it asks for the client id and, without showing it, the client secret. That list is a checklist for the owner, to relay exactly as the command printed it, the command in its own fenced `bash` block: never run that command, never fill a value into it, and never ask for the client id or the secret in the conversation.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-cloud-gcp gcp_login-setup <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-cloud-gcp --read-only gcp_login-setup <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command aleogr-cloud-gcp ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command aleogr-cloud-gcp could not be run: update the plugin aleogr-cloud-gcp, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "login-setup",
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
