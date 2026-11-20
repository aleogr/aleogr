---
description: Go stack setup. Use to write the minimal starting point of a Go component in its folder - go.mod, main.go (an HTTP server with GET / and GET /healthz on the port in PORT, default 8080) and main_test.go - from templates the plugin ships, once and only when the folder has no go.mod and no Go file; with dockerfile=yes it also writes the component's Dockerfile (a static binary built with the component's Go version, on a distroless base, as a non-root user) when it is missing, also for a component whose module already exists; it never overwrites anything. Returns the component's Go CI parameters (the reusable workflow ci-go.yml and its inputs). Needs no Go toolchain. Plan by default.
---

# go_setup

Writes the starting point of a Go component: exactly `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, filled from the templates in `${CLAUDE_PLUGIN_ROOT}/files/`. It writes them once: when `<path>/go.mod` exists it writes nothing, and when `<path>` holds a Go file without a `go.mod` it writes nothing and says so. With `dockerfile=yes` it also writes `<path>/Dockerfile` when that file is missing, also when the module already exists (its other files are still not touched); a `Dockerfile` that is there is never read and never overwritten. It never changes or overwrites a file. It needs no Go toolchain (CI compiles and tests the code) and returns the CI parameters of the component.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `component=<name>` | The component's name. Required. |
| `path=<folder>` | The component's folder, relative to the current folder. Default: the component's name. |
| `version=<major.minor>` | The Go language version, written on the `go` line of `go.mod` and passed to CI. Required. |
| `module=<module path>` | The Go module path: `github.com/<owner>/<repository>/<path>`. Required. |
| `dockerfile=<yes\|no>` | `yes` also handles `<path>/Dockerfile` (step 4). Default: `no`, which never looks at a `Dockerfile`. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` writes the files when nothing is there. |

A missing required argument is never asked for: the run ends with the result block with `status` `failed`, one sentence naming every missing argument, and nothing read or written. Validate before reading anything; a value that breaks a rule ends with the result block with `status` `failed`, one sentence per broken rule, and nothing read or written:

- Every argument is one of the table; an unknown argument fails, and so does an argument given twice.
- `component` has 1 to 20 characters of `a-z`, `0-9` and `-`, and starts with a letter.
- `path` is the component's folder, relative to the current folder: it is made of one or more parts separated by `/` (so it does not start or end with `/` and has no empty part, `a//b` fails). Each part uses only `a-z`, `0-9`, `-`, `_` and `.`; it is not `.` or `..`, does not start with `-` or `.`, and does not end with `.` (so `.github`, `.aleogr` and every folder under them are never a component's folder: `.github/web` fails, and so does `path=-R`).
- `version` matches `^[0-9]+\.[0-9]+$` (`1.27`; not `1.27.4`, not `go1.27`), and is `1.22` or later, compared as numbers (`1.9` is earlier than `1.22`): the template's `GET /{$}` patterns need Go 1.22. An earlier version (`1.20`) fails with one sentence saying so.
- `module` is `github.com/` + `<owner>` + `/` + `<repository>` + `/` + `path`, exactly: `<owner>` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-` and does not start or end with `-`; `<repository>` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-` and is not `.` or `..`; and what follows them is the `path` argument (or its default) character for character. `module=github.com/example-org/example-repo/other` with `path=web` fails: the module must end with `/web`.
- `dockerfile`, when given, is `yes` or `no`.
- `mode`, when given, is `plan` or `apply`.

## Steps

Use the Read tool and the Write tool. The only command this skill may run is the single `ls` of step 2, at most once: no other command (no `mkdir`, `cat`, `test`, `find`, `go`, `gh`, `git`; the Write tool creates the folders), and no skill. Show the command before running it. `<path>/Dockerfile` is never read, with the Read tool or otherwise: whether it exists is known only from the listing of step 2.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree, the text decides. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

1. Read `<path>/go.mod` in the current folder with the Read tool.
   - It has content, or the tool says the file exists but is empty: the component already has a module. With `dockerfile` `no` (or not given): `unchanged`: write nothing, run nothing else, go to the answer with `written` false. With `dockerfile=yes`: the module's files are never written; go to step 2 only to learn whether `<path>/Dockerfile` exists.
   - The tool says the file does not exist: go to step 2.
   - Any other answer (the path is a folder, cannot be read): `failed`, one sentence, nothing written.

2. List the folder, with a `/` after the path so that it lists the folder's content:

   ```
   ls -1Ap -- <path>/
   ```

   - Non-zero exit and the output says `No such file or directory`: the folder does not exist, so it holds nothing (and no `Dockerfile`). Go to step 3. (When step 1 found `go.mod`, this answer is `failed`, one sentence, nothing written.)
   - Exit 0: the output is one name per line; a folder's name ends with `/`. With `dockerfile=yes`, first: a line exactly `Dockerfile` means `<path>/Dockerfile` exists (it is `present`); no such line means it is missing; a line exactly `Dockerfile/` (a folder of that name): `failed`, one sentence, nothing written. Then: if step 1 found `go.mod`, or a line is exactly `go.mod`: the module exists; with `dockerfile` `no` (or not given), `unchanged`, as in step 1 (write nothing); with `dockerfile=yes`, go to step 4. Otherwise, if any line ends with `.go` (a file, not a folder): `pending` with the item `{ "item": "<path> has Go files but no go.mod", "reason": "manual", "how": "add a go.mod to <path>, or empty the folder" }`; write nothing (with `dockerfile=yes`, not the `Dockerfile` either). Otherwise (empty, or no Go file) go to step 3. Only the folder's own entries count: subfolders are not searched.
   - Any other non-zero exit (`Not a directory`: the path is a file; permission denied; anything else): `failed`, one sentence, nothing written.

