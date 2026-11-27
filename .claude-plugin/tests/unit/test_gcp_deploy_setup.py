"""Unit tests of gcp_deploy-setup: its golden commands (every write exactly as the
SKILL.md writes it), its gates (no write is built unless mode=apply and the reads hold),
and the rules no scenario covers.

The skill's run() is given a context whose read() answers from a dict (longest prefix of
the command, after `gcloud`) and whose execute() (where ctx.write runs a command that
passed the allowlist of writes) records the write and answers from another dict. No
provider command runs. The scenarios deploy-setup-* cover the rest, in the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_deploy-setup"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

PID = "aleogr-dev-demo-ab12"
CI = "demo-ci@%s.iam.gserviceaccount.com" % PID
AGENT = "serviceAccount:service-123456789012@gcp-sa-iap.iam.gserviceaccount.com"
ME = "demo-user@example.com"
IMAGE = "us-docker.pkg.dev/cloudrun/container/hello:latest"
ARGS = {"projectId": PID, "project": "demo", "region": "us-central1", "components": "web",
        "maxInstances": "2", "cpu": "1", "memory": "512Mi", "ciAccount": CI,
        "environment": "dev", "placeholderImage": IMAGE, "mode": "apply"}
ACCOUNT = "demo-web@%s.iam.gserviceaccount.com" % PID
MISSING_SERVICE = common.Completed(1, "", "ERROR: (gcloud.run.services.describe) Cannot find "
                                          "service [demo-web]")
MISSING_ACCOUNT = common.Completed(1, "", "ERROR: NOT_FOUND: Service account %s does not "
                                          "exist." % ACCOUNT)
DENIED = common.Completed(1, "", "ERROR: PERMISSION_DENIED: secret-text")

# The SKILL.md's commands, word for word, for the service demo-web (a value it writes in
# double quotes is one argument here, without its quotes).
GOLDEN = {
    "5.1": "gcloud iap web remove-iam-policy-binding --resource-type=cloud-run "
           "--service=demo-web --region=us-central1 --project=%s --member=allUsers "
           "--role=roles/iap.httpsResourceAccessor --all --quiet" % PID,
    "5.2": "gcloud run services remove-iam-policy-binding demo-web --member=allUsers "
           "--role=roles/run.invoker --region=us-central1 --project=%s --all --quiet" % PID,
    "5.3": "gcloud run services update demo-web --iap --region=us-central1 --project=%s "
           "--quiet" % PID,
    "5.4": "gcloud run services update demo-web --invoker-iam-check --region=us-central1 "
           "--project=%s --quiet" % PID,
    "6a": "gcloud iam service-accounts create demo-web --project=%s --display-name=demo web "
          "--quiet" % PID,
    "6b": "gcloud iam service-accounts add-iam-policy-binding %s --member=serviceAccount:%s "
          "--role=roles/iam.serviceAccountUser --project=%s --condition=None --quiet"
          % (ACCOUNT, CI, PID),
    "6c": "gcloud run deploy demo-web --image=%s --no-allow-unauthenticated --iap "
          "--service-account=%s --min=0 --max=2 --cpu=1 --memory=512Mi --cpu-throttling "
          "--labels=aleogr-project=demo,aleogr-environment=dev,aleogr-component=web "
          "--region=us-central1 --project=%s --quiet" % (IMAGE, ACCOUNT, PID),
    "6d1": "gcloud run services update demo-web --service-account=%s --min=0 --max=2 "
           "--scaling=auto --min-instances=default --cpu=1 --memory=512Mi --cpu-throttling "
           "--update-labels=aleogr-project=demo,aleogr-environment=dev,aleogr-component=web "
           "--region=us-central1 --project=%s --quiet" % (ACCOUNT, PID),
    "6d2": "gcloud run services add-iam-policy-binding demo-web --member=%s "
           "--role=roles/run.invoker --region=us-central1 --project=%s --condition=None "
           "--quiet" % (AGENT, PID),
    "6e": "gcloud run services add-iam-policy-binding demo-web --member=serviceAccount:%s "
          "--role=roles/run.developer --region=us-central1 --project=%s --condition=None "
          "--quiet" % (CI, PID),
    "6f": "gcloud iap web add-iam-policy-binding --resource-type=cloud-run --service=demo-web "
          "--region=us-central1 --project=%s --member=user:%s "
          "--role=roles/iap.httpsResourceAccessor --condition=None --quiet" % (PID, ME),
    "6g": "gcloud run services update demo-web --update-env-vars=^##^DB_NAME=demo_dev##"
          "DB_USER=demo-web@%s.iam --region=us-central1 --project=%s --quiet" % (PID, PID),
}


def split(line):
    """A golden line as argv: the display name is the one argument with a space."""
    words = line.split(" ")
    if "--display-name=demo" in words:
        i = words.index("--display-name=demo")
        words[i:i + 2] = ["--display-name=demo web"]
    return words


def service(**over):
    """A service as declared, as `run services describe --format=json` gives it."""
    s = {
        "metadata": {
            "name": "demo-web",
            "labels": {"aleogr-project": "demo", "aleogr-environment": "dev",
                       "aleogr-component": "web"},
            "annotations": {"run.googleapis.com/maxScale": "2",
                            "run.googleapis.com/iap-enabled": "true"},
        },
        "spec": {"template": {
            "metadata": {"annotations": {"run.googleapis.com/cpu-throttling": "true"}},
            "spec": {"serviceAccountName": ACCOUNT, "containers": [{
                "image": IMAGE, "resources": {"limits": {"cpu": "1000m", "memory": "512Mi"}},
                "env": []}]}}},
        "status": {"url": "https://demo-web-123456789012.us-central1.run.app"},
    }
    for path, value in over.items():
        obj = s
        keys = path.split("/")
        for k in keys[:-1]:
            obj = obj[int(k)] if isinstance(obj, list) else obj[k]
        obj[keys[-1]] = value
    return s


def policy(*bindings):
    return {"bindings": [{"role": r, "members": list(m)} for r, m in bindings]}


SERVICE_POLICY = policy(("roles/run.developer", ["serviceAccount:" + CI]),
                        ("roles/run.invoker", [AGENT]))
ACCOUNT_POLICY = policy(("roles/iam.serviceAccountUser", ["serviceAccount:" + CI]))
LOGIN_POLICY = policy(("roles/iap.httpsResourceAccessor", ["user:" + ME]))


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def reads(**over):
    """The answers of the reads (by the leading words after `gcloud`)."""
    a = {
        "projects describe": ok("123456789012\n"),
        "config get-value account": ok(ME + "\n"),
        "run services describe": ok(service()),
        "run services get-iam-policy": ok(SERVICE_POLICY),
        "iam service-accounts get-iam-policy": ok(ACCOUNT_POLICY),
        "iap web get-iam-policy": ok(LOGIN_POLICY),
    }
    keys = {"number": "projects describe", "me": "config get-value account",
            "service": "run services describe", "policy": "run services get-iam-policy",
            "account": "iam service-accounts get-iam-policy", "login": "iap web get-iam-policy"}
    for k, v in over.items():
        a[keys[k]] = v if isinstance(v, (common.Completed, list)) else ok(v)
    return a


class FakeContext(common.Context):
    """reads: {prefix: Completed or [Completed, ...] (one per call, the last repeated)};
    writes: {prefix: Completed or [...]}; a write with no answer exits 0."""

    def __init__(self, args, reads_, writes=None, read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.reads_ = {k: list(v) if isinstance(v, list) else v for k, v in reads_.items()}
        self.writes_ = {k: list(v) if isinstance(v, list) else v
                        for k, v in (writes or {}).items()}
        self.calls = []
        self.writes = []
        self.waits = 0

    @staticmethod
    def _answer(table, line):
        best = None
        for prefix in table:
            if line.startswith(prefix) and (best is None or len(prefix) > len(best)):
                best = prefix
        if best is None:
            return common.Completed(0, "", "")
        v = table[best]
        if isinstance(v, list):
            return v.pop(0) if len(v) > 1 else v[0]
        return v

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        if argv[0] == "sleep":
            self.waits += 1
            self.calls.append("sleep")
            return common.Completed(0, "", "")
        line = " ".join(argv[1:])
        self.calls.append(line)
        return self._answer(self.reads_, line)

    def execute(self, argv, timeout=None):
        # Reached only through ctx.write, after the allowlist of writes accepted argv.
        self.writes.append(list(argv))
        self.calls.append("WRITE " + " ".join(argv[1:]))
        return self._answer(self.writes_, " ".join(argv[1:]))


def run(reads_=None, writes=None, read_only=False, **over):
    args = dict(ARGS, **over)
    args = {k: v for k, v in args.items() if v is not None}
    common.reset_wait_budget()
    ctx = FakeContext(args, reads_ if reads_ is not None else reads(), writes, read_only)
    return skill.run(dict(args), ctx), ctx


def lines_of(ctx):
    return [" ".join(w) for w in ctx.writes]


class TestGoldenCommands(unittest.TestCase):
    def setUp(self):
        args = dict(ARGS, env="web:DB_NAME=demo_dev;web:DB_USER=demo-web@%s.iam" % PID)
        _, _, settings = skill.validate(args)
        self.args = args
        self.c = skill.Component("web", args, settings)
        self.info = {"agent": AGENT, "me": "user:" + ME}

    def built(self):
        c, args, info = self.c, self.args, self.info
        a = type("A", (), {"account_name_differs": True, "words": ["scaling", "labels"],
                           "manual": True, "template_min": True, "cpu_differs": True,
                           "memory_differs": True, "throttling_differs": True})()
        return {
            "5.1": skill.iap_remove_command(c, args, "allUsers", "roles/iap.httpsResourceAccessor"),
            "5.2": skill.run_remove_command(c, args, "allUsers", "roles/run.invoker"),
            "5.3": skill.login_command(c, args),
            "5.4": skill.invoker_command(c, args),
            "6a": skill.account_command(c, args),
            "6b": skill.act_as_command(c, args),
            "6c": skill.deploy_command(c, args),
            "6d1": skill.repair_command(c, args, skill.repair_flags(c, a, args)),
            "6d2": skill.agent_command(c, args, info),
            "6e": skill.ci_command(c, args),
            "6f": skill.access_command(c, args, info),
            "6g": skill.env_command(c, args, c.settings),
        }

    def test_every_write_as_the_skill_writes_it(self):
        built = self.built()
        self.assertEqual(sorted(built), sorted(GOLDEN))
        for key, argv in built.items():
            with self.subTest(step=key):
                self.assertEqual(argv, split(GOLDEN[key]))
                self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))

    def test_the_service_is_never_public(self):
        for argv in self.built().values():
            text = " ".join(argv)
            self.assertNotIn("--allow-unauthenticated", argv)
            self.assertNotIn("--no-iap", argv)
            self.assertNotIn("--no-invoker-iam-check", argv)
            self.assertNotIn("set-iam-policy", text)
            self.assertNotRegex(text, r"add-iam-policy-binding .*all(Authenticated)?Users")
            self.assertNotRegex(text, r"--(set|remove|clear)-env-vars|--env-vars-file")
        deploy = self.built()["6c"]
        self.assertIn("--no-allow-unauthenticated", deploy)
        self.assertIn("--iap", deploy)
        self.assertIn("--min=0", deploy)

    def test_a_create_runs_its_writes_in_the_skill_s_order(self):
        a = reads(service=[MISSING_SERVICE, ok(service())], account=[MISSING_ACCOUNT,
                                                                     ok(ACCOUNT_POLICY)],
                  login=ok(LOGIN_POLICY))
        r, ctx = run(a, env="web:DB_NAME=demo_dev;web:DB_USER=demo-web@%s.iam" % PID)
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes, [split(GOLDEN[k]) for k in ("6a", "6b", "6c", "6e",
                                                                  "6f", "6g")])
        self.assertEqual(r.block["outputs"]["envSet"], {"web": ["DB_NAME", "DB_USER"]})
        self.assertEqual(r.block["outputs"]["created"], ["web"])

    def test_a_repair_carries_only_what_differs(self):
        svc = service(**{"metadata/annotations": {"run.googleapis.com/maxScale": "3",
                                                  "run.googleapis.com/iap-enabled": "true"}})
        r, ctx = run(reads(service=[ok(svc), ok(service())]))
        self.assertEqual(r.status, "updated")
        self.assertEqual(lines_of(ctx), [
            "gcloud run services update demo-web --min=0 --max=2 --region=us-central1 "
            "--project=%s --quiet" % PID])

    def test_the_security_pass_in_its_order(self):
        svc = service(**{"metadata/annotations": {
            "run.googleapis.com/maxScale": "2",
            "run.googleapis.com/invoker-iam-disabled": "true"}})
        pol = policy(("roles/run.developer", ["serviceAccount:" + CI]),
                     ("roles/run.invoker", [AGENT, "allUsers", "allAuthenticatedUsers"]))
        login = policy(("roles/iap.httpsResourceAccessor", ["user:" + ME, "allUsers"]))
        r, ctx = run(reads(service=[ok(svc), ok(service())], policy=[ok(pol),
                                                                     ok(SERVICE_POLICY)],
                           login=[ok(login), ok(LOGIN_POLICY)]))
        self.assertEqual(r.status, "updated")
        w = lines_of(ctx)
        self.assertEqual(w[0], GOLDEN["5.1"])
        self.assertEqual(w[1], GOLDEN["5.2"])
        self.assertEqual(w[2], GOLDEN["5.2"].replace("--member=allUsers",
                                                     "--member=allAuthenticatedUsers"))
        self.assertEqual(w[3], GOLDEN["5.3"])
        self.assertEqual(w[4], GOLDEN["5.4"])
        self.assertEqual(len(w), 5)
        # The policy is read again, alone, right after the login was turned on.
        i = ctx.calls.index("WRITE " + GOLDEN["5.3"][len("gcloud "):])
        self.assertTrue(ctx.calls[i + 1].startswith("run services get-iam-policy demo-web"))


class TestGates(unittest.TestCase):
    """No write command is built unless mode=apply, the arguments hold and the reads
    hold."""

    def assert_no_write(self, r, ctx, status=None):
        if status:
            self.assertEqual(r.status, status)
        self.assertEqual(ctx.writes, [])
        self.assertFalse(any(c.startswith("WRITE") for c in ctx.calls))

    def needs_work(self):
        return reads(service=MISSING_SERVICE, account=MISSING_ACCOUNT)

    def test_mode_absent_is_a_plan(self):
        r, ctx = run(self.needs_work(), mode=None)
        self.assert_no_write(r, ctx, "would-create")
        self.assertEqual(r.block["mode"], "plan")
        self.assertIn("This plan changed nothing.", r.lines)

    def test_mode_plan(self):
        r, ctx = run(self.needs_work(), mode="plan")
        self.assert_no_write(r, ctx, "would-create")
        self.assertEqual(r.block["outputs"]["created"], [])

    def test_mode_with_another_value(self):
        for mode in ("APPLY", "yes", ""):
            with self.subTest(mode=mode):
                r, ctx = run(self.needs_work(), mode=mode)
                self.assert_no_write(r, ctx, "failed")
                self.assertEqual(ctx.calls, [])
                self.assertIn("mode must be plan or apply.", r.lines)

    def test_read_only_refuses_every_write(self):
        args = dict(ARGS)
        ctx = FakeContext(args, reads(), read_only=True)
        self.assertFalse(ctx.writable)
        with self.assertRaises(common.WriteRefused):
            ctx.write(split(GOLDEN["6c"]))
        self.assertEqual(ctx.writes, [])

    def test_an_argument_missing_or_broken(self):
        for over in ({"placeholderImage": None}, {"ciAccount": "x@y"}, {"maxInstances": "0"},
                     {"maxInstances": "02"}, {"cpu": "4"}, {"memory": "4Gi"},
                     {"environment": "test"}, {"placeholderImage": "gcr.io/x/hello"},
                     {"placeholderImage": IMAGE + "@sha256:abc"},
                     {"env": "web:A=has space"}, {"env": "api:A=1"}, {"components": "web,web"}):
            with self.subTest(over=over):
                r, ctx = run(**over)
                self.assert_no_write(r, ctx, "failed")
                self.assertEqual(ctx.calls, [])
                self.assertEqual(r.block["resources"], [])

    def test_a_failed_read_writes_nothing(self):
        for over in ({"number": common.Completed(0, "", "")}, {"me": ok("")},
                     {"service": DENIED}, {"policy": DENIED}, {"account": DENIED},
                     {"login": DENIED}, {"service": ok("not json")}):
            with self.subTest(over=over):
                r, ctx = run(reads(**over))
                self.assert_no_write(r, ctx, "failed")
                self.assertNotIn("secret-text", common.render_answer(r))

    def test_an_active_account_no_write_takes(self):
        # The account is read from gcloud: one that the shape of 6f refuses ends the run
        # before any write, in both modes.
        for mode in ("plan", "apply"):
            r, ctx = run(reads(me=ok("someone@localhost\n"), login=ok({})), mode=mode)
            self.assert_no_write(r, ctx, "failed")
            self.assertEqual(r.lines, [skill.ME_UNUSABLE])

    def test_a_role_no_remove_takes(self):
        login = {"bindings": [{"role": "roles/x y", "members": ["allUsers"]}]}
        for mode in ("plan", "apply"):
            r, ctx = run(reads(login=ok(login)), mode=mode)
            self.assert_no_write(r, ctx, "failed")
            self.assertEqual(r.lines, [skill.REMOVE_UNUSABLE % "demo-web"])


class TestPaths(unittest.TestCase):
    def test_unchanged_runs_no_write_and_reads_once(self):
        r, ctx = run()
        self.assertEqual((r.status, ctx.writes, r.block["pending"]), ("unchanged", [], []))
        self.assertEqual(len(ctx.calls), 6)
        self.assertNotIn("@", common.render_block(r.block))

    def test_the_poll_is_only_for_an_account_this_run_created(self):
        refused = common.Completed(1, "", "NOT_FOUND: does not exist")
        a = reads(account=ok({}))  # the account exists, without the CI binding
        r, ctx = run(a, writes={"iam service-accounts add-iam-policy-binding": refused})
        self.assertEqual(ctx.waits, 0)
        self.assertEqual(r.status, "failed")
        self.assertIn(skill.ACT_AS_FAILED % ACCOUNT, r.lines)
        self.assertIn("The binding was refused after 1 try.", r.lines)

    def test_a_refusal_that_waiting_does_not_cure_ends_the_poll(self):
        a = reads(service=MISSING_SERVICE, account=MISSING_ACCOUNT)
        r, ctx = run(a, writes={"iam service-accounts add-iam-policy-binding": DENIED})
        self.assertEqual((ctx.waits, r.status), (0, "created"))
        self.assertFalse(any("run deploy" in w for w in lines_of(ctx)))

    def test_the_wait_budget_ends_the_poll_as_the_tenth_refusal(self):
        refused = common.Completed(1, "", "NOT_FOUND: does not exist")
        a = reads(service=MISSING_SERVICE, account=MISSING_ACCOUNT)
        args = dict(ARGS)
        common.reset_wait_budget()
        ctx = FakeContext(args, a, {"iam service-accounts add-iam-policy-binding": refused})
        for _ in range(14):  # 14 of the 16 waits of the budget are spent already
            self.assertTrue(common.wait_allowed())
            common._waited[0] += common.WAIT_SECONDS
        r = skill.run(dict(args), ctx)
        self.assertEqual(ctx.waits, 2)
        self.assertEqual(r.status, "created")
        self.assertIn(common.WAIT_BUDGET_SENTENCE, r.lines)
        self.assertIn("The binding was refused after 3 tries.", r.lines)
        self.assertEqual([p["item"] for p in r.block["pending"]], ["web: service"])
        common.reset_wait_budget()

    def test_a_refused_access_does_not_stop_the_settings(self):
        a = reads(login=ok({}))
        r, ctx = run(a, writes={"iap web add-iam-policy-binding": DENIED},
                     env="web:DB_NAME=demo_dev")
        self.assertEqual(lines_of(ctx)[-1], "gcloud run services update demo-web "
                         "--update-env-vars=^##^DB_NAME=demo_dev --region=us-central1 "
                         "--project=%s --quiet" % PID)
        self.assertIn(skill.ACCESS_ITEM, r.block["pending"])
        self.assertEqual(r.block["pending"].count(skill.ACCESS_ITEM), 1)

    def test_only_a_refused_access_is_unchanged(self):
        r, ctx = run(reads(login=ok({})), writes={"iap web add-iam-policy-binding": DENIED})
        self.assertEqual(r.status, "unchanged")
        self.assertEqual(r.block["pending"], [skill.ACCESS_ITEM])

    def test_a_failed_create_whose_read_fails(self):
        a = reads(service=[MISSING_SERVICE, DENIED])
        r, ctx = run(a, writes={"run deploy": DENIED})
        self.assertEqual(r.status, "failed")
        self.assertIn(skill.CREATE_UNREADABLE % "demo-web", r.lines)
        self.assertEqual(lines_of(ctx)[-1].split(" ")[:3], ["gcloud", "run", "deploy"])

    def test_a_failed_create_that_created_nothing(self):
        a = reads(service=MISSING_SERVICE)
        r, ctx = run(a, writes={"run deploy": DENIED})
        self.assertEqual(r.status, "failed")
        self.assertIn(skill.CREATE_FAILED % "demo-web", r.lines)
        self.assertEqual(r.block["pending"][0]["item"], "web: service")

    def test_the_deploy_is_never_run_twice(self):
        a = reads(service=[MISSING_SERVICE, ok(service(**{"metadata/annotations": {}}))])
        r, ctx = run(a, writes={"run deploy": DENIED})
        self.assertEqual(sum(1 for w in lines_of(ctx) if " run deploy " in " " + w), 1)

    def test_a_stop_in_6_after_a_change_is_not_failed(self):
        svc = service(**{"metadata/labels": {}})
        a = reads(service=svc, policy=policy(("roles/run.developer", ["serviceAccount:" + CI])))
        r, ctx = run(a, writes={"run services add-iam-policy-binding": DENIED})
        self.assertEqual(r.status, "updated")
        self.assertIn(skill.AGENT_FAILED % "demo-web", r.lines)
        self.assertEqual(r.block["outputs"]["updated"], ["web"])

    def test_a_stop_at_the_first_command_of_6_is_failed(self):
        a = reads(service=service(**{"metadata/labels": {}}))
        r, ctx = run(a, writes={"run services update": DENIED})
        self.assertEqual(r.status, "failed")
        self.assertIn(skill.REPAIR_FAILED % "demo-web", r.lines)
        self.assertEqual([p["item"] for p in r.block["pending"]], ["web: labels"])

    def test_a_failed_read_after_the_change(self):
        a = reads(service=[ok(service(**{"metadata/labels": {}})), DENIED])
        r, _ = run(a)
        self.assertEqual(r.block["pending"],
                         [{"item": "web: read", "reason": skill.REASON_READ, "how": skill.HOW}])

    def test_the_block_holds_no_e_mail_and_no_value(self):
        a = reads(service=[MISSING_SERVICE, ok(service())], account=[MISSING_ACCOUNT,
                                                                     ok(ACCOUNT_POLICY)],
                  login=[ok({})])
        r, _ = run(a, writes={"iap web add-iam-policy-binding": DENIED},
                   env="web:DB_NAME=secret-value")
        block = common.render_block(r.block)
        self.assertNotIn("@", block)
        self.assertNotIn("secret-value", common.render_answer(r))

    def test_the_runner_as_a_service_account(self):
        r, ctx = run(reads(me=ok("deployer@%s.iam.gserviceaccount.com\n" % PID), login=ok({})))
        self.assertEqual(r.status, "updated")
        self.assertIn("--member=serviceAccount:deployer@%s.iam.gserviceaccount.com" % PID,
                      ctx.writes[0])

    def test_read_failure_in_step_3_reports_the_services_read(self):
        a = reads(service=[ok(service()), DENIED])
        r, _ = run(a, components="web,api")
        self.assertEqual(r.status, "failed")
        self.assertEqual([s["component"] for s in r.block["outputs"]["services"]], ["web"])
        self.assertEqual(r.lines, [skill.READ_FAILED % ("demo-api", PID)])



class TimeLimitContext(FakeContext):
    """The run's time limit is reached while its `at`-th write is still running."""

    def __init__(self, args, reads_, at):
        FakeContext.__init__(self, args, reads_)
        self.at = at

    def execute(self, argv, timeout=None):
        if len(self.writes) + 1 == self.at:
            self.writes.append(list(argv))
            raise common.TimeLimit(argv)
        return FakeContext.execute(self, argv, timeout)


