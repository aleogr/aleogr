"""platform-plan: compare the owner's defaults with the shared platform in Google Cloud
(the shared project with billing, its APIs, the budget alert, the database switch, the
shared Cloud SQL instance) and with the login of the organization; print a table of
items, state and action. Read-only: it runs no provider command of its own except
tools-check's reads (in this plugin, called as a function), and it invokes the other
plugins' commands with `--read-only` only.

The specification is skills/platform-plan/SKILL.md: the same invocations, in the same
order, the same items, states, actions, lines and result block.

The module keeps three things apart, so that platform-apply calls the plan as a
function and gets the same object:

- reading: gather(args, caller) runs steps 1 to 7 and returns a Reads, which holds every
  input (the defaults' values, each called skill's result) and, when a step ended the
  plan, its Failure;
- deciding: items(), status(), outputs(), pending(), resources() are pure functions of
  a Reads; decide() returns a Plan;
- printing: answer_lines(plan) and run().

plan(args, ctx) gives the Plan; run(args, ctx) prints it.
"""

import importlib.util
import json
import os
import re
import sys

import aleogr_common as common

FAMILY = "orchestrator"
PROVIDER = "aleogr"
ACTION = "platform-plan"
RESULT_MODE = "plan"  # mode is always plan
COST = {"fixed": False, "notes": "read-only plan"}

CLOUD = "aleogr-cloud-gcp"
DB = "aleogr-db-gcp-cloud-sql"


def _tools_check():
    """This plugin's tools-check module, loaded by its file path (a unit test loads this
    module by path too, where `skills` may be another plugin's package)."""
    name = "aleogr_plugin_tools_check"
    if name not in sys.modules:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools_check.py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


TC = _tools_check()

# ---------------------------------------------------------------------------
# Items, states and actions (word for word)

ITEMS = ("shared project", "services", "budget alert", "database switch",
         "database instance", "login")
NONE = "none"
CREATE = "create"
UPDATE = "update"
PREPARE = "prepare"
BLOCKED = "blocked"
UNKNOWN = "unknown"
NOT_CHECKED_PROJECT = "not checked, will be checked after the project exists"
NOT_CHECKED_SERVICES = "not checked, will be checked after the services are enabled"
NOT_CHECKED_SWITCH = "not checked, the database switch is blocked"
NOT_CHECKED = "not checked"
BUDGET_API = "billingbudgets.googleapis.com"
RUNNING_STATES = ("running", "starting", "creating")

# The weeknight and weekend jobs of the switch, by the part names of its lastRunFailed.
JOB_NAMES = {"job-weeknight": "aleogr-shared-stop-weeknight",
             "job-weekend": "aleogr-shared-stop-weekend"}

# ---------------------------------------------------------------------------
# Sentences: the prescribed ones word for word, the others fixed here

PLAN_AGAIN = "/aleogr:platform-plan"
APPLY_CONFIRMED = "/aleogr:platform-apply confirm=yes"
COST_LINE = ("Cost: the database instance has a fixed cost of about R$ 50 per month while "
             "stopped, from its creation.")
LAST_RUN_LINE = ("The last run of %s failed: the night stop may not be working and the "
                 "instance may have been left running. Check the instance's state and send this "
                 "output.")
RUNNING_LINE = ("The database instance is running and is charged by the hour until it is "
                "stopped: /aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop projectId=%s "
                "instance=%s")
LOGIN_NOT_CHECKED_LINE = ("The login of the organization could not be checked; "
                          "/aleogr:platform-apply confirm=yes reads it again and prepares it when "
                          "it is not prepared.")
NOTHING_TO_DO = "nothing to do"

# Fixed here (the SKILL.md leaves their wording to the answer).
ONLY_GCP = "Only GCP is implemented: cloud.provider in defaults.json is not gcp."
ONLY_GCP_HOW = "only GCP is implemented: set cloud.provider to gcp in defaults.json"
ARGUMENT_UNKNOWN = ("%s is not an argument of platform-plan: its one argument is "
                    "projectId=<id>.")
PROJECT_ID_INVALID = ("projectId is not valid: it must have 6 to 30 characters of a-z, 0-9 "
                      "and -, start with a letter and not end with -.")
