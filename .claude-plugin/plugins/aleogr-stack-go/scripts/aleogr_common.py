"""Shared module of the aleogr plugin commands.

One copy of this file lives in every plugin, under `scripts/`, and the copies are
byte-identical (a unit test fails when they differ): an installed plugin reaches only
its own files. Change one copy, then copy it over the five others.

It holds what every command needs and nothing of a skill's own rules:

- the command line (`<command> [--read-only] [--json] <skill> [key=value ...]`,
  `<command> --has <skill> [mode]`) and the dispatch to `scripts/skills/<module>.py`;
- `key=value` arguments;
- a runner that shows a provider command on stderr, then runs it, and returns its exit
  code, stdout and stderr; a READ-ONLY runner that refuses, before running it, any
  provider command that is not on the allowlist of reads (`READS` below); and a WRITING
  runner, given to a skill only in `mode=apply` without `--read-only`, that refuses any
  command that is not on its skill's allowlist of writes (`WRITE_SHAPES` below);
- the files of the current folder a skill writes (`FILE_WRITES`), the copies it keeps
  of them and puts back, and the waits of a run, within one budget;
- the clock of a run: waits end at seven minutes (WAIT_CLOCK_LIMIT), every provider
  command is bounded by the run's deadline (RUN_DEADLINE, a TimeLimit when it is
  reached), an orchestrator begins no step after four minutes (STEP_LIMIT), and an
  aborted run still ends with a `failed` result (aborted_result);
- `call_plugin`, which runs another plugin's command with `--json` and passes it this
  run's deadline (ALEOGR_RUN_ENDS);
- a run in more than one command, for the skills that declare CONTINUES: the status
  `continue`, its `next:` line, and the private file carried from one command to the
  next (ctx.carried, ctx.may_continue, ctx.continue_run);
- the answer: lines, a table, and the fenced `aleogr-result` block.

Python 3.9 or later, standard library only.
"""

import atexit
import errno
import importlib
import json
import os
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

# ---------------------------------------------------------------------------
# Exit codes and errors

EXIT_OK = 0  # a result was produced, whatever its status (failed included)
EXIT_USAGE = 2  # bad usage: unknown option, malformed argument, unknown skill
EXIT_NOT_CONVERTED = 64  # the skill, or this mode of it, is not converted
EXIT_SOFTWARE = 70  # a bug of the command: a refused read or write (after its `failed`
#                     result), an unexpected exception

PROVIDER_TOOLS = ("gcloud", "gh", "git", "go")


class UsageError(Exception):
    """Bad usage of a command (exit 2)."""


class ReadRefused(Exception):
    """A command that is not a read was given to the read-only runner.

    It is raised before anything runs. It is a bug of the skill's code, never a state
    of the provider: the dispatcher prints one line on stderr (without the command's
    values), prints the fixed `failed` result of a refusal (refused_result) and exits 70.
    """

    def __init__(self, argv, reason):
        self.argv = list(argv)
        self.reason = reason
        super().__init__("refused, not a read: %s (%s)" % (show_command(argv), reason))


class TimeLimit(Exception):
    """The run's deadline (RUN_DEADLINE) was reached while a provider command was still
    running: the command was killed, and may still take effect (a create that the
    provider had accepted goes on without it).

    `shown` is the command as its `+ ` line showed it (a Hidden value as `<value>`). The
    dispatcher prints the fixed `failed` result of an aborted run (aborted_result) and
    exits 70."""

    def __init__(self, argv):
        self.shown = argv if isinstance(argv, str) else show_command(argv)
        super().__init__("the run's time limit was reached while running: %s" % self.shown)


class WriteRefused(Exception):
    """A write the writing runner (or the file helpers) refused: a command that is not
    on the skill's allowlist of writes, a file the skill may not write, or any write
    outside `mode=apply` or under `--read-only`.

    It is raised before anything runs or is shown. Like ReadRefused it is a bug of the
    skill's code: the dispatcher prints one line on stderr (without the command's
    values), prints the fixed `failed` result of a refusal (refused_result) and exits 70.
    """

    def __init__(self, what, reason):
        self.what = what
        self.reason = reason
        super().__init__("refused, not an allowed write: %s (%s)" % (what, reason))


# ---------------------------------------------------------------------------
# Arguments

_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_SKILL = re.compile(r"^[a-z][a-z0-9_-]*$")


def parse_args(tokens, repeated=None):
    """Parse `key=value` tokens into a dict (insertion order kept).

    The value is everything after the first `=`, and may be empty or hold more `=`
    (`variables=A=1,B=2`). A token without `=`, or a key that is not letters and digits
    starting with a letter, is a UsageError. A key given twice is a UsageError too,
    unless `repeated` is a list: the key is then added to it (once), and its first value
    is kept. The dispatcher passes one, and answers a repeated key with a `failed`
    result (REPEATED_SENTENCE) without running the skill.
    """
    args = {}
    for token in tokens:
        key, sep, value = token.partition("=")
        if not sep:
            raise UsageError("argument is not key=value: %s" % token)
        if not _KEY.match(key):
            raise UsageError("bad argument name: %s" % key)
        if key in args:
            if repeated is None:
                raise UsageError("argument given twice: %s" % key)
            if key not in repeated:
                repeated.append(key)
            continue
        args[key] = value
    return args


def format_args(args):
    """The inverse of parse_args: a dict (or list of pairs) as `key=value` tokens."""
    items = args.items() if isinstance(args, dict) else args
    return ["%s=%s" % (k, "" if v is None else v) for k, v in items]


class Invocation(object):
    """A parsed command line."""

    def __init__(self, skill, args, json_mode=False, has=False, mode=None, read_only=False,
                 repeated=()):
        self.skill = skill
        self.args = args
        self.json = json_mode
        self.has = has
        self.mode = mode
        self.read_only = read_only
        self.repeated = list(repeated)  # keys given more than once, in order


def parse_command_line(argv):
    """Parse the arguments of `<command> ...` (without the command itself).

    `[--read-only] [--json] <skill> [key=value ...]` (the two options in either order,
    each at most once) or `--has <skill> [mode]`. Raises UsageError. A key=value
    argument given twice is not a UsageError: it is listed in `repeated`.
    """
    argv = list(argv)
    if not argv:
        raise UsageError("no skill given")
    if argv[0] == "--has":
        if len(argv) not in (2, 3):
            raise UsageError("usage: --has <skill> [mode]")
        skill = argv[1]
        if not _SKILL.match(skill):
            raise UsageError("bad skill name: %s" % skill)
        return Invocation(skill, {}, has=True, mode=argv[2] if len(argv) == 3 else None)
    json_mode = False
    read_only = False
    while argv and argv[0] in ("--json", "--read-only"):
        if argv[0] == "--json":
            if json_mode:
                raise UsageError("--json given twice")
            json_mode = True
        else:
            if read_only:
                raise UsageError("--read-only given twice")
            read_only = True
        argv = argv[1:]
    if not argv:
        raise UsageError("no skill given")
    skill = argv[0]
    if skill.startswith("-"):
        raise UsageError("unknown option: %s" % skill)
    if not _SKILL.match(skill):
        raise UsageError("bad skill name: %s" % skill)
    repeated = []
    args = parse_args(argv[1:], repeated)
    return Invocation(skill, args, json_mode=json_mode, read_only=read_only,
                      repeated=repeated)


def module_name(skill):
    """The module of a skill: its name with `-` written `_`."""
    return skill.replace("-", "_")


# ---------------------------------------------------------------------------
# Reads: the allowlist
#
# A provider command is a read when it matches one shape below; anything else is
# refused by the read-only runner before it runs. To accept a new read, add its shape
# here (and a case to .claude-plugin/tests/unit), in every copy of this file.
#
# A shape is a tuple of the leading words of the command after the tool (after the
# tool's leading global options for git and go), optionally followed by a guard: a
# function of the remaining arguments that returns None when they keep the call a read,
# or a reason why not.

_GH_API_VALUE_FLAGS = {
    "-X", "--method", "-H", "--header", "-f", "--raw-field", "-F", "--field",
    "--input", "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p",
    "--preview",
}
_GH_API_BODY_FLAGS = ("-f", "--raw-field", "-F", "--field", "--input")


def _gh_api(rest):
    """`gh api <endpoint>`: a read without a method or with GET, and with a body
    (`-f`, `-F`, `--field`, `--raw-field`, `--input`) only under an explicit GET.
    `graphql` is refused (it can hold a mutation)."""
    method = None
    body = False
    endpoint = None
    i = 0
    while i < len(rest):
        a = rest[i]
        flag, value = a, None
        if a.startswith("--") and "=" in a:
            flag, value = a.split("=", 1)
        elif a.startswith("-X") and len(a) > 2:
            flag, value = "-X", a[2:]
        elif len(a) > 2 and a[:2] in ("-f", "-F", "-H", "-q", "-t", "-p") and not a.startswith("--"):
            flag, value = a[:2], a[2:]
        if flag in _GH_API_VALUE_FLAGS:
            if value is None:
                i += 1
                value = rest[i] if i < len(rest) else ""
            if flag in ("-X", "--method"):
                method = value.upper()
            if flag in _GH_API_BODY_FLAGS:
                body = True
        elif a.startswith("--") or a == "-i":
            pass  # a boolean flag: --paginate, --slurp, -i, --silent, --verbose
        elif a.startswith("-"):
            # Short flags written together (-iXPOST, -if a=b) can hide a method or a body.
            return "short flags written together"
        elif endpoint is None:
            endpoint = a
        i += 1
    if endpoint is None:
        return "no endpoint"
    if endpoint == "graphql":
        return "graphql can write"
    if method is not None and method != "GET":
        return "method %s" % method
    if body and method != "GET":
        return "a body without an explicit GET is a POST"
    return None


def _no_arguments(rest):
    """Accepts the command only with nothing after it (`gh auth status -t` prints the token,
    also when `-t` is written together with another short flag)."""
    return "arguments are not accepted here" if rest else None


def _no_flags(*refused):
    def guard(rest):
        for a in rest:
            for r in refused:
                if a == r or a.startswith(r + "="):
                    return "flag %s" % r
        return None
    return guard


def _git_config(rest):
    """`git config` reads only with --get, --get-all, --get-regexp, --get-urlmatch,
    --list or -l, or as `git config get|list` (Git 2.46), and no writing action."""
    writes = ("--add", "--unset", "--unset-all", "--replace-all", "--rename-section",
              "--remove-section", "--edit", "-e")
    for a in rest:
        if a in writes:
            return "git config %s" % a
    if rest and rest[0] in ("get", "list"):
        return None
    if any(a in ("--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l")
           for a in rest):
        return None
    return "git config without --get or --list"


def _git_branch(rest):
    allowed = {"--show-current", "--list", "-l", "-a", "--all", "-r", "--remotes", "-v",
               "-vv", "--no-color"}
    for a in rest:
        if a not in allowed and not a.startswith("--format="):
            return "git branch %s" % a
    return None


def _git_remote(rest):
    if not rest or rest == ["-v"] or rest == ["--verbose"]:
        return None
    if rest[0] == "get-url":
        return None
    return "git remote %s" % rest[0]


def _go_env(rest):
    for a in rest:
        if a in ("-w", "-u"):
            return "go env %s" % a
    return None


def _sleep(rest):
    if len(rest) == 1 and re.match(r"^[0-9]+$", rest[0]):
        return None
    return "sleep takes one number of seconds"


def _only(*allowed):
    """Accepts the command only when what follows it is exactly `allowed`
    (`gcloud config get-value account`, and no other property)."""
    def guard(rest):
        return None if list(rest) == list(allowed) else "only %s here" % " ".join(allowed)
    return guard


_GIT_NO_OUTPUT = _no_flags("--output", "--ext-diff")

READS = {
    "gcloud": [
        ("--version",),
        ("auth", "list"),
        ("organizations", "list"),
        ("resource-manager", "folders", "list"),
        ("resource-manager", "folders", "describe"),
        ("projects", "list"),
        ("projects", "describe"),
        ("projects", "get-iam-policy"),
        ("billing", "projects", "describe"),
        ("services", "list"),
        ("iap", "settings", "get"),
        ("iap", "web", "get-iam-policy"),
        ("iam", "service-accounts", "describe"),
        ("iam", "service-accounts", "list"),
        ("iam", "service-accounts", "get-iam-policy"),
        ("iam", "workload-identity-pools", "describe"),
        ("iam", "workload-identity-pools", "list"),
        ("iam", "workload-identity-pools", "providers", "describe"),
        ("iam", "workload-identity-pools", "providers", "list"),
        ("run", "services", "describe"),
        ("run", "services", "list"),
        ("run", "services", "get-iam-policy"),
        ("artifacts", "repositories", "describe"),
        ("artifacts", "repositories", "list"),
        ("artifacts", "repositories", "get-iam-policy"),
        ("sql", "instances", "describe"),
        ("sql", "instances", "list"),
        ("sql", "operations", "list"),
        ("sql", "operations", "describe"),
        ("sql", "backups", "list"),
        ("sql", "databases", "list"),
        ("sql", "databases", "describe"),
        ("sql", "users", "list"),
        ("billing", "budgets", "list"),
        ("billing", "budgets", "describe"),
        # Added for part 2b (the skills that write to Google Cloud read these too).
        ("billing", "accounts", "list"),
        ("config", "get-value", _only("account")),
        ("organizations", "get-iam-policy"),
        ("iam", "roles", "describe"),
        ("scheduler", "jobs", "describe"),
    ],
    "gh": [
        ("--version",),
        ("auth", "status", _no_arguments),
        ("api", _gh_api),
        ("repo", "view"),
        ("pr", "list"),
        ("pr", "view"),
        ("pr", "checks"),
        ("secret", "list"),
        ("variable", "list"),
        ("variable", "get"),
    ],
    "git": [
        ("--version",),
        ("version",),
        ("status",),
        ("rev-parse",),
        ("rev-list",),
        ("ls-files",),
        ("diff", _GIT_NO_OUTPUT),
        ("log", _GIT_NO_OUTPUT),
        ("show", _GIT_NO_OUTPUT),
        ("merge-base",),
        ("cat-file",),
        ("branch", _git_branch),
        ("remote", _git_remote),
        ("config", _git_config),
    ],
    "go": [
        ("version",),
        ("env", _go_env),
    ],
    # The fake wait of the tests and the real one: it reads and changes nothing.
    "sleep": [
        (_sleep,),
    ],
}


def _tool_name(argv0):
    name = os.path.basename(argv0)
    if name.endswith(".cmd") or name.endswith(".exe"):
        name = name[:-4]
    return name


def _strip_global(tool, args):
    """Remove the leading global options that the allowlist accepts: `-C <dir>` and
    `--no-pager` for git, `-C <dir>` for go. Returns (rest, reason or None)."""
    args = list(args)
    if tool == "git":
        while args and args[0].startswith("-") and args[0] not in ("--version",):
            if args[0] == "-C" and len(args) > 1:
                args = args[2:]
            elif args[0] == "--no-pager":
                args = args[1:]
            else:
                # -c can set core.pager, core.fsmonitor ... and run a program.
                return args, "git global option %s" % args[0]
    if tool == "go":
        if len(args) > 1 and args[0] == "-C":
            args = args[2:]
    return args, None


def read_refusal(argv):
    """None when `argv` is a read by the allowlist, otherwise the reason it is not."""
    if not argv:
        return "empty command"
    tool = _tool_name(argv[0])
    shapes = READS.get(tool)
    if shapes is None:
        return "%s is not a provider command" % tool
    if tool == "gcloud":
        # What no skill may ever run is not a read either (`auth print-access-token`,
        # `config set`, `--impersonate-service-account` on a describe, ...).
        why = _gcloud_refused(argv[1:])
        if why:
            return why
    args, reason = _strip_global(tool, argv[1:])
    if reason:
        return reason
    for shape in shapes:
        words = [w for w in shape if isinstance(w, str)]
        guards = [g for g in shape if callable(g)]
        if list(args[:len(words)]) != words:
            continue
        rest = list(args[len(words):])
        why = None
        for g in guards:
            why = g(rest)
            if why:
                break
        if why is None:
            return None
        return why
    return "not on the allowlist of reads"


