"""Unit tests of platform-apply: every gate before the call it gates (absent, another value,
and the gated call not made), the order of the steps, the stops, the GitHub secrets and
Login sections, the run in more than one command and the resumable creation of the
instance (every ending), and paths no scenario covers.

Apply is given a plan function that runs the real platform-plan (gather and decide) over
a fake cloud, and a call function that answers each step's invocation from the same fake
cloud (and changes it, as the step would) and records it; the context is a stand-in with
an injected step limit and count of commands. No command and no provider runs. The
scenarios platform-apply-* cover the rest in the direct mode.
"""

import copy
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "platform-apply")
PP = skill.PP

PID = "aleogr-shared-ab12"
SERVICES = ["cloudresourcemanager.googleapis.com", "billingbudgets.googleapis.com",
            "sqladmin.googleapis.com", "cloudscheduler.googleapis.com", "iam.googleapis.com",
            "iamcredentials.googleapis.com", "sts.googleapis.com"]
SECRETS = ["GitHub secrets", "", "GCP_SHARED_PROJECT_ID: %s" % PID,
           "GCP_SHARED_WIF_PROVIDER: projects/1/locations/global/workloadIdentityPools/github/"
           "providers/aleogr", "GCP_SHARED_SWITCH_ACCOUNT: a@%s.iam.gserviceaccount.com" % PID,
           "", "Paste them in the repository on GitHub: Settings, Secrets and variables, "
           "Actions, New repository secret."]
STEPS = ["1. Consent screen: open https://console.cloud.google.com/auth/branding?project=%s." % PID,
         "2. Client: open https://console.cloud.google.com/auth/clients?project=%s." % PID,
         "3. Paste this command in a bash terminal (Cloud Shell):",
         "( read -r -s -p \"Client secret: \" CSEC; gcloud iap settings set --billing-project=%s )"
         % PID,
         "4. Run /aleogr:platform-plan; its row login then reads prepared."]
LOGIN_ITEM = {"item": "login", "reason": "manual",
              "how": "In the Google Cloud console of %s, ..., then run /aleogr:platform-plan" % PID}
STOP_HOW = ("/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop projectId=%s "
            "instance=aleogr-shared" % PID)
CREATE_ARGS = {"projectId": PID, "instance": "aleogr-shared", "platform": "shared",
               "mode": "apply", "confirm": "yes", "version": "POSTGRES_18",
               "tier": "db-f1-micro", "edition": "enterprise", "region": "us-central1",
               "storageGb": "10", "backupStartUtc": "23:00", "retainedBackups": "7",
               "stopJob": "aleogr-shared-stop-weeknight"}


def res(status="unchanged", answer=(), pending=(), data=None, **outputs):
    r = {"status": status, "outputs": outputs, "answer": list(answer),
         "pending": list(pending)}
    if data is not None:
        r["data"] = data
    return r


