"""gcp-cloud-sql_instance-create: create the shared platform's Cloud SQL instance, wait
for it, leave it stopped (by this skill's patch, or by running the night-stop job
`stopJob`, which proves the night stop) and verify it (mode=apply with confirm=yes), or
say what would be created (mode=plan).

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_cloud_sql_instance_create.py) and its scenarios. It was built from
skills/gcp-cloud-sql_instance-create/SKILL.md as that text was before the skill became a
shell over this command (the text is in the repository's history, at the commit before
that change): the same check (the describe skill, invoked), the same create, the same
waits, the same stop and the same one verification, the same states and the same result
block. The instance has a fixed monthly cost: nothing is created without mode=apply and
confirm=yes, checked in code before the create command is built.

Waits go through ctx.wait() only, inside the eight-minute budget of one run (16 waits).
The SKILL.md waits up to 20 minutes for the creation and up to 5 for the night stop: a
budget spent while the instance is still being created ends exactly as step 5's own
timeout does (pending, the instance left running and charged until it is stopped, and
the instance-stop command); a budget spent while waiting for the job's stop is "still not
stopped after 5 minutes": the skill falls back to its own patch, as step 6 says.

From the moment the create command exits zero until a describe shows the instance
stopped, a run aborted by its time limit or an unexpected error (common.aborted_result)
says what its own timeout says: the instance exists, runs and is charged by the hour
until it is stopped, and the command that stops it (ctx.on_abort).

`resume=yes` (with mode=apply and confirm=yes; any other value fails validation) is for
the caller whose own run asked for this creation in an earlier command, ended by the
run's clock before the instance was stopped (aleogr:platform-apply passes it only then):
when the instance exists, the creation is skipped and the run goes on as its text does
after a creation: it waits for the instance, stops it (with stopJob, by running the job,
which tests the night stop) and verifies it, with the same endings. It is honoured only
for an instance that is not stopped and whose last ten operations (`gcloud sql operations
list`) show its CREATE and nothing else but BACKUP_VOLUME. The skill sets no labels, so
this rule is all it has: an instance whose last ten operations show a stop, a start or
a change is never stopped by resume=yes (gcp-cloud-sql_instance-stop is for that), but an
instance of the same name made by hand, never stopped and recent, would meet the rule
and be stopped. That is why only platform-apply gives the argument, and only for a creation
its own run asked for. When it is not honoured, the run answers as without it (unchanged,
the instance's state, its cost and how to stop it) and says why in one sentence.

With resume=yes the instance is NEVER created: when the check does not find it (a
describe that may lag behind the creation the caller's run asked for) or cannot read it,
the run ends failed, running no write, with one sentence (RESUME_NOT_FOUND): resume=yes
was given and the instance was not found (or could not be read), so nothing was created;
it may exist and run, what it costs, and how to read its state and stop it. Without
resume=yes nothing differs from the skill's text. The write commands are the same in
every case.
"""

import json
import re

import aleogr_common as common

FAMILY = "db"
PROVIDER = "gcp-cloud-sql"
ACTION = "instance-create"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply with confirm=yes creates the instance, through ctx.write only

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_instance-create"
DESCRIBE = "gcp-cloud-sql_instance-describe"
COST = {"fixed": True, "notes": "about R$ 50 per month while stopped"}
COST_LINE = "It costs about R$ 50 per month while stopped."
CREATE_COST_LINE = ("Creating the instance takes several minutes. The instance has a fixed "
                    "cost of about R$ 50 per month while stopped, and it is charged by the "
                    "hour while it runs, until it is stopped.")

# Step 5 waits at most 20 minutes, step 6 at most 5 after the job's run (30 s each).
CREATE_WAITS = 40
JOB_WAITS = 10

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_INSTANCE = re.compile(r"^[a-z][a-z0-9-]{0,59}$")
_VERSION = re.compile(r"^POSTGRES_[0-9]+$")
_INTEGER = re.compile(r"^[0-9]+$")
_HHMM = re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
_STOP_JOB = re.compile(r"^[a-z0-9-]+$")

REQUIRED = ("projectId", "instance", "platform", "version", "tier", "edition", "region",
            "storageGb", "backupStartUtc", "retainedBackups")
ORDER = REQUIRED + ("mode", "confirm", "stopJob", "resume")

PLATFORM_NOT_SHARED = ("platform must be shared: this skill only creates the shared "
                       "platform's instance.")