def is_read(argv):
    return read_refusal(argv) is None


# ---------------------------------------------------------------------------
# Writes: the allowlist
#
# A skill writes only in `mode=apply`, only through the writing runner, and only the
# command shapes listed for that skill in WRITE_SHAPES. Each shape was taken from the
# skill's SKILL.md, made as narrow as the skill allows: the words and flags in the order
# the skill writes them, and a pattern for each value. A skill with no entry may write
# nothing. Before any shape is looked at, ALWAYS_REFUSED (below) refuses what no skill
# may ever run, whatever a shape says.
#
# A shape is a tuple of the whole command after the tool (git's `-c` options
# included). Each item is a literal word, a `_T` (a pattern one argument must match in
# full), or, last, a function `guard(rest, env) -> None | reason` that takes every
# remaining argument. `env` holds `root`, the plugin's folder (for a file of the
# plugin that a command reads, such as a ruleset).


class _T(object):
    """One argument matching the regular expression `pattern` in full."""

    def __init__(self, pattern, name):
        self.re = re.compile(pattern, re.S)
        self.name = name

    def match(self, arg, env):
        return self.re.fullmatch(arg) is not None


class _PluginFile(object):
    """One argument that is exactly `<prefix><plugin root>/files/<one of names>`: the
    path alone (`--input <file>`), or after a flag written with it (`prefix`
    `--message-body-from-file=`). Real paths are compared."""

    def __init__(self, *names, **kw):
        self.names = names
        self.prefix = kw.get("prefix", "")
        self.name = self.prefix + "a file of the plugin: " + ", ".join(names)

    def match(self, arg, env):
        root = (env or {}).get("root")
        if not root or not arg.startswith(self.prefix):
            return False
        path = arg[len(self.prefix):]
        return any(os.path.realpath(path) == os.path.realpath(os.path.join(root, "files", n))
                   for n in self.names)


# The private folder write_temp_file makes for a process (tempfile.mkdtemp's name: the
# prefix, then letters, digits and `_`; never the `-` of `aleogr-backup-`).
PRIVATE_TEMP_PREFIX = "aleogr-"
_PRIVATE_TEMP_RE = re.compile(re.escape(PRIVATE_TEMP_PREFIX) + r"[A-Za-z0-9_]{1,64}")


class _TempFile(object):
    """One argument that is exactly `<prefix><system temporary folder>/aleogr-<x>/<name>`,
    where `aleogr-<x>` is a private folder of write_temp_file (private_temp_dir) and
    `<name>` matches `pattern` in full: a file the skill wrote for this run with
    write_temp_file (TEMP_FILE_WRITES). Real paths of the temporary folder are
    compared; `env["temp"]` stands for it in the unit tests."""

    def __init__(self, pattern, prefix=""):
        self.re = re.compile(pattern)
        self.prefix = prefix
        self.name = "%s<temporary folder>/aleogr-<x>/%s" % (prefix, pattern)

    def match(self, arg, env):
        if not arg.startswith(self.prefix):
            return False
        path = arg[len(self.prefix):]
        folder = (env or {}).get("temp") or system_temp_dir()
        head, base = os.path.split(path)
        top, private = os.path.split(head)
        return (bool(top) and self.re.fullmatch(base) is not None
                and _PRIVATE_TEMP_RE.fullmatch(private) is not None
                and os.path.realpath(top) == os.path.realpath(folder))


class _AnyOf(object):
    """One argument that matches one of `items` (each a `_T`, `_PluginFile`, ...)."""

    def __init__(self, *items):
        self.items = items
        self.name = " or ".join(i.name for i in items)

    def match(self, arg, env):
        return any(i.match(arg, env) for i in self.items)


class _Opt(object):
    """In a shape: these items, in this order, all of them or none."""

    def __init__(self, *items):
        self.items = items


class _Rep(object):
    """In a shape: one item, `minimum` times or more, one after another."""

    def __init__(self, item, minimum=1):
        self.item = item
        self.minimum = minimum


class _Shape(object):
    """A shape whose arguments must also agree with each other: `check(args)` (args:
    the whole command after the tool) returns None, or the reason they do not (the
    account's project is not `--project`, a label names another component, ...)."""

    def __init__(self, *items, **kw):
        self.items = items
        self.check = kw.get("check")

    def __getitem__(self, i):
        return self.items[i]


def _F(flag, pattern, name=None):
    """One argument `<flag>=<value>`, the value matching `pattern` in full (gcloud's
    flags are written with their value in one argument)."""
    return _T(re.escape(flag) + "=(?:" + pattern + ")", "%s=<%s>" % (flag, name or "value"))


_OWNER_RE = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?"
_NAME_RE = r"(?!\.\.?(?:/|$))[A-Za-z0-9._-]{1,100}"
REPO_ARG = _T(_OWNER_RE + "/" + _NAME_RE, "<owner>/<name>")
ORIGIN_URL = _T(r"https://github\.com/" + _OWNER_RE + "/" + _NAME_RE + r"\.git",
                "https://github.com/<owner>/<name>.git")
# A branch read from GitHub (the default branch): no leading `-`, no `..`, none of the
# characters of a refspec (`+`, `:`, `^`, `~`, `*`, a space).
BRANCH_ARG = _T(r"(?!-)(?!HEAD$)(?!.*\.\.)(?!.*//)[A-Za-z0-9._/-]{1,255}(?<![/.])", "<branch>")
CHANGE_BRANCH_ARG = _T(r"aleogr/change-[a-z0-9]{6}", "aleogr/change-<random>")
# The default branch as github_checkout-setup pushes it: never a branch of a proposal.
DEFAULT_BRANCH_ARG = _T(r"(?!aleogr/change-)" + BRANCH_ARG.re.pattern, "<default branch>")
VARIABLE_ARG = _T(r"[A-Z][A-Z0-9_]{0,63}", "<NAME>")
VALUE_ARG = _T(r".+", "<value>")
TEXT_ARG = _T(r"[^\r\n]+", "<text>")
TOPIC_ARG = _T(r"[a-z0-9][a-z0-9-]{0,49}", "<topic>")
LOGIN_ARG = _T(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})", "<login>")
NOREPLY_ARG = _T(r"[0-9]{1,20}\+[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})@users\.noreply\.github\.com",
                 "<id>+<login>@users.noreply.github.com")
RULESET_ID_ARG = _T(r"[0-9]{1,19}", "<id>")
RULESET_FILE_ARG = _PluginFile("ruleset-main.json", "ruleset-main-ci.json")
# A component's folder, as go_setup's rule of `path` gives it.
GO_PATH_RE = r"[a-z0-9_](?:[a-z0-9._-]*[a-z0-9_-])?(?:/[a-z0-9_](?:[a-z0-9._-]*[a-z0-9_-])?)*"
GO_PATH_ARG = _T(GO_PATH_RE, "<path>")
GO_DATABASE_MODULES = ("cloud.google.com/go/cloudsqlconn", "github.com/jackc/pgx/v5")

# git's credential through gh, for one command, as the skills write it.
GIT_CREDENTIAL = ("-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential")

_FILE_PATH_RE = re.compile(r"(?!/)(?!-)[A-Za-z0-9._/-]{1,4096}")


def _file_paths(rest, env):
    """One or more relative file paths (after `--`): no leading `/` or `-`, no `..`
    part, no empty part, only A-Z, a-z, 0-9, `.`, `_`, `-` and `/`."""
    if not rest:
        return "no path"
    for a in rest:
        if not _FILE_PATH_RE.fullmatch(a):
            return "path %s" % a
        parts = a.split("/")
        if any(p in ("", ".", "..") for p in parts):
            return "path %s" % a
    return None


def _one_file_path(rest, env):
    """Exactly one relative file path (after `--`), by the rule of _file_paths."""
    if len(rest) != 1:
        return "exactly one path"
    return _file_paths(rest, env)


def _flag_sequence(single, repeated):
    """A guard for `gh repo edit <repo> <flags>`: `single` is the ordered list of
    (flag, value pattern or None for `--flag=<true|false>`) given at most once each, in
    that order; `repeated` the ordered list of (flag, value pattern) that may come any
    number of times, after them, each kind in its own run. At least one flag."""

    def guard(rest, env):
        if not rest:
            return "no flag"
        i = 0
        for flag, value in single:
            if i >= len(rest):
                break
            a = rest[i]
            if value is None:
                if a in (flag + "=true", flag + "=false"):
                    i += 1
            elif a == flag:
                if i + 1 >= len(rest) or not value.match(rest[i + 1], env):
                    return "flag %s needs %s" % (flag, value.name)
                i += 2
        for flag, value in repeated:
            while i < len(rest) and rest[i] == flag:
                if i + 1 >= len(rest) or not value.match(rest[i + 1], env):
                    return "flag %s needs %s" % (flag, value.name)
                i += 2
        if i != len(rest):
            return "flag %s is not allowed here, or not in this order" % rest[i]
        return None

    return guard


_CONFIGURE_FLAGS = [
    ("--description", TEXT_ARG),
    ("--enable-merge-commit", None),
    ("--enable-squash-merge", None),
    ("--enable-rebase-merge", None),
    ("--delete-branch-on-merge", None),
    ("--enable-issues", None),
    ("--enable-wiki", None),
    ("--enable-projects", None),
]
_TOPIC_FLAGS = [("--add-topic", TOPIC_ARG), ("--remove-topic", TOPIC_ARG)]


def _go_database_modules(rest, env):
    """`<module>@<version> <module>@<version>`: the two modules of the database check,
    each once, in either order, each at a version vX.Y.Z."""
    if len(rest) != 2:
        return "go get takes the two database modules"
    seen = []
    for a in rest:
        m = re.fullmatch(r"([A-Za-z0-9._~/-]+)@v[0-9]+\.[0-9]+\.[0-9]+", a)
        if not m or m.group(1) not in GO_DATABASE_MODULES or m.group(1) in seen:
            return "module %s" % a
        seen.append(m.group(1))
    return None


_GIT_IDENTITY = [
    ("config", "--local", "user.name", LOGIN_ARG),
    ("config", "--local", "user.email", NOREPLY_ARG),
]

WRITE_SHAPES = {
    "github_repo-create": [
        ("repo", "create", REPO_ARG, "--private", "--add-readme"),
        ("repo", "create", REPO_ARG, "--public", "--add-readme"),
        ("repo", "create", REPO_ARG, "--private", "--add-readme", "--description", TEXT_ARG),
        ("repo", "create", REPO_ARG, "--public", "--add-readme", "--description", TEXT_ARG),
        ("repo", "edit", REPO_ARG, _flag_sequence([], [("--add-topic", TOPIC_ARG)])),
    ],
    "github_repo-configure": [
        ("repo", "edit", REPO_ARG, _flag_sequence(_CONFIGURE_FLAGS, _TOPIC_FLAGS)),
        ("repo", "edit", REPO_ARG, "--visibility", _T("public|private", "<public|private>"),
         "--accept-visibility-change-consequences"),
    ],
    "github_branch-protect": [
        ("api", "--method", "POST", _T("repos/" + _OWNER_RE + "/" + _NAME_RE + "/rulesets",
                                       "repos/<owner>/<name>/rulesets"),
         "--input", RULESET_FILE_ARG),
        ("api", "--method", "PUT", _T("repos/" + _OWNER_RE + "/" + _NAME_RE
                                      + "/rulesets/[0-9]{1,19}",
                                      "repos/<owner>/<name>/rulesets/<id>"),
         "--input", RULESET_FILE_ARG),
    ],
    "github_checkout-setup": [
        ("init", "-b", BRANCH_ARG),
        ("remote", "add", "origin", ORIGIN_URL),
    ] + _GIT_IDENTITY + [
        GIT_CREDENTIAL + ("pull", "origin", BRANCH_ARG),
        ("add", "--", _one_file_path),
        ("commit", "-m", TEXT_ARG, "--", _one_file_path),
        # The birth: the only push to the default branch of any skill.
        GIT_CREDENTIAL + ("push", "-u", "origin", DEFAULT_BRANCH_ARG),
        GIT_CREDENTIAL + ("pull", "--ff-only", "origin", BRANCH_ARG),
    ],
    "github_pull-request-open": _GIT_IDENTITY + [
        GIT_CREDENTIAL + ("pull", "--ff-only", "origin", BRANCH_ARG),
        ("switch", "-c", CHANGE_BRANCH_ARG),
        ("add", "--", _file_paths),
        ("commit", "-m", TEXT_ARG, "--", _file_paths),
        # Never the default branch: only the branch this skill makes.
        GIT_CREDENTIAL + ("push", "-u", "origin", CHANGE_BRANCH_ARG),
        ("pr", "create", "--repo", REPO_ARG, "--base", BRANCH_ARG, "--head", CHANGE_BRANCH_ARG,
         "--title", TEXT_ARG, "--body", TEXT_ARG),
        ("switch", BRANCH_ARG),
    ],
    "github_variables-set": [
        ("variable", "set", VARIABLE_ARG, "--repo", REPO_ARG, "--body", VALUE_ARG),
        ("secret", "set", VARIABLE_ARG, "--repo", REPO_ARG, "--body", VALUE_ARG),
    ],
    "go_setup": [
        ("-C", GO_PATH_ARG, "get", _go_database_modules),
        ("-C", GO_PATH_ARG, "mod", "tidy"),
    ],
    # github_ci-setup and project-declare run no writing command: they write one file
    # each (FILE_WRITES).
}

# Which tool each skill's shapes are for: a shape names no tool itself.
WRITE_TOOLS = {
    "github_repo-create": "gh",
    "github_repo-configure": "gh",
    "github_branch-protect": "gh",
    "github_variables-set": "gh",
    "go_setup": "go",
}


# ---------------------------------------------------------------------------
# Writes to Google Cloud (part 2b): the gcloud shapes, one per command each SKILL.md
# prescribes, its flags in the SKILL.md's order (a value the SKILL.md double-quotes is
# one argument without its quotes). A role, a member's form, a condition flag and the
# resource are pinned as the skill writes them; a `_Shape`'s check makes the account,
# the project and the names of one command agree with each other.

_PID = r"[a-z][a-z0-9-]{4,28}[a-z0-9]"
_INSTANCE = r"[a-z][a-z0-9-]{0,59}"
_REGION = r"[a-z]+(?:-[a-z]+)+[0-9]+"
# The region of instance-create (no rule of its own) and of instance-switch-setup
# (lowercase letters, digits and -).
_LOCATION = r"[a-z0-9-]{1,63}"
_PROJECT_NAME = r"[a-z](?:[a-z0-9-]{0,12}[a-z0-9])?"
_COMPONENT = r"[a-z](?:[a-z0-9-]{0,18}[a-z0-9])?"
_SA_ID = r"[a-z][a-z0-9-]{4,28}[a-z0-9]"
_SERVICE = _SA_ID  # <project>-<component>: a service's name and its account's id
_SA = _SA_ID + "@" + _PID + r"\.iam\.gserviceaccount\.com"
_DOMAIN = r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{1,63}"
_EMAIL = r"[A-Za-z0-9._%+-]{1,64}@" + _DOMAIN
# One person: never a service account (its domain in any case of letters).
_PERSON = r"(?!(?i:[^@]*@(?:.*\.)?gserviceaccount\.com$))[A-Za-z0-9._+-]{1,64}@" + _DOMAIN
_ANY_SA = r"[a-z0-9][a-z0-9._-]{0,99}@(?:[a-z0-9-]{1,63}\.)*gserviceaccount\.com"
# The active gcloud account as a member: `user:` for a person, `serviceAccount:` for an
# address that ends with .gserviceaccount.com.
_ACTIVE_MEMBER = "user:" + _PERSON + "|serviceAccount:" + _ANY_SA
_ROLE = (r"roles/[A-Za-z0-9_.]{1,128}|(?:projects/" + _PID
         + r"|organizations/[0-9]{1,25})/roles/[A-Za-z0-9_.]{1,64}")
