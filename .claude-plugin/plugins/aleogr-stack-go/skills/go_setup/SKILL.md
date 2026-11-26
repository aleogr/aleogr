---
description: Go stack setup. Use to write the minimal starting point of a Go component in its folder - go.mod, main.go (an HTTP server with GET / and GET /healthz on the port in PORT, default 8080) and main_test.go - from templates the plugin ships, once and only when the folder has no go.mod and no Go file; with dockerfile=yes it also writes the component's Dockerfile (a static binary built with the component's Go version, on a distroless base, as a non-root user) when it is missing, also for a component whose module already exists; with database=yes it also writes the component's database check (db.go and db_test.go when missing, and the route GET /db in main.go only while main.go is still byte for byte the plugin's own file) and adds the pinned Cloud SQL connector and pgx modules with go get and go mod tidy, which needs Go. Otherwise it never overwrites anything and needs no Go toolchain. Returns the component's Go CI parameters (the reusable workflow ci-go.yml and its inputs). Plan by default.
---

# go_setup

Writes the starting point of a Go component: exactly `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, filled from the templates in `${CLAUDE_PLUGIN_ROOT}/files/`. It writes them once: when `<path>/go.mod` exists it writes nothing, and when `<path>` holds a Go file without a `go.mod` it writes nothing and says so. With `dockerfile=yes` it also writes `<path>/Dockerfile` when that file is missing, also when the module already exists (its other files are still not touched); a `Dockerfile` that is there is never read and never overwritten. Without `database=yes` it never changes or overwrites a file and needs no Go toolchain (CI compiles and tests the code). It returns the CI parameters of the component.

With `database=yes` it also gives the component its database check, `GET /db` (steps 0, 5 and 6): `<path>/db.go` and `<path>/db_test.go`, each written only when missing; the route in `<path>/main.go`, which it replaces only while that file is still byte for byte the plugin's own `main.go` with the component's name filled in (a new component gets the variant with the route at once); and the modules of the check in `<path>/go.mod` and `<path>/go.sum`, changed only by one `go get` of the given modules followed by `go mod tidy`, and put back as they were when that moved the module's `go` line or wrote a `toolchain` line. This needs Go where the skill runs (in `apply`). It never changes any other file, and never writes a password or a connection string.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `component=<name>` | The component's name. Required. |
| `path=<folder>` | The component's folder, relative to the current folder. Default: the component's name. |
| `version=<major.minor>` | The Go language version, written on the `go` line of `go.mod` and passed to CI. Required. |
| `module=<module path>` | The Go module path: `github.com/<owner>/<repository>/<path>`. Required. |
| `dockerfile=<yes\|no>` | `yes` also handles `<path>/Dockerfile` (step 4). Default: `no`, which never looks at a `Dockerfile`. |
| `database=<yes\|no>` | `yes` also handles the component's database check and its modules (steps 0, 5 and 6). Default: `no`, which never looks at them and runs no `go` command. |
| `modules=<module>@<version>[,<module>@<version>...]` | The modules of the check with their versions, as `defaults.json` gives them in `stacks.go.database.modules`. Required with `database=yes`; not allowed without it. |
| `minVersion=<major.minor>` | The earliest Go version a component that uses the database may declare, as `defaults.json` gives it in `stacks.go.database.minVersion`. Required with `database=yes`; not allowed without it. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` writes the files when nothing is there. |

A missing required argument is never asked for: the run ends with the result block with `status` `failed`, one sentence naming every missing argument, and nothing read or written. Validate before reading anything; a value that breaks a rule ends with the result block with `status` `failed`, one sentence per broken rule, and nothing read or written:

- Every argument is one of the table; an unknown argument fails, and so does an argument given twice.
- `component` has 1 to 20 characters of `a-z`, `0-9` and `-`, and starts with a letter.
- `path` is the component's folder, relative to the current folder: it is made of one or more parts separated by `/` (so it does not start or end with `/` and has no empty part, `a//b` fails). Each part uses only `a-z`, `0-9`, `-`, `_` and `.`; it is not `.` or `..`, does not start with `-` or `.`, and does not end with `.` (so `.github`, `.aleogr` and every folder under them are never a component's folder: `.github/web` fails, and so does `path=-R`).
- `version` matches `^[0-9]+\.[0-9]+$` (`1.27`; not `1.27.4`, not `go1.27`), and is `1.22` or later, compared as numbers (`1.9` is earlier than `1.22`): the template's `GET /{$}` patterns need Go 1.22. An earlier version (`1.20`) fails with one sentence saying so.
- `module` is `github.com/` + `<owner>` + `/` + `<repository>` + `/` + `path`, exactly: `<owner>` has 1 to 39 characters of `A-Z`, `a-z`, `0-9` and `-` and does not start or end with `-`; `<repository>` has 1 to 100 characters of `A-Z`, `a-z`, `0-9`, `.`, `_` and `-` and is not `.` or `..`; and what follows them is the `path` argument (or its default) character for character. `module=github.com/example-org/example-repo/other` with `path=web` fails: the module must end with `/web`.
- `dockerfile`, when given, is `yes` or `no`.
- `database`, when given, is `yes` or `no`. With `database=yes`, `modules` and `minVersion` are required (a missing one is a missing required argument, above); without `database=yes` (`no`, or not given), `modules` or `minVersion` given fails with one sentence saying it is only allowed with `database=yes`.
- `modules` is one or more `<module>@<version>` separated by `,`, with no space and no empty element. Each `<module>` has only `A-Z`, `a-z`, `0-9`, `.`, `_`, `~`, `-` and `/`, starts with a letter or a digit, and has no empty part between `/` (no `//`, no `/` at either end); each `<version>` matches `^v[0-9]+\.[0-9]+\.[0-9]+$` (`v1.27.1`). The modules are exactly `cloud.google.com/go/cloudsqlconn` and `github.com/jackc/pgx/v5`, each once, in any order: the two that `db.go` imports.
- `minVersion` matches `^[0-9]+\.[0-9]+$`, and `version` is `minVersion` or later, compared as numbers. An earlier `version` fails with exactly `Go <version> is earlier than <minVersion>, the earliest version of a component that uses the database; nothing was written.`
- `mode`, when given, is `plan` or `apply`.

## Steps

Use the Read tool and the Write tool. The only command this skill may run is the single `ls` of step 2, at most once: no other command (no `mkdir`, `cat`, `test`, `find`, `go`, `gh`, `git`; the Write tool creates the folders), and no skill. With `database=yes`, and only then, it may also run the commands that steps 0, 5 and 6 write out, exactly as they are written there and each at most once (`go version`, the two `cmp` of step 5, `go -C <path> get`, `go -C <path> mod tidy` and the `rm` of step 6), and nothing else. Show each command before running it. `<path>/Dockerfile` is never read, with the Read tool or otherwise: whether it exists is known only from the listing of step 2.

A command whose result decides a step is run alone: not piped into another command, not wrapped in a subshell, so that its exit code is the one read. Each case below names both the exit code and the text that identifies it; when the two disagree, the text decides. The text is read to decide and is never quoted: the answer gives the cause in one sentence in its own words, with no raw error text.

A step that ends the run `failed` or `pending` ends it: no later step runs.

0. Only with `database=yes` and `mode=apply` (in `plan`, and without `database=yes`, this step never runs). Before reading or writing anything else, and with no other tool call at the same time, run, alone, from the current folder:

   ```
   go version
   ```

   - Exit 0 and the output starts with `go version go`: Go can run. Go to step 1.
   - Exit 127, or the output says `command not found` or `not found`: `failed`, nothing written, with exactly `Go is not installed where this skill runs; nothing was written.`
   - Any other answer: `failed`, nothing written, with exactly `Go could not be started where this skill runs; nothing was written.`

   On either failure the answer is that sentence and the result block, nothing else: no word of what `go version` printed, and no exit code.