ARGUMENTS_HOW = "give only projectId=<id>, or no argument"
NEEDS_CHANGES = "%d item%s need%s changes: /aleogr:platform-apply confirm=yes %s."
CREATES_THEM = "creates them"
CREATES_IT = "creates it"
PREPARES_LOGIN = "prepares the login as far as a command can"
BLOCKED_LINE = "The item %s is blocked: %s."

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")


class Failure(object):
    """A step that ended the plan with failed: the sentence of the answer, the item it
    blocks, and the pending items (each with the fix or next command)."""

    def __init__(self, sentence, item, pending, called=False):
        self.sentence = sentence
        self.item = item
        self.pending = list(pending)
        # The plan ended on a read of a skill it invoked (its sentence is that skill's),
        # or on a command of another suite (PluginVersion).
        self.called = called


def pending_item(item, how):
    return {"item": item, "reason": "manual", "how": how}


def _out(result):
    o = result.get("outputs") if isinstance(result, dict) else None
    return o if isinstance(o, dict) else {}


def _status(result):
    return result.get("status") if isinstance(result, dict) else None


def _answer(result):
    lines = result.get("answer") if isinstance(result, dict) else None
    return [l for l in (lines or []) if isinstance(l, str)]


def cause(result):
    """The sentence a called skill gave for its failure: its first answer line."""
    for l in _answer(result):
        if l.strip():
            return l.strip()
    return "%s ended %s." % ((result.get("action") if isinstance(result, dict) else None)
                             or "A skill", _status(result))


def as_how(sentence):
    """A sentence as the start of a `how`: without its final period or its own advice
    to run it again."""
    s = sentence.strip()
    for tail in (", then run this again.", " Run this same skill again.", "."):
        if s.endswith(tail):
            return s[:-len(tail)]
    return s


# ---------------------------------------------------------------------------
# The defaults


class Invalid(Exception):
    pass


def _number_text(v):
    """A number of defaults.json as an argument: 100 is `100`, 0.5 is `0.5`, 1.0 is `1.0`
    (as the owner's defaults write it)."""
    if isinstance(v, bool):
        raise Invalid("not a number")
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    raise Invalid("not a number")


class Defaults(object):
    """defaults.json of this plugin, read once; get() raises Invalid naming what is
    missing."""

    def __init__(self, path):
        self.path = path
        self._data = None
        self._read = False

    def load(self):
        if not self._read:
            self._read = True
            try:
                with open(self.path, encoding="utf-8") as f:
                    self._data = json.loads(f.read())
            except (OSError, ValueError, UnicodeDecodeError):
                self._data = None
        if not isinstance(self._data, dict):
            raise Invalid("defaults.json of the plugin aleogr could not be read")
        return self._data

    def get(self, dotted, kind="str"):
        v = self.load()
        for part in dotted.split("."):
            v = v.get(part) if isinstance(v, dict) else None
        ok = {
            "str": lambda x: isinstance(x, str) and x != "",
            "list": lambda x: (isinstance(x, list) and x != []
                               and all(isinstance(i, str) and i for i in x)),
            "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
            "numbers": lambda x: (isinstance(x, list) and x != [] and all(
                isinstance(i, (int, float)) and not isinstance(i, bool) for i in x)),
        }[kind](v)
        if not ok:
            raise Invalid("defaults.json of the plugin aleogr has no %s" % dotted)
        return v


# The values the plan takes (step 1), and those platform-apply takes as well.
PLAN_VALUES = (
    ("project", "platform.shared.project", "str"),
    ("services", "platform.shared.services", "list"),
    ("displayName", "platform.budget.displayName", "str"),
    ("amount", "platform.budget.amount", "number"),
    ("currency", "platform.budget.currency", "str"),
    ("thresholds", "platform.budget.thresholds", "numbers"),
    ("instance", "platform.database.instance", "str"),
    ("timeZone", "platform.switch.timeZone", "str"),
    ("weeknightStop", "platform.switch.weeknightStop", "str"),
    ("weekendStop", "platform.switch.weekendStop", "str"),
    ("repository", "platform.switch.repository", "str"),
    ("region", "cloud.region", "str"),
)
APPLY_VALUES = (
    ("version", "platform.database.version", "str"),
    ("tier", "platform.database.tier", "str"),
    ("edition", "platform.database.edition", "str"),
    ("storageGb", "platform.database.storageGb", "number"),
    ("backupStartUtc", "platform.database.backupStartUtc", "str"),
    ("retainedBackups", "platform.database.retainedBackups", "number"),
)