class Cloud(object):
    """The fake shared platform: what the plan reads and what each step changes."""

    def __init__(self, **state):
        self.project = True
        self.billing = True
        self.services = True
        self.budget = True
        self.switch = True
        self.instance = "stopped"  # None (missing), creating, running, stopped, "unread"
        self.login = True
        for k, v in state.items():
            setattr(self, k, v)
        self.calls = []  # (skill, args) of the steps (not the plan's reads)
        self.reads = []  # the plan's invocations
        self.answers = {}  # skill -> result, or a list (one per call), overriding the cloud

    # -- the plan's reads --------------------------------------------------------
    def read(self, name, args):
        self.reads.append(name)
        if name == "gcp_environment-describe":
            if not self.project:
                return res(exists=False, projectId=None)
            return res(exists=True, projectId=PID, billingLinked=self.billing,
                       enabledServices=SERVICES if self.services else SERVICES[:1])
        if name == "gcp_login-describe":
            return res(prepared=self.login, readable=True)
        if name == "gcp_services-enable":
            if self.services:
                return res(projectId=PID, enabled=[], alreadyEnabled=SERVICES)
            return res("would-update", projectId=PID, enabled=SERVICES[1:],
                       alreadyEnabled=SERVICES[:1])
        if name == "gcp_budget-alert-setup":
            return res(compared=True) if self.budget else res("would-create")
        if name == "gcp-cloud-sql_instance-switch-setup":
            if self.switch:
                return res(answer=["| Part | State |", ""] + SECRETS, ready=True, missing=[],
                           lastRunFailed=[])
            return res("would-create", answer=["| Part | State |"], ready=False,
                       missing=["role"], lastRunFailed=[])
        if name == "gcp-cloud-sql_instance-describe":
            if self.instance == "unread":
                return res("failed", answer=["The instance aleogr-shared could not be read: "
                                             "gcloud failed."], exists=None)
            if self.instance is None:
                return res(exists=False, state=None)
            return res(exists=True, state=self.instance)
        raise AssertionError(name)

    # -- the steps -----------------------------------------------------------
    def step(self, name, args):
        self.calls.append((name, dict(args)))
        a = self.answers.get(name)
        if isinstance(a, list):
            a = a.pop(0) if len(a) > 1 else a[0]
        if callable(a):
            a = a(self, args)
        if a is not None:
            return copy.deepcopy(a)
        if name == "gcp_environment-create":
            if self.project:
                return res(projectId=PID)
            self.project = True
            return res("created", projectId=PID)
        if name == "gcp_services-enable":
            if self.services:
                return res()
            self.services = True
            return res("updated")
        if name == "gcp_budget-alert-setup":
            if self.budget:
                return res()
            self.budget = True
            return res("created")
        if name == "gcp-cloud-sql_instance-switch-setup":
            if self.switch:
                return res(answer=SECRETS, ready=True)
            self.switch = True
            return res("created", answer=["This run created: role."] + [""] + SECRETS,
                       ready=True)
        if name == "gcp-cloud-sql_instance-create":
            if self.instance is not None and args.get("resume") != "yes":
                return res(exists=True, state=self.instance)
            self.instance = "stopped"
            return res("created", answer=["Creating the instance takes several minutes.",
                                          "The Cloud SQL instance was created and is now "
                                          "stopped."], exists=True, state="stopped")
        if name == "gcp_login-setup":
            if self.login:
                return res(prepared=True)
            return res("updated", answer=["The login of the organization is not prepared."],
                       pending=[LOGIN_ITEM], prepared=False, roleGranted=True,
                       apiEnabled=True, steps=STEPS)
        raise AssertionError(name)


class Caller(object):
    def __init__(self, cloud):
        self.cloud = cloud

    def call(self, command, name, args):
        for v in args.values():
            assert isinstance(v, str), (name, args)
        assert "mode" not in args or args["mode"] == "plan", (name, args)
        return copy.deepcopy(self.cloud.read(name, args))

    def tools(self, command):
        class Check(object):
            ok = True
            tool = {"name": "gcloud", "command": "gcloud", "state": "ok", "fix": None}
        return Check()

    def defaults_path(self):
        return os.path.join(ROOT, "defaults.json")


class FakeCtx(object):
    """The parts of a Context that platform-apply uses, with the limits injected."""

    def __init__(self, step=True, may_continue=True):
        self.plugin = "aleogr"
        self.step = step  # bool, or a list of answers, one per step_allowed()
        self.steps_begun = 0
        self.may = may_continue
        self.abort = []
        self.aborts = []  # every registration, in order
        self.continued = None

    def step_allowed(self):
        if isinstance(self.step, list):
            ok = self.step.pop(0) if self.step else True
        else:
            ok = self.step
        if self.steps_begun == 0 or ok:
            self.steps_begun += 1
            return True
        return False

    def may_continue(self):
        return self.may

    def continue_run(self, line, carry, cost=None, **kw):
        self.continued = (line, copy.deepcopy(carry))
        return self.result("continue", {}, lines=[line, "next: ..."], cost=cost)

    def on_abort(self, lines):
        self.abort = list(lines)
        self.aborts.append(list(lines))

    def plugin_path(self, *parts):
        return os.path.join(ROOT, *parts)

    def result(self, status, outputs, resources=(), pending=(), cost=None, lines=(), **kw):
        block = common.result_block(skill.FAMILY, skill.PROVIDER, skill.ACTION, status,
                                    outputs, mode="apply", resources=resources,
                                    pending=pending, cost=cost)
        return common.Result(block, lines)


