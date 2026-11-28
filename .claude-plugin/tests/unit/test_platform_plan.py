"""Unit tests of platform-plan: each item's states and actions, the steps a prerequisite
skips, the steps that stop the plan, the lines under the table, the status, and that the
plan only reads (the read-only runner and `--read-only` calls only).

gather() is given a Caller that answers each invocation from canned result objects and
records it, and a tools-check that is ok; no command runs. The scenarios platform-plan-*
cover the rest in the direct mode.
"""

import copy
import os
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402
from helpers import called_commands, run_with_other_suite  # noqa: E402

PLUGIN = "aleogr"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "platform-plan")

PID = "aleogr-shared-ab12"
SERVICES = ["cloudresourcemanager.googleapis.com", "billingbudgets.googleapis.com",
            "sqladmin.googleapis.com", "cloudscheduler.googleapis.com", "iam.googleapis.com",
            "iamcredentials.googleapis.com", "sts.googleapis.com"]
SECRETS = ["", "GitHub secrets", "", "GCP_SHARED_PROJECT_ID: %s" % PID,
           "GCP_SHARED_WIF_PROVIDER: projects/1/locations/global/workloadIdentityPools/github/"
           "providers/aleogr", "GCP_SHARED_SWITCH_ACCOUNT: a@%s.iam.gserviceaccount.com" % PID,
           "", "Paste them in the repository on GitHub: Settings, Secrets and variables, "
           "Actions, New repository secret."]


def res(status="unchanged", answer=(), pending=(), **outputs):
    return {"status": status, "outputs": outputs, "answer": list(answer),
            "pending": list(pending)}


EXISTS = res(exists=True, projectId=PID, billingLinked=True, enabledServices=SERVICES)
MISSING = res(exists=False, projectId=None)
ALL_ENABLED = res(projectId=PID, enabled=[], alreadyEnabled=SERVICES)
SWITCH_READY = res(answer=["| Part | State |", "This plan changed nothing."] + SECRETS,
                   ready=True, missing=[], lastRunFailed=[])
STOPPED = res(exists=True, state="stopped")
PREPARED = res(prepared=True, readable=True, organization=True)


def answers(**over):
    a = {"gcp_environment-describe": EXISTS, "gcp_login-describe": PREPARED,
         "gcp_services-enable": ALL_ENABLED,
         "gcp_budget-alert-setup": res(compared=True),
         "gcp-cloud-sql_instance-switch-setup": SWITCH_READY,
         "gcp-cloud-sql_instance-describe": STOPPED}
    a.update(over)
    return a


class FakeCheck(object):
    def __init__(self, state="ok"):
        self.tool = {"name": "gcloud", "command": "gcloud", "state": state,
                     "fix": None if state == "ok" else "gcloud auth login"}

    @property
    def ok(self):
        return self.tool["state"] == "ok"


class FakeCaller(object):
    def __init__(self, answers, tool="ok", defaults=None):
        self.answers = answers
        self.calls = []
        self.tool = tool
        self.path = defaults or os.path.join(ROOT, "defaults.json")

    def call(self, command, name, args):
        for v in args.values():
            assert isinstance(v, str), (name, args)
        self.calls.append((command, name, dict(args)))
        return copy.deepcopy(self.answers[name])

    def suites(self, commands):
        self.suites_asked = list(commands)  # the versions, before the first read

    def tools(self, command):
        self.calls.append(("tools-check", command, {}))
        return FakeCheck(self.tool)

    def defaults_path(self):
        return self.path


def plan(args=None, **kw):
    caller = FakeCaller(answers(**{k: v for k, v in kw.items() if k not in ("tool",)}),
                        tool=kw.get("tool", "ok"))
    p = skill.decide(skill.gather(args or {}, caller))
    return p, caller


def names(caller):
    return [c[1] for c in caller.calls]


def rows(p):
    return dict((i, (s, a)) for i, s, a in p.items)