def read_values(defaults, wanted):
    """The values as the skills take them (text), or Invalid."""
    values = {}
    for key, dotted, kind in wanted:
        v = defaults.get(dotted, kind)
        if kind == "number":
            v = _number_text(v)
        elif kind == "numbers":
            v = [_number_text(x) for x in v]
        values[key] = v
    return values


# ---------------------------------------------------------------------------
# Reading: steps 1 to 7


class Reads(object):
    """Everything the plan read, and the Failure that ended it (or None)."""

    def __init__(self, args):
        self.args = dict(args)
        self.failure = None
        self.values = {}
        self.gcloud = None  # tools-check (a tools_check.Check)
        self.environment = None  # step 3
        self.login = None  # step 3, gcp_login-describe
        self.services = None  # step 4
        self.budget = None  # step 5 (None: not run)
        self.budget_checked = False  # step 5 was reached (run or skipped by its rule)
        self.switch = None  # step 6
        self.instance = None  # step 7
        self.reached = 0  # the last step reached (3 to 7)

    @property
    def exists(self):
        return _out(self.environment).get("exists") is True

    @property
    def project_id(self):
        if not self.exists:
            return None
        pid = _out(self.environment).get("projectId")
        return pid if isinstance(pid, str) and pid else None

    @property
    def billing_linked(self):
        return _out(self.environment).get("billingLinked") is True

    @property
    def services_unchanged(self):
        return _status(self.services) == "unchanged"


class Caller(object):
    """How gather() invokes the skills: call(command, skill, args) runs another plugin's
    command with `--read-only` (a plan only reads), tools(command) is this plugin's
    tools-check. A command of another suite raises PluginVersion. A unit test gives its
    own Caller."""

    def __init__(self, ctx):
        self.ctx = ctx

    def call(self, command, skill, args):
        r = common.call_plugin(command, skill, args, read_only=True, caller=self.ctx.plugin)
        if r.get("callError") == "version":
            raise common.PluginVersion(r)
        return r

    def tools(self, command):
        return TC.check(command, self.ctx.read)

    def defaults_path(self):
        return self.ctx.plugin_path("defaults.json")


def validate_args(args):
    for k in args:
        if k != "projectId":
            return ARGUMENT_UNKNOWN % k
    if "projectId" in args and not _PROJECT_ID.match(args["projectId"] or ""):
        return PROJECT_ID_INVALID
    return None


def _capital(s):
    return s[:1].upper() + s[1:]


def _call_failure(result, item, again):
    sentence = cause(result)
    return Failure(sentence, item, [pending_item(item, "%s, then run %s again"
                                                 % (as_how(sentence), again))], called=True)


def gather(args, caller, again=None, wanted=PLAN_VALUES):
    """Steps 1 to 7. Returns a Reads; r.failure is set when a step ended the plan.
    `again`: the command the owner ran (by default this plan's own), named in a `how`.
    `wanted`: the defaults' values to take (platform-apply takes more). A command of
    another suite ends the plan at once with its sentence."""
    r = Reads(args)
    r.again = again or PLAN_AGAIN
    try:
        _gather(args, caller, r, wanted)
    except common.PluginVersion as e:
        r.failure = Failure(e.sentence, "plugins", [pending_item("plugins", as_how(e.sentence))],
                            called=True)
    return r