_GH_REPO = _OWNER_RE + "/" + _NAME_RE
_SWITCH_REPO = r"[A-Za-z0-9._-]{1,100}/[A-Za-z0-9._-]{1,100}"
_ISSUER = "--issuer-uri=https://token.actions.githubusercontent.com"
_BILLING_ACCOUNT = r"[0-9A-Z]{6}-[0-9A-Z]{6}-[0-9A-Z]{6}"


def _principal_set(repo):
    return (r"principalSet://iam\.googleapis\.com/projects/[0-9]{1,20}/locations/global/"
            r"workloadIdentityPools/github/attribute\.repository/" + repo)


PROJECT_FLAG = _F("--project", _PID, "projectId")
REGION_FLAG = _F("--region", _REGION, "region")
INSTANCE_ARG = _T(_INSTANCE, "<instance>")
SERVICE_ARG = _T(_SERVICE, "<service>")
SA_ARG = _T(_SA, "<account>")
STOP_BODY_FILE_ARG = _PluginFile("stop-body.json", prefix="--message-body-from-file=")
CLEANUP_POLICY_FILE_ARG = _AnyOf(
    _PluginFile("cleanup-policy.json", prefix="--policy="),
    _TempFile(r"aleogr-cleanup-policy-keep-(?:[1-9]|[1-4][0-9]|50)\.json", prefix="--policy="))
PLACEHOLDER_IMAGE_RE = (r"us-docker\.pkg\.dev/cloudrun/container/hello"
                        r"(?::[A-Za-z0-9._-]{1,128}|@sha256:[0-9a-f]{64})?")


def _flag_value(args, flag):
    """The value of the first `<flag>=<value>` of args, or None."""
    for a in args:
        if a.startswith(flag + "="):
            return a[len(flag) + 1:]
    return None


def _account_project(email):
    """The project of a service account's address (`serviceAccount:` prefix allowed):
    `<id>@<project>.iam.gserviceaccount.com`, or None."""
    if email is None:
        return None
    if email.startswith("serviceAccount:"):
        email = email[len("serviceAccount:"):]
    m = re.fullmatch(r"[^@]+@([a-z0-9-]+)\.iam\.gserviceaccount\.com", email)
    return m.group(1) if m else None


def _agree(what, *getters):
    """A check: every getter gives the same value, and none gives None."""
    def check(args):
        values = [g(args) for g in getters]
        if None in values or len(set(values)) != 1:
            return "%s do not agree" % what
        return None
    return check


def _all(*checks):
    def check(args):
        for c in checks:
            why = c(args)
            if why:
                return why
        return None
    return check


def _arg(i):
    return lambda args: args[i] if i < len(args) else None


def _flag(name):
    return lambda args: _flag_value(args, name)


def _project_of(getter):
    return lambda args: _account_project(getter(args))


def _after(prefix_re, getter):
    """The first group of `prefix_re` matched in full on getter's value, or None."""
    def get(args):
        v = getter(args)
        m = re.fullmatch(prefix_re, v) if v is not None else None
        return m.group(1) if m else None
    return get


_SAME_PROJECT = "the account, the project and --project"
_LABELS3 = ("aleogr-project=(" + _PROJECT_NAME + "),aleogr-environment=(?:dev|hom|prd),"
            "aleogr-component=(" + _COMPONENT + ")")


def _labels_name(flag):
    """`<project>-<component>` from the three labels of gcp_deploy-setup."""
    def get(args):
        v = _flag_value(args, flag)
        m = re.fullmatch(_LABELS3, v) if v is not None else None
        return "%s-%s" % (m.group(1), m.group(2)) if m else None
    return get


def _service_name(args):
    """The service of `run deploy <service> ...` or `run services <verb> <service> ...`."""
    i = 2 if args[1:2] == ["deploy"] else 3
    return args[i] if len(args) > i else None


def _service_account_of_service(args):
    """`<service>@<projectId>.iam.gserviceaccount.com`, the service's own account."""
    p, s = _flag_value(args, "--project"), _service_name(args)
    return "%s@%s.iam.gserviceaccount.com" % (s, p) if p and s else None


def _deploy_update_check(args):
    """The repair of gcp_deploy-setup (6d1): at least one of its flags; --scaling=auto
    and --min-instances=default only with --min=0; the account is the service's own;
    the labels name this service."""
    flags = args[4:-3]  # after `run services update <service>`, before the three last
    if not flags:
        return "no flag to change"
    if ("--scaling=auto" in flags or "--min-instances=default" in flags) \
            and "--min=0" not in flags:
        return "--scaling=auto and --min-instances=default come with --min=0"
    account = _flag_value(flags, "--service-account")
    if account is not None and account != _service_account_of_service(args):
        return "the account is not the service's own"
    if _flag_value(flags, "--update-labels") is not None \
            and _labels_name("--update-labels")(flags) != _service_name(args):
        return "the labels name another service"
    return None


_DEPLOY_SIZE = [_F("--cpu", "1|2", "cpu"), _F("--memory", "512Mi|1Gi|2Gi", "memory")]
_DEPLOY_ENV = r"[A-Z][A-Z0-9_]{0,63}=[a-zA-Z0-9._:@-]{1,200}"
_CI_PROJECT = r"[a-z][a-z0-9-]{1,12}[a-z0-9]"
_CI_BRANCH = r"(?!/)(?!.*\.\.)[A-Za-z0-9._/-]{1,255}(?<!/)"
_CI_CONDITION = (
    r"assertion\.repository=='" + _GH_REPO + r"' && assertion\.repository_id=='[1-9][0-9]{0,19}'"
    r" && assertion\.repository_owner_id=='[1-9][0-9]{0,19}' && assertion\.ref=='refs/heads/"
    + _CI_BRANCH + r"' && assertion\.job_workflow_ref\.startsWith\('" + _GH_REPO
    + r"/\.github/workflows/[a-z0-9_-]{1,60}\.yml@'\)")
_CI_MAPPING = ("--attribute-mapping=google.subject=assertion.sub,"
               "attribute.repository=assertion.repository,attribute.ref=assertion.ref,"
               "attribute.repository_id=assertion.repository_id,"
               "attribute.repository_owner_id=assertion.repository_owner_id,"
               "attribute.job_workflow_ref=assertion.job_workflow_ref")
_POOL_CREATE = ("iam", "workload-identity-pools", "create", "github", PROJECT_FLAG,
                "--location=global", "--display-name=GitHub", "--quiet")
_SWITCH_SA = r"aleogr-shared-sql-switch@" + _PID + r"\.iam\.gserviceaccount\.com"
_SWITCH_JOB = _T("aleogr-shared-stop-weeknight|aleogr-shared-stop-weekend", "<job>")
_SWITCH_HEADERS = "Content-Type=application/json,X-HTTP-Method-Override=PATCH"
_SWITCH_URI = r"https://sqladmin\.googleapis\.com/v1/projects/(" + _PID + ")/instances/" \
              + _INSTANCE
_SWITCH_JOB_CHECK = _agree("the job's instance, its account and --project",
                           _after(_SWITCH_URI, _flag("--uri")),
                           _project_of(_flag("--oauth-service-account-email")),
                           _flag("--project"))
_CRON = r"[0-9*,/-]{1,40}(?: [0-9*,/-]{1,40}){4}"
_STOP_PATCH = ("sql", "instances", "patch", INSTANCE_ARG, PROJECT_FLAG,
               "--activation-policy=NEVER", "--quiet")
_BUDGET_AMOUNT = r"(?=[0-9.]*[1-9])[0-9]{1,15}(?:\.[0-9]{1,9})?[A-Z]{3}"
_THRESHOLD = r"percent=(?:0\.[0-9]{0,8}[1-9][0-9]{0,8}|1(?:\.0{1,9})?)"

