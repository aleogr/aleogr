"""Unit tests of project-apply: every gate before the call it gates (absent, another value,
and the gated call not made), the run in more than one command, and paths no scenario
covers.

Apply is given a plan function that returns fake plans (the rows, outputs and pending
items of a Plan, with a real Declaration) and a call function that answers each
invocation from canned result objects and records it; the context is a stand-in with an
injected step limit, wait and count of commands. No command and no provider runs. The
scenarios project-apply-* cover the rest in the direct mode.
"""

import copy
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "project-apply")
PP = skill.PP

PID = "aleogr-dev-demo-ab12"
SHARED = "aleogr-shared-ab12"

DECL = {
    "version": 1, "name": "demo",
    "repo": {"provider": "github", "owner": "example-org", "name": "demo",
             "visibility": "private", "description": "Demo project", "topics": [],
             "settings": {"mergeCommit": True, "squash": True, "rebase": False,
                          "deleteBranchOnMerge": True, "issues": True, "wiki": False,
                          "projects": False}},
    "components": [{"name": "web", "stack": "go", "path": "web", "version": "1.27",
                    "database": True}],
    "cloud": {"provider": "gcp", "region": "us-central1"},
    "environments": {"dev": {}},
}

VALUES = {"workflows": "aleogr/aleogr", "deployWorkflow": "deploy-cloud-run.yml",
          "services": ["run.googleapis.com"], "keep": 5, "maxInstances": 2, "cpu": "1",
          "memory": "512Mi", "modules": ["a@v1.0.0", "b@v2.0.0"], "minVersion": "1.26",
          "sharedProject": "shared", "instance": "aleogr-shared"}

ROWS = [("repository", "exists", "none"), ("settings", "as declared", "none"),
        ("visibility", "as declared", "none"), ("declaration", "in the repository", "none"),
        ("components", "as declared", "none"), ("ci", "as declared", "none"),
        ("protection", "protected", "none"), ("environment dev", "exists", "none"),
        ("apis", "enabled", "none"), ("registry", "as declared", "none"),
        ("ci identity", "as declared", "none"), ("services", "as declared", "none"),
        ("database", "as declared", "none"), ("ci secrets", "as declared", "none")]


class FakeReads(object):
    def __init__(self, decl, exists=True, failure=None):
        self.decl = PP.Declaration(decl)
        self.values = dict(VALUES)
        self.exists = exists
        self.failure = failure


class FakePlan(object):
    def __init__(self, rows=None, decl=None, failure=None, **outputs):
        rows = list(rows or ROWS)
        self.items = rows
        self.reads = FakeReads(decl or DECL, failure=failure)
        self.pending = list(outputs.pop("pending", []))
        o = {"exposes": False, "visibility": "private", "generate": False, "checks": "ci",
             "changed": [], "environment": {"name": "dev", "projectId": PID},
             "repositoryEnvironments": ["dev"], "repositoryDatabaseComponents": ["web"],
             "ciVariables": {"GCP_WIF_PROVIDER": "projects/1/p"},
             "urls": {"web": "https://demo-web.run.app"}, "ciDeployComponents": ["web"],
             "defaultBranch": "main",
             "database": {"name": "demo_dev", "instanceState": "running", "start": False,
                          "components": ["web"]}}
        o.update(outputs)
        o["items"] = [{"item": i, "state": s, "action": a} for i, s, a in rows]
        self.outputs = o

    @property
    def failure(self):
        return self.reads.failure


def rows(**changes):
    """ROWS with some rows replaced: name=(state, action)."""
    out = []
    for name, st, act in ROWS:
        key = name.replace(" ", "_")
        if key in changes:
            st, act = changes[key]
        out.append((name, st, act))
    return out


def res(status="unchanged", answer=(), pending=(), data=None, **outputs):
    r = {"status": status, "outputs": outputs, "answer": list(answer),
         "pending": list(pending)}
    if data is not None:
        r["data"] = data
    return r


class FakeCtx(object):
    """The parts of a Context that project-apply uses, with the limits injected."""

    def __init__(self, step=True, waits=None, may_continue=True, plugin="aleogr"):
        self.plugin = plugin
        self.step = step  # bool, or a list of answers, one per step_allowed()
        self.steps_begun = 0
        self.waits = waits  # None: every wait allowed; else a list of answers
        self.may = may_continue
        self.slept = 0
        self.abort = []
        self.continued = None

    def step_allowed(self):
        # As common.Context.step_allowed: the first step of a command is never held by
        # the step limit; `step` answers for the limit itself.
        if isinstance(self.step, list):
            ok = self.step.pop(0) if self.step else True
        else:
            ok = self.step
        if self.steps_begun == 0 or ok:
            self.steps_begun += 1
            return True
        return False

    def wait(self, counted=True):
        if self.waits is not None:
            ok = self.waits.pop(0) if self.waits else True
            if not ok:
                return False
        self.slept += 1
        return True

    def may_continue(self):
        return self.may

    def continue_run(self, line, carry, cost=None, **kw):
        self.continued = (line, copy.deepcopy(carry))
        return self.result("continue", {}, lines=[line, "next: ..."], cost=cost)

    def on_abort(self, lines):
        self.abort = list(lines)

    def plugin_path(self, *parts):
        return os.path.join(ROOT, *parts)

    def result(self, status, outputs, resources=(), pending=(), cost=None, lines=(), **kw):
        block = common.result_block(skill.FAMILY, skill.PROVIDER, skill.ACTION, status,
                                    outputs, mode="apply", resources=resources,
                                    pending=pending, cost=cost)
        return common.Result(block, lines)


class Harness(object):
    """Runs one command of project-apply with fake plans and invocations."""

    def __init__(self, plans, answers, args=None, ctx=None, carry=None):
        self.plans = list(plans)  # one plan per plan made, the last one repeated
        self.answers = answers  # skill -> result, or a list (one per call)
        self.calls = []
        self.plan_calls = []
        self.ctx = ctx or FakeCtx()
        self.args = {"confirm": "yes"} if args is None else args
        self.carry = carry or skill.new_carry()

    def plan(self, a):
        self.plan_calls.append(dict(a))
        if len(self.plans) > 1:
            return self.plans.pop(0)
        return self.plans[0]

    def call(self, command, name, a, read_only):
        for v in a.values():
            assert isinstance(v, str), (name, a)
        self.calls.append((name, dict(a), read_only))
        r = self.answers.get(name, res())
        if isinstance(r, list):
            r = r.pop(0) if len(r) > 1 else r[0]
        return copy.deepcopy(r)

    def run(self):
        apply = TestApply(self.args, self.ctx, self.carry, plan_fn=self.plan,
                          call_fn=self.call)
        self.apply = apply
        self.result = apply.run()
        self.block = self.result.block
        self.lines = list(self.result.lines)
        return self

    def called(self, name):
        return [c for c in self.calls if c[0] == name]


class TestApply(skill.Apply):
    def table_lines(self, plan):  # the plan's own lines need a real Plan
        return ["<table>"]

    def defaults(self, dotted):
        return {"project.deploy.placeholderImage": "us-docker.pkg.dev/cloudrun/container/hello",
                "cloud.region": "us-central1", "platform.switch.timeZone": "America/Sao_Paulo",
                "platform.switch.weeknightStop": "30 22 * * 0-4",
                "platform.switch.weekendStop": "0 4 * * 6,0",
                "platform.switch.repository": "aleogr/aleogr"}[dotted]


# The database to make on a stopped instance: the row of `<start>`.
START_PLAN = dict(rows=rows(database=("missing: roles, settings", "create")),
                  database={"name": "demo_dev", "instanceState": "stopped", "start": True,
                            "components": ["web"]})
SHARED_OK = res(exists=True, projectId=SHARED, enabledServices=["sqladmin.googleapis.com"])
READY = res(read=True)
NOT_READ = res(read=False)


def start_answers(**over):
    a = {"gcp_environment-describe": SHARED_OK,
         "gcp-cloud-sql_instance-switch-setup": res(ready=True),
         "gcp-cloud-sql_instance-start": res("updated", state="starting"),
         "gcp-cloud-sql_database-describe": READY,
         "gcp-cloud-sql_database-create": res("created"),
         "gcp-cloud-sql_access-grant": res("updated"),
         "gcp_deploy-setup": res("updated")}
    a.update(over)
    return a


def names(h):
    return [c[0] for c in h.calls]


