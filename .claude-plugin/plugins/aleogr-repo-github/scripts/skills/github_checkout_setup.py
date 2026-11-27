"""github_checkout-setup: whether the repository has the local file (by default the
project declaration) and whether it equals the local one. Only mode=plan is converted;
mode=apply stays in the SKILL.md's prose until step 2.

The specification is skills/github_checkout-setup/SKILL.md: the same reads, in the same
order, the same states and the same result block. examine() holds steps 1 to 5, shared
by both modes; run() holds step 6 for plan. Step 2 adds steps 7 to 18 after examine().
"""

import importlib.util
import os
import re
import sys

FAMILY = "repo"
PROVIDER = "github"
ACTION = "checkout-setup"
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

DEFAULT_PATH = ".aleogr/project.json"
DEFAULT_MESSAGE = "Add the project declaration"
_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")

ITEM_DIFFERS = "declaration changed in this folder"
ITEM_ATTENTION = "this folder needs attention"
ITEM_MISSING = "declaration is not in the repository"
HOW_DIFFERS = "propose the change with a pull request"
HOW_ATTENTION = {
    "not-a-checkout": "this folder is not a checkout of the repository",
    "other-remote": "this folder's origin is another repository",
    "other-branch": "git switch {branch}",
    "untracked-difference": ("the file in this folder differs from the repository's but git "
                             "sees no change in it; check that the file is not ignored"),
    "local-commits": "this folder has commits that are not in the repository",
}


def _validate(args):
    problem = G.first_missing(args, ("owner", "name"))
    if problem:
        return problem
    problem = G.owner_name_problem(args)
    if problem:
        return problem
    if "path" in args:
        p = args["path"]
        if (p == "" or p.startswith("/") or ".." in p or " " in p
                or not _PATH.match(p)):
            return ("path is not valid: it must be a relative path, not starting with /, "
                    "with no .. and no space, of A-Z, a-z, 0-9, ., _, - and / only.")
    if "message" in args:
        problem = G.free_text_problem("message", args["message"])
        if problem:
            return problem
    if "head" in args and args["head"] != "check":
        return "head is not valid: it must be check."
    return G.mode_problem(args)


def outputs(state=None, branch=None, path=DEFAULT_PATH, pushed=False, updated=False,
            reason=None):
    return {"state": state, "defaultBranch": branch, "path": path, "pushed": pushed,
            "updated": updated, "reason": reason}


class Found(object):
    """What steps 1 to 5 found."""

    def __init__(self, exists, branch, state, reason=None, local=None, file_equal=False,
                 copy=None):
        self.exists = exists  # step 1 proved the repository exists
        self.file_equal = file_equal  # step 4 found the two files equal
        self.branch = branch  # its default_branch (None when it does not exist)
        self.state = state  # equal, not-sent, differs, behind, needs-attention, missing
        self.reason = reason  # for needs-attention
        self.local = local  # the local file, as a JSON value
        # The repository's copy that step 3 read: None when it was not read (absent, or
        # the repository does not exist), else {"json": <it is valid JSON>, "value": ...}.
        self.copy = copy


class Failure(object):
    def __init__(self, sentence):
        self.sentence = sentence


