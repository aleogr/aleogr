"""gcp-cloud-sql_instance-start: start a stopped Cloud SQL instance (activation policy
ALWAYS, asynchronous). It has no mode: it acts when invoked, so it runs as mode=apply and
`--read-only` refuses it. A started instance is charged by the hour until it is stopped.

The specification is skills/gcp-cloud-sql_instance-start/SKILL.md: the same check (the
describe skill, invoked), the same patch, the one read after a failed patch (decided by
the activation policy alone, never by the failure's text), the same one verification,
the same states, the prescribed sentences word for word and the same result block. The
patch runs through ctx.write only: its shape (the only ALWAYS of any skill) is on this
skill's allowlist of writes alone. The SKILL.md names no confirm argument: the gates
before the patch are the arguments and the check of step 1 (state stopped only).

From just before the patch until the run ends with its own answer, a run aborted by its
time limit or an unexpected error (common.aborted_result) also says that a running
instance is charged by the hour, with the command that stops it (ctx.on_abort).
"""

import json
import re

FAMILY = "db"
PROVIDER = "gcp-cloud-sql"
ACTION = "instance-start"
WRITES = True
DEFAULT_MODE = "apply"  # no mode argument: every run acts, or fails before acting
RESULT_MODE = "apply"  # "mode is always apply: the skill acts"

PLUGIN = "aleogr-db-gcp-cloud-sql"
DESCRIBE = "gcp-cloud-sql_instance-describe"
COST = {"fixed": False, "notes": "charged by the hour while running"}

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_INSTANCE = re.compile(r"^[a-z][a-z0-9-]{0,59}$")
_POLICY_LINE = re.compile(r"^Its activation policy is (.*), which is not a known value\.$")

NO_MODE = ("mode is not an argument of gcp-cloud-sql_instance-start: it has no mode and "
           "acts when invoked.")

# The sentences the SKILL.md writes in backquotes, word for word.
NOT_READ = "The instance could not be read, so it was not started."
MISSING = "The instance does not exist, so it was not started."
FAILED_BUT_STARTING = ("The start command failed, but the instance is starting: it is charged "
                       "by the hour until it is stopped.")
FAILED_STILL_STOPPED = ("The instance could not be started: it is still stopped, so it is not "
                        "charged by the hour.")
FAILED_UNREAD = ("The instance could not be started, and the read after the failure could not "
                 "tell whether it is running: it may be charged by the hour until it is "
                 "stopped.")
NIGHT_STOP_LINE = ("This skill does not check the night stop: when it is not set up, the "
                   "instance runs until someone stops it by hand.")


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


def patch_command(project_id, instance):
    """Step 2, as the SKILL.md writes it."""
    return ["gcloud", "sql", "instances", "patch", instance, "--project=%s" % project_id,
            "--activation-policy=ALWAYS", "--async", "--quiet"]


def describe_command(project_id, instance):
    """Step 3 (and the one read after a failed patch), as the SKILL.md writes it."""
    return ["gcloud", "sql", "instances", "describe", instance, "--project=%s" % project_id,
            "--format=json"]


