# Reference project, stage 3a: design of the GitHub repository plugin

Status: waiting for the owner's approval. Source of truth after approval: [`DESIGN.md`](../DESIGN.md) and [`CONTRACTS.md`](../CONTRACTS.md); this document is what the implementation plan is written from.

## Intent

Stage 3 gives the reference project `pilot` ([`DESIGN.md`](../DESIGN.md) section 15.4) its repository: created and protected by skills, with a Go skeleton and CI, without the owner opening GitHub. It is the largest stage so far, so it is split into three parts, each with its own real run and pull request:

- **3a (this document):** the plugin `aleogr-repo-github`, which creates the repository `pilot`, configures it and protects `main`.
- **3b:** the project declaration and the skills `project-declare`, `project-plan` and `project-apply`, which drive the plugin from a file.
- **3c:** the Go skeleton and CI.

The owner will have **both public and private repositories**. On the free GitHub plan the two behave differently, and the tooling must handle both without cost and without pretending.

## Goals

- Four skills exist in a new plugin `aleogr-repo-github`: `github_repo-describe`, `github_repo-create`, `github_repo-configure`, `github_branch-protect`.
- They follow the rules of every skill ([`DESIGN.md`](../DESIGN.md) section 10.4): arguments validated first, each command shown, `plan`/`apply`, idempotent, a final verification, one `aleogr-result` block.
- A **public** repository ends created, configured and with `main` protected by the same rules `aleogr/aleogr` has today.
- A **private** repository in an organization on the free plan ends created and configured, with the protection reported as `pending` (plan limit): a known notice, not a failure.
- `pilot` proves both with one repository: it is born private, then made public.
- `tools-check` checks `gh`.

## Non-goals

- The other contract actions of the family (`ci-set-secret`, `ci-set-variable`, `ci-setup`, `repo-archive`): `ci-setup` comes in 3c, the secrets in stage 4, each when there is a real use to prove it.
- The declaration, the schema and `project-*` (3b). In 3a the owner calls the four skills directly.
- Required status checks in the protection: there is no CI yet; the argument is added in 3c.
- Cloning the repository or configuring a local remote (the `local directory` input of `repo-create`): added in 3c, when there is code to put in it.
- Deleting a repository: not in the contract ([`CONTRACTS.md`](../CONTRACTS.md)).
- A paid GitHub plan.

## Anti-goals

- A repository made public without the owner confirming that exact change.
- A private repository reported as protected when it is not.
- A token, an account name or an e-mail in the conversation output or in a versioned file.
- Anything that creates a cost.

## Constraints

- The repository `aleogr/aleogr` is public: test fixtures use fictitious owners and names (`example-org/example-repo`).
- Commands run in PowerShell in the Windows app and in bash in Cloud Shell: values with commas, spaces or quotes are quoted, and a JSON body goes in a file shipped with the plugin (`files/`), read through `${CLAUDE_PLUGIN_ROOT}`, never inline.
- A family plugin cannot read the orchestrator's `defaults.json`; until 3b the settings arrive as arguments.
- `gh` is preinstalled in Cloud Shell (2.104.0, seen on 2026-11-17). On Windows the owner installs it and logs in once (run checklist).

## Facts this design relies on

Read on 2026-11-18 from the GitHub API of `aleogr/aleogr`: the hand-made ruleset is named `main`, targets `~DEFAULT_BRANCH`, is `active`, has no bypass actor, and has three rules: `deletion`, `non_fast_forward`, and `pull_request` with 0 approvals and merge methods `merge`, `squash`, `rebase`.

From GitHub's documentation, **to be confirmed by the real run** and then recorded in [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md):

- Rulesets are enforced on public repositories on the free plan and not available on private repositories of a free organization.
- Private repositories of a free organization get 2,000 Actions minutes a month; public ones are not metered.
- `gh repo edit --visibility` needs `--accept-visibility-change-consequences`.
- How the API answers a ruleset request on a private repository of a free organization (expected: HTTP 403 with an "upgrade" message). The skill's detection of `pending` depends on it; see "Left to the builder".

## Approaches

- **1. Only what `pilot` needs now (chosen).** Four skills; the remaining contract actions come when a real use exists. Each skill is proven by a real run as soon as it is written. The plugin is incomplete against the contract for a while.
- **2. The whole contract at once.** Eight skills now. Four of them would have no real use to prove them, which is how the errors found only in the real run of stage 2 appeared, and it goes against building only what the project requires ([`DESIGN.md`](../DESIGN.md) section 17).
- **3. No separate 3a.** The plugin built together with `project-*`. The first real use would already be through the declaration, but the delivery is much larger and more new things fail at once.

The owner chose **1**.

## Decided by the owner

- Both public and private repositories are supported.
- `pilot` is born private and then becomes public, and stays public.
- No paid plan: on a private repository, `main` is held by the working rule (Claude Code opens the pull request, the owner merges), not by GitHub.
- A visibility change needs its own confirmation.
- Form 1 above.

## My calls (the owner can overrule any of them)