class Run(object):
    """One command of platform-apply over the fake cloud."""

    def __init__(self, cloud, args=None, ctx=None, carry=None, lost=None):
        self.cloud = cloud
        self.ctx = ctx or FakeCtx()
        self.args = {"confirm": "yes"} if args is None else args
        self.carry = carry if carry is not None else skill.new_carry()
        self.plans = []
        self.lost = lost

    def plan(self, a):
        self.plans.append(dict(a))
        return PP.decide(PP.gather(a, Caller(self.cloud), "/aleogr:platform-apply confirm=yes",
                                   PP.PLAN_VALUES + PP.APPLY_VALUES))

    def call(self, command, name, a):
        expected = skill.DB if name.startswith("gcp-cloud-sql_") else skill.CLOUD
        assert command == expected, (command, name)
        return self.cloud.step(name, a)

    def go(self):
        self.apply = skill.Apply(self.args, self.ctx, self.carry, plan_fn=self.plan,
                                 call_fn=self.call, lost=self.lost)
        r = self.apply.run()
        self.result, self.block, self.lines = r, r.block, list(r.lines)
        self.text = "\n".join(self.lines)
        return self


def run(cloud, **kw):
    return Run(cloud, **kw).go()


def names(cloud):
    return [c[0] for c in cloud.calls]


def until_done(cloud, ctx_factory=lambda: FakeCtx(), limit=8):
    """Run commands as the shell does while the answer says continue; the carry passes
    through JSON, as the file does."""
    carry = None
    runs = []
    for n in range(1, limit + 1):
        ctx = ctx_factory()
        if n == limit:
            ctx.may = False
        h = run(cloud, ctx=ctx, carry=copy.deepcopy(carry))
        runs.append(h)
        if h.block["status"] != "continue":
            return runs
        carry = json.loads(json.dumps(h.ctx.continued[1]))
        assert skill._valid_carry(carry) == carry
    return runs


class TestDeclarations(unittest.TestCase):
    def test_module(self):
        self.assertTrue(skill.CONTINUES)
        self.assertFalse(skill.WRITES)
        self.assertEqual((skill.DEFAULT_MODE, skill.RESULT_MODE), ("apply", "apply"))

    def test_no_own_runner(self):
        with open(skill.__file__, encoding="utf-8") as f:
            text = f.read()
        for word in ("ctx.write", "ctx.read", "ctx.run(", "subprocess", "write_file",
                     "call_plugin("):
            self.assertNotIn(word, text)

    def test_arguments(self):
        self.assertIsNone(skill.validate_args({}))
        self.assertIsNone(skill.validate_args({"confirm": "yes"}))
        self.assertEqual(skill.validate_args({"confirm": "no"}), skill.CONFIRM_INVALID)
        self.assertEqual(skill.validate_args({"confirm": "YES"}), skill.CONFIRM_INVALID)
        self.assertEqual(skill.validate_args({"mode": "apply"}),
                         skill.ARGUMENT_UNKNOWN % "mode")


class TestConfirmGate(unittest.TestCase):
    def test_absent(self):
        cloud = Cloud(project=False)
        h = run(cloud, args={})
        self.assertEqual(cloud.calls, [])
        self.assertEqual(h.block["status"], "pending")
        self.assertEqual(h.block["pending"], [{"item": "confirm", "reason": "manual",
                                               "how": "/aleogr:platform-apply confirm=yes"}])
        self.assertIn(skill.COST_LINE, h.lines)
        self.assertIn(skill.LOGIN_SENTENCE, h.lines)
        self.assertEqual(h.lines.count(skill.COST_LINE), 1)
        self.assertFalse(any(l.rstrip().endswith("?") for l in h.lines))
        self.assertEqual(len(h.plans), 1)

    def test_another_value_never_reaches_a_step(self):
        for value in ("no", "true", "YES", ""):
            with self.subTest(value=value):
                class Ctx(FakeCtx):
                    def carried(self, digest):
                        return None
                    carry_refusal = None

                    def carry_lost_sentence(self):
                        return None
                cloud = Cloud(project=False)
                ctx = Ctx()
                r = skill.run({"confirm": value}, ctx)
                self.assertEqual(r.block["status"], "failed")
                self.assertEqual(r.lines, [skill.CONFIRM_INVALID])
                self.assertEqual(cloud.calls, [])

    def test_absent_with_only_the_instance(self):
        cloud = Cloud(instance=None)
        h = run(cloud, args={})
        self.assertEqual(cloud.calls, [])
        self.assertIn(skill.COST_LINE, h.lines)
        self.assertNotIn(skill.LOGIN_SENTENCE, h.lines)

    def test_nothing_to_do_needs_no_confirm(self):
        cloud = Cloud()
        h = run(cloud, args={})
        self.assertEqual(h.block["status"], "unchanged")
        self.assertIn("nothing to do", h.lines)
        self.assertEqual(cloud.calls, [])


