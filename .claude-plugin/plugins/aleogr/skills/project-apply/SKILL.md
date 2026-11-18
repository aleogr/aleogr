---
description: aleogr project apply. Use in a project's folder to make the project's GitHub repository match the declaration `.aleogr/project.json`. Runs project-plan, takes one confirmation for the whole run (confirm=yes, or confirmVisibility=public|private when the plan changes the visibility), then creates the repository, configures it, sends the declaration as its first content and protects its default branch, and ends with a plan that says nothing to do.
---

# project-apply

Makes the GitHub repository of the project match its declaration, `.aleogr/project.json` in the folder the skill runs in. It runs `aleogr:project-plan`, takes one confirmation for the whole plan, does what the plan lists in a fixed order by invoking the `aleogr-repo-github` skills, and runs the plan again at the end. A repository that does not exist is born in one run: created, configured, the declaration sent as its first content, then its default branch protected.

The skill runs no `gh` or `git` command itself, and does not restate the declaration's rules: the plan validates the declaration.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `confirm=yes` | Confirms a plan that changes no visibility. |
| `confirmVisibility=<public\|private>` | Confirms a plan that creates a public repository or makes one public (`public`), or makes one private (`private`). It confirms the whole plan. |

Validate before invoking anything: `confirm` other than `yes`, `confirmVisibility` other than `public` or `private`, or any other argument, ends with `failed`, one sentence naming the argument and its allowed values, and no skill invoked.

## Steps

Show each skill invocation before making it. The skills below end with their own `aleogr-result` block: use those blocks only as input, never repeat them. Invoke only the skills these steps list, in this order, each at most once (the plan twice), and run no command yourself (no `gh`, no `git`, no `ls`, no `cat`). Never wait for an answer: a confirmation that is missing ends the run `pending`. Your answer ends with exactly one block, its own. Never print the account name.

Below, `<owner>`, `<name>`, `<visibility>` and `<description>` are the declaration's `repo.owner`, `repo.name`, `repo.visibility` and `repo.description`, read from `.aleogr/project.json` with the Read tool once the plan has validated it. `<topics>` is the derived topic `aleogr-<project name>` plus `repo.topics`, sorted, without duplicates, comma-separated, and in double quotes when there is more than one (`topics="aleogr-demo,sample"`, `topics=aleogr-demo`). `<settings>` is the seven settings as `mergeCommit=<bool> squash=<bool> rebase=<bool> deleteBranchOnMerge=<bool> issues=<bool> wiki=<bool> projects=<bool>`, from `repo.settings`.

1. Invoke `aleogr:project-plan`. Take `outputs.items`, `outputs.exposes`, `outputs.visibility` and its `pending` items.
   - `failed`: stop with `failed`, its cause and its `pending` items. Invoke nothing else.
   - Every action is `none`: no confirmation is needed. With no argument or with `confirm=yes`, write the line `nothing to do` (in exactly those words) and end with `unchanged`. With a `confirmVisibility`, end with `failed` by the first rule of step 3. Invoke nothing else.
2. An item has the action `merge first` or `open a pull request`: the apply cannot take it. End with `pending`, nothing changed, with the plan's `pending` items (their `how` says what the owner does first). Invoke nothing else.
3. Confirmation, before any change. The run is all or nothing: without the confirmation its plan needs, nothing at all is changed (the other items are not applied either). Take the first case that applies:
   - A `confirmVisibility` given when the plan has no visibility change or creation in that direction (`public` without `outputs.exposes` true; `private` without a `visibility` `update` to `private`): `failed`, nothing changed, with one sentence saying that the confirmation names a change this plan does not have. A `confirmVisibility` never confirms another plan, even with `confirm=yes` next to it.
   - `outputs.exposes` is `true` (the plan creates a public repository or makes one public): needs `confirmVisibility=public`. Without it: `pending`, with one sentence saying the repository would be public (its whole history visible), and the item `{ "item": "confirm visibility public", "reason": "manual", "how": "/aleogr:project-apply confirmVisibility=public" }`.
   - The `visibility` item has the action `update` and `outputs.visibility` is `private` (the plan makes the repository private): needs `confirmVisibility=private`. Without it: `pending`, with one sentence saying the repository would become private and its branch protection would stop being enforced on the free plan, and the item `{ "item": "confirm visibility private", "reason": "manual", "how": "/aleogr:project-apply confirmVisibility=private" }`.
   - Otherwise: needs `confirm=yes`. Without it: `pending`, with the item `{ "item": "confirm", "reason": "manual", "how": "/aleogr:project-apply confirm=yes" }`.

   With the confirmation the plan needs (`confirmVisibility=public` or `confirmVisibility=private` as above, `confirm=yes` given next to it or not), go on.
