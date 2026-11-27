"""github_branch-protect: makes the repository ruleset `main` equal to the plugin's
ruleset file and verifies it (mode=apply), or says what a run would do (mode=plan).

The specification is skills/github_branch-protect/SKILL.md: the same reads (steps 1, 2
and 4), the same file (step 3), the same decision (step 5), the same write (step 6, POST
or PUT, its body always the plugin's file passed with --input) and the same verification
(step 7), each at most once, and the same result block. The write runs through the
writing runner only (Reader.write, then ctx.write), so only in mode=apply. A ruleset with
another name is never read, changed or deleted.
"""

import importlib.util
import json
import os
import re
import sys

sys.dont_write_bytecode = True

FAMILY = "repo"
PROVIDER = "github"
ACTION = "branch-protect"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply creates or updates the ruleset main, through ctx.write only


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

RULESET_FILES = {"none": "ruleset-main.json", "ci": "ruleset-main-ci.json"}
COMPARED_KEYS = ("target", "enforcement", "bypass_actors", "conditions", "rules")
COST = {"fixed": False, "notes": "no cost"}

PLAN_LIMIT = ("Branch protection needs a paid plan or a public repository: the GitHub plan "
              "of %s does not allow rulesets on it, so nothing was changed.")


# ---------------------------------------------------------------------------
# Arguments


def validate(args):
    problem = G.first_missing(args, ("owner", "name"))
    if problem:
        return problem
    problem = G.owner_name_problem(args)
    if problem:
        return problem
    problem = G.mode_problem(args)
    if problem:
        return problem
    if "checks" in args and args["checks"] not in ("ci", "none"):
        return "checks is not valid: it must be ci or none."
    return None


# ---------------------------------------------------------------------------
# The comparison with the ruleset file (step 4's rule, the one github_repo-describe uses),
# which also says what differs.


def _canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _contexts(items):
    if not isinstance(items, list):
        return None
    out = set()
    for x in items:
        if not isinstance(x, dict):
            return None
        out.add(_canon(x.get("context")))
    return out


def _found(path, got, want):
    return "%s: found %s, the file has %s" % (path, _canon(got), _canon(want))


def _diff(want, got, path, key, out):
    """Each difference of `got` from `want` on the keys `want` has; every list is a set."""
    if isinstance(want, dict):
        if not isinstance(got, dict):
            out.append(_found(path, got, want))
            return
        for k, v in want.items():
            sub = "%s.%s" % (path, k)
            if k not in got:
                out.append("%s: absent, the file has %s" % (sub, _canon(v)))
            else:
                _diff(v, got[k], sub, k, out)
        return
    if isinstance(want, list):
        if key == "required_status_checks":
            g = _contexts(got)
            if g is None or g != _contexts(want):
                out.append("%s: found the checks %s, the file has %s"
                           % (path, _canon(sorted(g)) if g is not None else _canon(got),
                              _canon(sorted(_contexts(want) or []))))
            return
        if not isinstance(got, list) or (set(_canon(x) for x in want)
                                         != set(_canon(x) for x in got)):
            out.append(_found(path, got, want))
        return
    if not G.json_equal(want, got):
        out.append(_found(path, got, want))


def _rules_diff(want, got, out):
    if not isinstance(got, list) or not all(isinstance(r, dict) for r in got):
        out.append(_found("rules", got, want))
        return
    got_types = [_canon(r.get("type")) for r in got]
    want_types = [_canon(r.get("type")) for r in want if isinstance(r, dict)]
    for t in want_types:
        if t not in got_types:
            out.append("the rule %s is missing" % json.loads(t))
    for t in sorted(set(got_types)):
        if t not in want_types:
            out.append("the rule %s is not in the file" % json.loads(t))
        elif got_types.count(t) > 1:
            out.append("the rule %s is there more than once" % json.loads(t))
    by_type = dict((_canon(r.get("type")), r) for r in got)
    for r in want:
        t = _canon(r.get("type"))
        if t in by_type and got_types.count(t) == 1:
            _diff(r, by_type[t], "rules[%s]" % json.loads(t), None, out)


def differences(want, got):
    """What differs between the read ruleset `got` and the plugin's file `want`: [] when
    every compared key is equal."""
    out = []
    for k in COMPARED_KEYS:
        if k not in want:
            continue
        if k == "bypass_actors":
            a = want.get(k) or []
            b = got.get(k) or []
            if (not isinstance(a, list) or not isinstance(b, list)
                    or set(map(_canon, a)) != set(map(_canon, b))):
                out.append(_found(k, got.get(k), want.get(k)))
        elif k == "rules":
            _rules_diff(want[k], got.get(k), out)
        elif k not in got:
            out.append("%s: absent, the file has %s" % (k, _canon(want[k])))
        else:
            _diff(want[k], got[k], k, k, out)
    return out


# ---------------------------------------------------------------------------
# Outputs


def _rules(ruleset):
    r = ruleset.get("rules")
    return r if isinstance(r, list) else []