WRITE_SHAPES.update({
    # aleogr-db-gcp-cloud-sql
    "gcp-cloud-sql_instance-stop": [
        _STOP_PATCH,
    ],
    "gcp-cloud-sql_instance-start": [
        ("sql", "instances", "patch", INSTANCE_ARG, PROJECT_FLAG, "--activation-policy=ALWAYS",
         "--async", "--quiet"),
    ],
    "gcp-cloud-sql_instance-create": [
        ("sql", "instances", "create", INSTANCE_ARG, PROJECT_FLAG,
         _F("--database-version", r"POSTGRES_[0-9]{1,3}", "version"),
         _F("--edition", "enterprise|enterprise-plus", "edition"),
         _F("--tier", r"db-[a-z0-9-]{1,60}", "tier"),
         _F("--region", _LOCATION, "region"),
         "--availability-type=zonal", "--storage-type=SSD",
         _F("--storage-size", r"[1-9][0-9]|100", "storageGb"),
         "--no-storage-auto-increase", "--assign-ip", "--backup",
         _F("--backup-start-time", r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", "backupStartUtc"),
         _F("--retained-backups-count", r"[1-9]|[12][0-9]|30", "retainedBackups"),
         "--no-enable-point-in-time-recovery", "--database-flags=cloudsql.iam_authentication=on",
         "--no-enable-dataplex-integration", "--deletion-protection", "--async", "--quiet"),
        # Step 6: the new instance is stopped by this skill's own patch, or by its night
        # job. The only NEVER outside instance-stop: the SKILL.md prescribes it here.
        _STOP_PATCH,
        ("scheduler", "jobs", "run", _T(r"[a-z0-9-]{1,500}", "<stopJob>"), PROJECT_FLAG,
         _F("--location", _LOCATION, "region"), "--quiet"),
    ],
    "gcp-cloud-sql_instance-switch-setup": [
        ("iam", "roles", "create", "aleogrSharedSqlSwitch", PROJECT_FLAG,
         "--title=aleogr shared SQL switch",
         "--permissions=cloudsql.instances.get,cloudsql.instances.update", "--stage=GA",
         "--quiet"),
        ("iam", "service-accounts", "create", "aleogr-shared-sql-switch", PROJECT_FLAG,
         "--display-name=aleogr shared SQL switch", "--quiet"),
        _Shape("projects", "add-iam-policy-binding", _T(_PID, "<projectId>"),
               _F("--member", "serviceAccount:" + _SWITCH_SA),
               _F("--role", "projects/" + _PID + "/roles/aleogrSharedSqlSwitch"),
               "--condition=None", "--quiet",
               check=_agree(_SAME_PROJECT, _arg(2), _project_of(_flag("--member")),
                            _after("projects/(.*)/roles/aleogrSharedSqlSwitch",
                                   _flag("--role")))),
        _Shape("iam", "service-accounts", "add-iam-policy-binding", _T(_SWITCH_SA, "<account>"),
               PROJECT_FLAG, _F("--member", "user:" + _EMAIL),
               "--role=roles/iam.serviceAccountUser", "--quiet",
               check=_agree(_SAME_PROJECT, _project_of(_arg(3)), _flag("--project"))),
        _POOL_CREATE,
        ("iam", "workload-identity-pools", "providers", "create-oidc", "aleogr", PROJECT_FLAG,
         "--location=global", "--workload-identity-pool=github", _ISSUER,
         "--attribute-mapping=google.subject=assertion.sub,"
         "attribute.repository=assertion.repository,attribute.ref=assertion.ref",
         _F("--attribute-condition", r"assertion\.repository=='" + _SWITCH_REPO
            + r"' && assertion\.ref=='refs/heads/main'", "condition"),
         "--quiet"),
        _Shape("iam", "service-accounts", "add-iam-policy-binding", _T(_SWITCH_SA, "<account>"),
               PROJECT_FLAG, _F("--member", _principal_set(_SWITCH_REPO)),
               "--role=roles/iam.workloadIdentityUser", "--quiet",
               check=_agree(_SAME_PROJECT, _project_of(_arg(3)), _flag("--project"))),
        _Shape("scheduler", "jobs", "create", "http", _SWITCH_JOB, PROJECT_FLAG,
               _F("--location", _LOCATION, "region"), _F("--schedule", _CRON, "cron"),
               _F("--time-zone", r"[A-Za-z_]{1,64}/[A-Za-z_]{1,64}", "timeZone"),
               _F("--uri", _SWITCH_URI, "uri"), "--http-method=POST",
               "--headers=" + _SWITCH_HEADERS, STOP_BODY_FILE_ARG,
               _F("--oauth-service-account-email", _SWITCH_SA, "account"),
               "--oauth-token-scope=https://www.googleapis.com/auth/cloud-platform",
               "--max-retry-attempts=5", "--min-backoff=5m", "--max-backoff=15m",
               "--max-doublings=2", "--attempt-deadline=60s", "--quiet",
               check=_SWITCH_JOB_CHECK),
        _Shape("scheduler", "jobs", "update", "http", _SWITCH_JOB, PROJECT_FLAG,
               _F("--location", _LOCATION, "region"), _F("--schedule", _CRON, "cron"),
               _F("--time-zone", r"[A-Za-z_]{1,64}/[A-Za-z_]{1,64}", "timeZone"),
               _F("--uri", _SWITCH_URI, "uri"), "--http-method=POST",
               "--update-headers=" + _SWITCH_HEADERS, STOP_BODY_FILE_ARG,
               _F("--oauth-service-account-email", _SWITCH_SA, "account"),
               "--oauth-token-scope=https://www.googleapis.com/auth/cloud-platform", "--quiet",
               check=_SWITCH_JOB_CHECK),
        ("scheduler", "jobs", "resume", _SWITCH_JOB, PROJECT_FLAG,
         _F("--location", _LOCATION, "region"), "--quiet"),
    ],
    "gcp-cloud-sql_database-create": [
        ("sql", "databases", "create", _T(r"[a-z][a-z0-9_]{0,13}_(?:dev|hom|prd)", "<database>"),
         _F("--instance", _INSTANCE, "instance"), PROJECT_FLAG, "--quiet"),
    ],
    "gcp-cloud-sql_access-grant": [
        ("sql", "users", "create", _T(_SA_ID + "@" + _PID + r"\.iam", "<user>"),
         _F("--instance", _INSTANCE, "instance"), PROJECT_FLAG,
         "--type=cloud_iam_service_account", "--quiet"),
        ("projects", "add-iam-policy-binding", _T(_PID, "<sharedProjectId>"),
         _F("--member", "serviceAccount:" + _SA),
         _F("--role", r"roles/cloudsql\.client|roles/cloudsql\.instanceUser", "role"),
         "--condition=None", "--quiet"),
    ],

    # aleogr-registry-gcp-artifact-registry
    "gcp-artifact-registry_repository-create": [
        _Shape("artifacts", "repositories", "create", _T(_PROJECT_NAME, "<project>"),
               PROJECT_FLAG, _F("--location", _REGION, "region"), "--repository-format=docker",
               _F("--labels", "aleogr-project=" + _PROJECT_NAME
                  + ",aleogr-environment=(?:dev|hom|prd)", "labels"),
               check=_agree("the repository and its label", _arg(3),
                            _after("aleogr-project=([^,]*),.*", _flag("--labels")))),
    ],
    "gcp-artifact-registry_cleanup-configure": [
        ("artifacts", "repositories", "set-cleanup-policies", _T(_PROJECT_NAME, "<project>"),
         _F("--location", _REGION, "region"), PROJECT_FLAG, CLEANUP_POLICY_FILE_ARG,
         "--no-dry-run"),
    ],
    "gcp-artifact-registry_access-grant": [
        _Shape("artifacts", "repositories", "add-iam-policy-binding",
               _T(_PROJECT_NAME, "<project>"), _F("--location", _REGION, "region"),
               PROJECT_FLAG, _F("--member", "serviceAccount:" + _SA),
               "--role=roles/artifactregistry.writer", "--condition=None", "--quiet",
               check=_agree(_SAME_PROJECT, _project_of(_flag("--member")),
                            _flag("--project"))),
    ],

    # aleogr-cloud-gcp
    "gcp_environment-create": [
        ("projects", "create", _T(r"aleogr-shared-[a-z0-9]{4}", "aleogr-shared-<random>"),
         _F("--organization", r"[0-9]{1,25}", "id"), "--name=shared",
         "--labels=aleogr-project=shared,aleogr-platform=shared"),
        _Shape("projects", "create",
               _T(r"aleogr-(?:dev|hom|prd)-" + _PROJECT_NAME + r"-[a-z0-9]{4}",
                  "aleogr-<environment>-<project>-<random>"),
               _F("--folder", r"[0-9]{1,25}", "id"),
               _F("--name", r"(?:dev|hom|prd) " + _PROJECT_NAME, "environment project"),
               _F("--labels", "aleogr-project=" + _PROJECT_NAME
                  + ",aleogr-environment=(?:dev|hom|prd)", "labels"),
               check=_all(
                   _agree("the environment of the project id, its name and its labels",
                          _after(r"aleogr-([a-z]+)-.*-[a-z0-9]{4}", _arg(2)),
                          _after(r"([a-z]+) .*", _flag("--name")),
                          _after(r"aleogr-project=.*,aleogr-environment=(.*)",
                                 _flag("--labels"))),
                   _agree("the project of the project id, its name and its labels",
                          _after(r"aleogr-[a-z]+-(.*)-[a-z0-9]{4}", _arg(2)),
                          _after(r"[a-z]+ (.*)", _flag("--name")),
                          _after(r"aleogr-project=(.*),aleogr-environment=.*",
                                 _flag("--labels"))))),
        ("billing", "projects", "link", _T(_PID, "<projectId>"),
         _F("--billing-account", _BILLING_ACCOUNT, "id")),
    ],
    "gcp_services-enable": [
        ("services", "enable",
         _Rep(_T(r"[a-z0-9-][a-z0-9.-]{0,100}\.googleapis\.com", "<service>")), PROJECT_FLAG),
    ],
    "gcp_budget-alert-setup": [
        ("billing", "budgets", "create", _F("--billing-account", _BILLING_ACCOUNT, "id"),
         _F("--display-name", r"[A-Za-z0-9][A-Za-z0-9._-]{0,59}", "displayName"),
         _F("--budget-amount", _BUDGET_AMOUNT, "amount><currency"),
         _Rep(_F("--threshold-rule", _THRESHOLD, "percent=<t>")),
         _F("--billing-project", _PID, "quotaProject")),
        ("billing", "budgets", "update", _T(r"[A-Za-z0-9-]{1,64}", "<budgetId>"),
         _F("--billing-account", _BILLING_ACCOUNT, "id"),
         _F("--budget-amount", _BUDGET_AMOUNT, "amount><currency"), "--clear-threshold-rules",
         _Rep(_F("--add-threshold-rule", _THRESHOLD, "percent=<t>")),
         _F("--billing-project", _PID, "quotaProject")),
    ],
    "gcp_login-setup": [
        ("organizations", "add-iam-policy-binding", _T(r"[0-9]{1,25}", "<organizationId>"),
         _F("--member", _ACTIVE_MEMBER, "member"), "--role=roles/iap.settingsAdmin",
         "--condition=None", "--quiet"),
        ("services", "enable", "iap.googleapis.com", PROJECT_FLAG),
    ],
    "gcp_deploy-setup": [
        # 5.1 and 5.2, the security pass: only allUsers or allAuthenticatedUsers is ever
        # removed (always_refused refuses any other member of a remove).
        ("iap", "web", "remove-iam-policy-binding", "--resource-type=cloud-run",
         _F("--service", _SERVICE, "service"), REGION_FLAG, PROJECT_FLAG,
         _F("--member", "allUsers|allAuthenticatedUsers"), _F("--role", _ROLE, "role"), "--all",
         "--quiet"),
        ("run", "services", "remove-iam-policy-binding", SERVICE_ARG,
         _F("--member", "allUsers|allAuthenticatedUsers"), _F("--role", _ROLE, "role"),
         REGION_FLAG, PROJECT_FLAG, "--all", "--quiet"),
        # 5.3 and 5.4: each flag alone.
        ("run", "services", "update", SERVICE_ARG, "--iap", REGION_FLAG, PROJECT_FLAG, "--quiet"),
        ("run", "services", "update", SERVICE_ARG, "--invoker-iam-check", REGION_FLAG,
         PROJECT_FLAG, "--quiet"),
        # 6a: the service's account.
        _Shape("iam", "service-accounts", "create", SERVICE_ARG, PROJECT_FLAG,
               _F("--display-name", _PROJECT_NAME + " " + _COMPONENT, "project> <name"),
               "--quiet",
               check=_agree("the account and its display name", _arg(3),
                            lambda a: (_flag_value(a, "--display-name") or "").replace(" ", "-")
                            or None)),
        # 6b: the CI account may act as the service's account.
        _Shape("iam", "service-accounts", "add-iam-policy-binding", SA_ARG,
               _F("--member", "serviceAccount:" + _SA), "--role=roles/iam.serviceAccountUser",
               PROJECT_FLAG, "--condition=None", "--quiet",
               check=_agree(_SAME_PROJECT, _project_of(_arg(3)),
                            _project_of(_flag("--member")), _flag("--project"))),
        # 6c: the service, created behind the login, never public, never --min above 0.
        _Shape("run", "deploy", SERVICE_ARG, _F("--image", PLACEHOLDER_IMAGE_RE, "image"),
               "--no-allow-unauthenticated", "--iap", _F("--service-account", _SA, "account"),
               "--min=0", _F("--max", r"[1-9]|10", "maxInstances"), _DEPLOY_SIZE[0],
               _DEPLOY_SIZE[1], "--cpu-throttling", _F("--labels", _LABELS3, "labels"),
               REGION_FLAG, PROJECT_FLAG, "--quiet",
               check=_all(_agree("the service and its account", _flag("--service-account"),
                                 _service_account_of_service),
                          _agree("the service and its labels", _service_name,
                                 _labels_name("--labels")))),
        # 6d1: the repair, only the flags of what differs, never --image, a setting or a
        # security flag.
        _Shape("run", "services", "update", SERVICE_ARG,
               _Opt(_F("--service-account", _SA, "account")),
               _Opt("--min=0", _F("--max", r"[1-9]|10", "maxInstances")),
               _Opt("--scaling=auto"), _Opt("--min-instances=default"),
               _Opt(_DEPLOY_SIZE[0]), _Opt(_DEPLOY_SIZE[1]), _Opt("--cpu-throttling"),
               _Opt(_F("--update-labels", _LABELS3, "labels")),
               REGION_FLAG, PROJECT_FLAG, "--quiet", check=_deploy_update_check),
        # 6d2: the login's agent may call the service.
        ("run", "services", "add-iam-policy-binding", SERVICE_ARG,
         _F("--member", r"serviceAccount:service-[0-9]{1,20}@gcp-sa-iap\.iam\.gserviceaccount\.com",
            "agent"),
         "--role=roles/run.invoker", REGION_FLAG, PROJECT_FLAG, "--condition=None", "--quiet"),
        # 6e: the CI account may deploy this service.
        _Shape("run", "services", "add-iam-policy-binding", SERVICE_ARG,
               _F("--member", "serviceAccount:" + _SA), "--role=roles/run.developer",
               REGION_FLAG, PROJECT_FLAG, "--condition=None", "--quiet",
               check=_agree(_SAME_PROJECT, _project_of(_flag("--member")),
                            _flag("--project"))),
        # 6f: the active account gets in through the login.
        ("iap", "web", "add-iam-policy-binding", "--resource-type=cloud-run",
         _F("--service", _SERVICE, "service"), REGION_FLAG, PROJECT_FLAG,
         _F("--member", _ACTIVE_MEMBER, "me"), "--role=roles/iap.httpsResourceAccessor",
         "--condition=None", "--quiet"),
        # 6g: the settings, alone, only ever added or changed.
        ("run", "services", "update", SERVICE_ARG,
         _F("--update-env-vars", r"\^##\^" + _DEPLOY_ENV + r"(?:##" + _DEPLOY_ENV + r")*",
            "^##^NAME=value"),
         REGION_FLAG, PROJECT_FLAG, "--quiet"),
    ],
    "gcp_access-grant": [
        ("iap", "web", "add-iam-policy-binding", "--resource-type=cloud-run",
         _F("--service", _SERVICE, "service"), REGION_FLAG, PROJECT_FLAG,
         _F("--member", "user:" + _PERSON, "person"), "--role=roles/iap.httpsResourceAccessor",
         "--condition=None", "--quiet"),
    ],
    "gcp_ci-identity-setup": [
        _Shape("iam", "service-accounts", "create", _T(_CI_PROJECT + "-ci", "<project>-ci"),
               PROJECT_FLAG, _F("--display-name", _CI_PROJECT + " CI", "project> CI"), "--quiet",
               check=_agree("the account and its display name",
                            _after("(.*)-ci", _arg(3)),
                            _after("(.*) CI", _flag("--display-name")))),
        _POOL_CREATE,
        ("iam", "workload-identity-pools", "providers", "create-oidc", "github", PROJECT_FLAG,
         "--location=global", "--workload-identity-pool=github", _ISSUER, _CI_MAPPING,
         _F("--attribute-condition", _CI_CONDITION, "condition"), "--quiet"),
        ("iam", "workload-identity-pools", "providers", "update-oidc", "github", PROJECT_FLAG,
         "--location=global", "--workload-identity-pool=github", _ISSUER, _CI_MAPPING,
         _F("--attribute-condition", _CI_CONDITION, "condition"), "--quiet"),
        _Shape("iam", "service-accounts", "add-iam-policy-binding",
               _T(_CI_PROJECT + "-ci@" + _PID + r"\.iam\.gserviceaccount\.com", "<account>"),
               PROJECT_FLAG, _F("--member", _principal_set(_GH_REPO), "member"),
               "--role=roles/iam.workloadIdentityUser", "--quiet",
               check=_agree(_SAME_PROJECT, _project_of(_arg(3)), _flag("--project"))),
    ],
})

for _skill in list(WRITE_SHAPES):
    if _skill.startswith("gcp"):
        WRITE_TOOLS[_skill] = "gcloud"
del _skill
# Skills whose shapes mix tools: the shape's first word decides (pr is gh, every other
# word is git).
_MIXED_GH_WORDS = ("pr", "api", "repo", "secret", "variable")


def _shape_tool(skill, shape):
    tool = WRITE_TOOLS.get(skill)
    if tool:
        return tool
    first = shape[0] if isinstance(shape[0], str) else None
    return "gh" if first in _MIXED_GH_WORDS else "git"


# The files of the current folder each skill may write (relative paths, matched in
# full), through ctx.write_file and the copies of ctx.backup.
FILE_WRITES = {
    "github_ci-setup": [r"\.github/workflows/ci\.yml"],
    "project-declare": [r"\.aleogr/project\.json"],
    "go_setup": [GO_PATH_RE + r"/(?:go\.mod|go\.sum|main\.go|main_test\.go|db\.go|db_test\.go"
                 r"|Dockerfile)"],
}


def _git_subcommand(args):
    """git's subcommand and its arguments, past `-C <dir>`, `-c <x>` and `--no-pager`."""
    args = list(args)
    while args and args[0].startswith("-"):
        if args[0] in ("-C", "-c") and len(args) > 1:
            args = args[2:]
        elif args[0] == "--no-pager":
            args = args[1:]
        else:
            break
    return args


def _gh_api_method(rest):
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in ("-X", "--method") and i + 1 < len(rest):
            return rest[i + 1].upper()
        if a.startswith("--method="):
            return a.split("=", 1)[1].upper()
        if a.startswith("-X") and len(a) > 2:
            return a[2:].upper()
        if a.startswith("-") and not a.startswith("--") and "X" in a[1:]:
            return "a method in short flags written together"
        i += 1
    return None


def always_refused(argv):
    """The reason when `argv` is a command no skill may ever run, whatever an entry of
    WRITE_SHAPES says; None otherwise."""
    argv = _plain(argv)
    if not argv:
        return "empty command"
    tool = _tool_name(argv[0])
    rest = argv[1:]
    if tool == "gh":
        words = [a for a in rest[:3] if not a.startswith("-")]
        if "delete" in words:
            return "gh ... delete"
        if rest[:2] == ["pr", "merge"]:
            return "gh pr merge"
        if rest[:1] == ["auth"] and rest != ["auth", "status"]:
            return "gh auth other than status"
        if rest[:1] == ["api"]:
            method = _gh_api_method(rest[1:])
            if method and "DELETE" in method:
                return "gh api DELETE"
            if method and method.startswith("a method"):
                return method
    elif tool == "git":
        sub = _git_subcommand(rest)
        verb, args = (sub[0], sub[1:]) if sub else ("", [])
        if verb == "push":
            for a in args:
                if a in ("-f", "--force", "--force-if-includes", "-d", "--delete", "--mirror",
                         "--prune", "--all", "--tags") or a.startswith("--force"):
                    return "git push %s" % a
                if a.startswith("-") and not a.startswith("--") and any(
                        c in a[1:] for c in "fd"):
                    return "git push %s" % a
                if not a.startswith("-") and (a.startswith("+") or ":" in a):
                    return "git push with the refspec %s" % a
        if verb == "reset" and any(a == "--hard" for a in args):
            return "git reset --hard"
        if verb == "clean":
            return "git clean"
        if verb == "branch" and any(a in ("-d", "-D", "--delete") for a in args):
            return "git branch delete"
    elif tool == "gcloud":
        return _gcloud_refused(rest)
    return None


# gcloud's global flags that change who runs a command, with which configuration or
# credential, or what it logs or prints: refused anywhere in the arguments of any gcloud
# command, read or write, as `--flag=value` and as `--flag value` (and a boolean one as
# `--no-<flag>` too).
GCLOUD_REFUSED_FLAGS = (
    "--account", "--configuration", "--access-token-file", "--flags-file", "--log-http",
    "--trace-token", "--verbosity", "--credential-file-override",
    "--impersonate-service-account", "--user-output-enabled",
)
# `--billing-project` (the project billed for the quota of a call) only on the commands
# whose prescribed shape writes it, and only as `--billing-project=<id>`:
# `billing budgets list|describe|create|update` (gcp_budget-alert-setup) and `iap
# settings get` (gcp_login-describe, gcp_login-setup).
GCLOUD_BILLING_PROJECT_COMMANDS = (
    ("billing", "budgets", "list"), ("billing", "budgets", "describe"),
    ("billing", "budgets", "create"), ("billing", "budgets", "update"),
    ("iap", "settings", "get"),
)

_GCLOUD_PRIMITIVE_ROLES = ("roles/owner", "roles/editor", "roles/viewer", "owner", "editor",
                           "viewer")
_GCLOUD_PUBLIC_MEMBERS = ("allusers", "allauthenticatedusers")


def _gcloud_flag_values(rest, flag):
    """The values of `flag` in `rest`, written `--flag=value` or `--flag value`."""
    values = []
    for i, a in enumerate(rest):
        if a.startswith(flag + "="):
            values.append(a[len(flag) + 1:])
        elif a == flag:
            values.append(rest[i + 1] if i + 1 < len(rest) else "")
    return values


def _gcloud_refused(rest):
    """The reason when `gcloud <rest>` is a command no skill may ever run, read or write,
    whatever an entry of WRITE_SHAPES or READS says; None otherwise.

    - a flag before the command (`gcloud --project=x config set ...`), but `--version`;
    - `delete`, `set-iam-policy` or `set-password` (`sql users set-password`) among the
      first five words;
    - `remove-iam-policy-binding`, except with exactly one `--member`, `allUsers` or
      `allAuthenticatedUsers` (the security pass of gcp_deploy-setup, which only closes
      a service that is open to everyone);
    - `allUsers` or `allAuthenticatedUsers` as a member of anything else;
    - a primitive role (`roles/owner`, `roles/editor`, `roles/viewer`) in an
      `add-iam-policy-binding`;
    - `--allow-unauthenticated`, any flag with `password` in its name;
    - anywhere in the arguments, a global flag of GCLOUD_REFUSED_FLAGS (`--account`,
      `--configuration`, `--impersonate-service-account`, `--verbosity`, ...), and
      `--billing-project` except as `--billing-project=<id>` on a command of
      GCLOUD_BILLING_PROJECT_COMMANDS;
    - `gcloud auth` other than `auth list`, `gcloud config` other than `config
      get-value`, `gcloud iam service-accounts keys` (anything)."""
    if not rest:
        return None
    if rest[0].startswith("-") and rest != ["--version"]:
        return "gcloud with a flag before its command"
    words = [a for a in rest if not a.startswith("-")]
    lead = words[:5]
    if "delete" in lead:
        return "gcloud ... delete"
    if "set-iam-policy" in lead:
        return "gcloud ... set-iam-policy"
    if "set-password" in lead:
        return "gcloud ... set-password"
    for a in rest:
        if not a.startswith("-"):
            continue
        name = a.split("=", 1)[0].lower()
        if name == "--allow-unauthenticated":
            return "gcloud --allow-unauthenticated"
        if "password" in name:
            return "gcloud %s" % name
        if name in GCLOUD_REFUSED_FLAGS or (
                name.startswith("--no-") and "--" + name[5:] in GCLOUD_REFUSED_FLAGS):
            return "gcloud %s" % name
        if name == "--billing-project":
            if "=" not in a or tuple(words[:3]) not in GCLOUD_BILLING_PROJECT_COMMANDS:
                return "gcloud --billing-project here"
    if words[:1] == ["auth"] and words != ["auth", "list"]:
        return "gcloud auth other than list"
    if words[:1] == ["config"] and words[:2] != ["config", "get-value"]:
        return "gcloud config other than get-value"
    if words[:3] == ["iam", "service-accounts", "keys"]:
        return "gcloud iam service-accounts keys"
    members = _gcloud_flag_values(rest, "--member")
    public = [m for m in members if m.lower() in _GCLOUD_PUBLIC_MEMBERS]
    if "remove-iam-policy-binding" in lead:
        if len(members) != 1 or len(public) != 1:
            return "gcloud remove-iam-policy-binding of a member other than allUsers or " \
                   "allAuthenticatedUsers"
    elif public:
        return "gcloud with the member %s" % public[0]
    if "add-iam-policy-binding" in lead:
        for role in _gcloud_flag_values(rest, "--role"):
            if role.lower() in _GCLOUD_PRIMITIVE_ROLES:
                return "gcloud add-iam-policy-binding of the primitive role %s" % role
    return None


def _item_refusal(item, a, env):
    """None when the one argument `a` matches the one item (a word or a matcher)."""
    if isinstance(item, str):
        return None if a == item else "%s where the shape has %s" % (a, item)
    return None if item.match(a, env) else "%s is not %s" % (a, item.name)


def _take(items, args, i, env):
    """The index after `items` matched one argument each from `i`, or None."""
    for item in items:
        if i >= len(args) or _item_refusal(item, args[i], env):
            return None
        i += 1
    return i


def _match_shape(shape, args, env):
    """None when `args` (the command after the tool) matches `shape`, else a reason.

    Items are matched in order, each against one argument, except: an `_Opt` takes its
    items when they all match there (else none); a `_Rep` takes its item as many times
    as it matches, at least `minimum`; a guard function, last, takes every remaining
    argument. Matching is greedy and never goes back: the shapes are written so that
    the next item never matches what an `_Opt` or a `_Rep` could take. A `_Shape`'s
    check runs when every item matched."""
    items = shape.items if isinstance(shape, _Shape) else shape
    i = 0
    for item in items:
        if isinstance(item, _Opt):
            j = _take(item.items, args, i, env)
            if j is not None:
                i = j
            continue
        if isinstance(item, _Rep):
            n = 0
            while True:
                j = _take((item.item,), args, i, env)
                if j is None:
                    break
                i, n = j, n + 1
            if n < item.minimum:
                return "%s is needed %d times at least" % (
                    getattr(item.item, "name", item.item), item.minimum)
            continue
        if callable(item) and not hasattr(item, "match"):
            why = item(list(args[i:]), env)
            if why:
                return why
            i = len(args)
            break
        if i >= len(args):
            return "too short"
        why = _item_refusal(item, args[i], env)
        if why:
            return why
        i += 1
    if i != len(args):
        return "too long"
    check = getattr(shape, "check", None)
    if check is not None:
        return check(list(args))
    return None


def write_refusal(skill, argv, root=None, temp=None):
    """None when `argv` is a write that `skill` may run, otherwise the reason it is not.
    `root` is the plugin's folder (for the shapes that name a file of the plugin);
    `temp` the temporary folder of write_temp_file (system_temp_dir() when None)."""
    argv = _plain(argv)
    why = always_refused(argv)
    if why:
        return why
    shapes = WRITE_SHAPES.get(skill)
    if not shapes:
        return "%s has no allowed write" % skill
    tool = _tool_name(argv[0])
    env = {"root": root, "temp": temp}
    for shape in shapes:
        if _shape_tool(skill, shape) != tool:
            continue
        if _match_shape(shape, argv[1:], env) is None:
            return None
    return "not on the allowlist of writes of %s" % skill


def is_write_allowed(skill, argv, root=None, temp=None):
    return write_refusal(skill, argv, root, temp) is None


def file_refusal(skill, path):
    """None when `skill` may write the file `path` of the current folder (by its name
    only: ctx.write_file also checks where it leads), otherwise the reason."""
    if not isinstance(path, str) or not path:
        return "no path"
    if "\0" in path or "\\" in path:
        return "a path with a NUL or a backslash"
    if os.path.isabs(path) or path.startswith("/"):
        return "an absolute path"
    parts = path.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return "a path that leaves the folder or has an empty, . or .. part"
    patterns = FILE_WRITES.get(skill) or ()
    if not any(re.fullmatch(p, path) for p in patterns):
        return "%s may not write %s" % (skill, path)
    return None


def _inside(folder, path):
    """None when `path` (relative to `folder`) leads, through every link on its way,
    to a place inside `folder`; otherwise the reason."""
    base = os.path.realpath(folder)
    plain = os.path.normpath(os.path.join(base, path))
    target = os.path.realpath(plain)
    if target != base and not target.startswith(base.rstrip(os.sep) + os.sep):
        return "the path leads outside the folder through a link"
    # A link that stays inside the folder is refused too: through it a skill would
    # write a path it does not name (a file under .git, another skill's file).
    if target != plain or os.path.islink(plain):
        return "the path passes through a link"
    return None


# ---------------------------------------------------------------------------
# Running provider commands


class Completed(tuple):
    """(code, out, err) of a command: unpack it, or use .code, .out and .err."""

    def __new__(cls, code, out, err):
        return tuple.__new__(cls, (code, out, err))

    @property
    def code(self):
        return self[0]

    @property
    def out(self):
        return self[1]

    @property
    def err(self):
        return self[2]

    @property
    def ok(self):
        return self[0] == 0

    @property
    def text(self):
        """stdout and stderr together, for matching an error's words."""
        return (self[1] or "") + "\n" + (self[2] or "")


class Hidden(object):
    """An argument whose value is never shown: the command runs with `value`, and its
    `+ ` line (and any message that shows the command) has `shown` in its place,
    unquoted. `str()` and `repr()` give `shown` too, so a value cannot slip out by a
    print or a traceback.

        ctx.write(["gh", "variable", "set", name, "--repo", repo, "--body", Hidden(value)])
        # + gh variable set NAME --repo o/r --body <value>
    """

    __slots__ = ("value", "shown")

    def __init__(self, value, shown="<value>"):
        self.value = str(value)
        self.shown = shown

    def __str__(self):
        return self.shown

    __repr__ = __str__


def _plain(argv):
    """The arguments as they run: a Hidden one is its value."""
    return [a.value if isinstance(a, Hidden) else str(a) for a in argv]


def show_command(argv):
    """The command as its `+ ` line shows it: shell-quoted, a Hidden argument as its
    `shown` text."""
    return " ".join(a.shown if isinstance(a, Hidden) else shlex.quote(str(a)) for a in argv)


def _bounded(timeout):
    """(the timeout to run a command with, whether it is the run's deadline)."""
    limit = remaining_seconds()
    if timeout is None or timeout >= limit:
        return limit, True
    return timeout, False


def _run_process(argv, timeout, cwd=None, env=None, stderr=subprocess.PIPE):
    """Run argv (plain strings) with stdin closed and stdout (and stderr, unless given)
    captured, in a process group of its own; when `timeout` passes, kill the group (the
    command and every process it started) and raise subprocess.TimeoutExpired.
    Returns (code, stdout bytes, stderr bytes or None)."""
    kw = {}
    if os.name == "posix":
        kw["start_new_session"] = True
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=stderr, cwd=cwd, env=env, **kw)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "posix":
                os.killpg(p.pid, signal.SIGKILL)
            else:
                p.kill()
        except OSError:
            pass
        try:
            p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        raise
    except BaseException:
        p.kill()
        p.wait()
        raise
    return p.returncode, out, err