class TestOrderAndArguments(unittest.TestCase):
    def test_the_steps_in_order(self):
        p, c = plan()
        self.assertEqual(names(c), ["gcloud", "gcp_environment-describe", "gcp_login-describe",
                                    "gcp_services-enable", "gcp_budget-alert-setup",
                                    "gcp-cloud-sql_instance-switch-setup",
                                    "gcp-cloud-sql_instance-describe"])
        self.assertEqual([i for i, _s, _a in p.items], list(skill.ITEMS))
        self.assertEqual(p.status, "unchanged")
        self.assertEqual(skill.last_line(p), "nothing to do")
        args = dict((n, a) for _c, n, a in c.calls)
        self.assertEqual(args["gcp_environment-describe"],
                         {"project": "shared", "platform": "shared"})
        self.assertEqual(args["gcp_services-enable"],
                         {"projectId": PID, "services": ",".join(SERVICES), "mode": "plan"})
        self.assertEqual(args["gcp_budget-alert-setup"],
                         {"displayName": "aleogr", "amount": "100", "currency": "BRL",
                          "thresholds": "0.5,0.9,1.0", "quotaProject": PID, "mode": "plan"})
        self.assertEqual(args["gcp-cloud-sql_instance-switch-setup"],
                         {"projectId": PID, "instance": "aleogr-shared", "region": "us-central1",
                          "timeZone": "America/Sao_Paulo", "weeknightStop": "30 22 * * 0-4",
                          "weekendStop": "0 4 * * 6,0", "repository": "aleogr/aleogr",
                          "mode": "plan"})
        self.assertEqual(args["gcp-cloud-sql_instance-describe"],
                         {"projectId": PID, "instance": "aleogr-shared"})
        self.assertEqual(args["gcp_login-describe"], {"projectId": PID})

    def test_project_id_given(self):
        p, c = plan({"projectId": PID})
        self.assertEqual(c.calls[1][2], {"projectId": PID})

    def test_arguments_checked_before_any_command(self):
        for args in ({"projectId": "Bad_Id"}, {"projectId": "ab-"}, {"projectId": "a1234"},
                     {"other": "x"}):
            with self.subTest(args=args):
                p, c = plan(args)
                self.assertEqual(p.status, "failed")
                self.assertEqual(c.calls, [])
                self.assertEqual(p.items, [])

    def test_provider_not_gcp_runs_nothing(self):
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "defaults.json")
        with open(path, "w") as f:
            f.write('{"cloud": {"provider": "aws"}}')
        caller = FakeCaller(answers(), defaults=path)
        p = skill.decide(skill.gather({}, caller))
        self.assertEqual((p.status, caller.calls), ("failed", []))
        self.assertEqual(skill.answer_lines(p), [skill.ONLY_GCP])
        os.remove(path)
        os.rmdir(folder)

    def test_tools_check_failed(self):
        p, c = plan(tool="not-authenticated")
        self.assertEqual(names(c), ["gcloud"])
        self.assertEqual(p.status, "failed")
        self.assertEqual(p.pending, [{"item": "gcloud", "reason": "manual",
                                      "how": "gcloud auth login"}])