class TestArguments(unittest.TestCase):
    def ctx(self):
        return FakeCtx()

    def test_unknown_or_invalid_argument_fails_before_anything(self):
        for args, sentence in (({"confirm": "no"}, skill.CONFIRM_INVALID),
                               ({"confirmVisibility": "yes"}, skill.VISIBILITY_INVALID),
                               ({"mode": "apply"}, skill.ARGUMENT_UNKNOWN % "mode")):
            with self.subTest(args=args):
                self.assertEqual(skill.validate_args(args), sentence)
        self.assertIsNone(skill.validate_args({"confirm": "yes",
                                               "confirmVisibility": "public"}))

    def test_module_declares_what_the_dispatcher_needs(self):
        self.assertTrue(skill.CONTINUES)
        self.assertFalse(skill.WRITES)  # the orchestrator writes nothing itself
        self.assertEqual((skill.DEFAULT_MODE, skill.RESULT_MODE), ("apply", "apply"))


class TestConfirmGate(unittest.TestCase):
    PLAN = dict(rows=rows(ci_secrets=("missing: GCP_IMAGE_PATH", "set")))

    def test_absent(self):
        h = Harness([FakePlan(**self.PLAN)], {}, args={}).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["status"], "pending")
        self.assertEqual(h.block["pending"], [skill.item("confirm", skill.CONFIRM_HOW)])
        self.assertIn(skill.MAKES_IN_CLOUD % "the repository's CI secrets", h.lines)

    def test_given(self):
        h = Harness([FakePlan(**self.PLAN), FakePlan()],
                    {"github_variables-set": res("updated")}).run()
        self.assertEqual(names(h), ["github_variables-set"])
        self.assertEqual(h.block["status"], "updated")

    def test_confirm_visibility_with_no_such_change_confirms_nothing(self):
        h = Harness([FakePlan(**self.PLAN)], {}, args={"confirmVisibility": "public",
                                                      "confirm": "yes"}).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["status"], "failed")
        self.assertIn(skill.CONFIRM_VISIBILITY_NOT_NEEDED % "public", h.lines)


class TestVisibilityGate(unittest.TestCase):
    PLAN = dict(rows=[("repository", "missing", "create")] + ROWS[1:7], exposes=True,
                visibility="public",
                decl=dict(DECL, repo=dict(DECL["repo"], visibility="public"),
                          components=[]))

    def test_absent(self):
        h = Harness([FakePlan(**self.PLAN)], {}, args={"confirm": "yes"}).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["pending"],
                         [skill.item("confirm visibility public", skill.CONFIRM_PUBLIC_HOW)])
        self.assertIn(skill.WOULD_BE_PUBLIC, h.lines)

    def test_another_value(self):
        h = Harness([FakePlan(**self.PLAN)], {}, args={"confirmVisibility": "private"}).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["status"], "failed")
        self.assertEqual(h.block["pending"][0]["how"], skill.CONFIRM_PUBLIC_HOW)

    def test_given(self):
        h = Harness([FakePlan(**self.PLAN), FakePlan(rows=ROWS[:7])],
                    {"github_repo-create": res("created")},
                    args={"confirmVisibility": "public"}).run()
        create = h.called("github_repo-create")
        self.assertEqual(len(create), 1)
        self.assertEqual(create[0][1]["confirmVisibility"], "public")
        self.assertEqual(h.block["status"], "created")

    def test_private_needs_its_own_confirmation(self):
        plan = FakePlan(rows=rows(visibility=("differs", "update")), visibility="private")
        h = Harness([plan], {}, args={"confirm": "yes"}).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["pending"][0]["item"], "confirm visibility private")


class TestStartGates(unittest.TestCase):
    def test_start_needs_confirm_yes_itself(self):
        plan = FakePlan(rows=rows(visibility=("differs", "update"),
                                  database=("missing: roles", "create")), visibility="private",
                        database=START_PLAN["database"])
        h = Harness([plan], start_answers(), args={"confirmVisibility": "private"}).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["pending"],
                         [skill.item("confirm", skill.CONFIRM_START_HOW % "private")])
        self.assertIn(skill.START_NEEDS_CONFIRM, h.lines)

    def test_a_later_plan_asking_for_the_start_is_held_by_the_same_rule(self):
        first = FakePlan(rows=rows(visibility=("differs", "update"),
                                   services=("missing: web", "create"),
                                   database=(PP.FOLLOWS_SERVICES, "none")),
                         visibility="private")
        later = FakePlan(**START_PLAN)
        h = Harness([first, later], dict(start_answers(),
                                         **{"github_repo-configure": res("updated"),
                                            "gcp_deploy-setup": res("created")}),
                    args={"confirmVisibility": "private"}).run()
        self.assertEqual(len(h.called("gcp_deploy-setup")), 1)
        self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])
        self.assertEqual(h.called("gcp-cloud-sql_instance-switch-setup"), [])
        self.assertIn(skill.START_NEEDS_CONFIRM, h.lines)
        self.assertNotIn(skill.NOT_ALL_MADE % "web", h.lines)

    def test_night_stop_not_ready_never_starts(self):
        for ending in (res(ready=False), res("pending", ready=False), res("failed"),
                       res()):
            with self.subTest(ending=ending):
                h = Harness([FakePlan(**START_PLAN)], start_answers(
                    **{"gcp-cloud-sql_instance-switch-setup": ending})).run()
                self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])
                self.assertEqual(h.block["pending"],
                                 [skill.item("database", skill.NIGHT_STOP_HOW)])
                self.assertIn(skill.NIGHT_STOP_NOT_CONFIRMED, h.lines)

    def test_night_stop_read_right_before_the_start_and_read_only(self):
        h = Harness([FakePlan(**START_PLAN), FakePlan()], start_answers()).run()
        order = names(h)
        i = order.index("gcp-cloud-sql_instance-switch-setup")
        self.assertEqual(order[i + 1], "gcp-cloud-sql_instance-start")
        switch = h.called("gcp-cloud-sql_instance-switch-setup")[0]
        self.assertTrue(switch[2])  # --read-only
        self.assertEqual(switch[1]["mode"], "plan")
        self.assertEqual(switch[1]["projectId"], SHARED)
        start = h.called("gcp-cloud-sql_instance-start")[0]
        self.assertEqual(start[1], {"projectId": SHARED, "instance": "aleogr-shared"})
        self.assertFalse(start[2])

    def test_never_started_when_nothing_is_missing_in_it(self):
        for db_row in (("differs: settings", "update"), ("as declared", "none")):
            with self.subTest(row=db_row):
                plan = FakePlan(rows=rows(database=db_row),
                                database={"name": "demo_dev", "instanceState": "stopped",
                                          "start": False, "components": ["web"]})
                h = Harness([plan, FakePlan()], start_answers()).run()
                self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])
                self.assertEqual(h.called("gcp-cloud-sql_database-describe"), [])

    def test_start_registers_the_aborted_runs_lines(self):
        h = Harness([FakePlan(**START_PLAN), FakePlan()], start_answers()).run()
        # The lines of what the run made, then the start's sentence (I2).
        self.assertEqual(h.ctx.abort[-1], skill.START_SENTENCE)
        self.assertEqual(h.ctx.abort[:-1], h.carry["made"])
        self.assertIn(skill.START_SENTENCE, h.lines)
        self.assertEqual(h.block["cost"], skill.STARTED_COST)

    def test_start_failed_with_state_unknown(self):
        failed = res("failed", answer=[skill.START_FAILURES[2], "x"], state=None)
        h = Harness([FakePlan(**START_PLAN)], start_answers(
            **{"gcp-cloud-sql_instance-start": failed})).run()
        self.assertEqual(h.block["cost"], skill.START_UNKNOWN_COST)
        self.assertIn(skill.START_FAILURES[2], h.lines)
        self.assertNotIn("x", h.lines)
        self.assertEqual(h.called("gcp-cloud-sql_database-describe"), [])
        unknown = res("failed", answer=["Its activation policy is X."], state="unknown")
        h = Harness([FakePlan(**START_PLAN)], start_answers(
            **{"gcp-cloud-sql_instance-start": unknown})).run()
        self.assertIn(skill.START_STATE_UNKNOWN, h.lines)


