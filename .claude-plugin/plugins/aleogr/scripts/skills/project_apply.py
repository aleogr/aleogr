"""project-apply: make what the plan says is missing, in a fixed order, under one
confirmation, and end with a plan that proves it.

The rules are this module's, pinned by its unit tests (tests/unit/test_project_apply.py)
and its scenarios. It was built from skills/project-apply/SKILL.md as that text was
before the skill became a shell over this command (the text is in the repository's
history, at the commit before that change): the same invocations, in the same order, the
same gates, the same prescribed sentences and the same result block. This module runs no
provider command that changes something: every write is a called skill's, through its
plugin's command in `mode=apply`; its own commands are the plan's reads (the plan is
called as a function of this plugin, project_plan.plan) and the wait `sleep 30`.

Layout, by the SKILL.md's steps:

- run(): the arguments, the carried file of a run in more than one command, then
  step_1() ... step_5() and the_files_after_the_cloud(), each a method of Apply;
- step_4(): the declaration's update, the proposal (propose_and_generate), the
  repository's sub-steps 1 to 4 (repository_steps) and the environment's sub-steps 5 to
  13 (one method each: substep_5 ... substep_13), with the database's sub-step 12a
  driven by DATABASE_STEPS, the table of "Which steps run";
- the answer: Apply.answer() builds the lines and the block of every ending.

A run in more than one command (docs/plans/2026-11-27-scripts-step-3-design.md): before
each step, when the step limit has passed, when a called command was ended by a limit of
the run, or when the instance's wait is refused by the clock, the command ends
`continue` (ctx.continue_run); the next command starts from the top and plans again. What
is carried is only what the answer needs and cannot be read again (Carry).
"""

import importlib.util
import os
import re
import sys

import aleogr_common as common

FAMILY = "orchestrator"
PROVIDER = "aleogr"
ACTION = "project-apply"
DEFAULT_MODE = "apply"  # no mode argument: the skill acts
RESULT_MODE = "apply"  # "mode is always apply"
WRITES = False  # the orchestrator writes nothing itself
CONTINUES = True  # a run may take more than one command

DECLARATION = ".aleogr/project.json"
LOCAL_CI = ".github/workflows/ci.yml"

GH = "aleogr-repo-github"
CLOUD = "aleogr-cloud-gcp"
REGISTRY = "aleogr-registry-gcp-artifact-registry"
DB = "aleogr-db-gcp-cloud-sql"
GO = "aleogr-stack-go"
# Every other plugin's command this skill can call, in any path, in the order it first
# calls them: asked `--suite` (ctx.check_suites) right after the arguments are validated
# and before the first read, so that a plugin of another release ends the run before
# anything is read or written. A unit test checks the list against the module's calls.
SUITE_COMMANDS = (GH, GO, CLOUD, REGISTRY, DB)  # its own and its plan's

API_TRIES = 10  # the wait for just-enabled APIs: tries, the first one included
INSTANCE_TRIES = 30  # the wait for the shared instance, for the whole run
TITLE_LIMIT = 100


def _plan_module():
    """This plugin's project-plan module, loaded by its file path (as project_plan loads
    tools_check: a unit test loads this module by path, where `skills` may be another
    plugin's package)."""
    name = "aleogr_plugin_project_plan"
    if name not in sys.modules:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project_plan.py")
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
CONFIRM_VISIBILITY_NOT_NEEDED = ("confirmVisibility=%s names a change this plan does not "
                                 "have: nothing was changed.")
CREATION_NOTICE = ("The next run creates a Google Cloud project, the GCP project of dev, whose "
                   "id is permanent, with its APIs, the image repository %s with its cleanup "
                   "policy, and the CI identity %s-ci with push access to it.")
MAKES_IN_CLOUD = "With confirm=yes, this run makes in Google Cloud: %s."
START_NEEDS_CONFIRM = ("With confirm=yes, this run starts the shared database instance (about "
                       "twelve minutes); it then runs, charged by the hour, until the night "
                       "stop.")
CREATES_LINE = "This run creates the GCP project of dev, whose id is permanent."
PROPOSAL_WARNING = ("Applying this change after the merge creates a Google Cloud project, whose "
                    "id is permanent.")
DATABASE_WARNING = ("Applying this after the merge starts the shared database instance when it "
                    "is stopped: it then runs, charged by the hour, until the night stop.")
START_SENTENCE = ("This run started the shared database instance: it runs, charged by the hour, "
                  "until the night stop. To stop it sooner: "
                  "/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop, or the workflow "
                  "self-shared-database of aleogr/aleogr (action stop).")
ALREADY_STARTING = ("The shared instance was already starting: this run waited for it and did "
                    "not start it.")
NOTHING_DEPLOYED = ("Nothing is deployed yet: the CI identity can only push images to the "
                    "image repository.")
PLACEHOLDER_LINE = ("The services of %s still run the placeholder image: the first merge to "
                    "the default branch with their deploy jobs deploys them.")
APIS_WAITED = "Waited for the APIs enabled in this run: %s answered on try %d."
APIS_LIMIT = ("The APIs enabled in this run were still refused after 10 tries, about 5 "
              "minutes of waits; nothing after them was made.")
APIS_WAIT_NOT_RUN = ("The wait for the APIs enabled in this run could not be run; nothing after "
                     "them was made.")
NOT_ALL_MADE = "The database of %s was not all made; nothing after it was made."
NOTHING_FOR_DATABASE = "Nothing in Google Cloud was made for the database."
SHARED_AMBIGUOUS = ("More than one GCP project carries the labels of the shared platform: keep "
                    "one, then run /aleogr:project-plan again.")
SHARED_NOT_READY = ("The shared platform was not found or is not ready: /aleogr:platform-plan "
                    "shows what it makes and what it costs.")
SHARED_UNREADABLE = ("The shared project could not be read: check that the active gcloud "
                     "account may list and read projects, then run /aleogr:project-plan again.")
NIGHT_STOP_NOT_CONFIRMED = ("The night stop of the shared instance could not be confirmed, so "
                            "the instance was not started.")
START_STATE_UNKNOWN = "The state of the shared instance is not known, so it was not started."
INSTANCE_LIMIT_STARTED = ("The shared instance started in this run did not accept calls after "
                          "30 tries, about 15 minutes of waits; nothing after it was made.")
INSTANCE_LIMIT = ("The shared instance did not accept calls after 30 tries, about 15 minutes of "
                  "waits; nothing after it was made.")
INSTANCE_WAIT_NOT_RUN = ("The wait for the shared instance started in this run could not be "
                         "run; nothing after it was made.")
CREATION_NOT_VISIBLE = ("The GCP project %s was %s in this run, but the search by labels does "
                        "not show it yet: wait a minute, run /aleogr:project-plan, and run "
                        "/aleogr:project-apply confirm=yes only when that plan shows environment "
                        "dev as exists.")

# Prescribed items' `how`s
CONFIRM_HOW = "/aleogr:project-apply confirm=yes"
CONFIRM_PUBLIC_HOW = "/aleogr:project-apply confirmVisibility=public"
CONFIRM_PRIVATE_HOW = "/aleogr:project-apply confirmVisibility=private"
CONFIRM_START_HOW = "/aleogr:project-apply confirmVisibility=%s confirm=yes"
PR_HOW = "merge %s, then run /aleogr:project-apply confirm=yes"
AFTER_MERGE_HOW = ("%s wait for the run after the merge: merge the pull request, then run "
                   "/aleogr:project-apply confirm=yes (or the confirmVisibility that run asks "
                   "for)")
VERIFY_HOW = "/aleogr:project-plan"
GENERATE_HOW = "run /aleogr:project-apply confirm=yes to generate the components"
BIRTH_ENVIRONMENT_HOW = ("the next run creates the GCP project of dev, whose id is permanent: "
                         "read this plan, then run /aleogr:project-apply confirm=yes")
CREATION_WAIT = ("the GCP project %s was %s in this run: wait a minute, run "
                 "/aleogr:project-plan, and run /aleogr:project-apply confirm=yes only when that "
                 "plan shows environment dev as exists")
NOT_VISIBLE_HOW = ("the GCP project %s was %s in this run and is not visible to the search by "
                   "labels yet: wait a minute, run /aleogr:project-plan, and run "
                   "/aleogr:project-apply confirm=yes only when that plan shows environment dev "
                   "as exists")
APIS_HOW = ("the APIs were just enabled and may need a minute: wait a minute, then run "
            "/aleogr:project-apply confirm=yes")
APIS_HOW_CREATED = "the APIs were just enabled and may need a minute; %s"
SERVICES_HOW = ("the services were not all made as declared: run /aleogr:project-plan, and run "
                "/aleogr:project-apply confirm=yes when it shows what is left")
SECRETS_HOW = ("the repository's CI secrets were not all set: run /aleogr:project-plan, and run "
               "/aleogr:project-apply confirm=yes when it shows what is left")
DATABASE_HOW = ("the database of %s was not all made: run /aleogr:project-plan, and run "
                "/aleogr:project-apply confirm=yes when it shows what is left")
INSTANCE_STATE_HOW = ("the shared instance is %s: wait some minutes, run /aleogr:project-plan, "
                      "and run /aleogr:project-apply confirm=yes once that plan no longer says it "
                      "is %s")
INSTANCE_UNKNOWN_HOW = ("the state of the shared instance is not known: run "
                        "/aleogr:platform-plan, then /aleogr:project-plan")
NIGHT_STOP_HOW = ("the night stop of the shared instance is not confirmed: run "
                  "/aleogr:platform-plan, make what it shows, then run /aleogr:project-apply "
                  "confirm=yes")
START_FAILED_HOW = ("the shared instance could not be started: run /aleogr:platform-plan, which "
                    "shows whether it is running, then /aleogr:project-plan, and run "
                    "/aleogr:project-apply confirm=yes when it shows what is left")
INSTANCE_WAIT_HOW = ("the shared instance was started in this run and does not accept calls "
                     "yet: wait some minutes, run /aleogr:project-plan, and run "
                     "/aleogr:project-apply confirm=yes once that plan no longer says the shared "
                     "instance is starting")
FILES_KEPT_HOW = ("%s; the files written in this folder are kept: run /aleogr:project-apply "
                  "confirm=yes again, which proposes them")
BRANCH_HOW = ("%s; the generated files and the changed declaration are in the local branch %s, "
              "not in this folder: fix the cause, then %s")
BRANCH_ONLY_HOW = ("%s; the changed declaration is in the local branch %s, not in this folder: "
                   "fix the cause, then %s")
BRANCH_NEXT = "declare the components again and run /aleogr:project-apply confirm=yes"

NO_COST = {"fixed": False, "notes": "no cost"}
STARTED_COST = {"fixed": False,
                "notes": "the shared instance started in this run is charged by the hour until "
                         "the night stop"}
START_UNKNOWN_COST = {"fixed": False,
                      "notes": "the start of the shared instance failed and its state is not "
                               "known: it may be charged by the hour until the night stop"}

# ---------------------------------------------------------------------------
# Sentences the SKILL.md leaves to this skill's own words (fixed here)

ARGUMENT_UNKNOWN = ("%s is not an argument of project-apply: its arguments are confirm=yes and "
                    "confirmVisibility=public or private.")