class TestSteps(unittest.TestCase):
    def test_everything_in_order_then_the_last_plan(self):
        cloud = Cloud(project=False, services=False, budget=False, switch=False,
                      instance=None, login=False)
        h = run(cloud)
        self.assertEqual(names(cloud), list(skill.SKILLS))
        self.assertEqual(len(h.plans), 2)
        self.assertEqual(h.plans[1], {"projectId": PID})
        args = dict(cloud.calls)
        self.assertEqual(args["gcp_environment-create"],
                         {"project": "shared", "platform": "shared", "mode": "apply"})
        self.assertEqual(args["gcp_services-enable"]["projectId"], PID)
        self.assertEqual(args["gcp_budget-alert-setup"]["quotaProject"], PID)
        self.assertEqual(args["gcp-cloud-sql_instance-create"], CREATE_ARGS)
        # In the SKILL.md's order (step 4.5), as the command line passes them.
        self.assertEqual(list(args["gcp-cloud-sql_instance-create"]), [
            "projectId", "instance", "platform", "mode", "confirm", "version", "tier",
            "edition", "region", "storageGb", "backupStartUtc", "retainedBackups", "stopJob"])
        self.assertEqual(list(args["gcp-cloud-sql_instance-switch-setup"]), [
            "projectId", "instance", "region", "timeZone", "weeknightStop", "weekendStop",
            "repository", "mode"])
        self.assertEqual(args["gcp_login-setup"], {"projectId": PID, "mode": "apply"})
        self.assertEqual(h.block["status"], "created")
        self.assertEqual(h.lines[:6], ["%s: %s" % (n, s) for n, s in (
            ("gcp_environment-create", "created"), ("gcp_services-enable", "updated"),
            ("gcp_budget-alert-setup", "created"), ("gcp-cloud-sql_instance-switch-setup",
                                                    "created"),
            ("gcp-cloud-sql_instance-create", "created"), ("gcp_login-setup", "updated"))])
        self.assertEqual(h.block["pending"], [LOGIN_ITEM])
        self.assertNotIn("nothing to do", h.lines)
        self.assertEqual(h.block["cost"], skill.INSTANCE_COST)
        self.assertEqual(h.block["outputs"]["projectId"], PID)

    def test_steps_marked_none_are_skipped(self):
        cloud = Cloud(budget=False)
        h = run(cloud)
        self.assertEqual(names(cloud), ["gcp_budget-alert-setup"])
        self.assertEqual(h.block["status"], "updated")  # only the budget: updated
        self.assertIn("nothing to do", h.lines)
        self.assertEqual(h.block["cost"], skill.INSTANCE_COST)

    def test_the_switch_comes_before_the_instance(self):
        cloud = Cloud(switch=False, instance=None)
        run(cloud)
        self.assertEqual(names(cloud), ["gcp-cloud-sql_instance-switch-setup",
                                        "gcp-cloud-sql_instance-create"])

    def test_a_pending_switch_stops_before_the_instance(self):
        cloud = Cloud(switch=False, instance=None)
        how = {"item": "job-weeknight", "reason": "manual", "how": "/x again"}
        cloud.answers["gcp-cloud-sql_instance-switch-setup"] = res(
            "pending", answer=["The part job-weeknight could not be created."],
            pending=[how, dict(how, item="job-weekend")], ready=False)
        h = run(cloud)
        self.assertEqual(names(cloud), ["gcp-cloud-sql_instance-switch-setup"])
        self.assertEqual(h.block["status"], "pending")
        items = dict((x["item"], x["action"]) for x in h.block["outputs"]["items"])
        self.assertEqual(items["database switch"], "blocked")
        self.assertEqual(items["database instance"], "create")
        self.assertEqual(len(h.block["pending"]), 2)
        self.assertEqual(h.lines.count("/x again"), 1)
        self.assertEqual(len(h.plans), 1)  # no last plan after a stop
        self.assertNotIn("GitHub secrets", h.lines)

    def test_a_failed_step_stops_with_its_sentence(self):
        cloud = Cloud(services=False, budget=False)
        cloud.answers["gcp_services-enable"] = res("failed", answer=["It could not."])
        h = run(cloud)
        self.assertEqual(names(cloud), ["gcp_services-enable"])
        self.assertEqual(h.block["status"], "failed")
        self.assertIn("It could not.", h.lines)
        self.assertEqual(h.block["pending"][0]["item"], "services")
        self.assertIn("then run /aleogr:platform-apply confirm=yes",
                      h.block["pending"][0]["how"])

    def test_a_failed_plan(self):
        cloud = Cloud(instance="unread")
        h = run(cloud)
        self.assertEqual(cloud.calls, [])
        self.assertEqual(h.block["status"], "failed")
        self.assertIn("/aleogr:platform-apply confirm=yes", h.block["pending"][0]["how"])

    def test_project_created_but_billing_refused(self):
        cloud = Cloud(project=False)
        cloud.answers["gcp_environment-create"] = res(
            "pending", answer=["The project was created, but its billing could not be linked."],
            pending=[{"item": "billing", "reason": "manual", "how": "gcloud billing ..."}],
            projectId=PID)
        h = run(cloud)
        self.assertEqual(names(cloud), ["gcp_environment-create"])
        self.assertEqual(h.block["status"], "pending")
        self.assertEqual(h.block["outputs"]["projectId"], PID)
        self.assertEqual(h.block["resources"][0]["id"], PID)

    def test_the_create_id_is_used_not_the_label_search(self):
        cloud = Cloud(project=False, services=False)

        def created(c, a):
            return res("created", projectId=PID)  # the label search still does not see it
        cloud.answers["gcp_environment-create"] = created
        h = run(cloud)
        self.assertEqual(dict(cloud.calls)["gcp_services-enable"]["projectId"], PID)
        self.assertEqual(h.plans[-1], {"projectId": PID})

    def test_no_project_id_when_a_step_is_due(self):
        cloud = Cloud(project=False)
        cloud.answers["gcp_environment-create"] = res("created", projectId=None)
        h = run(cloud)
        self.assertEqual(names(cloud), ["gcp_environment-create"])
        self.assertEqual(h.block["status"], "failed")


