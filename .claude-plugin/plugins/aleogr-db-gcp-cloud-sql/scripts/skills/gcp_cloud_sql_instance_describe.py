"""gcp-cloud-sql_instance-describe: the state of a Cloud SQL instance. Read-only.

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_cloud_sql_instance_describe.py) and its scenarios. It was built
from skills/gcp-cloud-sql_instance-describe/SKILL.md as that text was before the skill
became a shell over this command (the text is in the repository's history, at the commit
before that change): the same reads, in the same order, the same states and the same
result block."""

import json
import re

FAMILY = "db"
PROVIDER = "gcp-cloud-sql"
ACTION = "instance-describe"
RESULT_MODE = "plan"  # the skill has no mode: its block always says plan

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_INSTANCE = re.compile(r"^[a-z][a-z0-9-]{0,59}$")

def _missing_outputs():
    """Instance does not exist: null, except the counts and booleans (0 and false)."""
    return {
        "exists": False,
        "state": None,
        "databaseVersion": None,
        "edition": None,
        "tier": None,
        "region": None,
        "diskSizeGb": None,
        "storageAutoIncrease": False,
        "publicAddress": False,
        "authorizedNetworks": 0,
        "backupEnabled": False,
        "backupStartUtc": None,
        "deletionProtection": False,
        "knowledgeCatalog": False,
        "lastBackup": None,
    }


def _bool(v):
    """A boolean that is absent from the JSON is false."""
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return v is True


def _number(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return int(str(v).strip())
    except ValueError:
        try:
            return float(str(v).strip())
        except ValueError:
            return None


def _str(v):
    return v if isinstance(v, str) and v != "" else None


def _state(policy, state):
    """The skill's state from settings.activationPolicy and state (before step 2)."""
    if policy == "NEVER":
        return "stopped"
    if policy == "ALWAYS":
        if state == "RUNNABLE":
            return "running"
        if state == "PENDING_CREATE":
            return "creating"
        return "starting"
    return "unknown"


def _cause(c):
    """One sentence's cause of a failed gcloud read, with no raw error text."""
    t = c.text.lower()
    if c.code == 127 or "command not found" in t:
        return "gcloud is not installed"
    if ("auth login" in t or "credentials" in t or "reauthentication" in t
            or "not currently have an active account" in t):
        return "gcloud is not authenticated"
    if "service_disabled" in t or "has not been used" in t or "is disabled" in t:
        return "the Cloud SQL Admin API is not enabled in the project"
    if "403" in t or "permission" in t or "not authorized" in t or "forbidden" in t:
        return "the active gcloud account is not allowed to read it"
    return "gcloud failed"


def _validate(args):
    for key in ("projectId", "instance"):
        if not args.get(key):
            return "%s is missing." % key
    if not _PROJECT_ID.match(args["projectId"]):
        return ("projectId is not valid: it must have 6 to 30 characters of a-z, 0-9 and -, "
                "start with a letter and not end with -.")
    if not _INSTANCE.match(args["instance"]):
        return ("instance is not valid: it must be lowercase letters, digits and -, "
                "start with a letter, at most 60 characters.")
    return None


def run(args, ctx):
    problem = _validate(args)
    if problem:
        return ctx.failed(problem, {"exists": None})
    project_id = args["projectId"]
    instance = args["instance"]

    # Step 1: describe the instance.
    c = ctx.read(["gcloud", "sql", "instances", "describe", instance,
                  "--project=%s" % project_id, "--format=json"])
    if not c.ok:
        if "does not exist" in c.text or "404" in c.text:
            return ctx.result("unchanged", _missing_outputs(), lines=[
                "The Cloud SQL instance %s does not exist in %s." % (instance, project_id)])
        return ctx.failed("The instance %s could not be read: %s." % (instance, _cause(c)),
                          {"exists": None})
    try:
        data = json.loads(c.out)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        return ctx.failed("The instance %s could not be read: gcloud gave no JSON." % instance,
                          {"exists": None})

    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    ip = settings.get("ipConfiguration") if isinstance(settings.get("ipConfiguration"),
                                                       dict) else {}
    backup = (settings.get("backupConfiguration")
              if isinstance(settings.get("backupConfiguration"), dict) else {})
    networks = ip.get("authorizedNetworks")
    policy = settings.get("activationPolicy")
    state = _state(policy, data.get("state"))
    notes = []

    # Step 2: pending operations, only for ALWAYS with RUNNABLE.
    if policy == "ALWAYS" and data.get("state") == "RUNNABLE":
        ops = ctx.read(["gcloud", "sql", "operations", "list", "--instance=%s" % instance,
                        "--project=%s" % project_id, "--filter=status!=DONE", "--limit=10",
                        "--format=value(operationType,status)"])
        if not ops.ok:
            notes.append("Pending operations could not be checked.")
        elif any(line.split()[:1] == ["UPDATE"] for line in ops.out.splitlines()):
            state = "starting"

    # Step 3: the last backup (the instance exists).
    last_backup = None
    b = ctx.read(["gcloud", "sql", "backups", "list", "--instance=%s" % instance,
                  "--project=%s" % project_id, "--filter=status=SUCCESSFUL",
                  "--sort-by=~windowStartTime", "--limit=1", "--format=value(windowStartTime)"])
    if b.ok:
        first = [line.strip() for line in b.out.splitlines() if line.strip()]
        last_backup = first[0] if first else None
    else:
        notes.append("The last backup could not be read.")

    outputs = {
        "exists": True,
        "state": state,
        "databaseVersion": _str(data.get("databaseVersion")),
        "edition": _str(settings.get("edition")),
        "tier": _str(settings.get("tier")),
        "region": _str(data.get("region")),
        "diskSizeGb": _number(settings.get("dataDiskSizeGb")),
        "storageAutoIncrease": _bool(settings.get("storageAutoResize")),
        "publicAddress": _bool(ip.get("ipv4Enabled")),
        "authorizedNetworks": len(networks) if isinstance(networks, list) else 0,
        "backupEnabled": _bool(backup.get("enabled")),
        "backupStartUtc": _str(backup.get("startTime")),
        "deletionProtection": _bool(settings.get("deletionProtectionEnabled")),
        "knowledgeCatalog": _bool(settings.get("enableDataplexIntegration")),
        "lastBackup": last_backup,
    }

    def shown(v):
        return v if v is not None else "unknown"

    lines = ["The Cloud SQL instance %s in %s is %s." % (instance, project_id, state)]
    if state == "unknown":
        if policy is None:
            lines.append("Its activation policy is absent.")
        else:
            lines.append("Its activation policy is %s, which is not a known value." % policy)
    if state == "starting":
        lines.append("It takes about twelve minutes from the start to accept connections.")
    lines.append("Tier %s, version %s." % (shown(outputs["tier"]),
                                           shown(outputs["databaseVersion"])))
    if outputs["publicAddress"]:
        n = outputs["authorizedNetworks"]
        lines.append("It has a public address, with %d authorized network%s."
                     % (n, "" if n == 1 else "s"))
    else:
        lines.append("It has no public address.")
    if last_backup:
        lines.append("Last backup: %s." % last_backup)
    elif "The last backup could not be read." not in notes:
        lines.append("Last backup: none.")
    lines.extend(notes)

    resources = [{"type": "instance", "id": "%s/%s" % (project_id, instance),
                  "name": instance, "labels": {}}]
    return ctx.result("unchanged", outputs, resources=resources, lines=lines)
