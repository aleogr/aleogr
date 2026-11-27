"""github_repo-create: creates a GitHub repository with a README, an optional
description and optional topics, and verifies it (mode=apply), or says what a run would
do (mode=plan). An existing repository is never changed.

The specification is skills/github_repo-create/SKILL.md: the same read (step 1), the same
comparison (step 2), the same stop for a public repository (step 3), the same create
(step 4), the same topics command (step 5) and the same verification (step 6), in that
order, each at most once, and the same result block. The writes run through the writing
runner only (Reader.write, then ctx.write), so only in mode=apply.
"""

import importlib.util
import os
import re
import sys

sys.dont_write_bytecode = True

FAMILY = "repo"
PROVIDER = "github"
ACTION = "repo-create"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply creates the repository, through ctx.write only


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

# The arguments of this skill, in the order of its table (for the `how` of an item).
KNOWN_ARGS = ("owner", "name", "visibility", "confirmVisibility", "description", "topics",
              "mode")

PRIVATE_COST = ("private repositories of a free organization use the 2,000 Actions minutes "
                "a month")
NOTHING_CREATED_COST = {"fixed": False, "notes": "no cost: nothing was created"}

TOPICS_RULE = ("topics is not valid: each topic must have 1 to 50 characters of a-z, 0-9 "
               "and -, and start with a letter or a digit (no capitals, no _, no spaces, no "
               "empty item).")
VISIBILITY_RULE = "visibility is not valid: it must be public or private."
CONFIRM_RULE = ("confirmVisibility is not valid: it is given only as confirmVisibility=public, "
                "with visibility=public.")


# ---------------------------------------------------------------------------
# Arguments


def parse_topics(value):
    """(the topics, repeated ones once, in the given order, None) or (None, the sentence)."""
    out = []
    for t in value.split(","):
        if not _TOPIC.match(t):
            return None, TOPICS_RULE
        if t not in out:
            out.append(t)
    return out, None


def validate(args):
    """((visibility, topics or None), None) or (None, the sentence). In the order of the
    SKILL.md: the missing ones, then each rule of its list."""
    problem = G.first_missing(args, ("owner", "name"))
    if problem:
        return None, problem
    problem = G.owner_name_problem(args)
    if problem:
        return None, problem
    if "visibility" in args and args["visibility"] not in ("public", "private"):
        return None, VISIBILITY_RULE
    visibility = args.get("visibility") or "private"
    if "confirmVisibility" in args:
        if args["confirmVisibility"] != "public" or visibility != "public":
            return None, CONFIRM_RULE
    if "description" in args:
        problem = G.free_text_problem("description", args["description"])
        if problem:
            return None, problem
    topics = None
    if "topics" in args:
        topics, problem = parse_topics(args["topics"])
        if problem:
            return None, problem
    problem = G.mode_problem(args)
    if problem:
        return None, problem
    return (visibility, topics), None


# ---------------------------------------------------------------------------
# Outputs


def _text(v):
    return v if isinstance(v, str) else None


def _topics_of(repo):
    t = repo.get("topics")
    return sorted(x for x in t if isinstance(x, str)) if isinstance(t, list) else []


def outputs_of(repo, differences=()):
    """outputs from a read of the repository (a JSON object)."""
    return {
        "url": _text(repo.get("html_url")),
        "sshUrl": _text(repo.get("ssh_url")),
        "visibility": _text(repo.get("visibility")),
        "defaultBranch": _text(repo.get("default_branch")),
        "topics": _topics_of(repo),
        "differences": list(differences),
    }


def failed_outputs():
    return {"url": None, "sshUrl": None, "visibility": None, "defaultBranch": None,
            "topics": [], "differences": []}


def planned_outputs(visibility, topics):
    return {"url": None, "sshUrl": None, "visibility": visibility, "defaultBranch": None,
            "topics": sorted(topics or []), "differences": []}


def built_outputs(owner, name, visibility):
    """outputs of `created` when the verification did not exit 0: from the arguments."""
    return {"url": "https://github.com/%s/%s" % (owner, name),
            "sshUrl": "git@github.com:%s/%s.git" % (owner, name),
            "visibility": visibility, "defaultBranch": None, "topics": [],
            "differences": []}


def cost_of(outputs):
    if outputs.get("visibility") == "public":
        return {"fixed": False, "notes": "no cost"}
    return {"fixed": False, "notes": PRIVATE_COST}


# ---------------------------------------------------------------------------
# Commands