1. Read `<path>/go.mod` in the current folder with the Read tool.
   - It has content, or the tool says the file exists but is empty: the component already has a module. With `dockerfile` `no` (or not given): `unchanged`: write nothing, run nothing else, go to the answer with `written` false. With `dockerfile=yes`: the module's files are never written; go to step 2 only to learn whether `<path>/Dockerfile` exists.
   - The tool says the file does not exist: go to step 2.
   - Any other answer (the path is a folder, cannot be read): `failed`, one sentence, nothing written.
   - With `database=yes`, an existing module does not end the run here: its `go.mod`, `main.go` and `main_test.go` are still never written by step 3, and the `Dockerfile` is still handled only with `dockerfile=yes`, as above; then, instead of going to the answer (with `dockerfile` `no`) or after step 4 (with `dockerfile=yes`), go to step 5.

2. List the folder, with a `/` after the path so that it lists the folder's content:

   ```
   ls -1Ap -- <path>/
   ```

   - Non-zero exit and the output says `No such file or directory`: the folder does not exist, so it holds nothing (and no `Dockerfile`). Go to step 3. (When step 1 found `go.mod`, this answer is `failed`, one sentence, nothing written.)
   - Exit 0: the output is one name per line; a folder's name ends with `/`. With `dockerfile=yes`, first: a line exactly `Dockerfile` means `<path>/Dockerfile` exists (it is `present`); no such line means it is missing; a line exactly `Dockerfile/` (a folder of that name): `failed`, one sentence, nothing written. Then: if step 1 found `go.mod`, or a line is exactly `go.mod`: the module exists; with `dockerfile` `no` (or not given), `unchanged`, as in step 1 (write nothing); with `dockerfile=yes`, go to step 4; with `database=yes`, as in step 1, go on to step 5 (after step 4 with `dockerfile=yes`). Otherwise, if any line ends with `.go` (a file, not a folder): `pending` with the item `{ "item": "<path> has Go files but no go.mod", "reason": "manual", "how": "add a go.mod to <path>, or empty the folder" }`; write nothing (with `dockerfile=yes`, not the `Dockerfile` either). Otherwise (empty, or no Go file) go to step 3. Only the folder's own entries count: subfolders are not searched.
   - Any other non-zero exit (`Not a directory`: the path is a file; permission denied; anything else): `failed`, one sentence, nothing written.

3. Nothing is there: no module and no Go file.
   - `plan`: `would-create`; write nothing. With `dockerfile=yes`, go to step 4. With `database=yes`, the check would be written with them: `database` `would-write`, `route` `would-add`, `modules` `would-add`; read nothing more and run nothing (after step 4 with `dockerfile=yes`, go to the answer).
   - `apply`: read `${CLAUDE_PLUGIN_ROOT}/files/go.mod.tmpl`, `${CLAUDE_PLUGIN_ROOT}/files/main.go.tmpl` and `${CLAUDE_PLUGIN_ROOT}/files/main_test.go.tmpl` with the Read tool (not a shell command); if one cannot be read: `failed`, nothing written. In each, replace every `{{MODULE}}` with `module`, every `{{COMPONENT}}` with `component` and every `{{GO_VERSION}}` with `version`, and change nothing else: no other line, no reformatting, tabs kept as tabs, a final newline kept. Then write, with the Write tool, in this order: `<path>/main_test.go`, `<path>/main.go`, and `<path>/go.mod` last (so that a `go.mod` exists only when the other two do). All three written: `created`; with `dockerfile=yes`, go to step 4. A write that fails: stop, write nothing more (not the `Dockerfile` either), `failed`, one sentence naming the files that were written; when one was written, add the `pending` item of step 2, since the folder now has Go files and no `go.mod`.
   - `apply` with `database=yes`: as `apply` above, with the check written with the starting files. Read `${CLAUDE_PLUGIN_ROOT}/files/main-database.go.tmpl` instead of `main.go.tmpl` (it is `main.go.tmpl` with the one line `mux.HandleFunc("GET /db", dbCheck)` added), and also `${CLAUDE_PLUGIN_ROOT}/files/db_test.go.tmpl` and `${CLAUDE_PLUGIN_ROOT}/files/db.go.tmpl`, with the same replacements (these two have none). Write `<path>/db_test.go`, then `<path>/db.go`, then `<path>/main_test.go`, `<path>/main.go` (from `main-database.go.tmpl`) and `<path>/go.mod` last. All five written: `created`, `database` `written`, `route` `added`; go to step 4 with `dockerfile=yes`, otherwise to step 6. A write that fails: as above.