NOT_RUNNABLE = ("These values cannot be passed to the create command of this skill (edition "
                "enterprise or enterprise-plus, a tier db-..., a region of lowercase letters, "
                "digits and - of at most 63 characters, a version POSTGRES_ with at most 3 "
                "digits, storageGb written without a leading zero), so nothing was created.")
NIGHT_STOP_HOW = ("the night stop does not work: send this output; until it is fixed, stop the "
                  "instance by hand after each use")

# resume=yes (fixed here: the SKILL.md predates it).
RESUME_INVALID = "resume, when given, must be yes."
RESUME_NEEDS_APPLY = "resume=yes needs mode=apply and confirm=yes."
RESUME_LINE = ("The Cloud SQL instance %s in %s exists and is %s: this run goes on from its "
               "creation, with its wait, its stop and its check.")
RESUME_REFUSED = "resume=yes was not used: %s; nothing was changed."
RESUME_STOPPED = "the instance is stopped"
RESUME_CHANGED = ("the instance has had other operations since its creation (it was stopped, "
                  "started or changed), so it is not one this skill has just created")
RESUME_UNREAD = "the operations of the instance could not be read"
# resume=yes and the check does not find the instance (or cannot read it): the caller's own
# plan read it as existing, so a describe that says missing may lag behind its creation.
# The instance is never created then: one sentence, no write. The third %s is "was not
# found" or "could not be read".
RESUME_NOT_FOUND = ("resume=yes was given and the Cloud SQL instance %s in %s %s, so nothing "
                    "was created: it may exist and run, with a fixed cost of about R$ 50 per "
                    "month while stopped, charged by the hour while it runs; read its state "
                    "with %s and stop it with %s.")
RESUME_MISSING = "was not found"
RESUME_NOT_READ = "could not be read"
# What an instance this skill created and has not stopped yet may show among its last
# operations, besides its CREATE.
RESUME_OPERATIONS = ("CREATE", "BACKUP_VOLUME")


def _validate(args):
    """None, or the one sentence of the first rule that fails, in the SKILL.md's order."""
    for key in REQUIRED:
        if not args.get(key):
            if key == "platform":
                return PLATFORM_NOT_SHARED
            return "%s is missing." % key
    if not _PROJECT_ID.match(args["projectId"]):
        return ("projectId is not valid: it must have 6 to 30 characters of a-z, 0-9 and -, "
                "start with a letter and not end with -.")
    if not _INSTANCE.match(args["instance"]):
        return ("instance is not valid: it must be lowercase letters, digits and -, "
                "start with a letter, at most 60 characters.")
    if args["platform"] != "shared":
        return PLATFORM_NOT_SHARED
    if not _VERSION.match(args["version"]):
        return "version is not valid: it must be POSTGRES_ followed by digits, such as POSTGRES_17."
    v = args["storageGb"]
    if not _INTEGER.match(v) or not 10 <= int(v) <= 100:
        return "storageGb is not valid: it must be an integer from 10 to 100."
    if not _HHMM.match(args["backupStartUtc"]):
        return "backupStartUtc is not valid: it must be HH:MM, in 24 hours."
    v = args["retainedBackups"]
    if not _INTEGER.match(v) or not 1 <= int(v) <= 30:
        return "retainedBackups is not valid: it must be an integer from 1 to 30."
    if "mode" in args and args["mode"] not in ("plan", "apply"):
        return "mode must be plan or apply."
    if "confirm" in args and args["confirm"] != "yes":
        return "confirm, when given, must be yes."
    if "stopJob" in args and not _STOP_JOB.match(args["stopJob"]):
        return "stopJob is not valid: it must be lowercase letters, digits and -."
    if "resume" in args:
        if args["resume"] != "yes":
            return RESUME_INVALID
        if args.get("mode") != "apply" or args.get("confirm") != "yes":
            return RESUME_NEEDS_APPLY
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


def _cause(c, verb):
    """One sentence's cause of a failed gcloud command, with no raw error text."""
    t = c.text.lower()
    if c.code == 127 or "command not found" in t:
        return "gcloud is not installed"
    if ("auth login" in t or "credentials" in t or "reauthentication" in t
            or "not currently have an active account" in t):
        return "gcloud is not authenticated"
    if "403" in t or "permission" in t or "not authorized" in t or "forbidden" in t:
        return "the active gcloud account is not allowed to %s it" % verb
    return "gcloud failed"


# The commands, as the SKILL.md writes them.