def _gather(args, caller, r, wanted):
    # The argument, before any command.
    problem = validate_args(args)
    if problem:
        r.failure = Failure(problem, "arguments", [pending_item("arguments", ARGUMENTS_HOW)])
        return

    # Step 1: the defaults.
    defaults = Defaults(caller.defaults_path())
    try:
        provider = defaults.get("cloud.provider")
    except Invalid as e:
        r.failure = Failure("%s." % _capital(str(e)), "defaults",
                            [pending_item("defaults", str(e))])
        return
    if provider != "gcp":
        r.failure = Failure(ONLY_GCP, "provider", [pending_item("provider", ONLY_GCP_HOW)])
        return
    try:
        r.values = read_values(defaults, wanted)
    except Invalid as e:
        r.failure = Failure("%s." % _capital(str(e)), "defaults",
                            [pending_item("defaults", str(e))])
        return
    v = r.values

    # Step 2: tools-check.
    r.gcloud = caller.tools("gcloud")
    if not r.gcloud.ok:
        tool = r.gcloud.tool
        r.failure = Failure("%s is %s: the fix is %s, then run %s again."
                            % (tool["name"], TC.STATE_WORDS[tool["state"]], tool["fix"],
                               r.again), "gcloud", [pending_item("gcloud", tool["fix"])])
        return

    # Step 3: the shared project, then the login.
    r.reached = 3
    if args.get("projectId"):
        a = {"projectId": args["projectId"]}
    else:
        a = {"project": v["project"], "platform": "shared"}
    r.environment = caller.call(CLOUD, "gcp_environment-describe", a)
    if _status(r.environment) == "failed" or _out(r.environment).get("exists") not in (
            True, False):
        r.failure = _call_failure(r.environment, "shared project", r.again)
        return
    if not r.exists:
        return
    pid = r.project_id
    if pid is None:
        r.failure = _call_failure(r.environment, "shared project", r.again)
        return
    r.login = caller.call(CLOUD, "gcp_login-describe", {"projectId": pid})

    # Step 4: services.
    r.reached = 4
    r.services = caller.call(CLOUD, "gcp_services-enable",
                             {"projectId": pid, "services": ",".join(v["services"]),
                              "mode": "plan"})
    if _status(r.services) not in ("unchanged", "would-update"):
        r.failure = _call_failure(r.services, "services", r.again)
        return

    # Step 5: the budget, only when its prerequisites are met.
    r.reached = 5
    r.budget_checked = True
    already = _out(r.services).get("alreadyEnabled") or []
    if r.billing_linked and (r.services_unchanged or BUDGET_API in already):
        r.budget = caller.call(CLOUD, "gcp_budget-alert-setup",
                               {"displayName": v["displayName"], "amount": v["amount"],
                                "currency": v["currency"],
                                "thresholds": ",".join(v["thresholds"]),
                                "quotaProject": pid, "mode": "plan"})
        if _status(r.budget) not in ("would-create", "would-update", "unchanged"):
            r.failure = _call_failure(r.budget, "budget alert", r.again)
            return

    if not r.services_unchanged:
        return

    # Step 6: the database switch.
    r.reached = 6
    r.switch = caller.call(DB, "gcp-cloud-sql_instance-switch-setup", switch_args(v, pid,
                                                                                  "plan"))
    st = _status(r.switch)
    if st == "pending":
        items = [x for x in (r.switch.get("pending") or []) if isinstance(x, dict)]
        r.failure = Failure(cause(r.switch), "database switch",
                            items or [pending_item("database switch", r.again)], called=True)
        return
    if st not in ("unchanged", "would-create", "would-update"):
        r.failure = _call_failure(r.switch, "database switch", r.again)
        return

    # Step 7: the database instance.
    r.reached = 7
    r.instance = caller.call(DB, "gcp-cloud-sql_instance-describe",
                             {"projectId": pid, "instance": v["instance"]})
    if _status(r.instance) == "failed" or _out(r.instance).get("exists") not in (True, False):
        r.failure = _call_failure(r.instance, "database instance", r.again)
        return


def switch_args(v, project_id, mode):
    """The switch's arguments, as steps 6 (plan) and 4.4 of platform-apply write them."""
    return {"projectId": project_id, "instance": v["instance"], "region": v["region"],
            "timeZone": v["timeZone"], "weeknightStop": v["weeknightStop"],
            "weekendStop": v["weekendStop"], "repository": v["repository"], "mode": mode}


# ---------------------------------------------------------------------------
# Deciding


def project_row(r):
    if r.environment is None:
        return None
    if r.failure is not None and r.failure.item == "shared project":
        return ("shared project", UNKNOWN, BLOCKED)
    if not r.exists:
        return ("shared project", "missing", CREATE)
    if r.billing_linked:
        return ("shared project", "ready", NONE)
    return ("shared project", "billing not linked", UPDATE)