class TestSections(unittest.TestCase):
    def test_github_secrets_when_the_switch_is_ready(self):
        h = run(Cloud(budget=False))
        start = h.lines.index("GitHub secrets")
        self.assertEqual(h.lines[start:start + len(SECRETS)], SECRETS)
        self.assertEqual(h.lines[start + len(SECRETS) + 1], skill.SECRETS_ONCE)
        self.assertNotIn("GCP_SHARED", json.dumps(h.block))

    def test_no_secrets_when_the_switch_is_not_ready(self):
        h = run(Cloud(services=False, switch=False), args={})
        self.assertNotIn("GitHub secrets", h.lines)

    def test_login_section_exactly_the_list(self):
        h = run(Cloud(login=False))
        start = h.lines.index("Login")
        self.assertEqual(h.lines[start:start + 8], ["Login", ""] + STEPS[:3] + [
            "```bash", STEPS[3], "```"])
        self.assertEqual(h.lines[start + 8], STEPS[4])
        self.assertNotIn(skill.LOGIN_PLAN_LINE, h.lines)  # its last line says it already
        self.assertEqual(h.block["status"], "updated")
        self.assertEqual(h.block["pending"], [LOGIN_ITEM])
        block = json.dumps(h.block)
        self.assertNotIn("console.cloud.google.com", block)
        self.assertNotIn("read -r", block)
        self.assertEqual(h.text.count("read -r -s -p"), 1)

    def test_login_plan_line_when_the_list_does_not_say_it(self):
        cloud = Cloud(login=False)
        cloud.answers["gcp_login-setup"] = res("pending", pending=[LOGIN_ITEM], prepared=False,
                                               steps=STEPS[:4])
        h = run(cloud)
        self.assertIn(skill.LOGIN_PLAN_LINE, h.lines)
        self.assertEqual(h.block["status"], "pending")  # nothing at all was changed

    def test_login_failed_stops(self):
        cloud = Cloud(login=False)
        cloud.answers["gcp_login-setup"] = res("failed", answer=["The role could not be granted."])
        h = run(cloud)
        self.assertEqual(h.block["status"], "failed")
        self.assertIn("The role could not be granted.", h.lines)
        self.assertNotIn("Login", h.lines)

    def test_login_would_update_is_failed(self):
        cloud = Cloud(login=False)
        cloud.answers["gcp_login-setup"] = res("would-update")
        h = run(cloud)
        self.assertEqual(h.block["status"], "failed")

    def test_login_unchanged_keeps_nothing(self):
        cloud = Cloud(login=False)

        def prepared(c, a):
            c.login = True
            return res(prepared=True)
        cloud.answers["gcp_login-setup"] = prepared
        h = run(cloud)
        self.assertEqual(h.block["status"], "unchanged")
        self.assertIn("nothing to do", h.lines)
        self.assertEqual(h.block["pending"], [])

    def test_no_secret_value_is_ever_built(self):
        with open(skill.__file__, encoding="utf-8") as f:
            text = f.read()
        for word in ("clientSecret", "CSEC", "client_secret"):
            self.assertNotIn(word, text)