def create_command(full, visibility, description):
    """Step 4, as the SKILL.md writes it."""
    argv = ["gh", "repo", "create", full,
            "--public" if visibility == "public" else "--private", "--add-readme"]
    if description is not None:
        argv += ["--description", description]
    return argv


def topics_command(full, topics):
    """Step 5: one `--add-topic` flag per topic."""
    argv = ["gh", "repo", "edit", full]
    for t in topics:
        argv += ["--add-topic", t]
    return argv


def shown_command(argv):
    """A command as the SKILL.md writes it, for the answer: the description in double
    quotes."""
    out = []
    quote_next = False
    for a in argv:
        if quote_next:
            out.append('"%s"' % a)
            quote_next = False
        else:
            out.append(a)
            quote_next = a == "--description"
    return " ".join(out)


def _arg(key, value):
    """`key=value`, in double quotes when the value has a comma or a space."""
    if "," in value or " " in value:
        return '%s="%s"' % (key, value)
    return "%s=%s" % (key, value)


def configure_how(owner, name, extra):
    """`/aleogr-repo-github:github_repo-configure owner=<owner> name=<name> ... mode=apply`."""
    return " ".join(["/aleogr-repo-github:github_repo-configure", "owner=%s" % owner,
                     "name=%s" % name] + extra + ["mode=apply"])


def _write_cause(c, owner):
    """The cause of a refused create, in a few words of our own (never its text)."""
    t = c.text.lower()
    if G.not_installed(c):
        return "gh could not be started"
    if G.not_logged_in(c):
        return "gh is not logged in"
    if "rate limit" in t or "http 429" in t:
        return "the GitHub API rate limit was reached"
    if ("http 403" in t or "forbidden" in t or "admin access" in t
            or "not accessible" in t or "permission" in t):
        return "this account has no permission to create repositories in %s" % owner
    if "http 422" in t or "already exists" in t or "name already" in t:
        return "GitHub did not accept a repository of this name in %s" % owner
    if re.search(r"http 5[0-9][0-9]", t):
        return "GitHub answered with an error of its own"
    if any(w in t for w in ("could not resolve", "no such host", "connection refused",
                            "timed out", "timeout", "dial tcp", "network is unreachable",
                            "connection reset", "tls")):
        return "GitHub could not be reached"
    return "gh failed"


def _edit_cause(c):
    t = c.text.lower()
    if "rate limit" in t or "http 429" in t:
        return "the GitHub API rate limit was reached"
    if ("http 403" in t or "forbidden" in t or "not accessible" in t or "admin" in t
            or "permission" in t):
        return "this account is not allowed to change the repository's topics"
    if re.search(r"http 5[0-9][0-9]", t):
        return "GitHub answered with an error of its own"
    if any(w in t for w in ("could not resolve", "no such host", "connection refused",
                            "timed out", "timeout", "dial tcp", "network is unreachable",
                            "connection reset", "tls")):
        return "GitHub could not be reached"
    return "gh failed"


def _list(values):
    return ", ".join(values) if values else "none"


def _quoted(v):
    return "none" if v is None else '"%s"' % v


# ---------------------------------------------------------------------------


