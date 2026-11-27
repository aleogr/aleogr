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
- `call_plugin`, which runs another plugin's command with `--json`;
- the answer: lines, a table, and the fenced `aleogr-result` block.

Python 3.9 or later, standard library only.
"""

import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

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
    """One argument that is exactly `<plugin root>/files/<one of names>`."""

    def __init__(self, *names):
        self.names = names
        self.name = "a file of the plugin: " + ", ".join(names)

    def match(self, arg, env):
        root = (env or {}).get("root")
        if not root:
            return False
        return any(os.path.realpath(arg) == os.path.realpath(os.path.join(root, "files", n))
                   for n in self.names)


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
        words = [a for a in rest if not a.startswith("-")][:5]
        if "delete" in words:
            return "gcloud ... delete"
        if "set-iam-policy" in words:
            return "gcloud ... set-iam-policy"
    return None


def _match_shape(shape, args, env):
    """None when `args` (the command after the tool) matches `shape`, else a reason."""
    i = 0
    for item in shape:
        if callable(item) and not hasattr(item, "match"):
            return item(list(args[i:]), env)
        if i >= len(args):
            return "too short"
        a = args[i]
        if isinstance(item, str):
            if a != item:
                return "%s where the shape has %s" % (a, item)
        elif not item.match(a, env):
            return "%s is not %s" % (a, item.name)
        i += 1
    if i != len(args):
        return "too long"
    return None


def write_refusal(skill, argv, root=None):
    """None when `argv` is a write that `skill` may run, otherwise the reason it is not.
    `root` is the plugin's folder (for the shapes that name a file of the plugin)."""
    argv = _plain(argv)
    why = always_refused(argv)
    if why:
        return why
    shapes = WRITE_SHAPES.get(skill)
    if not shapes:
        return "%s has no allowed write" % skill
    tool = _tool_name(argv[0])
    env = {"root": root}
    for shape in shapes:
        if _shape_tool(skill, shape) != tool:
            continue
        if _match_shape(shape, argv[1:], env) is None:
            return None
    return "not on the allowlist of writes of %s" % skill


def is_write_allowed(skill, argv, root=None):
    return write_refusal(skill, argv, root) is None


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


def run(argv, timeout=None, cwd=None, env=None, stream=None):
    """Show `argv` on stderr (`+ <command>`), then run it and return Completed.

    Nothing of the command's output is printed. stdin is closed. A command that is
    not found returns exit 127 with empty output, as a shell does. An argument given
    as Hidden runs with its value and is shown as `<value>`.
    """
    shown = show_command(argv)
    argv = _plain(argv)
    stream = stream or sys.stderr
    stream.write("+ %s\n" % shown)
    stream.flush()
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout, cwd=cwd, env=env)
    except FileNotFoundError:
        return Completed(127, "", "%s: command not found\n" % argv[0])
    except PermissionError:
        return Completed(126, "", "%s: permission denied\n" % argv[0])
    except subprocess.TimeoutExpired:
        return Completed(124, "", "%s: timed out\n" % argv[0])
    return Completed(p.returncode, p.stdout.decode("utf-8", "replace"),
                     p.stderr.decode("utf-8", "replace"))


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
# Waits: `sleep 30`, within eight minutes per run

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
    """True when one more wait of WAIT_SECONDS stays within the budget."""
    return _waited[0] + WAIT_SECONDS <= WAIT_BUDGET_SECONDS


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
    """
    path = shutil.which(command)
    if path is None:
        return _call_failure("not-found", command, skill,
                             NOT_FOUND_SENTENCE.format(command=command))
    argv = [path] + (["--read-only"] if read_only else []) + ["--json", skill] + format_args(
        args or {})
    try:
        p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=None, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return _call_failure("no-result", command, skill,
                             NO_RESULT_SENTENCE.format(command=command, skill=skill))
    if p.returncode == EXIT_NOT_CONVERTED:
        return _call_failure("not-converted", command, skill,
                             NOT_CONVERTED_SENTENCE.format(command=command, skill=skill))
    try:
        obj = json.loads(p.stdout.decode("utf-8"))
    except ValueError:
        obj = None
    if p.returncode != 0 or not isinstance(obj, dict):
        return _call_failure("no-result", command, skill,
                             NO_RESULT_SENTENCE.format(command=command, skill=skill))
    return obj


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

    Other:
    - ctx.wait(): one wait, `sleep 30`, within the budget of the run (False: the budget
      is spent, nothing was run; end `pending` with WAIT_BUDGET_SENTENCE and
      ctx.wait_budget_item()).
    - ctx.call(command, skill, args): call_plugin (with `--read-only` when this run was
      given it).
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

    def wait(self):
        if not wait_allowed():
            return False
        _waited[0] += WAIT_SECONDS
        self.read(["sleep", str(WAIT_SECONDS)])
        return True

    def wait_budget_item(self):
        return wait_budget_item(self.skill)

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


def refused_result(ctx):
    """The result printed when a read or a write was refused (ReadRefused,
    WriteRefused): `failed`, REFUSED_SENTENCE, then what this run had already written
    (ctx.writes_run), and never the refused command itself."""
    written = getattr(ctx, "writes_run", None)
    if written is None:
        second = REFUSED_UNKNOWN
    elif not written:
        second = REFUSED_NOTHING_WRITTEN
    else:
        second = REFUSED_WRITTEN.format(writes=", ".join("`%s`" % w for w in written))
    return ctx.result("failed", {}, cost=dict(REFUSED_COST), lines=[REFUSED_SENTENCE, second])


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
    ctx = Context(plugin, root, inv.skill, module, mode, inv.args, inv.json,
                  read_only=inv.read_only)
    code = EXIT_OK
    try:
        if inv.repeated:
            result = repeated_result(ctx, inv.repeated)
        elif inv.read_only and mode == "apply":
            result = read_only_refusal(ctx)
        else:
            result = module.run(inv.args, ctx)
    except (ReadRefused, WriteRefused) as e:
        # A bug of the command: loud (exit 70), but never without a result. Neither line
        # shows the refused command's values (the unit tests raise the exception itself,
        # whose message has the command, its hidden values hidden).
        stderr.write("%s: %s: refused, %s\n" % (
            plugin, inv.skill,
            "not a read" if isinstance(e, ReadRefused) else "not an allowed write"))
        stderr.flush()
        result = refused_result(ctx)
        code = EXIT_SOFTWARE
    if not isinstance(result, Result):
        stderr.write("%s: %s returned no Result\n" % (plugin, inv.skill))
        return EXIT_SOFTWARE
    stdout.write(render_json(result) if inv.json else render_answer(result))
    stdout.flush()
    return code
