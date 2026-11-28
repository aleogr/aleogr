"""gcp-cloud-sql_access-grant: let one component's service account connect to the shared
Cloud SQL instance as itself, with no password: the database user of the IAM
service-account type first, then the roles roles/cloudsql.client and
roles/cloudsql.instanceUser on the shared project, each when missing (mode=apply), or say
what would be done (mode=plan).

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_cloud_sql_access_grant.py) and its scenarios. It was built from
skills/gcp-cloud-sql_access-grant/SKILL.md as that text was before the skill became a
shell over this command (the text is in the repository's history, at the commit before
that change): the same reads in the same order, the user before the roles, nothing made or
granted on an instance that is not running, the one poll of a grant refused because the
account is not visible yet (at most 10 tries and 9 waits per role, through ctx.wait()
only), the prescribed sentences word for word and the same result block. Writes run
through ctx.write only. No password is ever set, read or printed: the user's type is
always cloud_iam_service_account. The result block never holds the account, the user or
the member."""

import json
import re

import aleogr_common as common

FAMILY = "db"
PROVIDER = "gcp-cloud-sql"
ACTION = "access-grant"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply creates the user and grants the roles, through ctx.write only

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_access-grant"
COST = {"fixed": False, "notes": "roles and database users have no cost"}

CLIENT = "roles/cloudsql.client"
INSTANCE_USER = "roles/cloudsql.instanceUser"
ROLES = (CLIENT, INSTANCE_USER)
TRIES = 10  # per role, the first one included (so at most 9 waits)

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_INSTANCE = re.compile(r"^[a-z][a-z0-9-]{0,59}$")
_ACCOUNT = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@[a-z][a-z0-9-]{4,28}[a-z0-9]"
                      r"\.iam\.gserviceaccount\.com$")

# The sentences the SKILL.md writes in backquotes, word for word.
INSTANCE_FAILED = ("The instance %s of the shared project could not be read; nothing was "
                   "changed. Check that it exists and that the active gcloud account may read it.")
POLICY_FAILED = ("The access policy of the shared project could not be read; nothing was "
                 "changed. Check that the active gcloud account may read it.")
USERS_FAILED = ("The users of the instance %s could not be read although it is running; "
                "nothing was changed.")
USER_FAILED_BUT_EXISTS = ("The command that creates the database user of the account failed, "
                          "but the user exists.")
USER_NOT_CREATED = "The database user of the account could not be created on the instance %s."
USER_FAILED_UNREAD = ("The command that creates the database user of the account failed and "
                      "the users could not be read: it may exist. Run this same skill again to "
                      "check.")
GRANT_REFUSED = ("The account could not be given the role %s on the shared project. Check that "
                 "the active gcloud account may change who has access to it.")
OPS_NOT_CHECKED = "Pending operations could not be checked."
NO_PASSWORD = "The account connects with no password, as itself."
NOT_RUNNABLE = ("The account's user or roles cannot be passed to the commands of this skill, so "
                "nothing was changed.")

NOT_RUNNING = {
    "stopped": ("/aleogr:project-apply confirm=yes",
                "The shared instance is stopped: the database user and its roles are made only "
                "while it runs; /aleogr:project-apply confirm=yes starts it."),
    "starting": ("Wait a few minutes, then /aleogr:project-plan.",
                 "The shared instance is starting: the database user and its roles are made "
                 "once it runs. Wait a few minutes, then run /aleogr:project-plan."),
    "creating": ("Wait a few minutes, then /aleogr:project-plan.",
                 "The shared instance is creating: the database user and its roles are made "
                 "once it runs. Wait a few minutes, then run /aleogr:project-plan."),
    "unknown": ("/aleogr:platform-plan",
                "The state of the shared instance is not one this skill knows: the database "
                "user and its roles are made only while it runs. Run /aleogr:platform-plan."),
}


def user_name(account):
    """`<id>@<project id>.iam`: the account without `.gserviceaccount.com`."""
    return account[:-len(".gserviceaccount.com")]


def _validate(args):
    problems = []
    rules = [
        ("sharedProjectId", lambda v: _PROJECT_ID.match(v),
         "sharedProjectId is not a GCP project id."),
        ("instance", lambda v: _INSTANCE.match(v),
         "instance must have 1 to 60 lowercase letters, digits and hyphens, starting with a "
         "letter."),
        ("account", lambda v: _ACCOUNT.match(v),
         "account must be the address of a service account "
         "(<id>@<project id>.iam.gserviceaccount.com), with no prefix."),
    ]
    for key, ok, sentence in rules:
        v = args.get(key)
        if not v:
            problems.append("%s is missing." % key)
        elif not ok(v):
            problems.append(sentence)
        elif key == "account" and len(user_name(v)) > 63:
            problems.append("The database user of account would have %d characters: PostgreSQL "
                            "allows 63." % len(user_name(v)))
    if "mode" in args and args["mode"] not in ("plan", "apply"):
        problems.append("mode must be plan or apply.")
    return problems


