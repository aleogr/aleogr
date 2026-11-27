"""Rules shared by the skills of aleogr-repo-github. Not a skill: no SKILL.md names it,
and its name cannot be a skill's (a skill's name starts with a letter).

A skill module loads it from its own folder by its file (see _shared() in each module),
under the name `aleogr_repo_github_shared`, so that it works both under the plugin's
command (package `skills`) and under the unit tests (which load each module from its
file).

Each rule here is written once in the SKILL.md files of the plugin, word for word the
same in each: the names of `owner` and `name`, the cases of a `gh` answer (not
installed, not logged in, HTTP 404, any other failure), the rule that the text decides
when an exit 0 comes with an error line, the address of `origin`, the comparison of
JSON values.
"""

import json
import re
import sys

sys.dont_write_bytecode = True

import aleogr_common as common  # noqa: E402  (scripts/ is on sys.path)

# ---------------------------------------------------------------------------
# Arguments

_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

OWNER_RULE = ("%s is not valid: it must have 1 to 39 characters of A-Z, a-z, 0-9 and -, "
              "and must not start or end with -.")
NAME_RULE = ("%s is not valid: it must have 1 to 100 characters of A-Z, a-z, 0-9, ., _ "
             "and -, and must not be . or .. alone.")

# The characters that could break out of the double quotes of a command.
QUOTE_BREAKERS = ('"', "“", "”", "„", "`", "$", "\\")


def owner_ok(v):
    return bool(_OWNER.match(v or ""))


def name_ok(v):
    return bool(_NAME.match(v or "")) and v not in (".", "..")


def owner_name_problem(args):
    """The sentence of the first rule `owner` or `name` breaks, or None. Both given."""
    if not owner_ok(args["owner"]):
        return OWNER_RULE % "owner"
    if not name_ok(args["name"]):
        return NAME_RULE % "name"
    return None


def first_missing(args, keys):
    """The sentence `<key> is missing.` for the first key absent or empty, or None."""
    for k in keys:
        if not args.get(k):
            return "%s is missing." % k
    return None


def free_text_problem(key, value, max_len=None):
    """A free text written in double quotes: not empty, at most max_len characters, no
    line break, none of QUOTE_BREAKERS. The sentence, or None."""
    if value == "" or "\n" in value or "\r" in value or any(c in value
                                                            for c in QUOTE_BREAKERS):
        what = "must not be empty" if max_len is None else (
            "must have 1 to %d characters" % max_len)
        return ("%s is not valid: it %s, and have no line break, no double quote of any "
                "kind, no backtick, no $ and no \\." % (key, what))
    if max_len is not None and len(value) > max_len:
        return ("%s is not valid: it must have 1 to %d characters, and have no line break, "
                "no double quote of any kind, no backtick, no $ and no \\."
                % (key, max_len))
    return None


def mode_problem(args):
    if "mode" in args and args["mode"] not in ("plan", "apply"):
        return "mode is not valid: it must be plan or apply."
    return None


# ---------------------------------------------------------------------------
# Reading gh and git answers

GH_NOT_INSTALLED = "gh is not installed: install the GitHub CLI (gh), then run this again."
GH_NOT_LOGGED_IN = "gh is not logged in: the fix is gh auth login, then run this again."
GIT_NOT_INSTALLED = "git is not installed: install git, then run this again."
UNTRUSTED = ("The exit code of gh could not be trusted: it reported success next to an "
             "error, so the error was taken as the answer.")

# An error line of gh, such as `gh: Not Found (HTTP 404)`.
_GH_ERROR_LINE = re.compile(r"^gh: .*\(HTTP [0-9]{3}\)\s*$", re.M)


def _gh_error_line(c):
    """gh's own error line: anywhere in stderr, or as the first line of stdout. Never
    further down stdout, which may be a file of the repository read raw."""
    if _GH_ERROR_LINE.search(c.err or ""):
        return True
    first = (c.out or "").lstrip().split("\n", 1)[0]
    return bool(_GH_ERROR_LINE.search(first))