CONFIRM_INVALID = "confirm is not valid: it must be yes."
VISIBILITY_INVALID = "confirmVisibility is not valid: it must be public or private."
ARGUMENTS_HOW = "give only confirm=yes, confirmVisibility=public or confirmVisibility=private"
WOULD_BE_PUBLIC = ("The repository would be public, its whole history visible, and its branch "
                   "protection is created once it is public.")
WOULD_BE_PRIVATE = ("The repository would become private, and its branch protection would stop "
                    "being enforced on the free plan.")
PUBLIC_NEXT_RUN = ("The repository would be public, its whole history visible: the next run "
                   "applies it.")
PRIVATE_NEXT_RUN = ("The repository would become private, and its branch protection would stop "
                    "being enforced on the free plan: the next run applies it.")
FILES_AFTER_CLOUD = ("The files to generate are written in this folder and proposed in one pull "
                     "request after the cloud is made.")
FILES_WITH_SERVICES = ("The files to generate (%s) are proposed with the services, after the "
                       "login is prepared (/aleogr:platform-plan).")
WOULD_WRITE = "With confirm=yes, this run writes in this folder: %s."
WAIT_FOR_MERGE = "%s wait for the run after the merge."
NOT_APPLIED_YET = "%s are not applied in this run: they wait for the run after the merge."
FILES_KEPT = ("The files written in this folder in this run are kept (%s): the next run "
              "proposes them.")
FILES_IN_BRANCH = ("The files written in this run are in the local branch %s, not in this "
                   "folder.")
CONTINUE_LINE = "This run goes on in its next command: %s comes next."
INSTANCE_CONTINUE = "Waiting for the shared instance: try %d of %d."
APIS_CONTINUE = "Waiting for the APIs enabled in this run: try %d of %d."
COMMANDS_LIMIT = ("This run reached its limit of eight commands before %s; nothing after it was "
                  "made.")
COMMANDS_LIMIT_HOW = ("this run reached its limit of eight commands: run /aleogr:project-plan, "
                      "and run /aleogr:project-apply confirm=yes when it shows what is left")

ENVIRONMENT_ITEMS = ("environment dev", "apis", "registry", "ci identity", "services",
                     "database", "ci secrets")
OWNER_ACTIONS = ("fix by hand", "prepare the login")


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
    """The called skill's sentence of its ending: the first line of its answer."""
    lines = _answer(result)
    if lines:
        return lines[0].strip()
    return "%s ended %s." % (result.get("action") or "A skill", _status(result))


def as_how(sentence):
    """A sentence as the start of a `how`: without its final period or its own advice to
    run it again."""
    s = sentence.strip()
    for tail in (", then run this again.", " Run this same skill again.", "."):
        if s.endswith(tail):
            return s[:-len(tail)]
    return s


def _row(plan, name):
    for row in plan.items:
        if row[0] == name:
            return row
    return None


def action(plan, name):
    row = _row(plan, name)
    return row[2] if row else None


def state(plan, name):
    row = _row(plan, name)
    return row[1] if row else None


def _names_of(state_text, prefix):
    if state_text and state_text.startswith(prefix):
        return [n.strip() for n in state_text[len(prefix):].split(",") if n.strip()]
    return []


def _join(parts):
    parts = list(parts)
    if len(parts) <= 1:
        return "".join(parts)
    if len(parts) == 2:
        return "%s and %s" % tuple(parts)
    return "%s, and %s" % (", ".join(parts[:-1]), parts[-1])


class End(Exception):
    """Ends the run with this Result."""

    def __init__(self, result):
        Exception.__init__(self, "end")
        self.result = result


class Continue(Exception):
    """A limit of the run was reached before `what`: end `continue` when the run may,
    otherwise end by `limit()` (the prose's ending of a wait that passed its limit)."""

    def __init__(self, line, limit):
        Exception.__init__(self, "continue")
        self.line = line
        self.limit = limit


# ---------------------------------------------------------------------------
# The carry: what a command gives the next one of the same run


def new_carry():
    return {
        "made": [],  # the answer's lines of the skills that made something, in order
        "repositoryCreated": False,
        "changed": False,  # something was changed by an earlier command
        "cloudChanged": False,  # something was changed in Google Cloud
        "project": None,  # {"id", "how": created|found}: the GCP project of this run
        "apisEnabled": False,  # sub-step 6 ended updated in this run
        "apisTries": 0,  # tries of an unfinished wait for just-enabled APIs
        "apisPolled": False,  # the one poll of sub-steps 7 to 11 was used in this run
        "apisAnswered": None,  # [skill, try] of APIS_WAITED, once the wait ended
        "startAsked": False,  # gcp-cloud-sql_instance-start was invoked in this run
        "startedInstance": False,
        "instanceTries": 0,
        "alreadyStarting": False,  # this run waited for an instance someone else started
        "wroteCode": False,  # step 0a of sub-step 12a wrote files
        "visibilityApplied": None,  # the confirmVisibility this run applied (I1)
        "access": None,  # the item access of gcp_deploy-setup, as it gave it
        "route": [],  # the items route of go_setup in this run
        "lost": None,  # CARRY_LOST_SENTENCE of a carry a command of this run refused
    }


# What a carried file may hold (_valid_carry): exactly what this module writes.
LOST_SENTENCES = tuple(common.CARRY_LOST_SENTENCE.format(why=why)
                       for why in common.CARRY_REFUSALS.values())
PROJECT_ID_RE = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")  # as the skills require it
LINE_STATUSES = ("created", "updated", "pending", "failed")
# Every skill this module calls, by the name its line gives it.
CALLED_SKILLS = (
    "github_checkout-setup", "github_repo-create", "github_repo-configure",
    "github_branch-protect", "github_ci-setup", "github_pull-request-open",
    "github_repo-describe", "github_variables-set", "go_setup",
    "gcp_environment-create", "gcp_services-enable", "gcp_ci-identity-setup",
    "gcp_deploy-setup", "gcp_environment-describe",
    "gcp-artifact-registry_repository-create", "gcp-artifact-registry_cleanup-configure",
    "gcp-artifact-registry_access-grant", "gcp-cloud-sql_instance-switch-setup",
    "gcp-cloud-sql_instance-start", "gcp-cloud-sql_database-describe",
    "gcp-cloud-sql_database-create", "gcp-cloud-sql_access-grant",
)
# The one key=value a line may name, by skill.
LINE_QUALIFIERS = {"go_setup": re.compile(r"component=[a-z][a-z0-9-]{0,62}"),
                   "github_branch-protect": re.compile(r"checks=ci")}
LINE_RE = re.compile(r"([a-z0-9_-]+)(?: ([A-Za-z]+=[^ :]+))?: ([a-z]+)")
ACCESS_ITEM = {"item": "access", "reason": "manual",
               "how": "/aleogr:project-access person=<e-mail>"}
ROUTE_HOW_RE = re.compile(
    r'add the line mux\.HandleFunc\("GET /db", dbCheck\) to the router in '
    r"([A-Za-z0-9._/-]{1,200})/main\.go; until then the tests of \1/db_test\.go, which "
    r"expect the route, fail")
MAX_CARRIED_LINES = 64


def valid_line(line):
    """True for a line `<skill>[ <key>=<value>]: <status>` of a skill this module calls,
    with a status a called skill gives."""
    if not isinstance(line, str):
        return False
    m = LINE_RE.fullmatch(line)
    if not m or m.group(1) not in CALLED_SKILLS or m.group(3) not in LINE_STATUSES:
        return False
    qualifier = LINE_QUALIFIERS.get(m.group(1))
    if m.group(2) is None:
        return True
    return qualifier is not None and qualifier.fullmatch(m.group(2)) is not None


def _is_int(v, low, high):
    return type(v) is int and low <= v <= high


def _valid_carry(c):
    """The carry as this module wrote it, or None when anything in it is not what this
    module writes (a file edited by hand): then the run goes on as a new one. Exactly the
    keys of new_carry, each of its type and within its range."""
    base = new_carry()
    if not isinstance(c, dict) or set(c) != set(base):
        return None
    flags = ("repositoryCreated", "changed", "cloudChanged", "apisEnabled", "apisPolled",
             "startAsked", "startedInstance", "alreadyStarting", "wroteCode")
    if any(type(c[k]) is not bool for k in flags):
        return None
    if not _is_int(c["instanceTries"], 0, INSTANCE_TRIES) \
            or not _is_int(c["apisTries"], 0, API_TRIES):
        return None
    made = c["made"]
    if not isinstance(made, list) or len(made) > MAX_CARRIED_LINES \
            or not all(valid_line(l) for l in made) or len(set(made)) != len(made):
        return None
    project = c["project"]
    if project is not None and not (
            isinstance(project, dict) and set(project) == {"id", "how"}
            and isinstance(project["id"], str) and PROJECT_ID_RE.fullmatch(project["id"])
            and project["how"] in ("created", "found")):
        return None
    answered = c["apisAnswered"]
    if answered is not None and not (
            isinstance(answered, list) and len(answered) == 2
            and answered[0] in CALLED_SKILLS + ("aleogr:project-plan",)
            and _is_int(answered[1], 2, API_TRIES)):
        return None
    if c["visibilityApplied"] not in (None, "public", "private"):
        return None
    if c["access"] is not None and c["access"] != ACCESS_ITEM:
        return None
    if c["lost"] is not None and c["lost"] not in LOST_SENTENCES:
        return None
    route = c["route"]
    if not isinstance(route, list) or len(route) > MAX_CARRIED_LINES or not all(
            isinstance(x, dict) and set(x) == {"item", "reason", "how"}
            and x["item"] == "route" and x["reason"] == "manual"
            and isinstance(x["how"], str) and ROUTE_HOW_RE.fullmatch(x["how"])
            for x in route):
        return None
    return dict(c)


# ---------------------------------------------------------------------------
# The arguments


def validate_args(args):
    """None, or the one sentence of the first argument that breaks a rule."""
    for k in args:
        if k not in ("confirm", "confirmVisibility"):
            return ARGUMENT_UNKNOWN % k
    if "confirm" in args and args["confirm"] != "yes":
        return CONFIRM_INVALID
    if "confirmVisibility" in args and args["confirmVisibility"] not in ("public", "private"):
        return VISIBILITY_INVALID
    return None


