---
description: GitHub repository create, with the gh CLI. Use to create a GitHub repository with a README (so `main` exists from the start), a description and topics, then verify it. Idempotent (an existing repository is never changed; what differs is reported for github_repo-configure); plan by default; private by default, and a public repository needs confirmVisibility=public.
---

# github_repo-create

Creates a GitHub repository with the `gh` CLI, with a README, an optional description and optional topics, and verifies it. An existing repository is never changed: the skill reports what differs from the arguments, and `github_repo-configure` is the skill that corrects it.

## Arguments

Free text after the skill name, as `key=value` pairs. A value with spaces is written in quotes (`description="Status pages, per tenant"`).

| Argument | Meaning |
|---|---|
| `owner=<owner>` | The user or organization that owns the repository. Required. |
| `name=<name>` | The repository name. Required. |
| `visibility=<public\|private>` | Visibility of the new repository. Default `private`. |
| `confirmVisibility=public` | Confirms that the repository is created public. Needed by `apply` with `visibility=public`. |
| `description=<text>` | Description of the repository. Optional. |
| `topics=<t1>,<t2>` | Topics, comma-separated. Optional. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` creates. |

`owner` and `name` are required: a missing `owner` or `name` ends with the result block with `status` `failed` and one sentence saying which is missing, with no command (do not ask for it). Validate before any command; a value that breaks a rule ends with the result block with `status` `failed`, one sentence saying which rule failed, and no command:

- `owner` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-`, and does not start or end with `-`.
- `name` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-`, and is not `.` or `..`.
- `visibility`, when given, is `public` or `private`.
- `confirmVisibility`, when given, is equal to `visibility` (after the default), and `visibility` is `public`. `confirmVisibility=public` with `visibility=private` (or with no `visibility`) fails; so does `confirmVisibility=private`.
- `description`, when given, is not empty and has no line break, no `"`, no backtick, no `$` and no `\` (they could break out of the quotes of the command).
- `topics`, when given, is split on `,`; each topic has 1 to 50 characters of `a-z`, `0-9` and `-`, and starts with a letter or a digit (no capitals, no `_`, no spaces, no empty item). Repeated topics count once.
- `mode`, when given, is `plan` or `apply`.

## Steps

Show each command before running it. Run only the commands below, in this order, each step's command at most once (the read of step 1 runs again as the verification of step 6): no `gh auth status`, no `gh repo view`, no other `gh` command, no retry. Never print the account name or the token. In commands, the description is always in double quotes.

1. Read the repository:

   ```
   gh api repos/<owner>/<name>
   ```

   Read the exit code and the output, then take the first case that applies:

   - `gh` is not installed (`command not found`, or the command cannot start): `failed`. Say in one sentence that `gh` must be installed. Run nothing else.
   - The output names authentication (`gh auth login`, not logged in, bad credentials, HTTP 401): `failed`. Say in one sentence that `gh` is not logged in and that the fix is `gh auth login`. Run nothing else.
   - Non-zero exit and the output contains `HTTP 404`: the repository does not exist (or this account cannot see it). This is the only answer that means "does not exist". Go to step 3.
   - Any other non-zero exit (HTTP 403, 5xx, network error, anything else): `failed`. The state is unknown: never report it as "does not exist" and never create. Say the cause in one sentence, with no raw error text. Run nothing else.
   - Exit 0: the repository exists. Go to step 2.

2. The repository exists: change nothing, in `plan` and in `apply`, whatever the arguments ask. `status` is `unchanged`. From the JSON take `html_url`, `ssh_url`, `visibility`, `default_branch`, `description` and `topics`, and build `differences`, in this order, from the names whose value differs:

   - `visibility`: only when `visibility` was given (the default `private` is not compared).
   - `description`: only when `description` was given; differs when it is not exactly the repository's `description`.
   - `topics`: only when `topics` was given; differs when the set of given topics is not the repository's set of `topics` (order does not matter).

   When `differences` is not empty, the answer names each difference (asked and found) and says that `github_repo-configure` corrects them. Run nothing else.

3. The repository does not exist.

   - `plan`: `status` `would-create`. Show the commands of steps 4 and 5 that `apply` would run, without running them. Run nothing else.
   - `apply` with `visibility=public` and no `confirmVisibility=public`: ask the owner "Create `<owner>/<name>` as PUBLIC?" and stop. Do not wait for an answer and do not create anything: end this run with the result block with `status` `pending` and one `pending` item `confirm visibility public`, whose `how` is this same invocation plus `confirmVisibility=public`. If the owner answers yes later in this conversation, run the skill again with `confirmVisibility=public`; any other answer creates nothing.
   - `apply` otherwise (private, or public with `confirmVisibility=public`): go to step 4.

4. Create the repository with a README, private or public as requested, adding `--description` only when `description` was given:

   ```
   gh repo create <owner>/<name> --private --add-readme --description "<description>"
   ```

   (`--public` instead of `--private` when `visibility=public`.) A non-zero exit stops with `failed`: nothing was created. Say the cause in one sentence (for example, that the account has no permission to create repositories in `<owner>`), with no raw error text. Run nothing else. From here on the repository exists: the status is `created` whatever happens in steps 5 and 6, and any problem there becomes an item in `pending`.