class Reader(object):
    """Runs the reads of a skill through ctx.read (always the read-only runner), and its
    writes through ctx.write, and keeps the sentences that the answer adds (an exit code
    that could not be trusted)."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.notes = []

    def gh(self, argv):
        c = self.ctx.read(argv)
        if c.ok and _gh_error_line(c):
            # The text decides: an exit 0 next to an error line is that error.
            if UNTRUSTED not in self.notes:
                self.notes.append(UNTRUSTED)
            c = common.Completed(1, c.out, c.err)
        return c

    def git(self, argv):
        return self.ctx.read(argv)

    def write(self, argv):
        """A write, through ctx.write (the writing runner: only in mode=apply, only the
        shapes of the skill's allowlist of writes). For gh, the same rule as a read: an
        exit 0 next to gh's error line is that error."""
        c = self.ctx.write(argv)
        if argv and str(argv[0]) == "gh" and c.ok and _gh_error_line(c):
            if UNTRUSTED not in self.notes:
                self.notes.append(UNTRUSTED)
            c = common.Completed(1, c.out, c.err)
        return c


def not_installed(c):
    return (not c.ok) and (c.code in (126, 127) or "command not found" in c.text.lower())


def not_logged_in(c):
    if c.ok:
        return False
    t = c.text.lower()
    return ("gh auth login" in t or "not logged in" in t or "bad credentials" in t
            or "http 401" in t)


def http(c, *codes):
    """A non-zero exit whose text has one of `HTTP <code>`."""
    return (not c.ok) and any(("HTTP %d" % n) in c.text for n in codes)


def gh_cause(c):
    """The cause of a failed gh read, in a few words of our own (never its text)."""
    t = c.text.lower()
    if "rate limit" in t or "http 429" in t:
        return "the GitHub API rate limit was reached"
    if "http 403" in t or "forbidden" in t or "resource not accessible" in t:
        return "this account is not allowed to read it"
    if re.search(r"http 5[0-9][0-9]", t):
        return "GitHub answered with an error of its own"
    if any(w in t for w in ("could not resolve", "no such host", "connection refused",
                            "timed out", "timeout", "dial tcp", "network is unreachable",
                            "connection reset", "tls")):
        return "GitHub could not be reached"
    return "gh failed"


def git_cause(c):
    t = c.text.lower()
    if c.code in (126, 127) or "command not found" in t:
        return "git is not installed"
    if "not a git repository" in t:
        return "this folder is not a git checkout"
    if "dubious ownership" in t:
        return "git does not trust this folder's owner"
    return "git failed"


def gh_first_read_failure(c):
    """The first two cases of every first gh read: gh not installed, not logged in.
    The sentence, or None."""
    if not_installed(c):
        return GH_NOT_INSTALLED
    if not_logged_in(c):
        return GH_NOT_LOGGED_IN
    return None


def json_of(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def is_sha(v):
    return isinstance(v, str) and re.match(r"^[0-9a-f]{40}$", v) is not None


def origin_matches(out, owner, name):
    """`git remote get-url origin` names https://github.com/<owner>/<name>, ignoring
    letter case and a trailing `.git` or `/`."""
    u = (out or "").strip().lower()
    while True:
        if u.endswith("/"):
            u = u[:-1]
        elif u.endswith(".git"):
            u = u[:-4]
        else:
            break
    return u == ("https://github.com/%s/%s" % (owner, name)).lower()


# ---------------------------------------------------------------------------
# JSON values and local files


def json_equal(a, b):
    """Two JSON values are equal: key order ignored, lists in order, a boolean never
    equal to a number."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, dict):
        return (isinstance(b, dict) and set(a) == set(b)
                and all(json_equal(a[k], b[k]) for k in a))
    if isinstance(a, list):
        return (isinstance(b, list) and len(a) == len(b)
                and all(json_equal(x, y) for x, y in zip(a, b)))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and a == b


def read_local(path):
    """The text of a file of the current folder: (text, None), or (None, "missing") when
    it does not exist, or (None, "unreadable")."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except (FileNotFoundError, NotADirectoryError):
        return None, "missing"
    except OSError:
        return None, "unreadable"
    return data.decode("utf-8", "replace"), None


def first_line(text):
    """The first line of a text, with a trailing carriage return removed."""
    line = text.split("\n", 1)[0]
    return line[:-1] if line.endswith("\r") else line


def pending_item(item, how):
    return {"item": item, "reason": "manual", "how": how}


def repository_resource(owner, name):
    return {"type": "repository", "id": "%s/%s" % (owner, name), "name": name}


NO_COST = {"fixed": False, "notes": "no cost"}

# The two commands with git's credential through gh, as the skills write them.
CREDENTIAL = ["-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential"]
CREDENTIAL_SHOWN = "git -c credential.helper= -c 'credential.helper=!gh auth git-credential'"


def shown(lines):
    """Commands shown, not run, in the answer: one per line, indented as code."""
    return ["    " + line for line in lines]
