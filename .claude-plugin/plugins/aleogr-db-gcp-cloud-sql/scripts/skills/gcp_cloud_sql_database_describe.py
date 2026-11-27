"""gcp-cloud-sql_database-describe: an aleogr project's database on the shared Cloud SQL
instance, its users and their connection roles. Read-only.

The specification is skills/gcp-cloud-sql_database-describe/SKILL.md: the same reads, in
the same order, the same states and the same result block. The result block holds no
e-mail: accounts are written by their position.
"""

import json
import re

FAMILY = "db"
PROVIDER = "gcp-cloud-sql"
ACTION = "database-describe"
RESULT_MODE = "plan"  # the skill has no mode: its block always says plan

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_INSTANCE = re.compile(r"^[a-z][a-z0-9-]{0,59}$")
_PROJECT = re.compile(r"^[a-z]([a-z0-9-]{0,12}[a-z0-9])?$")
_ACCOUNT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]"
                      r"\.iam\.gserviceaccount\.com$")
_ENVIRONMENTS = ("dev", "hom", "prd")
_ARGS = ("sharedProjectId", "instance", "project", "environment", "accounts")

CLIENT = "roles/cloudsql.client"
INSTANCE_USER = "roles/cloudsql.instanceUser"

INSTANCE_FAILED = ("The instance %s of the shared project could not be read; nothing was "
                   "changed. Check that it exists and that the active gcloud account may read it.")
POLICY_FAILED = ("The access policy of the shared project could not be read; nothing was "
                 "changed. Check that the active gcloud account may read it.")
LISTS_FAILED = ("The databases and users of the instance %s could not be read although it is "
                "running; nothing was changed.")
NOT_READ = "The database and its users were not read: the shared instance is %s."
OPS_NOT_CHECKED = "Pending operations could not be checked."


def database_name(project, environment):
    return "%s_%s" % (project.replace("-", "_"), environment)


def user_name(account):
    return account[:-len(".gserviceaccount.com")]


def _validate(args):
    """(sentences, database): every broken rule's sentence, in table order."""
    problems = []
    for key in _ARGS:
        if not args.get(key):
            problems.append("%s is missing." % key)
    v = args.get("sharedProjectId")
    if v and not _PROJECT_ID.match(v):
        problems.append("sharedProjectId is not a GCP project id.")
    v = args.get("instance")
    if v and not _INSTANCE.match(v):
        problems.append("instance must have 1 to 60 lowercase letters, digits and hyphens, "
                        "starting with a letter.")
    project_ok = bool(args.get("project")) and bool(_PROJECT.match(args["project"]))
    if args.get("project") and not project_ok:
        problems.append("project must have 1 to 14 lowercase letters, digits and hyphens, "
                        "starting with a letter and not ending with a hyphen.")
    env_ok = args.get("environment") in _ENVIRONMENTS
    if args.get("environment") and not env_ok:
        problems.append("environment must be dev, hom or prd.")
    if args.get("accounts"):
        seen = set()
        for n, entry in enumerate(args["accounts"].split(","), 1):
            if not _ACCOUNT.match(entry):
                problems.append("Entry %d of accounts is not the address of a service account "
                                "(<id>@<project id>.iam.gserviceaccount.com)." % n)
                continue
            if entry in seen:
                problems.append("Entry %d of accounts is given twice." % n)
                continue
            seen.add(entry)
            length = len(user_name(entry))
            if length > 63:
                problems.append("The database user of entry %d of accounts would have %d "
                                "characters: PostgreSQL allows 63." % (n, length))
    database = database_name(args["project"], args["environment"]) if (
        project_ok and env_ok) else None
    return problems, database


def _state(policy, state):
    """The state table of gcp-cloud-sql_instance-describe (before the operations)."""
    if policy == "NEVER":
        return "stopped"
    if policy == "ALWAYS":
        if state == "RUNNABLE":
            return "running"
        if state == "PENDING_CREATE":
            return "creating"
        return "starting"
    return "unknown"


def _holders(policy, role):
    """The lowercased members of every binding of exactly `role`, condition or not."""
    out = set()
    bindings = policy.get("bindings") if isinstance(policy, dict) else None
    for b in bindings if isinstance(bindings, list) else []:
        if isinstance(b, dict) and b.get("role") == role:
            for m in b.get("members") or []:
                if isinstance(m, str):
                    out.add(m.lower())
    return out


def _lines_of(text):
    return set(line.strip() for line in (text or "").splitlines() if line.strip())


