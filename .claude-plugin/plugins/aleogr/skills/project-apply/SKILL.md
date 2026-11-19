---
description: aleogr project apply. Use in a project's folder to make the project's GitHub repository match the declaration `.aleogr/project.json`. Runs project-plan, takes one confirmation for the whole run (confirm=yes, or confirmVisibility=public|private when the plan changes the visibility), then creates the repository, configures it, sends the declaration as its first content and protects its default branch, and ends with a plan that says nothing to do. A local change to the declaration is proposed by pull request; after the owner merged it, the next run updates the folder and applies what the merged declaration says. Stops on an open proposal or a folder that needs attention. Never merges.
---

# project-apply

Makes the GitHub repository of the project match its declaration, `.aleogr/project.json` in the folder the skill runs in. It runs `aleogr:project-plan`, takes one confirmation for the whole plan, does what the plan lists in a fixed order by invoking the `aleogr-repo-github` skills, and runs the plan again at the end. A repository that does not exist is born in one run: created, configured, the declaration sent as its first content, then its default branch protected.

Once the repository has its declaration, a change to it follows one cycle: `project-apply` proposes the local change by pull request, the owner merges it, and the next `project-apply` updates the folder and applies what the merged declaration says. An open proposal, or a folder that needs attention, is the owner's to handle first: the run stops on it. The skill never merges.

The skill runs no `gh` or `git` command itself, and does not restate the declaration's rules: the plan validates the declaration.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `confirm=yes` | Confirms a plan that changes no visibility. |
| `confirmVisibility=<public\|private>` | Confirms a plan that creates a public repository or makes one public (`public`), or makes one private (`private`). It confirms the whole plan. |

Validate before invoking anything: `confirm` other than `yes`, `confirmVisibility` other than `public` or `private`, or any other argument, ends with `failed`, one sentence naming the argument and its allowed values, and no skill invoked.

## Steps

Show each skill invocation before making it. The skills below end with their own `aleogr-result` block: use those blocks only as input, never repeat them. Invoke only the skills these steps list, in this order, each at most once (the plan up to three times: in step 1, after an update in step 4, and in step 5), and run no command yourself (no `gh`, no `git`, no `ls`, no `cat`). Never wait for an answer: a confirmation that is missing ends the run `pending`. Your answer ends with exactly one block, its own. Never print the account name.

Below, `<owner>`, `<name>`, `<visibility>` and `<description>` are the declaration's `repo.owner`, `repo.name`, `repo.visibility` and `repo.description`, read from `.aleogr/project.json` with the Read tool once the plan has validated it. `<topics>` is the derived topic `aleogr-<project name>` plus `repo.topics`, sorted, without duplicates, comma-separated, and in double quotes when there is more than one (`topics="aleogr-demo,sample"`, `topics=aleogr-demo`). `<settings>` is the seven settings as `mergeCommit=<bool> squash=<bool> rebase=<bool> deleteBranchOnMerge=<bool> issues=<bool> wiki=<bool> projects=<bool>`, from `repo.settings`.

1. Invoke `aleogr:project-plan`. Take `outputs.items`, `outputs.exposes`, `outputs.visibility` and its `pending` items.
   - `failed`: stop with `failed`, its cause and its `pending` items. Invoke nothing else.
   - Every action is `none`: no confirmation is needed. With no argument or with `confirm=yes`, write the line `nothing to do` (in exactly those words) and end with `unchanged`. With a `confirmVisibility`, end with `failed` by the first rule of step 3. Invoke nothing else.
2. An item has the action `merge it` or `fix the folder`: the apply cannot take it (an open proposal is the owner's to merge or close, a folder that needs attention is the owner's to fix by hand). End with `pending`, nothing changed, with the plan's `pending` items (their `how` says what the owner does first), whatever the argument. Invoke nothing else.
3. Confirmation, before any change. The run is all or nothing: without the confirmation its plan needs, nothing at all is changed (the other items are not applied either). Take the first case that applies:
   - A `confirmVisibility` given when the plan has no visibility change or creation in that direction (`public` without `outputs.exposes` true; `private` without a `visibility` `update` to `private`): `failed`, nothing changed, with the sentence `confirmVisibility=<value> names a change this plan does not have: nothing was changed.` (with the value given). A `confirmVisibility` never confirms another plan, even with `confirm=yes` next to it.
   - `outputs.exposes` is `true` (the plan creates a public repository or makes one public): needs `confirmVisibility=public`. Without it: `pending`, with one sentence saying the repository would be public (its whole history visible) and that its branch protection is created once it is public, and the item `{ "item": "confirm visibility public", "reason": "manual", "how": "/aleogr:project-apply confirmVisibility=public" }`.
   - The `visibility` item has the action `update` and `outputs.visibility` is `private` (the plan makes the repository private): needs `confirmVisibility=private`. Without it: `pending`, with one sentence saying the repository would become private and its branch protection would stop being enforced on the free plan, and the item `{ "item": "confirm visibility private", "reason": "manual", "how": "/aleogr:project-apply confirmVisibility=private" }`.
   - Otherwise: needs `confirm=yes`. Without it: `pending`, with the item `{ "item": "confirm", "reason": "manual", "how": "/aleogr:project-apply confirm=yes" }`.

   A plan whose only actions are `propose` and/or `update` (the `declaration` item) exposes nothing and changes no visibility: opening a pull request and updating the folder need `confirm=yes`, and a `confirmVisibility` given with such a plan is `failed` by the first case above. On a plan stopped by `merge it` or `fix the folder`, the stop of step 2 comes first: `pending`, whatever the argument.

   With the confirmation the plan needs (`confirmVisibility=public` or `confirmVisibility=private` as above, `confirm=yes` given next to it or not), go on.
