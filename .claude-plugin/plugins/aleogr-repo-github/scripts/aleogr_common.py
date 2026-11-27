"""Shared module of the aleogr plugin commands.

One copy of this file lives in every plugin, under `scripts/`, and the copies are
byte-identical (a unit test fails when they differ): an installed plugin reaches only
its own files. Change one copy, then copy it over the five others.

It holds what every command needs and nothing of a skill's own rules:

- the command line (`<command> [--json] <skill> [key=value ...]`,
  `<command> --has <skill> [mode]`) and the dispatch to `scripts/skills/<module>.py`;
- `key=value` arguments;
- a runner that shows a provider command on stderr, then runs it, and returns its exit
  code, stdout and stderr; and a READ-ONLY runner that refuses, before running it, any
  provider command that is not on the allowlist of reads (`READS` below);
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

sys.dont_write_bytecode = True

# ---------------------------------------------------------------------------
# Exit codes and errors

EXIT_OK = 0  # a result was produced, whatever its status (failed included)
EXIT_USAGE = 2  # bad usage: unknown option, malformed argument, unknown skill
EXIT_NOT_CONVERTED = 64  # the skill, or this mode of it, is not converted
EXIT_SOFTWARE = 70  # a bug of the command: a refused read, an unexpected exception

PROVIDER_TOOLS = ("gcloud", "gh", "git", "go")


class UsageError(Exception):
    """Bad usage of a command (exit 2)."""


class ReadRefused(Exception):
    """A command that is not a read was given to the read-only runner.

    It is raised before anything runs. It is a bug of the skill's code, never a state
    of the provider: the dispatcher prints it on stderr and exits 70, with no result.
    """

    def __init__(self, argv, reason):
        self.argv = list(argv)
        self.reason = reason
        super().__init__("refused, not a read: %s (%s)" % (show_command(argv), reason))


# ---------------------------------------------------------------------------
# Arguments

_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_SKILL = re.compile(r"^[a-z][a-z0-9_-]*$")


def parse_args(tokens):
    """Parse `key=value` tokens into a dict (insertion order kept).

    The value is everything after the first `=`, and may be empty or hold more `=`
    (`variables=A=1,B=2`). A token without `=`, a key that is not letters and digits
    starting with a letter, or a key given twice is a UsageError.
    """
    args = {}
    for token in tokens:
        key, sep, value = token.partition("=")
        if not sep:
            raise UsageError("argument is not key=value: %s" % token)
        if not _KEY.match(key):
            raise UsageError("bad argument name: %s" % key)
        if key in args:
            raise UsageError("argument given twice: %s" % key)
        args[key] = value
    return args


def format_args(args):
    """The inverse of parse_args: a dict (or list of pairs) as `key=value` tokens."""
    items = args.items() if isinstance(args, dict) else args
    return ["%s=%s" % (k, "" if v is None else v) for k, v in items]


class Invocation(object):
    """A parsed command line."""

    def __init__(self, skill, args, json_mode=False, has=False, mode=None):
        self.skill = skill
        self.args = args
        self.json = json_mode
        self.has = has
        self.mode = mode


def parse_command_line(argv):
    """Parse the arguments of `<command> ...` (without the command itself).

    `[--json] <skill> [key=value ...]` or `--has <skill> [mode]`. Raises UsageError.
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
    if argv[0] == "--json":
        json_mode = True
        argv = argv[1:]
    if not argv:
        raise UsageError("no skill given")
    skill = argv[0]
    if skill.startswith("-"):
        raise UsageError("unknown option: %s" % skill)
    if not _SKILL.match(skill):
        raise UsageError("bad skill name: %s" % skill)
    return Invocation(skill, parse_args(argv[1:]), json_mode=json_mode)


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
        elif a.startswith("-"):
            pass  # a boolean flag: --paginate, --slurp, -i, --silent, --verbose
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
        ("auth", "status", _no_flags("--show-token", "-t")),
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
        ("ls-remote",),
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


def show_command(argv):
    return " ".join(shlex.quote(a) for a in argv)