class TestGoGate(unittest.TestCase):
    def test_no_go_on_this_machine_makes_nothing(self):
        plan = FakePlan(rows=rows(components=(PP.NEEDS_GO, "fix by hand"),
                                  database=("missing: roles", "create")),
                        database=START_PLAN["database"],
                        pending=[skill.item("go", PP.GO_HOW)])
        h = Harness([plan], start_answers()).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["status"], "pending")

    def test_the_code_is_written_before_anything_that_costs(self):
        plan = FakePlan(rows=rows(components=("to generate: web", "generate"),
                                  database=("missing: roles", "create")),
                        generate=True, database=START_PLAN["database"])
        h = Harness([plan, FakePlan()], start_answers(
            go_setup=res("created", written=False, database="written", files=[]))).run()
        self.assertEqual(names(h)[0], "go_setup")
        self.assertTrue(h.carry["wroteCode"])
        go = h.called("go_setup")[0][1]
        self.assertEqual((go["database"], go["dockerfile"], go["mode"]), ("yes", "yes", "apply"))

    def test_a_failed_code_stops_before_the_start(self):
        plan = FakePlan(rows=rows(components=("to generate: web", "generate"),
                                  database=("missing: roles", "create")),
                        generate=True, database=START_PLAN["database"])
        h = Harness([plan], start_answers(
            go_setup=res("failed", answer=["The modules could not be added."]))).run()
        self.assertEqual(names(h), ["go_setup"])
        self.assertIn(skill.NOTHING_FOR_DATABASE, h.lines)
        self.assertIn("The modules could not be added.", h.lines)
        self.assertEqual(h.block["status"], "failed")


class TestInstanceWait(unittest.TestCase):
    def test_thirty_tries_and_the_limit(self):
        h = Harness([FakePlan(**START_PLAN)], start_answers(
            **{"gcp-cloud-sql_database-describe": NOT_READ})).run()
        self.assertEqual(len(h.called("gcp-cloud-sql_database-describe")), 30)
        self.assertEqual(h.ctx.slept, 29)
        self.assertIn(skill.INSTANCE_LIMIT_STARTED, h.lines)
        self.assertEqual(h.block["pending"], [skill.item("database", skill.INSTANCE_WAIT_HOW)])
        self.assertEqual(h.block["status"], "updated")
        self.assertEqual(h.called("gcp-cloud-sql_database-create"), [])

    def test_a_failed_try_counts_as_a_try(self):
        h = Harness([FakePlan(**START_PLAN), FakePlan()], start_answers(
            **{"gcp-cloud-sql_database-describe": [res("failed", answer=["denied"]),
                                                   READY]})).run()
        self.assertEqual(len(h.called("gcp-cloud-sql_database-describe")), 2)
        self.assertEqual(h.ctx.slept, 1)
        self.assertNotIn("denied", h.lines)
        self.assertEqual(len(h.called("gcp-cloud-sql_database-create")), 1)

    def test_the_clock_ends_the_wait_with_continue(self):
        ctx = FakeCtx(waits=[True, True, False])
        h = Harness([FakePlan(**START_PLAN)], start_answers(
            **{"gcp-cloud-sql_database-describe": NOT_READ}), ctx=ctx).run()
        self.assertEqual(h.block["status"], "continue")
        line, carry = ctx.continued
        self.assertEqual(line, skill.INSTANCE_CONTINUE % (3, 30))
        self.assertEqual((carry["instanceTries"], carry["startedInstance"]), (3, True))
        self.assertEqual(carry["made"], ["gcp-cloud-sql_instance-start: updated"])

    def test_the_eighth_command_ends_as_a_wait_that_cannot_be_run(self):
        ctx = FakeCtx(waits=[False], may_continue=False)
        h = Harness([FakePlan(**START_PLAN)], start_answers(
            **{"gcp-cloud-sql_database-describe": NOT_READ}), ctx=ctx).run()
        self.assertIn(skill.INSTANCE_WAIT_NOT_RUN, h.lines)
        self.assertEqual(h.block["pending"], [skill.item("database", skill.INSTANCE_WAIT_HOW)])

    def continuation(self, tries, plan_db=None):
        carry = skill.new_carry()
        carry.update(made=["gcp-cloud-sql_instance-start: updated"], changed=True,
                     cloudChanged=True, startedInstance=True, instanceTries=tries)
        plan = FakePlan(rows=rows(database=("missing: roles", "create")),
                        database=plan_db or {"name": "demo_dev", "instanceState": "starting",
                                             "start": False, "components": ["web"]})
        return carry, plan

    def test_a_continuation_waits_and_never_starts(self):
        carry, plan = self.continuation(14)
        h = Harness([plan, FakePlan()], start_answers(
            **{"gcp-cloud-sql_database-describe": [NOT_READ, READY]}), carry=carry).run()
        self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])
        self.assertEqual(h.called("gcp-cloud-sql_instance-switch-setup"), [])
        self.assertEqual(h.carry["instanceTries"], 16)
        self.assertNotIn(skill.ALREADY_STARTING, h.lines)
        self.assertIn(skill.START_SENTENCE, h.lines)
        self.assertEqual(h.lines.count("gcp-cloud-sql_instance-start: updated"), 1)
        self.assertEqual(h.block["cost"], skill.STARTED_COST)

    def test_the_tries_are_thirty_for_the_whole_run(self):
        carry, plan = self.continuation(28)
        h = Harness([plan], start_answers(
            **{"gcp-cloud-sql_database-describe": NOT_READ}), carry=carry).run()
        self.assertEqual(len(h.called("gcp-cloud-sql_database-describe")), 2)
        self.assertIn(skill.INSTANCE_LIMIT_STARTED, h.lines)

    def test_an_instance_someone_else_started(self):
        plan = FakePlan(rows=rows(database=("missing: roles", "create")),
                        database={"name": "demo_dev", "instanceState": "starting",
                                  "start": False, "components": ["web"]})
        h = Harness([plan, FakePlan()], start_answers()).run()
        self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])
        self.assertIn(skill.ALREADY_STARTING, h.lines)
        self.assertNotIn(skill.START_SENTENCE, h.lines)
        self.assertEqual(h.block["cost"], skill.NO_COST)


class TestPluginsAndSentences(unittest.TestCase):
    """Part 3b: a command of another suite, and the two sentences of section 18."""

    VERSION = common.VERSION_SENTENCE.format(callee="aleogr-repo-github", caller="aleogr")

    def test_a_command_of_another_suite_stops_the_run(self):
        version = {"aleogr-result": 1, "status": "failed", "answer": [self.VERSION],
                   "pending": [], "outputs": {}, "callError": "version"}
        plan = FakePlan(rows=rows(settings=("differs", "update"),
                                  protection=("protected", "update")))
        h = Harness([plan], {"github_repo-configure": version}).run()
        self.assertEqual(names(h), ["github_repo-configure"])  # nothing after it
        self.assertEqual(len(h.plan_calls), 1)
        self.assertEqual(h.block["status"], "failed")
        self.assertEqual(h.lines.count(self.VERSION), 1)
        self.assertEqual(h.block["pending"],
                         [skill.item("plugins", "/aleogr:project-apply confirm=yes")])

    def test_a_failed_read_is_said_once_and_its_how_is_the_skill_as_run(self):
        sentence = ("The repository's Actions secrets could not be read; nothing was set. "
                    "Check ..., then run this skill again.")
        failed = FakePlan(failure=PP.Failure(sentence, "ci secrets", sentence[:-1],
                                             called=True),
                          pending=[skill.item("ci secrets", sentence[:-1])])
        h = Harness([failed], {}, args={"confirmVisibility": "public",
                                        "confirm": "yes"}).run()
        self.assertEqual(h.block["status"], "failed")
        self.assertEqual(h.block["pending"], [skill.item(
            "ci secrets", "/aleogr:project-apply confirmVisibility=public confirm=yes")])
        self.assertNotIn(sentence[:-1], h.lines)
        # A failure of the plan's own (not a called read) keeps its own item.
        own = FakePlan(failure=PP.Failure("No declaration.", "declaration", "declare it"),
                       pending=[skill.item("declaration", "declare it")])
        h = Harness([own], {}).run()
        self.assertEqual(h.block["pending"], [skill.item("declaration", "declare it")])

    def test_the_plan_is_told_the_skill_as_the_owner_ran_it(self):
        a = skill.Apply({"confirm": "yes"}, FakeCtx(), skill.new_carry())
        self.assertEqual(a.again(), "/aleogr:project-apply confirm=yes")
        a = skill.Apply({}, FakeCtx(), skill.new_carry())
        self.assertEqual(a.again(), "/aleogr:project-apply")