def read_declaration_bytes():
    try:
        with open(DECLARATION, "rb") as f:
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
        self._plan_fn = plan_fn or (lambda a: PP.plan(a, ctx, again=self.again()))
        self._call_fn = call_fn or (lambda command, skill, a, read_only:
                                    common.call_plugin(command, skill, a,
                                                       read_only=read_only,
                                                       caller=ctx.plugin))
        self.confirm = args.get("confirm") == "yes"
        self.visibility_arg = args.get("confirmVisibility")
        # A carry refused by this command, or by an earlier one of the run (carried in
        # `lost`): the sentence is in the run's last answer, once, whichever command
        # gives it.
        if lost:
            carry["lost"] = lost
        self.sentences = [carry["lost"]] if carry["lost"] else []
        self.first = None  # the plan of step 1
        # The plan whose declaration is the folder's: the first, then the one made
        # after the folder's update (the update rewrites the declaration).
        self.source = None
        self.plan = None  # the plan whose items are applied
        self.db_plan = None  # the database's plan of sub-step 12a
        self.last = None  # the last plan this run invoked
        self.urls_plan = None  # the last plan that read the services
        self.pull_request = None
        self.pending_extra = []  # the pull request skill's own items, ...
        self.start_unknown = False
        self.account = None  # outputs.account of sub-step 10
        self.provider = None  # outputs.provider of sub-step 10
        self.registry_created = False
        self.identity_changed = False
        self.shared_project_id = None
        self.go_done = set()  # components whose go_setup ran in this run
        self.written = []  # files written in this folder in this run
        self.github_unchanged_only = True  # every step of step 4 ended unchanged
        self.values = {}
        if carry["apisAnswered"]:
            self.sentences.append(APIS_WAITED % tuple(carry["apisAnswered"]))
        self.register_abort()

    # -- small helpers --------------------------------------------------------

    @property
    def made(self):
        return self.carry["made"]

    @property
    def project(self):
        return self.carry["project"]

    @property
    def changed(self):
        return self.carry["changed"]

    def mark_changed(self, cloud=False):
        self.carry["changed"] = True
        if cloud:
            self.carry["cloudChanged"] = True

    def add_line(self, line):
        """A line `<skill>: <status>`, once. A line `<skill>: failed` that a limit of the
        run left (cut) gives way to the same skill's `created` or `updated` that a later
        command of the run found."""
        if line in self.made:
            return
        name, _, st = line.rpartition(": ")
        if st in ("created", "updated") and "%s: failed" % name in self.made:
            self.made[self.made.index("%s: failed" % name)] = line
        else:
            self.made.append(line)
        self.register_abort()

    def register_abort(self):
        """What an aborted run (the time limit, an unexpected error) says this run made:
        the lines of the skills, the creation's line, and the start's sentence once the
        start was asked for (ctx.on_abort; the shared module prints them in place of its
        own sentence of what was written)."""
        lines = list(self.made)
        if self.project and self.project["how"] == "created":
            lines.append(CREATES_LINE)
        if self.carry["startedInstance"] or self.carry["startAsked"]:
            lines.append(START_SENTENCE)
        self.ctx.on_abort(lines)

    def start_unknown_now(self):
        """The start was asked for in this run and its outcome is not known (the start
        was cut by a limit of the run, and no later read told)."""
        return self.carry["startAsked"] and not self.carry["startedInstance"]

    def start_took(self):
        """The instance this run asked to start is found starting or running: it is this
        run's start."""
        self.carry["startedInstance"] = True
        self.mark_changed(cloud=True)
        self.add_line("gcp-cloud-sql_instance-start: updated")
        self.register_abort()

    def visibility_applied_earlier(self):
        """confirmVisibility=<value> names the visibility this run already applied (an
        earlier command of it): its check against the plan is then skipped. It confirms
        nothing by itself: the run goes on under the same confirmVisibility it was given."""
        return bool(self.visibility_arg) \
            and self.carry["visibilityApplied"] == self.visibility_arg

    def decl(self):
        return self.source.reads.decl if self.source is not None else None

    def again(self):
        """This skill as the owner ran it: `/aleogr:project-apply` and the arguments it
        was given, in their order (validated: confirm and confirmVisibility only)."""
        return " ".join(["/aleogr:project-apply"]
                        + ["%s=%s" % (k, v) for k, v in self.args.items()])

    def defaults(self, dotted):
        return PP.Defaults(self.ctx.plugin_path("defaults.json")).get(dotted, "scalar")

    def make_plan(self, args, what="the plan", step=True):
        if step:
            self.check_step(what)
        p = self._plan_fn(args)
        self.last = p
        if p.failure is None and p.outputs.get("urls") is not None:
            self.urls_plan = p
        if self.start_unknown_now() and p.failure is None and (
                (p.outputs.get("database") or {}).get("instanceState")
                in ("starting", "running")):
            self.start_took()
        return p

    def plan_args(self):
        a = {}
        if self.project:
            a["projectId"] = self.project["id"]
        if self.carry["wroteCode"]:
            a["readCloud"] = "yes"
        return a

    def check_step(self, what):
        """Before a step (a call, or a plan after the first): the step limit, which never
        holds the first step after this command's first plan (ctx.step_allowed), so every
        command of a run makes at least one step."""
        if self.ctx.step_allowed():
            return
        raise Continue(CONTINUE_LINE % what, lambda: self.commands_limit(what))

    def call(self, command, skill, a, read_only=False, what=None, step=True, line=None,
             on_cut=None):
        """Invoke a skill (another plugin's command); a limit of the run that ended it
        ends this command `continue`. `step`: the step limit is checked first (not for
        the tries of a wait, which only the clock ends). `line`: the name of its line
        (default the skill's name). `on_cut(result)`: called when a limit ended it."""
        if step:
            self.check_step(what or skill)
        r = self._call_fn(command, skill, a, read_only)
        if isinstance(r, dict) and r.get("callError") == "version":
            # A command of another suite: nothing else is run, said once, and the item is
            # this skill as the owner ran it.
            self.end("failed", [item("plugins", self.again())], sentences=[first_sentence(r)])
        if common.ended_by_limit(r):
            self.cut_line(line or skill, r, cloud=command != GH and command != GO)
            if on_cut is not None:
                on_cut(r)
            raise Continue(CONTINUE_LINE % (what or skill),
                           lambda: self.commands_limit(what or skill))
        return r

    def cut_line(self, name, r, cloud):
        """A called command that a limit of the run ended, having changed something (its
        status `created` or `updated`, or the writes it had already run before it was
        aborted): its line, with the status it gave, once."""
        st = _status(r)
        if st in ("created", "updated"):
            self.add_line("%s: %s" % (name, st))
            self.mark_changed(cloud=cloud)
        elif wrote_before_abort(r):
            self.add_line("%s: %s" % (name, st if st in LINE_STATUSES else "failed"))
            self.mark_changed(cloud=cloud)

    def note(self, name, result):
        """The answer's line of a skill of step 4 that changed something."""
        if _status(result) in ("created", "updated"):
            self.add_line("%s: %s" % (name, _status(result)))
            self.github_unchanged_only = False

    def stop_line(self, name, result):
        """The line of a skill that stopped the run."""
        if _status(result) not in ("unchanged", None):
            self.add_line("%s: %s" % (name, _status(result)))

    def creation_wait(self):
        p = self.project
        return CREATION_WAIT % (p["id"], p["how"]) if p else None

    def apply_how(self, cause):
        """The `how` of a stop in sub-steps 5 to 11: the cause, then the way on."""
        if self.project:
            return "%s; %s" % (cause, self.creation_wait())
        return "%s, then run %s" % (cause, CONFIRM_HOW)

    def status(self, base):
        """The status of an ending, from what was changed in this run (every command of
        it) and the ending's own status."""
        if self.carry["repositoryCreated"]:
            return "created"
        if self.changed:
            return "updated" if base in ("unchanged", "pending", "failed") else base
        return base

    # -- the answer -----------------------------------------------------------

    def outputs(self):
        d = self.decl()
        last = self.last
        failed = last is None or last.failure is not None
        exists = self.carry["repositoryCreated"]
        if last is not None and not failed:
            exists = exists or bool(last.reads.exists)
        elif self.first is not None and self.first.failure is None:
            exists = exists or bool(self.source.reads.exists)
        return {
            "project": d.name if d else None,
            "repository": d.full if d else None,
            "url": ("https://github.com/%s" % d.full) if (d and exists) else None,
            "items": [] if failed else list(last.outputs["items"]),
            "pullRequest": ({"number": self.pull_request["number"],
                             "url": self.pull_request["url"]}
                            if self.pull_request else None),
        }

    def cost(self):
        if self.carry["startedInstance"]:
            return dict(STARTED_COST)
        if self.start_unknown or self.start_unknown_now():
            return dict(START_UNKNOWN_COST)
        return dict(NO_COST)

    def table_lines(self, plan):
        if plan is None:
            return []
        lines = PP.answer_lines(plan)
        if plan.failure is None:
            if _row(plan, "environment dev") is not None and not plan.outputs.get("urls"):
                lines.append(NOTHING_DEPLOYED)
        return lines

    def address_lines(self):
        lines = []
        if self.pull_request:
            lines.append(self.pull_request["url"])
        source = self.urls_plan
        if self.last is not None and self.last.failure is None \
                and self.last.outputs.get("urls") is not None:
            source = self.last
        d = self.decl()
        if source is not None and d is not None:
            urls = source.outputs.get("urls") or {}
            for n in d.names:
                if urls.get(n):
                    lines.append("%s: %s" % (n, urls[n]))
            for n in d.database_names:
                if urls.get(n):
                    lines.append("%s: %s/db" % (n, urls[n]))
        if self.last is not None and self.last.failure is None:
            waiting = _names_of(state(self.last, "services"), "waiting for the first deploy: ")
            if waiting:
                lines.append(PLACEHOLDER_LINE % ", ".join(waiting))
        return lines

    def final_pending(self, items):
        """`items`, then the items route (before access), then the item access."""
        out = []
        for x in list(items) + list(self.pending_extra) + list(self.carry["route"]):
            if x not in out:
                out.append(x)
        if self.carry["access"] and self.carry["access"] not in out:
            out.append(self.carry["access"])
        return out

    def answer(self, status, pending=(), sentences=(), table=None, lines_first=None):
        """Every ending: the lines of the skills, the creation's line and the start's
        sentence, the table of the last plan with its lines, the prescribed sentences,
        the `how` of each pending item, the addresses, the block."""
        pending = self.final_pending(pending)
        lines = list(self.made)
        if self.project and self.project["how"] == "created":
            lines.append(CREATES_LINE)
        if self.carry["startedInstance"]:
            lines.append(START_SENTENCE)
        if lines_first:
            lines += lines_first
        plan = table if table is not None else self.last
        if lines and plan is not None:
            lines.append("")
        lines += self.table_lines(plan)
        said = list(self.sentences) + list(sentences)
        if self.start_unknown_now():
            said.append(START_FAILURES[2])
        if self.carry["alreadyStarting"] and not self.carry["startedInstance"] \
                and not self.carry["startAsked"]:
            said.append(ALREADY_STARTING)
        out = []
        for s in said:
            if s and s not in out and s not in lines:
                out.append(s)
        if out:
            lines += [""] + out
        hows = [p["how"] for p in pending]
        if hows:
            lines += [""] + hows
        addresses = self.address_lines()
        if addresses:
            lines += [""] + addresses
        outputs = self.outputs()
        resources = ([{"type": "repository", "id": outputs["repository"],
                       "name": self.decl().repo_name}] if outputs["url"] else [])
        return self.ctx.result(self.status(status), outputs, resources=resources,
                               pending=pending, cost=self.cost(), lines=lines)

    def end(self, *a, **kw):
        raise End(self.answer(*a, **kw))

    # -- limits ---------------------------------------------------------------

    def commands_limit(self, what):
        """The eighth command reached a limit before `what`: end as a wait that passed
        its limit ends, with what was made and what is left."""
        how = self.creation_wait() if self.project else COMMANDS_LIMIT_HOW
        self.end("pending", [item("run", how)], sentences=[COMMANDS_LIMIT % what])

    # ======================================================================
    # Step 1

    def step_1(self):
        # The first plan of a command is never held by the step limit: the command just
        # started, and every command must make progress.
        self.first = self.plan = self.make_plan(self.plan_args(), "the plan", step=False)
        p = self.first
        self.source = p
        if self.carry["apisTries"] and self.carry["apisEnabled"]:
            # A continuation of the wait for just-enabled APIs: the plan is its next try.
            p = self.first = self.plan = self.poll_plan(p, self.plan_args())
            self.source = p
        if p.failure is not None:
            if getattr(p.failure, "called", False):
                # A failed read of a skill the plan invoked: its sentence is in the table's
                # lines, once; the item's `how` is this skill as the owner ran it.
                self.end("failed", [item(p.failure.item, self.again())])
            self.end("failed", p.pending)
        if state(p, "components") == PP.NEEDS_GO:
            self.end("pending", p.pending)
        database = _row(p, "database")
        others = [row for row in p.items if row[0] != "database"]
        if database is not None and database[1] == PP.SHARED_PLATFORM \
                and all(row[2] == NONE for row in others):
            self.end("pending", p.pending)
        if all(row[2] == NONE for row in p.items):
            if self.visibility_arg and not self.visibility_applied_earlier():
                self.visibility_not_needed(p)
            self.end("unchanged", p.pending)
        acting = [row for row in p.items if row[2] != NONE]
        owners_only = all(row[2] in OWNER_ACTIONS for row in acting)
        holds = (action(p, "services") == "prepare the login"
                 and state(p, "ci") != "missing")
        with_generate = all(row[2] in OWNER_ACTIONS + ("generate",) for row in acting)
        if owners_only or (holds and with_generate and any(
                row[2] == "generate" for row in acting)):
            self.end("pending", p.pending)

    # ======================================================================
    # Step 2

    def step_2(self):
        p = self.plan
        if any(row[2] in ("merge it", "fix the folder") for row in p.items):
            self.end("pending", p.pending)

    # ======================================================================
    # Step 3: confirmation, before any change

    def declaration_action(self, plan):
        """The declaration's action, where a continuation's own proposal counts as none:
        the files step 0a wrote in an earlier command make the declaration `changed here`,
        and they are this run's proposal ("The files after the cloud")."""
        a = action(plan, "declaration")
        if (a == "propose" and self.carry["wroteCode"]
                and state(plan, "declaration") == "changed here"):
            return NONE
        return a

    def environment_acting(self, plan):
        return [row for row in plan.items if row[0] in ENVIRONMENT_ITEMS
                and row[2] not in (NONE,) + OWNER_ACTIONS]

    def exposes(self, plan):
        return plan.outputs.get("exposes") is True

    def to_private(self, plan):
        return action(plan, "visibility") == "update" and plan.outputs.get("visibility") == "private"

    def needed_confirmation(self, plan):
        if self.exposes(plan):
            return CONFIRM_PUBLIC_HOW
        if self.to_private(plan):
            return CONFIRM_PRIVATE_HOW
        if all(row[2] == NONE for row in plan.items):
            return "/aleogr:project-apply"
        return CONFIRM_HOW

    def visibility_not_needed(self, plan):
        self.end("failed", [item("confirm visibility", self.needed_confirmation(plan))],
                 sentences=[CONFIRM_VISIBILITY_NOT_NEEDED % self.visibility_arg])

    def creation_notice(self, plan):
        if action(plan, "environment dev") == "create":
            name = self.decl().name
            return [CREATION_NOTICE % (name, name)]
        return []

    def step_3(self):
        p = self.plan
        cv = self.visibility_arg
        if cv and not ((cv == "public" and self.exposes(p))
                       or (cv == "private" and self.to_private(p))) \
                and not self.visibility_applied_earlier():
            self.visibility_not_needed(p)
        if self.exposes(p) and cv != "public":
            self.end("pending", [item("confirm visibility public", CONFIRM_PUBLIC_HOW)],
                     sentences=[WOULD_BE_PUBLIC] + self.creation_notice(p))
        if self.to_private(p) and cv != "private":
            self.end("pending", [item("confirm visibility private", CONFIRM_PRIVATE_HOW)],
                     sentences=[WOULD_BE_PRIVATE] + self.creation_notice(p))
        reaches = self.declaration_action(p) == NONE
        start = bool((p.outputs.get("database") or {}).get("start")) and reaches
        if cv and start and not self.confirm:
            self.end("pending", [item("confirm", CONFIRM_START_HOW % cv)],
                     sentences=[START_NEEDS_CONFIRM])
        if not cv and not self.confirm:
            self.end("pending", [item("confirm", CONFIRM_HOW)],
                     sentences=self.unconfirmed_sentences(p))

    def unconfirmed_sentences(self, p):
        """The sentences of a missing confirm=yes: what the confirmed run makes in Google
        Cloud, and the files it writes."""
        out = []
        decl_action = self.declaration_action(p)
        acting = self.environment_acting(p)
        if acting and decl_action == NONE:
            out.append(MAKES_IN_CLOUD % self.what_in_cloud(p))
            if p.outputs.get("generate"):
                if action(p, "services") == "prepare the login" and state(p, "ci") != "missing":
                    out.append(FILES_WITH_SERVICES % ", ".join(self.files_to_generate(p)))
                else:
                    out.append(FILES_AFTER_CLOUD)
        elif acting and decl_action == "propose":
            out.append(WAIT_FOR_MERGE % _capital(", ".join(row[0] for row in acting)))
        files = self.files_to_generate(p)
        if files and p.outputs.get("generate"):
            out.append(WOULD_WRITE % ", ".join(files))
        return out

    def files_to_generate(self, p):
        d = self.decl()
        files = []
        by_name = {c["name"]: c for c in d.components} if d else {}
        for n in _names_of(state(p, "components"), "to generate: "):
            c = by_name.get(n)
            if c:
                files += ["%s/go.mod" % c["path"], "%s/main.go" % c["path"],
                          "%s/main_test.go" % c["path"]]
        if action(p, "ci") == "generate":
            files.append(LOCAL_CI)
        return files

    def held_files(self, p):
        """The files the login holds: for each component the plan's go_setup would change,
        its starting point when it has no go.mod yet, its Dockerfile when missing, and the
        CI file when it is to generate."""
        out = []
        for c, r in getattr(p.reads, "go_setup", None) or []:
            path = c["path"]
            if _status(r) != "would-create":
                continue
            if not os.path.isfile(os.path.join(path, "go.mod")):
                out += ["%s/go.mod" % path, "%s/main.go" % path, "%s/main_test.go" % path]
            if _out(r).get("dockerfile") == "would-write":
                out.append("%s/Dockerfile" % path)
        if action(p, "ci") == "generate":
            out.append(LOCAL_CI)
        return out

    def what_in_cloud(self, p):
        name = self.decl().name
        dbnames = ", ".join((p.outputs.get("database") or {}).get("components") or [])
        parts = []
        a = (lambda n: action(p, n))
        if a("environment dev") == "create":
            parts.append("the GCP project of dev, whose id is permanent, its APIs, the image "
                         "repository %s with its cleanup policy, and the CI identity %s-ci with "
                         "push access to it" % (name, name))
        if a("environment dev") == "repair":
            parts.append("the billing link of the GCP project")
        if a("apis") == "enable":
            parts.append("the APIs to enable")
        if a("registry") == "create":
            parts.append("the image repository %s with its cleanup policy" % name)
        if a("registry") == "configure":
            parts.append("its cleanup policy")
        if a("ci identity") in ("create", "update"):
            parts.append("the CI identity %s-ci and its push access" % name)
        if a("ci identity") == "grant":
            parts.append("the push access of the CI identity")
        if a("services") == "create":
            parts.append("the services of the components behind the login, with the "
                         "placeholder image")
        if a("services") == "update":
            parts.append("the repair of the services")
        if (p.outputs.get("database") or {}).get("start"):
            parts.append("the start of the shared database instance, which then runs, charged "
                         "by the hour, until the night stop")
        if a("database") == "create":
            parts.append("the database of %s on the shared instance, with their users, roles "
                         "and settings" % dbnames)
        if a("database") == "update":
            parts.append("the database settings of the services of %s" % dbnames)
        if a("ci secrets") == "set":
            parts.append("the repository's CI secrets")
        return ", ".join(parts)

    # ======================================================================
    # Step 4: act

    def step_4(self):
        p = self.plan
        decl_action = self.declaration_action(p)
        if decl_action == "update":
            self.update_the_folder()
            p = self.plan
            decl_action = self.declaration_action(p)
            if all(row[2] == NONE for row in p.items):
                return  # go to step 5
        generate = p.outputs.get("generate") is True
        cloud_first = generate and decl_action == NONE and bool(self.environment_acting(p))
        holds = self.login_holds(p)
        if generate and holds and decl_action == NONE:
            # "The login holds the files": they are named, and come with the services.
            self.sentences.append(FILES_WITH_SERVICES % ", ".join(self.held_files(p)))
        if decl_action == "propose" or (generate and not cloud_first and not holds):
            self.propose_and_generate(p, after_cloud=False)
        if not cloud_first:
            self.repository_steps(p)
        if self.decl().environments and decl_action == NONE \
                and not self.carry["repositoryCreated"]:
            self.environment_steps()

    def login_holds(self, p):
        return action(p, "services") == "prepare the login" and state(p, "ci") != "missing"

    # -- the declaration's update --------------------------------------------

    def update_the_folder(self):
        d = self.decl()
        a = {"owner": d.owner, "name": d.repo_name}
        if d.components:
            a["head"] = "check"
        a["mode"] = "apply"
        r = self.call(GH, "github_checkout-setup", a)
        st = _status(r)
        if st in ("failed", "pending"):
            self.stop_line("github_checkout-setup", r)
            self.end(st, [item("declaration", as_how(first_sentence(r)))] + _pending(r),
                     sentences=[first_sentence(r)])
        self.note("github_checkout-setup", r)
        if st == "updated":
            self.mark_changed()
            if _pending(r):
                self.end("updated", _pending(r), sentences=[first_sentence(r)])
        p = self.make_plan(self.plan_args(), "the plan after the update")
        if p.failure is not None:
            self.end("failed", [item("verify", VERIFY_HOW)])
        if self.exposes(p) or self.to_private(p):
            public = self.exposes(p)
            self.end("pending",
                     [item("confirm visibility %s" % ("public" if public else "private"),
                           CONFIRM_PUBLIC_HOW if public else CONFIRM_PRIVATE_HOW)],
                     sentences=[PUBLIC_NEXT_RUN if public else PRIVATE_NEXT_RUN]
                     + self.creation_notice(p))
        left = [row for row in p.items if row[2] in ("merge it", "fix the folder")]
        decl_left = self.declaration_action(p) in ("update", "propose")
        if left or decl_left:
            items = [x for x in p.pending]
            if decl_left:
                items.append(item("declaration", CONFIRM_HOW))
            self.end("pending", items)
        self.plan = p
        # The folder now holds the repository's declaration: every argument built
        # from here on comes from it, not from the folder as it was.
        self.source = p

    # -- the proposal (the `propose` / `generate` step) ------------------------

    def go_setup_args(self, c):
        d = self.decl()
        a = {"component": c["name"], "path": c["path"], "version": c["version"],
             "module": d.module(c)}
        if d.environments:
            a["dockerfile"] = "yes"
        if c.get("database") is True:
            a["database"] = "yes"
            a["modules"] = ",".join(self.source.reads.values["modules"])
            a["minVersion"] = self.source.reads.values["minVersion"]
        a["mode"] = "apply"
        return a

    def go_setup(self, c):
        """One go_setup in mode=apply; (result, ok). The files it wrote are added to
        self.written."""
        r = self.call(GO, "go_setup", self.go_setup_args(c), what="go_setup of %s" % c["name"],
                      line="go_setup component=%s" % c["name"])
        self.go_done.add(c["name"])
        o = _out(r)
        files = o.get("files") or []
        path = c["path"]
        wrote = []
        if o.get("written") is True:
            wrote += files[:3]
        if o.get("dockerfile") == "written":
            wrote.append("%s/Dockerfile" % path)
        if c.get("database") is True:
            if o.get("database") == "written":
                wrote += ["%s/db.go" % path, "%s/db_test.go" % path]
            if o.get("route") == "added":
                wrote.append("%s/main.go" % path)
            if o.get("modules") == "added":
                wrote += ["%s/go.mod" % path, "%s/go.sum" % path]
        for f in wrote:
            if f not in self.written:
                self.written.append(f)
        if _status(r) == "created":
            self.mark_changed()
        others = [x for x in _pending(r) if x.get("item") != "route"]
        routes = [x for x in _pending(r) if x.get("item") == "route"]
        ok = (_status(r) in ("created", "unchanged") and not others
              and (not routes or c.get("database") is True))
        if ok:
            for x in routes:
                if x not in self.carry["route"]:
                    self.carry["route"].append(x)
        line = "go_setup component=%s" % c["name"]
        if ok:
            self.note(line, r)
        else:
            self.stop_line(line, r)
        return r, ok

    def tooling_paths(self):
        """<tooling paths>, in the SKILL.md's order."""
        d = self.decl()
        if not d.components:
            return [DECLARATION]
        paths = [DECLARATION, LOCAL_CI]
        for c in d.components:
            p = c["path"]
            paths += ["%s/go.mod" % p, "%s/main.go" % p, "%s/main_test.go" % p]
            if d.environments:
                paths.append("%s/Dockerfile" % p)
            if c.get("database") is True:
                paths += ["%s/go.sum" % p, "%s/db.go" % p, "%s/db_test.go" % p]
        return paths

    def title(self, plan, ci_written):
        d = self.decl()
        if not d.components:
            return "Change the project declaration"
        among = list(plan.outputs.get("changed") or []) + list(self.written)
        if ci_written:
            among.append(LOCAL_CI)
        ci = LOCAL_CI in among
        tail = " and CI" if ci else ""

        def within(text, short):
            return text if len(text) <= TITLE_LIMIT else short

        starting, check, docker = [], [], []
        changed = set(plan.outputs.get("changed") or [])
        for c in d.components:
            p, n = c["path"], c["name"]
            gomod = "%s/go.mod" % p
            if (gomod in changed and "%s/main_test.go" % p in changed) or (
                    gomod in self.written and "%s/main_test.go" % p in self.written):
                starting.append(n)
            if c.get("database") is True and any(
                    f in among for f in ("%s/db.go" % p, "%s/db_test.go" % p)) or (
                    c.get("database") is True and any(
                        f in self.written for f in ("%s/main.go" % p, gomod, "%s/go.sum" % p))):
                check.append(n)
            if "%s/Dockerfile" % p in among:
                docker.append(n)
        if starting:
            return within("Add the components %s and CI" % ", ".join(sorted(starting)),
                          "Add the components and CI")
        if check:
            return within("Add the database check of %s%s" % (", ".join(sorted(check)), tail),
                          "Add the database check%s" % tail)
        if docker:
            return within("Add the Dockerfiles of %s%s" % (", ".join(sorted(docker)), tail),
                          "Add the Dockerfiles%s" % tail)
        if ci:
            return "Update CI"
        return "Change the project declaration"

    def adds_environment(self):
        d = self.decl()
        if not d.environments:
            return False
        listed = self.first.outputs.get("repositoryEnvironments")
        return listed is None or "dev" not in listed

    def adds_database(self):
        d = self.decl()
        names = d.database_names
        if not names:
            return False
        listed = self.first.outputs.get("repositoryDatabaseComponents")
        return listed is None or any(n not in listed for n in names)

    def propose_and_generate(self, plan, after_cloud):
        """Sub-steps 1 to 3 of the `propose` / `generate` step: the components' starting
        points, the CI file, the pull request. It always ends the run."""
        d = self.decl()
        # 1. go_setup for each component to generate (none when components is none)
        by_name = {c["name"]: c for c in d.components}
        for n in sorted(_names_of(state(plan, "components"), "to generate: ")):
            c = by_name.get(n)
            if c is None or n in self.go_done:
                continue
            r, ok = self.go_setup(c)
            if not ok:
                self.generation_stop(plan, n, r)
        # 2. the CI file
        ci_written = False
        if action(plan, "ci") == "generate":
            a = {"owner": d.owner, "name": d.repo_name, "components": d.components_arg(),
                 "workflows": self.source.reads.values["workflows"],
                 "defaultBranch": plan.outputs.get("defaultBranch")}
            deploy = plan.outputs.get("ciDeployComponents") or []
            if deploy:
                a.update({"deploy": "dev", "deployComponents": ",".join(deploy),
                          "project": d.name, "region": d.region})
            a["mode"] = "apply"
            r = self.call(GH, "github_ci-setup", a)
            ok = _status(r) in ("created", "updated", "unchanged") and not _pending(r)
            if _status(r) in ("created", "updated"):
                ci_written = True
                self.mark_changed()
                if LOCAL_CI not in self.written:
                    self.written.append(LOCAL_CI)
            if not ok:
                self.stop_line("github_ci-setup", r)
                self.generation_stop(plan, "ci", r)
            self.note("github_ci-setup", r)
        # 3. the pull request
        notes = []
        if self.adds_environment():
            notes.append(PROPOSAL_WARNING)
        if self.adds_database():
            notes.append(DATABASE_WARNING)
        title = self.title(plan, ci_written)
        a = {"owner": d.owner, "name": d.repo_name, "paths": ",".join(self.tooling_paths()),
             "title": title}
        if notes:
            a["note"] = " ".join(notes)
        a["mode"] = "apply"
        r = self.call(GH, "github_pull-request-open", a)
        self.proposal_ending(plan, r, notes, after_cloud)

    def generation_stop(self, plan, what, r):
        """A stop of sub-step 1 or 2 (or of the pull request before its commit)."""
        cause = first_sentence(r)
        sentences = [cause]
        if self.written:
            sentences.append(FILES_KEPT % ", ".join(self.written))
            items = [item(what, FILES_KEPT_HOW % as_how(cause))] + _pending(r)
            self.end("updated", items, sentences=sentences, table=plan)
        st = _status(r) if _status(r) in ("failed", "pending") else "failed"
        self.end(st, [item(what, as_how(cause))] + _pending(r), sentences=sentences,
                 table=plan)

    def proposal_ending(self, plan, r, notes, after_cloud):
        st = _status(r)
        o = _out(r)
        pr = o.get("pullRequest") if isinstance(o.get("pullRequest"), dict) else None
        cause = first_sentence(r)
        if st == "created" and pr:
            self.add_line("github_pull-request-open: created")
            self.mark_changed()
            self.pull_request = {"number": pr.get("number"), "url": pr.get("url")}
            items = [item("pull request #%s is open" % pr.get("number"),
                          PR_HOW % pr.get("url"))] + _pending(r)
            sentences = list(notes)
            later = []
            for row in plan.items:
                if row[2] in (NONE,) + OWNER_ACTIONS:
                    continue
                if row[0] in ("settings", "visibility", "protection") or (
                        row[0] in ENVIRONMENT_ITEMS and not after_cloud):
                    later.append(row[0])
            if later:
                text = ", ".join(later)
                items.append(item("after the merge", AFTER_MERGE_HOW % text))
                sentences.append(NOT_APPLIED_YET % _capital(text))
            items += [x for x in plan.pending if self.owner_item(plan, x)]
            self.end("updated", items, sentences=sentences, table=plan)
        # Any other ending: a stop.
        branch = _local_branch(r)
        if branch:
            own = _pending(r)
            nxt = None
            for x in own:
                if x.get("item") == "open the pull request":
                    nxt = x.get("how")
            rest = [x for x in own if x.get("item") != "open the pull request"]
            template = BRANCH_HOW if self.written else BRANCH_ONLY_HOW
            how = template % (as_how(cause), branch, nxt or BRANCH_NEXT)
            sentences = [cause]
            if self.written:
                sentences.append(FILES_IN_BRANCH % branch)
            self.mark_changed()
            self.end("updated", [item("declaration", how)] + rest, sentences=sentences,
                     table=plan)
        if st == "updated":
            self.mark_changed()
            self.end("updated", [item("declaration", as_how(cause))] + _pending(r),
                     sentences=[cause], table=plan)
        if st == "unchanged":
            if self.written:
                self.generation_stop(plan, "declaration", r)
            self.end("failed", [item("declaration", VERIFY_HOW)], sentences=[cause],
                     table=plan)
        if self.written:
            self.generation_stop(plan, "declaration", r)
        self.end(st if st in ("failed", "pending") else "failed",
                 [item("declaration", as_how(cause))] + _pending(r),
                 sentences=_answer(r)[:2] or [cause], table=plan)

    def owner_item(self, plan, x):
        """The plan's items for `fix by hand` and `prepare the login`."""
        return x.get("item") in ("registry", "ci identity", "login", "go") or (
            x.get("item") == "database" and state(plan, "database") in (PP.TOO_LONG,
                                                                        PP.SHARED_PLATFORM))

    # -- the repository's sub-steps 1 to 4 -------------------------------------

    def repository_stop(self, what, name, r):
        """A stop of sub-steps 1 to 4: after a change, step 5 still runs."""
        self.stop_line(name, r)
        cause = first_sentence(r)
        items = [item(what, as_how(cause))] + _pending(r)
        if self.changed:
            raise _ToStep5(items, [cause])
        st = _status(r) if _status(r) in ("failed", "pending") else "failed"
        self.end(st, items, sentences=[cause], table=self.first)

    def visibility_done(self, value):
        """This run applied the visibility `value` it was confirmed with."""
        if value and value == self.visibility_arg:
            self.carry["visibilityApplied"] = value

    def visibility_cut(self, r, value):
        """A limit of the run ended the skill that applies the visibility after it
        changed something: the visibility may be applied. The next command's plan reads
        it: still to change, the check of step 3 holds as before; applied, the check is
        skipped for this run's own change (visibility_applied_earlier)."""
        if _status(r) in ("created", "updated") or wrote_before_abort(r):
            self.visibility_done(value)

    def repository_steps(self, p):
        d = self.decl()
        topics = ",".join(sorted(set(d.declared_topics)))
        made_public = False
        created = False
        # 1. the repository
        if action(p, "repository") == "create":
            a = {"owner": d.owner, "name": d.repo_name, "visibility": d.visibility,
                 "description": d.description, "topics": topics}
            if d.visibility == "public":
                a["confirmVisibility"] = "public"
            a["mode"] = "apply"
            public = a.get("confirmVisibility") == "public"
            r = self.call(GH, "github_repo-create", a,
                          on_cut=lambda r: self.visibility_cut(r, "public" if public else None))
            if _status(r) != "created" or _pending(r):
                self.repository_stop("repository", "github_repo-create", r)
            if public:
                self.visibility_done("public")
            self.note("github_repo-create", r)
            self.carry["repositoryCreated"] = True
            self.mark_changed()
            created = True
        # 2. its settings
        if action(p, "settings") == "update" or action(p, "visibility") == "update" or created:
            a = {"owner": d.owner, "name": d.repo_name, "description": d.description,
                 "topics": topics}
            for k in PP.SETTINGS_KEYS:
                a[k] = "true" if d.settings[k] else "false"
            if action(p, "visibility") == "update":
                a["visibility"] = d.visibility
                a["confirmVisibility"] = d.visibility
            a["mode"] = "apply"
            given = a.get("confirmVisibility")
            r = self.call(GH, "github_repo-configure", a,
                          on_cut=lambda r: self.visibility_cut(r, given))
            if _status(r) not in ("updated", "unchanged") or _pending(r):
                self.repository_stop("settings", "github_repo-configure", r)
            self.note("github_repo-configure", r)
            if _status(r) == "updated" and given:
                self.visibility_done(given)
            if _status(r) == "updated":
                self.mark_changed()
                if action(p, "visibility") == "update" and d.visibility == "public":
                    made_public = True
        # 3. the declaration, sent as the first content
        if action(p, "declaration") == "send" or created:
            r = self.call(GH, "github_checkout-setup",
                          {"owner": d.owner, "name": d.repo_name, "mode": "apply"})
            if _status(r) not in ("created", "unchanged") or _pending(r):
                self.repository_stop("declaration", "github_checkout-setup", r)
            self.note("github_checkout-setup", r)
            if _status(r) == "created":
                self.mark_changed()
        # 4. the protection
        if action(p, "protection") in ("create", "update") or created or made_public:
            a = {"owner": d.owner, "name": d.repo_name}
            name = "github_branch-protect"
            if p.outputs.get("checks") == "ci":
                a["checks"] = "ci"
                name = "github_branch-protect checks=ci"
            a["mode"] = "apply"
            r = self.call(GH, "github_branch-protect", a, line=name)
            limit = (d.visibility == "private" and _status(r) == "pending"
                     and all(x.get("reason") == "plan-limit" for x in _pending(r))
                     and _pending(r))
            if not limit and (_status(r) not in ("created", "updated", "unchanged")
                              or _pending(r)):
                self.repository_stop("protection", name, r)
            self.note(name, r)
            if _status(r) in ("created", "updated"):
                self.mark_changed()

    # -- the environment's sub-steps 5 to 13 -----------------------------------

    def environment_steps(self):
        p = self.plan
        self.db_plan = p
        ran5 = self.substep_5()
        ran6, updated6 = self.substep_6(ran5)
        if self.project is None and (self.env_updated or updated6):
            self.substep_7()
        self.substep_8()
        self.substep_9()
        ran10 = self.substep_10()
        self.substep_11(ran10)
        ran12 = self.substep_12()
        self.substep_12b(ran12)
        self.substep_12a()
        self.substep_13()
        self.ran_environment = True

    env_updated = False

    def cloud_stop(self, what, name, r, items=None, sentences=None, step5=True):
        """A stop in sub-steps 5 to 13: step 5 runs when something was changed."""
        self.stop_line(name, r)
        own = items is not None  # sub-steps 12 and 13: their one item, and only it
        if items is None:
            cause = first_sentence(r)
            items = [item(what, self.apply_how(as_how(cause)))] + _pending(r)
            sentences = [cause] if sentences is None else sentences
        if self.changed and step5:
            raise _ToStep5(items, sentences or [], own_items=own)
        st = _status(r) if _status(r) in ("failed", "pending") else "failed"
        if self.changed:
            st = "updated"
        self.end(st, items, sentences=sentences or [])

    def substep_5(self):
        p = self.plan
        a = action(p, "environment dev")
        if a not in ("create", "repair"):
            return False
        d = self.decl()
        args = {"project": d.name, "environment": "dev"}
        if (d.cloud or {}).get("root") == "tst":
            args["root"] = "tst"
        args["mode"] = "apply"
        r = self.call(CLOUD, "gcp_environment-create", args, what="the GCP project of dev")
        st = _status(r)
        pid = _out(r).get("projectId")
        if a == "create" and isinstance(pid, str) and pid and st != "failed":
            self.carry["project"] = {"id": pid,
                                     "how": "created" if st in ("created", "pending")
                                     else "found"}
            self.register_abort()
        if st in ("created", "updated") or (st == "pending" and self.project):
            self.mark_changed(cloud=True)
        if st in ("created", "updated", "unchanged") and not _pending(r):
            self.note("gcp_environment-create", r)
            self.project_id = pid
            self.env_updated = st == "updated" and a == "repair"
            return True
        self.cloud_stop("environment dev", "gcp_environment-create", r)

    project_id = None

    def current_project_id(self):
        if self.project:
            return self.project["id"]
        if self.project_id:
            return self.project_id
        env = self.plan.outputs.get("environment") or {}
        return env.get("projectId")

    def services_list(self):
        d = self.decl()
        services = list(self.source.reads.values["services"])
        if d.database_components:
            services.append("sqladmin.googleapis.com")
        return services

    def substep_6(self, ran5):
        if not (action(self.plan, "apis") == "enable" or ran5):
            return False, False
        r = self.call(CLOUD, "gcp_services-enable",
                      {"projectId": self.current_project_id(),
                       "services": ",".join(self.services_list()), "mode": "apply"},
                      what="the APIs")
        if _status(r) in ("updated", "unchanged") and not _pending(r):
            self.note("gcp_services-enable", r)
            if _status(r) == "updated":
                self.mark_changed(cloud=True)
                self.carry["apisEnabled"] = True
            return True, _status(r) == "updated"
        if _status(r) in ("created", "updated"):
            self.mark_changed(cloud=True)
        self.cloud_stop("apis", "gcp_services-enable", r)

    # -- the wait for just-enabled APIs ----------------------------------------

    def refused_plan(self, plan):
        return (self.carry["apisEnabled"] and plan.failure is not None
                and plan.failure.item in ("registry", "ci identity", "services"))

    def poll_plan(self, plan, args):
        """The plan polled by the wait for just-enabled APIs (sub-step 7, step 5, or the
        first plan of a continuation of that wait)."""
        tries = self.carry["apisTries"] + 1  # this plan is the next try of the run
        while self.refused_plan(plan):
            if tries >= API_TRIES:
                self.apis_limit(APIS_LIMIT)
            self.carry["apisTries"] = tries
            self.api_wait(tries)
            tries += 1
            plan = self.make_plan(args, "the plan", step=False)
        self.apis_answered("aleogr:project-plan", tries)
        return plan

    def apis_answered(self, skill, tries):
        """The wait for just-enabled APIs is over: its tries are spent, and its sentence,
        when it waited, is said once in the run (carried to the run's last answer)."""
        self.carry["apisTries"] = 0
        if tries > 1 and self.carry["apisAnswered"] is None:
            self.carry["apisAnswered"] = [skill, tries]
            self.sentences.append(APIS_WAITED % (skill, tries))

    def api_wait(self, tries):
        if not self.ctx.wait():
            raise Continue(APIS_CONTINUE % (tries, API_TRIES),
                           lambda: self.apis_limit(APIS_WAIT_NOT_RUN))

    def apis_limit(self, sentence):
        how = (APIS_HOW_CREATED % self.creation_wait()) if self.project else APIS_HOW
        self.end("updated", [item("apis", how)], sentences=[sentence])

    def poll_call(self, command, skill, args, what):
        """A Google Cloud skill of sub-steps 8 to 11: the first one after an enable is
        polled while it ends failed having changed nothing."""
        polled = self.carry["apisEnabled"] and not self.carry["apisPolled"]
        self.carry["apisPolled"] = True
        r = self.call(command, skill, args, what=what)
        if not polled:
            return r
        tries = 1
        while _status(r) == "failed":
            if tries >= API_TRIES:
                self.apis_limit(APIS_LIMIT)
            # A continuation goes on with the plan as the next try: it reads the same.
            self.carry["apisTries"] = tries
            self.api_wait(tries)
            tries += 1
            r = self.call(command, skill, args, what=what, step=False)
        self.apis_answered(skill, tries)
        return r

    def substep_7(self):
        args = self.plan_args()
        self.carry["apisPolled"] = True
        p = self.make_plan(args, "the plan")
        if self.carry["apisEnabled"]:
            p = self.poll_plan(p, args)
        if p.failure is not None:
            raise _Final("updated", [item("verify", VERIFY_HOW)])
        acting = [row for row in p.items if row[2] != NONE]
        if all(row[2] in OWNER_ACTIONS for row in acting):
            raise _Final("updated", p.pending)
        left = [row[0] for row in acting if row[0] in ("environment dev", "apis")]
        if left:
            raise _Final("updated", [item(n, CONFIRM_HOW) for n in left])
        self.plan = p
        self.db_plan = p

    def created_or_found(self):
        return self.project is not None

    def substep_8(self):
        if not (action(self.plan, "registry") == "create" or self.created_or_found()):
            return
        d = self.decl()
        r = self.poll_call(REGISTRY, "gcp-artifact-registry_repository-create",
                           {"projectId": self.current_project_id(), "project": d.name,
                            "environment": "dev", "region": d.region, "mode": "apply"},
                           "the image repository")
        if _status(r) in ("created", "unchanged") and not _pending(r):
            self.note("gcp-artifact-registry_repository-create", r)
            if _status(r) == "created":
                self.registry_created = True
                self.mark_changed(cloud=True)
            return
        if _status(r) in ("created", "updated"):
            self.mark_changed(cloud=True)
        self.cloud_stop("registry", "gcp-artifact-registry_repository-create", r)

    def substep_9(self):
        if not (action(self.plan, "registry") in ("create", "configure")
                or self.created_or_found()):
            return
        d = self.decl()
        r = self.poll_call(REGISTRY, "gcp-artifact-registry_cleanup-configure",
                           {"projectId": self.current_project_id(), "project": d.name,
                            "region": d.region,
                            "keep": PP._scalar_text(self.source.reads.values["keep"]),
                            "mode": "apply"}, "the cleanup policy")
        if _status(r) in ("updated", "unchanged") and not _pending(r):
            self.note("gcp-artifact-registry_cleanup-configure", r)
            if _status(r) == "updated":
                self.mark_changed(cloud=True)
            return
        if _status(r) in ("created", "updated"):
            self.mark_changed(cloud=True)
        self.cloud_stop("registry", "gcp-artifact-registry_cleanup-configure", r)

    def substep_10(self):
        if not (action(self.plan, "ci identity") in ("create", "update")
                or self.created_or_found()):
            return False
        d = self.decl()
        r = self.call(GH, "github_repo-describe", {"owner": d.owner, "name": d.repo_name},
                      read_only=True, what="the CI identity")
        o = _out(r)
        if _status(r) != "unchanged" or o.get("exists") is not True:
            self.cloud_stop("ci identity", "github_repo-describe", r)
        v = self.source.reads.values
        r = self.poll_call(CLOUD, "gcp_ci-identity-setup", {
            "projectId": self.current_project_id(), "project": d.name,
            "repository": d.full, "repositoryId": PP._scalar_text(o.get("id")),
            "ownerId": PP._scalar_text(o.get("ownerId")), "branch": o.get("defaultBranch"),
            "workflow": "%s/.github/workflows/%s" % (v["workflows"], v["deployWorkflow"]),
            "mode": "apply"}, "the CI identity")
        if _status(r) in ("created", "updated", "unchanged") and not _pending(r):
            self.note("gcp_ci-identity-setup", r)
            self.account = _out(r).get("account")
            self.provider = _out(r).get("provider")
            if _status(r) in ("created", "updated"):
                self.identity_changed = True
                self.mark_changed(cloud=True)
            return True
        if _status(r) in ("created", "updated"):
            self.mark_changed(cloud=True)
        self.cloud_stop("ci identity", "gcp_ci-identity-setup", r)

    def ci_account(self):
        if self.account:
            return self.account
        return "%s-ci@%s.iam.gserviceaccount.com" % (self.decl().name,
                                                   self.current_project_id())

    def substep_11(self, ran10):
        registry = state(self.plan, "registry")
        if not (action(self.plan, "ci identity") == "grant" or (
                ran10 and registry not in ("in another region", "not a Docker repository"))):
            return
        d = self.decl()
        r = self.poll_call(REGISTRY, "gcp-artifact-registry_access-grant",
                           {"projectId": self.current_project_id(), "project": d.name,
                            "region": d.region, "identity": self.ci_account(), "role": "push",
                            "mode": "apply"}, "the push access")
        if _status(r) in ("updated", "unchanged") and not _pending(r):
            self.note("gcp-artifact-registry_access-grant", r)
            if _status(r) == "updated":
                self.mark_changed(cloud=True)
            return
        if _status(r) in ("created", "updated"):
            self.mark_changed(cloud=True)
        self.cloud_stop("registry", "gcp-artifact-registry_access-grant", r)

    def deploy_args(self, env=None):
        d = self.decl()
        v = self.source.reads.values
        a = {"projectId": self.current_project_id(), "project": d.name, "environment": "dev",
             "region": d.region, "components": ",".join(d.names),
             "maxInstances": PP._scalar_text(v["maxInstances"]),
             "cpu": PP._scalar_text(v["cpu"]), "memory": PP._scalar_text(v["memory"]),
             "ciAccount": self.ci_account(),
             "placeholderImage": self.defaults("project.deploy.placeholderImage")}
        if env is not None:
            a["env"] = env
        a["mode"] = "apply"
        return a

    def deploy_ok(self, r):
        """created/updated/unchanged with no pending item but `access`; the item access is
        carried."""
        others = [x for x in _pending(r) if x.get("item") != "access"]
        for x in _pending(r):
            if x.get("item") == "access":
                self.carry["access"] = x
        return _status(r) in ("created", "updated", "unchanged") and not others

    def deploy_stop(self, r, database_stop=False):
        """A stop of gcp_deploy-setup: the sentences naming what is still open, and one
        item."""
        if _status(r) in ("created", "updated"):
            self.mark_changed(cloud=True)
        open_lines = [l.strip() for l in _answer(r) if l.strip().startswith("The service ")
                      and (" is still open" in l or " is still without the login" in l)]
        for x in _pending(r):
            if x.get("item") == "access":
                self.carry["access"] = x
        if database_stop:
            return open_lines
        self.cloud_stop("services", "gcp_deploy-setup", r, items=[item("services", SERVICES_HOW)],
                        sentences=open_lines)

    def substep_12(self):
        p = self.plan
        if not (action(p, "services") in ("create", "update") and not self.created_or_found()
                and action(p, "ci identity") != "fix by hand"):
            return None
        r = self.call(CLOUD, "gcp_deploy-setup", self.deploy_args(), what="the services")
        if self.deploy_ok(r):
            self.note("gcp_deploy-setup", r)
            if _status(r) in ("created", "updated"):
                self.mark_changed(cloud=True)
            return _status(r)
        self.deploy_stop(r)

    def substep_12b(self, ran12):
        if ran12 not in ("created", "updated") or state(self.plan, "database") != PP.FOLLOWS_SERVICES:
            return
        p = self.make_plan(self.plan_args(), "the plan of the database")
        if p.failure is not None:
            raise _Final("updated", [item("verify", VERIFY_HOW)])
        self.db_plan = p

    # -- sub-step 12a: the database --------------------------------------------

    def database_row(self):
        """The row of "Which steps run", from the database's plan alone."""
        p = self.db_plan
        st = state(p, "database")
        db = p.outputs.get("database") or {}
        instance_state = db.get("instanceState")
        if st == "differs: settings":
            return "settings"
        if db.get("start") is True:
            return "start"
        if instance_state == "running":
            return "running"
        if instance_state == "starting":
            return "starting"
        return "other"

    def substep_12a(self):
        d = self.decl()
        p = self.db_plan
        if not d.database_components or action(p, "database") not in ("create", "update"):
            return
        row = self.database_row()
        steps = DATABASE_STEPS[row]
        db = p.outputs.get("database") or {}
        self.dbnames = list(db.get("components") or d.database_names)
        if row == "start" and not self.confirm:
            self.database_stop(None, sentence=START_NEEDS_CONFIRM,
                               one=item("confirm", CONFIRM_START_HOW % self.visibility_arg),
                               status="pending")
        if row == "start" and self.start_unknown_now():
            # This run asked for the start (an earlier command, cut by a limit) and the
            # instance is still stopped: the start did not take effect. As a failed start
            # whose read shows it stopped: stop, and never start it a second time.
            self.carry["startAsked"] = False
            self.register_abort()
            self.database_stop(None, sentence=START_FAILURES[0],
                               one=item("database", START_FAILED_HOW))
        if row == "other":
            st = db.get("instanceState")
            how = (INSTANCE_UNKNOWN_HOW if st == "unknown" or st is None
                   else INSTANCE_STATE_HOW % (st, st))
            self.database_stop(None, sentence=None, one=item("database", how),
                               status="pending", how_only=True)
        if row == "starting" and not self.carry["startedInstance"] \
                and not self.carry["startAsked"]:
            self.carry["alreadyStarting"] = True
        for step in steps:
            getattr(self, "database_" + step)()

    dbnames = ()

    def database_0a(self):
        """The code first, before anything that costs."""
        d = self.decl()
        by_name = {c["name"]: c for c in d.database_components}
        for n in sorted(_names_of(state(self.db_plan, "components"), "to generate: ")):
            c = by_name.get(n)
            if c is None or n in self.go_done:
                continue
            r, ok = self.go_setup(c)
            if _status(r) == "created":
                self.carry["wroteCode"] = True
            if not ok:
                cause = first_sentence(r)
                if self.written:
                    items = [item(n, FILES_KEPT_HOW % as_how(cause))] + _pending(r)
                else:
                    items = [item(n, as_how(cause))] + _pending(r)
                st = "updated" if self.changed else (
                    _status(r) if _status(r) in ("failed", "pending") else "failed")
                sentences = _answer(r)[:1] + [NOTHING_FOR_DATABASE]
                if self.carry["cloudChanged"]:
                    raise _ToStep5(items, sentences, own_items=True)
                self.end(st, items, sentences=sentences)

    def database_0b(self):
        """The shared project, by this skill's own read."""
        r = self.call(CLOUD, "gcp_environment-describe",
                      {"project": self.source.reads.values["sharedProject"],
                       "platform": "shared"}, read_only=True, what="the shared project")
        o = _out(r)
        services = o.get("enabledServices") if isinstance(o.get("enabledServices"), list) else []
        if (_status(r) == "unchanged" and o.get("exists") is True
                and "sqladmin.googleapis.com" in services and o.get("projectId")):
            self.shared_project_id = o["projectId"]
            return
        if _status(r) == "unchanged":
            sentence = SHARED_NOT_READY
        elif first_sentence(r).startswith("More than one GCP project"):
            sentence = SHARED_AMBIGUOUS
        else:
            sentence = SHARED_UNREADABLE
        self.database_stop(r, sentence=sentence)

    def switch_arguments(self):
        return {"region": self.defaults("cloud.region"),
                "timeZone": self.defaults("platform.switch.timeZone"),
                "weeknightStop": self.defaults("platform.switch.weeknightStop"),
                "weekendStop": self.defaults("platform.switch.weekendStop"),
                "repository": self.defaults("platform.switch.repository")}

    def database_0c(self):
        """The night stop, read right before the start."""
        a = {"projectId": self.shared_project_id,
             "instance": self.source.reads.values["instance"]}
        a.update(self.switch_arguments())
        a["mode"] = "plan"
        r = self.call(DB, "gcp-cloud-sql_instance-switch-setup", a, read_only=True,
                      what="the night stop")
        if _out(r).get("ready") is True:
            return
        self.database_stop(r, sentence=NIGHT_STOP_NOT_CONFIRMED,
                           one=item("database", NIGHT_STOP_HOW), status="pending")

    def database_a(self):
        """The start (only with confirm=yes given, step 3)."""
        if not self.confirm:  # never reached: substep_12a stops first
            self.database_stop(None, sentence=START_NEEDS_CONFIRM,
                               one=item("confirm", CONFIRM_START_HOW % self.visibility_arg),
                               status="pending")
        # Before the start is invoked: from now on, until a read tells, this run may have
        # started the instance (the cost, the aborted run's lines, and never "already
        # starting" for the instance it finds starting later).
        self.check_step("the start of the shared instance")
        self.carry["startAsked"] = True
        self.register_abort()
        r = self.call(DB, "gcp-cloud-sql_instance-start",
                      {"projectId": self.shared_project_id,
                       "instance": self.source.reads.values["instance"]},
                      what="the start of the shared instance", step=False,
                      on_cut=self.start_cut)
        st = _status(r)
        self.carry["startAsked"] = st == "updated"  # its outcome is known from here
        if st == "updated":
            self.carry["startedInstance"] = True
            self.mark_changed(cloud=True)
            self.note("gcp-cloud-sql_instance-start", r)
            self.register_abort()
            return
        self.register_abort()
        if st == "unchanged":
            return
        if _out(r).get("state") == "unknown":
            sentence = START_STATE_UNKNOWN
        else:
            known = [l for l in _answer(r) if l in START_FAILURES]
            sentence = known[0] if known else START_FAILURES[0]
            if _out(r).get("state") is None and sentence == START_FAILURES[2]:
                self.start_unknown = True
        self.database_stop(r, sentence=sentence, one=item("database", START_FAILED_HOW))

    def start_cut(self, r):
        """The start was ended by a limit of the run. When it ran no write (its aborted
        result says nothing had been written) the instance was not asked to start: the
        next command plans again, and the start's every gate runs again. Otherwise its
        outcome is not known until a plan reads the instance."""
        if common.REFUSED_NOTHING_WRITTEN in _answer(r) and _status(r) not in (
                "created", "updated"):
            self.carry["startAsked"] = False
            self.register_abort()

    def database_b(self):
        """The wait for the shared instance: thirty tries for the whole run."""
        d = self.decl()
        accounts = ",".join(d.account(n, self.current_project_id()) for n in self.dbnames)
        args = {"sharedProjectId": self.shared_project_id,
                "instance": self.source.reads.values["instance"], "project": d.name,
                "environment": "dev", "accounts": accounts}
        while True:
            tries = self.carry["instanceTries"] + 1
            r = self.call(DB, "gcp-cloud-sql_database-describe", args, read_only=True,
                          what="the wait for the shared instance",
                          step=tries == 1)
            self.carry["instanceTries"] = tries
            if _status(r) == "unchanged" and _out(r).get("read") is True:
                return
            if tries >= INSTANCE_TRIES:
                self.instance_limit(INSTANCE_LIMIT_STARTED if self.carry["startedInstance"]
                                    else INSTANCE_LIMIT)
            if not self.ctx.wait(counted=False):
                raise Continue(INSTANCE_CONTINUE % (tries, INSTANCE_TRIES),
                               lambda: self.instance_limit(INSTANCE_WAIT_NOT_RUN))

    def instance_limit(self, sentence):
        self.end("pending", [item("database", INSTANCE_WAIT_HOW)], sentences=[sentence])

    def database_c(self):
        d = self.decl()
        r = self.call(DB, "gcp-cloud-sql_database-create",
                      {"sharedProjectId": self.shared_project_id,
                       "instance": self.source.reads.values["instance"], "project": d.name,
                       "environment": "dev", "mode": "apply"}, what="the database")
        if _status(r) in ("created", "unchanged") and not _pending(r):
            self.note("gcp-cloud-sql_database-create", r)
            if _status(r) == "created":
                self.mark_changed(cloud=True)
            return
        self.database_stop(r)

    def database_d(self):
        d = self.decl()
        for n in self.dbnames:
            r = self.call(DB, "gcp-cloud-sql_access-grant",
                          {"sharedProjectId": self.shared_project_id,
                           "instance": self.source.reads.values["instance"],
                           "account": d.account(n, self.current_project_id()),
                           "mode": "apply"}, what="the database user of %s" % n)
            if _status(r) in ("updated", "unchanged") and not _pending(r):
                self.note("gcp-cloud-sql_access-grant", r)
                if _status(r) == "updated":
                    self.mark_changed(cloud=True)
                continue
            self.database_stop(r)

    def database_e(self):
        d = self.decl()
        env = PP.database_settings(d.name, d.database_names, self.shared_project_id, d.region,
                                   self.source.reads.values["instance"],
                                   self.current_project_id())
        r = self.call(CLOUD, "gcp_deploy-setup", self.deploy_args(env=env),
                      what="the database settings")
        if self.deploy_ok(r):
            self.note("gcp_deploy-setup", r)
            if _status(r) in ("created", "updated"):
                self.mark_changed(cloud=True)
            return
        open_lines = self.deploy_stop(r, database_stop=True)
        self.database_stop(r, sentences=open_lines)

    def database_stop(self, r, sentence=None, sentences=None, one=None, status=None,
                      how_only=False):
        """A stop of sub-step 12a: the stopping skill's sentence (or this sub-step's), the
        sentence that the database was not all made, and exactly one item."""
        if r is not None:
            self.stop_line(_skill_name(r), r)
            if _status(r) in ("created", "updated"):
                self.mark_changed(cloud=True)
        names = ", ".join(self.dbnames)
        said = []
        if not how_only:
            if sentence is not None:
                said.append(sentence)
            elif sentences:
                said += sentences
            elif r is not None:
                said += _answer(r)
            if sentence != START_NEEDS_CONFIRM:
                said.append(NOT_ALL_MADE % names)
        items = [one or item("database", DATABASE_HOW % names)]
        if status is None:
            status = _status(r) if r is not None and _status(r) in ("failed", "pending") \
                else "failed"
        if self.carry["cloudChanged"]:
            raise _ToStep5(items, said, own_items=True)
        self.end(status, items, sentences=said)

    # -- sub-step 13 -----------------------------------------------------------

    def substep_13(self):
        p = self.plan
        st = state(p, "ci secrets")
        if not (action(p, "ci secrets") == "set" or st in (
                PP.FOLLOWS_ENVIRONMENT, PP.FOLLOWS_APIS, "follows the ci identity")):
            return
        if "fix by hand" in (action(p, "registry"), action(p, "ci identity")):
            return
        provider = self.provider or ((p.outputs.get("ciVariables") or {})
                                     .get("GCP_WIF_PROVIDER"))
        if not provider:
            return
        d = self.decl()
        pid = self.current_project_id()
        variables = ("GCP_PROJECT_ID=%s,GCP_WIF_PROVIDER=%s,GCP_CI_ACCOUNT=%s,GCP_IMAGE_PATH="
                     "%s-docker.pkg.dev/%s/%s" % (pid, provider, self.ci_account(), d.region,
                                                  pid, d.name))
        a = {"owner": d.owner, "name": d.repo_name, "kind": "secrets", "variables": variables}
        if self.created_or_found() or self.registry_created or self.identity_changed:
            a["replace"] = "yes"
        a["mode"] = "apply"
        r = self.call(GH, "github_variables-set", a, what="the CI secrets")
        if _status(r) in ("updated", "unchanged") and not _pending(r):
            self.note("github_variables-set", r)
            if _status(r) == "updated":
                self.mark_changed(cloud=True)
            return
        if _status(r) in ("created", "updated"):
            self.mark_changed(cloud=True)
        self.cloud_stop("ci secrets", "github_variables-set", r,
                        items=[item("ci secrets", SECRETS_HOW)], sentences=[])

    # ======================================================================
    # Step 5: the plan again, its own reads the proof

    def step_5(self, stop_items=None, stop_sentences=(), own_items=False):
        args = self.plan_args()
        p = self.make_plan(args, "the last plan")
        if self.carry["apisEnabled"]:
            self.carry["apisTries"] = 0
            p = self.poll_plan(p, args)
        if stop_items is not None:
            # A stop that still runs step 5: its table is the answer's, its items are
            # the stop's (for a stop of sub-steps 12, 12a and 13, only those).
            if p.failure is not None:
                stop_items = list(stop_items) + [item("verify", VERIFY_HOW)]
            if not own_items and p.failure is None:
                stop_items = list(stop_items) + self.left_items(p)
            self.end("updated", stop_items, sentences=stop_sentences)
        if p.failure is not None:
            self.end("failed", [item("verify", VERIFY_HOW)])
        if self.files_after_the_cloud(p):
            self.plan = p
            self.propose_and_generate(p, after_cloud=True)
        acting = [row for row in p.items if row[2] != NONE]
        if not acting:
            self.end("unchanged", p.pending)
        if not self.changed:
            self.end("pending", self.left_items(p))
        if self.project and action(p, "environment dev") == "create":
            pid, how = self.project["id"], self.project["how"]
            self.end("updated", [item("environment dev", NOT_VISIBLE_HOW % (pid, how))],
                     sentences=[CREATION_NOT_VISIBLE % (pid, how)])
        self.end("updated", self.left_items(p))

    def left_items(self, p):
        """One item per item the last plan still lists, then its own items for what the
        owner does."""
        out = []
        holds = self.login_holds(p)
        for name, st, act in p.items:
            if act in (NONE,) + OWNER_ACTIONS + ("merge it", "fix the folder"):
                continue
            if act == "generate":
                if holds:
                    continue
                how = self.creation_wait() if self.project else GENERATE_HOW
            elif name == "environment dev" and act == "create" and not self.project:
                how = BIRTH_ENVIRONMENT_HOW
            elif self.project:
                how = self.creation_wait()
            else:
                how = self.needed_confirmation(p)
            out.append(item(name, how))
        out += [x for x in p.pending]
        return out

    def files_after_the_cloud(self, p):
        """"The files after the cloud": the last plan, made after the cloud, has files to
        generate (or step 0a wrote files), and nothing holds them."""
        if self.created_or_found() or not self.decl().environments:
            return False
        if not self.ran_environment:
            return False
        decl_action = self.declaration_action(p)
        if decl_action != NONE:
            return False
        if any(row[2] in ("merge it", "fix the folder") for row in p.items):
            return False
        if self.login_holds(p):
            return False
        return p.outputs.get("generate") is True or self.carry["wroteCode"]

    ran_environment = False

    # ======================================================================

    def run(self):
        try:
            self.step_1()
            self.step_2()
            self.step_3()
            try:
                self.step_4()
            except _ToStep5 as stop:
                self.step_5(stop.items, stop.sentences, stop.own_items)
            except _Final as final:
                self.end(final.status, final.items, sentences=final.sentences)
            self.step_5()
        except End as e:
            return e.result
        except Continue as c:
            if self.ctx.may_continue():
                # The digest of the declaration as it is now (the update of the folder
                # may have rewritten it in this command), and of the arguments: what the
                # next command reads at its start.
                digest = common.carry_digest(read_declaration_bytes(), self.args)
                return self.ctx.continue_run(c.line, self.carry, cost=self.cost(),
                                             digest=digest)
            try:
                c.limit()
            except End as e:
                return e.result
        raise AssertionError("every path ends")  # pragma: no cover


