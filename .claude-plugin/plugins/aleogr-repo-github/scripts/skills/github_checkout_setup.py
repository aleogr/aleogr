"""github_checkout-setup: whether the repository has the local file (by default the
project declaration) and whether it equals the local one (mode=plan); in mode=apply,
sends the file at the repository's birth, or fast-forwards a folder that is behind.

The specification is skills/github_checkout-setup/SKILL.md: the same reads, in the same
order, the same states and the same result block. examine() holds steps 1 to 5, shared
by both modes; run() holds step 6; birth() holds steps 7 to 16 and fast_forward() steps
17 and 18, run through the writing runner (ctx.write) only in mode=apply.

The login, the id and the no-reply address are never printed: the two `git config`
commands pass them as Hidden, so their `+ ` lines show `<login>` and `<id>`.
"""

import importlib.util
import os
import re
import sys

FAMILY = "repo"
PROVIDER = "github"
ACTION = "checkout-setup"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply runs git writes, through ctx.write only


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


# ---------------------------------------------------------------------------
# mode=apply: steps 7 to 18

_LOGIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
LOGIN_SHOWN = "<login>"
EMAIL_SHOWN = "<id>+<login>@users.noreply.github.com"
NOT_CREATED = ("The repository %s does not exist: it must be created first, with "
               "/aleogr-repo-github:github_repo-create; nothing was changed.")
# Step 15: the repository's rules refused the push.
_RULES_WORDS = ("GH013", "GH006", "rule violations")
# Step 17: a fast-forward that is not possible.
_FF_WORDS = ("would be overwritten", "Not possible to fast-forward", "diverging", "CONFLICT")


def identity_commands(login, user_id):
    """The two commands of step 11, as the SKILL.md writes them; the values are Hidden,
    shown as `<login>` and `<id>+<login>@users.noreply.github.com`."""
    email = "%s+%s@users.noreply.github.com" % (user_id, login)
    return [
        ["git", "config", "--local", "user.name", common.Hidden(login, LOGIN_SHOWN)],
        ["git", "config", "--local", "user.email", common.Hidden(email, EMAIL_SHOWN)],
    ]


def init_command(branch):
    return ["git", "init", "-b", branch]


def remote_add_command(owner, name):
    return ["git", "remote", "add", "origin", "https://github.com/%s/%s.git" % (owner, name)]


def pull_command(branch):
    return ["git"] + G.CREDENTIAL + ["pull", "origin", branch]


def add_command(path):
    return ["git", "add", "--", path]


def commit_command(message, path):
    return ["git", "commit", "-m", message, "--", path]


def push_command(branch):
    return ["git"] + G.CREDENTIAL + ["push", "-u", "origin", branch]


def fast_forward_command(branch):
    return ["git"] + G.CREDENTIAL + ["pull", "--ff-only", "origin", branch]


def verify_item(args):
    how = "/aleogr-repo-github:github_checkout-setup owner=%s name=%s" % (args["owner"],
                                                                       args["name"])
    path = args.get("path", DEFAULT_PATH)
    if path != DEFAULT_PATH:
        how += " path=%s" % path
    if args.get("head") == "check":
        how += " head=check"
    return G.pending_item("verify", how + " mode=plan")


def _account(c):
    """(login, id) from `gh api user`, or None. The login is a GitHub login and the id
    a number, or it is not the account."""
    user = G.json_of(c.out) if c.ok else None
    if not isinstance(user, dict):
        return None
    login, user_id = user.get("login"), user.get("id")
    if not (isinstance(login, str) and _LOGIN.match(login)):
        return None
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 0:
        return None
    return login, user_id


def _changes_line(changes):
    if not changes:
        return "No local change was made in this folder."
    return "Local changes already made in this folder: %s." % ", ".join(changes)


def _verify(reader, full, path, local):
    """Steps 16 and 18: the read of step 3 again, compared by the rule of step 4. The
    state (equal, differs, or None when the read failed)."""
    c = reader.gh(["gh", "api", "repos/%s/contents/%s" % (full, path),
                   "-H", "Accept: application/vnd.github.raw"])
    if not c.ok:
        return None
    remote = G.json_of(c.out)
    is_json = remote is not None or c.out.strip() == "null"
    return "equal" if is_json and G.json_equal(remote, local) else "differs"


