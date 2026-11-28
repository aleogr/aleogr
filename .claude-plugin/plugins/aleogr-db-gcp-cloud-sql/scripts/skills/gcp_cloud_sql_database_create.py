"""gcp-cloud-sql_database-create: make an aleogr project's database for one environment on
the shared Cloud SQL instance when it is missing (mode=apply), or say whether it would be
made (mode=plan). It never starts, stops or changes the instance: on an instance that is
not running it runs no other command and ends pending.

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_cloud_sql_database_create.py) and its scenarios. It was built from
skills/gcp-cloud-sql_database-create/SKILL.md as that text was before the skill became a
shell over this command (the text is in the repository's history, at the commit before
that change): the same reads in the same order (the instance, its pending operations only
for ALWAYS with RUNNABLE, the databases only while running), the one create, the one list
after it that decides, the prescribed sentences word for word and the same result block.
The create runs through ctx.write only. No failure's text is ever read to decide or
quoted."""

import json
import re

import aleogr_common as common

FAMILY = "db"
PROVIDER = "gcp-cloud-sql"
ACTION = "database-create"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply creates the database, through ctx.write only

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_database-create"
COST = {"fixed": False,
        "notes": "a database adds no cost of its own; the instance costs by the hour while it runs"}

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_INSTANCE = re.compile(r"^[a-z][a-z0-9-]{0,59}$")
_PROJECT = re.compile(r"^[a-z]([a-z0-9-]{0,12}[a-z0-9])?$")
_ENVIRONMENTS = ("dev", "hom", "prd")

# The sentences the SKILL.md writes in backquotes, word for word.
INSTANCE_FAILED = ("The instance %s of the shared project could not be read; nothing was "
                   "changed. Check that it exists and that the active gcloud account may read it.")
LIST_FAILED = ("The databases of the instance %s could not be read although it is running; "
               "nothing was changed.")
CREATE_FAILED_BUT_EXISTS = "The command that creates the database %s failed, but the database exists."
NOT_FOUND_AFTER = ("The database %s was not found after its creation. Run this same skill again "
                   "to check.")
NOT_CREATED = "The database %s could not be created on the instance %s."
FAILED_UNREAD = ("The command that creates the database %s failed and the databases could not "
                 "be read: it may exist. Run this same skill again to check.")
OPS_NOT_CHECKED = "Pending operations could not be checked."
NOT_RUNNABLE = ("The database %s cannot be created by this command with these values, so "
                "nothing was changed.")

# Step 2: by the state, the item's how and the answer's sentence.
NOT_RUNNING = {
    "stopped": ("/aleogr:project-apply confirm=yes",
                "The shared instance is stopped: the database is made only while it runs; "
                "/aleogr:project-apply confirm=yes starts it."),
    "starting": ("Wait a few minutes, then /aleogr:project-plan.",
                 "The shared instance is starting: the database is made once it runs. Wait a "
                 "few minutes, then run /aleogr:project-plan."),
    "creating": ("Wait a few minutes, then /aleogr:project-plan.",
                 "The shared instance is creating: the database is made once it runs. Wait a "
                 "few minutes, then run /aleogr:project-plan."),
    "unknown": ("/aleogr:platform-plan",
                "The state of the shared instance is not one this skill knows: the database is "
                "made only while it runs. Run /aleogr:platform-plan."),
}


def database_name(project, environment):
    return "%s_%s" % (project.replace("-", "_"), environment)


def _validate(args):
    """(sentences, database): each broken rule's sentence, in the table's order."""
    problems = []
    rules = [
        ("sharedProjectId", lambda v: _PROJECT_ID.match(v),
         "sharedProjectId is not a GCP project id."),
        ("instance", lambda v: _INSTANCE.match(v),
         "instance must have 1 to 60 lowercase letters, digits and hyphens, starting with a "
         "letter."),
        ("project", lambda v: _PROJECT.match(v),
         "project must have 1 to 14 lowercase letters, digits and hyphens, starting with a "
         "letter and not ending with a hyphen."),
        ("environment", lambda v: v in _ENVIRONMENTS, "environment must be dev, hom or prd."),
    ]
    for key, ok, sentence in rules:
        v = args.get(key)
        if not v:
            problems.append("%s is missing." % key)
        elif not ok(v):
            problems.append(sentence)
    if "mode" in args and args["mode"] not in ("plan", "apply"):
        problems.append("mode must be plan or apply.")
    project, env = args.get("project"), args.get("environment")
    database = database_name(project, env) if (
        project and _PROJECT.match(project) and env in _ENVIRONMENTS) else None
    return problems, database


def state_of(policy, state):
    """The state table of step 1 (before the pending operations)."""
    if policy == "NEVER":
        return "stopped"
    if policy == "ALWAYS":
        if state == "RUNNABLE":
            return "running"
        if state == "PENDING_CREATE":
            return "creating"
        return "starting"
    return "unknown"


def describe_command(shared, instance):
    return ["gcloud", "sql", "instances", "describe", instance, "--project=%s" % shared,
            "--format=json"]


def operations_command(shared, instance):
    return ["gcloud", "sql", "operations", "list", "--instance=%s" % instance,
            "--project=%s" % shared, "--filter=status!=DONE", "--limit=10",
            "--format=value(operationType,status)"]