def described(ruleset):
    """rules, requiredApprovals and requiredChecks of a ruleset (read, or the file)."""
    types, approvals, checks = set(), None, set()
    for r in _rules(ruleset):
        if not isinstance(r, dict):
            continue
        t = r.get("type")
        if isinstance(t, str):
            types.add(t)
        params = r.get("parameters") if isinstance(r.get("parameters"), dict) else {}
        if t == "pull_request":
            n = params.get("required_approving_review_count")
            approvals = n if isinstance(n, int) and not isinstance(n, bool) else None
        elif t == "required_status_checks":
            items = params.get("required_status_checks")
            for c in items if isinstance(items, list) else []:
                if isinstance(c, dict) and isinstance(c.get("context"), str):
                    checks.add(c["context"])
    return {"rules": sorted(types), "requiredApprovals": approvals,
            "requiredChecks": sorted(checks)}


def outputs_of(ruleset_id, source, others):
    out = {"rulesetId": ruleset_id}
    if source is None:
        out.update({"rules": [], "requiredApprovals": None, "requiredChecks": []})
    else:
        out.update(described(source))
    out["otherRulesets"] = list(others)
    return out


def resources_of(ruleset_id):
    if ruleset_id is None:
        return []
    return [{"type": "ruleset", "id": str(ruleset_id), "name": "main"}]