def run(argv, timeout=None, cwd=None, env=None, stream=None):
    """Show `argv` on stderr (`+ <command>`), then run it and return Completed.

    Nothing of the command's output is printed. stdin is closed. A command that is
    not found returns exit 127 with empty output, as a shell does. An argument given
    as Hidden runs with its value and is shown as `<value>`.

    The command runs at most until the run's deadline (remaining_seconds(), at least 1
    second): when it is reached the command and what it started are killed and
    TimeLimit is raised (with the shown command). A shorter `timeout`, given by the
    caller, ends as exit 124 instead.
    """
    shown = show_command(argv)
    argv = _plain(argv)
    stream = stream or sys.stderr
    stream.write("+ %s\n" % shown)
    stream.flush()
    timeout, deadline = _bounded(timeout)
    try:
        code, out, err = _run_process(argv, timeout, cwd=cwd, env=env)
    except FileNotFoundError:
        return Completed(127, "", "%s: command not found\n" % argv[0])
    except PermissionError:
        return Completed(126, "", "%s: permission denied\n" % argv[0])
    except subprocess.TimeoutExpired:
        if deadline:
            raise TimeLimit(shown)
        return Completed(124, "", "%s: timed out\n" % argv[0])
    return Completed(code, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"))


def run_read(argv, timeout=None, cwd=None, env=None, stream=None):
    """The read-only runner: refuses (ReadRefused, before anything runs or is shown)
    a command that is not on the allowlist of reads, otherwise run()."""
    why = read_refusal(_plain(argv))
    if why:
        raise ReadRefused(argv, why)
    return run(argv, timeout=timeout, cwd=cwd, env=env, stream=stream)


def run_write(skill, argv, root=None, timeout=None, cwd=None, env=None, stream=None):
    """The writing runner: refuses (WriteRefused, before anything runs or is shown) a
    command that is not on the allowlist of writes of `skill`, otherwise run(). The
    module reaches it as ctx.write, which also refuses it outside `mode=apply`."""
    why = write_refusal(skill, argv, root=root)
    if why:
        raise WriteRefused(show_command(argv), why)
    return run(argv, timeout=timeout, cwd=cwd, env=env, stream=stream)


# ---------------------------------------------------------------------------
# Files of the current folder


def _checked_path(skill, path, folder=None):
    """Raise WriteRefused unless `skill` may write `path`, relative to the current
    folder (or `folder`), and the path leads inside it through every link."""
    why = file_refusal(skill, path)
    if why is None:
        why = _inside(folder or os.getcwd(), path)
    if why:
        raise WriteRefused("write %s" % path, why)


def write_file(skill, path, content, stream=None, folder=None):
    """Write the file `path` of the current folder: `content` (str, written as UTF-8,
    or bytes) exactly, with no line ending changed, creating its parent folders.

    Prints `+ write <path>` on stderr first. Raises WriteRefused, before printing or
    writing, for a path `skill` may not write (FILE_WRITES), an absolute path, a path
    with a `..` (or `.`, or empty) part, or one that leads outside the folder through a
    link. Returns True when written, False when the system refused (the module's
    sentence for a write that fails then applies; a part may have been created).
    """
    _checked_path(skill, path, folder)
    data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    stream = stream or sys.stderr
    stream.write("+ write %s\n" % path)
    stream.flush()
    full = os.path.join(folder or os.getcwd(), path)
    try:
        parent = os.path.dirname(full)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(full, "wb") as f:
            f.write(data)
    except OSError:
        return False
    return True


# Files a skill writes for one run in its process's private folder of the system's
# temporary folder (private_temp_dir), never in the working folder (names matched in
# full): the cleanup policy for a `keep` other than 5.
TEMP_FILE_WRITES = {
    "gcp-artifact-registry_cleanup-configure": [
        r"aleogr-cleanup-policy-keep-(?:[1-9]|[1-4][0-9]|50)\.json"],
}


def system_temp_dir():
    """The system's temporary folder as the skills name it: `/tmp` on Linux and macOS,
    the folder of the `TEMP` environment variable on Windows (what `$env:TEMP` or
    `echo %TEMP%` prints), with no command run."""
    if os.name == "nt":
        return os.environ.get("TEMP") or tempfile.gettempdir()
    return "/tmp"


_private_dirs = {}  # the real path of a temporary folder -> this process's private folder


def _remove_private_dirs():
    for d in list(_private_dirs.values()):
        if d:
            shutil.rmtree(d, ignore_errors=True)
    _private_dirs.clear()


atexit.register(_remove_private_dirs)


def private_temp_dir(folder=None):
    """This process's private folder in the system's temporary folder (or `folder`):
    made once, on first use, by tempfile.mkdtemp (prefix `aleogr-`, mode 0700, a name
    no one can know before), and removed with what it holds when the process ends.
    None when it cannot be made. Its path is not fixed, so no file or link left by
    someone else can be at a name inside it."""
    top = folder or system_temp_dir()
    key = os.path.realpath(top)
    if key not in _private_dirs or not os.path.isdir(_private_dirs[key]):
        try:
            _private_dirs[key] = tempfile.mkdtemp(prefix=PRIVATE_TEMP_PREFIX, dir=top)
        except OSError:
            return None
    return _private_dirs[key]


def temp_file_path(name, folder=None):
    """The path write_temp_file writes `name` at: inside private_temp_dir() (made now
    when it was not), or None when that folder cannot be made."""
    d = private_temp_dir(folder)
    return os.path.join(d, name) if d else None


def write_temp_file(skill, name, content, stream=None, folder=None):
    """Write the file `name` in this process's private folder of the system's temporary
    folder (or of `folder`; private_temp_dir): `content` (str as UTF-8, or bytes)
    exactly. Returns its path, or None when the system refused.

    Prints `+ write <path>` on stderr first. Raises WriteRefused, before printing, for
    a name `skill` may not write (TEMP_FILE_WRITES) or a name with a folder in it. The
    file is created new, mode 0600 (O_CREAT|O_EXCL|O_NOFOLLOW): a file or a link
    already at that name is never written through, so None. It is removed with the
    private folder when the process ends."""
    patterns = TEMP_FILE_WRITES.get(skill) or ()
    if not isinstance(name, str) or os.path.basename(name) != name or "\\" in name \
            or not any(re.fullmatch(p, name) for p in patterns):
        raise WriteRefused("write %s" % name, "%s may not write %s in the temporary folder"
                           % (skill, name))
    path = temp_file_path(name, folder)
    if path is None:
        return None
    data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    stream = stream or sys.stderr
    stream.write("+ write %s\n" % path)
    stream.flush()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) \
        | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
    except OSError:
        return None
    return path