class TestContinue(unittest.TestCase):
    PLAN = dict(rows=rows(ci_secrets=("missing: GCP_IMAGE_PATH", "set")))

    def test_step_limit_before_a_step(self):
        # The limit has passed: the first step after the plan is still made (every
        # command makes one), and the command continues before the next one.
        ctx = FakeCtx(step=False)
        h = Harness([FakePlan(**self.PLAN)], {"github_variables-set": res("updated")},
                    ctx=ctx).run()
        self.assertEqual(names(h), ["github_variables-set"])
        self.assertEqual(len(h.plan_calls), 1)
        self.assertEqual(h.block["status"], "continue")
        self.assertEqual(ctx.continued[0], skill.CONTINUE_LINE % "the last plan")
        self.assertEqual(ctx.continued[1]["made"], ["github_variables-set: updated"])

    def test_step_limit_on_the_eighth_command(self):
        ctx = FakeCtx(step=False, may_continue=False)
        h = Harness([FakePlan(**self.PLAN)], {"github_variables-set": res("updated")},
                    ctx=ctx).run()
        self.assertEqual(names(h), ["github_variables-set"])
        self.assertIn(skill.COMMANDS_LIMIT % "the last plan", h.lines)
        self.assertEqual(h.block["pending"], [skill.item("run", skill.COMMANDS_LIMIT_HOW)])

    def test_a_step_limit_of_one_step_per_command(self):
        # ALEOGR_STEP_LIMIT=1 with a plan longer than a second: after a merge, the run
        # takes three commands, one step each: the update, the configure, the last plan.
        behind = dict(rows=rows(declaration=("behind", "update")))
        after = dict(rows=rows(settings=("differs", "update")))
        answers = {"github_checkout-setup": res("updated"),
                   "github_repo-configure": res("updated")}
        h1 = Harness([FakePlan(**behind), FakePlan(**after)], answers,
                     ctx=FakeCtx(step=False)).run()
        self.assertEqual(names(h1), ["github_checkout-setup"])
        self.assertEqual(len(h1.plan_calls), 1)
        self.assertEqual(h1.ctx.continued[0], skill.CONTINUE_LINE % "the plan after the update")
        h2 = Harness([FakePlan(**after), FakePlan()], answers, ctx=FakeCtx(step=False),
                     carry=h1.ctx.continued[1]).run()
        self.assertEqual(names(h2), ["github_repo-configure"])
        self.assertEqual(h2.ctx.continued[0], skill.CONTINUE_LINE % "the last plan")
        h3 = Harness([FakePlan()], answers, ctx=FakeCtx(step=False),
                     carry=h2.ctx.continued[1]).run()
        self.assertEqual(h3.calls, [])
        self.assertEqual(h3.block["status"], "updated")
        self.assertEqual(h3.lines[:2], ["github_checkout-setup: updated",
                                        "github_repo-configure: updated"])
        # The same run in one command: the same lines and status.
        one = Harness([FakePlan(**behind), FakePlan(**after), FakePlan()], answers).run()
        self.assertEqual(names(one), ["github_checkout-setup", "github_repo-configure"])
        self.assertEqual((one.lines, one.block), (h3.lines, h3.block))

    def test_a_called_command_ended_by_a_limit(self):
        ctx = FakeCtx()
        cut = res("updated", data={"waitRefused": True})
        h = Harness([FakePlan(rows=rows(services=("missing: web", "create"),
                                        database=(PP.FOLLOWS_SERVICES, "none")))],
                    {"gcp_deploy-setup": cut}, ctx=ctx).run()
        self.assertEqual(h.block["status"], "continue")
        self.assertTrue(ctx.continued[1]["changed"])

    def test_a_continuation_keeps_the_lines_once(self):
        carry = skill.new_carry()
        carry.update(made=["gcp_services-enable: updated"], changed=True)
        h = Harness([FakePlan()], {}, carry=carry).run()
        self.assertEqual(h.lines[0], "gcp_services-enable: updated")
        self.assertEqual(h.block["status"], "updated")  # nothing to do, after a change

    def test_a_continuation_plans_with_the_project_it_created(self):
        carry = skill.new_carry()
        carry.update(project={"id": PID, "how": "created"}, changed=True, wroteCode=True)
        h = Harness([FakePlan()], {}, carry=carry).run()
        self.assertEqual(h.plan_calls[0], {"projectId": PID, "readCloud": "yes"})
        self.assertIn(skill.CREATES_LINE, h.lines)

    def test_carry_values_of_another_type_are_refused(self):
        # A carry is taken whole or not at all (M1): one value of another type refuses it.
        c = dict(skill.new_carry(), made="x", instanceTries="3", startedInstance=True,
                 project={"id": 5})
        self.assertIsNone(skill._valid_carry(c))
        self.assertEqual(skill._valid_carry(skill.new_carry()), skill.new_carry())

    def test_the_digest_holds_the_declaration_and_the_arguments(self):
        a = common.carry_digest(b"{}", {"confirm": "yes"})
        self.assertNotEqual(a, common.carry_digest(b"{} ", {"confirm": "yes"}))
        self.assertNotEqual(a, common.carry_digest(b"{}", {"confirmVisibility": "public",
                                                          "confirm": "yes"}))

    def test_an_api_poll_goes_on_in_the_next_command(self):
        refused = FakePlan(failure=PP.Failure("refused", "registry", "x"),
                           pending=[skill.item("registry", "x")])
        carry = skill.new_carry()
        carry.update(apisEnabled=True, apisTries=8, changed=True)
        h = Harness([refused, refused, refused], {}, carry=carry).run()
        self.assertEqual(len(h.plan_calls), 2)  # tries 9 and 10
        self.assertIn(skill.APIS_LIMIT, h.lines)
        self.assertEqual(h.block["pending"], [skill.item("apis", skill.APIS_HOW)])