def create_command(args):
    """Step 4."""
    return ["gcloud", "sql", "instances", "create", args["instance"],
            "--project=%s" % args["projectId"], "--database-version=%s" % args["version"],
            "--edition=%s" % args["edition"], "--tier=%s" % args["tier"],
            "--region=%s" % args["region"], "--availability-type=zonal", "--storage-type=SSD",
            "--storage-size=%s" % args["storageGb"], "--no-storage-auto-increase",
            "--assign-ip", "--backup", "--backup-start-time=%s" % args["backupStartUtc"],
            "--retained-backups-count=%s" % args["retainedBackups"],
            "--no-enable-point-in-time-recovery",
            "--database-flags=cloudsql.iam_authentication=on",
            "--no-enable-dataplex-integration", "--deletion-protection", "--async", "--quiet"]


def describe_command(project_id, instance):
    """Steps 5, 6 and 7."""
    return ["gcloud", "sql", "instances", "describe", instance, "--project=%s" % project_id,
            "--format=json"]


def patch_command(project_id, instance):
    """Step 6, without stopJob (and the fallback after a job that did not stop it)."""
    return ["gcloud", "sql", "instances", "patch", instance, "--project=%s" % project_id,
            "--activation-policy=NEVER", "--quiet"]


def operations_command(project_id, instance):
    """resume=yes: the instance's last ten operations, newest first (a read)."""
    return ["gcloud", "sql", "operations", "list", "--instance=%s" % instance,
            "--project=%s" % project_id, "--sort-by=~insertTime", "--limit=10",
            "--format=value(operationType)"]


def resume_refusal(ctx, project_id, instance, state):
    """None when resume=yes is honoured for this existing instance, else the reason."""
    if state == "stopped":
        return RESUME_STOPPED
    c = ctx.read(operations_command(project_id, instance))
    if not c.ok:
        return RESUME_UNREAD
    types = [line.strip() for line in c.out.splitlines() if line.strip()]
    if "CREATE" not in types or any(t not in RESUME_OPERATIONS for t in types):
        return RESUME_CHANGED
    return None


def job_run_command(args):
    """Step 6, with stopJob."""
    return ["gcloud", "scheduler", "jobs", "run", args["stopJob"],
            "--project=%s" % args["projectId"], "--location=%s" % args["region"], "--quiet"]


def commands_of_apply(args):
    """Every write the apply may run with these arguments."""
    out = [create_command(args), patch_command(args["projectId"], args["instance"])]
    if args.get("stopJob"):
        out.append(job_run_command(args))
    return out


def unrunnable(args, root):
    """Whether a write of the apply would be refused by the allowlist (a value the
    SKILL.md's rules accept but the command's shape does not). Both modes check it."""
    return any(common.write_refusal(SKILL, argv, root=root) for argv in commands_of_apply(args))


def invocation(args, extra=None):
    """This same invocation (the arguments in the table's order), plus `extra`."""
    a = dict(args)
    if extra:
        a.update(extra)
    parts = ["/%s:%s" % (PLUGIN, SKILL)]
    for k in ORDER:
        if k in a:
            parts.append("%s=%s" % (k, a[k]))
    return " ".join(parts)


def stop_how(project_id, instance):
    return "/%s:gcp-cloud-sql_instance-stop projectId=%s instance=%s" % (
        PLUGIN, project_id, instance)


def describe_how(project_id, instance):
    return "/%s:%s projectId=%s instance=%s" % (PLUGIN, DESCRIBE, project_id, instance)