def json_from_base64(text):
    """The JSON value that `text` (base64, as `gcloud ... describe` prints a body)
    encodes, or None when it is not base64 of UTF-8 JSON. Spaces and line breaks
    around it do not count."""
    import base64
    import binascii
    if not isinstance(text, str):
        return None
    try:
        raw = base64.b64decode("".join(text.split()), validate=True)
        return json.loads(raw.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None


def base64_of_file(path):
    """The base64 text of a file's bytes (the stop body of a file of the plugin, as a
    job's describe prints it), or None when it cannot be read."""
    import base64
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return None


def random_name_part(length=4, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"):
    """`length` random characters of `alphabet` (the `<random>` of a project id or a
    branch), drawn by the system's random source: no command is run, so no `+` line."""
    import random
    r = random.SystemRandom()
    return "".join(r.choice(alphabet) for _ in range(length))


class Backup(object):
    """Copies of files of the current folder, kept in a new temporary folder, to put
    back byte for byte (mode and times kept, as `cp -p`): what a skill would do with
    `mktemp -d`, `cp -p`, `rm -f` and `rm -rf`, with no shell command.

    - `ok`: False when the folder could not be made or a file that exists could not be
      copied (then nothing is kept and `dir` is None).
    - `dir`: the temporary folder (`<backup>` of a sentence).
    - `existed(path)`: whether the file existed when it was copied.
    - `restore()`: puts every file back from its copy, and removes each one that did
      not exist (as `rm -f`). True when every one is back, False otherwise (the copies
      are then kept in `dir`).
    - `discard()`: removes the temporary folder (as `rm -rf`); its result decides
      nothing.

    Every path is checked as ctx.write_file checks it, before anything is copied.
    `record` (a list, given by ctx.backup) gets `restore <paths>` when restore() runs.
    """

    def __init__(self, skill, paths, stream=None, folder=None, record=None):
        self.skill = skill
        self.record = record  # a list: what restore() wrote is added to it
        self.paths = list(paths)
        self.stream = stream or sys.stderr
        self.folder = folder or os.getcwd()
        self.dir = None
        self.ok = False
        self._existed = {}
        names = [os.path.basename(p) for p in self.paths]
        if len(set(names)) != len(names):
            raise WriteRefused("backup " + " ".join(self.paths), "two files of one name")
        for p in self.paths:
            _checked_path(skill, p, self.folder)
        self._say("backup", self.paths)
        try:
            self.dir = tempfile.mkdtemp(prefix="aleogr-backup-")
        except OSError:
            return
        for p in self.paths:
            src = os.path.join(self.folder, p)
            try:
                shutil.copy2(src, os.path.join(self.dir, os.path.basename(p)))
                self._existed[p] = True
            except FileNotFoundError:
                self._existed[p] = False
            except OSError:
                shutil.rmtree(self.dir, ignore_errors=True)
                self.dir = None
                return
        self.ok = True

    def _say(self, verb, paths):
        self.stream.write("+ %s %s\n" % (verb, " ".join(shlex.quote(p) for p in paths)))
        self.stream.flush()

    def existed(self, path):
        return self._existed.get(path, False)

    def restore(self):
        if not self.ok:
            return False
        for p in self.paths:
            _checked_path(self.skill, p, self.folder)
        self._say("restore", self.paths)
        if self.record is not None:
            self.record.append("restore " + " ".join(self.paths))
        done = True
        for p in self.paths:
            full = os.path.join(self.folder, p)
            try:
                if self._existed[p]:
                    copy = os.path.join(self.dir, os.path.basename(p))
                    shutil.copyfile(copy, full)  # refuses a folder where the file goes
                    shutil.copystat(copy, full)
                elif os.path.lexists(full):
                    os.remove(full)
            except OSError:
                done = False
        return done

    def discard(self):
        if self.dir:
            self.stream.write("+ remove %s\n" % shlex.quote(self.dir))
            self.stream.flush()
            shutil.rmtree(self.dir, ignore_errors=True)
            self.dir = None


# ---------------------------------------------------------------------------
# The clock of a run, and its waits: `sleep 30`, within eight minutes of waiting and
# seven minutes of the run
#
# A command runs under its shell's Bash tool timeout of ten minutes (600000 ms): a run
# killed there prints nothing. So the run keeps its own clock, started by the
# dispatcher (start_clock): a wait is allowed only while it ends within
# WAIT_CLOCK_LIMIT seconds of the run (and within the count budget below), and every
# provider command is bounded by RUN_DEADLINE (run: TimeLimit), which leaves the
# dispatcher the time to print the result of an aborted run.

WAIT_CLOCK_LIMIT = 420  # seven minutes: no wait ends later in a run
RUN_DEADLINE = 570  # nine and a half minutes: no provider command runs later in a run
STEP_LIMIT = 240  # four minutes: an orchestrator begins no new step later (step_allowed)
# What a caller keeps for itself after the deadline it passes to a command it calls: the
# called command ends by then, and the caller still has the time to print its answer.
CALL_MARGIN = 30
# The environment of a command:
# - ALEOGR_RUN_ENDS: set by call_plugin for the command it calls, the caller's deadline
#   (less CALL_MARGIN) as an absolute wall-clock time (seconds since the epoch). The
#   called command's deadline, wait limit and step limit become the smaller of its own
#   and what is left of it (clock_limits).
# - ALEOGR_STEP_LIMIT and ALEOGR_WAIT_CLOCK_LIMIT: test aids that can only shorten a
#   run, an integer of seconds from 1 to STEP_LIMIT (WAIT_CLOCK_LIMIT); anything else,
#   a larger number included, is ignored.
# - ALEOGR_TEST_SLEEP_CLOCK=1: a test aid of the harness, honoured only when FAKE_LOG is
#   set too (the harness's fake commands are in use): each `sleep <n>` line that the fake
#   `sleep` logs in FAKE_LOG during the run moves the run's clock by <n> seconds. It only
#   adds to the clock, so it can only shorten a run.
RUN_ENDS_ENV = "ALEOGR_RUN_ENDS"
STEP_LIMIT_ENV = "ALEOGR_STEP_LIMIT"
WAIT_CLOCK_LIMIT_ENV = "ALEOGR_WAIT_CLOCK_LIMIT"
TEST_SLEEP_CLOCK_ENV = "ALEOGR_TEST_SLEEP_CLOCK"
_clock = {"now": time.monotonic, "wall": time.time, "start": None, "limits": None,
          "sleep_log": None, "sleep_base": 0}


def _lowering(value, ceiling):
    """The integer `value` (a string of digits) when it is from 1 to `ceiling`, else
    `ceiling`: an environment variable that may only lower a limit."""
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,6}", value):
        n = int(value)
        if 1 <= n <= ceiling:
            return n
    return ceiling


def clock_limits(environ, wall_now):
    """The limits of a run started now (`wall_now`, seconds since the epoch) with the
    environment `environ`: {"deadline", "wait", "step"}, in seconds of the run.

    Each is the module's own (RUN_DEADLINE, WAIT_CLOCK_LIMIT, STEP_LIMIT), lowered by
    ALEOGR_WAIT_CLOCK_LIMIT and ALEOGR_STEP_LIMIT and by what is left of a caller's
    ALEOGR_RUN_ENDS: the deadline is then what is left, and the wait and step limits
    keep the distance they have to the deadline at the top of a run (150 and 330 seconds
    before it), never below 0. A value that is not a number is ignored; none of them can
    raise a limit."""
    deadline, wait, step = float(RUN_DEADLINE), float(WAIT_CLOCK_LIMIT), float(STEP_LIMIT)
    ends = environ.get(RUN_ENDS_ENV)
    if isinstance(ends, str) and re.fullmatch(r"[0-9]{1,12}(?:\.[0-9]{1,6})?", ends):
        left = max(0.0, float(ends) - wall_now)
        if left < deadline:
            deadline = left
            wait = min(wait, max(0.0, left - (RUN_DEADLINE - WAIT_CLOCK_LIMIT)))
            step = min(step, max(0.0, left - (RUN_DEADLINE - STEP_LIMIT)))
    wait = min(wait, float(_lowering(environ.get(WAIT_CLOCK_LIMIT_ENV), WAIT_CLOCK_LIMIT)))
    step = min(step, float(_lowering(environ.get(STEP_LIMIT_ENV), STEP_LIMIT)))
    return {"deadline": deadline, "wait": wait, "step": step}


_SLEEP_LINE = re.compile(r"sleep ([0-9]{1,6})")


def _slept(log):
    """The seconds of the `sleep <n>` lines of the fake commands' log (0 when unread)."""
    try:
        with open(log, encoding="utf-8", errors="replace") as f:
            return sum(int(m.group(1)) for m in (_SLEEP_LINE.fullmatch(line.rstrip("\n"))
                                                  for line in f) if m)
    except OSError:
        return 0


def start_clock(environ=None):
    """The dispatcher's start of the run: the clock counts from now, with the limits of
    clock_limits (os.environ when `environ` is None) and, under the harness only, the
    test aid ALEOGR_TEST_SLEEP_CLOCK."""
    env = os.environ if environ is None else environ
    _clock["start"] = _clock["now"]()
    _clock["limits"] = clock_limits(env, _clock["wall"]())
    log = env.get("FAKE_LOG") if env.get(TEST_SLEEP_CLOCK_ENV) == "1" else None
    _clock["sleep_log"] = log or None
    _clock["sleep_base"] = _slept(log) if log else 0


def set_clock(now=None, start=None, wall=None):
    """For the unit tests only: the time function (time.monotonic when None), the
    start of the run (None: the clock is not started and counts 0) and the wall clock
    (time.time when None). The limits are the module's own and no test aid is on."""
    _clock["now"] = now or time.monotonic
    _clock["wall"] = wall or time.time
    _clock["start"] = start
    _clock["limits"] = None
    _clock["sleep_log"] = None
    _clock["sleep_base"] = 0


def _limit(name, default):
    limits = _clock["limits"]
    return default if limits is None else limits[name]


def run_deadline():
    """This run's deadline in seconds of the run: RUN_DEADLINE, or less (clock_limits)."""
    return _limit("deadline", RUN_DEADLINE)


def wait_clock_limit():
    """No wait ends later than this, in seconds of the run: WAIT_CLOCK_LIMIT, or less."""
    return _limit("wait", WAIT_CLOCK_LIMIT)


def step_limit():
    """No step begins later than this, in seconds of the run: STEP_LIMIT, or less."""
    return _limit("step", STEP_LIMIT)


def elapsed_seconds():
    """The seconds since the dispatcher started the run (0 before it did), with the
    seconds of the fake waits when the test aid ALEOGR_TEST_SLEEP_CLOCK is on."""
    if _clock["start"] is None:
        return 0.0
    seconds = max(0.0, _clock["now"]() - _clock["start"])
    if _clock["sleep_log"]:
        seconds += max(0, _slept(_clock["sleep_log"]) - _clock["sleep_base"])
    return seconds


def remaining_seconds():
    """The time a provider command may still run: up to the run's deadline, at least 1."""
    return max(1, run_deadline() - elapsed_seconds())


def step_allowed():
    """True while the run's clock has not passed the step limit (four minutes, or
    less): an orchestrator checks it before each step and, once it is False, ends the
    command with `continue` (ctx.continue_run) instead of beginning the step."""
    return elapsed_seconds() <= step_limit()


WAIT_SECONDS = 30
WAIT_BUDGET_SECONDS = 8 * 60
WAIT_BUDGET_SENTENCE = ("This run reached its limit of eight minutes of waiting, so it "
                        "stopped here; run it again with the same arguments: it goes on "
                        "from where this run stopped.")
WAIT_BUDGET_HOW = ("run {skill} again with the same arguments: it goes on from where "
                   "this run stopped")
_waited = [0]


def wait_budget_item(skill):
    """The fixed `pending` item of a run that ended on the wait budget."""
    return {"item": "run again", "reason": "manual",
            "how": WAIT_BUDGET_HOW.format(skill=skill)}


def waited_seconds():
    """The seconds of waiting this process has counted (30 per wait run)."""
    return _waited[0]


def reset_wait_budget():
    """For the unit tests only: start the count of waits again."""
    _waited[0] = 0


def wait_allowed():
    """True when one more wait of WAIT_SECONDS stays within the budget: the count of
    waits (sixteen of thirty seconds) and the clock (the wait ends within
    WAIT_CLOCK_LIMIT seconds of the run). With a wait that returns at once (the fake
    `sleep` of the tests) the count decides; with real waits and slow commands, the
    clock does."""
    return _waited[0] + WAIT_SECONDS <= WAIT_BUDGET_SECONDS and wait_clock_allows()


def wait_clock_allows():
    """True when one more wait of WAIT_SECONDS ends within the run's wait limit
    (wait_clock_limit): the only limit of an uncounted wait (ctx.wait(counted=False))."""
    return elapsed_seconds() + WAIT_SECONDS <= wait_clock_limit()


# ---------------------------------------------------------------------------
# Calling another plugin's command

NOT_FOUND_SENTENCE = ("The command {command} was not found: install the plugin {command} "
                      "of the aleogr marketplace (/plugin install {command}@aleogr), then "
                      "run this again.")
NOT_CONVERTED_SENTENCE = "The command {command} cannot run {skill} yet: update the plugin {command}."
NO_RESULT_SENTENCE = "The command {command} gave no result for {skill}."


def _call_failure(kind, command, skill, sentence):
    return {
        "aleogr-result": 1,
        "action": skill,
        "status": "failed",
        "resources": [],
        "outputs": {},
        "pending": [],
        "answer": [sentence],
        "callError": kind,
    }


def call_plugin(command, skill, args=None, timeout=None, read_only=False):
    """Run `<command> --json <skill> key=value ...`, the command found on PATH (with
    `--read-only` first when `read_only`).

    Its stderr (the provider commands it shows) goes through to ours. Returns the
    parsed result object (with its `answer` lines). When the command is not found, is
    not converted for that skill (exit 64) or gives no JSON object, returns a fixed
    failure: `status` `failed`, `callError` `not-found`, `not-converted` or
    `no-result`, and one sentence in `answer`.

    A callee stopped by a refused read or write exits 70 after printing its own
    `failed` result (refused_result: the sentence of the refusal, and what it had
    already written). That result is returned as the callee gave it, its answer kept,
    with `callError` `refused` added, so the caller can relay the callee's sentence.
    Any other exit 70, or a non-zero exit with no result object, is `no-result`.

    The callee runs at most until this run's deadline, as a provider command does:
    when it is reached, the callee and what it started are killed and TimeLimit is
    raised. A shorter `timeout` ends as `no-result` instead.

    The callee is told this run's deadline, less CALL_MARGIN, in its environment
    (ALEOGR_RUN_ENDS, an absolute wall-clock time): its own deadline, wait limit and
    step limit are then no later (clock_limits), so it ends first and this run can
    still print its answer. A callee whose wait was refused (by the count of waits or
    by the clock) says so in its document as `data.waitRefused: true`, and one stopped
    by its deadline as `data.timeLimit: true` (with `callError` `time-limit` here
    instead of `refused`): ended_by_limit(result) tells a caller that may answer
    `continue` instead of treating it as a failure.
    """
    path = shutil.which(command)
    if path is None:
        return _call_failure("not-found", command, skill,
                             NOT_FOUND_SENTENCE.format(command=command))
    argv = [path] + (["--read-only"] if read_only else []) + ["--json", skill] + format_args(
        args or {})
    timeout, deadline = _bounded(timeout)
    env = dict(os.environ)
    env[RUN_ENDS_ENV] = "%.3f" % (_clock["wall"]() + max(
        0.0, run_deadline() - elapsed_seconds() - CALL_MARGIN))
    try:
        code, out, _ = _run_process(argv, timeout, stderr=None, env=env)
    except subprocess.TimeoutExpired:
        if deadline:
            raise TimeLimit([command] + argv[1:])
        return _call_failure("no-result", command, skill,
                             NO_RESULT_SENTENCE.format(command=command, skill=skill))
    except OSError:
        return _call_failure("no-result", command, skill,
                             NO_RESULT_SENTENCE.format(command=command, skill=skill))
    if code == EXIT_NOT_CONVERTED:
        return _call_failure("not-converted", command, skill,
                             NOT_CONVERTED_SENTENCE.format(command=command, skill=skill))
    try:
        obj = json.loads(out.decode("utf-8"))
    except ValueError:
        obj = None
    if code == EXIT_SOFTWARE and isinstance(obj, dict) \
            and obj.get("aleogr-result") == 1 and obj.get("status") == "failed":
        data = obj.get("data")
        obj["callError"] = "time-limit" if isinstance(data, dict) \
            and data.get("timeLimit") is True else "refused"
        return obj
    if code != 0 or not isinstance(obj, dict):
        return _call_failure("no-result", command, skill,
                             NO_RESULT_SENTENCE.format(command=command, skill=skill))
    return obj


def ended_by_limit(result):
    """True when a called command's result (call_plugin) says that a limit of the run
    ended it: its wait was refused (`data.waitRefused`) or it reached its deadline
    (`data.timeLimit`). A caller that can continue then answers `continue`."""
    data = result.get("data") if isinstance(result, dict) else None
    return isinstance(data, dict) and (data.get("waitRefused") is True
                                       or data.get("timeLimit") is True)


# ---------------------------------------------------------------------------
# The answer: result block, table, printing

READ_ONLY_COST = {"fixed": False, "notes": "read-only"}


def result_block(family, provider, action, status, outputs, mode="plan", resources=(),
                 pending=(), cost=None, **extra):
    """The `aleogr-result` object, its keys in the contract's order. `extra` keys
    (`secretRefs`, `requests`, ...) go between `outputs` and `cost`."""
    block = {
        "aleogr-result": 1,
        "family": family,
        "provider": provider,
        "action": action,
        "mode": mode,
        "status": status,
        "resources": list(resources),
        "outputs": outputs,
    }
    for k, v in extra.items():
        block[k] = v
    block["cost"] = dict(READ_ONLY_COST) if cost is None else cost
    block["pending"] = list(pending)
    return block


class Result(object):
    """What a skill's run() returns: the answer's lines and the result object.

    `data` (optional, a JSON object) is what the skill read that a calling command needs
    and the block does not hold (for example the repository's copy of a file). It goes
    only into the `--json` document, as its key `data`: never into the fenced block or
    the answer, so the owner never sees it.
    """

    def __init__(self, block, lines=(), data=None, expand=None):
        self.block = block
        self.lines = list(lines)
        self.data = data
        self.expand = expand  # the layout of the fenced block (render_block); None: default

    @property
    def status(self):
        return self.block.get("status")


def _inline(v):
    if isinstance(v, dict):
        if not v:
            return "{}"
        return "{ " + ", ".join("%s: %s" % (json.dumps(k, ensure_ascii=False), _inline(x))
                                for k, x in v.items()) + " }"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_inline(x) for x in v) + "]"
    return json.dumps(v, ensure_ascii=False)