def _folder(reader, full, owner, name, branch, path, file_equal):
    """Steps 4a to 4e (file_equal False), or 4a, 4b, 4c and 4e for an equal file with
    head=check (file_equal True). (state, reason), or a Failure."""
    attention = (lambda why: ("needs-attention", why))
    # 4a
    c = reader.git(["git", "rev-parse", "--is-inside-work-tree"])
    if G.not_installed(c):
        return Failure(G.GIT_NOT_INSTALLED)
    if not (c.ok and c.out.strip() == "true"):
        return ("equal", None) if file_equal else attention("not-a-checkout")
    # 4b
    c = reader.git(["git", "remote", "get-url", "origin"])
    if c.ok:
        if not G.origin_matches(c.out, owner, name):
            return attention("other-remote")
    elif "No such remote" in c.text:
        return attention("other-remote")
    else:
        return Failure("This folder's remote origin could not be read: %s." % G.git_cause(c))
    # 4c
    c = reader.git(["git", "branch", "--show-current"])
    if not c.ok:
        return Failure("This folder's branch could not be read: %s." % G.git_cause(c))
    if c.out.strip() != branch:
        return attention("other-branch")
    # 4d
    if not file_equal:
        c = reader.git(["git", "status", "--porcelain", "--", path])
        if not c.ok:
            return Failure("This folder's status of %s could not be read: %s."
                           % (path, G.git_cause(c)))
        if c.out.strip():
            return ("differs", None)
    # 4e
    c = reader.git(["git", "rev-parse", "HEAD"])
    sha = c.out.strip() if c.ok else None
    if not G.is_sha(sha):
        return Failure("This folder's last commit could not be read: %s."
                       % (G.git_cause(c) if not c.ok else "git did not give one commit"))
    c = reader.gh(["gh", "api", "repos/%s/commits/%s" % (full, branch)])
    head = G.json_of(c.out) if c.ok else None
    if not (isinstance(head, dict) and isinstance(head.get("sha"), str) and head["sha"]):
        return Failure("The head of the default branch of %s could not be read: %s."
                       % (full, G.gh_cause(c) if not c.ok else "gh gave no commit"))
    if sha == head["sha"]:
        return ("equal", None) if file_equal else attention("untracked-difference")
    c = reader.gh(["gh", "api", "repos/%s/commits/%s" % (full, sha)])
    if c.ok:
        return ("behind", None)
    if G.http(c, 404, 422):
        return attention("local-commits")
    return Failure("This folder's last commit could not be looked up in %s: %s."
                   % (full, G.gh_cause(c)))


def examine(args, ctx, reader):
    """Steps 1 to 5. A Found, or a Result (failed)."""
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    path = args.get("path", DEFAULT_PATH)

    def failed(sentence, exists, branch=None, state=None):
        resources = [G.repository_resource(owner, name)] if exists else []
        return ctx.result("failed", outputs(state, branch, path), resources=resources,
                          cost=G.NO_COST, lines=[sentence] + reader.notes)

    # Step 1: the repository.
    c = reader.gh(["gh", "api", "repos/%s" % full])
    first = G.gh_first_read_failure(c)
    if first:
        return failed(first, False)
    exists = True
    branch = None
    if G.http(c, 404):
        exists = False
    elif not c.ok:
        return failed("The repository %s could not be read: %s." % (full, G.gh_cause(c)),
                      False)
    else:
        repo = G.json_of(c.out)
        branch = repo.get("default_branch") if isinstance(repo, dict) else None
        if not isinstance(branch, str) or not branch:
            return failed("The repository %s could not be read: gh gave no default branch."
                          % full, False)

    # Step 2: the local file (read as a file, never with a shell command).
    text, _ = G.read_local(path)
    local = G.json_of(text) if text is not None else None
    if text is None:
        return failed("The local file %s does not exist." % path, exists, branch)
    if local is None and text.strip() != "null":
        return failed("The local file %s is not valid JSON." % path, exists, branch)
    if not exists:
        return Found(False, None, "not-sent", local=local)

    # Step 3: the repository's copy, from its default branch.
    c = reader.gh(["gh", "api", "repos/%s/contents/%s" % (full, path),
                   "-H", "Accept: application/vnd.github.raw"])
    if c.ok:
        # Step 4: the file is present; compare as JSON values.
        remote = G.json_of(c.out)
        is_json = remote is not None or c.out.strip() == "null"
        copy = {"json": is_json, "value": remote}
        equal = is_json and G.json_equal(remote, local)
        if equal and args.get("head") != "check":
            return Found(True, branch, "equal", local=local, file_equal=True, copy=copy)
        got = _folder(reader, full, owner, name, branch, path, equal)
        if isinstance(got, Failure):
            return failed(got.sentence, True, branch)
        return Found(True, branch, got[0], got[1], local, equal, copy=copy)
    if not G.http(c, 404):
        return failed("The repository's copy of %s could not be read: %s."
                      % (path, G.gh_cause(c)), True, branch)

    # Step 5: the file is absent; count the commits of the default branch, at most two.
    c = reader.gh(["gh", "api", "repos/%s/commits?per_page=2" % full])
    listed = G.json_of(c.out) if c.ok else None
    if G.http(c, 409) or (c.ok and listed == []):
        return failed("The repository %s has no commit: it was not created with its README."
                      % full, True, branch)
    if not c.ok:
        return failed("The commits of %s could not be read: %s." % (full, G.gh_cause(c)),
                      True, branch)
    if not isinstance(listed, list):
        return failed("The commits of %s could not be read: gh did not give a JSON list."
                      % full, True, branch)
    if len(listed) == 1:
        return Found(True, branch, "not-sent", local=local)
    return Found(True, branch, "missing", local=local)


