"""github_pull-request-open: whether a tooling pull request is open, whether the folder
is fit for a proposal and which of the named files changed. Only mode=plan is converted;
mode=apply stays in the SKILL.md's prose until step 2.

The specification is skills/github_pull-request-open/SKILL.md: the same reads, in the
same order, the same states and the same result block. examine() holds steps 1 to 7,
shared by both modes; run() holds step 8 for plan. Step 2 adds steps 9 to 15.
"""

import importlib.util
import os
import re
import sys

FAMILY = "repo"
PROVIDER = "github"
ACTION = "pull-request-open"
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

DEFAULT_BODY = "Proposed by aleogr."
BRANCH_PREFIX = "aleogr/change-"
_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")

ITEM_ATTENTION = "this folder needs attention"
HOW_ATTENTION = {
    "not-a-checkout": "this folder is not a checkout of the repository",
    "other-remote": "this folder's origin is another repository",
    "other-branch": "git switch {branch}",
    "local-commits": "this folder has commits that are not in the repository",
}
PATHS_RULE = ("paths is not valid: it must be one or more file paths separated by , with no "
              "empty entry, each relative (not starting with / or ./, not ending with /), "
              "with no // and no .., no space, and only A-Z, a-z, 0-9, ., _, - and /.")


def split_paths(value):
    """The paths of `paths`, in the order given, a path named twice counted once; None
    when the value breaks the rule."""
    out = []
    for p in value.split(","):
        if (p == "" or p.startswith("/") or p.startswith("./") or p.endswith("/")
                or "//" in p or ".." in p or " " in p or not _PATH.match(p)):
            return None
        if p not in out:
            out.append(p)
    return out


def _validate(args, mode):
    keys = ["owner", "name", "paths"] + (["title"] if mode == "apply" else [])
    problem = G.first_missing(args, keys)
    if problem:
        return problem
    problem = G.owner_name_problem(args)
    if problem:
        return problem
    if split_paths(args["paths"]) is None:
        return PATHS_RULE
    for key, max_len in (("title", 100), ("body", 100), ("note", 300)):
        if key in args:
            problem = G.free_text_problem(key, args[key], max_len)
            if problem:
                return problem
    return G.mode_problem(args)


def full_body(args):
    body = args.get("body", DEFAULT_BODY)
    return "%s %s" % (body, args["note"]) if args.get("note") else body


def outputs(folder=None, changed=(), open_pr=None, pull_request=None, branch=None):
    return {"folder": folder, "changed": list(changed), "openPullRequest": open_pr,
            "pullRequest": pull_request, "defaultBranch": branch}


class Found(object):
    """What steps 1 to 7 found."""

    def __init__(self, branch, open_pr, folder, changed):
        self.branch = branch
        self.open_pr = open_pr  # {"number", "url", "branch"} or None
        self.folder = folder  # ready, not-a-checkout, other-remote, other-branch, ...
        self.changed = changed


def _tooling_pr(listed):
    best = None
    for pr in listed:
        if not isinstance(pr, dict):
            continue
        head = pr.get("headRefName")
        if (isinstance(head, str) and head.startswith(BRANCH_PREFIX)
                and pr.get("isCrossRepository") is False
                and isinstance(pr.get("number"), int)):
            if best is None or pr["number"] < best["number"]:
                best = pr
    if best is None:
        return None
    return {"number": best["number"], "url": best.get("url"), "branch": best["headRefName"]}


def _listed_paths(out):
    """The paths of `git status --porcelain` lines (after ` -> ` for a rename)."""
    paths = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        p = line[3:]
        if " -> " in p:
            p = p.split(" -> ", 1)[1]
        if len(p) >= 2 and p.startswith('"') and p.endswith('"'):
            p = p[1:-1]
        paths.append(p)
    return paths