class TestPathsNoScenarioCovers(unittest.TestCase):
    def test_shared_project_endings_name_no_id(self):
        cases = ((res(exists=False), skill.SHARED_NOT_READY),
                 (res(exists=True, projectId=SHARED, enabledServices=[]),
                  skill.SHARED_NOT_READY),
                 (res("failed", answer=["More than one GCP project has the labels x (%s)"
                                        % SHARED]), skill.SHARED_AMBIGUOUS),
                 (res("failed", answer=["The projects of %s could not be read." % SHARED]),
                  skill.SHARED_UNREADABLE))
        for ending, sentence in cases:
            with self.subTest(sentence=sentence):
                h = Harness([FakePlan(**START_PLAN)], start_answers(
                    **{"gcp_environment-describe": ending})).run()
                self.assertIn(sentence, h.lines)
                self.assertFalse(any(SHARED in l for l in h.lines))
                self.assertEqual(h.called("gcp-cloud-sql_instance-switch-setup"), [])

    def test_instance_states_that_make_nothing(self):
        for st, how in (("creating", skill.INSTANCE_STATE_HOW % ("creating", "creating")),
                        ("unknown", skill.INSTANCE_UNKNOWN_HOW)):
            with self.subTest(state=st):
                plan = FakePlan(rows=rows(database=("missing: roles", "create")),
                                database={"name": "demo_dev", "instanceState": st,
                                          "start": False, "components": ["web"]})
                h = Harness([plan], start_answers()).run()
                self.assertEqual(h.calls, [])
                self.assertEqual(h.block["pending"], [skill.item("database", how)])
                self.assertEqual(h.block["status"], "pending")

    def test_settings_only_reads_the_shared_project_then_sets_them(self):
        plan = FakePlan(rows=rows(database=("differs: settings", "update")))
        h = Harness([plan, FakePlan()], start_answers()).run()
        self.assertEqual(names(h), ["gcp_environment-describe", "gcp_deploy-setup"])
        env = h.called("gcp_deploy-setup")[0][1]["env"]
        self.assertEqual(env, PP.database_settings("demo", ["web"], SHARED, "us-central1",
                                                   "aleogr-shared", PID))
        self.assertEqual(list(h.called("gcp_deploy-setup")[0][1])[-2:], ["env", "mode"])

    def test_the_item_access_is_carried_last(self):
        access = {"item": "access", "reason": "manual",
                  "how": "/aleogr:project-access person=<e-mail>"}
        plan = FakePlan(rows=rows(services=("missing: web", "create"),
                                  database=(PP.FOLLOWS_SERVICES, "none")))
        later = FakePlan(rows=rows(database=("missing: roles", "create")))
        h = Harness([plan, later, FakePlan()], start_answers(
            **{"gcp_deploy-setup": res("created", pending=[access])})
        ).run()
        self.assertEqual(h.block["pending"][-1], access)
        self.assertEqual(len(h.called("gcp_deploy-setup")), 2)

    def test_proposal_title_and_warnings(self):
        d = copy.deepcopy(DECL)
        plan = FakePlan(rows=rows(declaration=("changed here", "propose"),
                                  database=("not checked until the change is merged",
                                            "none")),
                        decl=d, repositoryEnvironments=[], repositoryDatabaseComponents=[],
                        changed=[".aleogr/project.json", "web/db.go"])
        h = Harness([plan], {"github_pull-request-open": res(
            "created", pullRequest={"number": 7, "url": "https://x/pull/7"})}).run()
        pr = h.called("github_pull-request-open")[0][1]
        self.assertEqual(pr["title"], "Add the database check of web")
        self.assertEqual(pr["note"], "%s %s" % (skill.PROPOSAL_WARNING, skill.DATABASE_WARNING))
        self.assertEqual(pr["paths"].split(",")[:3],
                         [".aleogr/project.json", ".github/workflows/ci.yml", "web/go.mod"])
        self.assertIn(skill.PROPOSAL_WARNING, h.lines)
        self.assertIn(skill.DATABASE_WARNING, h.lines)
        self.assertEqual(h.block["outputs"]["pullRequest"], {"number": 7, "url": "https://x/pull/7"})

    def test_a_refused_push_names_the_local_branch(self):
        plan = FakePlan(rows=rows(declaration=("changed here", "propose")),
                        changed=[".aleogr/project.json"])
        r = res("failed", answer=["The branch aleogr/change-abc123 could not be pushed: x; "
                                  "nothing reached GitHub, and the commit is kept in the local "
                                  "branch aleogr/change-abc123."])
        h = Harness([plan], {"github_pull-request-open": r}).run()
        how = h.block["pending"][0]["how"]
        self.assertIn("aleogr/change-abc123", how)
        self.assertTrue(how.endswith(skill.BRANCH_NEXT))
        self.assertEqual(h.block["status"], "updated")

    def test_the_login_holds_the_files(self):
        plan = FakePlan(rows=rows(ci=("differs", "generate"),
                                  services=("waits for the login", "prepare the login"),
                                  database=(PP.FOLLOWS_SERVICES, "none"),
                                  ci_secrets=("missing: GCP_IMAGE_PATH", "set")),
                        generate=True, pending=[skill.item("login", PP.LOGIN_HOW)])
        h = Harness([plan, plan], {"github_variables-set": res("updated")}).run()
        self.assertEqual(names(h), ["github_variables-set"])  # no go_setup, ci-setup or PR
        self.assertIn(skill.FILES_WITH_SERVICES % skill.LOCAL_CI, h.lines)
        self.assertIn(skill.item("login", PP.LOGIN_HOW), h.block["pending"])
        self.assertNotIn("ci", [x["item"] for x in h.block["pending"]])

    def test_no_invocation_runs_a_provider_command_itself(self):
        # The module has no runner of its own: every command is a called skill's.
        with open(skill.__file__, encoding="utf-8") as f:
            text = f.read()
        for word in ("ctx.write(", "ctx.run(", "ctx.read(", "subprocess"):
            self.assertNotIn(word, text)



# ---------------------------------------------------------------------------
# The review of part 3a: a run that takes more than one command

import io  # noqa: E402
import json  # noqa: E402
import shlex  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

PATCH = "gcloud sql instances patch aleogr-shared --project=%s --activation-policy=ALWAYS" % SHARED


def aborted(written=True, sentence=common.TIME_LIMIT_SENTENCE):
    """A called command aborted by its deadline, as call_plugin returns it."""
    wrote = (common.REFUSED_WRITTEN.format(writes="`%s`" % PATCH) if written
             else common.REFUSED_NOTHING_WRITTEN)
    return res("failed", answer=[sentence, wrote, common.READ_STATE_SENTENCE],
               data={"timeLimit": True})


def block_of(out):
    return json.loads(out.split("```aleogr-result\n", 1)[1].split("\n```", 1)[0])


def next_words(out):
    lines = [l for l in out.splitlines() if l.startswith("next: ")]
    return shlex.split(lines[-1][len("next: "):]) if lines else None


class RealRun(object):
    """Commands of project-apply through the real dispatcher (run_command: the carried
    file, its digest, the aborted result), with fake plans and invocations: the module's
    Apply is replaced, for the time of a command, by a TestApply given this object's plan
    and call functions. The folder holds a declaration whose bytes a call may change."""

    def __init__(self, test, plans, answers, waits=None, on_call=None):
        self.test = test
        self.plans = list(plans)
        self.answers = answers
        self.waits = list(waits or [])
        self.on_call = on_call or {}
        self.calls = []
        self.plan_calls = []
        self.applies = []
        self.top = tempfile.mkdtemp()
        self.folder = os.path.join(self.top, "work")
        os.makedirs(os.path.join(self.folder, ".aleogr"))
        self.write_declaration(json.dumps(DECL))
        os.makedirs(os.path.join(self.top, "tmp"))
        common.set_carry_folder(os.path.join(self.top, "tmp"))
        common.set_clock(lambda: 1000.0)
        self.cwd = os.getcwd()
        os.chdir(self.folder)
        test.addCleanup(self.close)

    def close(self):
        os.chdir(self.cwd)
        common.set_carry_folder()
        common.set_clock()
        shutil.rmtree(self.top)

    def write_declaration(self, text):
        with open(os.path.join(self.folder, skill.DECLARATION), "w") as f:
            f.write(text)

    def carried_files(self):
        folder = common.carry_folder_path()
        return sorted(os.listdir(folder)) if os.path.isdir(folder) else []

    def plan(self, a):
        self.plan_calls.append(dict(a))
        return self.plans.pop(0) if len(self.plans) > 1 else self.plans[0]

    def call(self, command, name, a, read_only):
        self.calls.append((name, dict(a), read_only))
        r = self.answers.get(name, res())
        if isinstance(r, list):
            r = r.pop(0) if len(r) > 1 else r[0]
        if name in self.on_call:
            self.on_call[name]()
        if isinstance(r, Exception):
            raise r
        return copy.deepcopy(r)

    def wait(self, counted=True):
        return self.waits.pop(0) if self.waits else True

    def command(self, words):
        run = self

        class Patched(TestApply):
            def __init__(self, args, ctx, carry, lost=None):
                ctx.wait = run.wait
                TestApply.__init__(self, args, ctx, carry, plan_fn=run.plan,
                                   call_fn=run.call, lost=lost)
                run.applies.append(self)

        inv = common.parse_command_line(words)
        out, err = io.StringIO(), io.StringIO()
        saved = skill.Apply
        skill.Apply = Patched
        try:
            code = common.run_command("aleogr", ROOT, inv, skill, "apply", out, err,
                                      environ={})
        finally:
            skill.Apply = saved
        return code, out.getvalue()

    def whole_run(self, words, limit=8):
        """The command, then each `next:` command: the (code, out) of each."""
        got = []
        while len(got) < limit:
            code, out = self.command(words)
            got.append((code, out))
            if code != 0 or block_of(out)["status"] != "continue":
                break
            words = next_words(out)[1:]
        return got

    def called(self, name):
        return [c for c in self.calls if c[0] == name]


# After a merge: the folder is updated (the pull rewrites the declaration), then the
# database is made on a stopped instance, which accepts calls only in the next command.
UPDATE_PLAN = dict(rows=rows(declaration=("behind", "update"),
                             database=("missing: roles, settings", "create")),
                   database=START_PLAN["database"])
STARTING_DB = {"name": "demo_dev", "instanceState": "starting", "start": False,
               "components": ["web"]}
RUNNING_DB = dict(STARTING_DB, instanceState="running")



class TestDeclarationAfterTheUpdate(unittest.TestCase):
    """Found in the real run of part 3a: after a merge the folder is behind; the update
    rewrites the declaration, and what the run makes next must come from the declaration
    as it is then, not from the folder as it was when the command started."""

    def test_the_settings_are_made_from_the_updated_declaration(self):
        merged = copy.deepcopy(DECL)
        merged["repo"]["topics"] = ["go", "sample"]
        merged["repo"]["description"] = "Demo project, merged"
        before = FakePlan(rows=rows(declaration=("behind", "update")))
        after = FakePlan(rows=rows(settings=("differs: topics", "update")), decl=merged)
        done = FakePlan(decl=merged)
        h = Harness([before, after, done],
                    {"github_checkout-setup": res("updated"),
                     "github_repo-configure": res("updated")}).run()
        configure = h.called("github_repo-configure")
        self.assertEqual(len(configure), 1)
        a = configure[0][1]
        self.assertEqual(a["topics"], "aleogr-demo,go,sample")
        self.assertEqual(a["description"], "Demo project, merged")
        self.assertEqual(a["mode"], "apply")
        self.assertEqual(h.block["status"], "updated")
        self.assertIn("github_repo-configure: updated", h.lines)


