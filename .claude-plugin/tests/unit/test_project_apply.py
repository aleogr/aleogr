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

    def __init__(self, step=True, waits=None, may_continue=True):
        self.step = step  # bool, or a list of answers, one per step_allowed()
        self.waits = waits  # None: every wait allowed; else a list of answers
        self.may = may_continue
        self.slept = 0
        self.abort = []
        self.continued = None

    def step_allowed(self):
        if isinstance(self.step, list):
            return self.step.pop(0) if self.step else True
        return self.step

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
        self.assertEqual(h.ctx.abort, [skill.START_SENTENCE])
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


class TestContinue(unittest.TestCase):
    PLAN = dict(rows=rows(ci_secrets=("missing: GCP_IMAGE_PATH", "set")))

    def test_step_limit_before_a_step(self):
        ctx = FakeCtx(step=False)
        h = Harness([FakePlan(**self.PLAN)], {}, ctx=ctx).run()
        self.assertEqual(h.calls, [])
        self.assertEqual(h.block["status"], "continue")
        self.assertEqual(ctx.continued[0], skill.CONTINUE_LINE % "the CI secrets")

    def test_step_limit_on_the_eighth_command(self):
        ctx = FakeCtx(step=False, may_continue=False)
        h = Harness([FakePlan(**self.PLAN)], {}, ctx=ctx).run()
        self.assertEqual(h.calls, [])
        self.assertIn(skill.COMMANDS_LIMIT % "the CI secrets", h.lines)
        self.assertEqual(h.block["pending"], [skill.item("run", skill.COMMANDS_LIMIT_HOW)])

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

    def test_carry_values_of_another_type_are_ignored(self):
        c = skill._valid_carry({"made": "x", "instanceTries": "3", "startedInstance": True,
                                "project": {"id": 5}})
        self.assertEqual((c["made"], c["instanceTries"], c["startedInstance"], c["project"]),
                         ([], 0, True, None))

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


if __name__ == "__main__":
    unittest.main()
