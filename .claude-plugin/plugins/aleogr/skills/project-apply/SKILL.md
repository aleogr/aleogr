---
description: aleogr project apply. Use in a project's folder to make the project's GitHub repository match the declaration `.aleogr/project.json`. Runs project-plan, takes one confirmation for the whole run (confirm=yes, or confirmVisibility=public|private when the plan changes the visibility), then creates the repository, configures it, sends the declaration as its first content and protects its default branch, and ends with a plan that says nothing to do. A local change to the declaration is proposed by pull request; after the owner merged it, the next run updates the folder and applies what the merged declaration says. Declared components get their Go starting points and the project's CI file written in this folder and proposed with the declaration in the same pull request; once that CI file is on the default branch, the protection is made to require the check ci. Stops on an open proposal or a folder that needs attention. Never merges.
---

# project-apply

Makes the GitHub repository of the project match its declaration, `.aleogr/project.json` in the folder the skill runs in. It runs `aleogr:project-plan`, takes one confirmation for the whole plan, does what the plan lists in a fixed order by invoking the `aleogr-repo-github` skills, and runs the plan again at the end. A repository that does not exist is born in one run: created, configured, the declaration sent as its first content, then its default branch protected.

Once the repository has its declaration, a change to it follows one cycle: `project-apply` proposes the local change by pull request, the owner merges it, and the next `project-apply` updates the folder and applies what the merged declaration says. An open proposal, or a folder that needs attention, is the owner's to handle first: the run stops on it. The skill never merges.

When the declaration has components, the code follows the same cycle. A run whose plan lists `generate` writes, in this folder, the starting point of each component that has none (`aleogr-stack-go:go_setup`) and the project's CI file `.github/workflows/ci.yml` (`github_ci-setup`), and proposes them, with the declaration, in one pull request. After the owner merged it, the next run updates the folder; the plan then finds `ci.yml` on the default branch and expects the protection to require the check `ci`, and the run updates the protection to require it. The check is required only when the plan says `ci.yml` is on the default branch (its output `checks` is `ci`): a required check that nothing reports would block every pull request of the project.

The skill runs no `gh` or `git` command itself, and does not restate the declaration's rules: the plan validates the declaration.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `confirm=yes` | Confirms a plan that changes no visibility. |
| `confirmVisibility=<public\|private>` | Confirms a plan that creates a public repository or makes one public (`public`), or makes one private (`private`). It confirms the whole plan. |

Validate before invoking anything: `confirm` other than `yes`, `confirmVisibility` other than `public` or `private`, or any other argument, ends with `failed`, one sentence naming the argument and its allowed values, and no skill invoked.

## Steps

Show each skill invocation before making it. The skills below end with their own `aleogr-result` block: use those blocks only as input, never repeat them, and after each one go on with the next step: a skill's block is never the end of this answer, which always ends with this skill's own block. Invoke only the skills these steps list, in this order, each at most once (the plan up to three times: in step 1, after an update in step 4, and in step 5; `go_setup` once per component to generate), and run no command yourself (no `gh`, no `git`, no `ls`, no `cat`). Never wait for an answer: a confirmation that is missing ends the run `pending`. Your answer ends with exactly one block, its own. Never print the account name.

Below, `<owner>`, `<name>`, `<visibility>` and `<description>` are the declaration's `repo.owner`, `repo.name`, `repo.visibility` and `repo.description`, read from `.aleogr/project.json` with the Read tool once the plan has validated it. `<topics>` is the derived topic `aleogr-<project name>` plus `repo.topics`, sorted, without duplicates, comma-separated, and in double quotes when there is more than one (`topics="aleogr-demo,sample"`, `topics=aleogr-demo`). `<settings>` is the seven settings as `mergeCommit=<bool> squash=<bool> rebase=<bool> deleteBranchOnMerge=<bool> issues=<bool> wiki=<bool> projects=<bool>`, from `repo.settings`.

