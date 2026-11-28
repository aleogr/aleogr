"""github_repo-describe: the state of a GitHub repository and of its ruleset `main`.
Read-only.

The rules are this module's, pinned by its unit tests
(tests/unit/test_github_repo_describe.py) and its scenarios. It was built from
skills/github_repo-describe/SKILL.md as that text was before the skill became a shell
over this command (the text is in the repository's history, at the commit before that
change): the same reads, in the same order, the same states and the same result block."""

import importlib.util
import json
import os
import sys

FAMILY = "repo"
PROVIDER = "github"
ACTION = "repo-describe"
RESULT_MODE = "plan"  # the skill has no mode: its block always says plan


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

RULESET_FILES = {"none": "ruleset-main.json", "ci": "ruleset-main-ci.json"}
COMPARED_KEYS = ("target", "enforcement", "bypass_actors", "conditions", "rules")


def _unknown_outputs(exists):
    """Before or at step 1: nothing is known (exists null) or the repository is absent."""
    return {
        "exists": exists,
        "id": None,
        "ownerId": None,
        "url": None,
        "visibility": None,
        "defaultBranch": None,
        "description": None,
        "topics": [],
        "settings": None,
        "protection": None,
    }


def _failed_protection():
    return {"state": None, "rulesetId": None, "matches": None, "requiredChecks": [],
            "otherRulesets": []}


def _validate(args):
    problem = G.first_missing(args, ("owner", "name"))
    if problem:
        return problem
    problem = G.owner_name_problem(args)
    if problem:
        return problem
    if "checks" in args and args["checks"] not in ("ci", "none"):
        return "checks is not valid: it must be ci or none."
    return None