3. Nothing is there: no module and no Go file.
   - `plan`: `would-create`; write nothing. With `dockerfile=yes`, go to step 4.
   - `apply`: read `${CLAUDE_PLUGIN_ROOT}/files/go.mod.tmpl`, `${CLAUDE_PLUGIN_ROOT}/files/main.go.tmpl` and `${CLAUDE_PLUGIN_ROOT}/files/main_test.go.tmpl` with the Read tool (not a shell command); if one cannot be read: `failed`, nothing written. In each, replace every `{{MODULE}}` with `module`, every `{{COMPONENT}}` with `component` and every `{{GO_VERSION}}` with `version`, and change nothing else: no other line, no reformatting, tabs kept as tabs, a final newline kept. Then write, with the Write tool, in this order: `<path>/main_test.go`, `<path>/main.go`, and `<path>/go.mod` last (so that a `go.mod` exists only when the other two do). All three written: `created`; with `dockerfile=yes`, go to step 4. A write that fails: stop, write nothing more (not the `Dockerfile` either), `failed`, one sentence naming the files that were written; when one was written, add the `pending` item of step 2, since the folder now has Go files and no `go.mod`.

4. The `Dockerfile`, only with `dockerfile=yes` (with `no`, or not given, this step never runs).
   - `<path>/Dockerfile` is present (the listing of step 2 showed it): write nothing to it, ever, and do not read it. The status is what step 3 gave (`created` or `would-create`), or, when the module already existed, `unchanged`.
   - It is missing and the mode is `plan`: write nothing; `would-create`.
   - It is missing and the mode is `apply`: write, with the Write tool, `<path>/Dockerfile` with exactly the lines below, replacing `{{GO_VERSION}}` with `version` and changing nothing else (no other line, no reformatting, a final newline). Do not read, write or change any other file: when the module already existed, its files stay as they are. Written: `created`. The write fails: `failed`, one sentence naming the files this run wrote (the three of step 3, when it wrote them; the folder then has its `go.mod`, so no `pending` item).

   ```dockerfile
   # Generated by aleogr. Written once and never overwritten: it is yours to change.
   FROM golang:{{GO_VERSION}} AS build
   WORKDIR /src
   COPY go.mod go.sum* ./
   RUN go mod download
   COPY . .
   RUN CGO_ENABLED=0 go build -trimpath -o /out/app .

   FROM gcr.io/distroless/static-debian13:nonroot
   COPY --from=build /out/app /app
   USER nonroot:nonroot
   ENTRYPOINT ["/app"]
   ```

   The lines are written without the indentation of this list. `go.sum*` copies `go.sum` when there is one: a module with no dependency has none. The base images are named by tag, not by digest, so that they receive security fixes.

## Answer

One sentence saying what happened: the files written (`created`), the files that would be written (`would-create`), that `<path>/go.mod` exists and nothing was written (`unchanged`), that `<path>` holds Go files and no `go.mod` (`pending`), or why it failed. With `dockerfile=yes` the sentence also says whether `<path>/Dockerfile` was written, would be written, or was already there and left as it is. Then the result block. The answer ends with exactly one block.

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.

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
    "dockerfile": "not-asked",
    "ci": { "workflow": "ci-go.yml", "inputs": { "working-directory": "web", "go-version": "1.27" } }
  },
  "cost": { "fixed": false, "notes": "writes local files only" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). `status` is one of: `created` (`apply`, the three files were written; with `dockerfile=yes`, the three files, the `Dockerfile`, or both were written); `would-create` (`plan`, nothing is there; with `dockerfile=yes`, also a module whose `Dockerfile` is missing; nothing written); `unchanged` (`<path>/go.mod` exists, and with `dockerfile=yes` so does `<path>/Dockerfile`; nothing written); `pending` (`<path>` has Go files and no `go.mod`; nothing written; the item of step 2); `failed` (an argument, a read, the listing or a write failed).
- `outputs.files` is always the three expected paths, `<path>/go.mod`, `<path>/main.go`, `<path>/main_test.go`, in that order, whether or not this run wrote them; with `dockerfile=yes`, `<path>/Dockerfile` follows them as a fourth path. `outputs.written` is `true` only when this run wrote the three Go files (`created` of a new component), `false` otherwise (also when only the `Dockerfile` was written).
- `outputs.dockerfile`: `not-asked` when `dockerfile` is `no` or not given. With `dockerfile=yes`: `written` (this run wrote `<path>/Dockerfile`); `would-write` (it is missing and was not written: `plan`, or `pending`, since nothing is written while the folder has Go files and no `go.mod`); `present` (the listing showed it; it was not read and not changed).
- `outputs.ci` is the component's CI parameters: the workflow `ci-go.yml`, with `working-directory` the `path` and `go-version` the `version`.
- On `failed` because of an argument, `outputs` keeps the same keys with what is known: `component` and `path` as received when each is valid, otherwise `null` (`path` is the default when not given and `component` is valid); `module` `null`; `files` `[]`; `written` `false`; `dockerfile` `null`; `ci` `null`. On any other `failed`, `outputs` has the shape above with `written` `false`, and `dockerfile` `not-asked` without `dockerfile=yes`, otherwise `present` when the listing showed it, `written` when this run wrote it, and `null` when it is not known.
- `resources` is always empty. `pending` is `[]` except for the item of step 2.
