"""github_repo-configure: corrects the given settings and the visibility of an existing
GitHub repository and verifies them (mode=apply), or says what a run would change
(mode=plan). Only the settings given as arguments are compared and changed.

The specification is skills/github_repo-configure/SKILL.md: the same read (step 1), the
same comparison (step 2), the same settings command (step 4), the same visibility command
after it (step 5) and the same verification (step 6), each at most once, and the same
result block. The writes run through the writing runner only (Reader.write, then
ctx.write), so only in mode=apply.
"""

import importlib.util
import json
import os
import re
import sys

sys.dont_write_bytecode = True

FAMILY = "repo"
PROVIDER = "github"
ACTION = "repo-configure"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply changes the repository, through ctx.write only


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
common = G.common

_TOPIC = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")

# The settings, in the order of the table of step 2: (argument, key read, flag of step 4).
BOOLEANS = (
    ("mergeCommit", "allow_merge_commit", "--enable-merge-commit"),
    ("squash", "allow_squash_merge", "--enable-squash-merge"),
    ("rebase", "allow_rebase_merge", "--enable-rebase-merge"),
    ("deleteBranchOnMerge", "delete_branch_on_merge", "--delete-branch-on-merge"),
    ("issues", "has_issues", "--enable-issues"),
    ("wiki", "has_wiki", "--enable-wiki"),
    ("projects", "has_projects", "--enable-projects"),
)
# The settings, in the order of the table: description, topics, the booleans, visibility.
SETTINGS = ("description", "topics") + tuple(b[0] for b in BOOLEANS) + ("visibility",)
MERGE_METHODS = ("mergeCommit", "squash", "rebase")

PRIVATE_COST = ("private repositories of a free organization use the 2,000 Actions minutes "
                "a month")

NOTHING_GIVEN = "Nothing to configure was given."
TOPICS_RULE = ("topics is not valid: each topic must have 1 to 50 characters of a-z, 0-9 "
               "and -, and start with a letter or a digit (no capitals, no _, no spaces, no "
               "empty item).")
VISIBILITY_RULE = "visibility is not valid: it must be public or private."
CONFIRM_RULE = ("confirmVisibility is not valid: it must be public or private, visibility "
                "must be given, and the two must be equal.")
MERGE_RULE = ("mergeCommit, squash and rebase are not valid: they are all false, and at "
              "least one merge method must stay on.")
MERGE_READ = ("At least one merge method must stay on: with the values read from GitHub, "
              "merge commits, squash merging and rebase merging would all be off; nothing "
              "was changed.")

QUESTIONS = {
    "public": "Make `%s` PUBLIC? Its whole history becomes visible.",
    "private": "Make `%s` PRIVATE? Branch protection stops being enforced on the free plan.",
}


# ---------------------------------------------------------------------------
# Arguments


def parse_topics(value):
    """([] for `topics=`, or the topics, repeated ones once, in the given order, None),
    or (None, the sentence)."""
    if value == "":
        return [], None
    out = []
    for t in value.split(","):
        if not _TOPIC.match(t):
            return None, TOPICS_RULE
        if t not in out:
            out.append(t)
    return out, None


def validate(args):
    """(wanted, None) or (None, the sentence). `wanted` maps each given setting to its
    value (a str, a list of topics, or a bool), in the order of the table of step 2."""
    problem = G.first_missing(args, ("owner", "name"))
    if problem:
        return None, problem
    if not any(s in args for s in SETTINGS):
        return None, NOTHING_GIVEN
    problem = G.owner_name_problem(args)
    if problem:
        return None, problem
    if "description" in args:
        problem = G.free_text_problem("description", args["description"])
        if problem:
            return None, problem
    topics = None
    if "topics" in args:
        topics, problem = parse_topics(args["topics"])
        if problem:
            return None, problem
    for key, _, _ in BOOLEANS:
        if key in args and args[key] not in ("true", "false"):
            return None, "%s is not valid: it must be true or false." % key
    if "visibility" in args and args["visibility"] not in ("public", "private"):
        return None, VISIBILITY_RULE
    if "confirmVisibility" in args:
        if (args["confirmVisibility"] not in ("public", "private")
                or "visibility" not in args
                or args["confirmVisibility"] != args["visibility"]):
            return None, CONFIRM_RULE
    if all(args.get(k) == "false" for k in MERGE_METHODS):
        return None, MERGE_RULE
    problem = G.mode_problem(args)
    if problem:
        return None, problem
    wanted = []
    for s in SETTINGS:
        if s not in args:
            continue
        if s == "topics":
            wanted.append((s, topics))
        elif s in ("description", "visibility"):
            wanted.append((s, args[s]))
        else:
            wanted.append((s, args[s] == "true"))
    return wanted, None


# ---------------------------------------------------------------------------
# What was read


def _text(v):
    return v if isinstance(v, str) else None


def _flag(v):
    return v if isinstance(v, bool) else None


def _topics_of(repo):
    t = repo.get("topics")
    return sorted(x for x in t if isinstance(x, str)) if isinstance(t, list) else []