class _ToStep5(Exception):
    """A stop after a change: step 5 still runs, its table is the answer's."""

    def __init__(self, items, sentences, own_items=False):
        Exception.__init__(self, "step 5")
        self.items = items
        self.sentences = sentences
        self.own_items = own_items


class _Final(Exception):
    """A stop with the plan just made as the last one (step 5 does not run)."""

    def __init__(self, status, items, sentences=()):
        Exception.__init__(self, "final")
        self.status = status
        self.items = items
        self.sentences = sentences


# "Which steps run" of sub-step 12a: the row (database_row) and its steps, in order.
DATABASE_STEPS = {
    "settings": ("0b", "e"),
    "start": ("0a", "0b", "0c", "a", "b", "c", "d", "e"),
    "running": ("0a", "0b", "c", "d", "e"),
    "starting": ("0a", "0b", "b", "c", "d", "e"),
    "other": (),
}

# The sentences of a failed start, fixed and with no name (gcp-cloud-sql_instance-start).
START_FAILURES = (
    "The instance could not be started: it is still stopped, so it is not charged by the "
    "hour.",
    "The instance could not be read, so it was not started.",
    "The instance could not be started, and the read after the failure could not tell "
    "whether it is running: it may be charged by the hour until it is stopped.",
    "The instance does not exist, so it was not started.",
)