4. The `Dockerfile`, only with `dockerfile=yes` (with `no`, or not given, this step never runs).
   - `<path>/Dockerfile` is present (the listing of step 2 showed it): write nothing to it, ever, and do not read it. The status is what step 3 gave (`created` or `would-create`), or, when the module already existed, `unchanged`.
   - It is missing and the mode is `plan`: write nothing; `would-create`.
   - It is missing and the mode is `apply`: write, with the Write tool, `<path>/Dockerfile` with exactly the lines below, replacing `{{GO_VERSION}}` with `version` and changing nothing else (no other line, no reformatting, a final newline). Do not read, write or change any other file: when the module already existed, its files stay as they are. Written: `created`. The write fails: `failed`, and `outputs.dockerfile` is `null`; the answer's sentence is exactly `<path>/Dockerfile could not be written; nothing was written.` when step 3 wrote nothing, and exactly `<path>/go.mod, <path>/main.go and <path>/main_test.go were written; <path>/Dockerfile could not be written.` when step 3 wrote the three files (the folder then has its `go.mod`, so no `pending` item); with `database=yes`, when step 3 wrote its five files, exactly `<path>/go.mod, <path>/main.go, <path>/main_test.go, <path>/db.go and <path>/db_test.go were written; <path>/Dockerfile could not be written.`
   - With `database=yes`, unless the step ended `failed`, go on: to step 5 when the module already existed, to step 6 when step 3 wrote it, to the answer when step 3 was `plan`.

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

5. The check's files in a module that already existed, only with `database=yes` (a new component got them in step 3).
   - Read `<path>/db.go` and `<path>/db_test.go` with the Read tool. Each one that has content, or that the tool says exists but is empty, is present: it is never written and never changed. Each one the tool says does not exist is missing. Any other answer: `failed`, one sentence, nothing written.
   - Whether `<path>/main.go` is still the plugin's own file is decided by `cmp`, byte for byte, never by reading and comparing: run, alone,

     ```
     cmp -s -- <path>/main.go <(sed -e 's/{{COMPONENT}}/<component>/g' -- "${CLAUDE_PLUGIN_ROOT}/files/main.go.tmpl")
     ```

     with `<component>` the component's name. The `sed` inside `<( )` only fills the template, replacing every `{{COMPONENT}}` with the name and nothing else; the exit code read is `cmp`'s own. `cmp` compares every byte: a different character, a tab written as spaces, a line ending `\r\n` instead of `\n`, a missing or an extra final newline each make the files differ. Exit 0: the files are equal: `main.go` is the plain file, and it is replaced (below). Any other exit (1: they differ; 2: `main.go` is missing or cannot be read): run, alone,

     ```
     cmp -s -- <path>/main.go <(sed -e 's/{{COMPONENT}}/<component>/g' -- "${CLAUDE_PLUGIN_ROOT}/files/main-database.go.tmpl")
     ```

     Exit 0: `main.go` already has the route: `route` `present`, it is not written. Any other exit: `main.go` is someone's code: it is never written; `route` `manual`, and `pending` gets the item `{ "item": "route", "reason": "manual", "how": "add the line mux.HandleFunc(\"GET /db\", dbCheck) to the router in <path>/main.go" }`, which does not change the status.
   - `plan`: write nothing. `database` is `would-write` when `db.go` or `db_test.go` is missing, `present` otherwise; `route` is `would-add` when `main.go` is the plain file. Go to step 6.
   - `apply`: for each missing file, read its template with the Read tool (`${CLAUDE_PLUGIN_ROOT}/files/db_test.go.tmpl`, `${CLAUDE_PLUGIN_ROOT}/files/db.go.tmpl`) and write it unchanged with the Write tool, `<path>/db_test.go` first, then `<path>/db.go`. Then, only when `main.go` is the plain file: read `${CLAUDE_PLUGIN_ROOT}/files/main-database.go.tmpl`, replace every `{{COMPONENT}}` with the component's name and change nothing else (tabs kept as tabs, a final newline kept), read `<path>/main.go` with the Read tool (the Write tool needs it; what it shows decides nothing), and write `<path>/main.go` with the result: `route` `added`. `database` is `written` when this step wrote `db.go` or `db_test.go`, `present` when both were present. A template that cannot be read, or a write that fails: stop, write nothing more, `failed`, one sentence naming the files this step wrote. Go to step 6.