def _ruleset_id(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


# ---------------------------------------------------------------------------
# Commands


def write_command(full, ruleset_id, path):
    """Step 6: POST without an id (create), PUT with it (update); the body is the file."""
    if ruleset_id is None:
        return ["gh", "api", "--method", "POST", "repos/%s/rulesets" % full, "--input", path]
    return ["gh", "api", "--method", "PUT", "repos/%s/rulesets/%d" % (full, ruleset_id),
            "--input", path]


def shown_command(argv):
    """The command as the SKILL.md writes it: the file of --input in double quotes."""
    return " ".join(argv[:-1] + ['"%s"' % argv[-1]])


def _write_cause(c):
    """The cause of a refused write, in a few words of our own: no HTTP code, no API
    message."""
    t = c.text.lower()
    if G.not_installed(c):
        return "gh could not be started"
    if G.not_logged_in(c):
        return "gh is not logged in"
    if "rate limit" in t or "http 429" in t:
        return "the GitHub API rate limit was reached"
    if "http 403" in t or "forbidden" in t or "admin" in t or "not accessible" in t:
        return "this account is not allowed to change the repository's rulesets"
    if "http 422" in t or "validation" in t:
        return "GitHub did not accept the ruleset"
    if "http 404" in t:
        return "GitHub did not find the repository or the ruleset"
    if re.search(r"http 5[0-9][0-9]", t):
        return "GitHub answered with an error of its own"
    if any(w in t for w in ("could not resolve", "no such host", "connection refused",
                            "timed out", "timeout", "dial tcp", "network is unreachable",
                            "connection reset", "tls")):
        return "GitHub could not be reached"
    return "gh failed"


def _plan_limit(c):
    return (not c.ok) and G.http(c, 403) and "Upgrade" in c.text


# ---------------------------------------------------------------------------


def run(args, ctx):
    problem = validate(args)
    if problem:
        return ctx.failed(problem, outputs_of(None, None, []), cost=dict(COST))
    owner, name = args["owner"], args["name"]
    full = "%s/%s" % (owner, name)
    ci = args.get("checks") == "ci"
    ruleset_file = RULESET_FILES["ci" if ci else "none"]
    suffix = " checks=ci" if ci else ""
    reader = G.Reader(ctx)
    others = []

    def ended(status, lines, ruleset_id=None, source=None, pending=()):
        return ctx.result(status, outputs_of(ruleset_id, source, others),
                          resources=resources_of(ruleset_id), pending=pending,
                          cost=dict(COST), lines=lines + reader.notes)

    def failed(sentence, ruleset_id=None, source=None):
        return ended("failed", [sentence], ruleset_id, source)

    def plan_limited(ruleset_id=None, source=None):
        how = ("make %s public (/aleogr-repo-github:github_repo-configure owner=%s name=%s "
               "visibility=public mode=apply) or move the owner to a paid plan, then run "
               "/aleogr-repo-github:github_branch-protect owner=%s name=%s mode=apply%s"
               % (full, owner, name, owner, name, suffix))
        item = {"item": "branch protection needs a paid plan or a public repository",
                "reason": "plan-limit", "how": how}
        return ended("pending", [PLAN_LIMIT % full], ruleset_id, source, [item])

    # Step 1: the repository.
    c = reader.gh(["gh", "api", "repos/%s" % full])
    first = G.gh_first_read_failure(c)
    if first:
        return failed(first)
    if G.http(c, 404):
        return failed("The repository %s does not exist, or this account cannot see it: "
                      "there is nothing to protect; github_repo-create creates it." % full)
    if not c.ok:
        return failed("The repository %s could not be read: %s; nothing was changed."
                      % (full, G.gh_cause(c)))

    # Step 2: its rulesets.
    c = reader.gh(["gh", "api", "repos/%s/rulesets" % full])
    if not c.ok:
        if _plan_limit(c):
            return plan_limited()
        return failed("The rulesets of %s could not be read: %s; nothing was changed."
                      % (full, G.gh_cause(c)))
    listed = G.json_of(c.out)
    if not isinstance(listed, list):
        return failed("The rulesets of %s could not be read: gh did not give a JSON list; "
                      "nothing was changed." % full)
    mains = [r for r in listed if isinstance(r, dict) and r.get("name") == "main"]
    others[:] = sorted(r.get("name") for r in listed
                       if isinstance(r, dict) and isinstance(r.get("name"), str)
                       and r.get("name") != "main")
    if len(mains) > 1:
        return failed("Two rulesets of %s are named main; nothing was changed." % full)
    main_id = None
    if mains:
        main_id = _ruleset_id(mains[0].get("id"))
        if main_id is None:
            return failed("The ruleset main of %s has no usable id; nothing was changed."
                          % full)
    lines = []
    if others:
        lines.append("These other rulesets exist and were left as they are: %s."
                     % ", ".join(others))

    # Step 3: the plugin's ruleset file.
    path = ctx.plugin_path("files", ruleset_file)
    text, _ = G.read_local(path)
    want = G.json_of(text) if text is not None else None
    if text is None:
        return failed("The plugin's file %s could not be read; nothing was changed."
                      % ruleset_file)
    if not isinstance(want, dict):
        return failed("The plugin's file %s is not valid JSON; nothing was changed."
                      % ruleset_file)

    # Step 4: the ruleset main, compared with the file.
    now = None
    diffs = []
    if main_id is not None:
        c = reader.gh(["gh", "api", "repos/%s/rulesets/%d" % (full, main_id)])
        if not c.ok:
            return failed("The ruleset main of %s could not be read: %s; nothing was "
                          "changed." % (full, G.gh_cause(c)))
        now = G.json_of(c.out)
        if not isinstance(now, dict):
            return failed("The ruleset main of %s could not be read: gh did not give a JSON "
                          "object; nothing was changed." % full)
        diffs = differences(want, now)
        if not diffs:
            return ended("unchanged", ["The ruleset main of %s already matches %s; nothing "
                                       "was changed." % (full, ruleset_file)] + lines,
                         main_id, now)
    differ_line = ("The ruleset main differs from %s: %s." % (ruleset_file, "; ".join(diffs))
                   if diffs else None)

    # Step 5: decide.
    command = write_command(full, main_id, path)
    if args.get("mode") != "apply":
        if main_id is None:
            out = ["There is no ruleset main on %s; apply would create it from %s with this "
                   "command:" % (full, ruleset_file)]
            out += G.shown([shown_command(command)])
            return ended("would-create", out + lines, None, want)
        out = [differ_line, "apply would update it from the file with this command:"]
        out += G.shown([shown_command(command)])
        return ended("would-update", out + lines, main_id, now)

    # Step 6: write the ruleset from the file.
    c = reader.write(command)
    if not c.ok:
        if _plan_limit(c):
            return plan_limited(main_id, now)
        return ended("failed", ["The ruleset main of %s was not written: %s; nothing was "
                                "changed." % (full, _write_cause(c))] + lines, main_id, now)
    status = "created" if main_id is None else "updated"
    if main_id is None:
        answer = G.json_of(c.out)
        main_id = _new_id(answer)
        head = ["The ruleset main of %s was created from %s." % (full, ruleset_file)]
    else:
        head = ["The ruleset main of %s was updated from %s." % (full, ruleset_file),
                differ_line.replace("differs", "differed", 1)]

    # Step 7: verify, once.
    verify = G.pending_item("verify", "/aleogr-repo-github:github_repo-describe owner=%s "
                                      "name=%s%s" % (owner, name, suffix))
    if main_id is None:
        return ended(status, head + ["GitHub's answer gave no id for the new ruleset, so it "
                                     "could not be verified."] + lines, None, want, [verify])
    c = reader.gh(["gh", "api", "repos/%s/rulesets/%d" % (full, main_id)])
    after = G.json_of(c.out) if c.ok else None
    if not isinstance(after, dict):
        return ended(status, head + ["The ruleset could not be read back to verify it."]
                     + lines, main_id, want, [verify])
    left = differences(want, after)
    if left:
        item = G.pending_item("branch protection differs",
                              "/aleogr-repo-github:github_branch-protect owner=%s name=%s "
                              "mode=apply%s" % (owner, name, suffix))
        return ended(status, head + ["After the write, the ruleset still differs from %s: "
                                     "%s." % (ruleset_file, "; ".join(left))] + lines,
                     main_id, after, [item])
    return ended(status, head + lines, main_id, after)


def _new_id(answer):
    return _ruleset_id(answer.get("id")) if isinstance(answer, dict) else None