4. Act, in this order, invoking only what the plan lists. Run each skill in full, with `mode=apply`.
   1. `repository` has the action `create`:

      ```
      aleogr-repo-github:github_repo-create owner=<owner> name=<name> visibility=<visibility> description="<description>" topics=<topics> mode=apply
      ```

      plus `confirmVisibility=public` when `<visibility>` is `public`. It must end `created` with an empty `pending`.
   2. `settings` has the action `update` or `visibility` has the action `update`, or the repository was created in this run:

      ```
      aleogr-repo-github:github_repo-configure owner=<owner> name=<name> description="<description>" topics=<topics> <settings> mode=apply
      ```

      When `visibility` has the action `update`, the same call adds `visibility=<visibility> confirmVisibility=<visibility>`. It must end `updated` or `unchanged`, with an empty `pending`.
   3. `declaration` has the action `send`, or the repository was created in this run:

      ```
      aleogr-repo-github:github_checkout-setup owner=<owner> name=<name> mode=apply
      ```

      It must end `created` or `unchanged`, with an empty `pending`.
   4. `protection` has the action `create` or `update`, or the repository was created in this run, or this run made it public (the plan checks the protection again once the repository is public):

      ```
      aleogr-repo-github:github_branch-protect owner=<owner> name=<name> mode=apply
      ```

      It must end `created`, `updated` or `unchanged`, with an empty `pending`. When `<visibility>` is `private` and it ends `pending` with the item whose `reason` is `plan-limit`, that is the expected end on a private repository: it does not stop the run.

   A step whose item the plan marked `none` (and that the rules above do not call for) is skipped. Any step that ends `failed`, or with the status `pending`, or with a non-empty `pending` list (other than the plan limit above): stop. Invoke no later step of this list; the answer carries the step's cause, in one sentence, and its `pending` items. A step that ends `created` or `updated` changed something; a stop after such a step still goes to step 5, a stop before any change ends the run here.
5. Invoke `aleogr:project-plan` again, in full, whenever step 4 changed something: its own reads are the proof. Only if every action in that last plan is `none`, write the line `nothing to do`, in exactly those words. Otherwise list each item that still has an action, and never write those words.

## Answer

In every ending: the table of the first plan (item, state, action), what each step of step 4 did (skill and status), the table of the last plan with the lines it printed under it (such as `main is held by the working rule, not by GitHub.`), and the result block. On `failed` or `pending` before any change: the plan's table, the one sentence of the cause, and the `how` that unblocks it.

## Result block

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "project-apply",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "repository", "id": "example-org/demo", "name": "demo" }
  ],
  "outputs": {
    "project": "demo",
    "repository": "example-org/demo",
    "url": "https://github.com/example-org/demo",
    "items": [
      { "item": "repository", "state": "exists", "action": "none" },
      { "item": "settings", "state": "as declared", "action": "none" },
      { "item": "visibility", "state": "as declared", "action": "none" },
      { "item": "declaration", "state": "in the repository", "action": "none" },
      { "item": "protection", "state": "not available on this plan", "action": "none" }
    ]
  },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

Write each item of `outputs.items` on one line, as in the example.

- `mode` is always `apply`.
- `status`:
  - `created`: the repository was created in this run (whatever happened after).
  - `updated`: something else changed in this run (a step ended `created` or `updated`) and the repository was not created.
  - `unchanged`: every action of the plan was `none`; nothing was invoked after it.
  - `pending`: nothing was changed, and the run waits for the owner: a missing confirmation, `merge first` or `open a pull request`, or the first step of step 4 that ran ended with the status `pending`.
  - `failed`: nothing was changed: an argument broke a rule, the plan failed, a `confirmVisibility` named a change the plan does not have, or the first step of step 4 that ran ended `failed`.
  - When a step stopped the run after something was changed, or the last plan still has an action other than `none`, the status is `created` or `updated` (it says what was done) and what is left is in `pending`.
- `outputs` has the same four keys in every ending:
  - `project`: the declaration's `name`; `repository`: `<owner>/<name>`. Both `null` when the plan failed on the declaration (missing or invalid) or before it was read.
  - `url`: `https://github.com/<owner>/<name>` when the repository exists at the end of the run (by the last plan, or created in this run); `null` otherwise.
  - `items`: the items of the last plan this run invoked, as it gave them: the plan of step 5 when it ran, otherwise the plan of step 1. `[]` when that plan failed or when no plan was invoked.
- `pending`, items `{ "item": "<what>", "reason": "<reason>", "how": "<text>" }`:
  - A missing confirmation: the one item of step 3.
  - `merge first` or `open a pull request`: the plan's items, as it gave them.
  - `failed`: one item `{ "item": "<what failed>", "reason": "manual", "how": "<fix>" }`: for an argument, `item` `arguments` and the allowed values; for the plan, its item as it gave it; for a `confirmVisibility` the plan does not need, `item` `confirm visibility` and the confirmation this plan needs (`/aleogr:project-apply confirm=yes`, or the other `confirmVisibility`); for a step, its item (`repository`, `settings`, `declaration` or `protection`) and its cause, plus the step's own `pending` items.
  - A step that stopped the run after a change: its cause as one item, as above, plus its own `pending` items.
  - The last plan still has an action other than `none`: one item per such item, `{ "item": "<item>", "reason": "manual", "how": "<the confirmation it needs, as in step 3, or the plan's how>" }`.
  - `nothing to do` (in this run or from the first plan): `[]`. The plan limit of a private repository is not an item: the last plan shows it as `not available on this plan`, with its line under the table.
- `resources` is `[{ "type": "repository", "id": "<owner>/<name>", "name": "<name>" }]` when `url` is not `null`, `[]` otherwise.
- `cost` is always `{ "fixed": false, "notes": "no cost" }`. The block never holds the account name.
