"""github_variables-set: which of the given Actions variables (or secrets) a run would
set. Only mode=plan is converted; mode=apply stays in the SKILL.md's prose until step 2.

The specification is skills/github_variables-set/SKILL.md: the same read, the same
comparison and the same result block. examine() holds steps 1 and 2, shared by both
modes; run() holds the plan's answer. Step 2 adds step 3 (the sets).

No value is ever printed: the answer and the block name variables only.
"""

import importlib.util
import os
import re
import sys

FAMILY = "repo"
PROVIDER = "github"
ACTION = "variables-set"
UNCONVERTED_MODES = ("apply",)
DEFAULT_MODE = "plan"


def _shared():
    name = "aleogr_repo_github_shared"
    if name not in sys.modules:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_repo_github.py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


G = _shared()

_VAR_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_VALUE_BREAKERS = (",", '"', "`", "$", "\\")

NOT_FOUND = "The repository %s was not found, or this account cannot see it; nothing was set."
READ_REFUSED = {
    "variables": ("The repository's Actions variables could not be read; nothing was set. "
                  "Check that gh is signed in, may read the repository's variables, and that "
                  "GitHub answers, then run this skill again."),
    "secrets": ("The repository's Actions secrets could not be read; nothing was set. Check "
                "that gh is signed in, may read the repository's secrets, and that GitHub "
                "answers, then run this skill again."),
}


def parse_variables(value, word):
    """([(NAME, value)] sorted by name, None) or (None, the sentence). The sentence names
    a variable, never its value."""
    entries = value.split(",")
    out = []
    for entry in entries:
        if entry == "":
            return None, "variables is not valid: it has an empty entry."
        if "=" not in entry:
            return None, ("variables is not valid: an entry has no =; each entry is "
                          "<NAME>=<value>.")
        name, v = entry.split("=", 1)
        if not _VAR_NAME.match(name):
            return None, ("variables is not valid: the %s name %s must be A-Z, 0-9 and _, "
                          "start with a letter, at most 64 characters." % (word, name))
        if name.startswith("GITHUB_"):
            return None, ("variables is not valid: the %s name %s starts with GITHUB_, which "
                          "GitHub reserves." % (word, name))
        if any(n == name for n, _ in out):
            return None, "variables is not valid: the %s %s is given twice." % (word, name)
        if v == "" or any(ch.isspace() for ch in v) or any(b in v for b in _VALUE_BREAKERS):
            return None, ("variables is not valid: the value of %s must not be empty and must "
                          "have no comma, no whitespace, no \", no backtick, no $ and no \\."
                          % name)
        out.append((name, v))
    return sorted(out, key=lambda p: p[0].encode("utf-8")), None


def validate(args):
    """((kind, variables, replace), None) or (None, the sentence)."""
    problem = G.first_missing(args, ("owner", "name", "variables"))
    if problem:
        return None, problem
    problem = G.owner_name_problem(args)
    if problem:
        return None, problem
    kind = args.get("kind", "variables")
    variables, problem = parse_variables(args["variables"],
                                         "secret" if kind == "secrets" else "variable")
    if problem:
        return None, problem
    if kind not in ("variables", "secrets"):
        return None, "kind is not valid: it must be variables or secrets."
    if "replace" in args:
        if args["replace"] not in ("yes", "no"):
            return None, "replace is not valid: it must be yes or no."
        if kind != "secrets":
            return None, "replace is not valid: it is given only with kind=secrets."
    problem = G.mode_problem(args)
    if problem:
        return None, problem
    return (kind, variables, args.get("replace") == "yes"), None


def outputs(to_set=(), already=()):
    return {"set": list(to_set), "already": list(already)}


class Found(object):
    """What steps 1 and 2 found: the names to set and those already as given, sorted."""

    def __init__(self, to_set, already):
        self.to_set = to_set
        self.already = already


def examine(args, ctx, reader, kind, variables, replace):
    """Steps 1 and 2. A Found, or a Result (failed)."""
    full = "%s/%s" % (args["owner"], args["name"])

    def failed(lines):
        return ctx.result("failed", outputs(), cost=G.NO_COST, lines=lines)

    # Step 1: one read of the variables (or of the secrets' names).
    if kind == "secrets":
        argv = ["gh", "secret", "list", "--repo", full, "--json", "name"]
    else:
        argv = ["gh", "variable", "list", "--repo", full, "--json", "name,value"]
    c = reader.gh(argv)
    first = G.gh_first_read_failure(c)
    if first:
        return failed([first] + reader.notes)
    if G.http(c, 404):
        return failed([NOT_FOUND % full] + reader.notes)
    listed = G.json_of(c.out) if c.ok else None
    well_formed = isinstance(listed, list) and all(
        isinstance(x, dict) and isinstance(x.get("name"), str)
        and (kind == "secrets" or "value" in x) for x in listed)
    if not well_formed:
        return failed([READ_REFUSED[kind]])  # repeat no word of gh's answer

    # Step 2: compare by name; the names not given are ignored.
    held = dict((x["name"], x.get("value")) for x in listed)
    to_set, already = [], []
    for name, value in variables:
        if kind == "secrets":
            is_already = (name in held) and not replace
        else:
            is_already = name in held and isinstance(held[name], str) and held[name] == value
        (already if is_already else to_set).append(name)
    return Found(to_set, already)


def run(args, ctx):
    parsed, problem = validate(args)
    if problem:
        return ctx.failed(problem, outputs(), cost=G.NO_COST)
    kind, variables, replace = parsed
    reader = G.Reader(ctx)
    found = examine(args, ctx, reader, kind, variables, replace)
    if not isinstance(found, Found):
        return found
    resources = [G.repository_resource(args["owner"], args["name"])]
    secrets = kind == "secrets"
    lines = []
    if not found.to_set:
        status = "unchanged"
        if secrets:
            lines.append("Every given secret already exists and is left alone: %s."
                         % ", ".join(found.already))
        else:
            lines.append("Every given variable already holds the given value: %s."
                         % ", ".join(found.already))
        out = outputs((), found.already)
    else:
        status = "would-update"
        lines.append("apply would set these %s: %s." % ("secrets" if secrets else "variables",
                                                       ", ".join(found.to_set)))
        if found.already:
            if secrets:
                lines.append("These secrets already exist and would be left alone: %s."
                             % ", ".join(found.already))
            else:
                lines.append("These variables already hold the given value: %s."
                             % ", ".join(found.already))
        out = outputs(found.to_set, found.already)
    if secrets:
        lines.append("A secret's value cannot be read back: only its name is compared.")
    return ctx.result(status, out, resources=resources, cost=G.NO_COST,
                      lines=lines + reader.notes)