def _outputs(state, database, exists, users, read):
    return {"instanceState": state, "database": database, "databaseExists": exists,
            "users": users, "read": read}


def _account_sentence(n, account, item):
    if item["user"] is None:
        user = "not read as a user of the instance"
    elif item["user"]:
        user = "a user of the instance"
    else:
        user = "not a user of the instance"
    if item["client"] and item["instanceUser"]:
        roles = "both %s and %s" % (CLIENT, INSTANCE_USER)
    elif item["client"]:
        roles = "%s only" % CLIENT
    elif item["instanceUser"]:
        roles = "%s only" % INSTANCE_USER
    else:
        roles = "neither %s nor %s" % (CLIENT, INSTANCE_USER)
    return "Account %d (%s): %s; it holds %s." % (n, account, user, roles)


def run(args, ctx):
    problems, database = _validate(args)
    if problems:
        return ctx.failed(problems, _outputs(None, database, None, [], False))
    shared = args["sharedProjectId"]
    instance = args["instance"]
    accounts = args["accounts"].split(",")
    resources = [{"type": "instance", "id": "%s/%s" % (shared, instance), "name": instance,
                  "labels": {}}]

    # Step 1: the instance and its state.
    c = ctx.read(["gcloud", "sql", "instances", "describe", instance,
                  "--project=%s" % shared, "--format=json"])
    data = None
    if c.ok:
        try:
            data = json.loads(c.out)
        except ValueError:
            data = None
    if not isinstance(data, dict):
        return ctx.failed(INSTANCE_FAILED % instance, _outputs(None, database, None, [], False))
    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    policy = settings.get("activationPolicy")
    state = _state(policy, data.get("state"))
    notes = []
    if policy == "ALWAYS" and data.get("state") == "RUNNABLE":
        ops = ctx.read(["gcloud", "sql", "operations", "list", "--instance=%s" % instance,
                        "--project=%s" % shared, "--filter=status!=DONE", "--limit=10",
                        "--format=value(operationType,status)"])
        if not ops.ok:
            notes.append(OPS_NOT_CHECKED)
        elif any(line.split()[:1] == ["UPDATE"] for line in ops.out.splitlines()):
            state = "starting"

    # Step 2: the shared project's policy, whatever the state.
    p = ctx.read(["gcloud", "projects", "get-iam-policy", shared, "--format=json"])
    iam = None
    if p.ok:
        try:
            iam = json.loads(p.out)
        except ValueError:
            iam = None
    if not isinstance(iam, dict):
        return ctx.failed(notes + [POLICY_FAILED], _outputs(state, database, None, [], False),
                          resources=resources)
    clients = _holders(iam, CLIENT)
    instance_users = _holders(iam, INSTANCE_USER)
    users = []
    for n, account in enumerate(accounts, 1):
        member = ("serviceAccount:%s" % account).lower()
        users.append({"account": n, "user": None, "client": member in clients,
                      "instanceUser": member in instance_users})

    # Step 3: the databases and the users, only while running.
    exists = None
    read = False
    if state == "running":
        dbs = ctx.read(["gcloud", "sql", "databases", "list", "--instance=%s" % instance,
                        "--project=%s" % shared, "--format=value(name)"])
        if not dbs.ok:
            return ctx.failed(notes + [LISTS_FAILED % instance],
                              _outputs(state, database, None, users, False),
                              resources=resources)
        exists = database in _lines_of(dbs.out)
        us = ctx.read(["gcloud", "sql", "users", "list", "--instance=%s" % instance,
                       "--project=%s" % shared, "--format=value(name)"])
        if not us.ok:
            return ctx.failed(notes + [LISTS_FAILED % instance],
                              _outputs(state, database, exists, users, False),
                              resources=resources)
        names = _lines_of(us.out)
        for item, account in zip(users, accounts):
            item["user"] = user_name(account) in names
        read = True

    lines = ["The shared instance %s is %s." % (instance, state)]
    if state == "unknown":
        if policy is None:
            lines.append("Its activation policy is absent.")
        else:
            lines.append("Its activation policy is %s, which is not a known value." % policy)
    lines.extend(notes)
    if read:
        lines.append("The database %s %s." % (database, "exists" if exists else "does not exist"))
    else:
        lines.append(NOT_READ % state)
    for n, (account, item) in enumerate(zip(accounts, users), 1):
        lines.append(_account_sentence(n, account, item))
    return ctx.result("unchanged", _outputs(state, database, exists, users, read),
                      resources=resources, lines=lines)
