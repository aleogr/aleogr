# Schemas

JSON Schema for the project declaration (`.aleogr/project.json`) and example declarations.

Source of truth: [`docs/DESIGN.md` — section 11](../../docs/DESIGN.md#11-project-model) (tests in [section 15](../../docs/DESIGN.md#15-tests)).

## Local rules

- `project.schema.json` is versioned; `project.json` has a `version` field and `$schema` for autocomplete:
  `https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/project.schema.json`.
- Exclusive families = object; combinable = list; exactly one `primary` cloud; payments `mode` defaults to `"test"`; `environments` field; optional `notes` field.
- Project names **cannot** be `test` or `shared`, nor start with `test-` (reserved for tests and for the shared platform project).
- Family plugins may publish sub-schemas for their options.
- `examples/`: JSON declarations with **fictitious values** only — they are the test inputs; validated against the schema on every PR (`self-validate-marketplace.yml`). Never projects with code.

## Version 1 of the declaration

`project.schema.json` (draft 2020-12, no unknown keys anywhere) describes `.aleogr/project.json` as it is today: the repository and, optionally, the components.

- Top level: `$schema` (optional), `version` (`1`), `name`, `repo`, `components` (optional), `notes` (optional).
- `name`: 1 to 14 characters of `a-z`, `0-9`, `-`, starting with a letter, not ending with `-`; not `test`, `shared` or `test-*`.
- `repo`: `provider` (`github`), `owner`, `name`, `visibility` (`public` or `private`), `description` (1 to 350 characters), `topics` (optional, unique, default `[]`) and `settings`. `owner`, `name`, `description` and topics follow the rules of the `aleogr-repo-github` skills.
- `settings` is complete: `mergeCommit`, `squash`, `rebase`, `deleteBranchOnMerge`, `issues`, `wiki`, `projects`, all booleans; at least one of the first three is `true`.
- **The topic `aleogr-<name>` is derived, not typed.** `repo.topics` holds only extra topics and must not contain `aleogr-<name>`; the list sent to GitHub is the derived topic plus `repo.topics`, sorted, without duplicates. The schema cannot express this, so it is stated in prose only.
- `components` (optional; a declaration without it stays valid): a list, possibly empty, of objects with exactly `name`, `stack`, `path` and `version`, all required.
  - `name`: 1 to 20 characters of `a-z`, `0-9`, `-`, starting with a letter; not `changes` or `ci` (the project's CI file has jobs with those names, and each component is a job named after it), nor `true`, `false`, `null`, `yes`, `no`, `on` or `off` (YAML does not read them as names).
  - `stack`: `go`, the only stack implemented.
  - `path`: the component's folder, relative to the repository root: parts separated by `/`, none empty; each part uses only `a-z`, `0-9`, `-`, `_` and `.`, is not `.` or `..`, does not start with `-` or `.` (so never `.github`, `.aleogr` or under them) and does not end with `.`. Default: the name.
  - `version`: the language version, `major.minor` (`^[0-9]+\.[0-9]+$`). Default: `stacks.<stack>.version` of the owner's defaults. **With the stack `go` it is `1.22` or later**, comparing the major and then the minor as numbers (`1.21` and `1.9` are refused): the Go starting point's routes need Go 1.22. The pattern checks the form only, so the minimum is stated in prose (in the schema's description).
  - **Each `name` and each `path` is unique in the list, and no component's `path` is inside another's** (`web` and `web/api` cannot both be components: one module per component folder). The schema cannot express these rules, so they are stated in prose only.
- The canonical file is written with two-space indentation, keys in the order above and a final newline; `components` is sorted by name and each component is on one line, `{ "name": "web", "stack": "go", "path": "web", "version": "1.27" }`.
- Examples: [`examples/repo-only.json`](examples/repo-only.json), [`examples/with-components.json`](examples/with-components.json).