def run(args, ctx):
    parsed, problem = validate(args)
    if problem:
        return ctx.failed(problem, failed_outputs(), cost=dict(NOTHING_CREATED_COST))
    visibility, topics = parsed
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    description = args.get("description")
    reader = G.Reader(ctx)

    def failed(lines):
        return ctx.result("failed", failed_outputs(), cost=dict(NOTHING_CREATED_COST),
                          lines=lines + reader.notes)

    # Step 1: read the repository.
    c = reader.gh(["gh", "api", "repos/%s" % full])
    first = G.gh_first_read_failure(c)
    if first:
        return failed([first])
    if not G.http(c, 404):
        if not c.ok:
            return failed(["The repository %s could not be read: %s; nothing was created."
                           % (full, G.gh_cause(c))])
        repo = G.json_of(c.out)
        if not isinstance(repo, dict):
            return failed(["The repository %s could not be read: gh did not give a JSON "
                           "object; nothing was created." % full])
        return existing(ctx, reader, args, owner, name, repo, topics)

    # Step 3: the repository does not exist.
    commands = [create_command(full, visibility, description)]
    if topics:
        commands.append(topics_command(full, topics))
    if args.get("mode") != "apply":
        lines = ["The repository %s does not exist; apply would create it, %s, with a "
                 "README, with %s:" % (full, visibility,
                                       "these commands" if len(commands) > 1
                                       else "this command")]
        lines += G.shown([shown_command(a) for a in commands])
        if visibility == "public" and args.get("confirmVisibility") != "public":
            lines.append("apply creates it public only with confirmVisibility=public.")
        return ctx.result("would-create", planned_outputs(visibility, topics),
                          cost=dict(NOTHING_CREATED_COST), lines=lines + reader.notes)
    if visibility == "public" and args.get("confirmVisibility") != "public":
        how = " ".join(["/aleogr-repo-github:github_repo-create"]
                       + [_arg(k, args[k]) for k in args if k in KNOWN_ARGS]
                       + ["confirmVisibility=public"])
        lines = ["Create `%s` as PUBLIC?" % full,
                 "Nothing was created: to create it public, run this again with "
                 "confirmVisibility=public."]
        return ctx.result("pending", planned_outputs(visibility, topics),
                          pending=[G.pending_item("confirm visibility public", how)],
                          cost=dict(NOTHING_CREATED_COST), lines=lines + reader.notes)

    # Step 4: create the repository.
    c = reader.write(create_command(full, visibility, description))
    if not c.ok:
        return failed(["The repository %s was not created: %s."
                       % (full, _write_cause(c, owner))])
    lines = ["The repository %s was created, %s, with a README." % (full, visibility)]
    pending = []

    # Step 5: the topics, in one command.
    topics_item = False
    if topics:
        c = reader.write(topics_command(full, topics))
        if not c.ok:
            topics_item = True
            lines.append("The topics could not be added: %s." % _edit_cause(c))
            pending.append(G.pending_item("topics", configure_how(
                owner, name, ['topics="%s"' % ",".join(topics)])))

    # Step 6: verify, once.
    c = reader.gh(["gh", "api", "repos/%s" % full])
    repo = G.json_of(c.out) if c.ok else None
    if not isinstance(repo, dict):
        outputs = built_outputs(owner, name, visibility)
        lines.append("The new repository could not be read back to verify it.")
        pending.append(G.pending_item("verify", "/aleogr-repo-github:github_repo-describe "
                                                "owner=%s name=%s" % (owner, name)))
    else:
        outputs = outputs_of(repo)
        differ, extra = [], []
        if description is not None and repo.get("description") != description:
            differ.append("the description")
            extra.append('description="%s"' % description)
        missing = [t for t in (topics or []) if t not in outputs["topics"]]
        if missing:
            differ.append("the topics (missing: %s)" % ", ".join(missing))
            if not topics_item:
                extra.append('topics="%s"' % ",".join(topics))
        if repo.get("visibility") != visibility:
            differ.append("the visibility (%s, not %s)"
                          % (_text(repo.get("visibility")) or "unknown", visibility))
            extra.append("visibility=%s" % visibility)
        if differ:
            lines.append("The verification found these differences from the arguments: "
                         "%s." % "; ".join(differ))
        if extra:
            pending.append(G.pending_item("configure", configure_how(owner, name, extra)))
    lines.append(_where(outputs))
    if pending:
        lines.append("Left in pending: %s." % ", ".join(p["item"] for p in pending))
    return ctx.result("created", outputs,
                      resources=[G.repository_resource(owner, name)], pending=pending,
                      cost=cost_of(outputs), lines=lines + reader.notes)


def _where(outputs):
    return ("URL %s, visibility %s, default branch %s."
            % (outputs["url"] or "unknown", outputs["visibility"] or "unknown",
               outputs["defaultBranch"] or "not known"))


def existing(ctx, reader, args, owner, name, repo, topics):
    """Step 2: the repository exists. Nothing is changed, in plan and in apply."""
    full = "%s/%s" % (owner, name)
    found = outputs_of(repo)
    differences, said = [], []
    if "visibility" in args and found["visibility"] != args["visibility"]:
        differences.append("visibility")
        said.append("visibility: asked %s, found %s."
                    % (args["visibility"], found["visibility"] or "none"))
    if "description" in args and repo.get("description") != args["description"]:
        differences.append("description")
        said.append("description: asked %s, found %s."
                    % (_quoted(args["description"]), _quoted(_text(repo.get("description")))))
    if topics is not None and set(topics) != set(found["topics"]):
        differences.append("topics")
        said.append("topics: asked %s, found %s." % (_list(sorted(topics)),
                                                     _list(found["topics"])))
    found["differences"] = differences
    lines = ["The repository %s already exists; nothing was changed." % full, _where(found)]
    if said:
        lines.append("It differs from the arguments:")
        lines += said
        lines.append("github_repo-configure corrects these differences.")
    return ctx.result("unchanged", found, resources=[G.repository_resource(owner, name)],
                      cost=cost_of(found), lines=lines + reader.notes)