With components (the declaration's `components` is a non-empty list), also, with the components sorted by `name`:

- `<components>` is the entries `<name>:<path>:<stack>:<version>` of the components, joined by `,` (`api:services/api:go:1.27,web:web:go:1.27`).
- The module of a component is `github.com/<owner>/<name>/<path>`, with the component's `path`.
- `<workflows>` is `ci.workflowsRepository` of `${CLAUDE_PLUGIN_ROOT}/defaults.json`, read with the Read tool when it is needed (the plan has already checked that it can be read).
- `<tooling paths>` is `.aleogr/project.json`, `.github/workflows/ci.yml` and, for each component, `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, in that order, joined by `,` (the same paths the plan checks). Without components, the only path is `.aleogr/project.json`.

1. Invoke `aleogr:project-plan`. Take `outputs.items`, `outputs.exposes`, `outputs.visibility`, `outputs.generate`, `outputs.checks`, `outputs.changed` and its `pending` items.
   - `failed`: stop with `failed`, its cause and its `pending` items. Invoke nothing else.
   - Every action is `none`: no confirmation is needed. With no argument or with `confirm=yes`, write the line `nothing to do` (in exactly those words) and end with `unchanged`. With a `confirmVisibility`, end with `failed` by the first rule of step 3. Invoke nothing else.
2. An item has the action `merge it` or `fix the folder`: the apply cannot take it (an open proposal is the owner's to merge or close, a folder that needs attention is the owner's to fix by hand, and so is a component folder that holds Go files but no `go.mod`, the `components` item `needs attention: <names>`). End with `pending`, nothing changed, with the plan's `pending` items (their `how` says what the owner does first), whatever the argument. Invoke nothing else.
3. Confirmation, before any change. The run is all or nothing: without the confirmation its plan needs, nothing at all is changed (the other items are not applied either). Take the first case that applies:
   - A `confirmVisibility` given when the plan has no visibility change or creation in that direction (`public` without `outputs.exposes` true; `private` without a `visibility` `update` to `private`): `failed`, nothing changed, with the sentence `confirmVisibility=<value> names a change this plan does not have: nothing was changed.` (with the value given). A `confirmVisibility` never confirms another plan, even with `confirm=yes` next to it.
   - `outputs.exposes` is `true` (the plan creates a public repository or makes one public): needs `confirmVisibility=public`. Without it: `pending`, with one sentence saying the repository would be public (its whole history visible) and that its branch protection is created once it is public, and the item `{ "item": "confirm visibility public", "reason": "manual", "how": "/aleogr:project-apply confirmVisibility=public" }`.
   - The `visibility` item has the action `update` and `outputs.visibility` is `private` (the plan makes the repository private): needs `confirmVisibility=private`. Without it: `pending`, with one sentence saying the repository would become private and its branch protection would stop being enforced on the free plan, and the item `{ "item": "confirm visibility private", "reason": "manual", "how": "/aleogr:project-apply confirmVisibility=private" }`.
   - Otherwise: needs `confirm=yes`. Without it: `pending`, with the item `{ "item": "confirm", "reason": "manual", "how": "/aleogr:project-apply confirm=yes" }`.

   A plan whose only actions are `propose` and/or `update` (the `declaration` item) and `generate` (the `components` and `ci` items) exposes nothing and changes no visibility: writing the generated files in this folder, opening a pull request and updating the folder need `confirm=yes`, and a `confirmVisibility` given with such a plan is `failed` by the first case above. On a plan stopped by `merge it` or `fix the folder`, the stop of step 2 comes first: `pending`, whatever the argument.

   With the confirmation the plan needs (`confirmVisibility=public` or `confirmVisibility=private` as above, `confirm=yes` given next to it or not), go on.
4. Act, in this order, invoking only what the plan lists. Run each skill in full, with `mode=apply`.

   First the `declaration` item, when its action is `update` or `propose`, and the generated files, when the plan has `generate` (`outputs.generate` is `true`). With the `declaration` action `update` or `propose`, `settings`, `visibility` and `protection` are `not checked until the change is merged`.

   - `declaration` has the action `update` (the owner merged a change and this folder is behind):

     ```
     aleogr-repo-github:github_checkout-setup owner=<owner> name=<name> mode=apply
     ```

     plus `head=check` exactly when the declaration has components (as the plan invokes it): a merged pull request that added code or `ci.yml` without changing the declaration leaves the declaration equal and the folder behind all the same, and only `head=check` lets the checkout see it and fast-forward the folder.

     - It ends `failed`, or `pending`: stop, nothing changed, with that status, its cause and its `pending` items.
     - It ends `updated` with a non-empty `pending` list (such as the item `verify`): the folder was updated but its state is not proven. Stop there with status `updated`, its cause and its `pending` items: no further step runs, and step 5 does not run.
     - Otherwise (`updated` with an empty `pending`, or `unchanged`: the folder already held the merged declaration) go on as if updated: the folder now holds the merged declaration; invoke `aleogr:project-plan` again, in full, and go on **with that new plan**. From here on, "the plan" is that new plan, and its items are the ones applied (when the checkout ended `unchanged`, nothing was changed yet: the stops below then end `pending` instead of `updated`, or `failed` for a plan that failed):
     - The new plan ends `failed`: stop, with status `updated` and the item `verify` of step 5. Invoke nothing else.
     - The new plan needs a `confirmVisibility` (`outputs.exposes` true, or a `visibility` `update` to `private`): this run was confirmed with `confirm=yes` for an update that exposes nothing, and a merged change of exposure is never applied in the run that updated the folder. Stop with status `updated` and the item of step 3 for that direction (`{ "item": "confirm visibility public", "reason": "manual", "how": "/aleogr:project-apply confirmVisibility=public" }`, or the same with `private`), with one sentence saying the repository would be public (or private) and that the next run applies it. Invoke nothing else.
     - The new plan has an item with the action `merge it` or `fix the folder`, or its `declaration` action is still `update` or `propose`, or it has `generate`: stop the same way, with status `updated` and its `pending` items (for an `update`, `propose` or `generate` left, one item per such item, as in step 5). Generation and a proposal are never made in the run that updated the folder. Invoke nothing else.
     - Every action is `none`: nothing else to do here; go to step 5.
     - Otherwise: carry on with its actions, by the sub-steps below, under the `confirm=yes` already given.
   - `declaration` has the action `propose` (a change in this folder, or a declaration the repository's history does not have), or the plan has `generate` (a component without its starting point in this folder, or a CI file that is missing or not as declared). These are one step and one pull request, in this order. After each skill's block, go on with the next sub-step: a skill's block never ends this answer.

     1. For each component named in the `components` state `to generate: <names>` (sorted by name; none when `components` is `none`):

        ```
        aleogr-stack-go:go_setup component=<component name> path=<component path> version=<component version> module=github.com/<owner>/<name>/<component path> mode=apply
        ```

        It must end `created` (or `unchanged`), with an empty `pending`. It ends `failed`, or `pending`, or with a non-empty `pending`: stop (below). Otherwise go on with the next component, then sub-step 2.
     2. `ci` has the action `generate`:

        ```
        aleogr-repo-github:github_ci-setup owner=<owner> name=<name> components=<components> workflows=<workflows> mode=apply
        ```

        It must end `created`, `updated` or `unchanged`, with an empty `pending`. Any other ending: stop (below). Otherwise go on with sub-step 3.
     3. Propose, in one pull request, the declaration and every file of the tooling (a file that did not change is not committed: the pull request skill commits only the named files that changed):

        ```
        aleogr-repo-github:github_pull-request-open owner=<owner> name=<name> paths=<tooling paths> title="<title>" mode=apply
        ```

        `<title>` follows what the pull request will carry: the paths of the plan's `outputs.changed` plus the files this run wrote (the `outputs.files` of each `go_setup` that ended `created`, and `.github/workflows/ci.yml` when `github_ci-setup` ended `created` or `updated`). Some `<path>/go.mod` among them: `Add the components <names> and CI`, where `<names>` are the components whose `<path>/go.mod` is among them, sorted, separated by `, ` (`Add the components api, web and CI`); a title that would pass 100 characters is `Add the components and CI`. Otherwise `.github/workflows/ci.yml` among them: `Update CI`. Otherwise `Change the project declaration`. Without components, the call is exactly `paths=.aleogr/project.json title="Change the project declaration"`.

        - `created`: the change is proposed. The run ends here, with status `updated` and the `pending` item `{ "item": "pull request #<n> is open", "reason": "manual", "how": "merge <url>, then run /aleogr:project-apply confirm=yes" }`, with the `number` and `url` of its `outputs.pullRequest` (plus its own `pending` items, if any, such as `return this folder to the default branch`). No other sub-step runs and step 5 does not run: the next run, after the merge, applies the change. When the plan also lists actions on GitHub (a `settings`, `visibility` or `protection` item with an action other than `none`, possible only with the `declaration` action `none`), they are not applied in this run: the answer says so in one sentence, and `pending` has one more item, `{ "item": "after the merge", "reason": "manual", "how": "<those items, comma-separated> wait for the run after the merge: merge the pull request, then run /aleogr:project-apply confirm=yes (or the confirmVisibility that run asks for)" }`. The answer says that the folder shows the merged state again (the proposed declaration and files live in the pull request and in the local branch, which is kept) until the owner merges.
        - Any other ending: stop with its cause, in one sentence, and its `pending` items. `updated` (the branch was pushed but no pull request opened): status `updated`. `pending` or `failed`: that status (unless sub-step 1 or 2 wrote files in this run, below), nothing changed on GitHub; the folder may have been changed all the same (this checkout's identity set, a fast-forward of the default branch, a local `aleogr/change-*` branch with the commit after a refused push), and the answer relays what the pull request skill said it left in the folder, never "nothing changed" alone. `unchanged` (it found nothing to commit): `failed`, nothing changed, with the item `{ "item": "declaration", "reason": "manual", "how": "/aleogr:project-plan" }`. Step 5 does not run.

     A stop in this list invokes nothing after it, and step 5 does not run. When sub-step 1 or 2 wrote files in this run (a `go_setup` that ended `created`, a `github_ci-setup` that ended `created` or `updated`), the folder was changed: the status is `updated` (never `pending` or `failed`), and the stop's item is `{ "item": "<what stopped>", "reason": "manual", "how": "<its cause>; the files written in this folder are kept: run /aleogr:project-apply confirm=yes again, which proposes them" }`, plus the stopping skill's own `pending` items; `<what stopped>` is the component's name for a `go_setup`, `ci` for `github_ci-setup`, `declaration` for the pull request. When nothing was written, a stop of sub-step 1 or 2 ends with that skill's status (`failed` or `pending`), its cause as the item (`item` the component's name or `ci`), and its own `pending` items. A cause is always said in one sentence in this skill's own words: never the raw error text of a skill or a command (no HTTP code, no API message). Either way the answer names the files written in this run and says what the owner sees and does: the written files stay in this folder, uncommitted; the next run's plan sees them (`components` and `ci` `as declared`, the `declaration` `changed here` / `propose`) and proposes them, with whatever is still to generate, in one pull request.

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

      plus `checks=ci` exactly when the plan's `outputs.checks` is `ci` (after an update, the `checks` of the plan run after it): `ci.yml` is then on the repository's default branch, and the plan computed the `protection` row with the check `ci`. Never add `checks=ci` for any other reason (not because the declaration has components, nor because `ci.yml` is in this folder): a required check that no workflow of the default branch reports blocks every pull request of the project. It must end `created`, `updated` or `unchanged`, with an empty `pending`. When `<visibility>` is `private` and it ends `pending` with the item whose `reason` is `plan-limit`, that is the expected end on a private repository: it does not stop the run.

   A step whose item the plan marked `none` (and that the rules above do not call for) is skipped. Any step that ends `failed`, or with the status `pending`, or with a non-empty `pending` list (other than the plan limit above): stop. Invoke no later step of this list; the answer carries the step's cause, in one sentence, and its `pending` items. A step that ends `created` or `updated` changed something; a stop after such a step still goes to step 5, a stop before any change ends the run here (with the stopping step's status, `failed` or `pending`, whichever step it was).
5. Invoke `aleogr:project-plan` again, in full, whenever step 4 ran to its end or changed something (except where step 4 says that step 5 does not run, or stops with the plan it ran after an update): its own reads are the proof. Only if every action in that last plan is `none`, write the line `nothing to do`, in exactly those words. Otherwise list each item that still has an action, and never write those words.
   - That plan ends `failed`: the run keeps the status of what was done (`created` or `updated`) and adds the `pending` item `{ "item": "verify", "reason": "manual", "how": "/aleogr:project-plan" }`. When nothing was changed, the status is `failed` with that same item.
   - Every step of step 4 ended `unchanged` (nothing was changed although the first plan listed actions): the last plan decides. `nothing to do`: `unchanged`. Otherwise `pending`, with one item per item it still lists.
   - The last plan lists `generate` (a declaration born with components in this run: the repository was created, configured, sent its declaration and protected without the check `ci`, and the code comes next): the run keeps its status (`created`) and has, for each item with the action `generate`, the `pending` item `{ "item": "<item>", "reason": "manual", "how": "run /aleogr:project-apply confirm=yes to generate the components" }`. Generation is never made in the run that created the repository.

## Answer

In every ending: the table of the first plan (item, state, action), what each step of step 4 did (skill and status), the table of the last plan with the lines it printed under it (such as `main is held by the working rule, not by GitHub.`), and the result block. After an update, the table of the plan run after it too. On `failed` or `pending` before any change: the plan's table, the one sentence of the cause, and the `how` that unblocks it. A missing confirmation on a plan with `generate` also names the files the confirmed run would write in this folder: for each component of `to generate: <names>`, `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, and `.github/workflows/ci.yml` when `ci` has the action `generate`. After a proposal: the plan's table, what each skill of the proposal did (each `go_setup`, `github_ci-setup`, the pull request), the invocation of `github_pull-request-open` as it was made (with its `paths=` and `title=`), the files written in this folder, the pull request's number and address, that the folder shows the merged state again until the owner merges, and the `how` of the `pending` item. After a stop in the generation or the proposal: the files written in this folder in this run (kept), the cause in one sentence, and that the next run proposes them.

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
  - `updated`: something else changed in this run (a step ended `created` or `updated`: files generated in this folder, a pull request opened or a branch pushed, the folder updated, the repository configured or protected) and the repository was not created.
  - `unchanged`: nothing was changed and a plan says `nothing to do`: every action of the first plan was `none`, or every step of step 4 ended `unchanged` and the last plan says `nothing to do`.
  - `pending`: nothing was changed, and something is left: a missing confirmation, `merge it` or `fix the folder`, a `go_setup`, the proposal or a step of step 4 that ended with the status `pending` when no earlier step had changed anything, or every step ended `unchanged` and the last plan still lists an action.
  - `failed`: nothing was changed: an argument broke a rule, the first plan failed, a `confirmVisibility` named a change the plan does not have, the proposal found nothing to commit, a `go_setup`, `github_ci-setup` or a step of step 4 ended `failed` when no earlier step had changed anything, or nothing was changed and the last plan failed.
  - When a step stopped the run after something was changed, or the last plan still has an action other than `none`, the status is `created` or `updated` (it says what was done) and what is left is in `pending`.
- `outputs` has the same five keys in every ending:
  - `project`: the declaration's `name`; `repository`: `<owner>/<name>`. Both `null` when the plan failed on the declaration (missing or invalid) or before it was read.
  - `url`: `https://github.com/<owner>/<name>` when the repository exists at the end of the run (by the last plan, or created in this run); `null` otherwise.
  - `items`: the items of the last plan this run invoked, as it gave them: the plan of step 5 when it ran, otherwise the plan run after an update when it ran, otherwise the plan of step 1. `[]` when that plan failed or when no plan was invoked.
  - `pullRequest`: `{ "number": <n>, "url": "<url>" }` of the pull request this run opened (the `number` and `url` of `outputs.pullRequest` of `github_pull-request-open` when it ended `created`); `null` in every other ending.
- `pending`, items `{ "item": "<what>", "reason": "<reason>", "how": "<text>" }`:
  - A missing confirmation: the one item of step 3.
  - `merge it` or `fix the folder`: the plan's items, as it gave them (also when the plan run after an update has them).
  - A proposal opened: the item `pull request #<n> is open` of step 4, plus the pull request skill's own items, if any, plus the item `after the merge` when the plan also listed actions on GitHub.
  - A stop in the generation or the proposal after files were written in this run: the item of step 4 (`how` ending with `run /aleogr:project-apply confirm=yes again, which proposes them`), plus the stopping skill's own items.
  - The last plan lists `generate` after a birth: the items `run /aleogr:project-apply confirm=yes to generate the components` of step 5.
  - A merged change of exposure after an update: the item `confirm visibility <value>` of step 4.
  - `failed`: one item `{ "item": "<what failed>", "reason": "manual", "how": "<fix>" }`: for an argument, `item` `arguments` and the allowed values; for the plan, its item as it gave it; for a `confirmVisibility` the plan does not need, `item` `confirm visibility` and the confirmation this plan needs (`/aleogr:project-apply confirm=yes`, or the other `confirmVisibility`); for a step, its item (`repository`, `settings`, `declaration` or `protection`; the component's name for a `go_setup`, `ci` for `github_ci-setup`) and its cause, plus the step's own `pending` items.
  - A step that stopped the run after a change: its cause as one item, as above, plus its own `pending` items.
  - The last plan still has an action other than `none`: one item per such item, `{ "item": "<item>", "reason": "manual", "how": "<the confirmation it needs, as in step 3, or the plan's how>" }`; for the action `generate`, the `how` is `run /aleogr:project-apply confirm=yes to generate the components`.
  - The last plan failed: the item `verify` of step 5.
  - `nothing to do` (in this run or from the first plan): `[]`. The plan limit of a private repository is not an item: the last plan shows it as `not available on this plan`, with its line under the table.
- `resources` is `[{ "type": "repository", "id": "<owner>/<name>", "name": "<name>" }]` when `url` is not `null`, `[]` otherwise.
- `cost` is always `{ "fixed": false, "notes": "no cost" }`. The block never holds the account name.
