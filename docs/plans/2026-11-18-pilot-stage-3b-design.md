# Reference project, stage 3b: design of the project declaration and the `project-*` skills

Status: waiting for the owner's approval. Source of truth after approval: [`DESIGN.md`](../DESIGN.md) and [`CONTRACTS.md`](../CONTRACTS.md); this document is what the implementation plan is written from.

## Intent

Stage 3a gave the tooling four skills that describe, create, configure and protect a GitHub repository, each called by hand with its arguments. Stage 3b puts a file in front of them: the project is described once, in `.aleogr/project.json`, and three orchestrator skills write that file, compare it with reality and make reality match it. From here on the owner states what a project is, not which commands to run.

The proof is the goal of the whole tooling in miniature: **the repository of `pilot` comes out of nothing, from its declaration**. The owner deletes the hand-built `aleogr-sandbox/pilot` and `project-apply` rebuilds it.

## Goals

- A declaration format, version 1, with only what can be proven now: the project's name and its repository.
- `project-declare` writes or edits `.aleogr/project.json` in the current folder, pre-filled from the owner's defaults, and executes nothing.
- `project-plan` compares the declaration with GitHub and prints a table of items, state and action; it changes nothing.
- `project-apply` does what the plan lists, in order, and ends with a plan that says `nothing to do`.
- A new repository is born in one run: created, configured, the declaration sent as its first content, then `main` protected.
- After the birth, `project-apply` applies only what is merged in the repository.
- Everything works for a public and for a private repository, with the rules of stage 3a (nothing public without its own confirmation; protection `pending` on a private repository of a free organization).

## Non-goals

- Components, environments, cloud, database, DNS in the declaration: they enter with the stage that can prove them (3c, 4, 5).
- `.aleogr/state.json`. The plan reads reality from the provider, as `platform-plan` does; a state file is added only when something cannot be discovered.
- The shortcuts and maintenance skills of [`DESIGN.md`](../DESIGN.md) section 12 (`project-create`, `component-add`, `plugins-sync`, removals).
- Project-scope plugin activation (`.claude/settings.json` in the project): the plugins stay installed at user level, as today.
- Layouts other than a single repository (manifest, federated).
- The workflow that validates declarations on every pull request (`self-validate-marketplace.yml`).
- Opening the pull request for a change to the declaration: Claude Code does that in the normal way, without a skill.
- Deleting a repository: by hand, as stage 3a decided.

## Anti-goals

- A repository made public without the owner confirming that exact exposure.
- `project-apply` applying a declaration that is not the one merged in the repository (after the birth).
- A commit that publishes the owner's e-mail address.
- A plan that says `nothing to do` while something differs, or that hides the protection it could not apply.
- Any cost.

## Constraints

- A family plugin cannot read the orchestrator's files, and families never call each other: the orchestrator reads `defaults.json` and the declaration and passes values as arguments.
- The orchestrator runs no provider command itself (`tools-check` aside): what touches GitHub is done by a `repo-*` skill.
- Commands run in bash (Cloud Shell) and PowerShell (Windows app): the rules of stage 3a on quoting and on files instead of inline JSON hold.
- The skills do not wait for an answer: when a confirmation is needed the run ends `pending` and shows the text that confirms.
- A model does not always capture a command's exit code reliably ([`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md)): every decision by exit code also names the text that identifies the case.
- `aleogr/aleogr` is public: examples and fixtures use fictitious values.

## Approaches

How the declaration reaches a repository that does not exist yet:

- **1. Born in a local folder, sent as the first content, then `main` is protected (chosen).** One run, no pull request; the only direct push to `main` in the repository's life is its birth.
- **2. Sent by pull request after the protection.** No exception to the working rule, but every new project needs a manual merge at birth and exists for a while without its own declaration.
- **3. Kept outside the project's repository.** No ordering problem, but one more repository and a declaration that does not travel with the code.

The owner chose **1**.

How stage 3b is proven:

- **Recreate from nothing (chosen).** The owner deletes `aleogr-sandbox/pilot` by hand and `project-apply` rebuilds it from the declaration.
- Adopt the existing repository and prove `project-apply` with a small change only. Rejected by the owner: creation from the declaration would stay unproven.

## Decided by the owner

- Recreate `pilot` from nothing.
- Approach 1 for the birth.
- After the birth, a change goes: edit the declaration, pull request, merge, `project-apply`; and `project-apply` refuses a local declaration that differs from the merged one. (Proposed by me, accepted with approach 1.)

## My calls (the owner can overrule any of them)

### The declaration, version 1