6. The modules, only with `database=yes`, after step 3 (`apply`) or step 5.
   - Read `<path>/go.mod` with the Read tool. A module of `modules` is required when `go.mod` has a line `require <module> <any version>`, or a line whose first word is `<module>` between a line `require (` and the next line `)`; whatever version is there counts, and is never changed. Every module required: `modules` `present`; run nothing; go to the answer.
   - Otherwise, in `plan`: `modules` `would-add`; run nothing; go to the answer.
   - Otherwise, in `apply`: keep, exactly as read, the content of `<path>/go.mod`, its `go` line, and its `toolchain` line if it has one. Read `<path>/go.sum` with the Read tool: keep its content exactly as read, or that it does not exist. Then run, alone, every element of `modules` in the order given, separated by one space, in one command:

     ```
     go -C <path> get <module>@<version> <module>@<version>
     ```

     Exit 0: run, alone,

     ```
     go -C <path> mod tidy
     ```

     Exit 0: read `<path>/go.mod` again with the Read tool. Its `go` line must be exactly the one kept, and its `toolchain` line exactly the one kept (no `toolchain` line when there was none). Both hold: `modules` `added`, and the run has changed the module: `created`; go to the answer.
   - Putting back: when `go get` or `go mod tidy` ends with another exit, or the `go` line or the `toolchain` line is not the one kept, put `<path>/go.mod` and `<path>/go.sum` back as they were: read `<path>/go.mod` with the Read tool (the Write tool needs a read of the file as it is now) and write it with exactly the content kept; when `go.sum` existed, read it the same way and write it with exactly the content kept; when it did not exist, run, alone, `rm -f -- <path>/go.sum`. Then `failed`, with exactly:
     - `go get` failed: `The database modules could not be added to <path>/go.mod; <path>/go.mod and <path>/go.sum are as they were.`
     - `go mod tidy` failed: `go mod tidy could not complete in <path>; <path>/go.mod and <path>/go.sum were put back as they were.`
     - the `go` line or the `toolchain` line changed: `The database modules need a newer Go than <path>/go.mod declares (<the go line kept>); <path>/go.mod and <path>/go.sum were put back as they were.`
     - A write or the `rm` of the putting back fails: `<path>/go.mod and <path>/go.sum could not be put back as they were; restore them from the repository.`

     The files steps 3 and 5 wrote stay as they are.

## Answer

