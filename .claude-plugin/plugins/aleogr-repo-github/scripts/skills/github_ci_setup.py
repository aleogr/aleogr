"""github_ci-setup: whether `.github/workflows/ci.yml`, in this folder and in the
repository, is as declared. Only mode=plan is converted; mode=apply stays in the
SKILL.md's prose until step 2.

The specification is skills/github_ci-setup/SKILL.md: the same reads, in the same order,
the same states and the same result block. examine() holds steps 1 to 3, shared by both
modes, and kept_commit() the part of step 4 that reads the local file; run() holds the
plan's answer. Step 2 adds steps 4 to 6 (the head read, the write, the verification).
"""

import importlib.util
import os
import re
import sys

FAMILY = "repo"
PROVIDER = "github"
ACTION = "ci-setup"
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

CI_PATH = ".github/workflows/ci.yml"
STACKS = ("go",)
RESERVED_NAMES = ("changes", "ci", "true", "false", "null", "yes", "no", "on", "off")

READ_REFUSED = ("The repository's CI file could not be read; nothing was written. Check that "
                "gh is signed in, may read the repository, and that GitHub answers, then run "
                "this skill again.")
TWO_ENVIRONMENTS = ("deploy names more than one environment; this version deploys to "
                    "exactly one, because the repository secrets the deploy job reads would "
                    "clash.")
NO_REGION = ("deploy needs region=<region>: the deploy jobs write the services' region, "
             "which is never guessed.")
COMPONENTS_WITHOUT_DEPLOY = ("deployComponents is given without deploy; give "
                             "deploy=<environment> as well, or leave deployComponents out.")
UNKNOWN_DEPLOY_COMPONENT = "deployComponents names %s, which is not one of the components."
SERVICE_NAME = ("The service name %s breaks the rule on service names (6 to 30 characters, "
                "not ending with -); shorten the project or the component name.")
NOT_NEEDED_HOW = ("remove .github/workflows/ci.yml by hand and propose the removal with a "
                  "pull request")

_COMPONENT_NAME = re.compile(r"^[a-z][a-z0-9-]{0,19}$")
_PATH_PART = re.compile(r"^[a-z0-9_](?:[a-z0-9_.-]*[a-z0-9_-])?$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,100}$")
_ENVIRONMENT = re.compile(r"^[a-z][a-z0-9]{0,19}$")
_REGION = re.compile(r"^[a-z](?:[a-z0-9-]{0,28}[a-z0-9])?$")
_PROJECT = re.compile(r"^[a-z](?:[a-z0-9-]{0,12}[a-z0-9])?$")


class Declared(object):
    """The valid arguments: components sorted by name (empty path replaced by name)."""

    def __init__(self, components, workflows, ref, branch, deploy, deploy_components,
                 region, project):
        self.components = components  # [(name, path, stack, version)], sorted by name
        self.workflows = workflows
        self.ref = ref
        self.branch = branch
        self.deploy = deploy  # [] or [environment]
        self.deploy_components = deploy_components  # sorted
        self.region = region
        self.project = project

    @property
    def marker(self):
        if not self.components:
            return None
        entries = ",".join(":".join(c) for c in self.components)
        if not self.deploy:
            return "# aleogr-ci 1 " + entries
        return "# aleogr-ci 2 %s deploy=%s:%s project=%s branch=%s region=%s" % (
            entries, self.deploy[0], "+".join(self.deploy_components), self.project,
            self.branch, self.region)


def _components(value):
    """(sorted components, None) or (None, the sentence of the rule broken)."""
    if value == "":
        return [], None
    out = []
    for entry in value.split(","):
        if entry == "":
            return None, "components is not valid: it has an empty entry."
        fields = entry.split(":")
        if len(fields) != 4:
            return None, ("components is not valid: the entry %s is not "
                          "<name>:<path>:<stack>:<version>." % entry)
        name, path, stack, version = fields
        if (not _COMPONENT_NAME.match(name) or name in RESERVED_NAMES
                or name.startswith("deploy-")):
            return None, ("components is not valid: the name %s must have 1 to 20 characters "
                          "of a-z, 0-9 and -, start with a letter, not start with deploy- and "
                          "not be changes, ci, true, false, null, yes, no, on or off." % name)
        if any(c[0] == name for c in out):
            return None, "components is not valid: the name %s is given twice." % name
        path = path or name
        if not all(_PATH_PART.match(p) and p not in (".", "..") for p in path.split("/")):
            return None, ("components is not valid: the path of %s must be parts of a-z, "
                          "0-9, -, _ and . separated by /, none starting with - or . nor "
                          "ending with ." % name)
        if stack not in STACKS:
            return None, ("components is not valid: the stack of %s must be go, the only "
                          "stack implemented." % name)
        if not _VERSION.match(version):
            return None, ("components is not valid: the version of %s must be like 1.27."
                          % name)
        for other in out:
            q = other[1]
            if path == q:
                return None, ("components is not valid: %s and %s have the same path."
                              % (other[0], name))
            if path.startswith(q + "/") or q.startswith(path + "/"):
                return None, ("components is not valid: the path of %s is inside the path of "
                              "%s." % ((name, other[0]) if path.startswith(q + "/")
                                       else (other[0], name)))
        out.append((name, path, stack, version))
    return sorted(out, key=lambda c: c[0].encode("utf-8")), None