def list_command(shared, instance):
    return ["gcloud", "sql", "databases", "list", "--instance=%s" % instance,
            "--project=%s" % shared, "--format=value(name)"]


def create_command(database, shared, instance):
    """Step 4, as the SKILL.md writes it: no --async, no --charset, no --collation."""
    return ["gcloud", "sql", "databases", "create", database, "--instance=%s" % instance,
            "--project=%s" % shared, "--quiet"]


def read_state(ctx, shared, instance):
    """Step 1: (state, notes), or (None, notes) when the describe failed."""
    c = ctx.read(describe_command(shared, instance))
    data = None
    if c.ok:
        try:
            data = json.loads(c.out)
        except ValueError:
            data = None
    if not isinstance(data, dict):
        return None, []
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    policy = settings.get("activationPolicy")
    state = state_of(policy, data.get("state"))
    notes = []
    if policy == "ALWAYS" and data.get("state") == "RUNNABLE":
        ops = ctx.read(operations_command(shared, instance))
        if not ops.ok:
            notes.append(OPS_NOT_CHECKED)
        elif any(line.split()[:1] == ["UPDATE"] for line in ops.out.splitlines()):
            state = "starting"
    return state, notes


def _listed(c, database):
    return any(line.strip() == database for line in c.out.splitlines())


def run(args, ctx):
    mode = args.get("mode") or DEFAULT_MODE
    problems, database = _validate(args)

    def outputs(state=None, exists=None):
        return {"instanceState": state, "database": database, "exists": exists}

    if problems:
        return ctx.failed(problems, outputs(), cost=dict(COST),
                          mode=mode if mode in ("plan", "apply") else DEFAULT_MODE)
    shared = args["sharedProjectId"]
    instance = args["instance"]
    instance_res = {"type": "instance", "id": "%s/%s" % (shared, instance), "name": instance,
                    "labels": {}}
    database_res = {"type": "database", "id": "%s/%s/%s" % (shared, instance, database),
                    "name": database, "labels": {}}

    # Step 1: the instance and its state.
    state, notes = read_state(ctx, shared, instance)
    if state is None:
        return ctx.failed(INSTANCE_FAILED % instance, outputs(), cost=dict(COST))
    lines = ["The shared instance %s is %s." % (instance, state)] + notes

    # Step 2: not running: nothing else runs.
    if state != "running":
        how, sentence = NOT_RUNNING[state]
        item = {"item": "instance",
                "reason": "The shared instance is %s: the database is made only while it runs."
                % state, "how": how}
        return ctx.result("pending", outputs(state, None), resources=[instance_res],
                          cost=dict(COST), pending=[item],
                          lines=lines + [sentence, "Nothing was changed."])

    # Step 3: the databases.
    c = ctx.read(list_command(shared, instance))
    if not c.ok:
        return ctx.result("failed", outputs(state, None), resources=[instance_res],
                          cost=dict(COST), lines=lines + [LIST_FAILED % instance])
    if _listed(c, database):
        return ctx.result("unchanged", outputs(state, True),
                          resources=[instance_res, database_res], cost=dict(COST),
                          lines=lines + ["The database %s exists; nothing was changed."
                                         % database])

    # The create's shape, checked in both modes before the plan announces it.
    create = create_command(database, shared, instance)
    if common.write_refusal(SKILL, create, root=ctx.root):
        return ctx.result("failed", outputs(state, False), resources=[instance_res],
                          cost=dict(COST), lines=lines + [NOT_RUNNABLE % database])
    if mode == "plan":
        return ctx.result("would-create", outputs(state, False), resources=[instance_res],
                          cost=dict(COST),
                          lines=lines + ["The database %s does not exist: it would be created. "
                                         "This plan changed nothing." % database])

    # Step 4: the one create of this run.
    made = ctx.write(create)

    # Step 5: one list decides, whatever the create's exit.
    v = ctx.read(list_command(shared, instance))
    if not v.ok:
        if made.ok:
            item = {"item": "database",
                    "reason": "The database could not be read after its creation.",
                    "how": "/%s:%s sharedProjectId=%s instance=%s project=%s environment=%s "
                           "mode=apply" % (PLUGIN, SKILL, shared, instance, args["project"],
                                           args["environment"])}
            return ctx.result("created", outputs(state, None), resources=[instance_res],
                              cost=dict(COST), pending=[item],
                              lines=lines + ["The database %s was created; it could not be "
                                             "read afterwards to confirm it." % database])
        return ctx.result("failed", outputs(state, None), resources=[instance_res],
                          cost=dict(COST), lines=lines + [FAILED_UNREAD % database])
    if _listed(v, database):
        said = ["The database %s was created by this run." % database] if made.ok else [
            CREATE_FAILED_BUT_EXISTS % database]
        return ctx.result("created", outputs(state, True), resources=[instance_res, database_res],
                          cost=dict(COST), lines=lines + said)
    said = NOT_FOUND_AFTER % database if made.ok else NOT_CREATED % (database, instance)
    return ctx.result("failed", outputs(state, False), resources=[instance_res],
                      cost=dict(COST), lines=lines + [said])