class TestDigestAfterTheUpdate(unittest.TestCase):
    """C1: the update of the folder rewrites the declaration; the carry saved at the end of
    that command holds the digest of the declaration as it is then."""

    def after_merge(self, edit_between=None):
        run = RealRun(self, [FakePlan(**UPDATE_PLAN), FakePlan(**START_PLAN),
                             FakePlan(rows=rows(database=("missing: roles", "create")),
                                      database=STARTING_DB), FakePlan()],
                      dict(start_answers(**{
                          "github_checkout-setup": res("updated"),
                          "gcp-cloud-sql_database-describe": [NOT_READ, NOT_READ, READY]})),
                      waits=[True, False],  # the clock ends the wait on try 2
                      on_call={"github_checkout-setup": lambda: run.write_declaration(
                          json.dumps(DECL, indent=2) + "\n")})
        code, out = run.command(["project-apply", "confirm=yes"])
        self.assertEqual((code, block_of(out)["status"]), (0, "continue"))
        if edit_between:
            run.write_declaration(edit_between)
        code, out = run.command(next_words(out)[1:])
        return run, code, out

    def test_the_carry_survives_the_update_of_the_folder(self):
        run, code, out = self.after_merge()
        self.assertEqual(code, 0)
        lines = out.split("```aleogr-result")[0].splitlines()
        self.assertNotIn("could not be recalled", out)
        for line in ("github_checkout-setup: updated", "gcp-cloud-sql_instance-start: updated",
                     "gcp-cloud-sql_database-create: created", skill.START_SENTENCE):
            self.assertEqual(lines.count(line), 1, line)
        self.assertNotIn(skill.ALREADY_STARTING, out)
        self.assertEqual(block_of(out)["cost"], skill.STARTED_COST)
        self.assertEqual(block_of(out)["status"], "updated")
        self.assertEqual(len(run.called("gcp-cloud-sql_instance-start")), 1)
        self.assertEqual(len(run.called("github_checkout-setup")), 1)
        self.assertEqual(len(run.called("gcp-cloud-sql_database-describe")), 3)
        self.assertEqual(run.carried_files(), [])

    def test_a_declaration_changed_by_hand_between_commands_is_still_refused(self):
        run, code, out = self.after_merge(edit_between=json.dumps(DECL) + " ")
        self.assertIn(common.CARRY_LOST_SENTENCE.format(
            why=common.CARRY_REFUSALS["mismatch"]), out)
        self.assertNotIn(skill.START_SENTENCE, out)  # the new run started nothing


class TestStartCutByTheDeadline(unittest.TestCase):
    """C2: the start is invoked, and a limit of the run ends it before its result."""

    def cut(self, **ctx_kw):
        ctx = FakeCtx(**ctx_kw)
        h = Harness([FakePlan(**START_PLAN)], start_answers(
            **{"gcp-cloud-sql_instance-start": aborted()}), ctx=ctx).run()
        return h

    def test_the_start_asked_is_carried_and_costs(self):
        h = self.cut()
        self.assertEqual(h.block["status"], "continue")
        carry = h.ctx.continued[1]
        self.assertTrue(carry["startAsked"])
        self.assertFalse(carry["startedInstance"])
        self.assertEqual(carry["made"], ["gcp-cloud-sql_instance-start: failed"])
        self.assertEqual(h.block["cost"], skill.START_UNKNOWN_COST)
        self.assertEqual(h.ctx.abort[-1], skill.START_SENTENCE)

    def test_on_the_eighth_command_the_answer_says_the_state_is_not_known(self):
        h = self.cut(may_continue=False)
        self.assertIn(skill.START_FAILURES[2], h.lines)
        self.assertNotIn(skill.START_SENTENCE, h.lines)
        self.assertEqual(h.block["cost"], skill.START_UNKNOWN_COST)

    def test_registered_before_the_start_is_invoked(self):
        seen = []
        ctx = FakeCtx()
        h = Harness([FakePlan(**START_PLAN)], start_answers(), ctx=ctx)
        call = h.call

        def spy(command, name, a, read_only):
            if name == "gcp-cloud-sql_instance-start":
                seen.append((list(ctx.abort), h.apply.carry["startAsked"]))
            return call(command, name, a, read_only)

        h.call = spy
        h.run()
        self.assertEqual(seen, [([skill.START_SENTENCE], True)])

    def test_a_start_cut_before_its_write_was_not_asked(self):
        h = Harness([FakePlan(**START_PLAN)], start_answers(
            **{"gcp-cloud-sql_instance-start": aborted(written=False)})).run()
        carry = h.ctx.continued[1]
        self.assertFalse(carry["startAsked"])
        self.assertEqual(carry["made"], [])
        self.assertEqual(h.block["cost"], skill.NO_COST)

    def next_command(self, db, rows_db=("missing: roles", "create"), **answers):
        carry = self.cut().ctx.continued[1]
        plan = FakePlan(rows=rows(database=rows_db), database=db)
        return Harness([plan, FakePlan()], start_answers(**answers), carry=carry).run()

    def test_the_next_command_finds_it_starting(self):
        h = self.next_command(STARTING_DB)
        self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])
        self.assertEqual(h.called("gcp-cloud-sql_instance-switch-setup"), [])
        self.assertNotIn(skill.ALREADY_STARTING, h.lines)
        self.assertIn(skill.START_SENTENCE, h.lines)
        self.assertNotIn(skill.START_FAILURES[2], h.lines)
        self.assertIn("gcp-cloud-sql_instance-start: updated", h.lines)
        self.assertNotIn("gcp-cloud-sql_instance-start: failed", h.lines)
        self.assertEqual(h.block["cost"], skill.STARTED_COST)
        self.assertEqual(len(h.called("gcp-cloud-sql_database-create")), 1)

    def test_the_next_command_finds_it_running(self):
        h = self.next_command(RUNNING_DB)
        self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])
        self.assertEqual(h.called("gcp-cloud-sql_database-describe"), [])
        self.assertIn(skill.START_SENTENCE, h.lines)
        self.assertNotIn(skill.ALREADY_STARTING, h.lines)
        self.assertEqual(h.block["cost"], skill.STARTED_COST)

    def test_the_next_command_finds_it_stopped(self):
        # The start did not take effect: as a failed start whose read shows the instance
        # stopped, the run stops; it never starts the instance a second time.
        h = self.next_command(START_PLAN["database"])
        self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])
        self.assertEqual(h.called("gcp-cloud-sql_instance-switch-setup"), [])
        self.assertEqual(h.called("gcp-cloud-sql_database-create"), [])
        self.assertIn(skill.START_FAILURES[0], h.lines)
        self.assertNotIn(skill.START_SENTENCE, h.lines)
        self.assertNotIn(skill.START_FAILURES[2], h.lines)
        self.assertEqual(h.block["cost"], skill.NO_COST)
        self.assertIn(skill.item("database", skill.START_FAILED_HOW), h.block["pending"])

    def test_the_next_command_cannot_read_it(self):
        carry = self.cut().ctx.continued[1]
        plan = FakePlan(rows=rows(database=("missing: roles", "create")),
                        database=dict(STARTING_DB, instanceState="unknown"))
        h = Harness([plan], start_answers(), carry=carry).run()
        self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])
        self.assertIn(skill.START_FAILURES[2], h.lines)
        self.assertEqual(h.block["cost"], skill.START_UNKNOWN_COST)
        self.assertNotIn(skill.ALREADY_STARTING, h.lines)


VIS_DECL = dict(DECL, repo=dict(DECL["repo"], visibility="public"), components=[],
                environments={})
PRIV_DECL = dict(DECL, components=[], environments={})
REPO_ROWS = ROWS[:7]


def repo_rows(**changes):
    return [(n, changes.get(n.replace(" ", "_"), (st, act))[0],
             changes.get(n.replace(" ", "_"), (st, act))[1]) for n, st, act in REPO_ROWS]


