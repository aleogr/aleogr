"""platform-apply: create what platform-plan lists as missing, in a fixed order (the shared
project, its APIs, the budget alert, the database switch, the database instance, then the
login of the organization as far as a command can), under one confirmation, and end with
a plan that proves it.

The rules are this module's, pinned by its unit tests
(tests/unit/test_platform_apply.py) and its scenarios. It was built from
skills/platform-apply/SKILL.md as that text was before the skill became a shell over
this command (the text is in the repository's history, at the commit before that
change): the same invocations, in the same order, the same gates, the same prescribed
sentences and the same result block. This module runs no provider command that changes
something: every write is a called skill's, through its plugin's command (ctx.call) in
`mode=apply`; its own commands are the plan's reads (the plan is called as a function of
this plugin, platform_plan.plan).

Layout, by the SKILL.md's steps: step_2() (the plan), step_3() (the confirmation),
step_4() (one method per sub-step: step_4_1 ... step_4_6), step_5() (the last plan), and
answer(), which builds the lines and the block of every ending.

A run in more than one command (docs/plans/2026-11-27-scripts-step-3-design.md): before
each step after the first of a command, when the step limit has passed, and when a
called command was ended by a limit of the run, the command ends `continue`
(ctx.continue_run); the next command starts from the top and plans again. What is
carried is only what the answer needs and cannot be read again (new_carry).

The creation of the instance is resumable: when this run asked for the creation in an
earlier command (`createAsked`, set before the create is invoked) and the plan of a
later command finds the instance existing and not stopped, the create is invoked again
with `resume=yes`: it skips the creation, waits for the instance, stops it and tests the
night stop. Without the carried file the run does not pass `resume=yes`, and the answer
is the plan's: the instance exists, whether it runs, what it costs and how to stop it.
"""

import importlib.util
import os
import re
import sys

import aleogr_common as common

FAMILY = "orchestrator"
PROVIDER = "aleogr"
ACTION = "platform-apply"
DEFAULT_MODE = "apply"  # no mode argument: the skill acts
RESULT_MODE = "apply"  # "mode is apply"
WRITES = False  # the orchestrator writes nothing itself
CONTINUES = True  # a run may take more than one command

CLOUD = "aleogr-cloud-gcp"
DB = "aleogr-db-gcp-cloud-sql"
STOP_JOB = "aleogr-shared-stop-weeknight"


def _plan_module():
    """This plugin's platform-plan module, loaded by its file path (a unit test loads this
    module by path, where `skills` may be another plugin's package)."""
    name = "aleogr_plugin_platform_plan"
    if name not in sys.modules:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "platform_plan.py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


PP = _plan_module()
NONE = PP.NONE

# ---------------------------------------------------------------------------
# Prescribed sentences, word for word

NOTHING_TO_DO = "nothing to do"
COST_LINE = PP.COST_LINE
LOGIN_SENTENCE = ("Preparing the login grants the account that runs this the role "
                  "roles/iap.settingsAdmin on the organization and enables the IAP API in the "
                  "shared project; both are free.")
CONFIRM_HOW = "/aleogr:platform-apply confirm=yes"
SECRETS_TITLE = "GitHub secrets"
LOGIN_TITLE = "Login"

INSTANCE_COST = {"fixed": True, "notes": "about R$ 50 per month while stopped"}
FREE_COST = {"fixed": False, "notes": "everything created here is free"}

# ---------------------------------------------------------------------------
# Sentences the SKILL.md leaves to this skill's own words (fixed here)

ARGUMENT_UNKNOWN = "%s is not an argument of platform-apply: its one argument is confirm=yes."
CONFIRM_INVALID = "confirm is not valid: it must be yes."
ARGUMENTS_HOW = "give only confirm=yes, or no argument"
SECRETS_ONCE = ("Pasting them is needed once, by hand; running /aleogr:platform-apply "
                "confirm=yes again shows them again and changes nothing when everything "
                "exists.")
LOGIN_PLAN_LINE = "Once the clicks and the command are done, run /aleogr:platform-plan."
NO_PROJECT_ID = ("The id of the shared project is not known, so %s was not run; nothing after "
                 "it was made.")
