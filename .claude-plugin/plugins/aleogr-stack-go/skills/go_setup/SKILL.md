---
description: Go stack setup. Use to write the minimal starting point of a Go component in its folder - go.mod, main.go (an HTTP server with GET / and GET /healthz on the port in PORT, default 8080) and main_test.go - from templates the plugin ships, once and only when the folder has no go.mod and no Go file; with dockerfile=yes it also writes the component's Dockerfile (a static binary built with the component's Go version, on a distroless base, as a non-root user) when it is missing, also for a component whose module already exists; with database=yes it also writes the component's database check (db.go and db_test.go when missing, and the route GET /db in main.go only while main.go is still byte for byte the plugin's own file) and adds the pinned Cloud SQL connector and pgx modules with go get and go mod tidy, which needs Go. Otherwise it never overwrites anything and needs no Go toolchain. Returns the component's Go CI parameters (the reusable workflow ci-go.yml and its inputs). Plan by default.
allowed-tools: Bash(aleogr-stack-go --read-only go_setup), Bash(aleogr-stack-go --read-only go_setup *)
---

# go_setup

Writes the starting point of a Go component: exactly `<path>/go.mod`, `<path>/main.go` and `<path>/main_test.go`, filled from the templates in `${CLAUDE_PLUGIN_ROOT}/files/`. It writes them once: when `<path>/go.mod` exists it writes nothing, and when `<path>` holds a Go file without a `go.mod` it writes nothing and says so. With `dockerfile=yes` it also writes `<path>/Dockerfile` when that file is missing, also when the module already exists (its other files are still not touched); a `Dockerfile` that is there is never read and never overwritten. Without `database=yes` it never changes or overwrites a file and needs no Go toolchain (CI compiles and tests the code). It returns the CI parameters of the component.

With `database=yes` it also gives the component its database check, `GET /db`: `<path>/db.go` and `<path>/db_test.go`, each written only when missing; the route in `<path>/main.go`, which it replaces only while that file is still byte for byte the plugin's own `main.go` with the component's name filled in (a new component gets the variant with the route at once); and the modules of the check in `<path>/go.mod` and `<path>/go.sum`, changed only by one `go get` of the given modules followed by `go mod tidy`, and put back as they were, from a copy taken before, when a command failed, the module's `go` line moved or a `toolchain` line appeared. This needs Go where the skill runs, only in `apply` and only when the modules are to be added. It never changes any other file, and never writes a password or a connection string.

## Arguments

Free text after the skill name, as `key=value` pairs.

| Argument | Meaning |
|---|---|
| `component=<name>` | The component's name. Required. |
| `path=<folder>` | The component's folder, relative to the current folder. Default: the component's name. |
| `version=<major.minor>` | The Go language version, written on the `go` line of `go.mod` and passed to CI. Required. |
| `module=<module path>` | The Go module path: `github.com/<owner>/<repository>/<path>`. Required. |
| `dockerfile=<yes\|no>` | `yes` also handles `<path>/Dockerfile`. Default: `no`, which never looks at a `Dockerfile`. |
| `database=<yes\|no>` | `yes` also handles the component's database check and its modules. Default: `no`, which never looks at them and runs no `go` command. |
| `modules=<module>@<version>[,<module>@<version>...]` | The modules of the check with their versions, as `defaults.json` gives them in `stacks.go.database.modules`. Required with `database=yes`; not allowed without it. |
| `minVersion=<major.minor>` | The earliest Go version a component that uses the database may declare, as `defaults.json` gives it in `stacks.go.database.minVersion`. Required with `database=yes`; not allowed without it. |
| `mode=<plan\|apply>` | `plan` (default) only reads; `apply` writes the files when nothing is there. |

`component`, `version` and `module` are required, and `modules` and `minVersion` are required with `database=yes` and allowed only with it.

The command checks the arguments itself: pass them as they were given, and never ask for one that is missing.

## Run

Run one of these two commands with the Bash tool, once, with every argument given to this skill, unchanged and in the same order (no argument given: the command alone):

- When the arguments hold `mode=apply`, run exactly:

  ```
  aleogr-stack-go go_setup <arguments>
  ```

- In every other case (no `mode`, `mode=plan`, or any other value of `mode`), run exactly:

  ```
  aleogr-stack-go --read-only go_setup <arguments>
  ```

Run it in the foreground, with the Bash tool's `timeout` set to 600000 milliseconds, once: never in the background, and never a second time.

Write each argument inside single quotes, whatever it holds (`'project=demo'`, `'env=web:A=1;web:B=2'`), so the shell passes it as it is and reads nothing in it; a single quote inside an argument is written `'\''`. Never leave an argument unquoted and never use double quotes.

It prints two kinds of lines:

- Lines that begin with `+ ` are the commands it ran. They are shown by the tool already: never repeat them.
- Every other line is this skill's answer, ending with one fenced `aleogr-result` block.

Give that answer exactly as printed, character for character, the fenced block included and last. Add nothing before it, between its lines or after it; do not summarize, reword, translate or explain it. Run no other command, read no file, and do not run the command a second time, whatever it printed.

Only when the command printed no `aleogr-result` block at all (it was not found, or it stopped with an error), the answer is one sentence followed by the block below, and nothing else:

- When the command was the one for `mode=apply`, the sentence is `The command aleogr-stack-go ended without an answer: it may have changed something before it stopped. Read the state (run this skill with mode=plan, or the plan of the orchestrator) before running it again.` In the block, `"mode": "apply"` takes the place of `"mode": "plan"` and `"notes": "the run may have changed something"` the place of `"notes": "nothing was run"`.
- When it was the `--read-only` command, the sentence is `The command aleogr-stack-go could not be run: update the plugin aleogr-stack-go, then try again.` and the block is as it is below.

The block:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "stack",
  "provider": "go",
  "action": "setup",
  "mode": "plan",
  "status": "failed",
  "resources": [],
  "outputs": {},
  "cost": { "fixed": false, "notes": "nothing was run" },
  "pending": [ { "item": "command", "reason": "failed", "how": "update the plugin aleogr-stack-go, then try again" } ]
}
```

## Result block

When another skill invoked this one (an orchestrator, such as `aleogr:project-plan`, `aleogr:project-apply`, `aleogr:platform-plan` or `aleogr:platform-apply`), this skill still runs every step in full, each command exactly as its steps write it (the same flags and the same `--format`); only its lines and its block change role: they are that skill's input, not an answer to the owner, and the turn is not over when the block is written: go on at once with the invoking skill's next step (its next invocation, or its own table and block). The invoking skill's answer never contains this block and never ends with it.