class TestVisibilityAppliedEarlier(unittest.TestCase):
    """I1: a run confirmed with confirmVisibility=<value> that applied it in an earlier
    command goes on in the next one."""

    def test_public_at_birth(self):
        birth = FakePlan(rows=repo_rows(repository=("missing", "create")), exposes=True,
                         visibility="public", decl=VIS_DECL)
        ctx = FakeCtx(step=[True, False])  # the step limit right after the creation
        h = Harness([birth], {"github_repo-create": res("created")}, ctx=ctx,
                    args={"confirmVisibility": "public"}).run()
        self.assertEqual(h.block["status"], "continue")
        carry = h.ctx.continued[1]
        self.assertEqual(carry["visibilityApplied"], "public")
        later = FakePlan(rows=repo_rows(settings=("differs", "update"),
                                        declaration=("not sent", "send"),
                                        protection=("missing", "create")),
                         visibility="public", decl=VIS_DECL)
        h2 = Harness([later, FakePlan(rows=REPO_ROWS, decl=VIS_DECL)],
                     {"github_repo-configure": res("updated"),
                      "github_checkout-setup": res("created"),
                      "github_branch-protect": res("created")},
                     carry=carry, args={"confirmVisibility": "public"}).run()
        self.assertNotIn(skill.CONFIRM_VISIBILITY_NOT_NEEDED % "public", h2.lines)
        self.assertEqual(names(h2), ["github_repo-configure", "github_checkout-setup",
                                     "github_branch-protect"])
        self.assertEqual(h2.block["status"], "created")

    def test_private(self):
        change = FakePlan(rows=repo_rows(visibility=("differs", "update"),
                                         protection=("protected", "update")),
                          visibility="private", decl=PRIV_DECL)
        ctx = FakeCtx(step=[True, False])
        h = Harness([change], {"github_repo-configure": res("updated")}, ctx=ctx,
                    args={"confirmVisibility": "private"}).run()
        carry = h.ctx.continued[1]
        self.assertEqual(carry["visibilityApplied"], "private")
        self.assertEqual(h.called("github_repo-configure")[0][1]["confirmVisibility"],
                         "private")
        later = FakePlan(rows=repo_rows(protection=("protected", "update")),
                         visibility="private", decl=PRIV_DECL)
        h2 = Harness([later, FakePlan(rows=REPO_ROWS, decl=PRIV_DECL)],
                     {"github_branch-protect": res("updated")}, carry=carry,
                     args={"confirmVisibility": "private"}).run()
        self.assertEqual(names(h2), ["github_branch-protect"])
        self.assertEqual(h2.block["status"], "updated")
        # Everything made: nothing to do, not a failure.
        h3 = Harness([FakePlan(rows=REPO_ROWS, decl=PRIV_DECL)], {}, carry=carry,
                     args={"confirmVisibility": "private"}).run()
        self.assertEqual(h3.block["status"], "updated")
        self.assertNotIn(skill.CONFIRM_VISIBILITY_NOT_NEEDED % "private", h3.lines)

    def test_the_flag_confirms_nothing_by_itself(self):
        carry = skill.new_carry()
        carry.update(visibilityApplied="public", changed=True)
        # Another change of visibility: its own confirmation, as before.
        private = FakePlan(rows=repo_rows(visibility=("differs", "update")),
                           visibility="private", decl=PRIV_DECL)
        h = Harness([private], {}, carry=copy.deepcopy(carry),
                    args={"confirmVisibility": "public"}).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["pending"][0]["item"], "confirm visibility private")
        # An exposure without confirmVisibility=public in this command's arguments.
        public = FakePlan(rows=repo_rows(visibility=("differs", "update")), exposes=True,
                          visibility="public", decl=VIS_DECL)
        h = Harness([public], {}, carry=copy.deepcopy(carry), args={"confirm": "yes"}).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["pending"][0]["item"], "confirm visibility public")
        # A visibility applied by this run, but another one named: the check holds.
        h = Harness([FakePlan(rows=REPO_ROWS, decl=PRIV_DECL)], {},
                    carry=copy.deepcopy(carry), args={"confirmVisibility": "private"}).run()
        self.assertIn(skill.CONFIRM_VISIBILITY_NOT_NEEDED % "private", h.lines)
        # The start needs confirm=yes itself, whatever the flag.
        start = FakePlan(**START_PLAN)
        h = Harness([start], start_answers(), carry=copy.deepcopy(carry),
                    args={"confirmVisibility": "public"}).run()
        self.assertEqual(h.called("gcp-cloud-sql_instance-start"), [])


class TestAbortedOrchestrator(unittest.TestCase):
    """I2: the aborted answer of a run that calls other commands never says that nothing
    was written."""

    def test_the_lines_made_so_far(self):
        run = RealRun(self, [FakePlan(**UPDATE_PLAN), FakePlan(**START_PLAN)],
                      start_answers(**{
                          "github_checkout-setup": res("updated"),
                          "gcp-cloud-sql_database-create": common.TimeLimit(["gcloud"])}))
        code, out = run.command(["project-apply", "confirm=yes"])
        self.assertEqual(code, common.EXIT_SOFTWARE)
        lines = out.split("\n\n")[0].splitlines()
        self.assertEqual(lines, [common.TIME_LIMIT_SENTENCE, "github_checkout-setup: updated",
                                 "gcp-cloud-sql_instance-start: updated",
                                 skill.START_SENTENCE, common.READ_STATE_SENTENCE])
        self.assertNotIn(common.REFUSED_NOTHING_WRITTEN, out)

    def test_nothing_made_yet_says_it_is_not_known(self):
        run = RealRun(self, [FakePlan(**UPDATE_PLAN)],
                      {"github_checkout-setup": ValueError("x")})
        code, out = run.command(["project-apply", "confirm=yes"])
        self.assertEqual(code, common.EXIT_SOFTWARE)
        self.assertEqual(out.split("\n\n")[0].splitlines(),
                         [common.UNEXPECTED_SENTENCE, common.REFUSED_UNKNOWN,
                          common.READ_STATE_SENTENCE])

    def test_the_lines_are_registered_as_each_is_added(self):
        h = Harness([FakePlan(**UPDATE_PLAN), FakePlan(**START_PLAN), FakePlan()],
                    start_answers(**{"github_checkout-setup": res("updated")})).run()
        self.assertEqual(h.ctx.abort, h.carry["made"] + [skill.START_SENTENCE])


