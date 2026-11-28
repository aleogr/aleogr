"""gcp-artifact-registry_registry-describe: the state of a project's image repository in
Artifact Registry. Read-only.

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_artifact_registry_registry_describe.py) and its scenarios. It was
built from skills/gcp-artifact-registry_registry-describe/SKILL.md as that text was
before the skill became a shell over this command (the text is in the repository's
history, at the commit before that change): the same reads, in the same order, the same
states and the same result block."""

import json
import re

FAMILY = "registry"
PROVIDER = "gcp-artifact-registry"
ACTION = "registry-describe"
RESULT_MODE = "plan"  # the skill has no mode: its block always says plan

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_PROJECT = re.compile(r"^[a-z]([a-z0-9-]{0,12}[a-z0-9])?$")
_REGION = re.compile(r"^[a-z]+(-[a-z]+)+[0-9]+$")

WRITER = "roles/artifactregistry.writer"

READ_FAILED = ("The repository could not be read; nothing was changed. Check that the GCP "
               "project %s exists, that the Artifact Registry API is enabled in it, and that "
               "the active gcloud account is signed in and may read its repositories.")
ACCESS_FAILED = ("The repository's access could not be read; nothing was changed. Check that "
                 "the active gcloud account may read the repository's access.")


def _validate(args):
    for key in ("projectId", "project", "region"):
        if not args.get(key):
            return "%s is missing." % key
    if not _PROJECT_ID.match(args["projectId"]):
        return ("projectId is not valid: it must have 6 to 30 characters of a-z, 0-9 and -, "
                "start with a letter and not end with -.")
    if not _PROJECT.match(args["project"]):
        return ("project is not valid: it must have 1 to 14 lowercase letters, digits and -, "
                "start with a letter and not end with -.")
    if not _REGION.match(args["region"]):
        return ("region is not valid: it must be a Google Cloud region name such as "
                "us-central1, not a multi-region.")
    return None


