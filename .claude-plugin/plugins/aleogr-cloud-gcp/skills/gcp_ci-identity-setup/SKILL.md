---
description: Google Cloud (GCP) CI identity setup. Use to create, in the GCP project of an aleogr project and environment, the keyless identity through which one GitHub repository's CI reaches that project - a service account `<project>-ci`, a workload identity federation pool `github` and provider `github` that accept only tokens of the declared repository (by name and by GitHub's numeric ids) on its default branch from a job of the declared reusable deploy workflow, and the binding that lets those tokens act as the account. Updates in place a provider whose condition, issuer or mapping differs (one made before the workflow clause existed included); refuses a deleted or disabled pool or provider, and a pool that holds another provider. Grants the account no project role. Idempotent; plan by default.
allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_ci-identity-setup), Bash("${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_ci-identity-setup *)
---

# gcp_ci-identity-setup

Sets up the identity GitHub Actions of one repository use to reach one GCP project, with no key: a service account (`<project>-ci`), a workload identity federation pool (`github`) with an OIDC provider (`github`) whose condition accepts only tokens of the declared repository, checked by its name, its numeric id and its owner's numeric id (a repository deleted and recreated under the same name does not pass), on the declared branch, and only in a job that runs the declared reusable workflow (another workflow of the same repository and branch does not pass), and the binding that lets those tokens act as the account. It grants the account no role on the project: what the account may do is granted elsewhere, on each resource. It never creates a GCP project, never creates a service account key, and writes nothing to GitHub. There is no cost: service accounts and workload identity federation are free.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project of the project and environment (from `gcp_environment-describe`). |
| `project=<name>` | The aleogr project name; the account is `<project>-ci`. |
| `repository=<owner>/<name>` | The GitHub repository whose CI may act as the account. |
| `repositoryId=<digits>` | GitHub's numeric id of that repository (`id` of `github_repo-describe`). |
| `ownerId=<digits>` | GitHub's numeric id of its owner (`ownerId` of `github_repo-describe`). |
| `branch=<name>` | The only branch whose runs are accepted: the repository's default branch. |
| `workflow=<owner>/<name>/.github/workflows/<file>.yml` | The reusable workflow whose jobs alone may act as the account: the deploy workflow, without `@` and what follows it. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |

Its result gives `outputs.account` and `outputs.provider`, which the repository's CI secrets name.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" gcp_ci-identity-setup <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  "${CLAUDE_PLUGIN_ROOT}/bin/aleogr-cloud-gcp" --read-only gcp_ci-identity-setup <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

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
  "action": "ci-identity-setup",
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