def _birth_commands(args, owner, name, branch):
    """The commands of steps 7 to 15, as apply would run them (with <login> and <id>)."""
    path = args.get("path", DEFAULT_PATH)
    message = args.get("message", DEFAULT_MESSAGE)
    b = branch or "<branch>"
    return [
        "gh api user",
        "git rev-parse --is-inside-work-tree",
        "git init -b %s   (only when this folder is not a git checkout)" % b,
        "git remote get-url origin",
        "git remote add origin https://github.com/%s/%s.git   (only when there is no "
        "remote origin)" % (owner, name),
        "git branch --show-current",
        "git config --local user.name <login>",
        "git config --local user.email <id>+<login>@users.noreply.github.com",
        "%s pull origin %s" % (G.CREDENTIAL_SHOWN, b),
        "git rev-list --count origin/%s..HEAD" % b,
        "git add -- %s" % path,
        "git commit -m \"%s\" -- %s" % (message, path),
        "%s push -u origin %s" % (G.CREDENTIAL_SHOWN, b),
    ]


def run(args, ctx):
    path = args.get("path", DEFAULT_PATH)
    problem = _validate(args)
    if problem:
        return ctx.failed(problem, outputs(path=path), cost=G.NO_COST)
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    reader = G.Reader(ctx)
    found = examine(args, ctx, reader)
    if not isinstance(found, Found):
        return found

    # Step 6, plan.
    resources = [G.repository_resource(owner, name)] if found.exists else []
    out = outputs(found.state, found.branch, path, reason=found.reason)
    state = found.state
    pending = []
    if state == "equal":
        status = "unchanged"
        if args.get("head") == "check":
            lines = ["The repository's copy of %s equals the local file, and this folder is "
                     "not behind the repository." % path]
        else:
            lines = ["The repository's copy of %s equals the local file." % path]
        lines.append("Nothing to do.")
    elif state == "differs":
        status = "pending"
        pending = [G.pending_item(ITEM_DIFFERS, HOW_DIFFERS)]
        lines = ["The repository's copy of %s differs from the local file, which is changed "
                 "in this folder." % path,
                 "Nothing is sent: propose the change with a pull request."]
    elif state == "needs-attention":
        status = "pending"
        how = HOW_ATTENTION[found.reason].format(branch=found.branch)
        pending = [G.pending_item(ITEM_ATTENTION, how)]
        lines = ["The repository's copy of %s %s the local file, and this folder needs "
                 "attention (%s): %s." % (path, "equals" if found.file_equal else
                                          "differs from", found.reason, how),
                 "Nothing is changed: the owner fixes the folder by hand."]
    elif state == "behind":
        status = "would-update"
        lines = ["This folder is behind the repository: its last commit is in the "
                 "repository, which has moved on since.",
                 "apply would bring it up to date by a fast-forward only, with:"]
        lines += G.shown(["%s pull --ff-only origin %s" % (G.CREDENTIAL_SHOWN,
                                                          found.branch)])
    elif state == "missing":
        status = "pending"
        pending = [G.pending_item(ITEM_MISSING, "open a pull request that adds %s" % path)]
        lines = ["The repository %s has history but does not have %s: a repository with "
                 "history is never pushed to." % (full, path),
                 "Open a pull request that adds %s." % path]
    else:  # not-sent
        status = "would-create"
        if found.exists:
            lines = ["The repository %s is at its birth: its default branch has only its "
                     "README and does not have %s." % (full, path)]
        else:
            lines = ["The repository %s does not exist yet: it must be created first, with "
                     "/aleogr-repo-github:github_repo-create." % full]
        lines.append("apply would run, without anything run now:")
        lines += G.shown(_birth_commands(args, owner, name, found.branch))
    result = ctx.result(status, out, resources=resources, pending=pending, cost=G.NO_COST,
                        lines=lines + reader.notes)
    # For a calling command only (the --json document): the copy step 3 read, which the
    # block does not hold. project-plan notes its environments and database components
    # from it, with no read of its own.
    result.data = {"repositoryCopy": found.copy}
    return result