def run(args, ctx):
    mode = args.get("mode") or DEFAULT_MODE

    def outputs(exists=None, state=None):
        return {"exists": exists, "state": state}

    problem = _validate(args)
    if problem:
        return ctx.failed(problem, outputs(), cost=dict(COST),
                          mode=mode if mode in ("plan", "apply") else DEFAULT_MODE)
    project_id = args["projectId"]
    instance = args["instance"]
    stop_job = args.get("stopJob")
    resources = [{"type": "instance", "id": "%s/%s" % (project_id, instance),
                  "name": instance, "labels": {}}]

    # Step 1: the check, by the describe skill (its block is input only).
    found = ctx.call(PLUGIN, DESCRIBE, {"projectId": project_id, "instance": instance})
    out = found.get("outputs") if isinstance(found.get("outputs"), dict) else {}
    resume = args.get("resume") == "yes"
    if resume and (found.get("status") == "failed" or out.get("exists") is not True):
        # resume=yes never creates: the instance may exist and run (a lagging read).
        why = RESUME_MISSING if (found.get("status") != "failed"
                                 and out.get("exists") is False) else RESUME_NOT_READ
        return ctx.failed(RESUME_NOT_FOUND % (instance, project_id, why,
                                              describe_how(project_id, instance),
                                              stop_how(project_id, instance)),
                          outputs(), cost=dict(COST))
    if found.get("status") == "failed" or out.get("exists") not in (True, False):
        answer = found.get("answer") or []
        cause = answer[0] if answer and isinstance(answer[0], str) else (
            "The instance %s could not be read." % instance)
        return ctx.failed(cause, outputs(), cost=dict(COST))
    refused = None
    if out.get("exists") is True and resume and not unrunnable(args, ctx.root):
        refused = resume_refusal(ctx, project_id, instance, out.get("state"))
        if refused is None:
            # resume=yes: the creation is skipped; the run goes on after it.
            return _after_creation(ctx, args, [RESUME_LINE % (instance, project_id,
                                                              out.get("state"))],
                                   resources, outputs)
    if out.get("exists") is True:
        state = out.get("state")
        lines = ["The Cloud SQL instance %s already exists in %s and is %s; nothing was "
                 "changed." % (instance, project_id, state)]
        if refused is not None:
            lines.append(RESUME_REFUSED % refused)
        if state == "stopped":
            lines.append(COST_LINE)
        else:
            lines.append("It is not stopped: it is charged by the hour until it is stopped "
                         "(%s)." % stop_how(project_id, instance))
            lines.append(COST_LINE)
        return ctx.result("unchanged", outputs(True, state), resources=resources,
                          cost=dict(COST), lines=lines)

    # A value the rules accept but no command of the apply would take: neither mode goes on.
    if unrunnable(args, ctx.root):
        return ctx.failed(NOT_RUNNABLE, outputs(False, None), cost=dict(COST))

    # Step 2: the plan.
    if mode == "plan":
        stopper = ("by running the night-stop job %s" % stop_job if stop_job
                   else "by this skill's own command")
        lines = [
            "Would create the Cloud SQL instance %s in %s: %s, tier %s, edition %s, region %s, "
            "%s GB of SSD disk without automatic increase, a daily backup at %s UTC keeping "
            "%s, no point-in-time recovery, deletion protection on, a public address with no "
            "authorized networks and IAM database authentication on."
            % (instance, project_id, args["version"], args["tier"], args["edition"],
               args["region"], args["storageGb"], args["backupStartUtc"],
               args["retainedBackups"]),
            "Then it would be stopped, %s, and verified." % stopper,
            "It would cost about R$ 50 per month while stopped.",
            "This plan changed nothing.",
        ]
        return ctx.result("would-create", outputs(False, None), cost=dict(COST), lines=lines)

    # Step 3: apply without confirm=yes creates nothing (the gate, before any write).
    if args.get("confirm") != "yes":
        how = invocation(args, {"confirm": "yes"})
        return ctx.result(
            "pending", outputs(False, None), cost=dict(COST),
            pending=[{"item": "confirm", "reason": "manual", "how": how}],
            lines=["Nothing was created: the instance has a fixed cost of about R$ 50 per "
                   "month while stopped, so it is created only with confirm=yes. Run it with "
                   "confirm=yes: %s" % how])

    # Step 4: create it (asynchronous). The cost is said before the command's report.
    lines = [CREATE_COST_LINE]
    c = ctx.write(create_command(args))
    if not c.ok:
        lines.append("The instance %s could not be created: %s; nothing was created."
                     % (instance, _cause(c, "create")))
        return ctx.result("failed", outputs(False, None), cost=dict(COST), lines=lines)
    return _after_creation(ctx, args, lines, resources, outputs)