def _unknown_sentence(instance, answer):
    """One sentence giving the activation policy the describe reported."""
    for line in answer or []:
        if not isinstance(line, str):
            continue
        if line == "Its activation policy is absent.":
            return "The instance %s was not started: its activation policy is absent." % instance
        m = _POLICY_LINE.match(line)
        if m:
            return ("The instance %s was not started: its activation policy is %s, which is "
                    "not a known value." % (instance, m.group(1)))
    return ("The instance %s was not started: its activation policy is not a known value."
            % instance)


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
    describe_how = "/%s:%s projectId=%s instance=%s" % (PLUGIN, DESCRIBE, project_id, instance)
    stop_how = "/%s:gcp-cloud-sql_instance-stop projectId=%s instance=%s" % (
        PLUGIN, project_id, instance)
    cost_line = ("While it runs it is charged by the hour, until it is stopped with %s."
                 % stop_how)

    # Step 1: the check, by the describe skill (its block is input only).
    found = ctx.call(PLUGIN, DESCRIBE, {"projectId": project_id, "instance": instance})
    out = found.get("outputs") if isinstance(found.get("outputs"), dict) else {}
    if found.get("status") == "failed" or out.get("exists") not in (True, False):
        return ctx.failed(NOT_READ, outputs(), cost=dict(COST))
    if out.get("exists") is False:
        return ctx.failed(MISSING, outputs(False, None), cost=dict(COST))
    state = out.get("state")
    if state in ("running", "starting", "creating"):
        return ctx.result("unchanged", outputs(True, state), resources=resources,
                          cost=dict(COST),
                          lines=["The Cloud SQL instance %s in %s is already %s; nothing was "
                                 "changed." % (instance, project_id, state), cost_line,
                                 NIGHT_STOP_LINE])
    if state != "stopped":
        return ctx.result("failed", outputs(True, "unknown"), resources=resources,
                          cost=dict(COST),
                          lines=[_unknown_sentence(instance, found.get("answer"))])

    def read_back():
        """The state and activation policy of one describe; (None, None) when it failed."""
        c = ctx.read(describe_command(project_id, instance))
        data = None
        if c.ok:
            try:
                data = json.loads(c.out)
            except ValueError:
                data = None
        if not isinstance(data, dict):
            return None, None
        settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
        return state_of(data), settings.get("activationPolicy")

    connect = ("It takes about twelve minutes to accept connections; %s shows when it is "
               "running." % describe_how)

    # Step 2: start it. The cost is said before the lines that report the command, and
    # by an aborted run from here on.
    lines = [cost_line]
    ctx.on_abort([cost_line])
    result = _after_patch(ctx, project_id, instance, resources, outputs, lines, connect,
                          describe_how, read_back)
    ctx.on_abort([])  # the run ends with its own answer
    return result


def _after_patch(ctx, project_id, instance, resources, outputs, lines, connect, describe_how,
                 read_back):
    """Steps 2 and 3, from the patch on: the result."""
    c = ctx.write(patch_command(project_id, instance))
    if not c.ok:
        # The one read after a failed patch, decided by the activation policy alone.
        seen, policy = read_back()
        if policy == "ALWAYS":
            return ctx.result("updated", outputs(True, "starting"), resources=resources,
                              cost=dict(COST),
                              lines=lines + [FAILED_BUT_STARTING,
                                             "The Cloud SQL instance %s in %s is starting."
                                             % (instance, project_id), connect,
                                             NIGHT_STOP_LINE])
        if policy == "NEVER":
            return ctx.result("failed", outputs(True, "stopped"), resources=resources,
                              cost=dict(COST), lines=[FAILED_STILL_STOPPED])
        return ctx.result("failed", outputs(True, None), resources=resources, cost=dict(COST),
                          lines=lines + [FAILED_UNREAD,
                                         "%s shows whether it is running." % describe_how])

    # Step 3: one verification, never repeated.
    seen, _policy = read_back()
    if seen is None:
        return ctx.result("updated", outputs(True, None), resources=resources, cost=dict(COST),
                          lines=lines + ["The Cloud SQL instance %s in %s was asked to start, "
                                         "but its state could not be read afterwards."
                                         % (instance, project_id), connect, NIGHT_STOP_LINE])
    if seen == "stopped":
        return ctx.result("updated", outputs(True, "stopped"), resources=resources,
                          cost=dict(COST),
                          lines=lines + ["The Cloud SQL instance %s in %s was asked to start; it "
                                         "still shows stopped, as it may for a moment before "
                                         "starting." % (instance, project_id), connect,
                                         NIGHT_STOP_LINE])
    return ctx.result("updated", outputs(True, "starting"), resources=resources,
                      cost=dict(COST),
                      lines=lines + ["The Cloud SQL instance %s in %s was asked to start: it is "
                                     "starting." % (instance, project_id), connect,
                                     NIGHT_STOP_LINE])