def _value(v, indent):
    if isinstance(v, (list, tuple)) and v and all(isinstance(x, dict) for x in v):
        pad = " " * (indent + 2)
        return "[\n" + ",\n".join(pad + _inline(x) for x in v) + "\n" + " " * indent + "]"
    return _inline(v)


def _members(obj, indent, expand):
    pad = " " * indent
    out = []
    items = list(obj.items())
    for i, (k, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        key = json.dumps(k, ensure_ascii=False)
        if k in expand and isinstance(v, dict) and v:
            inner = expand[k] if isinstance(expand, dict) else ()
            out.append("%s%s: {" % (pad, key))
            out.extend(_members(v, indent + 2, inner or ()))
            out.append("%s}%s" % (pad, comma))
        else:
            out.append("%s%s: %s%s" % (pad, key, _value(v, indent), comma))
    return out


DEFAULT_EXPAND = ("outputs",)


def render_block(block, expand=DEFAULT_EXPAND):
    """The result object laid out as the skills print it: one top-level key per line,
    `outputs` one key per line, a list of objects one object per line, every other
    value on one line (`{ "a": 1 }`, `["x", "y"]`, `[]`, `{}`).

    `expand` names the objects laid out one key per line: a tuple of keys (their own
    members on one line each), or a dict of key to the same kind of value, for objects
    inside them (`{"outputs": {"declaration": ("repo",)}}`). A module that prints a
    nested object expanded in its SKILL.md's example sets BLOCK_EXPAND."""
    return "\n".join(["{"] + _members(block, 2, expand) + ["}"])


def render_table(headers, rows):
    """A Markdown table: `| a | b |`, `|---|---|`, one row per line. A `|` in a cell
    is written `\\|`; None is an empty cell."""
    def cell(x):
        return ("" if x is None else str(x)).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(cell(h) for h in headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(cell(x) for x in r) + " |")
    return lines


def render_answer(result):
    """The full stdout of a command: the lines, a blank line, the fenced block."""
    text = ""
    if result.lines:
        text = "\n".join(result.lines) + "\n\n"
    expand = getattr(result, "expand", None) or DEFAULT_EXPAND
    return text + "```aleogr-result\n" + render_block(result.block, expand) + "\n```\n"


def render_json(result):
    """The stdout of `--json`: the result object, with the answer's lines as `answer`
    and, when the skill gave any, its `data`."""
    obj = dict(result.block)
    obj["answer"] = list(result.lines)
    if getattr(result, "data", None) is not None:
        obj["data"] = result.data
    return json.dumps(obj, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# A run in more than one command
#
# A skill whose module sets CONTINUES = True (an orchestrator) may end a command with
# the status `continue` (ctx.continue_run): its answer is one line (what the run waits
# for), then `next: <the command to run>`, then the block. The next command is the same
# plugin command and skill with the same arguments, each single-quoted as the shells
# write them, and `run=<id>`. What the run carries from one command to the next is kept
# in a private file named by <id> (below); the dispatcher accepts `run=` only for such
# a skill, takes it out of the arguments the module gets, and removes the file when the
# run ends with any other status. A run has at most MAX_COMMANDS commands.

MAX_COMMANDS = 8
CARRY_FOLDER_PREFIX = "aleogr-runs-"  # + the user's id: <system temporary folder>/aleogr-runs-<uid>
CARRY_MAX_AGE = 24 * 60 * 60  # a carried file older than a day is removed when a run starts
MAX_CARRY_BYTES = 64 * 1024
RUN_ID_RE = re.compile(r"[a-z0-9]{12}")
CARRY_LOST_SENTENCE = "An earlier part of this run could not be recalled: {why}."
# Why a carried file was not read (ctx.carry_refusal), each the end of CARRY_LOST_SENTENCE.
CARRY_REFUSALS = {
    "malformed": "the id of the run is not well formed",
    "missing": "its file is missing",
    "unreadable": "its file could not be read",
    "invalid": "its file is not valid",
    "not-private": "its file or its folder is not private to this user",
    "mismatch": "the declaration or the arguments are not the ones it was kept for",
}
_carry_top = [None]  # the folder the carried files' folder is made in (None: system_temp_dir)


class CarryNotSaved(Exception):
    """ctx.continue_run could not save the carried file (the folder is not private, the
    disk refused, the carry is too large): an unexpected error of the run."""


def set_carry_folder(top=None):
    """For the unit tests only: make the folder of carried files in `top` instead of the
    system's temporary folder (None: back to it)."""
    _carry_top[0] = top


def _uid():
    return os.getuid() if hasattr(os, "getuid") else None


def carry_folder_path():
    """<system temporary folder>/aleogr-runs-<uid>: the folder of this user's carried
    files (`aleogr-runs-user` where the system has no user id)."""
    uid = _uid()
    return os.path.join(_carry_top[0] or system_temp_dir(),
                        CARRY_FOLDER_PREFIX + ("user" if uid is None else str(uid)))


def _private(st, directory):
    """True when `st` (an lstat or fstat) is a real folder (a regular file), not a link,
    owned by this user, with no permission for its group or others. Where the system
    has no user id (Windows), only the kind is checked."""
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(st.st_mode):
        return False
    uid = _uid()
    if uid is not None and (st.st_uid != uid or stat.S_IMODE(st.st_mode) & 0o077):
        return False
    return True


def carry_folder(create=True):
    """(the folder of carried files, None) when it is private (_private), made 0700 when
    missing and `create`; (None, "missing") when it is missing and not `create`; (None,
    "not-private") when it is a link, not a folder, someone else's, open to the group or
    others, or cannot be made."""
    path = carry_folder_path()
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        if not create:
            return None, "missing"
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
        except OSError:
            return None, "not-private"
        try:
            st = os.lstat(path)
        except OSError:
            return None, "not-private"
    except OSError:
        return None, "not-private"
    if not _private(st, directory=True):
        return None, "not-private"
    return path, None


def new_run_id():
    """Twelve random lowercase letters and digits."""
    return random_name_part(12)


def _valid_record(record):
    return (isinstance(record, dict) and record.get("aleogr-run") == 1
            and isinstance(record.get("plugin"), str) and isinstance(record.get("skill"), str)
            and (record.get("digest") is None or isinstance(record.get("digest"), str))
            and type(record.get("commands")) is int and 1 <= record["commands"] < MAX_COMMANDS
            and isinstance(record.get("carry"), dict))


def read_carry(run_id):
    """(the record of the carried file `<id>.json`, None), or (None, why): why is a key
    of CARRY_REFUSALS. The file is opened without following a link and must be a
    regular file of this user with no permission for others (`not-private`)."""
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        return None, "malformed"
    folder, why = carry_folder(create=False)
    if folder is None:
        return None, why
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) \
        | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(os.path.join(folder, run_id + ".json"), flags)
    except FileNotFoundError:
        return None, "missing"
    except OSError as e:
        return None, "not-private" if e.errno == errno.ELOOP else "unreadable"
    try:
        if not _private(os.fstat(fd), directory=False):
            return None, "not-private"
        chunks, size = [], 0
        while size <= MAX_CARRY_BYTES:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    except OSError:
        return None, "unreadable"
    finally:
        os.close(fd)
    if size > MAX_CARRY_BYTES:
        return None, "invalid"
    try:
        record = json.loads(b"".join(chunks).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, "invalid"
    if not _valid_record(record):
        return None, "invalid"
    return record, None


def save_carry(run_id, record, replace=False):
    """Write the carried file `<id>.json`, mode 0600, whole: a new one is created with
    O_EXCL|O_NOFOLLOW (False when anything is already at that name); a rewrite
    (`replace`) writes a new file the same way and renames it over the old one. False
    when the folder is not private, the record is larger than MAX_CARRY_BYTES or the
    system refused."""
    folder, _ = carry_folder(create=True)
    if folder is None or not RUN_ID_RE.fullmatch(run_id or ""):
        return False
    data = json.dumps(record, ensure_ascii=False, sort_keys=True).encode("utf-8")
    if len(data) > MAX_CARRY_BYTES:
        return False
    final = os.path.join(folder, run_id + ".json")
    target = final if not replace else os.path.join(
        folder, "%s.json.%s.tmp" % (run_id, random_name_part(8)))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) \
        | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(target, flags, 0o600)
    except OSError:
        return False
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if replace:
            os.replace(target, final)
    except OSError:
        try:
            os.remove(target)
        except OSError:
            pass
        return False
    return True


def remove_carry(run_id):
    """Remove the carried file `<id>.json` (nothing when the id is not well formed or
    the folder is not private)."""
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        return
    folder, _ = carry_folder(create=False)
    if folder is None:
        return
    try:
        os.remove(os.path.join(folder, run_id + ".json"))
    except OSError:
        pass


def sweep_carries(max_age=CARRY_MAX_AGE):
    """Remove the files of the carried files' folder (a private one only) that were last
    written more than `max_age` seconds ago."""
    folder, _ = carry_folder(create=False)
    if folder is None:
        return
    now = time.time()
    try:
        names = os.listdir(folder)
    except OSError:
        return
    for name in names:
        path = os.path.join(folder, name)
        try:
            st = os.lstat(path)
            if not stat.S_ISDIR(st.st_mode) and now - st.st_mtime > max_age:
                os.remove(path)
        except OSError:
            pass


def carry_digest(*parts):
    """A digest (hex SHA-256) of `parts`, each bytes (a file's bytes), a string, or a
    JSON value (a dict of arguments, in its keys' order): what ctx.carried compares.
    For project-apply: carry_digest(<the declaration's bytes>, <the arguments without
    run=>)."""
    import hashlib
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, bytes):
            data, kind = p, b"b"
        elif isinstance(p, str):
            data, kind = p.encode("utf-8"), b"s"
        else:
            data, kind = json.dumps(p, ensure_ascii=False).encode("utf-8"), b"j"
        h.update(kind + str(len(data)).encode("ascii") + b":" + data)
    return h.hexdigest()


def quote_argument(text):
    """One argument as the shells write it: inside single quotes, a `'` written `'\\''`."""
    return "'" + str(text).replace("'", "'\\''") + "'"


# ---------------------------------------------------------------------------
# The context a skill runs with


