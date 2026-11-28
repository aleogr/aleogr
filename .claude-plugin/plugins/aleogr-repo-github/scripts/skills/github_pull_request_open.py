"""github_pull-request-open: whether a tooling pull request is open, whether the folder
is fit for a proposal and which of the named files changed (mode=plan); in mode=apply,
commits the changed files on a new branch aleogr/change-<random>, pushes it, opens the
pull request and returns the folder to the default branch.

The rules are this module's, pinned by its unit tests
(tests/unit/test_github_pull_request_open.py) and its scenarios. It was built from
skills/github_pull-request-open/SKILL.md as that text was before the skill became a
shell over this command (the text is in the repository's history, at the commit before
that change): the same reads, in the same order, the same states and the same result
block. examine() holds steps 1 to 7, shared by both modes; run() holds step 8; apply()
holds steps 9 to 15, run through the writing runner (ctx.write) only in mode=apply.

The login, the id and the no-reply address are never printed: the two `git config`
commands pass them as Hidden, so their `+ ` lines show `<login>` and `<id>`.
"""

import importlib.util
import os
import random
import re
import sys

FAMILY = "repo"
PROVIDER = "github"
ACTION = "pull-request-open"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply runs git and gh writes, through ctx.write only


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


# ---------------------------------------------------------------------------
# mode=apply: steps 9 to 15

_LOGIN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
LOGIN_SHOWN = "<login>"
EMAIL_SHOWN = "<id>+<login>@users.noreply.github.com"
_RANDOM_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
# Step 10: a fast-forward that conflicts with what the repository has now.
_FF_WORDS = ("would be overwritten", "Not possible to fast-forward", "diverging", "CONFLICT")


def new_branch():
    """aleogr/change-<random>: 6 random characters of a-z0-9, drawn once, by the
    system's random source (never written by hand)."""
    rng = random.SystemRandom()
    return BRANCH_PREFIX + "".join(rng.choice(_RANDOM_CHARS) for _ in range(6))


def identity_commands(login, user_id):
    """The two commands of step 9, as the SKILL.md writes them; the values are Hidden,
    shown as `<login>` and `<id>+<login>@users.noreply.github.com`."""
    email = "%s+%s@users.noreply.github.com" % (user_id, login)
    return [
        ["git", "config", "--local", "user.name", common.Hidden(login, LOGIN_SHOWN)],
        ["git", "config", "--local", "user.email", common.Hidden(email, EMAIL_SHOWN)],
    ]


def fast_forward_command(branch):
    return ["git"] + G.CREDENTIAL + ["pull", "--ff-only", "origin", branch]


def switch_new_command(head):
    return ["git", "switch", "-c", head]


def add_command(changed):
    return ["git", "add", "--"] + list(changed)


def commit_command(title, changed):
    return ["git", "commit", "-m", title, "--"] + list(changed)


def push_command(head):
    return ["git"] + G.CREDENTIAL + ["push", "-u", "origin", head]


def pr_create_command(full, branch, head, title, body):
    return ["gh", "pr", "create", "--repo", full, "--base", branch, "--head", head,
            "--title", title, "--body", body]


def switch_back_command(branch):
    return ["git", "switch", branch]


def _account(c):
    """(login, id) from `gh api user`, or None."""
    user = G.json_of(c.out) if c.ok else None
    if not isinstance(user, dict):
        return None
    login, user_id = user.get("login"), user.get("id")
    if not (isinstance(login, str) and _LOGIN.match(login)):
        return None
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id < 0:
        return None
    return login, user_id


def _pr_address(out, owner, name):
    """(number, url) from the last line of `gh pr create`, or None."""
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    if not lines:
        return None
    m = re.match(r"^https://github\.com/%s/%s/pull/([0-9]+)$"
                 % (re.escape(owner), re.escape(name)), lines[-1], re.I)
    if not m:
        return None
    return int(m.group(1)), lines[-1]


def _changes_line(changes):
    if not changes:
        return "No local change was made in this folder."
    return "Local changes made in this folder: %s." % ", ".join(changes)


PATH_UNUSABLE = ("The path {path} cannot be committed as it is written: it has a . part; "
                 "name the file by its plain relative path (such as a/b.json, not "
                 "a/./b.json); nothing was committed, and nothing reached GitHub.")
BRANCH_UNUSABLE = ("The default branch {branch} of {full} has a name this tooling does not "
                   "use in a git command: it may hold only A-Z, a-z, 0-9, ., _, - and /, "
                   "not start with -, have no .. and no //, and not end with / or .; "
                   "nothing was committed, and nothing reached GitHub.")


def path_usable(path):
    """Whether `git add -- <path>` and `git commit ... -- <path>` take this path."""
    return common.write_refusal("github_pull-request-open",
                                ["git", "add", "--", path]) is None


def branch_usable(branch):
    """Whether the git and gh commands of steps 10, 14 and 15 take this branch."""
    return isinstance(branch, str) and common.BRANCH_ARG.re.fullmatch(branch) is not None


def unusable(args, ctx, reader, found):
    """The `failed` result of a changed path or a default branch that no git or gh
    command of steps 9 to 15 would take, or None: values the SKILL.md's rules let
    through but that the shapes of aleogr_common's allowlist of writes refuse. Both
    modes run it when there is something to propose, so a plan never announces a write
    that the apply refuses."""
    full = "%s/%s" % (args["owner"], args["name"])
    sentence = None
    for p in found.changed:
        if not path_usable(p):
            sentence = PATH_UNUSABLE.format(path=p)
            break
    if sentence is None and not branch_usable(found.branch):
        sentence = BRANCH_UNUSABLE.format(branch=found.branch, full=full)
    if sentence is None:
        return None
    return ctx.result("failed", outputs("ready", found.changed, None, None, found.branch),
                      cost=G.NO_COST, lines=[sentence, _changes_line([])] + reader.notes)