class TestItems(unittest.TestCase):
    def test_project_missing(self):
        p, c = plan(**{"gcp_environment-describe": MISSING})
        self.assertEqual(names(c), ["gcloud", "gcp_environment-describe"])
        self.assertEqual(p.status, "would-create")
        r = rows(p)
        self.assertEqual(r["shared project"], ("missing", "create"))
        for name in ("services", "budget alert", "database switch", "database instance"):
            self.assertEqual(r[name], (skill.NOT_CHECKED_PROJECT, "create"))
        self.assertEqual(r["login"], (skill.NOT_CHECKED_PROJECT, "prepare"))
        self.assertEqual((p.outputs["projectId"], p.resources), (None, []))
        self.assertIn(skill.COST_LINE, skill.lines_under(p))

    def test_billing_not_linked_skips_the_budget(self):
        env = res(exists=True, projectId=PID, billingLinked=False, enabledServices=SERVICES)
        p, c = plan(**{"gcp_environment-describe": env})
        self.assertNotIn("gcp_budget-alert-setup", names(c))
        r = rows(p)
        self.assertEqual(r["shared project"], ("billing not linked", "update"))
        self.assertEqual(r["budget alert"], (skill.NOT_CHECKED_SERVICES, "create"))
        self.assertEqual(p.status, "would-update")

    def test_budget_api_not_enabled_skips_budget_switch_and_instance(self):
        svc = res("would-update", projectId=PID, enabled=["billingbudgets.googleapis.com"],
                  alreadyEnabled=SERVICES[:1])
        p, c = plan(**{"gcp_services-enable": svc})
        self.assertEqual(names(c)[-1], "gcp_services-enable")
        r = rows(p)
        self.assertEqual(r["services"], ("missing: billingbudgets.googleapis.com", "update"))
        self.assertEqual(r["budget alert"], (skill.NOT_CHECKED_SERVICES, "create"))
        self.assertEqual(r["database switch"], (skill.NOT_CHECKED_SERVICES, "create"))
        self.assertEqual(r["database instance"], (skill.NOT_CHECKED_SERVICES, "create"))

    def test_budget_checked_when_its_api_is_enabled_but_another_is_not(self):
        svc = res("would-update", projectId=PID, enabled=["sts.googleapis.com"],
                  alreadyEnabled=SERVICES[:-1])
        p, c = plan(**{"gcp_services-enable": svc})
        self.assertIn("gcp_budget-alert-setup", names(c))
        self.assertNotIn("gcp-cloud-sql_instance-switch-setup", names(c))

    def test_budget_states(self):
        cases = ((res("would-create"), ("missing", "create")),
                 (res("would-update", compared=True, differs=["amount 50 -> 100", "x"]),
                  ("differs: amount 50 -> 100; x", "update")),
                 (res(compared=True), ("exists", "none")),
                 (res(compared=False), ("exists, not compared", "none")))
        for result, row in cases:
            with self.subTest(row=row):
                p, _ = plan(**{"gcp_budget-alert-setup": result})
                self.assertEqual(rows(p)["budget alert"], row)

    def test_switch_states(self):
        cases = ((res("would-create", ready=False, missing=["role"]), ("missing", "create")),
                 (res("would-update", ready=False, missing=["job-weekend"]),
                  ("incomplete: job-weekend", "update")))
        for result, row in cases:
            with self.subTest(row=row):
                p, c = plan(**{"gcp-cloud-sql_instance-switch-setup": result})
                self.assertEqual(rows(p)["database switch"], row)
                self.assertIn("gcp-cloud-sql_instance-describe", names(c))

    def test_switch_pending_stops_before_the_instance(self):
        how = {"item": "provider", "reason": "manual", "how": "fix the provider by hand"}
        sw = res("pending", answer=["| Part | State |"], pending=[how], ready=False,
                 missing=["provider"])
        p, c = plan(**{"gcp-cloud-sql_instance-switch-setup": sw})
        self.assertNotIn("gcp-cloud-sql_instance-describe", names(c))
        self.assertEqual(p.status, "failed")
        r = rows(p)
        self.assertEqual(r["database switch"], ("incomplete: provider", "blocked"))
        self.assertEqual(r["database instance"], (skill.NOT_CHECKED_SWITCH, "blocked"))
        self.assertEqual(r["login"], ("prepared", "none"))  # read before
        self.assertEqual(p.pending, [how])
        self.assertEqual(p.outputs["projectId"], PID)
        self.assertEqual(len(p.resources), 1)

    def test_a_failed_step_stops_and_nothing_later_is_guessed(self):
        failed = res("failed", answer=["It could not be read."])
        for name, item_name, later in (
                ("gcp_services-enable", "services", "gcp_budget-alert-setup"),
                ("gcp_budget-alert-setup", "budget alert", "gcp-cloud-sql_instance-switch-setup"),
                ("gcp-cloud-sql_instance-switch-setup", "database switch",
                 "gcp-cloud-sql_instance-describe")):
            with self.subTest(name=name):
                p, c = plan(**{name: failed})
                self.assertNotIn(later, names(c))
                self.assertEqual(p.status, "failed")
                self.assertEqual(rows(p)[item_name], ("unknown", "blocked"))
                self.assertEqual(p.items[-1][0], "login")
                self.assertEqual(p.pending[0]["item"], item_name)
                self.assertIn("It could not be read", p.pending[0]["how"])
        p, c = plan(**{"gcp-cloud-sql_instance-describe": failed})
        self.assertEqual(rows(p)["database instance"], ("unknown", "blocked"))
        p, c = plan(**{"gcp_environment-describe": failed})
        self.assertEqual(names(c), ["gcloud", "gcp_environment-describe"])
        self.assertEqual(p.items, [("shared project", "unknown", "blocked")])

    def test_instance_states(self):
        for state in ("stopped", "running", "starting", "creating"):
            with self.subTest(state=state):
                p, _ = plan(**{"gcp-cloud-sql_instance-describe": res(exists=True,
                                                                        state=state)})
                self.assertEqual(rows(p)["database instance"], ("exists, %s" % state, "none"))
                running = skill.RUNNING_LINE % (PID, "aleogr-shared")
                self.assertEqual(running in skill.lines_under(p), state != "stopped")
                # A running instance is never a difference.
                self.assertEqual(p.status, "unchanged")
        p, _ = plan(**{"gcp-cloud-sql_instance-describe": res(exists=False)})
        self.assertEqual(rows(p)["database instance"], ("missing", "create"))
        self.assertIn(skill.COST_LINE, skill.lines_under(p))

    def test_login_states(self):
        cases = ((PREPARED, ("prepared", "none")),
                 (res(prepared=False, readable=False), ("not prepared", "prepare")),
                 (res(prepared=False, readable=True), ("not prepared", "prepare")),
                 (res("failed", answer=["x"]), ("not checked", "prepare")))
        for result, row in cases:
            with self.subTest(row=row):
                p, _ = plan(**{"gcp_login-describe": result})
                self.assertEqual(rows(p)["login"], row)
                # An unknown login is never none: the plan is not unchanged.
                self.assertEqual(p.status, "unchanged" if row[1] == "none" else "would-update")
                self.assertEqual(skill.LOGIN_NOT_CHECKED_LINE in skill.lines_under(p),
                                 row[0] == "not checked")

    def test_last_runs_failed(self):
        sw = res(answer=SECRETS, ready=True, missing=[], lastRunFailed=["job-weeknight"])
        p, _ = plan(**{"gcp-cloud-sql_instance-switch-setup": sw})
        self.assertIn(skill.LAST_RUN_LINE % "aleogr-shared-stop-weeknight", skill.lines_under(p))
        self.assertEqual(p.status, "unchanged")

    def test_last_line(self):
        p, _ = plan(**{"gcp_login-describe": res(prepared=False)})
        self.assertEqual(skill.last_line(p), "1 item needs changes: /aleogr:platform-apply "
                         "confirm=yes prepares the login as far as a command can.")
        p, _ = plan(**{"gcp_environment-describe": MISSING})
        self.assertEqual(skill.last_line(p), "6 items need changes: /aleogr:platform-apply "
                         "confirm=yes creates them and prepares the login as far as a command "
                         "can.")

    def test_block_holds_no_organization_or_client(self):
        p, _ = plan()
        text = repr(p.outputs) + repr(p.resources) + repr(p.pending)
        self.assertNotIn("organization", text)
        self.assertNotIn("GCP_SHARED", text)

    def test_secrets_section(self):
        self.assertEqual(skill.switch_secrets(SWITCH_READY), SECRETS[1:])
        self.assertIsNone(skill.switch_secrets(res(answer=["x"])))

    def test_version_mismatch_ends_with_its_sentence(self):
        class Caller(FakeCaller):
            def call(self, command, name, args):
                if name == "gcp_services-enable":
                    raise common.PluginVersion({"answer": ["The plugin x is not the same."]})
                return FakeCaller.call(self, command, name, args)
        c = Caller(answers())
        p = skill.decide(skill.gather({}, c))
        self.assertEqual((p.status, p.items), ("failed", []))
        self.assertEqual(skill.answer_lines(p), ["The plugin x is not the same."])


