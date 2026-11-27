"""tools-check: whether gcloud (by default), gh (command=gh) or go (command=go) is
ready, and where this session runs. Read-only.

The specification is skills/tools-check/SKILL.md: the same commands, in the same order,
the same states and the same result block. check() does the reads and decides the
tool's entry; run() turns it into the answer. project-plan calls check() directly (it
is in the same plugin), so its provider commands are exactly those of this command.
"""

import os

FAMILY = "orchestrator"
PROVIDER = "aleogr"
ACTION = "tools-check"
RESULT_MODE = "plan"  # mode is always plan
COST = {"fixed": False, "notes": "read-only check"}

COMMANDS = ("gcloud", "gh", "go")
GCLOUD_FIX = "https://cloud.google.com/sdk/docs/install"
GH_FIX = "https://cli.github.com"
GO_FIX = "https://go.dev/doc/install"

INVALID_COMMAND = "command must be gcloud, gh or go."
# The SKILL leaves the wording of these to the answer; fixed here.
AUTH_CHECK_FAILED = ("The authentication check itself failed, so gcloud is reported as not "
                     "authenticated.")
GCLOUD_CMD = "Every gcloud command must be run as gcloud.cmd."
CLOUD_SESSION = ("Infrastructure setup is done from the local app, where the CLIs are "
                 "authenticated.")
BLOCKED = {
    "gcloud": "Every platform skill needs gcloud: none can run until it is fixed.",
    "gh": "The GitHub repository skills cannot run until gh is fixed.",
    "go": ("The database check of a Go component (go_setup with database=yes) cannot be "
           "written until go is fixed."),
}
STATE_WORDS = {"ok": "ok", "missing": "missing", "not-authenticated": "not authenticated"}


def where(environ=None):
    """Step 1: cloud-session, codespace or local, from the environment variables."""
    env = os.environ if environ is None else environ
    if env.get("CLAUDE_CODE_REMOTE") == "true":
        return "cloud-session"
    if env.get("CODESPACES") == "true":
        return "codespace"
    return "local"


def _not_found(c):
    t = c.text.lower()
    return c.code == 127 or "command not found" in t or "not recognized" in t


def _first_line(c):
    for line in c.text.splitlines():
        if line.strip():
            return line.strip()
    return None


class Check(object):
    """What the check found: `where`, the tool's entry, and the notes of the answer."""

    def __init__(self, where, tool, notes=()):
        self.where = where
        self.tool = tool  # {"name", "command", "state", "fix"}
        self.notes = list(notes)  # extra sentences (gcloud.cmd, the failed check, ...)

    @property
    def ok(self):
        return self.tool["state"] == "ok"

    @property
    def status(self):
        return "unchanged" if self.ok else "failed"

    def outputs(self):
        return {"where": self.where, "tools": [dict(self.tool)]}


def _tool(name, command, state, fix):
    return {"name": name, "command": command, "state": state, "fix": fix}


def _gcloud(read):
    c = read(["gcloud", "--version"])
    command = "gcloud"
    if not c.ok:
        if _not_found(c):
            return _tool("gcloud", "gcloud", "missing", GCLOUD_FIX), []
        first = _first_line(c)
        c2 = read(["gcloud.cmd", "--version"])
        if not c2.ok:
            notes = []
            if first:
                notes.append("gcloud --version failed: %s" % first)
            return _tool("gcloud", "gcloud", "missing", GCLOUD_FIX), notes
        command = "gcloud.cmd"
    notes = [GCLOUD_CMD] if command == "gcloud.cmd" else []
    c = read([command, "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if not c.ok:
        return (_tool("gcloud", command, "not-authenticated", "gcloud auth login"),
                notes + [AUTH_CHECK_FAILED])
    if not c.out.strip():
        return _tool("gcloud", command, "not-authenticated", "gcloud auth login"), notes
    return _tool("gcloud", command, "ok", None), notes


def _gh(read):
    c = read(["gh", "--version"])
    if not c.ok:
        return _tool("gh", "gh", "missing", GH_FIX), []
    c = read(["gh", "auth", "status"])
    if not c.ok:
        return _tool("gh", "gh", "not-authenticated", "gh auth login"), []
    return _tool("gh", "gh", "ok", None), []


def _go(read):
    c = read(["go", "version"])
    if c.ok and c.out.startswith("go version go"):
        return _tool("go", "go", "ok", None), []
    return _tool("go", "go", "missing", GO_FIX), []


def check(command, read, environ=None):
    """The whole check, with `read` the read-only runner. command is gcloud, gh or go
    (already validated). Returns a Check."""
    w = where(environ)
    tool, notes = {"gcloud": _gcloud, "gh": _gh, "go": _go}[command](read)
    return Check(w, tool, notes)


def tool_line(tool):
    """`<name>: <state>` and the fix when it is not ok."""
    words = STATE_WORDS[tool["state"]]
    if tool["state"] == "ok":
        return "%s: ok." % tool["name"]
    return "%s: %s; fix: %s." % (tool["name"], words, tool["fix"])


def answer(chk):
    lines = [tool_line(chk.tool)]
    lines.extend(chk.notes)
    lines.append("Where it runs: %s." % chk.where)
    if not chk.ok:
        lines.append(BLOCKED[chk.tool["name"]])
    if chk.where == "cloud-session":
        lines.append(CLOUD_SESSION)
    return lines


def run(args, ctx):
    command = args.get("command", "gcloud")
    if command not in COMMANDS:
        return ctx.failed(INVALID_COMMAND, {"where": where(), "tools": []}, cost=dict(COST))
    chk = check(command, ctx.read)
    return ctx.result(chk.status, chk.outputs(), cost=dict(COST), lines=answer(chk))