def validate(args):
    """(Declared, None) or (None, the sentence)."""
    components_value = args.get("components", "")
    deploy_value = args.get("deploy", "")
    keys = ["owner", "name"]
    if components_value:
        keys.append("workflows")
    if deploy_value:
        keys += ["project", "deployComponents"]
    problem = G.first_missing(args, keys)
    if problem:
        return None, problem
    if deploy_value and not args.get("region"):
        return None, NO_REGION
    problem = G.owner_name_problem(args)
    if problem:
        return None, problem
    workflows = args.get("workflows")
    if workflows is not None:
        parts = workflows.split("/")
        if len(parts) != 2 or not G.owner_ok(parts[0]) or not G.name_ok(parts[1]):
            return None, ("workflows is not valid: it must be <owner>/<name>, with the rules "
                          "of owner and name.")
    components, problem = _components(components_value)
    if problem:
        return None, problem
    ref = args.get("ref", "keep")
    if ref not in ("keep", "latest"):
        return None, "ref is not valid: it must be keep or latest."
    branch = args.get("defaultBranch", "main")
    if (not _BRANCH.match(branch) or branch[0] in "-/" or branch[-1] in "/."
            or ".." in branch or "//" in branch):
        return None, ("defaultBranch is not valid: it must have 1 to 100 characters of A-Z, "
                      "a-z, 0-9, ., _, - and /, not start with - or /, not end with / or ., "
                      "and have no .. and no //.")
    deploy = []
    if deploy_value:
        deploy = deploy_value.split(",")
        if not all(_ENVIRONMENT.match(e) for e in deploy):
            return None, ("deploy is not valid: each environment must have 1 to 20 "
                          "characters of a-z and 0-9 and start with a letter.")
        if len(deploy) > 1:
            return None, TWO_ENVIRONMENTS
        if not _REGION.match(args["region"]):
            return None, ("region is not valid: it must have 1 to 30 characters of a-z, 0-9 "
                          "and -, start with a letter and not end with -.")
        if not _PROJECT.match(args["project"]):
            return None, ("project is not valid: it must have 1 to 14 characters of a-z, 0-9 "
                          "and -, start with a letter and not end with -.")
    deploy_components = []
    if "deployComponents" in args:
        if not deploy:
            return None, COMPONENTS_WITHOUT_DEPLOY
        listed = args["deployComponents"].split(",")
        if "" in listed:
            return None, "deployComponents is not valid: it has an empty entry."
        if len(set(listed)) != len(listed):
            return None, "deployComponents is not valid: it names a component twice."
        names = [c[0] for c in components]
        for n in listed:
            if n not in names:
                return None, UNKNOWN_DEPLOY_COMPONENT % n
        deploy_components = sorted(listed, key=lambda n: n.encode("utf-8"))
        for n in deploy_components:
            service = "%s-%s" % (args["project"], n)
            if not 6 <= len(service) <= 30 or n.endswith("-"):
                return None, SERVICE_NAME % service
    problem = G.mode_problem(args)
    if problem:
        return None, problem
    return Declared(components, workflows, ref, branch, deploy, deploy_components,
                    args.get("region"), args.get("project")), None


def outputs(declared=None, local=None, in_repository=None, as_declared=None, ref=None,
            written=False):
    valid = declared is not None and bool(declared.components)
    return {
        "path": CI_PATH,
        "local": local,
        "inRepository": in_repository,
        "repositoryAsDeclared": as_declared,
        "marker": declared.marker if declared is not None else None,
        "ref": ref,
        "written": written,
        "checks": ["ci"] if valid else [],
        "deploy": list(declared.deploy) if valid else [],
        "deployComponents": list(declared.deploy_components) if valid and declared.deploy
        else [],
    }