def _after_creation(ctx, args, lines, resources, outputs):
    """Steps 5 to 7, after the create command (or, with resume=yes, after an earlier
    run's): the wait, the stop, the verification, and every ending of them."""
    project_id = args["projectId"]
    instance = args["instance"]
    stop_job = args.get("stopJob")
    stop_item = {"item": "instance", "reason": "manual", "how": stop_how(project_id, instance)}
    running_line = ("It is not stopped: it runs and is charged by the hour until it is "
                    "stopped. Stop it with %s." % stop_how(project_id, instance))
    # The instance exists from here: an aborted run says so, until it is seen stopped.
    ctx.on_abort(["The instance %s was created." % instance, COST_LINE, running_line])
    night_item = {"item": "night stop", "reason": "manual", "how": NIGHT_STOP_HOW}

    def pending(state, said, items=None):
        return ctx.result("pending", outputs(True, state), resources=resources,
                          cost=dict(COST), pending=items or [stop_item],
                          lines=lines + said)

    def describe():
        """The state of one describe, or None when it failed."""
        d = ctx.read(describe_command(project_id, instance))
        data = None
        if d.ok:
            try:
                data = json.loads(d.out)
            except ValueError:
                data = None
        state = state_of(data) if isinstance(data, dict) else None
        if state == "stopped":
            ctx.on_abort([])  # seen stopped: an aborted run leaves nothing charged by the hour
        return state

    # Step 5: wait until it runs (or shows stopped).
    seen = None
    waits = 0
    while True:
        state = describe()
        if state is None:
            return pending(seen, ["The instance %s was created, but it could not be read "
                                  "while waiting for it, so it was not stopped." % instance,
                                  running_line])
        seen = state
        if state in ("running", "stopped"):
            break
        if waits >= CREATE_WAITS or not ctx.wait():
            # The timeout of step 5, also when the run's budget of waiting is spent.
            said = ["The instance %s was created, but it was still %s when this run stopped "
                    "waiting for it, so it was not stopped." % (instance, state), running_line]
            if stop_job:
                said.append("The night stop was not tested.")
            return pending(state, said)
        waits += 1

    if seen == "stopped":
        # Already stopped: no stop command, no job; step 7 verifies.
        night = ["The night stop was not tested: the instance was already stopped."] if (
            stop_job) else []
        return _verify(ctx, args, lines, night, False, pending, describe, resources,
                       outputs, stop_item, running_line, seen)

    # Step 6: stop it.
    if not stop_job:
        c = ctx.write(patch_command(project_id, instance))
        if not c.ok:
            return pending(seen, ["The instance %s was created, but it could not be "
                                  "stopped: %s." % (instance, _cause(c, "change")),
                                  running_line])
        return _verify(ctx, args, lines, [], False, pending, describe, resources, outputs,
                       stop_item, running_line, seen)

    c = ctx.write(job_run_command(args))
    if c.ok:
        state = describe()
        waits = 0
        while state is not None and state != "stopped":
            seen = state
            if waits >= JOB_WAITS or not ctx.wait():
                break
            waits += 1
            state = describe()
        if state == "stopped":
            # The night stop is proven, and this describe is step 7's verification.
            return ctx.result("created", outputs(True, "stopped"), resources=resources,
                              cost=dict(COST),
                              lines=lines + ["The Cloud SQL instance %s in %s was created and "
                                             "is now stopped." % (instance, project_id),
                                             "The night stop is proven: the job %s stopped the "
                                             "new instance." % stop_job, COST_LINE])

    # The job did not stop the instance: this skill's own patch, then step 7.
    c = ctx.write(patch_command(project_id, instance))
    if not c.ok:
        return pending(seen, ["The night-stop job %s did NOT stop the instance %s, and the "
                              "instance could not be stopped: %s."
                              % (stop_job, instance, _cause(c, "change")), running_line],
                       [stop_item, night_item])
    return _verify(ctx, args, lines, [], True, pending, describe, resources, outputs,
                   stop_item, running_line, seen)


def _verify(ctx, args, lines, night, job_failed, pending, describe, resources, outputs,
            stop_item, running_line, seen):
    """Step 7: one describe. `created` only when it shows stopped and the job did not
    fail (job_failed: step 6 fell back to the patch)."""
    project_id, instance, stop_job = args["projectId"], args["instance"], args.get("stopJob")
    night_item = {"item": "night stop", "reason": "manual", "how": NIGHT_STOP_HOW}
    state = describe()
    if state == "stopped":
        if job_failed:
            return pending("stopped", [
                "The instance %s exists and is stopped, but the night-stop job %s did NOT stop "
                "it." % (instance, stop_job), COST_LINE], [night_item])
        return ctx.result("created", outputs(True, "stopped"), resources=resources,
                          cost=dict(COST),
                          lines=lines + ["The Cloud SQL instance %s in %s was created and is "
                                         "now stopped." % (instance, project_id)]
                          + night + [COST_LINE])
    if state is None:
        said = ["The instance %s was created and asked to stop, but it could not be read "
                "afterwards to confirm it." % instance]
    else:
        said = ["The instance %s was created and asked to stop, but it is %s." % (instance,
                                                                                 state)]
    said.append(running_line)
    items = [stop_item]
    last = state if state is not None else seen
    if job_failed:
        said.insert(0, "The night-stop job %s did NOT stop the instance %s." % (stop_job,
                                                                                 instance))
        items.append(night_item)
    return pending(last, said, items)