def services_row(r):
    if r.environment is not None and not r.exists and r.failure is None:
        return ("services", NOT_CHECKED_PROJECT, CREATE)
    if r.services is None:
        return None
    st = _status(r.services)
    if st == "unchanged":
        return ("services", "all enabled", NONE)
    if st == "would-update":
        return ("services", "missing: %s" % ", ".join(_out(r.services).get("enabled") or []),
                UPDATE)
    return ("services", UNKNOWN, BLOCKED)


def budget_row(r):
    if r.environment is not None and not r.exists and r.failure is None:
        return ("budget alert", NOT_CHECKED_PROJECT, CREATE)
    if not r.budget_checked:
        return None
    if r.budget is None:
        return ("budget alert", NOT_CHECKED_SERVICES, CREATE)
    st = _status(r.budget)
    o = _out(r.budget)
    if st == "would-create":
        return ("budget alert", "missing", CREATE)
    if st == "would-update":
        differs = o.get("differs") or []
        return ("budget alert", "differs: %s" % "; ".join(str(d) for d in differs), UPDATE)
    if st == "unchanged":
        return ("budget alert", "exists" if o.get("compared") is not False
                else "exists, not compared", NONE)
    return ("budget alert", UNKNOWN, BLOCKED)


def switch_row(r):
    if r.environment is not None and not r.exists and r.failure is None:
        return ("database switch", NOT_CHECKED_PROJECT, CREATE)
    if not r.budget_checked or (r.failure is not None and r.reached < 6):
        return None
    if not r.services_unchanged:
        return ("database switch", NOT_CHECKED_SERVICES, CREATE)
    st = _status(r.switch)
    missing = ", ".join(_out(r.switch).get("missing") or [])
    if st == "unchanged":
        return ("database switch", "ready", NONE)
    if st == "would-create":
        return ("database switch", "missing", CREATE)
    if st == "would-update":
        return ("database switch", "incomplete: %s" % missing, UPDATE)
    if st == "pending":
        return ("database switch", "incomplete: %s" % missing, BLOCKED)
    return ("database switch", UNKNOWN, BLOCKED)


def instance_row(r):
    if r.environment is not None and not r.exists and r.failure is None:
        return ("database instance", NOT_CHECKED_PROJECT, CREATE)
    if not r.budget_checked or (r.failure is not None and r.reached < 6):
        return None
    if not r.services_unchanged:
        return ("database instance", NOT_CHECKED_SERVICES, CREATE)
    if r.reached < 7:
        return ("database instance", NOT_CHECKED_SWITCH, BLOCKED)
    o = _out(r.instance)
    if r.failure is not None and r.failure.item == "database instance":
        return ("database instance", UNKNOWN, BLOCKED)
    if o.get("exists") is False:
        return ("database instance", "missing", CREATE)
    return ("database instance", "exists, %s" % o.get("state"), NONE)


def login_row(r):
    if r.environment is not None and not r.exists and r.failure is None:
        return ("login", NOT_CHECKED_PROJECT, PREPARE)
    if r.login is None:
        return None
    if _status(r.login) == "failed":
        return ("login", NOT_CHECKED, PREPARE)
    if _out(r.login).get("prepared") is True:
        return ("login", "prepared", NONE)
    return ("login", "not prepared", PREPARE)


def items(r):
    """The rows (item, state, action), in the fixed order; only those checked. A command
    of another suite ends the plan with no row: nothing read before it is decided."""
    if r.failure is not None and r.failure.item == "plugins":
        return []
    rows = [f(r) for f in (project_row, services_row, budget_row, switch_row, instance_row,
                           login_row)]
    return [row for row in rows if row is not None]


def row(rows, name):
    for x in rows:
        if x[0] == name:
            return x
    return None


def status(r, rows):
    if r.failure is not None:
        return "failed"
    if all(x[2] == NONE for x in rows):
        return "unchanged"
    if row(rows, "shared project") and row(rows, "shared project")[2] == CREATE:
        return "would-create"
    return "would-update"


def outputs(r, rows):
    return {"projectId": r.project_id,
            "items": [{"item": i, "state": s, "action": a} for i, s, a in rows]}


def pending(r):
    return list(r.failure.pending) if r.failure is not None else []


def resources(r, name=None):
    pid = r.project_id
    if pid is None:
        return []
    return [{"type": "project", "id": pid, "name": name or r.values.get("project"),
             "labels": {}}]


