---
description: aleogr project declare. Use to write or edit the project's declaration, `.aleogr/project.json` in the current folder (project name, GitHub repository, visibility, description, topics, settings, components and whether each uses the database, cloud and environments), pre-filled from the owner's defaults. It only writes that file: it runs no provider command and changes nothing on GitHub.
---

# project-declare

Writes or edits the declaration of the project, `.aleogr/project.json` in the folder the skill runs in. A new declaration takes what the arguments do not give from the owner's defaults in `${CLAUDE_PLUGIN_ROOT}/defaults.json`; an existing one keeps everything the arguments do not change. The skill shows the resulting file and writes it in the canonical form. It runs no provider command (`gh`, `git`, `gcloud`, `go`) and invokes no skill: nothing changes on GitHub or anywhere else (`project-plan` and `project-apply` do that from the file).

## Arguments

Free text after the skill name, as `key=value` pairs. A value with spaces is written in quotes (`description="Status pages, per tenant"`).

| Argument | Key in the file | Meaning |
|---|---|---|
| `name=<name>` | `name` | The project name. Required for a new declaration. |
| `owner=<owner>` | `repo.owner` | The user or organization that owns the repository. Required for a new declaration (there is no default owner). |
| `repoName=<name>` | `repo.name` | The repository name. Default for a new declaration: the project name. |
| `visibility=<public\|private>` | `repo.visibility` | Default for a new declaration: `repo.visibility` of the defaults. |
| `description=<text>` | `repo.description` | Description of the repository. Required for a new declaration. |
| `topics=<t1>,<t2>` | `repo.topics` | Extra topics, comma-separated. `topics=` with an empty value means none. Default for a new declaration: none. Never the derived topic `aleogr-<name>`. |
| `mergeCommit=<true\|false>` | `repo.settings.mergeCommit` | Default for a new declaration: the same key of `repo.settings` in the defaults. |
| `squash=<true\|false>` | `repo.settings.squash` | Same. |
| `rebase=<true\|false>` | `repo.settings.rebase` | Same. |
| `deleteBranchOnMerge=<true\|false>` | `repo.settings.deleteBranchOnMerge` | Same. |
| `issues=<true\|false>` | `repo.settings.issues` | Same. |
| `wiki=<true\|false>` | `repo.settings.wiki` | Same. |
| `projects=<true\|false>` | `repo.settings.projects` | Same. |
| `notes=<text>` | `notes` | Optional free text. `notes=` with an empty value removes the key. Default for a new declaration: no `notes` key. |
| `component=<name>` | `components` | The component this run adds or changes: one per call. A component not in the declaration is added; an existing one is changed. |
| `stack=<go>` | `stack` of the component | Required when the component is new. For an existing component, when given, it equals the component's `stack`. |
| `path=<folder>` | `path` of the component | Default for a new component: its name. For an existing component, when given, it equals the component's `path`. |
| `version=<major.minor>` | `version` of the component | Default for a new component: `stacks.<stack>.version` of the defaults. For an existing component, the new version. |
| `database=<yes\|no>` | `database` of the component | `yes` writes `"database": true`: the component uses the project's database. `no` removes the key. Default: a new component has no `database` key; an existing one keeps what it has. |
| `environment=<dev>` | `environments` | The environment this run adds: `dev`, the only one built yet. When the declaration has no `cloud`, it is written too, with `cloud.provider` and `cloud.region` of the defaults. An environment already declared stays as it is. |
| `cloudRoot=<tst>` | `cloud.root` | `tst`, the only value: the project tests the tooling, and its cloud projects are created inside the folder `tst`. It needs `cloud`: the declaration has one, or `environment=` is given in the same call. |

`stack`, `path`, `version` and `database` describe the component named by `component`: given without `component`, the run fails. Removing a component is not done by this skill, nor removing an environment, the cloud or the root, nor changing the region.

An argument given twice fails, and so does an argument that is not in the table (`mode` included: this skill has no `mode`, and every run writes the file when a value changes).

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run exactly this command with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

```
"${CLAUDE_PLUGIN_ROOT}/bin/aleogr" project-declare <arguments>
```

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

An argument given with its value in double quotes (`description="Status pages, per tenant"`) is one argument whose value is the text inside them: write it `'description=Status pages, per tenant'`, without the double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is the sentence `The command ${CLAUDE_PLUGIN_ROOT}/bin/aleogr ended without an answer: it may have changed something before it stopped. Read the state (look at .aleogr/project.json) before running it again.` followed by this block, and nothing else:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "orchestrator",
  "provider": "aleogr",
  "action": "project-declare",
  "mode": "apply",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "the run may have changed something" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr, then try again" } ]
}
```