- **Tool:** `gh` with the owner's login, as the cloud skills use `gcloud`. No MCP.
- **Default visibility is `private`** when not given: making public later is easy, the opposite does not undo what was seen.
- **`github_repo-create` creates the repository with a README**, so that `main` exists from the start: a ruleset that requires pull requests on an empty repository could block the first commit. Topics are set in the same skill.
- **Topics:** the caller passes them; for `pilot`, `aleogr-pilot` (the `aleogr-<project>` topic of [`DESIGN.md`](../DESIGN.md) section 11.2).
- **`github_repo-configure` only touches what it is given:** an argument left out means "leave as it is". Arguments: description, topics, merge commit, squash, rebase, delete branch on merge, issues, wiki, projects, visibility. It is the only skill that corrects an existing repository; `github_repo-create` on an existing repository changes nothing and lists what differs.
- **Settings used for `pilot`** (they become the `repo` block of `defaults.json` in 3b): merge commit on, squash on, rebase off, delete branch on merge on, issues on, wiki off, projects off.
- **Visibility change:** in `plan`, shown as a difference. In `apply`, the skill stops and asks, naming the direction, unless called with `confirmVisibility=<public|private>` equal to the requested visibility. Making private also warns that the protection stops being enforced on the free plan.
- **Creating a repository directly as public asks the same question:** `github_repo-create` with `visibility=public` stops in `apply` unless called with `confirmVisibility=public`. Nothing becomes public without that exact confirmation, whichever skill does it.
- **Protection = a repository ruleset** named `main`, equal to the one of `aleogr/aleogr` (facts above), sent from `files/ruleset-main.json`. The skill compares target, enforcement, bypass actors and the three rules; a ruleset named `main` that differs is updated, other rulesets are left alone and reported.
- **`pending` instead of failure** when the plan does not allow the protection: `status` `pending`, an item in `pending` saying "branch protection needs a paid plan or a public repository", nothing in `resources`.
- **`plan` says `pending` too.** The skill first reads the repository's rulesets; when that read is refused with a message that names the plan, both `plan` and `apply` end with `pending` and no write is attempted, and `github_repo-describe` reports the protection as `unavailable`. [`CONTRACTS.md`](../CONTRACTS.md) is changed to allow `pending` in `plan` for a feature the provider's plan forbids, so that plan and apply never diverge. If the real run shows that the read is not refused and only the write is, the skill is corrected then (run step 5 is done in `plan` and then in `apply` to find out).
- **Extra proof at no cost:** `github_branch-protect` in `plan` mode against `aleogr/aleogr` must report `unchanged`.
- **`tools-check` gains `command=gh`:** it then checks only `gh`, installed and logged in, without printing the account or the token. Called with no argument it stays as it is, checking only `gcloud`, so the platform skills do not start depending on `gh`. Access to the organization is not checked there.
- **Each of the four skills handles a missing or logged-out `gh` itself**, as the cloud skills do with `gcloud`: one sentence, no raw error text, `status` `failed`. The same for a refusal by the organization.
- **Tests:** a fake `gh` beside the fake `gcloud`, same harness and same kinds of expectation. Scenarios cover, for each skill: invalid arguments, plan, apply, already as wanted, a difference, a refused command; and for the protection: public, private `pending`, existing equal, existing different.
- **Versions:** `aleogr-repo-github` 0.1.0 (new entry in `marketplace.json`); `aleogr` 0.5.0.

## The four skills

| Skill | Arguments | Changes | Result |
|---|---|---|---|
| `github_repo-describe` | `owner`, `name` | nothing | `exists`, visibility, default branch, description, topics, merge settings, features, protection (`protected`, `unprotected`, or `unavailable` on this plan) |
| `github_repo-create` | `owner`, `name`, `visibility` (default `private`), `confirmVisibility`, `description`, `topics`, `mode` | creates the repository with a README and topics | URLs, default branch; `unchanged` when it already exists (differences are for `repo-configure`, and are reported) |
| `github_repo-configure` | `owner`, `name`, `description`, `topics`, any of the settings, `visibility`, `confirmVisibility`, `mode` | only the given settings that differ | applied settings |
| `github_branch-protect` | `owner`, `name`, `mode` | creates or updates the ruleset `main` | applied rules, or `pending` |

Names are validated before any command: `owner` and `name` by GitHub's rules; `visibility` is `public` or `private`; a project name follows [`DESIGN.md`](../DESIGN.md) section 11.1 only from 3b on (here the skill receives a repository name, not a project).

## The real run (its checklist is written with the plan)

In Cloud Shell or the Windows app, after the pull request is merged and the plugins updated:

1. `tools-check command=gh`.
2. `github_branch-protect` in `plan` against `aleogr/aleogr`: `unchanged`.
3. `github_repo-create` for `aleogr-sandbox/pilot`, private: plan, then apply.
4. `github_repo-configure` with the settings above: plan, then apply.
5. `github_branch-protect`, in `plan` and then in `apply`: `pending` both times.
6. `github_repo-configure visibility=public`: asks, the owner confirms.
7. `github_branch-protect`: plan shows the ruleset to create, apply creates it.
8. Every skill again in `plan`: `unchanged`.

What the run shows goes into [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md).

## Documents changed with this work

- [`DESIGN.md`](../DESIGN.md): the three parts of stage 3 (section 17), `pilot` born private then public (15.4), default visibility and the `pending` protection (11.1, 10.3), `tools-check` with `gh` (12), the tree (2), open items (18).
- [`CONTRACTS.md`](../CONTRACTS.md): `repo-configure` gains description, topics and visibility; `pending` allowed in `plan`; `branch-protect` on a plan without protection; `repo-create` with a README.
- [`cloud-shell.md`](../cloud-shell.md): the `gh` login and the new plugin.
- The READMEs of the plugins folder and of the tests.

## Left to the builder

- The exact `gh` commands and API paths, checked against `gh` 2.104 help and the REST documentation.
- How `pending` is detected: by attempting the ruleset request and reading the refusal, with the rule that only a refusal that names the plan becomes `pending`; any other refusal is `failed`. If the real run shows a different answer, the skill is corrected then.
- How the fake `gh` matches `gh api` calls with a method and an input file.
- The wording of the skills and the list of scenarios.