class TestAborted(unittest.TestCase):
    def aborted(self, at):
        a = reads(service=[MISSING_SERVICE, ok(service())], account=[MISSING_ACCOUNT,
                                                                     ok(ACCOUNT_POLICY)],
                  login=ok(LOGIN_POLICY))
        common.reset_wait_budget()
        ctx = TimeLimitContext(dict(ARGS), a, at)
        r, code, why = common.run_skill(skill, dict(ARGS), ctx)
        self.assertEqual((code, why), (common.EXIT_SOFTWARE, "time limit reached"))
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.block["cost"], common.ABORTED_COST)
        self.assertEqual((r.lines[0], r.lines[-1]),
                         (common.TIME_LIMIT_SENTENCE, common.READ_STATE_SENTENCE))
        return r, ctx

    def test_after_the_first_write_it_says_what_may_exist(self):
        for at in (2, 3):  # the act-as grant after the account, the deploy
            with self.subTest(at=at):
                r, ctx = self.aborted(at)
                self.assertEqual(len(ctx.writes), at)
                self.assertTrue(r.lines[1].startswith(
                    "Before it stopped, this run had already run these writes: `gcloud iam "
                    "service-accounts create demo-web "), r.lines[1])
                self.assertEqual(r.lines[2:-1], [skill.ABORT_LINE])
                self.assertIn("running this skill again with the same arguments goes on",
                              skill.ABORT_LINE)

    def test_the_first_write_itself_is_still_running(self):
        r, ctx = self.aborted(1)
        self.assertEqual(len(ctx.writes), 1)
        self.assertEqual(len(r.lines), 3)


if __name__ == "__main__":
    unittest.main()