def run(argv, timeout=None, cwd=None, env=None, stream=None):
    """Show `argv` on stderr (`+ <command>`), then run it and return Completed.

    Nothing of the command's output is printed. stdin is closed. A command that is
    not found returns exit 127 with empty output, as a shell does.
    """
    argv = [str(a) for a in argv]
    stream = stream or sys.stderr
    stream.write("+ %s\n" % show_command(argv))
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
    argv = [str(a) for a in argv]
    why = read_refusal(argv)
    if why:
        raise ReadRefused(argv, why)
    return run(argv, timeout=timeout, cwd=cwd, env=env, stream=stream)


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


def call_plugin(command, skill, args=None, timeout=None):
    """Run `<command> --json <skill> key=value ...`, the command found on PATH.

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
    argv = [path, "--json", skill] + format_args(args or {})
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

    def __init__(self, block, lines=(), data=None):
        self.block = block
        self.lines = list(lines)
        self.data = data

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
            out.append("%s%s: {" % (pad, key))
            out.extend(_members(v, indent + 2, ()))
            out.append("%s}%s" % (pad, comma))
        else:
            out.append("%s%s: %s%s" % (pad, key, _value(v, indent), comma))
    return out


def render_block(block, expand=("outputs",)):
    """The result object laid out as the skills print it: one top-level key per line,
    `outputs` one key per line, a list of objects one object per line, every other
    value on one line (`{ "a": 1 }`, `["x", "y"]`, `[]`, `{}`)."""
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
    return text + "```aleogr-result\n" + render_block(result.block) + "\n```\n"


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

    - ctx.read(argv): the read-only runner (always).
    - ctx.run(argv): the runner; read-only too unless the skill module sets
      WRITES = True and the mode is not in its READ_ONLY_MODES (default ("plan",)).
    - ctx.call(command, skill, args): call_plugin.
    - ctx.sleep(seconds): the wait, run as the command `sleep` (the tests log it).
    - ctx.result(...), ctx.failed(...): build a Result with the module's FAMILY,
      PROVIDER and ACTION.
    - ctx.plugin_path(*parts), ctx.defaults(): files of this plugin.
    """

    def __init__(self, plugin, root, skill, module, mode, args, json_mode=False):
        self.plugin = plugin
        self.root = root
        self.skill = skill
        self.module = module
        self.mode = mode
        self.args = args
        self.json = json_mode
        writes = bool(getattr(module, "WRITES", False))
        self.read_only = (not writes) or mode in getattr(module, "READ_ONLY_MODES", ("plan",))

    def read(self, argv, timeout=None):
        return run_read(argv, timeout=timeout)

    def run(self, argv, timeout=None):
        if self.read_only:
            return run_read(argv, timeout=timeout)
        return run(argv, timeout=timeout)

    def call(self, command, skill, args=None, timeout=None):
        return call_plugin(command, skill, args, timeout=timeout)

    def sleep(self, seconds):
        return run_read(["sleep", str(int(seconds))])

    def plugin_path(self, *parts):
        return os.path.join(self.root, *parts)

    def defaults(self):
        with open(self.plugin_path("defaults.json"), encoding="utf-8") as f:
            return json.load(f)

    def result(self, status, outputs, resources=(), pending=(), cost=None, lines=(),
               mode=None, **extra):
        m = self.module
        block = result_block(m.FAMILY, m.PROVIDER, m.ACTION, status, outputs,
                             mode=mode or getattr(m, "RESULT_MODE", None) or self.mode,
                             resources=resources, pending=pending, cost=cost, **extra)
        return Result(block, lines)

    def failed(self, lines, outputs, pending=(), cost=None, **extra):
        if isinstance(lines, str):
            lines = [lines]
        return self.result("failed", outputs, pending=pending, cost=cost, lines=lines,
                           **extra)


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
        stderr.write("%s: %s\nusage: %s [--json] <skill> [key=value ...]\n"
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
    ctx = Context(plugin, root, inv.skill, module, mode, inv.args, inv.json)
    try:
        result = module.run(inv.args, ctx)
    except ReadRefused as e:
        stderr.write("%s: %s\n" % (plugin, e))
        return EXIT_SOFTWARE
    if not isinstance(result, Result):
        stderr.write("%s: %s returned no Result\n" % (plugin, inv.skill))
        return EXIT_SOFTWARE
    stdout.write(render_json(result) if inv.json else render_answer(result))
    stdout.flush()
    return EXIT_OK