def state_of(repo):
    """The values of the settings, as read: {setting: value}."""
    state = {"description": _text(repo.get("description")) or None,
             "topics": _topics_of(repo),
             "visibility": _text(repo.get("visibility"))}
    for key, read, _ in BOOLEANS:
        state[key] = _flag(repo.get(read))
    return state


def outputs_of(state, changes=()):
    return {
        "changes": list(changes),
        "settings": dict((key, state[key]) for key, _, _ in BOOLEANS),
        "visibility": state["visibility"],
        "description": state["description"],
        "topics": sorted(state["topics"]),
    }


def failed_outputs():
    return {"changes": [], "settings": None, "visibility": None, "description": None,
            "topics": []}


def cost_of(outputs):
    v = outputs.get("visibility")
    if v is None:
        return {"fixed": False, "notes": "no cost: nothing was changed"}
    if v == "public":
        return {"fixed": False, "notes": "no cost"}
    return {"fixed": False, "notes": PRIVATE_COST}


def differs(setting, want, repo, state):
    """Step 2's rule for one setting. `repo` is the JSON read (for the exact description:
    an empty one is not equal to a given text either)."""
    if setting == "description":
        return repo.get("description") != want
    if setting == "topics":
        return set(want) != set(state["topics"])
    if setting == "visibility":
        return state["visibility"] != want
    return state[setting] is None or state[setting] != want


def compare(wanted, repo):
    """The differences, as changes {setting, from, to}, in the order of the table."""
    state = state_of(repo)
    changes = []
    for setting, want in wanted:
        if differs(setting, want, repo, state):
            if setting == "topics":
                frm, to = sorted(state["topics"]), sorted(want)
            elif setting == "description":
                frm, to = repo.get("description") if "description" in repo else None, want
            else:
                frm, to = state[setting], want
            changes.append({"setting": setting, "from": frm, "to": to})
    return changes


# ---------------------------------------------------------------------------
# Commands


def settings_command(full, changes, read_topics):
    """Step 4: one command with only the flags of the settings that differ, in the order
    the SKILL.md writes them; never --visibility."""
    by = dict((c["setting"], c["to"]) for c in changes)
    argv = ["gh", "repo", "edit", full]
    if "description" in by:
        argv += ["--description", by["description"]]
    for key, _, flag in BOOLEANS:
        if key in by:
            argv.append("%s=%s" % (flag, "true" if by[key] else "false"))
    if "topics" in by:
        wanted = by["topics"]
        for t in wanted:
            if t not in read_topics:
                argv += ["--add-topic", t]
        for t in read_topics:
            if t not in wanted:
                argv += ["--remove-topic", t]
    return argv


def visibility_command(full, value):
    """Step 5, in its own command."""
    return ["gh", "repo", "edit", full, "--visibility", value,
            "--accept-visibility-change-consequences"]


def shown_command(argv):
    """A command as the SKILL.md writes it: the description in double quotes."""
    out = []
    quote_next = False
    for a in argv:
        out.append('"%s"' % a if quote_next else a)
        quote_next = (not quote_next) and a == "--description"
    return " ".join(out)


def how_configure(owner, name, extra):
    return " ".join(["/aleogr-repo-github:github_repo-configure", "owner=%s" % owner,
                     "name=%s" % name] + extra + ["mode=apply"])


def as_argument(setting, value):
    """`<setting>=<value>` for a suggested command, quoted as the SKILL.md writes it."""
    if setting == "description":
        return 'description="%s"' % value
    if setting == "topics":
        return 'topics="%s"' % ",".join(value)
    if isinstance(value, bool):
        return "%s=%s" % (setting, "true" if value else "false")
    return "%s=%s" % (setting, value)


def _value(v):
    return json.dumps(v, ensure_ascii=False)


def change_text(c):
    return "%s (%s to %s)" % (c["setting"], _value(c["from"]), _value(c["to"]))


def _edit_cause(c, what):
    """The cause of a refused `gh repo edit`, in a few words of our own (never its text)."""
    t = c.text.lower()
    if G.not_installed(c):
        return "gh could not be started"
    if G.not_logged_in(c):
        return "gh is not logged in"
    if "rate limit" in t or "http 429" in t:
        return "the GitHub API rate limit was reached"
    if ("http 403" in t or "forbidden" in t or "admin" in t or "not accessible" in t
            or "permission" in t):
        return "this account is not allowed to change %s (it needs admin rights)" % what
    if "http 422" in t:
        return "GitHub did not accept the change"
    if re.search(r"http 5[0-9][0-9]", t):
        return "GitHub answered with an error of its own"
    if any(w in t for w in ("could not resolve", "no such host", "connection refused",
                            "timed out", "timeout", "dial tcp", "network is unreachable",
                            "connection reset", "tls")):
        return "GitHub could not be reached"
    return "gh failed"


# ---------------------------------------------------------------------------


