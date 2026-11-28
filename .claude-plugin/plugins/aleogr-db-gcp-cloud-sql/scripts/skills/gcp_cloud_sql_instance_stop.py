"""gcp-cloud-sql_instance-stop: stop a running Cloud SQL instance (activation policy
NEVER). It has no mode: it acts when invoked, so it runs as mode=apply and `--read-only`
refuses it.

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_cloud_sql_instance_stop.py) and its scenarios. It was built from
skills/gcp-cloud-sql_instance-stop/SKILL.md as that text was before the skill became a
shell over this command (the text is in the repository's history, at the commit before
that change): the same check (the describe skill, invoked), the same patch, the same one
verification, the same states and the same result block. The patch runs through
ctx.write only: its shape is on the allowlist of writes of this skill alone (with
instance-create's own stop)."""

import json
import re

FAMILY = "db"
PROVIDER = "gcp-cloud-sql"
ACTION = "instance-stop"
WRITES = True
DEFAULT_MODE = "apply"  # no mode argument: every run acts, or fails before acting
RESULT_MODE = "apply"  # "mode is always apply: the skill acts"

PLUGIN = "aleogr-db-gcp-cloud-sql"
DESCRIBE = "gcp-cloud-sql_instance-describe"
COST = {"fixed": True, "notes": "about R$ 50 per month while stopped"}
COST_LINE = "It costs about R$ 50 per month while stopped."

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_INSTANCE = re.compile(r"^[a-z][a-z0-9-]{0,59}$")

NO_MODE = ("mode is not an argument of gcp-cloud-sql_instance-stop: it has no mode and "
           "acts when invoked.")


def _validate(args):
    """None, or the one sentence of the first argument missing or wrong."""
    for key in ("projectId", "instance"):
        if not args.get(key):
            return "%s is missing." % key
    if not _PROJECT_ID.match(args["projectId"]):
        return ("projectId is not valid: it must have 6 to 30 characters of a-z, 0-9 and -, "
                "start with a letter and not end with -.")
    if not _INSTANCE.match(args["instance"]):
        return ("instance is not valid: it must be lowercase letters, digits and -, "
                "start with a letter, at most 60 characters.")
    # The dispatcher reads `mode`: anything but apply would be a run that may not write.
    if "mode" in args and args["mode"] != "apply":
        return NO_MODE
    return None


def state_of(data):
    """The skill's state from the describe JSON ("Reading the state")."""
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    policy = settings.get("activationPolicy")
    if policy == "NEVER":
        return "stopped"
    if policy == "ALWAYS":
        state = data.get("state")
        if state == "RUNNABLE":
            return "running"
        if state == "PENDING_CREATE":
            return "creating"
        return "starting"
    return "unknown"


def _cause(c):
    """One sentence's cause of a failed gcloud command, with no raw error text."""
    t = c.text.lower()
    if c.code == 127 or "command not found" in t:
        return "gcloud is not installed"
    if ("auth login" in t or "credentials" in t or "reauthentication" in t
            or "not currently have an active account" in t):
        return "gcloud is not authenticated"
    if "403" in t or "permission" in t or "not authorized" in t or "forbidden" in t:
        return "the active gcloud account is not allowed to change it"
    return "gcloud failed"


def patch_command(project_id, instance):
    """Step 2, as the SKILL.md writes it."""
    return ["gcloud", "sql", "instances", "patch", instance, "--project=%s" % project_id,
            "--activation-policy=NEVER", "--quiet"]


def describe_command(project_id, instance):
    """Step 3, as the SKILL.md writes it."""
    return ["gcloud", "sql", "instances", "describe", instance, "--project=%s" % project_id,
            "--format=json"]


def run(args, ctx):
    def outputs(exists=None, state=None):
        return {"exists": exists, "state": state}

    problem = _validate(args)
    if problem:
        return ctx.failed(problem, outputs(), cost=dict(COST))
    project_id = args["projectId"]
    instance = args["instance"]
    resources = [{"type": "instance", "id": "%s/%s" % (project_id, instance),
                  "name": instance, "labels": {}}]

    def failed(sentence, exists=True, state=None, listed=True):
        return ctx.result("failed", outputs(exists, state),
                          resources=resources if listed else [], cost=dict(COST),
                          lines=[sentence])

    # Step 1: the check, by the describe skill (its block is input only).
    found = ctx.call(PLUGIN, DESCRIBE, {"projectId": project_id, "instance": instance})
    out = found.get("outputs") if isinstance(found.get("outputs"), dict) else {}
    if found.get("status") == "failed" or out.get("exists") not in (True, False):
        answer = found.get("answer") or []
        cause = answer[0] if answer and isinstance(answer[0], str) else (
            "The instance %s could not be read." % instance)
        return failed(cause, exists=None, listed=False)
    if out.get("exists") is False:
        return failed("The instance %s does not exist in %s, so it was not stopped."
                      % (instance, project_id), exists=False, listed=False)
    state = out.get("state")
    if state == "stopped":
        return ctx.result("unchanged", outputs(True, "stopped"), resources=resources,
                          cost=dict(COST),
                          lines=["The Cloud SQL instance %s in %s was already stopped; "
                                 "nothing was changed." % (instance, project_id), COST_LINE])
    if state == "creating":
        return failed("The instance %s is still being created: wait for the creation to "
                      "end, then run this skill again." % instance, state="creating")

    # Step 2: stop it (running, starting or unknown).
    c = ctx.write(patch_command(project_id, instance))
    if not c.ok:
        return failed("The instance %s could not be stopped: %s." % (instance, _cause(c)),
                      state=state)

    # Step 3: one verification, never repeated.
    c = ctx.read(describe_command(project_id, instance))
    data = None
    if c.ok:
        try:
            data = json.loads(c.out)
        except ValueError:
            data = None
    if not isinstance(data, dict):
        return failed("The instance %s was asked to stop, but it could not be read "
                      "afterwards to confirm it." % instance, state=state)
    seen = state_of(data)
    if seen != "stopped":
        return failed("The instance %s was asked to stop, but it is %s." % (instance, seen),
                      state=seen)
    return ctx.result("updated", outputs(True, "stopped"), resources=resources,
                      cost=dict(COST),
                      lines=["The Cloud SQL instance %s in %s is now stopped."
                             % (instance, project_id), COST_LINE])