def _json_object(text):
    """The JSON object in `text`, which may follow lines such as `Encryption: ...`."""
    text = text or ""
    for m in re.finditer(r"(?m)^\{", text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _is_missing(c):
    return "NOT_FOUND:" in c.text and "Requested entity was not found" in c.text


def _number(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v == int(v) else v
    try:
        return int(str(v).strip())
    except ValueError:
        return None


def _bool(v):
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return v is True


def _cleanup(data):
    policies = data.get("cleanupPolicies")
    if not isinstance(policies, dict):
        return {"keep": None, "deletesTheRest": False,
                "dryRun": _bool(data.get("cleanupPolicyDryRun")), "rules": 0}
    values = list(policies.values())
    keeps = []
    deletes_rest = False
    for p in values:
        if not isinstance(p, dict):
            continue
        action = p.get("action")
        mrv = p.get("mostRecentVersions")
        if action == "KEEP" and isinstance(mrv, dict) and "packageNamePrefixes" not in mrv:
            keeps.append(mrv)
        cond = p.get("condition")
        if (action == "DELETE" and isinstance(cond, dict) and list(cond.keys()) == ["tagState"]
                and isinstance(cond["tagState"], str) and cond["tagState"].upper() == "ANY"):
            deletes_rest = True
    keep = _number(keeps[0].get("keepCount")) if len(keeps) == 1 else None
    return {"keep": keep, "deletesTheRest": deletes_rest,
            "dryRun": _bool(data.get("cleanupPolicyDryRun")), "rules": len(values)}


def _push(policy):
    out = []
    bindings = policy.get("bindings") if isinstance(policy, dict) else None
    for b in bindings if isinstance(bindings, list) else []:
        if not isinstance(b, dict) or b.get("role") != WRITER or "condition" in b:
            continue
        for m in b.get("members") or []:
            if isinstance(m, str) and m not in out:
                out.append(m)
    return out


def _missing_outputs(other_regions):
    return {
        "exists": False,
        "region": None,
        "otherRegions": other_regions,
        "format": None,
        "labels": {},
        "cleanup": {"keep": None, "deletesTheRest": False, "dryRun": False, "rules": 0},
        "push": [],
        "imagePath": None,
    }


def _cleanup_sentence(c):
    if c["keep"] is None:
        keep = "no single rule says how many versions it keeps"
    else:
        keep = "keeps the %d most recent versions" % c["keep"]
    rest = "deletes the rest" if c["deletesTheRest"] else "does not delete the rest"
    return "Cleanup policy: %s, %s, dry-run %s, %d rule%s." % (
        keep, rest, "on" if c["dryRun"] else "off", c["rules"], "" if c["rules"] == 1 else "s")


def run(args, ctx):
    problem = _validate(args)
    if problem:
        return ctx.failed(problem, {"exists": None})
    project_id = args["projectId"]
    project = args["project"]
    region = args["region"]
    read_failed = READ_FAILED % project_id

    # Step 1: describe the repository in the declared region.
    c = ctx.read(["gcloud", "artifacts", "repositories", "describe", project,
                  "--location=%s" % region, "--project=%s" % project_id, "--format=json"])
    if not c.ok:
        if not _is_missing(c):
            return ctx.failed(read_failed, {"exists": None})
        # Step 2: the same id in other regions.
        ls = ctx.read(["gcloud", "artifacts", "repositories", "list", "--location=all",
                       "--project=%s" % project_id, "--format=value(name)"])
        if not ls.ok:
            return ctx.failed(read_failed, {"exists": None})
        others = []
        for line in ls.out.splitlines():
            line = line.strip()
            if not line.startswith("projects/"):
                continue
            parts = line.split("/")
            if (len(parts) == 6 and parts[2] == "locations" and parts[4] == "repositories"
                    and parts[5] == project and parts[3] != region and parts[3] not in others):
                others.append(parts[3])
        lines = ["The repository %s does not exist in %s." % (project, region)]
        if others:
            lines.append("A repository with the same id exists in %s." % ", ".join(others))
        else:
            lines.append("No repository with that id exists in any other region.")
        return ctx.result("unchanged", _missing_outputs(others), lines=lines)

    data = _json_object(c.out) or _json_object(c.text)
    if data is None:
        return ctx.failed(read_failed, {"exists": None})

    name = data.get("name") if isinstance(data.get("name"), str) else ""
    m = re.match(r"^projects/[^/]+/locations/([^/]+)/repositories/[^/]+$", name)
    read_region = m.group(1) if m else region
    fmt = data.get("format") if isinstance(data.get("format"), str) else None
    labels = data.get("labels") if isinstance(data.get("labels"), dict) else {}
    cleanup = _cleanup(data)

    # Step 3: who may push.
    p = ctx.read(["gcloud", "artifacts", "repositories", "get-iam-policy", project,
                  "--location=%s" % region, "--project=%s" % project_id, "--format=json"])
    if not p.ok:
        return ctx.failed(ACCESS_FAILED, {"exists": None})
    policy = _json_object(p.out)
    if policy is None:
        return ctx.failed(ACCESS_FAILED, {"exists": None})
    push = _push(policy)

    image_path = ("%s-docker.pkg.dev/%s/%s" % (read_region, project_id, project)
                  if fmt == "DOCKER" else None)
    outputs = {
        "exists": True,
        "region": read_region,
        "otherRegions": [],
        "format": fmt,
        "labels": labels,
        "cleanup": cleanup,
        "push": push,
        "imagePath": image_path,
    }
    lines = ["The repository %s exists in %s, with the format %s."
             % (project, read_region, fmt if fmt is not None else "unknown"),
             _cleanup_sentence(cleanup)]
    if push:
        lines.append("Who may push: %s." % ", ".join(push))
    else:
        lines.append("Nobody may push.")
    if image_path:
        lines.append("Image path: %s." % image_path)
    else:
        lines.append("Image path: none, the format is not DOCKER.")
    resources = [{"type": "repository", "id": "%s/%s/%s" % (project_id, read_region, project),
                  "name": project, "labels": labels}]
    return ctx.result("unchanged", outputs, resources=resources, lines=lines)