def run(args, ctx):
    wanted, problem = validate(args)
    if problem:
        return ctx.failed(problem, failed_outputs(), cost=cost_of(failed_outputs()))
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    reader = G.Reader(ctx)
    resources = [G.repository_resource(owner, name)]

    def failed(lines):
        out = failed_outputs()
        return ctx.result("failed", out, cost=cost_of(out), lines=lines + reader.notes)

    # Step 1: read the repository.
    c = reader.gh(["gh", "api", "repos/%s" % full])
    first = G.gh_first_read_failure(c)
    if first:
        return failed([first])
    if G.http(c, 404):
        return failed(["The repository %s does not exist, or this account cannot see it; "
                       "github_repo-create creates it first." % full])
    if not c.ok:
        return failed(["The repository %s could not be read: %s; nothing was changed."
                       % (full, G.gh_cause(c))])
    repo = G.json_of(c.out)
    if not isinstance(repo, dict):
        return failed(["The repository %s could not be read: gh did not give a JSON object; "
                       "nothing was changed." % full])
    state = state_of(repo)
    given = dict(wanted)

    def ended(status, lines, changes=(), pending=(), out_state=None):
        out = outputs_of(out_state or state, changes)
        return ctx.result(status, out, resources=resources, pending=pending,
                          cost=cost_of(out), lines=lines + reader.notes)

    # Step 2: compare.
    changes = compare(wanted, repo)
    resulting = [given[k] if k in given else state[k] for k in MERGE_METHODS]
    if all(v is False for v in resulting):
        return ended("failed", [MERGE_READ])
    if not changes:
        return ended("unchanged", ["Every given setting of %s already has the given value; "
                                   "nothing was changed." % full])

    others = [ch for ch in changes if ch["setting"] != "visibility"]
    vis = [ch for ch in changes if ch["setting"] == "visibility"]
    target = vis[0]["to"] if vis else None
    commands = []
    if others:
        commands.append(settings_command(full, others, state["topics"]))
    if vis:
        commands.append(visibility_command(full, target))

    # Step 3: plan.
    if args.get("mode") != "apply":
        lines = ["apply would change these settings of %s: %s."
                 % (full, ", ".join(change_text(ch) for ch in changes)),
                 "apply would run %s:" % ("these commands" if len(commands) > 1
                                          else "this command")]
        lines += G.shown([shown_command(a) for a in commands])
        if vis:
            lines.append("The visibility change needs confirmVisibility=%s (or the owner's "
                         "answer) in apply." % target)
            if target == "private":
                lines.append("Once the repository is private, branch protection stops being "
                             "enforced on the free plan.")
        return ended("would-update", lines, changes)

    # Step 4: apply the settings other than the visibility, in one command.
    lines, pending, done = [], [], []
    edited = False
    if others:
        c = reader.write(commands[0])
        if not c.ok:
            return ended("failed", ["The settings of %s were not changed: %s; nothing was "
                                    "changed." % (full, _edit_cause(c, "its settings"))])
        edited = True
        done += others

    # Step 5: the visibility, in its own command, after step 4.
    visibility_changed = False
    if vis:
        how = how_configure(owner, name, ["visibility=%s" % target,
                                          "confirmVisibility=%s" % target])
        if args.get("confirmVisibility") != target:
            pending.append(G.pending_item("confirm visibility %s" % target, how))
            question = QUESTIONS[target] % full
            if not edited:
                return ended("pending", [question, "Nothing was changed: the visibility "
                                         "waits for the confirmation."], pending=pending)
            lines.append(question)
        else:
            c = reader.write(visibility_command(full, target))
            if c.ok:
                visibility_changed = True
                edited = True
                done += vis
            elif not edited:
                return ended("failed", ["The visibility of %s was not changed: %s; nothing "
                                        "was changed." % (full, _edit_cause(c, "its "
                                                                           "visibility"))])
            else:
                lines.append("The visibility of %s was not changed: %s."
                             % (full, _edit_cause(c, "its visibility")))
                pending.append(G.pending_item("visibility", how))

    # Step 6: verify, once.
    c = reader.gh(["gh", "api", "repos/%s" % full])
    after = G.json_of(c.out) if c.ok else None
    if not isinstance(after, dict):
        final = dict(state)
        for ch in done:
            final[ch["setting"]] = ch["to"]
        lines.append("The repository could not be read back to verify the change.")
        pending.append(G.pending_item("verify", "/aleogr-repo-github:github_repo-describe "
                                                "owner=%s name=%s" % (owner, name)))
    else:
        final = state_of(after)
        checked = [(s, v) for s, v in wanted if s != "visibility" or visibility_changed]
        still = compare(checked, after)
        if still:
            lines.append("After the change, these settings still differ: %s."
                         % ", ".join(change_text(ch) for ch in still))
            pending.append(G.pending_item("configure", how_configure(
                owner, name, [as_argument(ch["setting"], ch["to"]) for ch in still])))
            left = set(ch["setting"] for ch in still)
            done = [ch for ch in done if ch["setting"] not in left]
    changed = [ch for ch in changes if ch in done]
    head = ("These settings of %s were changed: %s." % (full, ", ".join(change_text(ch)
                                                                         for ch in changed))
            if changed else "A change was sent to %s, but the verification does not show it."
            % full)
    lines.insert(0, head)
    if pending:
        lines.append("Left in pending: %s." % ", ".join(p["item"] for p in pending))
    return ended("updated", lines, changed, pending, final)
