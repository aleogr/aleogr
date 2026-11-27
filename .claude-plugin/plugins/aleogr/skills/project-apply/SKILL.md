---
description: aleogr project apply. Use in a project's folder to make the project's GitHub repository match the declaration `.aleogr/project.json`. Runs project-plan, takes one confirmation for the whole run (confirm=yes, or confirmVisibility=public|private when the plan changes the visibility), then creates the repository, configures it, sends the declaration as its first content and protects its default branch, and ends with a plan that says nothing to do. A local change to the declaration is proposed by pull request; after the owner merged it, the next run updates the folder and applies what the merged declaration says in the same run, under the same confirmation; a proposal that adds an environment says, in the answer and in the pull request, that applying it after the merge creates a GCP project, whose id is permanent. Where APIs it has just enabled still refuse, it waits and tries again by itself. Declared components get their Go starting points and the project's CI file written in this folder and proposed with the declaration in the same pull request; once that CI file is on the default branch, the protection is made to require the check ci. When the merged declaration has the environment dev, the same confirmation also makes its ground on Google Cloud: the GCP project, its APIs, the Docker image repository with its cleanup policy, and a keyless CI identity that may push images to it; with components, once the login of the organization is prepared, it also creates each component's Cloud Run service behind the login, with the placeholder image, sets the repository's CI secrets, and then proposes the Dockerfiles and the CI file with its deploy jobs in one pull request, so that the merge deploys. When a component declares the database, the same confirmation makes, once the services exist, its database on the shared instance, the database user of each such component's service account with its two connection roles (no password), and the services' three database settings, starting the shared instance first when it is stopped and something must be made in it (the answer then says that it runs, charged by the hour, until the night stop), and proposes the database check (go_setup database=yes) with the rest of the code. Stops on an open proposal or a folder that needs attention, and leaves to the owner what the plan says to fix by hand. Never merges.
---

# project-apply

Makes the GitHub repository of the project match its declaration, `.aleogr/project.json` in the folder the skill runs in, and, when the declaration has the environment `dev`, its ground on Google Cloud: the GCP project, its APIs, the image repository, the CI identity and, with components, their Cloud Run services behind the login, the repository's CI secrets and, for a component that declares the database, its database on the shared instance. It runs `aleogr:project-plan` first, takes one confirmation for the whole run, makes what the plan lists in a fixed order through the other plugins' skills, and runs the plan again at the end. A local change to the declaration, with the code it generates, is proposed by pull request; after the owner merged it, the next run updates the folder and applies what the merged declaration says, under the same confirmation. An open proposal, or a folder that needs attention, stops the run, and what the plan says to fix by hand is left to the owner. The GCP project's id is permanent: its creation is announced at the proposal and before the run that makes it.

The skill never merges: it opens the pull request, and merging it is the owner's.

Nothing it makes in Google Cloud has a fixed cost: a service has no instance always on and is billed by request. The one cost is the shared database instance. When a component declares the database, something must be made in it and the instance is stopped, the confirmed run starts it (about twelve minutes) and waits until it accepts calls; it then runs, charged by the hour, until the night stop, and the answer says so. That start needs `confirm=yes` itself: a `confirmVisibility` alone never confirms it. The instance is never started otherwise, and never stopped.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `confirm=yes` | Confirms a plan that changes no visibility. |
| `confirmVisibility=<public\|private>` | Confirms a plan that creates a public repository or makes one public (`public`), or makes one private (`private`). It confirms the whole plan. |

Without the confirmation its plan needs, the run changes nothing: it only reads, and its answer says what a confirmed run would make and ends `pending` with the command that confirms it. `confirm` other than `yes`, `confirmVisibility` other than `public` or `private`, or any other argument, ends `failed` before any skill is invoked.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
aleogr project-apply <arguments>
```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds: never in the background.

Write each argument inside single quotes, whatever it holds (`'confirm=yes'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is its answer, ending with one fenced `aleogr-result` block.

A run may take more than one command. After a command ends, look at the `status` in its `aleogr-result` block. When it is `continue`, show the owner only the first line of that answer (the line that says what the run waits for, such as `Waiting for the shared instance: try 14 of 30.`), then run, with the Bash tool, again in the foreground with the same `timeout` of 600000 milliseconds, exactly the command written after `next: ` in that answer, character for character, and look at its status in the same way; repeat. Never change, reorder, re-quote or drop an argument of the `next:` command, never add `confirm=yes` or any other argument yourself, never run anything else between two commands (no other command, no file read), never answer the owner or stop while the status is `continue`, and never run a `next:` command more than once. A run has at most eight commands: the command itself ends the run at that bound.

When the status is anything else, that command's answer is this skill's answer: give it exactly as printed, character for character, the fenced block included and last. The `continue` answers before it are not part of it. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command again, whatever it printed.

Only when a command (the first or a `next:` one) printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command aleogr ended without an answer: it may have changed something before it stopped. Read the state (run /aleogr:project-plan) before running it again. An instance that runs is charged by the hour: stop it with /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "project-apply",
  "mode": "apply",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "the run may have changed something" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr, then try again" } ]
}
```