NO_PROJECT_ID_HOW = "run /aleogr:platform-plan, then /aleogr:platform-apply confirm=yes"
STEP_FAILED_HOW = "%s, then run /aleogr:platform-apply confirm=yes"
LOGIN_WOULD_UPDATE = "gcp_login-setup ended would-update in mode=apply."
CONTINUE_LINE = "This run goes on in its next command: %s comes next."
INSTANCE_CONTINUE = "Waiting for the database instance created in this run: it is %s."
COMMANDS_LIMIT = ("This run reached its limit of eight commands before %s; nothing after it was "
                  "made.")
COMMANDS_LIMIT_HOW = ("this run reached its limit of eight commands: run /aleogr:platform-plan, "
                      "then /aleogr:platform-apply confirm=yes")
INSTANCE_MAY_RUN = ("This run asked to create the database instance %s: it may exist and run, "
                    "charged by the hour until it is stopped, with a fixed cost of about R$ 50 per "
                    "month while stopped. To stop it: "
                    "/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop projectId=%s "
                    "instance=%s")
INSTANCE_GONE = ("The database instance %s that this run asked to create in an earlier command "
                 "does not exist: its creation did not finish, and it was not created again.")
INSTANCE_GONE_HOW = ("the creation of the database instance did not finish: run "
                     "/aleogr:platform-plan, then /aleogr:platform-apply confirm=yes")
INSTANCE_NOT_READ = ("The database instance %s that this run asked to create in an earlier "
                     "command was not read by the plan, so this run did not go on with it.")
NIGHT_STOP_UNKNOWN = ("The database instance created in this run is stopped, but this run "
                      "could not tell whether its night stop was tested: the command that tested "
                      "it was cut by the time limit.")
RESUME_REFUSED_PREFIX = "resume=yes was not used"
# The end of the create's line that says it resumed (not a cause: not relayed).
RESUME_GOES_ON = "this run goes on from its creation, with its wait, its stop and its check."

# The plan's item of each step of step 4, and the skill it invokes.
STEPS = (
    ("shared project", CLOUD, "gcp_environment-create"),
    ("services", CLOUD, "gcp_services-enable"),
    ("budget alert", CLOUD, "gcp_budget-alert-setup"),
    ("database switch", DB, "gcp-cloud-sql_instance-switch-setup"),
    ("database instance", DB, "gcp-cloud-sql_instance-create"),
    ("login", CLOUD, "gcp_login-setup"),
)
SKILLS = tuple(s for _i, _c, s in STEPS)
ITEM_OF = dict((s, i) for i, _c, s in STEPS)
LINE_STATUSES = ("created", "updated", "unchanged", "pending", "failed")
RANK = {"failed": 0, "unchanged": 1, "pending": 2, "updated": 3, "created": 4}


def item(name, how, reason="manual"):
    return {"item": name, "reason": reason, "how": how}


def _out(result):
    o = result.get("outputs") if isinstance(result, dict) else None
    return o if isinstance(o, dict) else {}


def _status(result):
    return result.get("status") if isinstance(result, dict) else None


def _pending(result):
    p = result.get("pending") if isinstance(result, dict) else None
    return [x for x in (p or []) if isinstance(x, dict)]


def _answer(result):
    lines = result.get("answer") if isinstance(result, dict) else None
    return [l for l in (lines or []) if isinstance(l, str) and l.strip()]


def first_sentence(result):
    lines = _answer(result)
    if lines:
        return lines[0].strip()
    return "%s ended %s." % (result.get("action") or "A skill", _status(result))


WROTE_PREFIX = common.REFUSED_WRITTEN.split("{writes}")[0]


def wrote_before_abort(result):
    """True when a called command's aborted (or refused) result says it had already run
    writes before it stopped."""
    return any(l.startswith(WROTE_PREFIX) for l in _answer(result))


def stop_how(project_id, instance):
    return "/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop projectId=%s instance=%s" % (
        project_id, instance)


class End(Exception):
    """Ends the run with this Result."""

    def __init__(self, result):
        Exception.__init__(self, "end")
        self.result = result


class Continue(Exception):
    """A limit of the run was reached before `line`'s step: end `continue` when the run may,
    otherwise end by `limit()` (the prose's ending of a wait that passed its limit)."""

    def __init__(self, line, limit):
        Exception.__init__(self, "continue")
        self.line = line
        self.limit = limit