class TestOnlyReads(unittest.TestCase):
    def test_calls_are_read_only(self):
        seen = []

        def fake(command, name, args=None, timeout=None, read_only=False, caller=None):
            seen.append((name, read_only, caller))
            return {"status": "unchanged", "outputs": {"exists": False}}
        real = common.call_plugin
        common.call_plugin = fake
        try:
            class Ctx(object):
                plugin = "aleogr"

                def plugin_path(self, *parts):
                    return os.path.join(ROOT, *parts)

                def read(self, argv, timeout=None):
                    return common.Completed(0, "x\n", "")
            c = skill.Caller(Ctx())
            c.call("aleogr-cloud-gcp", "gcp_environment-describe", {"project": "shared"})
        finally:
            common.call_plugin = real
        self.assertEqual(seen, [("gcp_environment-describe", True, "aleogr")])

    def test_no_own_runner(self):
        with open(skill.__file__, encoding="utf-8") as f:
            text = f.read()
        for word in ("ctx.write", "ctx.run(", "subprocess", "write_file", "mode=apply"):
            self.assertNotIn(word, text)
        self.assertFalse(getattr(skill, "WRITES", False))
        self.assertTrue(re.search(r'"mode": "plan"', text))


class TestSuites(unittest.TestCase):
    """The versions are checked before the first read: every plugin command this
    orchestrator can call is asked `--suite` right after its arguments are validated."""

    def test_every_command_it_calls_is_in_its_list(self):
        listed = list(skill.SUITE_COMMANDS)
        self.assertEqual(len(listed), len(set(listed)))
        self.assertEqual(called_commands(skill) - set(listed), set())
        self.assertEqual(set(listed) - called_commands(skill), set())

    def test_another_suite_on_the_last_plugin_ends_before_anything(self):
        other = skill.SUITE_COMMANDS[-1]
        result, logs, ran = run_with_other_suite(PLUGIN, "platform-plan", skill, {},
                                                 other, declaration=None)
        sentence = common.VERSION_SENTENCE.format(callee=other, caller="aleogr")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.lines.count(sentence), 1)
        self.assertEqual([l for l in result.lines if l.startswith("|")], [])  # no table
        # Each command asked once for its suite, and nothing invoked or run.
        self.assertEqual(logs, dict((c, ["--suite"]) for c in skill.SUITE_COMMANDS))
        self.assertEqual(ran, [])


if __name__ == "__main__":
    unittest.main()