4. Act, in this order, invoking only what the plan lists. Run each skill in full, with `mode=apply`.

   First the `declaration` item, when its action is `update` or `propose` (the plan then has no other action: `settings`, `visibility` and `protection` are `not checked until the change is merged`):

   - `declaration` has the action `update` (the owner merged a change and this folder is behind):

     ```
     aleogr-repo-github:github_checkout-setup owner=<owner> name=<name> mode=apply
     ```

     - It ends `failed`, or `pending`: stop, nothing changed, with that status, its cause and its `pending` items.
     - It ends `updated` with a non-empty `pending` list (such as the item `verify`): the folder was updated but its state is not proven. Stop there with status `updated`, its cause and its `pending` items: no further step runs, and step 5 does not run.
     - Otherwise (`updated` with an empty `pending`, or `unchanged`: the folder already held the merged declaration) go on as if updated: the folder now holds the merged declaration; invoke `aleogr:project-plan` again, in full, and go on **with that new plan**. From here on, "the plan" is that new plan, and its items are the ones applied (when the checkout ended `unchanged`, nothing was changed yet: the stops below then end `pending` instead of `updated`, or `failed` for a plan that failed):
     - The new plan ends `failed`: stop, with status `updated` and the item `verify` of step 5. Invoke nothing else.
     - The new plan needs a `confirmVisibility` (`outputs.exposes` true, or a `visibility` `update` to `private`): this run was confirmed with `confirm=yes` for an update that exposes nothing, and a merged change of exposure is never applied in the run that updated the folder. Stop with status `updated` and the item of step 3 for that direction (`{ "item": "confirm visibility public", "reason": "manual", "how": "/aleogr:project-apply confirmVisibility=public" }`, or the same with `private`), with one sentence saying the repository would be public (or private) and that the next run applies it. Invoke nothing else.
     - The new plan has an item with the action `merge it` or `fix the folder`, or its `declaration` action is still `update` or `propose`: stop the same way, with status `updated` and its `pending` items (for an `update` or `propose` left, one item per such item, as in step 5). Invoke nothing else.
     - Every action is `none`: nothing else to do here; go to step 5.
     - Otherwise: carry on with its actions, by the sub-steps below, under the `confirm=yes` already given.
   - `declaration` has the action `propose` (a change in this folder, or a declaration the repository's history does not have):

     ```
     aleogr-repo-github:github_pull-request-open owner=<owner> name=<name> paths=.aleogr/project.json title="Change the project declaration" mode=apply
     ```

     - `created`: the change is proposed. The run ends here, with status `updated` and the `pending` item `{ "item": "pull request #<n> is open", "reason": "manual", "how": "merge <url>, then run /aleogr:project-apply confirm=yes" }`, with the `number` and `url` of its `outputs.pullRequest` (plus its own `pending` items, if any, such as `return this folder to the default branch`). No other sub-step runs and step 5 does not run: the next run, after the merge, applies the change. The answer says that the folder shows the merged state again (the proposed declaration lives in the pull request and in the local branch, which is kept) until the owner merges.
     - Any other ending: stop with its cause, in one sentence, and its `pending` items. `updated` (the branch was pushed but no pull request opened): status `updated`. `pending` or `failed`: that status, nothing changed on GitHub; the folder may have been changed all the same (this checkout's identity set, a fast-forward of the default branch, a local `aleogr/change-*` branch with the commit after a refused push), and the answer relays what the pull request skill said it left in the folder, never "nothing changed" alone. `unchanged` (it found nothing to commit): `failed`, nothing changed, with the item `{ "item": "declaration", "reason": "manual", "how": "/aleogr:project-plan" }`. Step 5 does not run.

   Then, in this order:

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

   A step whose item the plan marked `none` (and that the rules above do not call for) is skipped. Any step that ends `failed`, or with the status `pending`, or with a non-empty `pending` list (other than the plan limit above): stop. Invoke no later step of this list; the answer carries the step's cause, in one sentence, and its `pending` items. A step that ends `created` or `updated` changed something; a stop after such a step still goes to step 5, a stop before any change ends the run here (with the stopping step's status, `failed` or `pending`, whichever step it was).
5. Invoke `aleogr:project-plan` again, in full, whenever step 4 ran to its end or changed something (except where step 4 says that step 5 does not run, or stops with the plan it ran after an update): its own reads are the proof. Only if every action in that last plan is `none`, write the line `nothing to do`, in exactly those words. Otherwise list each item that still has an action, and never write those words.
   - That plan ends `failed`: the run keeps the status of what was done (`created` or `updated`) and adds the `pending` item `{ "item": "verify", "reason": "manual", "how": "/aleogr:project-plan" }`. When nothing was changed, the status is `failed` with that same item.
   - Every step of step 4 ended `unchanged` (nothing was changed although the first plan listed actions): the last plan decides. `nothing to do`: `unchanged`. Otherwise `pending`, with one item per item it still lists.

## Answer

In every ending: the table of the first plan (item, state, action), what each step of step 4 did (skill and status), the table of the last plan with the lines it printed under it (such as `main is held by the working rule, not by GitHub.`), and the result block. After an update, the table of the plan run after it too. On `failed` or `pending` before any change: the plan's table, the one sentence of the cause, and the `how` that unblocks it. After a proposal: the plan's table, the pull request's number and address, that the folder shows the merged state again until the owner merges, and the `how` of the `pending` item.

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
    ],
    "pullRequest": null
  },
  "cost": { "fixed": false, "notes": "no cost" },
  "pending": []
}
```

Write each item of `outputs.items` on one line, as in the example.

- `mode` is always `apply`.
- `status`:
  - `created`: the repository was created in this run (whatever happened after).
  - `updated`: something else changed in this run (a step ended `created` or `updated`: a pull request opened or a branch pushed, the folder updated, the repository configured or protected) and the repository was not created.
  - `unchanged`: nothing was changed and a plan says `nothing to do`: every action of the first plan was `none`, or every step of step 4 ended `unchanged` and the last plan says `nothing to do`.
  - `pending`: nothing was changed, and something is left: a missing confirmation, `merge it` or `fix the folder`, the proposal or a step of step 4 that ended with the status `pending` when no earlier step had changed anything, or every step ended `unchanged` and the last plan still lists an action.
  - `failed`: nothing was changed: an argument broke a rule, the first plan failed, a `confirmVisibility` named a change the plan does not have, the proposal found nothing to commit, a step of step 4 ended `failed` when no earlier step had changed anything, or nothing was changed and the last plan failed.
  - When a step stopped the run after something was changed, or the last plan still has an action other than `none`, the status is `created` or `updated` (it says what was done) and what is left is in `pending`.
- `outputs` has the same five keys in every ending:
  - `project`: the declaration's `name`; `repository`: `<owner>/<name>`. Both `null` when the plan failed on the declaration (missing or invalid) or before it was read.
  - `url`: `https://github.com/<owner>/<name>` when the repository exists at the end of the run (by the last plan, or created in this run); `null` otherwise.
  - `items`: the items of the last plan this run invoked, as it gave them: the plan of step 5 when it ran, otherwise the plan run after an update when it ran, otherwise the plan of step 1. `[]` when that plan failed or when no plan was invoked.
  - `pullRequest`: `{ "number": <n>, "url": "<url>" }` of the pull request this run opened (the `number` and `url` of `outputs.pullRequest` of `github_pull-request-open` when it ended `created`); `null` in every other ending.