# ---------------------------------------------------------------------------
# The carry: what a command gives the next one of the same run


def new_carry():
    return {
        "made": [],  # "<skill>: <status>", one per step of step 4 that ran, in order
        "projectId": None,  # the id gcp_environment-create gave in this run
        "projectCreated": False,
        "switchCreated": False,
        "instanceCreated": False,
        "changed": False,  # something was changed in this run (any command of it)
        "createAsked": False,  # gcp-cloud-sql_instance-create was invoked in this run
        "instanceDone": False,  # its outcome is known (it ended, or a plan saw it stopped)
        "nightUnknown": False,  # seen stopped after a create the time limit cut
        "login": None,  # {"status", "steps", "pending"} of gcp_login-setup in this run
        "lost": None,  # CARRY_LOST_SENTENCE of a carry a command of this run refused
    }


PROJECT_ID_RE = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")
LINE_RE = re.compile(r"([a-z0-9_-]+): ([a-z]+)")
MAX_LINE = 4000
MAX_LINES = 16
LOST_SENTENCES = tuple(common.CARRY_LOST_SENTENCE.format(why=why)
                       for why in common.CARRY_REFUSALS.values())


def _valid_text(x):
    return isinstance(x, str) and 0 < len(x) <= MAX_LINE and "\n" not in x and "\r" not in x


def _valid_item(x):
    return (isinstance(x, dict) and set(x) == {"item", "reason", "how"}
            and all(_valid_text(x[k]) for k in x))


def _valid_carry(c):
    """The carry as this module wrote it, or None when anything in it is not what this
    module writes (a file edited by hand): then the run goes on as a new one."""
    base = new_carry()
    if not isinstance(c, dict) or set(c) != set(base):
        return None
    flags = ("projectCreated", "switchCreated", "instanceCreated", "changed", "createAsked",
             "instanceDone", "nightUnknown")
    if any(type(c[k]) is not bool for k in flags):
        return None
    made = c["made"]
    if not isinstance(made, list) or len(made) > len(SKILLS):
        return None
    names = []
    for line in made:
        m = LINE_RE.fullmatch(line) if isinstance(line, str) else None
        if not m or m.group(1) not in SKILLS or m.group(2) not in LINE_STATUSES:
            return None
        names.append(m.group(1))
    if len(set(names)) != len(names):
        return None
    pid = c["projectId"]
    if pid is not None and not (isinstance(pid, str) and PROJECT_ID_RE.fullmatch(pid)):
        return None
    login = c["login"]
    if login is not None and not (
            isinstance(login, dict) and set(login) == {"status", "steps", "pending"}
            and login["status"] in ("updated", "pending")
            and isinstance(login["steps"], list) and len(login["steps"]) <= MAX_LINES
            and all(_valid_text(s) for s in login["steps"])
            and isinstance(login["pending"], list) and 0 < len(login["pending"]) <= 4
            and all(_valid_item(x) for x in login["pending"])):
        return None
    if c["instanceDone"] and not c["createAsked"]:
        return None
    if c["lost"] is not None and c["lost"] not in LOST_SENTENCES:
        return None
    return dict(c)


# ---------------------------------------------------------------------------
# The arguments


def validate_args(args):
    """None, or the one sentence of the first argument that breaks a rule."""
    for k in args:
        if k != "confirm":
            return ARGUMENT_UNKNOWN % k
    if "confirm" in args and args["confirm"] != "yes":
        return CONFIRM_INVALID
    return None


def read_defaults_bytes(ctx):
    try:
        with open(ctx.plugin_path("defaults.json"), "rb") as f:
            return f.read()
    except OSError:
        return b""


# ---------------------------------------------------------------------------
# The run