class TestContinue(unittest.TestCase):
    def test_step_limit_before_each_step_after_the_first(self):
        cloud = Cloud(services=False, budget=False)
        h = run(cloud, ctx=FakeCtx(step=False))
        self.assertEqual(names(cloud), ["gcp_services-enable"])
        self.assertEqual(h.block["status"], "continue")
        self.assertEqual(h.ctx.continued[0],
                         skill.CONTINUE_LINE % "gcp_budget-alert-setup")
        carry = h.ctx.continued[1]
        self.assertEqual(carry["made"], ["gcp_services-enable: updated"])
        self.assertTrue(carry["changed"])

    def test_a_continuation_plans_again_and_ends_as_one_command(self):
        one = run(Cloud(project=False, services=False, budget=False, switch=False,
                        instance=None, login=False))
        cloud = Cloud(project=False, services=False, budget=False, switch=False,
                      instance=None, login=False)
        runs = until_done(cloud, lambda: FakeCtx(step=False))
        self.assertGreater(len(runs), 2)
        last = runs[-1]
        self.assertEqual(last.lines, one.lines)
        self.assertEqual(last.block, one.block)
        self.assertEqual(names(cloud), list(skill.SKILLS))  # nothing made twice

    def test_login_is_not_run_again(self):
        cloud = Cloud(login=False)
        runs = until_done(cloud, lambda: FakeCtx(step=False))
        self.assertEqual(names(cloud), ["gcp_login-setup"])
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[-1].block["pending"], [LOGIN_ITEM])
        self.assertIn("Login", runs[-1].lines)

    def test_login_prepared_in_between_drops_its_items(self):
        cloud = Cloud(login=False)
        first = run(cloud, ctx=FakeCtx(step=False))
        carry = json.loads(json.dumps(first.ctx.continued[1]))
        cloud.login = True  # the owner's clicks, between the commands
        h = run(cloud, carry=carry)
        self.assertEqual(h.block["pending"], [])
        self.assertNotIn("Login", h.lines)
        self.assertIn("nothing to do", h.lines)
        self.assertEqual(h.block["status"], "updated")

    def test_a_called_command_ended_by_a_limit(self):
        cloud = Cloud(switch=False)
        cloud.answers["gcp-cloud-sql_instance-switch-setup"] = [
            res("pending", pending=[{"item": "run", "reason": "manual", "how": "x"}],
                data={"waitRefused": True}, ready=False), None]
        h = run(cloud)
        self.assertEqual(h.block["status"], "continue")
        self.assertEqual(h.ctx.continued[1]["made"], [])  # it changed nothing
        h = run(cloud, carry=h.ctx.continued[1])
        self.assertEqual(h.block["status"], "created")
        self.assertEqual(names(cloud), ["gcp-cloud-sql_instance-switch-setup"] * 2)

    def test_the_eighth_command_ends_pending(self):
        cloud = Cloud(services=False, budget=False)
        h = run(cloud, ctx=FakeCtx(step=False, may_continue=False))
        self.assertEqual(h.block["status"], "pending")
        self.assertIn(skill.COMMANDS_LIMIT % "gcp_budget-alert-setup", h.lines)
        self.assertEqual(h.block["pending"][0]["item"], "run")

    def test_carry_validation(self):
        good = skill.new_carry()
        self.assertEqual(skill._valid_carry(good), good)
        for bad in ({"made": ["x: created"]}, {"made": ["gcp_login-setup: maybe"]},
                    {"projectId": "Not An Id"}, {"changed": 1}, {"instanceDone": True},
                    {"login": {"status": "updated", "steps": ["a\nb"], "pending": [LOGIN_ITEM]}},
                    {"login": {"status": "unchanged", "steps": [], "pending": [LOGIN_ITEM]}},
                    {"extra": True}):
            with self.subTest(bad=bad):
                c = dict(good)
                c.update(bad)
                self.assertIsNone(skill._valid_carry(c))