- `pending`, items `{ "item": "<what>", "reason": "<reason>", "how": "<text>" }`:
  - A missing confirmation: the one item of step 3.
  - `merge it` or `fix the folder`: the plan's items, as it gave them (also when the plan run after an update has them).
  - A proposal opened: the item `pull request #<n> is open` of step 4, plus the pull request skill's own items, if any.
  - A merged change of exposure after an update: the item `confirm visibility <value>` of step 4.
  - `failed`: one item `{ "item": "<what failed>", "reason": "manual", "how": "<fix>" }`: for an argument, `item` `arguments` and the allowed values; for the plan, its item as it gave it; for a `confirmVisibility` the plan does not need, `item` `confirm visibility` and the confirmation this plan needs (`/aleogr:project-apply confirm=yes`, or the other `confirmVisibility`); for a step, its item (`repository`, `settings`, `declaration` or `protection`) and its cause, plus the step's own `pending` items.
  - A step that stopped the run after a change: its cause as one item, as above, plus its own `pending` items.
  - The last plan still has an action other than `none`: one item per such item, `{ "item": "<item>", "reason": "manual", "how": "<the confirmation it needs, as in step 3, or the plan's how>" }`.
  - The last plan failed: the item `verify` of step 5.
  - `nothing to do` (in this run or from the first plan): `[]`. The plan limit of a private repository is not an item: the last plan shows it as `not available on this plan`, with its line under the table.
- `resources` is `[{ "type": "repository", "id": "<owner>/<name>", "name": "<name>" }]` when `url` is not `null`, `[]` otherwise.
- `cost` is always `{ "fixed": false, "notes": "no cost" }`. The block never holds the account name.