def birth(args, ctx, reader, found):
    """Steps 7 to 16: the state is not-sent and the repository exists."""
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    path = args.get("path", DEFAULT_PATH)
    message = args.get("message", DEFAULT_MESSAGE)
    branch = found.branch
    resources = [G.repository_resource(owner, name)]
    changes = []

    def failed(sentence, extra=()):
        lines = [sentence] + list(extra) + [
            "Nothing was changed on GitHub.", _changes_line(changes)]
        return ctx.result("failed", outputs("not-sent", branch, path), resources=resources,
                          cost=G.NO_COST, lines=lines + reader.notes)

    # Step 7: the account, for the commit identity only.
    c = reader.gh(["gh", "api", "user"])
    account = _account(c)
    if account is None:
        return failed("The account of gh could not be read: %s."
                      % (G.gh_cause(c) if not c.ok else "gh gave no login and id"))
    login, user_id = account

    # Step 8: a git checkout?
    c = reader.git(["git", "rev-parse", "--is-inside-work-tree"])
    was_checkout = c.ok and c.out.strip() == "true"
    if not was_checkout:
        if G.not_installed(c):
            return failed(G.GIT_NOT_INSTALLED)
        if c.ok or "not a git repository" not in c.text:
            return failed("This folder could not be read as a git checkout: %s."
                          % (G.git_cause(c) if not c.ok else "git did not answer true"))
        if not reader.write(init_command(branch)).ok:
            return failed("git init -b needs git 2.28 or later: this folder could not be "
                          "made a git checkout.")
        changes.append("a new git checkout")

    # Step 9: origin is this repository?
    c = reader.git(["git", "remote", "get-url", "origin"])
    if c.ok:
        if not G.origin_matches(c.out, owner, name):
            return failed("This folder's origin is not the repository %s; nothing was "
                          "changed." % full)
    elif "No such remote" in c.text:
        if not reader.write(remote_add_command(owner, name)).ok:
            return failed("The remote origin could not be added to this folder: git "
                          "refused it.")
        changes.append("the remote origin")
    else:
        return failed("This folder's remote origin could not be read: %s." % G.git_cause(c))

    # Step 10: on the default branch?
    c = reader.git(["git", "branch", "--show-current"])
    current = c.out.strip() if c.ok else None
    if current != branch:
        if c.ok and current:
            return failed("This folder is on the branch %s, and it must be on %s."
                          % (current, branch))
        if c.ok:
            return failed("This folder is on no branch, and it must be on %s." % branch)
        return failed("This folder's branch could not be read (%s), and it must be on %s."
                      % (G.git_cause(c), branch))

    # Step 11: this checkout's commit identity.
    name_cmd, email_cmd = identity_commands(login, user_id)
    if not reader.write(name_cmd).ok:
        return failed("This checkout's commit identity could not be set: git refused "
                      "git config --local user.name <login>.")
    changes.append("this checkout's commit name")
    if not reader.write(email_cmd).ok:
        return failed("This checkout's commit identity could not be set: git refused "
                      "git config --local user.email %s." % EMAIL_SHOWN)
    changes[-1] = "this checkout's identity"

    # Step 12: the repository's first commit (its README).
    c = reader.write(pull_command(branch))
    if not c.ok:
        extra = ["An interrupted merge may be left in this folder."] if was_checkout else []
        return failed("The README of %s could not be pulled into this folder: %s."
                      % (full, G.git_cause(c)), extra)
    changes.append("the pulled README")

    # Step 13: only this run's commit may be pushed.
    local_commits = ("This folder has local commits that are not in the repository; "
                     "nothing was pushed.")
    c = reader.git(["git", "rev-list", "--count", "origin/%s..HEAD" % branch])
    count = c.out.strip() if c.ok else None
    resume = False
    if count == "1":
        c = reader.git(["git", "diff", "--name-only", "origin/%s" % branch, "HEAD"])
        listed = [l.rstrip("\r") for l in c.out.strip().splitlines()] if c.ok else None
        if listed != [path]:
            return failed(local_commits)
        c = reader.git(["git", "log", "-1", "--format=%ae", "HEAD"])
        email = "%s+%s@users.noreply.github.com" % (user_id, login)
        if not (c.ok and c.out.strip() == email):
            return failed(local_commits)
        resume = True
    elif count != "0":
        return failed(local_commits)

    # Step 14: commit the file, and only the file.
    if not resume:
        if not reader.write(add_command(path)).ok:
            return failed("The file %s could not be added: git refused it." % path)
        if not reader.write(commit_command(message, path)).ok:
            return failed("The file %s could not be committed: git refused it." % path)
        changes.append("a local commit")

    # Step 15: push to the default branch.
    c = reader.write(push_command(branch))
    if not c.ok:
        t = c.text
        if any(w in t for w in _RULES_WORDS) or "protected branch" in t.lower():
            lines = ["The repository's rules refused the push of %s to %s: the file is not "
                     "in the repository." % (path, branch),
                     "Nothing was changed on GitHub; the local commit is kept.",
                     _changes_line(changes),
                     "Open a pull request that adds %s." % path]
            return ctx.result("pending", outputs("not-sent", branch, path),
                              resources=resources,
                              pending=[G.pending_item(ITEM_MISSING,
                                                      "open a pull request that adds %s"
                                                      % path)],
                              cost=G.NO_COST, lines=lines + reader.notes)
        return failed("The push of %s to %s failed: %s; the local commit is kept."
                      % (path, branch, G.git_cause(c)))

    # Step 16: verify, once.
    state = _verify(reader, full, path, found.local)
    lines = ["The file %s was sent to %s as its first content after its README, on %s."
             % (path, full, branch),
             "Local changes made in this folder: %s." % ", ".join(changes)]
    pending = []
    if state == "equal":
        lines.append("The repository's copy of %s now equals the local file." % path)
    else:
        lines.append("The repository's copy of %s could not be read back to verify it."
                     % path if state is None else
                     "The repository's copy of %s, read back, does not equal the local file."
                     % path)
        pending.append(verify_item(args))
    return ctx.result("created", outputs(state, branch, path, pushed=True),
                      resources=resources, pending=pending, cost=G.NO_COST,
                      lines=lines + reader.notes)