def state_of(policy, state):
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


def policy_command(shared):
    return ["gcloud", "projects", "get-iam-policy", shared, "--format=json"]


def users_command(shared, instance):
    return ["gcloud", "sql", "users", "list", "--instance=%s" % instance,
            "--project=%s" % shared, "--format=value(name)"]


def user_create_command(account, shared, instance):
    """Step 5, as the SKILL.md writes it: the IAM service-account type, no password."""
    return ["gcloud", "sql", "users", "create", user_name(account), "--instance=%s" % instance,
            "--project=%s" % shared, "--type=cloud_iam_service_account", "--quiet"]


def grant_command(shared, account, role):
    """Step 6, as the SKILL.md writes it."""
    return ["gcloud", "projects", "add-iam-policy-binding", shared,
            "--member=serviceAccount:%s" % account, "--role=%s" % role, "--condition=None",
            "--quiet"]


def holds(policy, account, role):
    """Whether a binding of exactly `role` lists serviceAccount:<account> (case aside),
    with or without a condition."""
    member = ("serviceAccount:%s" % account).lower()
    bindings = policy.get("bindings") if isinstance(policy, dict) else None
    for b in bindings if isinstance(bindings, list) else []:
        if isinstance(b, dict) and b.get("role") == role:
            for m in b.get("members") or []:
                if isinstance(m, str) and m.lower() == member:
                    return True
    return False


def _json(c):
    if not c.ok:
        return None
    try:
        data = json.loads(c.out)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _listed(c, user):
    return any(line.strip() == user for line in c.out.splitlines())


def _not_visible_yet(c):
    """The one decision made by an error's text: the account is not visible yet."""
    return "does not exist" in c.text or "NOT_FOUND" in c.text


def _tries(n):
    return "%d %s" % (n, "try" if n == 1 else "tries")