WROTE_PREFIX = common.REFUSED_WRITTEN.split("{writes}")[0]


def wrote_before_abort(result):
    """True when a called command's aborted (or refused) result says it had already run
    writes before it stopped."""
    return any(l.startswith(WROTE_PREFIX) for l in _answer(result))


def _skill_name(result):
    """The skill name of a called skill's result, for its line (`gcp-cloud-sql_access-grant`,
    `gcp_deploy-setup`, ...)."""
    action_name = result.get("action") or "skill"
    provider = result.get("provider")
    if provider == "gcp-cloud-sql":
        return "gcp-cloud-sql_%s" % action_name
    if provider == "gcp-artifact-registry":
        return "gcp-artifact-registry_%s" % action_name
    if provider == "gcp":
        return "gcp_%s" % action_name
    if provider == "github":
        return "github_%s" % action_name
    if provider == "go":
        return "go_%s" % action_name
    return action_name


def _local_branch(r):
    """The local branch `aleogr/change-<random>` the pull request skill committed to and
    named (a refused push, or a branch pushed with no pull request), or None."""
    import re
    if _status(r) not in ("failed", "updated"):
        return None
    for line in _answer(r):
        if "the commit is kept in the local branch " in line or (
                _status(r) == "updated" and "is on GitHub, but the pull request was not "
                "opened" in line):
            m = re.search(r"aleogr/change-[a-z0-9]{6}", line)
            if m:
                return m.group(0)
    return None


def _capital(s):
    return s[:1].upper() + s[1:]


def run(args, ctx):
    raw = read_declaration_bytes()
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
        return ctx.result("failed", {"project": None, "repository": None, "url": None,
                                     "items": [], "pullRequest": None},
                          pending=[item("arguments", ARGUMENTS_HOW)], cost=dict(NO_COST),
                          lines=[problem])
    # The versions of every plugin this run can call, before its first read: a plugin of
    # another release ends it here (PluginVersion: failed, its one sentence), before the
    # plan reads anything and before any step writes.
    ctx.check_suites(SUITE_COMMANDS)
    return Apply(args, ctx, carry, lost=lost).run()