```json
{
  "$schema": "https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json",
  "version": 1,
  "name": "pilot",
  "repo": {
    "provider": "github",
    "owner": "aleogr-sandbox",
    "name": "pilot",
    "visibility": "public",
    "description": "Reference project of aleogr: status pages per tenant",
    "topics": [],
    "settings": {
      "mergeCommit": true, "squash": true, "rebase": false,
      "deleteBranchOnMerge": true, "issues": true, "wiki": false, "projects": false
    }
  },
  "notes": "optional free text"
}
```

- `name`: the project name, with the rule the cloud skills already use (1 to 14 characters of `a-z`, `0-9`, `-`, starting with a letter, not ending with `-`), and not `test`, `shared`, nor starting with `test-`.
- `repo` is an object (an exclusive family, [`DESIGN.md`](../DESIGN.md) section 11.1). `provider` is `github`, the only one implemented. `repo.name` defaults to the project name. `visibility`, `description`, topics and settings follow the rules of the stage 3a skills.
- **The topic `aleogr-<name>` is derived, not typed**: `repo.topics` holds only extra topics; the list sent to GitHub is the derived topic plus those.
- `settings` is complete in the file (all seven keys), so the file says everything about the repository without reading the defaults.
- The schema is `.claude-plugin/schemas/project.schema.json`, strict (no unknown keys), with one example of fictitious values in `examples/`. The three skills check a declaration by the schema's rules written in their own text; no validator tool is required on the owner's machine.

### The defaults

`defaults.json` of the orchestrator gains `repo`: `{ "provider": "github", "visibility": "private", "settings": { the seven values used for pilot } }`. No default owner: `project-declare` needs it.

### One new skill in the GitHub plugin: `github_checkout-setup`

The birth needs the local folder tied to the repository and the declaration sent to it. That is provider work (the repository's address, the account's commit identity), so it lives in the family, as one composite action (`*-setup`):