def run(args, ctx):
    mode = args.get("mode") or DEFAULT_MODE
    empty = {"instanceState": None, "user": None, "client": False, "instanceUser": False,
             "granted": [], "userCreated": False}
    problems = _validate(args)
    if problems:
        return ctx.failed(problems, dict(empty), cost=dict(COST),
                          mode=mode if mode in ("plan", "apply") else DEFAULT_MODE)
    shared = args["sharedProjectId"]
    instance = args["instance"]
    account = args["account"]
    user = user_name(account)
    resources = [{"type": "instance", "id": "%s/%s" % (shared, instance), "name": instance,
                  "labels": {}}]
    access_how = ("/%s:%s sharedProjectId=%s instance=%s account=<e-mail> mode=apply"
                  % (PLUGIN, SKILL, shared, instance))

    def access_item(reason):
        return {"item": "access", "reason": reason, "how": access_how}

    # Step 1: the instance and its state.
    d = _json(ctx.read(describe_command(shared, instance)))
    if d is None:
        return ctx.failed(INSTANCE_FAILED % instance, dict(empty), cost=dict(COST))
    settings = d.get("settings") if isinstance(d.get("settings"), dict) else {}
    policy_value = settings.get("activationPolicy")
    state = state_of(policy_value, d.get("state"))
    lines = []
    if policy_value == "ALWAYS" and d.get("state") == "RUNNABLE":
        ops = ctx.read(operations_command(shared, instance))
        if not ops.ok:
            lines.append(OPS_NOT_CHECKED)
        elif any(line.split()[:1] == ["UPDATE"] for line in ops.out.splitlines()):
            state = "starting"
    lines.insert(0, "The shared instance %s is %s." % (instance, state))

    o = dict(empty, instanceState=state)

    def result(status, pending=(), said=()):
        return ctx.result(status, dict(o), resources=resources, cost=dict(COST),
                          pending=list(pending), lines=lines + list(said))

    # Step 2: the shared project's policy, whatever the state.
    policy = _json(ctx.read(policy_command(shared)))
    if policy is None:
        return result("failed", said=[POLICY_FAILED])
    o["client"] = holds(policy, account, CLIENT)
    o["instanceUser"] = holds(policy, account, INSTANCE_USER)

    def roles_sentence():
        held = [r for r in ROLES if o[_key(r)]]
        if not held:
            return "The account %s holds neither %s nor %s." % (account, CLIENT, INSTANCE_USER)
        return "The account %s holds %s." % (account, " and ".join(held))

    # Step 4 (first half): not running: nothing is read, made or granted.
    if state != "running":
        how, sentence = NOT_RUNNING[state]
        item = {"item": "instance",
                "reason": "The shared instance is %s: the database user and its roles are made "
                          "only while it runs." % state, "how": how}
        return result("pending", [item], [sentence, roles_sentence(),
                                          "Its database user was not read.",
                                          "Nothing was changed."])

    # Step 3: the users of the instance.
    c = ctx.read(users_command(shared, instance))
    if not c.ok:
        return result("failed", said=[USERS_FAILED % instance])
    o["user"] = _listed(c, user)
    missing = [r for r in ROLES if not o[_key(r)]]

    # Every write this run could make, checked against the allowlist in both modes.
    planned = ([] if o["user"] else [user_create_command(account, shared, instance)]) + [
        grant_command(shared, account, r) for r in missing]
    if any(common.write_refusal(SKILL, argv, root=ctx.root) for argv in planned):
        return result("failed", said=[NOT_RUNNABLE])

    # Step 4 (second half): the plan.
    if mode == "plan":
        o["granted"] = list(missing)
        said = []
        if o["user"]:
            said.append("The account %s is a user of the instance." % account)
        else:
            said.append("The account %s is not a user of the instance: it would be made one, "
                        "of the IAM service-account type." % account)
        for r in ROLES:
            said.append("It %s %s." % ("would be granted" if r in missing else "holds", r))
        said.extend([NO_PASSWORD, "This plan changed nothing."])
        status = "would-update" if missing or not o["user"] else "unchanged"
        return result(status, said=said)

    said = []
    items = []

    # Step 5: the user first.
    if not o["user"]:
        made = ctx.write(user_create_command(account, shared, instance))
        v = ctx.read(users_command(shared, instance))
        if not v.ok:
            o["user"] = None
            if made.ok:
                o["userCreated"] = True
                said.append("The database user of the account was created, but the users "
                            "could not be read to confirm it; no role was granted.")
                return result("updated", [access_item(
                    "The database user of the account could not be confirmed, so no role was "
                    "granted.")], said + [roles_sentence(), NO_PASSWORD])
            said.append(USER_FAILED_UNREAD)
            return result("failed", [access_item(
                "The database user of the account could not be confirmed, so no role was "
                "granted.")], said + [roles_sentence()])
        if not _listed(v, user):
            o["user"] = False
            said.append(USER_NOT_CREATED % instance)
            return result("failed", [access_item(
                "The database user of the account could not be made, so no role was "
                "granted.")], said + [roles_sentence()])
        o["user"] = True
        o["userCreated"] = True
        said.append(USER_FAILED_BUT_EXISTS if not made.ok else
                    "The account %s was made a user of the instance, of the IAM "
                    "service-account type." % account)
    else:
        said.append("The account %s is a user of the instance." % account)

    # Step 6: the roles, each when missing, in order.
    granted = []
    for role in missing:
        tries = 0
        accepted = False
        budget_spent = False
        while True:
            tries += 1
            g = ctx.write(grant_command(shared, account, role))
            if g.ok:
                accepted = True
                break
            if not _not_visible_yet(g) or tries >= TRIES:
                break
            if not ctx.wait():
                # A wait that cannot be run counts as the refusal that ends the poll.
                budget_spent = True
                break
        if not accepted:
            said.append(GRANT_REFUSED % role)
            if budget_spent:
                # The run's wait budget ended the poll: a second run goes on.
                said.append(common.WAIT_BUDGET_SENTENCE)
            said.append("The grant of the role %s was refused after %s." % (role, _tries(tries)))
            if granted:
                back = _json(ctx.read(policy_command(shared)))
                if back is not None:
                    o["client"] = holds(back, account, CLIENT)
                    o["instanceUser"] = holds(back, account, INSTANCE_USER)
                o["granted"] = list(granted)
                said.append(roles_sentence())
            else:
                said.append(roles_sentence())
            return result("failed", [access_item(
                "A role could not be granted to the account on the shared project.")], said)
        granted.append(role)
        o["granted"] = list(granted)

    if granted:
        back = _json(ctx.read(policy_command(shared)))
        if back is None:
            items = [access_item("The roles granted by this run could not be read back to "
                                 "confirm them.")]
            said.append("This run granted %s; the policy could not be read back to confirm it."
                        % " and ".join(granted))
        else:
            o["client"] = holds(back, account, CLIENT)
            o["instanceUser"] = holds(back, account, INSTANCE_USER)
            unseen = [r for r in granted if not o[_key(r)]]
            said.append("This run granted %s." % " and ".join(granted))
            if unseen:
                items = [access_item("A role granted by this run is not yet seen in the policy "
                                     "of the shared project.")]
                said.append("The policy read back does not show %s yet." % " and ".join(unseen))
    said.append(roles_sentence())
    said.append(NO_PASSWORD)
    status = "updated" if (o["userCreated"] or granted) else "unchanged"
    return result(status, items, said)


def _key(role):
    return "client" if role == CLIENT else "instanceUser"