def fast_forward(args, ctx, reader, found):
    """Steps 17 and 18: the state is behind."""
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    path = args.get("path", DEFAULT_PATH)
    branch = found.branch
    resources = [G.repository_resource(owner, name)]

    # Step 17: a fast-forward only.
    c = reader.write(fast_forward_command(branch))
    if not c.ok:
        if any(w in c.text for w in _FF_WORDS):
            sentence = ("This folder cannot be brought up to date by a fast-forward; nothing "
                        "was changed on GitHub.")
        else:
            sentence = ("This folder could not be brought up to date: %s; nothing was "
                        "changed on GitHub." % G.git_cause(c))
        return ctx.result("failed", outputs("behind", branch, path), resources=resources,
                          cost=G.NO_COST, lines=[sentence] + reader.notes)

    # Step 18: verify, once, against the local file read again.
    text, _ = G.read_local(path)
    local = G.json_of(text) if text is not None else None
    local_ok = text is not None and (local is not None or text.strip() == "null")
    state = _verify(reader, full, path, local)
    if state == "equal" and not local_ok:
        state = "differs"
    lines = ["This folder was behind the repository: it was brought up to date by a "
             "fast-forward of %s." % branch,
             "Nothing was committed, pushed, configured or initialised."]
    pending = []
    if state == "equal":
        lines.append("The repository's copy of %s equals the local file." % path)
    else:
        lines.append("The repository's copy of %s could not be read back to verify it."
                     % path if state is None else
                     "The repository's copy of %s, read back, does not equal the local file."
                     % path)
        pending.append(verify_item(args))
    return ctx.result("updated", outputs(state, branch, path, updated=True),
                      resources=resources, pending=pending, cost=G.NO_COST,
                      lines=lines + reader.notes)


# Values the SKILL.md's rules let through but that no git command of this skill takes
# (the shapes of aleogr_common's allowlist of writes): checked before any write, each
# with one fixed sentence, instead of a refused write.
PATH_UNUSABLE = ("path={path} cannot be committed as it is written: it has a . part, an "
                 "empty part or a / at the end; give the file's plain relative path (such "
                 "as a/b.json, not ./a/b.json, a//b.json or a/); nothing was changed.")
BRANCH_UNUSABLE = ("The default branch {branch} of {full} has a name this tooling does not "
                   "use in a git command: it may hold only A-Z, a-z, 0-9, ., _, - and /, "
                   "not start with -, have no .. and no //, and not end with / or .{extra}; "
                   "nothing was changed.")
BRANCH_UNUSABLE_BIRTH = ", and the birth does not push a branch named aleogr/change-..."


def path_usable(path):
    """Whether `git add -- <path>` and `git commit ... -- <path>` take this path."""
    return common.write_refusal("github_checkout-setup", ["git", "add", "--", path]) is None


def branch_usable(branch, birth):
    """Whether the git commands of a birth (or of a fast-forward) take this branch."""
    pattern = common.DEFAULT_BRANCH_ARG if birth else common.BRANCH_ARG
    return isinstance(branch, str) and pattern.re.fullmatch(branch) is not None


def apply(args, ctx, reader, found):
    """Step 6 for apply, when it acts: a birth, a folder behind, or a repository that
    does not exist."""
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    path = args.get("path", DEFAULT_PATH)
    if found.state == "behind":
        if not branch_usable(found.branch, False):
            return ctx.result("failed", outputs("behind", found.branch, path),
                              resources=[G.repository_resource(owner, name)], cost=G.NO_COST,
                              lines=[BRANCH_UNUSABLE.format(branch=found.branch, full=full,
                                                            extra="")] + reader.notes)
        return fast_forward(args, ctx, reader, found)
    if not found.exists:
        return ctx.result("failed", outputs("not-sent", None, path),
                          cost=G.NO_COST, lines=[NOT_CREATED % full] + reader.notes)
    problem = None
    if not path_usable(path):
        problem = PATH_UNUSABLE.format(path=path)
    elif not branch_usable(found.branch, True):
        problem = BRANCH_UNUSABLE.format(branch=found.branch, full=full,
                                         extra=BRANCH_UNUSABLE_BIRTH)
    if problem:
        return ctx.result("failed", outputs("not-sent", found.branch, path),
                          resources=[G.repository_resource(owner, name)], cost=G.NO_COST,
                          lines=[problem, "No local change was made in this folder."]
                          + reader.notes)
    return birth(args, ctx, reader, found)


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
    if args.get("mode") == "apply" and found.state in ("behind", "not-sent"):
        result = apply(args, ctx, reader, found)
        result.data = {"repositoryCopy": found.copy}
        return result

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