def apply(args, ctx, reader, found):
    """Steps 9 to 15: the folder is ready, no tooling pull request is open, and
    `changed` is not empty."""
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    branch = found.branch
    changed = found.changed
    title = args["title"]
    body = full_body(args)
    changes = []

    def ending(status, sentences, pull_request=None, pending=(), resources=()):
        lines = list(sentences) + [_changes_line(changes)]
        return ctx.result(status, outputs("ready", changed, None, pull_request, branch),
                          resources=list(resources), pending=list(pending), cost=G.NO_COST,
                          lines=lines + reader.notes)

    nothing = "Nothing was committed, and nothing reached GitHub."

    # Before any write (run() ran it already, for both modes; apply() keeps it so that
    # it never writes without it).
    refused = unusable(args, ctx, reader, found)
    if refused is not None:
        return refused

    # Step 9: the account, then this checkout's commit identity.
    c = reader.gh(["gh", "api", "user"])
    account = _account(c)
    if account is None:
        return ending("failed", ["The account of gh could not be read: %s."
                                 % (G.gh_cause(c) if not c.ok else "gh gave no login and id"),
                                 nothing])
    name_cmd, email_cmd = identity_commands(*account)
    if not reader.write(name_cmd).ok:
        return ending("failed", ["This checkout's commit identity could not be set: git "
                                 "refused git config --local user.name <login>.", nothing])
    changes.append("this checkout's commit name")
    if not reader.write(email_cmd).ok:
        return ending("failed", ["This checkout's commit identity could not be set: git "
                                 "refused git config --local user.email %s." % EMAIL_SHOWN,
                                 nothing])
    changes[-1] = "this checkout's identity"

    # Step 10: the default branch, by a fast-forward only.
    c = reader.write(fast_forward_command(branch))
    if not c.ok:
        if any(w in c.text for w in _FF_WORDS):
            sentence = ("The change in this folder conflicts with what the repository has "
                        "now; nothing was committed.")
        else:
            sentence = ("The default branch %s could not be brought up to date: %s; nothing "
                        "was committed." % (branch, G.git_cause(c)))
        return ending("failed", [sentence, "Nothing reached GitHub."])
    changes.append("a fast-forward of %s" % branch)

    # Step 11: the branch of the proposal.
    head = new_branch()
    if not reader.write(switch_new_command(head)).ok:
        return ending("failed", ["The branch %s could not be created: git refused it; "
                                 "nothing was committed." % head, "Nothing reached GitHub."])
    changes.append("the local branch %s" % head)

    status, sentences, pull_request, pending, resources = None, [], None, [], []
    # Step 12: commit the changed files, and only them.
    if not reader.write(add_command(changed)).ok:
        what = "add"
    elif not reader.write(commit_command(title, changed)).ok:
        what = "commit"
    else:
        what = None
    if what:
        status = "failed"
        sentences = ["The changed files could not be committed: git refused the %s; nothing "
                     "reached GitHub." % what,
                     "The named files stay staged in this folder, and the empty local branch "
                     "%s is kept." % head]
    else:
        changes[-1] = "the local branch %s and its commit, which is kept" % head
        # Step 13: push the new branch, never the default branch.
        c = reader.write(push_command(head))
        if not c.ok:
            status = "failed"
            sentences = ["The branch %s could not be pushed: %s; nothing reached GitHub, and "
                         "the commit is kept in the local branch %s."
                         % (head, G.git_cause(c), head)]
        else:
            # Step 14: open the pull request.
            command = pr_create_command(full, branch, head, title, body)
            c = reader.write(command)
            address = _pr_address(c.out, owner, name) if c.ok else None
            if address:
                number, url = address
                status = "created"
                pull_request = {"number": number, "url": url, "branch": head}
                resources = [{"type": "pull-request", "id": "%s#%d" % (full, number),
                              "name": head}]
                sentences = ["The pull request #%d was opened: %s." % (number, url),
                             "Proposed on %s: %s." % (head, ", ".join(changed))]
            else:
                status = "updated"
                how = ('gh pr create --repo %s --base %s --head %s --title "%s" --body "%s"'
                       % (full, branch, head, title, body))
                pending.append(G.pending_item("open the pull request", how))
                sentences = ["The branch %s is on GitHub, but the pull request was not "
                             "opened: %s." % (head, G.gh_cause(c) if not c.ok
                                              else "gh gave no pull request address"),
                             "Open it with: %s" % how]

    # Step 15: return the folder to the default branch (always, once step 11 succeeded).
    if reader.write(switch_back_command(branch)).ok:
        sentences.append("This folder is back on %s." % branch)
    else:
        sentences.append("This folder is still on %s: git refused to switch it back to %s."
                         % (head, branch))
        pending.append(G.pending_item("return this folder to the default branch",
                                      "git switch %s" % branch))
    return ending(status, sentences, pull_request, pending, resources)


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
    if not pending and found.changed:
        # Both modes: a path or the branch that the apply's commands would refuse ends
        # here, with the apply's sentence, before anything is announced or written.
        refused = unusable(args, ctx, reader, found)
        if refused is not None:
            return refused
    if not pending and found.changed and args.get("mode") == "apply":
        return apply(args, ctx, reader, found)
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
