---
description: Go stack setup. Use to write the minimal starting point of a Go component in its folder - go.mod, main.go (an HTTP server with GET / and GET /healthz on the port in PORT, default 8080) and main_test.go - from templates the plugin ships, once and only when the folder has no go.mod and no Go file; it never overwrites anything. Returns the component's Go CI parameters (the reusable workflow ci-go.yml and its inputs). Needs no Go toolchain. Plan by default.
---

# go_setup

Writes the starting point of a Go component: exactly `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, filled from the templates in `${CLAUDE_PLUGIN_ROOT}/files/`. It writes them once: when `<path>/go.mod` exists it writes nothing, and when `<path>` holds a Go file without a `go.mod` it writes nothing and says so. It never changes or overwrites a file. It needs no Go toolchain (CI compiles and tests the code) and returns the CI parameters of the component.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `component=<name>` | The component's name. Required. |
| `path=<folder>` | The component's folder, relative to the current folder. Default: the component's name. |
| `version=<major.minor>` | The Go language version, written on the `go` line of `go.mod` and passed to CI. Required. |
| `module=<module path>` | The Go module path: `github.com/<owner>/<repository>/<path>`. Required. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` writes the files when nothing is there. |

A missing required argument is never asked for: the run ends with the result block with `status` `failed`, one sentence naming every missing argument, and nothing read or written. Validate before reading anything; a value that breaks a rule ends with the result block with `status` `failed`, one sentence per broken rule, and nothing read or written:

- Every argument is one of the table; an unknown argument fails, and so does an argument given twice.
- `component` has 1 to 20 characters of `a-z`, `0-9` and `-`, and starts with a letter.
- `path` is a relative folder: it does not start or end with `/`, has no space, no empty part (`a//b`) and no part `.` or `..`, and it is not `.aleogr` or `.github` and not under them (`.github/web` fails). Each part between `/` has only `A-Z`, `a-z`, `0-9`, `-`, `_` and `.`, and does not start or end with `.` (a Go module path cannot hold it).
- `version` matches `^[0-9]+\.[0-9]+$` (`1.27`; not `1.27.4`, not `go1.27`).
- `module` is `github.com/` + `<owner>` + `/` + `<repository>` + `/` + `path`, exactly: `<owner>` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-` and does not start or end with `-`; `<repository>` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-` and is not `.` or `..`; and what follows them is the `path` argument (or its default) character for character. `module=github.com/example-org/example-repo/other` with `path=web` fails: the module must end with `/web`.
- `mode`, when given, is `plan` or `apply`.

## Steps

Use the Read tool and the Write tool. The only command this skill may run is the single `ls` of step 2, at most once: no other command (no `mkdir`, `cat`, `test`, `find`, `go`, `gh`, `git`; the Write tool creates the folders), and no skill. Show the command before running it.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree, the text decides. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

1. Read `<path>/go.mod` in the current folder with the Read tool.
   - It has content, or the tool says the file exists but is empty: the component already has a module. `unchanged`: write nothing, run nothing else, go to the answer with `written` false.
   - The tool says the file does not exist: go to step 2.
   - Any other answer (the path is a folder, cannot be read): `failed`, one sentence, nothing written.

2. List the folder, with a `/` after the path so that it lists the folder's content:

   ```
   ls -1Ap <path>/
   ```

   - Non-zero exit and the output says `No such file or directory`: the folder does not exist, so it holds nothing. Go to step 3.
   - Exit 0: the output is one name per line; a folder's name ends with `/`. If a line is exactly `go.mod`: `unchanged`, as in step 1 (write nothing). Otherwise, if any line ends with `.go` (a file, not a folder): `pending` with the item `{ "item": "<path> has Go files but no go.mod", "reason": "manual", "how": "add a go.mod to <path>, or empty the folder" }`; write nothing. Otherwise (empty, or no Go file) go to step 3.
   - Any other non-zero exit (`Not a directory`: the path is a file; permission denied; anything else): `failed`, one sentence, nothing written.

3. Nothing is there.
   - `plan`: `would-create`; write nothing.
   - `apply`: read `${CLAUDE_PLUGIN_ROOT}/files/go.mod.tmpl`, `${CLAUDE_PLUGIN_ROOT}/files/main.go.tmpl` and `${CLAUDE_PLUGIN_ROOT}/files/main_test.go.tmpl` with the Read tool (not a shell command); if one cannot be read: `failed`, nothing written. In each, replace every `{{MODULE}}` with `module`, every `{{COMPONENT}}` with `component` and every `{{GO_VERSION}}` with `version`, and change nothing else: no other line, no reformatting, tabs kept as tabs, a final newline kept. Then write, with the Write tool, in this order: `<path>/main_test.go`, `<path>/main.go`, and `<path>/go.mod` last (so that a `go.mod` exists only when the other two do). All three written: `created`. A write that fails: stop, write nothing more, `failed`, one sentence naming the files that were written; when one was written, add the `pending` item of step 2, since the folder now has Go files and no `go.mod`.

## Answer

One sentence saying what happened: the files written (`created`), the files that would be written (`would-create`), that `<path>/go.mod` exists and nothing was written (`unchanged`), that `<path>` holds Go files and no `go.mod` (`pending`), or why it failed. Then the result block. The answer ends with exactly one block.

## Result block

```aleogr-result
{
  "aleogr-result": 1,
  "family": "stack",
  "provider": "go",
  "action": "setup",
  "mode": "apply",
  "status": "created",
  "resources": [],
  "outputs": {
    "component": "web",
    "path": "web",
    "module": "github.com/example-org/example-repo/web",
    "files": ["web/go.mod", "web/main.go", "web/main_test.go"],
    "written": true,
    "ci": { "workflow": "ci-go.yml", "inputs": { "working-directory": "web", "go-version": "1.27" } }
  },
  "cost": { "fixed": false, "notes": "writes local files only" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of: `created` (`apply`, the three files were written); `would-create` (`plan`, nothing is there; nothing written); `unchanged` (`<path>/go.mod` exists; nothing written); `pending` (`<path>` has Go files and no `go.mod`; nothing written; the item of step 2); `failed` (an argument, a read, the listing or a write failed).
- `outputs.files` is always the three expected paths, `<path>/go.mod`, `<path>/main.go`, `<path>/main_test.go`, in that order, whether or not this run wrote them. `outputs.written` is `true` only on `created`, `false` otherwise.
- `outputs.ci` is the component's CI parameters: the workflow `ci-go.yml`, with `working-directory` the `path` and `go-version` the `version`.
- On `failed` because of an argument, `outputs` is `null`. On any other `failed`, `outputs` has the shape above with `written` `false`.
- `resources` is always empty. `pending` is `[]` except for the item of step 2.
