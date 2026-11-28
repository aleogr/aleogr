"""github_ci-setup: whether `.github/workflows/ci.yml`, in this folder and in the
repository, is as declared (mode=plan); in mode=apply, writes that file when it is
missing or differs.

The rules are this module's, pinned by its unit tests
(tests/unit/test_github_ci_setup.py) and its scenarios. It was built from
skills/github_ci-setup/SKILL.md as that text was before the skill became a shell over
this command (the text is in the repository's history, at the commit before that
change): the same reads, in the same order, the same states and the same result block.
examine() holds steps 1 to 3, shared by both modes, and kept_commit() the part of step 4
that reads the local file; run() holds the plan's answer; apply() holds steps 4 to 6
(the head read, the write through ctx.write_file, the verification), and ci_yml() the
text of step 5."""

import importlib.util
import os
import re
import sys

FAMILY = "repo"
PROVIDER = "github"
ACTION = "ci-setup"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply writes .github/workflows/ci.yml, through ctx.write_file only


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


# ---------------------------------------------------------------------------
# mode=apply: steps 4 to 6

CHECKOUT_ACTION = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"
FILTER_ACTION = "dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d # v4.0.3"
_SHA = re.compile(r"^[0-9a-f]{40}$")


def ci_yml(declared, sha):
    """The text of step 5, exactly: built from the sorted components, two spaces per
    indentation level, no trailing space, one line break at the end."""
    comps = declared.components
    branch, workflows = declared.branch, declared.workflows
    lines = [
        declared.marker,
        "# Generated by aleogr from .aleogr/project.json. Do not edit: change the "
        "declaration and run project-apply.",
        "name: ci",
        "",
        "on:",
        "  pull_request:",
        "  push:",
        "    branches: [%s]" % branch,
        "",
        "permissions:",
        "  contents: read",
        "",
        "jobs:",
        "  changes:",
        "    runs-on: ubuntu-latest",
        "    permissions:",
        "      contents: read",
        "      pull-requests: read",
        "    outputs:",
    ]
    for name, _, _, _ in comps:
        lines.append("      %s: ${{ steps.filter.outputs.%s }}" % (name, name))
    lines += [
        "    steps:",
        "      - uses: " + CHECKOUT_ACTION,
        "      - id: filter",
        "        uses: " + FILTER_ACTION,
        "        with:",
        "          filters: |",
    ]
    for name, path, _, _ in comps:
        lines += [
            "            %s:" % name,
            "              - '%s/**'" % path,
            "              - '.github/workflows/ci.yml'",
        ]
    for name, path, stack, version in comps:
        lines += [
            "",
            "  %s:" % name,
            "    needs: changes",
            "    if: needs.changes.outputs.%s == 'true'" % name,
            "    uses: %s/.github/workflows/ci-%s.yml@%s" % (workflows, stack, sha),
            "    with:",
            '      working-directory: "%s"' % path,
            '      go-version: "%s"' % version,
        ]
        if name in declared.deploy_components:
            for environment in declared.deploy:
                lines += [
                    "",
                    "  deploy-%s-%s:" % (name, environment),
                    "    needs: [%s]" % name,
                    "    if: github.event_name == 'push' && github.ref == 'refs/heads/%s' && "
                    "needs.%s.result == 'success'" % (branch, name),
                    "    permissions:",
                    "      contents: read",
                    "      id-token: write",
                    "    uses: %s/.github/workflows/deploy-cloud-run.yml@%s" % (workflows, sha),
                    "    with:",
                    '      working-directory: "%s"' % path,
                    '      service: "%s-%s"' % (declared.project, name),
                    '      image-name: "%s"' % name,
                    '      region: "%s"' % declared.region,
                    "    secrets:",
                    "      project-id: ${{ secrets.GCP_PROJECT_ID }}",
                    "      workload-identity-provider: ${{ secrets.GCP_WIF_PROVIDER }}",
                    "      service-account: ${{ secrets.GCP_CI_ACCOUNT }}",
                    "      image-path: ${{ secrets.GCP_IMAGE_PATH }}",
                ]
    names = ", ".join(c[0] for c in comps)
    results = " ".join("${{ needs.%s.result }}" % c[0] for c in comps)
    lines += [
        "",
        "  ci:",
        "    needs: [changes, %s]" % names,
        "    if: always()",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - name: The change detection passed, and every component job passed or was "
        "skipped",
        "        env:",
        "          CHANGES: ${{ needs.changes.result }}",
        "          RESULTS: %s" % results,
        "        run: |",
        '          if [ "$CHANGES" != "success" ]; then echo "the job changes ended: $CHANGES";'
        ' exit 1; fi',
        "          for r in $RESULTS; do",
        '            case "$r" in success|skipped) ;; *) echo "a component job ended: $r"; '
        "exit 1 ;; esac",
        "          done",
    ]
    return "\n".join(lines) + "\n"