class TestCarryContent(unittest.TestCase):
    """M1: a carried file is taken only as this module writes it."""

    def valid(self, **over):
        c = skill.new_carry()
        c.update(made=["github_checkout-setup: updated", "go_setup component=web: created",
                       "github_branch-protect checks=ci: updated"],
                 project={"id": PID, "how": "created"}, instanceTries=30, apisTries=10,
                 apisAnswered=["gcp_ci-identity-setup", 3], visibilityApplied="private",
                 access=dict(skill.ACCESS_ITEM),
                 route=[{"item": "route", "reason": "manual",
                         "how": "add the line mux.HandleFunc(\"GET /db\", dbCheck) to the "
                                "router in web/main.go; until then the tests of "
                                "web/db_test.go, which expect the route, fail"}])
        c.update(over)
        return c

    def test_what_this_module_writes_is_taken(self):
        c = self.valid()
        self.assertEqual(skill._valid_carry(c), c)

    def test_each_value_out_of_range_refuses_it(self):
        bad = {
            "instanceTries": [31, -1, True, 1.0], "apisTries": [11, -1, False],
            "startAsked": [1, "true", None], "startedInstance": [0], "changed": ["yes"],
            "project": [{"id": "Bad_Id", "how": "created"}, {"id": PID, "how": "made"},
                        {"id": PID}, {"id": PID, "how": "found", "x": 1}, "x",
                        {"id": "ab", "how": "found"}],
            "made": [["rm -rf: updated"], ["github_repo-create: deleted"],
                     ["github_repo-create created"], ["go_setup component=Web: created"],
                     ["github_repo-create checks=ci: created"],
                     ["github_repo-create: created", "github_repo-create: created"],
                     [5], "github_repo-create: created"],
            "apisAnswered": [["gcp_x", 3], ["aleogr:project-plan", 1],
                             ["aleogr:project-plan", 11], "aleogr:project-plan"],
            "visibilityApplied": ["internal", True],
            "access": [{"item": "access", "reason": "manual", "how": "rm -rf /"},
                       dict(skill.ACCESS_ITEM, extra=1)],
            "route": [[{"item": "route", "reason": "manual", "how": "x"}],
                      [dict(skill.ACCESS_ITEM)], {"item": "route"}],
        }
        for key, values in bad.items():
            for v in values:
                with self.subTest(key=key, value=v):
                    self.assertIsNone(skill._valid_carry(self.valid(**{key: v})))

    def test_a_key_more_or_less_refuses_it(self):
        c = self.valid()
        c["extra"] = 1
        self.assertIsNone(skill._valid_carry(c))
        c = self.valid()
        del c["made"]
        self.assertIsNone(skill._valid_carry(c))

    def test_a_file_edited_by_hand_goes_on_as_a_new_run(self):
        run = RealRun(self, [FakePlan(**START_PLAN), FakePlan()], start_answers(
            **{"gcp-cloud-sql_database-describe": [NOT_READ, READY]}), waits=[False])
        code, out = run.command(["project-apply", "confirm=yes"])
        self.assertEqual(block_of(out)["status"], "continue")
        words = next_words(out)[1:]
        name = run.carried_files()[0]
        path = os.path.join(common.carry_folder_path(), name)
        with open(path) as f:
            record = json.load(f)
        record["carry"]["instanceTries"] = 31
        with open(path, "w") as f:
            json.dump(record, f)
        code, out = run.command(words)
        self.assertIn(common.CARRY_LOST_SENTENCE.format(
            why=common.CARRY_REFUSALS["invalid"]), out)
        fresh = run.applies[-1].carry  # nothing of the edited file is taken
        self.assertEqual((fresh["instanceTries"], fresh["startedInstance"], fresh["made"]),
                         (0, False, []))
        self.assertIn(name, run.carried_files())  # not this run's own: left to the sweep

    def test_a_refusal_in_a_command_that_continues_reaches_the_last_answer_once(self):
        # Command 1 continues; its file is edited by hand; command 2 refuses it, goes on
        # as a new run and continues itself; command 3 ends the run. The sentence of the
        # refusal is in the run's last answer, once, and in no `continue` answer.
        run = RealRun(self, [FakePlan(**START_PLAN), FakePlan(**START_PLAN), FakePlan()],
                      start_answers(**{"gcp-cloud-sql_database-describe":
                                       [NOT_READ, NOT_READ, READY]}),
                      waits=[False, False])
        code, out = run.command(["project-apply", "confirm=yes"])
        self.assertEqual(block_of(out)["status"], "continue")
        words = next_words(out)[1:]
        path = os.path.join(common.carry_folder_path(), run.carried_files()[0])
        with open(path) as f:
            record = json.load(f)
        record["carry"]["instanceTries"] = 31
        with open(path, "w") as f:
            json.dump(record, f)
        lost = common.CARRY_LOST_SENTENCE.format(why=common.CARRY_REFUSALS["invalid"])
        code, out = run.command(words)
        self.assertEqual(block_of(out)["status"], "continue")
        self.assertNotIn(lost, out)
        self.assertEqual(run.applies[-1].carry["lost"], lost)
        code, out = run.command(next_words(out)[1:])
        self.assertNotEqual(block_of(out)["status"], "continue")
        self.assertEqual(out.split("```aleogr-result")[0].splitlines().count(lost), 1)

    def test_the_sentence_carried_must_be_one_of_the_fixed_ones(self):
        for why in common.CARRY_REFUSALS.values():
            c = self.valid(lost=common.CARRY_LOST_SENTENCE.format(why=why))
            self.assertEqual(skill._valid_carry(c), c)
        for v in ("An earlier part of this run could not be recalled: rm -rf.", "", 1, True):
            with self.subTest(value=v):
                self.assertIsNone(skill._valid_carry(self.valid(lost=v)))


class TestApiTriesAcrossCommands(unittest.TestCase):
    """M2: the ten tries of the wait for just-enabled APIs are the run's, and its sentence
    is said once."""

    REGISTRY = dict(rows=rows(apis=("missing: run.googleapis.com", "enable"),
                              registry=("missing", "create")))

    REFUSED = FakePlan(failure=PP.Failure("refused", "registry", "x"),
                       pending=[skill.item("registry", "x")])

    def first_command(self):
        # Sub-step 7's plan is refused after the enable: tries 1 to 3, and the clock ends
        # the third wait.
        ctx = FakeCtx(waits=[True, True, False])
        h = Harness([FakePlan(**self.REGISTRY), self.REFUSED],
                    {"gcp_services-enable": res("updated")}, ctx=ctx).run()
        self.assertEqual(h.block["status"], "continue")
        self.assertEqual(ctx.continued[0], skill.APIS_CONTINUE % (3, 10))
        return ctx.continued[1]

    def test_the_tries_go_on_from_the_carry(self):
        carry = self.first_command()
        self.assertEqual((carry["apisTries"], carry["apisPolled"]), (3, True))
        h = Harness([self.REFUSED], {}, carry=carry).run()
        self.assertEqual(len(h.plan_calls), 7)  # tries 4 to 10
        self.assertIn(skill.APIS_LIMIT, h.lines)

    def test_the_sentence_is_said_once(self):
        carry = self.first_command()
        later = FakePlan(rows=rows(registry=("missing", "create")))
        h = Harness([later, FakePlan()], {
            "gcp-artifact-registry_repository-create": [res("failed", answer=["x"]),
                                                        res("created")]},
            carry=carry).run()
        said = [l for l in h.lines if l.startswith("Waited for the APIs")]
        self.assertEqual(said, [skill.APIS_WAITED % ("aleogr:project-plan", 4)])
        # The poll of the run was used: the registry's failure is a stop, not a new poll.
        self.assertEqual(len(h.called("gcp-artifact-registry_repository-create")), 1)

    def test_a_sentence_of_an_earlier_command_is_in_the_last_answer(self):
        carry = skill.new_carry()
        carry.update(apisEnabled=True, apisPolled=True, changed=True,
                     apisAnswered=["gcp_ci-identity-setup", 3])
        h = Harness([FakePlan()], {}, carry=carry).run()
        self.assertEqual([l for l in h.lines if l.startswith("Waited")],
                         [skill.APIS_WAITED % ("gcp_ci-identity-setup", 3)])


class TestLineOfACutCommand(unittest.TestCase):
    """M4: a called command that made something and was then ended by a limit leaves its
    line, once."""

    PLAN = dict(rows=rows(services=("missing: web", "create"),
                          database=(PP.FOLLOWS_SERVICES, "none")))

    def test_its_status_then_unchanged(self):
        ctx = FakeCtx()
        h = Harness([FakePlan(**self.PLAN)], {"gcp_deploy-setup": res(
            "created", data={"waitRefused": True})}, ctx=ctx).run()
        carry = ctx.continued[1]
        self.assertEqual(carry["made"], ["gcp_deploy-setup: created"])
        h = Harness([FakePlan(**self.PLAN), FakePlan()],
                    {"gcp_deploy-setup": res("unchanged")}, carry=carry).run()
        self.assertEqual(h.lines.count("gcp_deploy-setup: created"), 1)
        self.assertNotIn("gcp_deploy-setup: unchanged", h.lines)

    def test_an_aborted_command_that_had_written(self):
        ctx = FakeCtx()
        h = Harness([FakePlan(**self.PLAN)], {"gcp_deploy-setup": aborted()}, ctx=ctx).run()
        carry = ctx.continued[1]
        self.assertEqual(carry["made"], ["gcp_deploy-setup: failed"])
        self.assertTrue(carry["cloudChanged"])
        h = Harness([FakePlan(**self.PLAN), FakePlan()],
                    {"gcp_deploy-setup": res("created")}, carry=carry).run()
        self.assertEqual([l for l in h.lines if l.startswith("gcp_deploy-setup")],
                         ["gcp_deploy-setup: created"])

    def test_an_aborted_command_that_had_written_nothing(self):
        ctx = FakeCtx()
        Harness([FakePlan(**self.PLAN)], {"gcp_deploy-setup": aborted(written=False)},
                ctx=ctx).run()
        self.assertEqual(ctx.continued[1]["made"], [])
        self.assertFalse(ctx.continued[1]["changed"])

    def test_its_line_has_the_name_of_its_line(self):
        plan = FakePlan(rows=rows(components=("to generate: web", "generate"),
                                  declaration=("changed here", "propose")),
                        generate=True)
        ctx = FakeCtx()
        Harness([plan], {"go_setup": res("created", data={"waitRefused": True})},
                ctx=ctx).run()
        self.assertEqual(ctx.continued[1]["made"], ["go_setup component=web: created"])


if __name__ == "__main__":
    unittest.main()