class Context(object):
    """Given to a skill's run(args, ctx).

    Reads:
    - ctx.read(argv): the read-only runner (always, in every mode).
    - ctx.run(argv): ctx.read for a read; when the run may write, ctx.write for the
      rest.

    Writes, only when the run may write (`ctx.writable`: the module sets WRITES = True,
    the mode is `apply`, and the command was not given `--read-only`); otherwise each
    raises WriteRefused before anything runs or is shown:
    - ctx.write(argv): the writing runner (allowlist of writes of this skill).
    - ctx.write_file(path, content): a file of the current folder (FILE_WRITES).
    - ctx.backup(paths): copies of files of the folder, to put back (Backup).
    - ctx.write_temp_file(name, content): a file of this process's private folder in
      the system's temporary folder (TEMP_FILE_WRITES, private_temp_dir), for a flag
      that takes a file the plugin does not hold; its path, or None. Its path is
      common.temp_file_path(name).

    Other:
    - ctx.wait(): one wait, `sleep 30`, within the budget of the run (wait_allowed: the
      count of waits and the clock; False: the budget is spent, nothing was run; end `pending` with WAIT_BUDGET_SENTENCE and
      ctx.wait_budget_item()). ctx.wait(counted=False): the same wait, limited by the
      clock only (wait_clock_allows) and not counted in the budget, for an
      orchestrator's own long wait (thirty tries of the shared instance's start).
      A refused wait sets ctx.wait_refused, which a `--json` document reports as
      `data.waitRefused: true`; a run ended by its deadline reports `data.timeLimit`.
    - ctx.step_allowed(): step_allowed, the step limit of four minutes.
    - ctx.call(command, skill, args): call_plugin (with `--read-only` when this run was
      given it).

    A run in more than one command, for a module that sets CONTINUES = True:
    - ctx.carried(digest): at the start of every command, what an earlier command of
      this run carried (a dict), or None: no `run=` was given, or the carried file was
      refused, and then ctx.carry_refusal says why (a key of CARRY_REFUSALS, None when
      no `run=` was given) and ctx.carry_lost_sentence() is its one fixed sentence.
      `digest` (a string, e.g. carry_digest(...)) is compared with the one the file was
      saved with: a different one refuses it (`mismatch`).
    - ctx.commands: the number of commands this run has used, this one included.
    - ctx.may_continue(): False once the run has used MAX_COMMANDS commands, or when
      the carried file cannot be kept; the module then ends as its SKILL.md ends a
      wait that passed its limit.
    - ctx.continue_run(line, carry, ...): the Result of a command that ends `continue`:
      `line`, `next: <command>`, and the block; `carry` (a small JSON object) is saved
      for the next command.
    - ctx.on_abort(lines): the lines that the result of an aborted run (aborted_result:
      the time limit, an unexpected error) prints, from now on, after what the run
      wrote: what may now cost or need doing. Each call replaces the lines given
      before; an empty list clears them.
    - ctx.result(...), ctx.failed(...): build a Result with the module's FAMILY,
      PROVIDER and ACTION.
    - ctx.plugin_path(*parts), ctx.defaults(): files of this plugin.

    Every command runs through ctx.execute(argv), which unit tests replace.
    """

    def __init__(self, plugin, root, skill, module, mode, args, json_mode=False,
                 read_only=False):
        self.plugin = plugin
        self.root = root
        self.skill = skill
        self.module = module
        self.mode = mode
        self.args = args
        self.json = json_mode
        self.forced_read_only = bool(read_only)
        writes = bool(getattr(module, "WRITES", False))
        self.writable = writes and mode == "apply" and not self.forced_read_only
        self.read_only = not self.writable
        # What this run wrote, in order: each write command run (as its `+ ` line shows
        # it), `write <path>` for each file written, `restore <paths>` for copies put
        # back. A refusal's result names them (refused_result).
        self.writes_run = []
        # The lines of aborted_result, as the module last registered them (on_abort).
        self.abort_lines = []
        # A wait refused by the budget or the clock, and a run ended by its deadline: in
        # the `--json` document as data.waitRefused and data.timeLimit (_with_limits).
        self.wait_refused = False
        self.time_limit = False
        # A run in more than one command (begin_run, carried, continue_run).
        self.continues = bool(getattr(module, "CONTINUES", False))
        self.given_args = list(args.items()) if isinstance(args, dict) else []
        self.run_given = None  # the `run=` value given to this command
        self.run_id = None  # the id of this run's carried file, once known to be its own
        self.commands = 1
        self.carry_refusal = None
        self._record = None
        self._digest = None
        self._digest_given = False
        self.continued = False

    # A run in more than one command

    def begin_run(self, run_value):
        """The dispatcher's start of a command of a CONTINUES skill: old carried files
        are removed (sweep_carries), and the one `run=` names is read (read_carry)."""
        sweep_carries()
        self.run_given = run_value
        if run_value is None:
            return
        record, why = read_carry(run_value)
        if record is not None and (record["plugin"] != self.plugin
                                   or record["skill"] != self.skill):
            record, why = None, "mismatch"
        if record is None:
            self.carry_refusal = why
            return
        self._record = record
        self.run_id = run_value
        self.commands = record["commands"] + 1

    def carried(self, digest):
        """What an earlier command of this run carried (a copy), or None (carry_refusal
        says why, None when no `run=` was given)."""
        self._digest = digest
        self._digest_given = True
        if self._record is None:
            return None
        if self._record.get("digest") != digest:
            self._record = None
            self.run_id = None
            self.commands = 1
            self.carry_refusal = "mismatch"
            return None
        return json.loads(json.dumps(self._record["carry"]))

    def carry_lost_sentence(self):
        """CARRY_LOST_SENTENCE for carry_refusal, or None when nothing was refused."""
        if self.carry_refusal is None:
            return None
        return CARRY_LOST_SENTENCE.format(why=CARRY_REFUSALS[self.carry_refusal])

    def may_continue(self):
        return (self.continues and self.commands < MAX_COMMANDS
                and carry_folder(create=True)[0] is not None)

    def next_command(self, run_id):
        """`<plugin> [--read-only] [--json] <skill> '<key>=<value>' ... 'run=<id>'`: the
        arguments this command was given (without `run=`), in their order."""
        words = [self.plugin] + (["--read-only"] if self.forced_read_only else []) \
            + (["--json"] if self.json else []) + [self.skill]
        words += [quote_argument("%s=%s" % (k, "" if v is None else v))
                  for k, v in self.given_args]
        words.append(quote_argument("run=" + run_id))
        return " ".join(words)

    def continue_run(self, line, carry, outputs=None, resources=(), pending=(), cost=None,
                     **extra):
        """The Result of a command that ends `continue`: the answer is `line`, then
        `next: <next_command>`, then the block (status `continue`). `carry`, a dict of
        JSON values, is saved for the next command with the digest given to carried()
        and the count of commands. Call carried() first and continue only when
        may_continue(); CarryNotSaved when the file cannot be saved."""
        if not self.continues:
            raise CarryNotSaved("%s does not declare CONTINUES" % self.skill)
        if not self._digest_given:
            raise CarryNotSaved("carried() was not called in this command")
        if not self.may_continue():
            raise CarryNotSaved("this run may not continue")
        if not isinstance(carry, dict):
            raise CarryNotSaved("the carry is not a dict")
        record = {"aleogr-run": 1, "plugin": self.plugin, "skill": self.skill,
                  "digest": self._digest, "commands": self.commands,
                  "carry": json.loads(json.dumps(carry))}
        if self.run_id is not None:
            saved = save_carry(self.run_id, record, replace=True)
        else:
            saved = False
            for _ in range(3):
                run_id = new_run_id()
                if save_carry(run_id, record):
                    self.run_id, saved = run_id, True
                    break
        if not saved:
            raise CarryNotSaved("the carried file could not be saved")
        self.continued = True
        return self.result("continue", {} if outputs is None else outputs,
                           resources=resources, pending=pending, cost=cost,
                           lines=[line, "next: " + self.next_command(self.run_id)], **extra)

    def step_allowed(self):
        return step_allowed()

    # Running

    def execute(self, argv, timeout=None):
        """Show then run a command that was already checked (the one place a command
        runs; unit tests replace it)."""
        return run(argv, timeout=timeout)

    def read(self, argv, timeout=None):
        why = read_refusal(_plain(argv))
        if why:
            raise ReadRefused(argv, why)
        return self.execute(argv, timeout=timeout)

    def _may_write(self, what):
        if not self.writable:
            raise WriteRefused(what, "this run may not write (mode=%s%s)" % (
                self.mode, ", --read-only" if self.forced_read_only else ""))

    def write(self, argv, timeout=None):
        self._may_write(show_command(argv))
        why = write_refusal(self.skill, argv, root=self.root)
        if why:
            raise WriteRefused(show_command(argv), why)
        self.writes_run.append(show_command(argv))
        return self.execute(argv, timeout=timeout)

    def run(self, argv, timeout=None):
        if self.writable and read_refusal(_plain(argv)):
            return self.write(argv, timeout=timeout)
        return self.read(argv, timeout=timeout)

    def write_file(self, path, content):
        self._may_write("write %s" % path)
        done = write_file(self.skill, path, content)
        self.writes_run.append("write %s" % path)
        return done

    def backup(self, paths):
        self._may_write("backup %s" % " ".join(paths))
        return Backup(self.skill, paths, record=self.writes_run)

    def write_temp_file(self, name, content):
        """A file of the system's temporary folder (TEMP_FILE_WRITES): its path, or
        None when the system refused. Only when the run may write."""
        self._may_write("write %s" % name)
        path = write_temp_file(self.skill, name, content)
        self.writes_run.append("write %s" % (path or name))
        return path

    def wait(self, counted=True):
        if not (wait_allowed() if counted else wait_clock_allows()):
            self.wait_refused = True
            return False
        if counted:
            _waited[0] += WAIT_SECONDS
        self.read(["sleep", str(WAIT_SECONDS)])
        return True

    def wait_budget_item(self):
        return wait_budget_item(self.skill)

    def on_abort(self, lines):
        self.abort_lines = [lines] if isinstance(lines, str) else list(lines or ())

    def call(self, command, skill, args=None, timeout=None):
        return call_plugin(command, skill, args, timeout=timeout,
                           read_only=self.forced_read_only)

    # Files of this plugin

    def plugin_path(self, *parts):
        return os.path.join(self.root, *parts)

    def defaults(self):
        with open(self.plugin_path("defaults.json"), encoding="utf-8") as f:
            return json.load(f)

    # The result

    def result(self, status, outputs, resources=(), pending=(), cost=None, lines=(),
               mode=None, **extra):
        m = self.module
        block = result_block(m.FAMILY, m.PROVIDER, m.ACTION, status, outputs,
                             mode=mode or getattr(m, "RESULT_MODE", None) or self.mode,
                             resources=resources, pending=pending, cost=cost, **extra)
        return Result(block, lines, expand=getattr(m, "BLOCK_EXPAND", None))

    def failed(self, lines, outputs, pending=(), cost=None, **extra):
        if isinstance(lines, str):
            lines = [lines]
        return self.result("failed", outputs, pending=pending, cost=cost, lines=lines,
                           **extra)


READ_ONLY_APPLY_SENTENCE = ("mode=apply cannot run with --read-only: nothing was run. Run "
                            "the command again without --read-only to apply.")
NOTHING_RUN_COST = {"fixed": False, "notes": "nothing was run"}


def read_only_refusal(ctx):
    """The result of `--read-only` with `mode=apply`: `failed`, one fixed sentence,
    nothing run."""
    return ctx.result("failed", {}, cost=dict(NOTHING_RUN_COST),
                      lines=[READ_ONLY_APPLY_SENTENCE], mode="apply")


REPEATED_SENTENCE = "The argument {key} is given twice."


def repeated_result(ctx, keys):
    """The result of a command line that gives a key=value argument more than once:
    `failed`, one fixed sentence per such key, nothing run."""
    return ctx.result("failed", {}, cost=dict(NOTHING_RUN_COST),
                      lines=[REPEATED_SENTENCE.format(key=k) for k in keys])


REFUSED_SENTENCE = ("This run stopped before a command that this tooling does not allow, "
                    "and nothing after it was run.")
REFUSED_NOTHING_WRITTEN = "Nothing had been written by this run before it stopped."
REFUSED_WRITTEN = "Before it stopped, this run had already run these writes: {writes}."
REFUSED_UNKNOWN = ("Earlier steps of this run may have been made; running the plan shows "
                   "the state.")
REFUSED_COST = {"fixed": False, "notes": "stopped before a command the tooling does not allow"}


def _written_line(ctx):
    """The sentence of what this run had already written (ctx.writes_run)."""
    written = getattr(ctx, "writes_run", None)
    if written is None:
        return REFUSED_UNKNOWN
    if not written:
        return REFUSED_NOTHING_WRITTEN
    return REFUSED_WRITTEN.format(writes=", ".join("`%s`" % w for w in written))


def refused_result(ctx):
    """The result printed when a read or a write was refused (ReadRefused,
    WriteRefused): `failed`, REFUSED_SENTENCE, then what this run had already written
    (ctx.writes_run), and never the refused command itself."""
    return ctx.result("failed", {}, cost=dict(REFUSED_COST),
                      lines=[REFUSED_SENTENCE, _written_line(ctx)])


TIME_LIMIT_SENTENCE = ("This run reached its time limit while a command was still running; "
                       "that command may still take effect.")
UNEXPECTED_SENTENCE = "This run stopped on an unexpected error of the tooling."
READ_STATE_SENTENCE = "Read the state before running it again: the plan shows it."
ABORTED_COST = {"fixed": False, "notes": "the run may have changed something"}


def aborted_result(ctx, sentence):
    """The result printed when a run was aborted (TimeLimit, or any unexpected
    exception): `failed`, `sentence` (TIME_LIMIT_SENTENCE or UNEXPECTED_SENTENCE), what
    this run had already written, the lines the module registered (ctx.on_abort), then
    READ_STATE_SENTENCE. Nothing of the exception's text: it may hold values."""
    lines = [sentence, _written_line(ctx)] + list(getattr(ctx, "abort_lines", None) or ())
    lines.append(READ_STATE_SENTENCE)
    return ctx.result("failed", {}, cost=dict(ABORTED_COST), lines=lines)


def run_skill(module, args, ctx):
    """module.run(args, ctx), and every way it can end: (Result, exit code, the kind of
    ending or None). A refused read or write gives refused_result, the time limit and
    any other exception aborted_result, each with EXIT_SOFTWARE; a run that returns no
    Result is an unexpected error. The kind (`not a read`, `not an allowed write`, `time
    limit`, `unexpected error`) is for the one line on stderr."""
    try:
        result = module.run(args, ctx)
    except ReadRefused:
        return refused_result(ctx), EXIT_SOFTWARE, "refused, not a read"
    except WriteRefused:
        return refused_result(ctx), EXIT_SOFTWARE, "refused, not an allowed write"
    except TimeLimit:
        try:
            ctx.time_limit = True
        except AttributeError:
            pass
        return aborted_result(ctx, TIME_LIMIT_SENTENCE), EXIT_SOFTWARE, "time limit reached"
    except Exception:  # noqa: BLE001 - never a traceback: its text may hold values
        return aborted_result(ctx, UNEXPECTED_SENTENCE), EXIT_SOFTWARE, "unexpected error"
    if not isinstance(result, Result):
        return aborted_result(ctx, UNEXPECTED_SENTENCE), EXIT_SOFTWARE, "returned no Result"
    return result, EXIT_OK, None


# ---------------------------------------------------------------------------
# The command's entry point


def _load(skill):
    try:
        return importlib.import_module("skills." + module_name(skill))
    except ModuleNotFoundError as e:
        if e.name in ("skills", "skills." + module_name(skill)):
            return None
        raise


def _converted(module, mode):
    if module is None:
        return False
    return mode is None or mode not in getattr(module, "UNCONVERTED_MODES", ())


def main(plugin, root, argv, stdout=None, stderr=None):
    """Dispatch `<plugin> ...`. Returns the exit code."""
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        inv = parse_command_line(argv)
    except UsageError as e:
        stderr.write("%s: %s\nusage: %s [--read-only] [--json] <skill> [key=value ...]\n"
                     "       %s --has <skill> [mode]\n" % (plugin, e, plugin, plugin))
        return EXIT_USAGE
    module = _load(inv.skill)
    if module is None and not os.path.isfile(os.path.join(root, "skills", inv.skill,
                                                          "SKILL.md")):
        stderr.write("%s: unknown skill: %s\n" % (plugin, inv.skill))
        return EXIT_USAGE
    if inv.has:
        return EXIT_OK if _converted(module, inv.mode) else EXIT_NOT_CONVERTED
    mode = inv.args.get("mode") or getattr(module, "DEFAULT_MODE", "plan")
    if not _converted(module, mode):
        what = inv.skill if module is None else "%s mode=%s" % (inv.skill, mode)
        stderr.write("%s: not converted: %s\n" % (plugin, what))
        return EXIT_NOT_CONVERTED
    return run_command(plugin, root, inv, module, mode, stdout, stderr)


def run_command(plugin, root, inv, module, mode, stdout=None, stderr=None, environ=None):
    """Run the parsed command `inv` with the skill's `module` (a module, or any object
    with its names: the unit tests give one): start the run's clock (start_clock, with
    `environ`), dispatch, and give the clock back as it was. Returns the exit code."""
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    before = dict(_clock)
    start_clock(environ)
    try:
        return _dispatch(plugin, root, inv, module, mode, stdout, stderr)
    finally:
        _clock.update(before)  # a process ends here; an in-process test goes on


CONTINUE_UNEXPECTED = "ended continue without ctx.continue_run"


def _end_run(ctx, result, code, plugin, stderr):
    """The end of a command and its carried file: a `continue` is accepted only from
    ctx.continue_run; any other status removes the run's file. The file `run=` named is
    removed too unless it is the one this command saved."""
    if result.status == "continue" and not getattr(ctx, "continued", False):
        stderr.write("%s: %s: %s\n" % (plugin, ctx.skill, CONTINUE_UNEXPECTED))
        stderr.flush()
        result, code = aborted_result(ctx, UNEXPECTED_SENTENCE), EXIT_SOFTWARE
    if ctx.continues:
        if ctx.run_given is not None and ctx.run_given != ctx.run_id:
            remove_carry(ctx.run_given)
        if result.status != "continue" and ctx.run_id is not None:
            remove_carry(ctx.run_id)
    return result, code


def _with_limits(result, ctx):
    """data.waitRefused and data.timeLimit (only when true) in the `--json` document."""
    flags = {}
    if getattr(ctx, "wait_refused", False):
        flags["waitRefused"] = True
    if getattr(ctx, "time_limit", False):
        flags["timeLimit"] = True
    if flags and (result.data is None or isinstance(result.data, dict)):
        data = dict(result.data or {})
        data.update(flags)
        result.data = data
    return result


def _dispatch(plugin, root, inv, module, mode, stdout, stderr):
    args = inv.args
    run_value = None
    continues = bool(getattr(module, "CONTINUES", False))
    if continues and "run" in args:
        # `run=` is the dispatcher's for a skill that can continue; for any other skill
        # it is an argument like any other (the module refuses it as unknown).
        args = dict(args)
        run_value = args.pop("run")
    ctx = Context(plugin, root, inv.skill, module, mode, args, inv.json,
                  read_only=inv.read_only)
    if continues:
        ctx.begin_run(run_value)
    code = EXIT_OK
    if inv.repeated:
        result = repeated_result(ctx, inv.repeated)
    elif inv.read_only and mode == "apply":
        result = read_only_refusal(ctx)
    else:
        result, code, why = run_skill(module, args, ctx)
        if why:
            # A bug of the command, or its time limit: loud (exit 70), but never without
            # a result. The line shows no value of a command and no exception's text.
            stderr.write("%s: %s: %s\n" % (plugin, inv.skill, why))
            stderr.flush()
    result, code = _end_run(ctx, result, code, plugin, stderr)
    result = _with_limits(result, ctx)
    try:
        text = render_json(result) if inv.json else render_answer(result)
    except Exception:  # noqa: BLE001 - a result that cannot be printed (too deep, ...)
        stderr.write("%s: %s: unexpected error\n" % (plugin, inv.skill))
        result = aborted_result(ctx, UNEXPECTED_SENTENCE)
        text = render_json(result) if inv.json else render_answer(result)
        code = EXIT_SOFTWARE
    stdout.write(text)
    stdout.flush()
    return code