- Arguments: `owner`, `name`, `paths` (the files to send; for now only `.aleogr/project.json`), `message`, `mode`.
- It makes the current folder a checkout of the repository (git, with the remote `origin`), brings the repository's first commit (the README), commits the given paths and pushes them to the default branch.
- **Commit identity:** it always sets the identity of this checkout (local git configuration only), whatever the machine's global identity is: the account's login as the name and GitHub's no-reply address (`<id>+<login>@users.noreply.github.com`) as the e-mail. A real e-mail address is never used. The login is written to the checkout's configuration and is public in the commit, but it is not repeated in the skill's answer or result block; the same identity then signs the commits of later pull requests made from this folder.
- **No global configuration is changed.** The push authenticates through `gh` for that command only (git's credential helper given on the command line), never by writing to the machine's git configuration.
- **`send` is only the completion of a birth.** The declaration is pushed to the default branch only when that branch has exactly one commit (the README of `github_repo-create`) and no `.aleogr/project.json`. A repository with any other history that lacks the declaration, protected or not, public or private, is never pushed to: `pending`, "open a pull request with the declaration". That is also how an existing repository is adopted.
- It also answers the question the plan needs: is the declaration in the repository's default branch, and is it equal to the local one? In `plan` mode it reads the repository's copy through the GitHub API, so it works in a folder that is not a checkout yet and changes nothing anywhere. "Equal" compares the two files as JSON values, not byte by byte (line endings differ between Windows and Linux).
- A push refused because the branch is protected is not a failure of the tooling: `pending`, "open a pull request with the change".
- It replaces the `local directory` input that stage 3a had left on `repo-create` for stage 3c; [`CONTRACTS.md`](../CONTRACTS.md) records it as its own action, `checkout-setup`.

### `project-declare`

- Arguments: `name`, `owner`, and any of `repoName`, `visibility`, `description`, `topics`, the seven settings, `notes`.
- No file yet: `name`, `owner` and `description` are required (missing: `failed`, saying which); everything else comes from the defaults. File exists: only the given arguments change, the rest is kept.
- It shows the resulting file, writes it, and runs no command. Changing `name` or `repo.owner`/`repo.name` of an existing declaration is refused: that is another project.
- Status: `created`, `updated`, `unchanged`, `failed`.

### `project-plan`

Run in the project's folder. It validates the declaration, runs `tools-check command=gh`, then `github_repo-describe` and `github_checkout-setup mode=plan`, and prints:

| Item | States | Action |
|---|---|---|
| `repository` | `missing`; `exists` | `create`; `none` |
| `settings` | `as declared`; a list of what differs (description, topics, the seven settings) | `none`; `update` |
| `visibility` | `as declared`; `differs` | `none`; `update` (needs confirmation) |
| `declaration` | `in the repository`; `not sent yet`; `differs from the repository` | `none`; `send` (only before the protection exists); `merge first` |
| `protection` | `protected`; `unprotected`; `differs`; `not available on this plan` | `none`; `create`; `update`; `none` with a notice |

- It ends with the line `nothing to do` only when every action is `none`. `merge first` is not an action the apply can take: the plan says so and `project-apply` stops on it.
- While the local declaration differs from the merged one, the plan shows only the `repository` and `declaration` rows; `settings`, `visibility` and `protection` are `not checked until the change is merged`. The plan never lists an update that the apply would refuse.
- `declaration` on an existing repository that has no declaration and is not a birth (see `github_checkout-setup`): state `not in the repository`, action `open a pull request`, which `project-apply` also stops on.
- A repository that does not exist: the other four items are listed as following from the creation, with no further command.

### `project-apply`

- Runs `project-plan` first and shows its table.
- **One confirmation per run, for the whole plan; a run is all or nothing.** Without the confirmation its plan needs, the run ends `pending` and changes nothing at all (it does not apply the other items and leave the visibility for later).
  - A plan that exposes nothing is confirmed by `confirm=yes`.
  - A plan that creates a public repository or makes one public is confirmed only by `confirmVisibility=public`, which then confirms the whole plan; `confirm=yes` alone ends `pending`. Making a repository private: `confirmVisibility=private`, the same way.
  - `confirmVisibility` given when the plan has no such visibility change, or with the wrong value, is `failed` with no change: a confirmation never applies to a plan other than the one it names.
- Order: `github_repo-create` → `github_repo-configure` (settings, then visibility) → `github_checkout-setup` (send the declaration) → `github_branch-protect`. The declaration is sent before the protection exists; on a repository already protected it is never pushed.
- `declaration` `differs from the repository`: stop before any change, `pending`, "merge the change first, then update this folder".
- Any step that ends `failed` or `pending` stops the run, with its cause and its `pending` items — except the protection's plan limit on a private repository, which is the expected end there.
- It ends by running `project-plan` again; `nothing to do` only from that last plan.

### Carried from stage 3a

- The four existing GitHub skills gain the rule on exit codes (each decision names the text that identifies the case, and how the exit code is captured in bash and in PowerShell), the open item of [`DESIGN.md`](../DESIGN.md) section 18.
- The output key names that differ between the four skills are settled now that `project-plan` reads them, changing as little as possible.

### Tests

- The harness gains a fake `git` (same fake, a third wrapper), a way to start a scenario with files in the working folder, and an expectation on a file's content, so that `project-declare` and the birth can be tested.
- Scenarios cover each skill's paths: declare (new, edit, invalid, refused rename), plan (missing repository, everything as declared, each item differing, private with protection unavailable, declaration differing), apply (birth public confirmed and unconfirmed, birth private, update of settings, stopped by `merge first`, a step failing), checkout-setup (new folder, already a checkout, identity set, push refused by protection).

### Versions

`aleogr` 0.6.0; `aleogr-repo-github` 0.2.0.

## The real run (its checklist is written with the plan)

In Cloud Shell, after the merge and the plugin update:

1. The owner deletes `aleogr-sandbox/pilot` by hand in GitHub's settings.
2. In a new empty folder (`~/pilot`): `project-declare name=pilot owner=aleogr-sandbox visibility=public description="..."`. The file appears; nothing else happens.
3. `project-plan`: repository `missing`, everything to create.
4. `project-apply`: ends `pending`, asking for the public confirmation.
5. `project-apply confirmVisibility=public`: creates, configures, sends the declaration, protects; ends `nothing to do`.
6. `project-plan` again: `nothing to do`. The repository on GitHub has the README, `.aleogr/project.json`, the topic, the settings and the ruleset.
7. The change path: `project-declare topics=status-page` edits the local file; `project-apply` stops with `merge first`; the owner asks Claude Code to open the pull request and merges it; the folder is updated; `project-apply confirm=yes` adds the topic; `project-plan` says `nothing to do`.

## Documents changed with this work

- [`DESIGN.md`](../DESIGN.md): sections 7 (state: discovered, no state file yet), 11 (declaration version 1, the birth and the merged-only rule), 12 (the three skills as built, the confirmation rule), 12.2 (the order for the repository part), 2 (tree), 17 and 18.
- [`CONTRACTS.md`](../CONTRACTS.md): `checkout-setup` in the repo-* table; `repo-create` loses its `local directory` input.
- `schemas/README.md`, the plugins and tests READMEs, [`cloud-shell.md`](../cloud-shell.md) (the new skills; working in a project folder).

## Left to the builder

- The exact git and `gh` commands of `github_checkout-setup`, in forms that work in bash and PowerShell, and how the account's login and id are read.
- How `project-plan` maps the outputs of the two skills to the table, and the exact wording of states and notices.
- The JSON Schema details and the fictitious example.
- How the fake `git` and the file expectations are built into the harness, and the list of scenarios.