def examine(args, ctx, reader):
    """Steps 1 to 7. A Found, or a Result (failed)."""
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    paths = split_paths(args["paths"])
    state = {"branch": None, "open_pr": None, "folder": None}

    def failed(sentence):
        return ctx.result("failed", outputs(state["folder"], (), state["open_pr"], None,
                                            state["branch"]),
                          cost=G.NO_COST, lines=[sentence] + reader.notes)

    # Step 1: the repository.
    c = reader.gh(["gh", "api", "repos/%s" % full])
    first = G.gh_first_read_failure(c)
    if first:
        return failed(first)
    if G.http(c, 404):
        return failed("The repository %s does not exist, or this account cannot see it: it "
                      "must be created first, with /aleogr-repo-github:github_repo-create."
                      % full)
    if not c.ok:
        return failed("The repository %s could not be read: %s." % (full, G.gh_cause(c)))
    repo = G.json_of(c.out)
    branch = repo.get("default_branch") if isinstance(repo, dict) else None
    if not isinstance(branch, str) or not branch:
        return failed("The repository %s could not be read: gh gave no default branch." % full)
    state["branch"] = branch

    # Step 2: an open tooling pull request.
    c = reader.gh(["gh", "pr", "list", "--repo", full, "--state", "open", "--json",
                   "number,url,headRefName,isCrossRepository"])
    listed = G.json_of(c.out) if c.ok else None
    if not isinstance(listed, list):
        return failed("The open pull requests of %s could not be read: %s."
                      % (full, G.gh_cause(c) if not c.ok else "gh did not give a JSON list"))
    state["open_pr"] = _tooling_pr(listed)

    def found(folder, changed=()):
        return Found(branch, state["open_pr"], folder, list(changed))

    # Step 3: a git checkout?
    c = reader.git(["git", "rev-parse", "--is-inside-work-tree"])
    if G.not_installed(c):
        return failed(G.GIT_NOT_INSTALLED)
    if not (c.ok and c.out.strip() == "true"):
        return found("not-a-checkout")
    # Step 4: origin is this repository?
    c = reader.git(["git", "remote", "get-url", "origin"])
    if c.ok:
        if not G.origin_matches(c.out, owner, name):
            return found("other-remote")
    elif "No such remote" in c.text:
        return found("other-remote")
    else:
        return failed("This folder's remote origin could not be read: %s." % G.git_cause(c))
    # Step 5: on the default branch?
    c = reader.git(["git", "branch", "--show-current"])
    if not c.ok:
        return failed("This folder's branch could not be read: %s." % G.git_cause(c))
    if c.out.strip() != branch:
        return found("other-branch")
    # Step 6: the folder's last commit is in the repository?
    c = reader.git(["git", "rev-parse", "HEAD"])
    sha = c.out.strip() if c.ok else None
    if not G.is_sha(sha):
        return failed("This folder's last commit could not be read: %s."
                      % (G.git_cause(c) if not c.ok else "git did not give one commit"))
    c = reader.gh(["gh", "api", "repos/%s/commits/%s" % (full, sha)])
    if not c.ok:
        if G.http(c, 404, 422):
            return found("local-commits")
        return failed("This folder's last commit could not be looked up in %s: %s."
                      % (full, G.gh_cause(c)))
    # Step 7: which of the named files changed?
    c = reader.git(["git", "status", "--porcelain", "--"] + paths)
    if not c.ok:
        return failed("This folder's status could not be read: %s." % G.git_cause(c))
    state["folder"] = "ready"  # steps 3 to 6 found nothing; a folder path keeps it
    listed = _listed_paths(c.out)
    if any(p.endswith("/") or p not in paths for p in listed):
        return failed("paths must be files: a named path is a folder.")
    return found("ready", [p for p in paths if p in listed])


def apply_commands(args, full, branch, changed):
    """The commands of steps 9 to 15, as apply would run them (with <login>, <id> and
    <random>)."""
    title = args.get("title") or "<title>"
    head = BRANCH_PREFIX + "<random>"
    files = " ".join(changed)
    return [
        "gh api user",
        "git config --local user.name <login>",
        "git config --local user.email <id>+<login>@users.noreply.github.com",
        "%s pull --ff-only origin %s" % (G.CREDENTIAL_SHOWN, branch),
        "git switch -c %s" % head,
        "git add -- %s" % files,
        "git commit -m \"%s\" -- %s" % (title, files),
        "%s push -u origin %s" % (G.CREDENTIAL_SHOWN, head),
        "gh pr create --repo %s --base %s --head %s --title \"%s\" --body \"%s\""
        % (full, branch, head, title, full_body(args)),
        "git switch %s" % branch,
    ]


def run(args, ctx):
    mode = ctx.mode
    problem = _validate(args, mode)
    if problem:
        return ctx.failed(problem, outputs(), cost=G.NO_COST)
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    reader = G.Reader(ctx)
    found = examine(args, ctx, reader)
    if not isinstance(found, Found):
        return found

    # Step 8, plan.
    out = outputs(found.folder, found.changed, found.open_pr, None, found.branch)
    pending = []
    lines = []
    if found.open_pr:
        pr = found.open_pr
        pending.append(G.pending_item("pull request #%d is open" % pr["number"],
                                      "merge or close %s" % pr["url"]))
        lines.append("The tooling pull request #%d is open: %s." % (pr["number"], pr["url"]))
    else:
        lines.append("No tooling pull request is open.")
    if found.folder != "ready":
        how = HOW_ATTENTION[found.folder].format(branch=found.branch)
        pending.append(G.pending_item(ITEM_ATTENTION, how))
        lines.append("This folder needs attention (%s): %s." % (found.folder, how))
    else:
        lines.append("This folder is ready for a proposal.")
        if found.changed:
            lines.append("Changed: %s." % ", ".join(found.changed))
        else:
            lines.append("None of the named files changed.")
    if pending:
        status = "pending"
        lines.append("Nothing is changed, in this folder or on GitHub.")
    elif not found.changed:
        status = "unchanged"
        lines.append("Nothing to do.")
    else:
        status = "would-create"
        lines.append("apply would run, without anything run now:")
        lines += G.shown(apply_commands(args, full, found.branch, found.changed))
    return ctx.result(status, out, pending=pending, cost=G.NO_COST,
                      lines=lines + reader.notes)
