"""gcp_environment-describe: the state of the GCP project of a project and environment
(or of the shared platform project). Read-only.

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_environment_describe.py) and its scenarios. It was built from
skills/gcp_environment-describe/SKILL.md as that text was before the skill became a
shell over this command (the text is in the repository's history, at the commit before
that change): the same reads, in the same order, the same states and the same result
block."""

import json
import re

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "environment-describe"
RESULT_MODE = "plan"  # the skill has no mode: its block always says plan

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_ENVIRONMENTS = ("dev", "hom", "prd")

FAILED_OUTPUTS = {"exists": None}
MISSING_OUTPUTS = {"exists": False, "projectId": None, "parent": None, "billingLinked": False,
                   "enabledServices": [], "labels": {}}


def _cause(c):
    """One sentence's cause of a failed gcloud read, with no raw error text."""
    t = c.text.lower()
    if c.code == 127 or "command not found" in t:
        return "gcloud is not installed"
    if ("auth login" in t or "credentials" in t or "reauthentication" in t
            or "not currently have an active account" in t):
        return "gcloud is not authenticated"
    if "service_disabled" in t or "has not been used" in t or "is disabled" in t:
        return "a Google Cloud API it needs is not enabled"
    if "403" in t or "permission" in t or "not authorized" in t or "forbidden" in t:
        return "the active gcloud account is not allowed to read it"
    return "gcloud failed"


def _json_object(text):
    """The JSON object of a read; {} for an empty output; None when it is not JSON."""
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _validate(args):
    """None, or the one sentence of the first rule broken."""
    project = args.get("project") or ""
    environment = args.get("environment") or ""
    platform = args.get("platform") or ""
    project_id = args.get("projectId") or ""
    if environment and environment not in _ENVIRONMENTS:
        return "environment must be dev, hom or prd."
    if platform and platform != "shared":
        return "platform must be shared."
    if project_id:
        if not _PROJECT_ID.match(project_id):
            return ("projectId must have 6 to 30 characters of a-z, 0-9 and -, start with a "
                    "letter and not end with -.")
        return None
    if platform == "shared":
        if project != "shared" or environment:
            return "platform=shared needs project=shared and no environment."
        return None
    if project == "shared":
        return "project=shared needs platform=shared."
    for key in ("project", "environment"):
        if not args.get(key):
            return "%s is missing." % key
    return None


def _parent(data):
    p = data.get("parent")
    if not isinstance(p, dict):
        return None
    kind, ident = p.get("type"), p.get("id")
    if not isinstance(kind, str) or not kind or ident in (None, ""):
        return None
    return "%ss/%s" % (kind, ident)


def run(args, ctx):
    problem = _validate(args)
    if problem:
        return ctx.failed(problem, dict(FAILED_OUTPUTS))
    project_id = args.get("projectId") or ""
    shared = not project_id and args.get("platform") == "shared"

    # Step 1: find the project by its labels (skipped with projectId).
    if not project_id:
        if shared:
            labels_text = "aleogr-project=shared and aleogr-platform=shared"
            flt = "labels.aleogr-project=shared AND labels.aleogr-platform=shared"
        else:
            labels_text = "aleogr-project=%s and aleogr-environment=%s" % (
                args["project"], args["environment"])
            flt = "labels.aleogr-project=%s AND labels.aleogr-environment=%s" % (
                args["project"], args["environment"])
        c = ctx.read(["gcloud", "projects", "list", "--filter=%s" % flt,
                      "--format=value(projectId)"])
        if not c.ok:
            return ctx.failed("The GCP projects could not be listed: %s." % _cause(c),
                              dict(FAILED_OUTPUTS))
        found = [line.strip() for line in c.out.splitlines() if line.strip()]
        if not found:
            return ctx.result("unchanged", dict(MISSING_OUTPUTS), lines=[
                "No GCP project has the labels %s: it does not exist." % labels_text])
        if len(found) > 1:
            return ctx.failed("More than one GCP project has the labels %s (%s): none was "
                              "picked." % (labels_text, ", ".join(found)),
                              dict(FAILED_OUTPUTS))
        project_id = found[0]

    # Step 2: labels and parent.
    c = ctx.read(["gcloud", "projects", "describe", project_id, "--format=json"])
    data = _json_object(c.out) if c.ok else None
    if not c.ok or data is None:
        cause = _cause(c) if not c.ok else "gcloud gave no JSON"
        return ctx.failed("The GCP project %s could not be read: %s." % (project_id, cause),
                          dict(FAILED_OUTPUTS))
    labels = data.get("labels") if isinstance(data.get("labels"), dict) else {}
    parent = _parent(data)

    # Step 3: billing.
    c = ctx.read(["gcloud", "billing", "projects", "describe", project_id,
                  "--format=value(billingEnabled)"])
    if not c.ok:
        return ctx.failed("The billing of the GCP project %s could not be read: %s."
                          % (project_id, _cause(c)), dict(FAILED_OUTPUTS))
    billing = c.out.strip().lower() == "true"

    # Step 4: enabled services.
    c = ctx.read(["gcloud", "services", "list", "--enabled", "--project=%s" % project_id,
                  "--format=value(config.name)"])
    if not c.ok:
        return ctx.failed("The enabled services of the GCP project %s could not be read: %s."
                          % (project_id, _cause(c)), dict(FAILED_OUTPUTS))
    services = sorted(line.strip() for line in c.out.splitlines() if line.strip())

    outputs = {
        "exists": True,
        "projectId": project_id,
        "parent": parent,
        "billingLinked": billing,
        "enabledServices": services,
        "labels": labels,
    }
    name = labels.get("aleogr-project") or args.get("project") or project_id
    resources = [{"type": "project", "id": project_id, "name": name, "labels": labels}]
    n = len(services)
    lines = [
        "The GCP project %s exists, %s." % (
            project_id, "under %s" % parent if parent else "with no parent"),
        "Billing is linked." if billing else "Billing is not linked.",
        "%d service%s enabled." % (n, " is" if n == 1 else "s are"),
    ]
    return ctx.result("unchanged", outputs, resources=resources, lines=lines)
