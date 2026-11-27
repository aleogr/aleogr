---
description: Google Cloud (GCP) deploy setup. Use to make each component of an aleogr project run, in the GCP project of an environment, as a Cloud Run service as declared - created with the placeholder image in one command that keeps it behind the login (IAP) and never public, with its own account, no instance always on and billing by request - and to let the CI account replace its image (roles on that service and that account only, never on the project) and the person running it get in. Sets the settings it is given, in their own command, last. Repairs an existing service that differs without ever changing its image. Idempotent; plan by default.
allowed-tools: Bash(aleogr-cloud-gcp --read-only gcp_deploy-setup), Bash(aleogr-cloud-gcp --read-only gcp_deploy-setup *)
---

# gcp_deploy-setup

Makes each component's Cloud Run service `<project>-<component>` exist as declared in one GCP project. A missing service is created with the placeholder image, behind the login from its first moment: one `gcloud run deploy` with `--no-allow-unauthenticated --iap`. An existing service that differs is repaired with only the settings that differ, and its image is never changed: replacing the image is CI's job. The CI account gets `roles/run.developer` on each service and `roles/iam.serviceAccountUser` on each service's account, never a role on the project, and the active `gcloud` account (the person running this) gets `roles/iap.httpsResourceAccessor` on each service, so that it can get in through the login. The settings (environment variables) given in `env` are set last, in their own command, without touching the image; a setting it was not given is never removed, changed or reported.

Before it makes anything, a security pass closes every existing service that is open (to anyone through its login, or to anyone through its access policy) or without the login. It never passes `--allow-unauthenticated`, `--no-iap`, `--no-invoker-iam-check` or `--ingress`, never passes `--image` to an existing service, never adds `allUsers` or `allAuthenticatedUsers` to anything, never sets a minimum above 0, never deletes a service or an account, never removes or replaces a setting (no `--set-env-vars`, `--remove-env-vars`, `--clear-env-vars` or `--env-vars-file`), and never runs `set-iam-policy`. There is no fixed cost: with a minimum of 0 instances and billing by request, a service costs only while it answers requests.

## Arguments

Free text after the skill name, as `key=value` pairs. All are required except `mode` and `env`.

| Argument | Meaning |
|---|---|
| `projectId=<id>` | The GCP project of the project and environment (from `gcp_environment-describe`). |
| `project=<name>` | The aleogr project name. |
| `environment=<name>` | The environment: `dev`, `hom` or `prd`. |
| `region=<region>` | The region of the services, for example `us-central1`. |
| `components=<name>[,<name>…]` | The components, in the declaration's order; each runs as the service `<project>-<name>`. |
| `maxInstances=<n>` | The maximum number of instances of each service. |
| `cpu=<n>` | The CPU of each service. |
| `memory=<size>` | The memory of each service, such as `512Mi`. |
| `ciAccount=<e-mail>` | The CI account (`<project>-ci@<projectId>.iam.gserviceaccount.com`, from `gcp_ci-identity-setup`). |
| `placeholderImage=<image>` | The image a new service starts with, until CI deploys the component's own: Google's hello sample. |
| `mode=plan\|apply` | `plan` (default) reports and changes nothing; `apply` executes. |
| `env=<component>:<NAME>=<value>[;<component>:<NAME>=<value>…]` | Optional: settings (environment variables) a service must hold, each for one component, `;` between them. Given, each one is part of that service's "as declared" and is set when it is missing or holds another value. Without it, no setting is read, compared or set. It may be written in double quotes (`env="…"`); the quotes are not part of it. |

One run waits at most eight minutes in all (`sleep 30` at a time, run by the command itself, while a new service's account becomes usable): when that is spent before every new service is made, the run ends with an item that says to run it again with the same arguments and `mode=apply`, and the next run goes on from what exists.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-cloud-gcp gcp_deploy-setup <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-cloud-gcp --read-only gcp_deploy-setup <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

An argument given with its value in double quotes (`env="web:A=1;web:B=2"`) is one argument whose value is the text inside them: write it `'env=web:A=1;web:B=2'`, without the double quotes.

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
  "action": "deploy-setup",
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