5. Only when `topics` was given, add them in one command, one `--add-topic` flag per topic:

   ```
   gh repo edit <owner>/<name> --add-topic <t1> --add-topic <t2>
   ```

   A non-zero exit: say so in one sentence, with no raw error text, add one `pending` item `topics` whose `how` is `/aleogr-repo-github:github_repo-configure owner=<owner> name=<name> topics="<t1>,<t2>" mode=apply`, and go on to step 6.

6. Verify, once:

   ```
   gh api repos/<owner>/<name>
   ```

   The status stays `created`. Check that the exit is 0, `visibility` is the requested one, the description is the given one (when given) and every given topic is in `topics`. Anything else is said in one sentence and becomes items in `pending`, each problem once:

   - The read fails: one item `verify` whose `how` is `/aleogr-repo-github:github_repo-describe owner=<owner> name=<name>`.
   - A wrong visibility, a wrong description, or missing topics: one item `configure` whose `how` is `/aleogr-repo-github:github_repo-configure owner=<owner> name=<name>` plus the arguments that differ (`description="<description>"`, `topics="<t1>,<t2>"`, `visibility=<visibility>`), plus `mode=apply`. Topics already covered by the `topics` item of step 5 are not repeated here; when nothing else differs, there is no `configure` item.

Then answer in a few lines: what was done (or would be done), the repository URL, visibility and default branch when known, the differences (with the pointer to `github_repo-configure`) when it already existed, and the result block.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "repo",
  "provider": "github",
  "action": "repo-create",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "repository", "id": "<owner>/<name>", "name": "<name>" }
  ],
  "outputs": {
    "url": "https://github.com/<owner>/<name>",
    "sshUrl": "git@github.com:<owner>/<name>.git",
    "visibility": "private",
    "defaultBranch": "main",
    "topics": ["<topic>"],
    "differences": []
  },
  "cost": { "fixed": false, "notes": "private repositories of a free organization use the 2,000 Actions minutes a month" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of:
  - `would-create`: `plan`, the repository does not exist.
  - `created`: `gh repo create` succeeded in this run, whatever happened after it. A failed topics command, or a verification that failed or differs, is reported as items in `pending`: `created` with a non-empty `pending` is allowed.
  - `unchanged`: the repository already existed (in `plan` or `apply`); nothing was done.
  - `pending`: only when nothing was done and the run waits for the visibility confirmation (`apply`, `visibility=public`, no `confirmVisibility=public`).
  - `failed`: an argument missing or broke a rule, `gh` missing or not logged in, the read of step 1 refused, or the create refused. Nothing was created.
- Values read from GitHub come only from the commands' output: `url` from `html_url`, `sshUrl` from `ssh_url`, `visibility` from `visibility` (`public`, `private` or `internal`), `defaultBranch` from `default_branch`, `topics` from `topics` (sorted). `differences` holds only the names `visibility`, `description`, `topics`, in that order.
- Each `pending` item is `{ "item": "<what>", "reason": "manual", "how": "<text>" }`. `pending` has items only with `created` (the items of steps 5 and 6) and with the status `pending` (the one item `confirm visibility public`); it is `[]` otherwise. In a suggested command, a value with a comma or a space is in double quotes (`topics="a,b"`).
- The shape for each ending:
  - `created`: `resources` has the repository; `outputs` comes from the read of step 6 when it exited 0, otherwise `{ "url": "https://github.com/<owner>/<name>", "sshUrl": "git@github.com:<owner>/<name>.git", "visibility": "<requested visibility>", "defaultBranch": null, "topics": [], "differences": [] }` (built from the arguments); `differences` is always `[]`; `pending` has the items of steps 5 and 6, if any.
  - `unchanged`: `resources` has the repository; `outputs` comes from the read of step 1, with `differences` as in step 2 (`[]` when nothing differs).
  - `would-create`: `resources` is empty; `outputs` is `{ "url": null, "sshUrl": null, "visibility": "<requested visibility>", "defaultBranch": null, "topics": [<given topics, sorted>], "differences": [] }`.
  - `pending` because public was not confirmed: `resources` is empty; `outputs` as for `would-create`; `pending` has the one item `confirm visibility public`.
  - `failed` (an argument missing or broke a rule, `gh` missing or not logged in, the read of step 1 refused, or the create refused): `resources` is empty and `outputs` is `{ "url": null, "sshUrl": null, "visibility": null, "defaultBranch": null, "topics": [], "differences": [] }`. A failed read never says the repository does not exist.
- `cost` is always `"fixed": false`. For `would-create`, `pending` and `failed` (nothing was created) `notes` is `"no cost: nothing was created"`. For `created` and `unchanged`, `notes` is `"no cost"` when `outputs.visibility` is `public`, and `"private repositories of a free organization use the 2,000 Actions minutes a month"` otherwise (`private` or `internal`).