class Plan(object):
    """What the plan decided: the Reads it came from, the rows, the status, the outputs,
    the pending items and the resources. platform-apply takes this object."""

    def __init__(self, reads, rows, status, outputs, pending, resources):
        self.reads = reads
        self.items = rows
        self.status = status
        self.outputs = outputs
        self.pending = pending
        self.resources = resources

    @property
    def failure(self):
        return self.reads.failure

    @property
    def project_id(self):
        return self.reads.project_id

    def action(self, name):
        x = row(self.items, name)
        return x[2] if x else None

    def state(self, name):
        x = row(self.items, name)
        return x[1] if x else None

    @property
    def instance_state(self):
        """The instance's state as its describe read it (None when not read, or when it
        does not exist)."""
        o = _out(self.reads.instance)
        return o.get("state") if o.get("exists") is True else None

    @property
    def instance_exists(self):
        """True, False, or None when the instance was not read."""
        e = _out(self.reads.instance).get("exists")
        return e if e in (True, False) else None


def decide(r):
    rows = items(r)
    return Plan(r, rows, status(r, rows), outputs(r, rows), pending(r), resources(r))


def plan(args, ctx, caller=None, again=None, wanted=PLAN_VALUES):
    """The whole plan, read and decided, not printed. `again`: the command the owner ran
    when another skill invokes the plan (platform-apply), named in a `how`."""
    return decide(gather(args, caller or Caller(ctx), again, wanted))


# ---------------------------------------------------------------------------
# Printing


def switch_secrets(result):
    """The `GitHub secrets` section of a switch result's answer (its title to its last
    line), or None when it printed none."""
    lines = _answer(result)
    if "GitHub secrets" not in lines:
        return None
    start = lines.index("GitHub secrets")
    out = lines[start:]
    while out and not out[-1].strip():
        out.pop()
    return out


def lines_under(p):
    """The lines under the table, as they apply: the cause of a stop, the cost line, the
    last runs of the night jobs, the running instance, the login not checked."""
    r = p.reads
    out = []
    if p.failure is not None and p.items:
        out.append(p.failure.sentence)
    if p.action("database instance") == CREATE:
        out.append(COST_LINE)
    failed_jobs = _out(r.switch).get("lastRunFailed") or [] if r.switch is not None else []
    if failed_jobs:
        names = [JOB_NAMES.get(j, j) for j in failed_jobs]
        out.append(LAST_RUN_LINE % (" and ".join(names)))
    st = p.state("database instance") or ""
    if st in ("exists, %s" % s for s in RUNNING_STATES):
        out.append(RUNNING_LINE % (r.project_id, r.values["instance"]))
    if p.state("login") == NOT_CHECKED:
        out.append(LOGIN_NOT_CHECKED_LINE)
    return out


def last_line(p):
    """`nothing to do`, how many items need changes, or what blocks."""
    if p.failure is not None:
        how = "; ".join(x.get("how", "") for x in p.failure.pending if isinstance(x, dict))
        return BLOCKED_LINE % (p.failure.item, how or as_how(p.failure.sentence))
    acting = [x for x in p.items if x[2] != NONE]
    if not acting:
        return NOTHING_TO_DO
    n = len(acting)
    made = [x for x in acting if x[0] != "login"]
    login = any(x[0] == "login" for x in acting)
    if made and login:
        what = "%s and %s" % (CREATES_THEM if len(made) > 1 else CREATES_IT, PREPARES_LOGIN)
    elif made:
        what = CREATES_THEM if n > 1 else CREATES_IT
    else:
        what = PREPARES_LOGIN
    return NEEDS_CHANGES % (n, "" if n == 1 else "s", "s" if n == 1 else "", what)


def table_lines(p):
    """The table (item, state, action), or nothing when no item was checked."""
    if not p.items:
        return []
    return common.render_table(["Item", "State", "Action"], [list(x) for x in p.items])


def answer_lines(p):
    if not p.items:
        return [p.failure.sentence] if p.failure is not None else [NOTHING_TO_DO]
    lines = table_lines(p)
    under = lines_under(p)
    if under:
        lines += [""] + under
    lines += ["", last_line(p)]
    return lines


def run(args, ctx):
    p = plan(args, ctx)
    return ctx.result(p.status, p.outputs, resources=p.resources, pending=p.pending,
                      cost=dict(COST), lines=answer_lines(p))