def _number(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _flag(v):
    return v if isinstance(v, bool) else None


def _text(v):
    return v if isinstance(v, str) else None


# ---------------------------------------------------------------------------
# The comparison with the ruleset file (the rule the other skills of this plugin use)


def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"))


def _contexts(items):
    if not isinstance(items, list):
        return None
    out = set()
    for x in items:
        if not isinstance(x, dict):
            return None
        out.add(_canon(x.get("context")))
    return out


def _same(want, got, key=None):
    """`got` equals `want` on the keys `want` has; every list is a set."""
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return False
        for k, v in want.items():
            if k not in got:
                return False
            if not _same(v, got[k], k):
                return False
        return True
    if isinstance(want, list):
        if key == "required_status_checks":
            return _contexts(want) == _contexts(got) and _contexts(got) is not None
        if not isinstance(got, list):
            return False
        return set(_canon(x) for x in want) == set(_canon(x) for x in got)
    return G.json_equal(want, got)


def _rules_match(want, got):
    if not isinstance(want, list) or not isinstance(got, list):
        return False
    if not all(isinstance(r, dict) for r in got):
        return False
    got_types = [r.get("type") for r in got]
    want_types = [r.get("type") for r in want]
    if sorted(map(_canon, got_types)) != sorted(map(_canon, want_types)):
        return False  # exactly the file's types, each once
    if len(set(map(_canon, got_types))) != len(got_types):
        return False
    by_type = dict((_canon(r.get("type")), r) for r in got)
    return all(_same(r, by_type[_canon(r.get("type"))]) for r in want)


def ruleset_matches(want, got):
    """protection.matches: the read ruleset `got` against the plugin's file `want`."""
    for k in COMPARED_KEYS:
        if k not in want:
            continue
        if k == "bypass_actors":
            a = want.get(k) or []
            b = got.get(k) or []
            if not isinstance(a, list) or not isinstance(b, list):
                return False
            if set(map(_canon, a)) != set(map(_canon, b)):
                return False
        elif k == "rules":
            if not _rules_match(want[k], got.get(k)):
                return False
        else:
            if k not in got or not _same(want[k], got[k], k):
                return False
    return True


def required_checks(got):
    rules = got.get("rules")
    found = set()
    if isinstance(rules, list):
        for r in rules:
            if isinstance(r, dict) and r.get("type") == "required_status_checks":
                params = r.get("parameters") if isinstance(r.get("parameters"), dict) else {}
                checks = params.get("required_status_checks")
                for c in checks if isinstance(checks, list) else []:
                    if isinstance(c, dict) and isinstance(c.get("context"), str):
                        found.add(c["context"])
    return sorted(found)


# ---------------------------------------------------------------------------


def run(args, ctx):
    problem = _validate(args)
    if problem:
        return ctx.failed(problem, _unknown_outputs(None))
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    ruleset_file = RULESET_FILES[args.get("checks") or "none"]
    reader = G.Reader(ctx)

    def failed(sentence, outputs, resources=()):
        return ctx.result("failed", outputs, resources=resources,
                          lines=[sentence] + reader.notes)

    # Step 1: the repository.
    c = reader.gh(["gh", "api", "repos/%s" % full])
    first = G.gh_first_read_failure(c)
    if first:
        return failed(first, _unknown_outputs(None))
    if G.http(c, 404):
        return ctx.result("unchanged", _unknown_outputs(False), lines=[
            "The repository %s does not exist, or this account cannot see it." % full]
            + reader.notes)
    if not c.ok:
        return failed("The repository %s could not be read: %s." % (full, G.gh_cause(c)),
                      _unknown_outputs(None))
    repo = G.json_of(c.out)
    if not isinstance(repo, dict):
        return failed("The repository %s could not be read: gh did not give a JSON object."
                      % full, _unknown_outputs(None))
    owner_obj = repo.get("owner") if isinstance(repo.get("owner"), dict) else {}
    topics = repo.get("topics")
    outputs = {
        "exists": True,
        "id": _number(repo.get("id")),
        "ownerId": _number(owner_obj.get("id")),
        "url": _text(repo.get("html_url")),
        "visibility": _text(repo.get("visibility")),
        "defaultBranch": _text(repo.get("default_branch")),
        "description": _text(repo.get("description")) or None,
        "topics": sorted(t for t in topics if isinstance(t, str))
        if isinstance(topics, list) else [],
        "settings": {
            "mergeCommit": _flag(repo.get("allow_merge_commit")),
            "squash": _flag(repo.get("allow_squash_merge")),
            "rebase": _flag(repo.get("allow_rebase_merge")),
            "deleteBranchOnMerge": _flag(repo.get("delete_branch_on_merge")),
            "issues": _flag(repo.get("has_issues")),
            "wiki": _flag(repo.get("has_wiki")),
            "projects": _flag(repo.get("has_projects")),
        },
        "protection": _failed_protection(),
    }
    resources = [G.repository_resource(owner, name)]

    def failed_later(sentence):
        outputs["protection"] = _failed_protection()
        return failed(sentence, outputs, resources)

    # Step 2: the rulesets.
    c = reader.gh(["gh", "api", "repos/%s/rulesets" % full])
    protection = {"state": None, "rulesetId": None, "matches": None, "requiredChecks": [],
                  "otherRulesets": []}
    main_id = None
    if c.ok:
        listed = G.json_of(c.out)
        if not isinstance(listed, list):
            return failed_later("The rulesets of %s could not be read: gh did not give a "
                                "JSON list." % full)
        mains = [r for r in listed if isinstance(r, dict) and r.get("name") == "main"]
        others = sorted(r.get("name") for r in listed
                        if isinstance(r, dict) and r.get("name") != "main"
                        and isinstance(r.get("name"), str))
        if len(mains) > 1:
            return failed_later("Two rulesets of %s are named main." % full)
        protection["otherRulesets"] = others
        if mains:
            main_id = mains[0].get("id")
        else:
            protection["state"] = "unprotected"
    elif G.http(c, 403) and "Upgrade" in c.text:
        protection["state"] = "unavailable"
    else:
        return failed_later("The rulesets of %s could not be read: %s."
                            % (full, G.gh_cause(c)))

    # Step 3: the ruleset main, compared with the plugin's file.
    if main_id is not None:
        c = reader.gh(["gh", "api", "repos/%s/rulesets/%s" % (full, main_id)])
        if not c.ok:
            return failed_later("The ruleset main of %s could not be read: %s."
                                % (full, G.gh_cause(c)))
        got = G.json_of(c.out)
        if not isinstance(got, dict):
            return failed_later("The ruleset main of %s could not be read: gh did not give "
                                "a JSON object." % full)
        text, _ = G.read_local(ctx.plugin_path("files", ruleset_file))
        want = G.json_of(text) if text is not None else None
        if text is None:
            return failed_later("The plugin's file %s could not be read." % ruleset_file)
        if not isinstance(want, dict):
            return failed_later("The plugin's file %s is not valid JSON." % ruleset_file)
        protection["state"] = "protected"
        protection["rulesetId"] = main_id
        protection["matches"] = ruleset_matches(want, got)
        protection["requiredChecks"] = required_checks(got)
    outputs["protection"] = protection

    lines = ["The repository %s exists: %s." % (full, outputs["url"] or "no address given"),
             "Visibility %s, default branch %s." % (outputs["visibility"] or "unknown",
                                                    outputs["defaultBranch"] or "unknown")]
    state = protection["state"]
    if state == "protected":
        lines.append("Branch protection: the ruleset main exists and %s %s."
                     % ("matches" if protection["matches"] else "does not match",
                        ruleset_file))
    elif state == "unprotected":
        lines.append("Branch protection: no ruleset is named main.")
    else:
        lines.append("Branch protection: unavailable, because rulesets need a paid plan or a "
                     "public repository.")
    return ctx.result("unchanged", outputs, resources=resources, lines=lines + reader.notes)