class TestInstance(unittest.TestCase):
    """The creation of the instance: its cost said before it, the switch before it, and
    resumable across commands."""

    def cut(self, state="creating"):
        """A create whose wait the clock ended, the instance still `state`."""
        def answer(c, a):
            c.instance = state
            return res("pending", answer=[
                "Creating the instance takes several minutes.",
                "The instance aleogr-shared was created, but it was still %s when this run "
                "stopped waiting for it, so it was not stopped." % state,
                "It is not stopped: it runs and is charged by the hour until it is stopped. "
                "Stop it with %s." % STOP_HOW, "The night stop was not tested."],
                pending=[{"item": "instance", "reason": "manual", "how": STOP_HOW}],
                data={"waitRefused": True}, exists=True, state=state)
        return answer

    def test_cost_line_before_the_create(self):
        cloud = Cloud(instance=None)
        h = run(cloud)
        self.assertIn(skill.COST_LINE, h.lines)
        self.assertEqual(h.block["status"], "created")
        self.assertEqual(h.block["cost"], skill.INSTANCE_COST)

    def test_on_abort_from_the_moment_the_create_is_asked(self):
        cloud = Cloud(instance=None)
        seen = []

        def create(c, a):
            seen.append(list(h.ctx.abort))
            c.instance = "stopped"
            return res("created", exists=True, state="stopped")
        cloud.answers["gcp-cloud-sql_instance-create"] = create
        h = Run(cloud)
        h.go()
        sentence = skill.INSTANCE_MAY_RUN % ("aleogr-shared", PID, "aleogr-shared")
        self.assertEqual(seen, [[sentence]])
        self.assertNotIn(sentence, h.ctx.abort)  # its outcome is known

    def test_cut_by_the_clock_then_resumed(self):
        cloud = Cloud(instance=None)
        cloud.answers["gcp-cloud-sql_instance-create"] = [self.cut(), None]
        first = run(cloud)
        self.assertEqual(first.block["status"], "continue")
        self.assertEqual(first.ctx.continued[0], skill.INSTANCE_CONTINUE % "creating")
        carry = json.loads(json.dumps(first.ctx.continued[1]))
        self.assertTrue(carry["createAsked"])
        self.assertFalse(carry["instanceDone"])
        self.assertIn(skill.INSTANCE_MAY_RUN % ("aleogr-shared", PID, "aleogr-shared"),
                      first.ctx.abort)
        h = run(cloud, carry=carry)
        self.assertEqual([a.get("resume") for _n, a in cloud.calls], [None, "yes"])
        self.assertEqual(cloud.calls[1][1], dict(CREATE_ARGS, resume="yes"))
        self.assertEqual(h.block["status"], "created")
        one = run(Cloud(instance=None))
        self.assertEqual(h.lines, one.lines)
        self.assertEqual(h.block, one.block)

    def test_resumed_for_each_state_but_stopped(self):
        for state in ("creating", "running", "starting"):
            with self.subTest(state=state):
                cloud = Cloud(instance=None)
                cloud.answers["gcp-cloud-sql_instance-create"] = [self.cut(state), None]
                carry = run(cloud).ctx.continued[1]
                run(cloud, carry=carry)
                self.assertEqual(cloud.calls[-1][1].get("resume"), "yes")

    def test_found_stopped_by_the_next_command(self):
        cloud = Cloud(instance=None)

        def cut_after_stop(c, a):
            c.instance = "stopped"
            return res("failed", answer=[common.TIME_LIMIT_SENTENCE],
                       data={"timeLimit": True}, exists=None)
        cloud.answers["gcp-cloud-sql_instance-create"] = cut_after_stop
        carry = run(cloud).ctx.continued[1]
        h = run(cloud, carry=carry)
        self.assertEqual(names(cloud), ["gcp-cloud-sql_instance-create"])  # not again
        self.assertEqual(h.block["status"], "created")
        self.assertIn(skill.NIGHT_STOP_UNKNOWN, h.lines)
        self.assertIn("gcp-cloud-sql_instance-create: created", h.lines)

    def test_found_missing_is_not_created_again(self):
        cloud = Cloud(instance=None)

        def vanished(c, a):
            c.instance = None
            return res("pending", data={"waitRefused": True}, exists=True, state="creating")
        cloud.answers["gcp-cloud-sql_instance-create"] = vanished
        carry = run(cloud).ctx.continued[1]
        h = run(cloud, carry=carry)
        self.assertEqual(names(cloud), ["gcp-cloud-sql_instance-create"])
        self.assertEqual(h.block["status"], "pending")
        self.assertIn(skill.INSTANCE_GONE % "aleogr-shared", h.lines)

    def test_found_unreadable_says_it_may_run(self):
        cloud = Cloud(instance=None)
        cloud.answers["gcp-cloud-sql_instance-create"] = self.cut()
        carry = run(cloud).ctx.continued[1]
        cloud.instance = "unread"
        h = run(cloud, carry=carry)
        self.assertEqual(names(cloud), ["gcp-cloud-sql_instance-create"])
        self.assertEqual(h.block["status"], "failed")
        self.assertIn(skill.INSTANCE_MAY_RUN % ("aleogr-shared", PID, "aleogr-shared"),
                      h.lines)
        self.assertEqual(h.block["cost"], skill.INSTANCE_COST)

    def test_eight_commands_while_it_is_still_being_created(self):
        cloud = Cloud(instance=None)
        cloud.answers["gcp-cloud-sql_instance-create"] = self.cut()
        runs = until_done(cloud)
        self.assertEqual(len(runs), 8)
        last = runs[-1]
        self.assertEqual(last.block["status"], "pending")
        self.assertEqual(names(cloud), ["gcp-cloud-sql_instance-create"] * 8)
        self.assertEqual([a.get("resume") for _n, a in cloud.calls], [None] + ["yes"] * 7)
        self.assertIn(STOP_HOW, last.lines)
        self.assertTrue(any("charged by the hour" in l for l in last.lines))
        self.assertIn(skill.COST_LINE, last.lines)
        self.assertEqual(last.block["cost"], skill.INSTANCE_COST)
        self.assertEqual(last.block["pending"],
                         [{"item": "instance", "reason": "manual", "how": STOP_HOW}])
        items = dict((x["item"], x["action"]) for x in last.block["outputs"]["items"])
        self.assertEqual(items["database instance"], "blocked")

    def test_carry_lost_never_resumes(self):
        cloud = Cloud(instance="creating")
        lost = common.CARRY_LOST_SENTENCE.format(why=common.CARRY_REFUSALS["missing"])
        h = run(cloud, lost=lost)
        self.assertEqual(cloud.calls, [])
        self.assertIn(lost, h.lines)
        self.assertIn(PP.RUNNING_LINE % (PID, "aleogr-shared"), h.lines)
        self.assertEqual(h.block["cost"], skill.INSTANCE_COST)
        self.assertEqual(h.block["status"], "unchanged")

    def test_after_its_outcome_never_resumed(self):
        cloud = Cloud(instance=None, login=False)
        first = run(cloud, ctx=FakeCtx(step=[True, False]))  # the create, then the limit
        carry = first.ctx.continued[1]
        self.assertTrue(carry["instanceDone"])
        cloud.instance = "running"  # started by someone else in between
        run(cloud, carry=carry)
        self.assertEqual([a.get("resume") for n, a in cloud.calls
                          if n == "gcp-cloud-sql_instance-create"], [None])

    def test_a_pending_create_stops_with_its_lines(self):
        cloud = Cloud(instance=None)
        cloud.answers["gcp-cloud-sql_instance-create"] = res(
            "pending", answer=["Creating the instance takes several minutes.",
                               "The night-stop job did NOT stop the instance aleogr-shared.",
                               "It costs about R$ 50 per month while stopped."],
            pending=[{"item": "night stop", "reason": "manual", "how": "send this output"}],
            exists=True, state="stopped")
        h = run(cloud)
        self.assertEqual(h.block["status"], "pending")
        self.assertIn("The night-stop job did NOT stop the instance aleogr-shared.", h.lines)
        self.assertNotIn("Creating the instance takes several minutes.", h.lines)
        self.assertEqual(h.block["pending"][0]["item"], "night stop")


if __name__ == "__main__":
    unittest.main()