class Apply(object):
    """One command of a run: the steps of the SKILL.md as methods."""

    def __init__(self, args, ctx, carry, plan_fn=None, call_fn=None, lost=None):
        self.args = dict(args)
        self.ctx = ctx
        self.carry = carry
        self.confirm = args.get("confirm") == "yes"
        self._plan_fn = plan_fn or (lambda a: PP.plan(a, ctx, again=self.again(),
                                                      wanted=PP.PLAN_VALUES + PP.APPLY_VALUES))
        self._call_fn = call_fn or (lambda command, skill, a: ctx.call(command, skill, a))
        # A carry refused by this command, or by an earlier one of the run (carried in
        # `lost`): the sentence is in the run's last answer, once, whichever command
        # gives it.
        if lost:
            carry["lost"] = lost
        self.sentences = [carry["lost"]] if carry["lost"] else []
        self.first = None  # the plan of step 2
        self.last = None  # the last plan this command made
        self.stopped_item = None  # the item a stop marks blocked
        self.secrets = None  # the last GitHub secrets section the switch printed
        self.switch_ready = False  # the switch, as the last read of it says
        self.steps_run = 0  # the steps of step 4 invoked in this command
        if carry["nightUnknown"]:
            self.sentences.append(NIGHT_STOP_UNKNOWN)
        self.register_abort()

    # -- small helpers --------------------------------------------------------

    def again(self):
        return " ".join(["/aleogr:platform-apply"]
                        + ["%s=%s" % (k, v) for k, v in self.args.items()])

    @property
    def values(self):
        p = self.first
        return p.reads.values if p is not None else {}

    def project_id(self):
        """The id the create step returned when it ran in this run; otherwise the last
        plan's (never guessed)."""
        if self.carry["projectId"]:
            return self.carry["projectId"]
        for p in (self.last, self.first):
            if p is not None and p.project_id:
                return p.project_id
        return None

    def add_line(self, skill, st):
        """The line `<skill>: <status>`, once per skill: a later status of the same skill
        (a step cut by a limit and run again in a later command) replaces it when it says
        more (created over updated over pending over unchanged over failed)."""
        if st not in LINE_STATUSES:
            st = "failed"
        line = "%s: %s" % (skill, st)
        made = self.carry["made"]
        for i, old in enumerate(made):
            name, _, old_st = old.rpartition(": ")
            if name == skill:
                if RANK[st] >= RANK.get(old_st, 0):
                    made[i] = line
                break
        else:
            made.append(line)
        self.register_abort()

    def instance_open(self):
        """This run asked for the creation of the instance and has not seen it stopped
        or its create end: it may exist and run."""
        return self.carry["createAsked"] and not self.carry["instanceDone"]

    def instance_sentence(self):
        pid = self.project_id() or "<projectId>"
        name = self.values.get("instance") or "<instance>"
        return INSTANCE_MAY_RUN % (name, pid, name)

    def register_abort(self):
        """What an aborted run (the time limit, an unexpected error, a command of another
        suite) says this run made: the lines of the skills, and, from the moment the
        create of the instance is asked for until its outcome is known, that the instance
        may exist and run, what it costs and how to stop it (ctx.on_abort)."""
        lines = list(self.carry["made"])
        if self.instance_open():
            lines.append(self.instance_sentence())
        self.ctx.on_abort(lines)

    def mark(self, plan):
        """What a plan tells: the switch's state and its GitHub secrets section, and the
        outcome of a create this run asked for in an earlier command."""
        r = plan.reads
        if r.switch is not None:
            self.switch_ready = _out(r.switch).get("ready") is True
            self.secrets = PP.switch_secrets(r.switch)
        elif plan.failure is None:
            self.switch_ready, self.secrets = False, None
        if self.instance_open() and plan.instance_state == "stopped":
            # The create asked for in an earlier command was cut after it stopped the
            # instance: this run created it.
            self.carry["instanceDone"] = True
            self.carry["instanceCreated"] = True
            self.carry["changed"] = True
            self.carry["nightUnknown"] = True
            if NIGHT_STOP_UNKNOWN not in self.sentences:
                self.sentences.append(NIGHT_STOP_UNKNOWN)
            self.add_line("gcp-cloud-sql_instance-create", "created")
        self.register_abort()

    def make_plan(self, what="the last plan", step=True):
        if step:
            self.check_step(what)
        a = {}
        pid = self.carry["projectId"]
        if pid:
            a["projectId"] = pid
        p = self._plan_fn(a)
        self.last = p
        self.mark(p)
        return p

    def check_step(self, what):
        """Before a step: the step limit, which never holds the first step of a command
        (ctx.step_allowed), so every command of a run makes at least one step."""
        if self.ctx.step_allowed():
            return
        raise Continue(CONTINUE_LINE % what, lambda: self.commands_limit(what))

    def commands_limit(self, what):
        """The eighth command reached a limit before `what`: end as a wait that passed
        its limit ends, with what was made and what is left."""
        items = [item("run", COMMANDS_LIMIT_HOW)]
        sentences = [COMMANDS_LIMIT % what]
        if self.instance_open():
            sentences.append(self.instance_sentence())
        self.end("pending", items, sentences=sentences)

    def call(self, skill, a, cut=None, line=None, limit=None):
        """Invoke a step's skill (another plugin's command); a limit of the run that
        ended it ends this command `continue` (`cut(result)` decides, by default always),
        with `line` (default: the skill comes next) and, on the eighth command,
        `limit(result)` (default: commands_limit)."""
        command = DB if skill.startswith("gcp-cloud-sql_") else CLOUD
        self.steps_run += 1
        r = self._call_fn(command, skill, a)
        if common.ended_by_limit(r) and (cut is None or cut(r)):
            st = _status(r)
            if st in ("created", "updated") or wrote_before_abort(r):
                self.add_line(skill, st)
                self.carry["changed"] = True
                self.note_created(skill, r)
            text = line(r) if line is not None else CONTINUE_LINE % skill
            end = (lambda: limit(r)) if limit is not None else (
                lambda: self.commands_limit(skill))
            raise Continue(text, end)
        return r

    def note_created(self, skill, r):
        if _status(r) != "created":
            return
        if skill == "gcp_environment-create":
            self.carry["projectCreated"] = True
        elif skill == "gcp-cloud-sql_instance-switch-setup":
            self.carry["switchCreated"] = True
        elif skill == "gcp-cloud-sql_instance-create":
            self.carry["instanceCreated"] = True

    def ran(self, skill, r):
        """The line of a step that ran, and what it changed."""
        st = _status(r)
        self.add_line(skill, st)
        if st in ("created", "updated"):
            self.carry["changed"] = True
        self.note_created(skill, r)

    # -- the answer -----------------------------------------------------------

    def plan_rows(self, plan):
        rows = [list(x) for x in plan.items]
        if self.stopped_item is not None:
            for x in rows:
                if x[0] == self.stopped_item:
                    x[2] = PP.BLOCKED
        return rows

    def login_stands(self):
        """The login step's items and list, unless the last plan, made after it, reads
        the login as prepared (the owner's clicks may have been made since)."""
        login = self.carry["login"]
        if login is None:
            return False
        p = self.last
        if p is not None and p.failure is None and p.action("login") == NONE:
            return False
        return True

    def cost(self):
        p = self.last
        if (p is not None and p.instance_exists is True) or self.carry["instanceCreated"] \
                or self.instance_open():
            return dict(INSTANCE_COST)
        return dict(FREE_COST)

    def outputs(self, rows):
        return {"projectId": self.project_id(),
                "items": [{"item": i, "state": s, "action": a} for i, s, a in rows]}

    def resources(self):
        pid = self.project_id()
        if pid is None:
            return []
        return [{"type": "project", "id": pid, "name": self.values.get("project") or "shared",
                 "labels": {}}]

    def login_lines(self):
        """The section `Login`: the setup's list, once, exactly as it gave it, the command
        in a fenced bash block of its own; then the line to run the plan, when the list's
        last line does not say it already."""
        steps = self.carry["login"]["steps"] if self.carry["login"] else []
        if not steps:
            return []
        out = [LOGIN_TITLE, ""]
        for s in steps:
            if re.match(r"[0-9]+\. ", s):
                out.append(s)
            else:
                out += ["```bash", s, "```"]
        if "/aleogr:platform-plan" not in steps[-1]:
            out.append(LOGIN_PLAN_LINE)
        return out

    def answer(self, status, pending=(), sentences=(), nothing=False, plan=None):
        """Every ending, in the SKILL.md's order: one line per step of step 4 that ran;
        the table of the last plan with the lines it printed under it (and `nothing to
        do`); the prescribed sentences, each once; the GitHub secrets section; the Login
        section; the `how` of each pending item; the block."""
        plan = plan if plan is not None else self.last
        lines = list(self.carry["made"])
        rows = self.plan_rows(plan) if plan is not None else []
        if rows:
            if lines:
                lines.append("")
            lines += common.render_table(["Item", "State", "Action"], rows)
            under = PP.lines_under(plan)
            if nothing:
                under = under + [NOTHING_TO_DO]
            if under:
                lines += [""] + under
        elif plan is not None and plan.failure is not None:
            lines += ([""] if lines else []) + [plan.failure.sentence]
        said = []
        cost = [COST_LINE] if self.carry["createAsked"] else []
        for s in list(self.sentences) + cost + list(sentences):
            if s and s not in said and s not in lines:
                said.append(s)
        if said:
            lines += [""] + said
        if self.switch_ready and self.secrets:
            lines += [""] + list(self.secrets) + ["", SECRETS_ONCE]
        pending = list(pending)
        if self.login_stands():
            for x in self.carry["login"]["pending"]:
                if x not in pending:
                    pending.append(x)
            section = self.login_lines()
            if section:
                lines += [""] + section
        hows = []
        for x in pending:
            if isinstance(x, dict) and x.get("how") and x["how"] not in hows:
                hows.append(x["how"])  # each once (two parts with one fix)
        if hows:
            lines += [""] + hows
        return self.ctx.result(status, self.outputs(rows), resources=self.resources(),
                               pending=pending, cost=self.cost(), lines=lines)

    def end(self, *a, **kw):
        raise End(self.answer(*a, **kw))

    def final_status(self, base):
        """The status when every step succeeded: created when the project, the switch or
        the instance was created in this run; updated when something else changed; else
        `base`."""
        c = self.carry
        if c["projectCreated"] or c["switchCreated"] or c["instanceCreated"]:
            return "created"
        if c["changed"]:
            return "updated"
        return base

    def stop(self, skill, r, status=None, sentences=None, items=None):
        """A step ended failed or pending: no later step, the same status, its item
        blocked, its `pending[].how` carried."""
        st = status or (_status(r) if _status(r) in ("pending", "failed") else "failed")
        self.stopped_item = ITEM_OF.get(skill)
        if items is None:
            items = _pending(r)
            if not items:
                items = [item(ITEM_OF.get(skill, skill),
                              STEP_FAILED_HOW % PP.as_how(first_sentence(r)))]
        if sentences is None:
            sentences = [first_sentence(r)]
        if self.instance_open():
            sentences = list(sentences) + [self.instance_sentence()]
        self.end(st, items, sentences=sentences)

    # ======================================================================
    # Step 2: the plan

    def step_2(self):
        # The first plan of a command is never held by the step limit.
        p = self.first = self.make_plan("the plan", step=False)
        if p.failure is not None:
            sentences = [self.instance_sentence()] if self.instance_open() else []
            self.end("failed", list(p.pending), sentences=sentences)
        if p.status == "unchanged" and not self.needs_resume(p):
            self.end(self.final_status("unchanged"), [], nothing=True)

    def needs_resume(self, plan):
        return (self.instance_open() and plan.instance_exists is True
                and plan.instance_state != "stopped")

    # ======================================================================
    # Step 3: the confirmation, before any change

    def step_3(self):
        if self.confirm:
            return
        p = self.first
        sentences = []
        if p.action("database instance") == PP.CREATE:
            sentences.append(COST_LINE)
        if p.action("login") == PP.PREPARE:
            sentences.append(LOGIN_SENTENCE)
        self.end("pending", [item("confirm", CONFIRM_HOW)], sentences=sentences)

    # ======================================================================
    # Step 4: create, in order

    def step_4(self):
        p = self.first
        if p.action("shared project") != NONE:
            self.step_4_1()
        if p.action("services") != NONE:
            self.step_4_2()
        if p.action("budget alert") != NONE:
            self.step_4_3()
        if p.action("database switch") != NONE:
            self.step_4_4()
        self.step_4_5()
        if p.action("login") != NONE and self.carry["login"] is None:
            self.step_4_6()

    def due_project_id(self, skill):
        pid = self.project_id()
        if pid is None:
            self.stopped_item = ITEM_OF[skill]
            self.end("failed", [item(ITEM_OF[skill], NO_PROJECT_ID_HOW)],
                     sentences=[NO_PROJECT_ID % skill])
        return pid

    def step_4_1(self):
        skill = "gcp_environment-create"
        self.check_step(skill)

        def cut(r):
            pid = _out(r).get("projectId")
            if isinstance(pid, str) and PROJECT_ID_RE.fullmatch(pid):
                self.carry["projectId"] = pid
            return True
        r = self.call(skill, {"project": self.values["project"], "platform": "shared",
                              "mode": "apply"}, cut=cut)
        pid = _out(r).get("projectId")
        if isinstance(pid, str) and PROJECT_ID_RE.fullmatch(pid):
            self.carry["projectId"] = pid
        self.ran(skill, r)
        if _status(r) not in ("created", "updated", "unchanged"):
            self.stop(skill, r)

    def step_4_2(self):
        skill = "gcp_services-enable"
        pid = self.due_project_id(skill)
        self.check_step(skill)
        r = self.call(skill, {"projectId": pid, "services": ",".join(self.values["services"]),
                              "mode": "apply"})
        self.ran(skill, r)
        if _status(r) not in ("updated", "unchanged"):
            self.stop(skill, r)

    def step_4_3(self):
        skill = "gcp_budget-alert-setup"
        pid = self.due_project_id(skill)
        self.check_step(skill)
        v = self.values
        r = self.call(skill, {"displayName": v["displayName"], "amount": v["amount"],
                              "currency": v["currency"], "thresholds": ",".join(v["thresholds"]),
                              "quotaProject": pid, "mode": "apply"})
        self.ran(skill, r)
        if _status(r) not in ("created", "updated", "unchanged"):
            self.stop(skill, r)

    def step_4_4(self):
        skill = "gcp-cloud-sql_instance-switch-setup"
        pid = self.due_project_id(skill)
        self.check_step(skill)
        r = self.call(skill, PP.switch_args(self.values, pid, "apply"))
        self.ran(skill, r)
        self.switch_ready = _out(r).get("ready") is True
        section = PP.switch_secrets(r)
        if section:
            self.secrets = section
        if _status(r) not in ("created", "updated", "unchanged"):
            self.stop(skill, r)

    def create_args(self, pid, resume):
        v = self.values
        a = {"projectId": pid, "instance": v["instance"], "platform": "shared",
             "mode": "apply", "confirm": "yes", "version": v["version"], "tier": v["tier"],
             "edition": v["edition"], "region": v["region"], "storageGb": v["storageGb"],
             "backupStartUtc": v["backupStartUtc"],
             "retainedBackups": v["retainedBackups"], "stopJob": STOP_JOB}
        if resume:
            a["resume"] = "yes"
        return a

    def step_4_5(self):
        """The database instance: created when the plan says so; when this run asked for
        its creation in an earlier command, resumed (resume=yes) while it exists and is
        not stopped, never created a second time."""
        skill = "gcp-cloud-sql_instance-create"
        p = self.first
        c = self.carry
        if c["instanceDone"]:
            return
        if c["createAsked"]:
            if p.instance_exists is False:
                self.stopped_item = ITEM_OF[skill]
                self.end("pending", [item("database instance", INSTANCE_GONE_HOW)],
                         sentences=[INSTANCE_GONE % self.values["instance"]])
            if p.instance_exists is not True:
                self.stopped_item = ITEM_OF[skill]
                name = self.values["instance"]
                self.end("pending", [item("instance", stop_how(self.project_id(), name))],
                         sentences=[INSTANCE_NOT_READ % name, self.instance_sentence()])
            if p.instance_state == "stopped":  # mark() has taken it
                return
            resume = True
        elif p.action("database instance") == PP.CREATE:
            resume = False
        else:
            return
        pid = self.due_project_id(skill)
        # Before this step, the cost line (answer(): said whenever this run asked for the
        # creation, in this command or an earlier one).
        self.check_step(skill)
        # From here until its outcome is known, the instance may exist and run.
        c["createAsked"] = True
        self.register_abort()

        def cut(r):
            # Cut by a limit while the instance still runs or is being created: the next
            # command resumes it. An ending with the instance stopped stands.
            return _out(r).get("state") != "stopped"

        def line(r):
            return INSTANCE_CONTINUE % (_out(r).get("state") or "being created")
        r = self.call(skill, self.create_args(pid, resume), cut=cut, line=line,
                      limit=self.instance_limit)
        st = _status(r)
        c["instanceDone"] = True
        self.ran(skill, r)
        if st == "unchanged":
            self.sentences += [l for l in _answer(r) if l.startswith(RESUME_REFUSED_PREFIX)]
            return
        if st == "created":
            return
        self.stop(skill, r, sentences=self.relayed(r))

    def relayed(self, r):
        """The create's sentences as it wrote them, without its two cost sentences (this
        skill's cost line says it)."""
        drop = ("Creating the instance takes several minutes.", "It costs about R$ 50 per "
                "month while stopped.")
        return [l for l in _answer(r) if not l.startswith(drop)
                and not l.endswith(RESUME_GOES_ON)] or [first_sentence(r)]

    def instance_limit(self, r):
        """The eighth command, the instance still being created: the create's own ending
        of a wait that passed its limit (it runs, its cost, how to stop it)."""
        self.stopped_item = "database instance"
        name = self.values["instance"]
        items = _pending(r) or [item("instance", stop_how(self.project_id(), name))]
        sentences = [COMMANDS_LIMIT % "the database instance was stopped"]
        if _status(r) == "pending":
            sentences += self.relayed(r)
        else:
            sentences.append(self.instance_sentence())
        self.end("pending", items, sentences=sentences)

    def step_4_6(self):
        skill = "gcp_login-setup"
        pid = self.due_project_id(skill)
        self.check_step(skill)
        r = self.call(skill, {"projectId": pid, "mode": "apply"})
        st = _status(r)
        if st == "would-update":
            self.stop(skill, r, status="failed", sentences=[LOGIN_WOULD_UPDATE])
        self.ran(skill, r)
        if st not in ("unchanged", "updated", "pending"):
            self.stop(skill, r)
        if st in ("updated", "pending"):
            steps = [s for s in (_out(r).get("steps") or []) if isinstance(s, str)]
            self.carry["login"] = {"status": st, "steps": steps,
                                   "pending": _pending(r)
                                   or [item("login", "/aleogr:platform-plan")]}

    # ======================================================================
    # Step 5: the last plan

    def step_5(self):
        if self.steps_run == 0:
            # A command that ran no step (a continuation whose earlier commands made
            # everything; the login, already prepared as far as a command can, is not run
            # again): its own plan, made after every step of the run, is the last plan.
            p = self.first
        else:
            p = self.make_plan("the last plan")
        if p.failure is not None:
            sentences = [self.instance_sentence()] if self.instance_open() else []
            self.end("failed", list(p.pending), sentences=sentences)
        acting = [x for x in p.items if x[2] != NONE]
        if not acting:
            self.end(self.final_status("unchanged"), [], nothing=True)
        login_ran = self.carry["login"] is not None
        left = [x for x in acting if not (x[0] == "login" and login_ran)]
        if left:
            self.end("pending", [item(x[0], CONFIRM_HOW) for x in left])
        # Only the login is left, after the login step: its items stand in its place.
        self.end(self.final_status("pending"), [])

    # ======================================================================

    def run(self):
        try:
            self.step_2()
            self.step_3()
            self.step_4()
            self.step_5()
        except End as e:
            return e.result
        except Continue as c:
            if self.ctx.may_continue():
                return self.ctx.continue_run(c.line, self.carry, cost=self.cost())
            try:
                c.limit()
            except End as e:
                return e.result
        raise AssertionError("every path ends")  # pragma: no cover


def run(args, ctx):
    raw = read_defaults_bytes(ctx)
    carried = ctx.carried(common.carry_digest(raw, args))
    carry = new_carry()
    if carried is not None:
        valid = _valid_carry(carried)
        if valid is None:
            ctx.refuse_carry("invalid")  # a carry this module did not write: a new run
        else:
            carry = valid
    lost = ctx.carry_lost_sentence()
    problem = validate_args(args)
    if problem:
        return ctx.result("failed", {"projectId": None, "items": []},
                          pending=[item("arguments", ARGUMENTS_HOW)], cost=dict(FREE_COST),
                          lines=[problem])
    return Apply(args, ctx, carry, lost=lost).run()