One sentence saying what happened: the files written (`created`), the files that would be written (`would-create`), that `<path>/go.mod` exists and nothing was written (`unchanged`), that `<path>` holds Go files and no `go.mod` (`pending`), or why it failed. With `dockerfile=yes` the sentence also says whether `<path>/Dockerfile` was written, would be written, or was already there and left as it is. With `database=yes` it also says, in the same sentence or one more, what happened to the check's files, the route and the modules, and, with `route` `manual`, that `main.go` was left as it is and the one line to add. Then the result block. The answer ends with exactly one block.

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
    "database": "not-asked",
    "route": "not-asked",
    "modules": "not-asked",
    "ci": { "workflow": "ci-go.yml", "inputs": { "working-directory": "web", "go-version": "1.27" } }
  },
  "cost": { "fixed": false, "notes": "writes local files only" },
  "pending": []
}
```

- `mode` echoes the mode used (`plan` when not given). With `database=yes`, `status` counts the check too: `created` when this run wrote any file (the starting files, `db.go`, `db_test.go`, `main.go`, the `Dockerfile`) or added the modules; `would-create` in `plan` when any of them would be written or added; `unchanged` when nothing was written and nothing is to write (`database` `present`, `route` `present` or `manual`, `modules` `present`, and with `dockerfile=yes` the `Dockerfile` present). Otherwise `status` is one of: `created` (`apply`, the three files were written; with `dockerfile=yes`, the three files, the `Dockerfile`, or both were written); `would-create` (`plan`, nothing is there; with `dockerfile=yes`, also a module whose `Dockerfile` is missing; nothing written); `unchanged` (`<path>/go.mod` exists, and with `dockerfile=yes` so does `<path>/Dockerfile`; nothing written); `pending` (`<path>` has Go files and no `go.mod`; nothing written; the item of step 2); `failed` (an argument, a read, the listing or a write failed).
- `outputs.files` is always the three expected paths, `<path>/go.mod`, `<path>/main.go`, `<path>/main_test.go`, in that order, whether or not this run wrote them; with `database=yes`, `<path>/go.sum`, `<path>/db.go` and `<path>/db_test.go` follow them; with `dockerfile=yes`, `<path>/Dockerfile` comes last (the fourth path without `database=yes`). `outputs.written` is `true` only when this run wrote the three Go files (`created` of a new component), `false` otherwise (also when only the `Dockerfile` was written).
- `outputs.dockerfile`: `not-asked` when `dockerfile` is `no` or not given. With `dockerfile=yes`: `written` (this run wrote `<path>/Dockerfile`); `would-write` (it is missing and was not written: `plan`, or `pending`, since nothing is written while the folder has Go files and no `go.mod`); `present` (the listing showed it; it was not read and not changed).
- `outputs.database`, `outputs.route` and `outputs.modules` are `not-asked` without `database=yes`. With it: `database` is `written` (this run wrote `db.go`, `db_test.go` or both), `would-write` (one is missing and was not written: `plan`, or `pending`), or `present` (both were there; never changed); `route` is `added` (this run wrote `main.go` with the route), `would-add` (`plan`, or `pending`, of a new component or a plain `main.go`), `present` (`main.go` already has it), or `manual` (`main.go` is someone's code: left as it is, the item `route` in `pending`); `modules` is `added` (`go get` and `go mod tidy` added them and the `go` line did not move), `would-add` (some module is not required and was not added: `plan`, or `pending`), or `present` (every module was already required; no `go` command ran).
- `outputs.ci` is the component's CI parameters: the workflow `ci-go.yml`, with `working-directory` the `path` and `go-version` the `version`.
- On `failed` because of an argument, `outputs` keeps the same keys with what is known: `component` and `path` as received when each is valid, otherwise `null` (`path` is the default when not given and `component` is valid); `module` `null`; `files` `[]`; `written` `false`; `dockerfile` `null`; `ci` `null`. With `database=yes`, on `failed` because of an argument, `database`, `route` and `modules` are `null`; on `failed` in step 0 the arguments were valid, so `outputs` has the shape of any other `failed` (below), with `database`, `route` and `modules` `null`; on any later `failed`, each is what the run had reached (`database` `written` and `route` `added` stay true of files written before the failure), and `null` for what it had not reached, `modules` `null` when step 6 put the module back. Without `database=yes` they are `not-asked` on every end. On any other `failed`, `outputs` has the shape above with `written` `false`, and `dockerfile` `not-asked` without `dockerfile=yes`, otherwise `present` when the listing showed it, `written` when this run wrote it, and `null` otherwise: when the listing did not run or did not end, and when the write of step 4 failed (even after the three files of step 3 were written).
- `resources` is always empty. `pending` is `[]` except for the item of step 2 and, with `database=yes`, the item `route` of step 5.