def verify_item(args):
    how = ("/aleogr-repo-github:github_ci-setup owner=%s name=%s components=%s workflows=%s"
           % (args["owner"], args["name"], args.get("components", ""),
              args.get("workflows", "")))
    if args.get("deploy"):
        how += (" deploy=%s deployComponents=%s project=%s region=%s"
                % (args["deploy"], args["deployComponents"], args["project"],
                   args["region"]))
    return G.pending_item("verify", how + " mode=plan")


def _repository_line(found):
    if found.in_repository:
        return ("The repository's copy on its default branch is %s."
                % ("as declared" if found.as_declared else "not as declared"))
    return "The repository has no %s on its default branch." % CI_PATH


def apply(declared, args, ctx, reader, found):
    """Steps 4 to 6: local is missing or differs, with components."""

    def failed(sentence):
        return ctx.result("failed", outputs(declared, found.local, found.in_repository,
                                            found.as_declared),
                          cost=G.NO_COST, lines=[sentence] + reader.notes)

    # Step 4: the commit of the reusable workflow.
    sha = kept_commit(declared, found.content)
    kept = sha is not None
    if not kept:
        c = reader.gh(["gh", "api", "repos/%s/commits/main" % declared.workflows])
        head = G.json_of(c.out) if c.ok else None
        sha = head.get("sha") if isinstance(head, dict) else None
        if not (isinstance(sha, str) and _SHA.match(sha)):
            if G.http(c, 404):
                return failed("The repository %s or its branch main was not found; nothing "
                              "was written." % declared.workflows)
            return failed("The head of the branch main of %s could not be read: %s; nothing "
                          "was written." % (declared.workflows,
                                            G.gh_cause(c) if not c.ok
                                            else "gh gave no commit"))

    # Step 5: write the whole file.
    if not ctx.write_file(CI_PATH, ci_yml(declared, sha)):
        return failed("The file %s could not be written; nothing was written." % CI_PATH)
    status = "created" if found.local == "missing" else "updated"
    lines = []
    if status == "created":
        lines.append("The file %s was missing in this folder: it was written." % CI_PATH)
    else:
        lines.append("The file %s in this folder was not as declared: it was rewritten "
                     "whole." % CI_PATH)
    if kept:
        lines.append("It keeps the commit %s that the file pinned." % sha)
    else:
        lines.append("It pins the commit %s, the head of the branch main of %s."
                     % (sha, declared.workflows))

    # Step 6: verify, once.
    pending = []
    text, _ = G.read_local(CI_PATH)
    if text is None:
        lines.append("The file %s could not be read again to verify it." % CI_PATH)
        pending.append(verify_item(args))
    elif G.first_line(text) != declared.marker:
        lines.append("The file %s, read again, does not start with the marker." % CI_PATH)
        pending.append(verify_item(args))
    lines.append(_repository_line(found))
    lines.append("Nothing was committed or pushed: the file goes to the repository with the "
                 "pull request.")
    return ctx.result(status, outputs(declared, found.local, found.in_repository,
                                      found.as_declared, ref=sha, written=True),
                      pending=pending, cost=G.NO_COST, lines=lines + reader.notes)


def run(args, ctx):
    declared, problem = validate(args)
    if problem:
        return ctx.failed(problem, outputs(), cost=G.NO_COST)
    reader = G.Reader(ctx)
    found = examine(declared, args, ctx, reader)
    if not isinstance(found, Found):
        return found
    if (args.get("mode") == "apply" and declared.components
            and found.local in ("missing", "differs")):
        return apply(declared, args, ctx, reader, found)

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