class Found(object):
    """What steps 1 to 3 found."""

    def __init__(self, local, content, in_repository, as_declared):
        self.local = local  # as-declared, missing, differs or not-needed
        self.content = content  # the local file's text, or None when missing
        self.in_repository = in_repository
        self.as_declared = as_declared


def examine(declared, args, ctx, reader):
    """Steps 1 to 3. A Found, or a Result (failed)."""
    full = "%s/%s" % (args["owner"], args["name"])

    def failed(lines):
        return ctx.result("failed", outputs(declared), cost=G.NO_COST, lines=lines)

    # Step 1: the local file (read as a file, never with a shell command).
    content, why = G.read_local(CI_PATH)
    if why == "unreadable":
        return failed(["The local file %s could not be read." % CI_PATH] + reader.notes)

    # Step 2: the repository's copy, from its default branch.
    c = reader.gh(["gh", "api", "repos/%s/contents/%s" % (full, CI_PATH),
                   "-H", "Accept: application/vnd.github.raw"])
    first = G.gh_first_read_failure(c)
    if first:
        return failed([first] + reader.notes)
    if G.http(c, 404):
        in_repository, as_declared = False, None
    elif not c.ok:
        return failed([READ_REFUSED])  # that sentence is all the answer says
    else:
        in_repository = True
        as_declared = bool(declared.components) and G.first_line(c.out) == declared.marker

    # Step 3: local.
    if not declared.components:
        local = "not-needed" if content is None else "differs"
    elif content is None:
        local = "missing"
    elif G.first_line(content) == declared.marker:
        local = "as-declared"
    else:
        local = "differs"
    return Found(local, content, in_repository, as_declared)


def kept_commit(declared, content):
    """Step 4 without its command: the commit that `ref=keep` keeps from the local file,
    or None when the head of the workflows repository's main must be read."""
    if declared.ref != "keep" or content is None:
        return None
    if declared.deploy and not G.first_line(content).startswith("# aleogr-ci 2 "):
        return None
    base = r"^\s*uses: %s/\.github/workflows/" % re.escape(declared.workflows)
    stacks = "|".join(re.escape(s) for s in sorted(set(c[2] for c in declared.components)))
    kinds = [re.compile(base + r"ci-(?:%s)\.yml@([0-9a-f]{40})\s*$" % stacks, re.M)]
    if declared.deploy:
        kinds.append(re.compile(base + r"deploy-cloud-run\.yml@([0-9a-f]{40})\s*$", re.M))
    commits = set()
    for kind in kinds:
        found = kind.findall(content)
        if not found:
            return None
        commits.update(found)
    return commits.pop() if len(commits) == 1 else None


def run(args, ctx):
    declared, problem = validate(args)
    if problem:
        return ctx.failed(problem, outputs(), cost=G.NO_COST)
    reader = G.Reader(ctx)
    found = examine(declared, args, ctx, reader)
    if not isinstance(found, Found):
        return found

    out = outputs(declared, found.local, found.in_repository, found.as_declared)
    pending = []
    lines = []
    if found.local == "not-needed":
        status = "unchanged"
        lines.append("No component is declared and this folder has no %s: none is needed."
                     % CI_PATH)
    elif not declared.components:
        status = "pending"
        pending.append(G.pending_item("ci.yml is not needed", NOT_NEEDED_HOW))
        lines.append("No component is declared, but this folder has %s: it is left as it "
                     "is; remove it by hand and propose the removal with a pull request."
                     % CI_PATH)
    elif found.local == "as-declared":
        status = "unchanged"
        lines.append("The file %s in this folder is as declared." % CI_PATH)
    else:
        if found.local == "missing":
            status = "would-create"
            lines.append("The file %s is missing in this folder: apply would write it."
                         % CI_PATH)
        else:
            status = "would-update"
            lines.append("The file %s in this folder is not as declared: apply would "
                         "rewrite it whole." % CI_PATH)
        sha = kept_commit(declared, found.content)
        if sha:
            lines.append("apply would keep the commit %s that the file pins." % sha)
        else:
            lines.append("apply would pin the head of the branch main of %s, read when it "
                         "runs." % declared.workflows)
    if found.in_repository:
        lines.append("The repository's copy on its default branch is %s."
                     % ("as declared" if found.as_declared else "not as declared"))
    else:
        lines.append("The repository has no %s on its default branch." % CI_PATH)
    if declared.components:
        lines.append("Nothing is committed or pushed: the file goes to the repository with "
                     "the pull request.")
    return ctx.result(status, out, pending=pending, cost=G.NO_COST, lines=lines + reader.notes)
