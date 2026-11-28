"""Unit tests of gcp-cloud-sql_instance-create: its golden commands, its gate (no create
without mode=apply and confirm=yes, and no write at all in the paths that must not write),
the eight-minute budget of waiting, and the paths no scenario covers.

The skill's run() is given a context whose call() answers for the describe skill, whose
read() answers each describe from a list (one state per describe) and logs `sleep 30`,
and whose execute() (reached only through ctx.write, after the allowlist of writes)
records each write. No provider command runs. The scenarios sql-create-* cover the rest.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_instance-create"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ARGS = {"projectId": "aleogr-shared-zz99", "instance": "aleogr-shared", "platform": "shared",
        "version": "POSTGRES_17", "tier": "db-f1-micro", "edition": "enterprise",
        "region": "southamerica-east1", "storageGb": "10", "backupStartUtc": "06:00",
        "retainedBackups": "7", "mode": "apply", "confirm": "yes"}

# The SKILL.md's commands, word for word (steps 4 to 7), the quotes of
# --database-flags="..." removed as the shell removes them.
GOLDEN_CREATE = (
    "gcloud sql instances create aleogr-shared --project=aleogr-shared-zz99 "
    "--database-version=POSTGRES_17 --edition=enterprise --tier=db-f1-micro "
    "--region=southamerica-east1 --availability-type=zonal --storage-type=SSD --storage-size=10 "
    "--no-storage-auto-increase --assign-ip --backup --backup-start-time=06:00 "
    "--retained-backups-count=7 --no-enable-point-in-time-recovery "
    "--database-flags=cloudsql.iam_authentication=on --no-enable-dataplex-integration "
    "--deletion-protection --async --quiet")
GOLDEN_DESCRIBE = ("gcloud sql instances describe aleogr-shared --project=aleogr-shared-zz99 "
                   "--format=json")
GOLDEN_PATCH = ("gcloud sql instances patch aleogr-shared --project=aleogr-shared-zz99 "
                "--activation-policy=NEVER --quiet")
GOLDEN_JOB = ("gcloud scheduler jobs run aleogr-shared-stop-weeknight --project=aleogr-shared-zz99 "
              "--location=southamerica-east1 --quiet")
STOP_HOW = ("/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop projectId=aleogr-shared-zz99 "
            "instance=aleogr-shared")
DESCRIBE_HOW = ("/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe "
                "projectId=aleogr-shared-zz99 instance=aleogr-shared")

JSON = {"stopped": ("NEVER", "RUNNABLE"), "running": ("ALWAYS", "RUNNABLE"),
        "creating": ("ALWAYS", "PENDING_CREATE"), "starting": ("ALWAYS", "MAINTENANCE")}


def described(exists, state=None, status="unchanged"):
    return {"aleogr-result": 1, "status": status, "outputs": {"exists": exists, "state": state},
            "answer": []}


class FakeContext(common.Context):
    def __init__(self, args, found, states=(), fail=(), read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.found = found
        self.states = list(states)  # one per describe; None: the describe fails
        self.fail = set(fail)  # the writes that exit 1, by their first words
        self.called = []
        self.log = []
        self.writes = []

    def call(self, command, name, args=None, timeout=None):
        self.called.append(name)
        return self.found

    def execute(self, argv, timeout=None):
        line = " ".join(argv)
        self.writes.append(line)
        self.log.append(line)
        failed = any(line.startswith(f) for f in self.fail)
        return common.Completed(1 if failed else 0, "", "ERROR: PERMISSION_DENIED" if failed
                                else "")

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.log.append(line)
        if argv[0] == "sleep":
            return common.Completed(0, "", "")
        assert line == GOLDEN_DESCRIBE, line
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if state is None:
            return common.Completed(1, "", "ERROR")
        policy, raw = JSON[state]
        return common.Completed(0, json.dumps({"state": raw,
                                               "settings": {"activationPolicy": policy}}), "")


def run(found=None, states=("running", "stopped"), fail=(), **over):
    common.reset_wait_budget()
    args = dict(ARGS, **over)
    args = {k: v for k, v in args.items() if v is not None}
    ctx = FakeContext(args, found or described(False), states, fail)
    return skill.run(dict(args), ctx), ctx


def waits(ctx):
    return sum(1 for line in ctx.log if line == "sleep 30")


class TestGoldenCommands(unittest.TestCase):
    def test_without_stop_job(self):
        r, ctx = run()
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE, GOLDEN_PATCH])
        self.assertEqual(ctx.log, [GOLDEN_CREATE, GOLDEN_DESCRIBE, GOLDEN_PATCH, GOLDEN_DESCRIBE])
        self.assertEqual(ctx.called, ["gcp-cloud-sql_instance-describe"])
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "stopped"})

    def test_with_stop_job(self):
        r, ctx = run(stopJob="aleogr-shared-stop-weeknight")
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE, GOLDEN_JOB])
        # The describe that shows stopped after the job is step 7's verification.
        self.assertEqual(ctx.log, [GOLDEN_CREATE, GOLDEN_DESCRIBE, GOLDEN_JOB, GOLDEN_DESCRIBE])
        self.assertIn("The night stop is proven: the job aleogr-shared-stop-weeknight stopped "
                      "the new instance.", r.lines)

    def test_every_write_is_on_the_allowlist(self):
        args = dict(ARGS, stopJob="aleogr-shared-stop-weeknight")
        built = [" ".join(a) for a in skill.commands_of_apply(args)]
        self.assertEqual(built, [GOLDEN_CREATE, GOLDEN_PATCH, GOLDEN_JOB])
        for argv in skill.commands_of_apply(args):
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))
        self.assertEqual(skill.create_command(ARGS), GOLDEN_CREATE.split(" "))


class TestGate(unittest.TestCase):
    """The create has a fixed monthly cost: it is built only with mode=apply and
    confirm=yes, once the instance is known to be missing."""

    def assert_no_write(self, r, ctx):
        self.assertEqual(ctx.writes, [])
        self.assertEqual(r.block["cost"], skill.COST)

    def test_confirm_absent(self):
        r, ctx = run(confirm=None)
        self.assert_no_write(r, ctx)
        self.assertEqual(r.status, "pending")
        self.assertEqual(ctx.log, [])
        self.assertEqual(r.block["outputs"], {"exists": False, "state": None})
        self.assertEqual(r.block["resources"], [])
        how = r.block["pending"][0]["how"]
        self.assertTrue(how.endswith(" mode=apply confirm=yes"), how)
        self.assertIn("confirm=yes", r.lines[0])

    def test_confirm_with_another_value(self):
        for value in ("no", "YES", "true", ""):
            with self.subTest(value=value):
                r, ctx = run(confirm=value)
                self.assert_no_write(r, ctx)
                self.assertEqual(r.status, "failed")
                self.assertEqual(ctx.called, [])
                self.assertEqual(ctx.log, [])

    def test_plan_writes_nothing(self):
        for mode in ("plan", None):
            r, ctx = run(mode=mode)
            self.assert_no_write(r, ctx)
            self.assertEqual(r.status, "would-create")
            self.assertEqual(r.block["mode"], "plan")
            self.assertEqual(ctx.log, [])
            self.assertIn("It would cost about R$ 50 per month while stopped.", r.lines)

    def test_read_only_refuses_the_create(self):
        ctx = FakeContext(ARGS, described(False), read_only=True)
        self.assertFalse(ctx.writable)
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.create_command(ARGS))
        self.assertEqual(ctx.writes, [])

    def test_validation(self):
        cases = [({"projectId": None}, "projectId is missing."),
                 ({"tier": None}, "tier is missing."),
                 ({"platform": None}, skill.PLATFORM_NOT_SHARED),
                 ({"platform": "other"}, skill.PLATFORM_NOT_SHARED),
                 ({"version": "MYSQL_8"}, None), ({"storageGb": "9"}, None),
                 ({"storageGb": "101"}, None), ({"backupStartUtc": "24:00"}, None),
                 ({"retainedBackups": "0"}, None), ({"mode": "yes"}, None),
                 ({"stopJob": "Bad_Job"}, None)]
        for over, sentence in cases:
            with self.subTest(over=over):
                r, ctx = run(**over)
                self.assert_no_write(r, ctx)
                self.assertEqual(r.status, "failed")
                self.assertEqual((ctx.called, ctx.log), ([], []))
                self.assertEqual(len(r.lines), 1)
                if sentence:
                    self.assertEqual(r.lines, [sentence])
                self.assertEqual(r.block["outputs"], {"exists": None, "state": None})

    def test_an_existing_instance_is_never_touched(self):
        for state in ("stopped", "running", "creating"):
            with self.subTest(state=state):
                r, ctx = run(found=described(True, state))
                self.assert_no_write(r, ctx)
                self.assertEqual(r.status, "unchanged")
                self.assertEqual(r.block["outputs"], {"exists": True, "state": state})
                self.assertEqual(ctx.log, [])
                if state != "stopped":
                    # A running instance is never left so without the answer saying it.
                    self.assertTrue(any("charged by the hour until it is stopped" in line
                                        for line in r.lines))

    def test_the_check_failed(self):
        found = {"status": "failed", "outputs": {"exists": None},
                 "answer": ["The instance aleogr-shared could not be read: gcloud failed."]}
        r, ctx = run(found=found)
        self.assert_no_write(r, ctx)
        self.assertEqual(r.lines, found["answer"])
        self.assertEqual(r.block["outputs"], {"exists": None, "state": None})

    def test_a_value_no_command_takes(self):
        # The SKILL.md has no rule for edition, tier or region; the create's shape has.
        for over in ({"edition": "standard"}, {"tier": "f1-micro"}, {"region": "x" * 64},
                     {"version": "POSTGRES_1234"}, {"storageGb": "010"}):
            for mode in ("plan", "apply"):
                with self.subTest(over=over, mode=mode):
                    r, ctx = run(mode=mode, **over)
                    self.assert_no_write(r, ctx)
                    self.assertEqual(r.status, "failed")
                    self.assertEqual(r.lines, [skill.NOT_RUNNABLE])
                    self.assertEqual(r.block["outputs"], {"exists": False, "state": None})


class TestPaths(unittest.TestCase):
    def test_a_create_that_fails(self):
        r, ctx = run(fail=("gcloud sql instances create",))
        self.assertEqual(r.status, "failed")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE])
        self.assertEqual(r.block["outputs"], {"exists": False, "state": None})
        self.assertEqual(r.block["resources"], [])
        self.assertNotIn("PERMISSION_DENIED", "\n".join(r.lines))
        # The cost sentence comes before the lines that report the create.
        self.assertEqual(r.lines[0], skill.CREATE_COST_LINE)

    def test_it_waits_for_the_creation(self):
        r, ctx = run(states=("creating", "creating", "starting", "running", "stopped"))
        self.assertEqual(r.status, "created")
        self.assertEqual(waits(ctx), 3)
        self.assertEqual(ctx.writes, [GOLDEN_CREATE, GOLDEN_PATCH])

    def test_the_budget_is_spent_while_it_is_still_being_created(self):
        r, ctx = run(states=("creating",))
        self.assertEqual(r.status, "pending")
        self.assertEqual(waits(ctx), 16)
        self.assertEqual(ctx.writes, [GOLDEN_CREATE])  # no stop of an instance being created
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "creating"})
        self.assertEqual(len(r.block["resources"]), 1)
        self.assertEqual(r.block["pending"], [{"item": "instance", "reason": "manual",
                                               "how": STOP_HOW}])
        text = "\n".join(r.lines)
        self.assertIn("it runs and is charged by the hour until it is stopped", text)
        self.assertIn(STOP_HOW, text)
        self.assertEqual(r.lines[0], skill.CREATE_COST_LINE)

    def test_a_describe_that_fails_while_waiting(self):
        r, ctx = run(states=("creating", None))
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "creating"})
        self.assertEqual(r.block["pending"][0]["how"], STOP_HOW)
        self.assertIn("charged by the hour", "\n".join(r.lines))

    def test_already_stopped_after_the_creation(self):
        r, ctx = run(states=("stopped",), stopJob="aleogr-shared-stop-weeknight")
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE])
        self.assertIn("The night stop was not tested: the instance was already stopped.", r.lines)

    def test_a_patch_that_fails(self):
        r, ctx = run(fail=("gcloud sql instances patch",))
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "running"})
        self.assertEqual(r.block["pending"][0]["how"], STOP_HOW)
        self.assertIn("charged by the hour", "\n".join(r.lines))

    def test_a_verification_that_does_not_show_stopped(self):
        r, ctx = run(states=("running", "running"))
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "running"})
        self.assertEqual(ctx.log.count(GOLDEN_DESCRIBE), 2)

    def test_the_job_fails_to_run(self):
        r, ctx = run(stopJob="aleogr-shared-stop-weeknight", fail=("gcloud scheduler",))
        self.assertEqual(r.status, "pending")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE, GOLDEN_JOB, GOLDEN_PATCH])
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "stopped"})
        self.assertEqual([p["item"] for p in r.block["pending"]], ["night stop"])
        self.assertEqual(r.block["pending"][0]["how"], skill.NIGHT_STOP_HOW)

    def test_the_job_does_not_stop_it_within_the_budget(self):
        # The job runs, the instance stays running: the waits end on the budget (or the
        # five minutes), then this skill's own patch, then step 7.
        r, ctx = run(states=["running"] * 20 + ["stopped"],
                     stopJob="aleogr-shared-stop-weeknight")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE, GOLDEN_JOB, GOLDEN_PATCH])
        self.assertEqual(waits(ctx), 10)
        self.assertEqual(r.status, "pending")
        self.assertIn("night stop", [p["item"] for p in r.block["pending"]])

    def test_the_job_wait_after_a_long_creation(self):
        # 14 waits for the creation leave 2 for the job: the budget ends the job's wait,
        # which counts as "still not stopped": the patch runs.
        states = ["creating"] * 14 + ["running"] * 4 + ["stopped"]
        r, ctx = run(states=states, stopJob="aleogr-shared-stop-weeknight")
        self.assertEqual(waits(ctx), 16)
        self.assertEqual(ctx.writes, [GOLDEN_CREATE, GOLDEN_JOB, GOLDEN_PATCH])
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.block["outputs"]["state"], "stopped")
        self.assertTrue(any("did NOT stop it" in line for line in r.lines))

    def test_the_state_table(self):
        cases = [({"settings": {"activationPolicy": "NEVER"}, "state": "RUNNABLE"}, "stopped"),
                 ({"settings": {"activationPolicy": "ALWAYS"}, "state": "RUNNABLE"}, "running"),
                 ({"settings": {"activationPolicy": "ALWAYS"}, "state": "PENDING_CREATE"},
                  "creating"),
                 ({"settings": {"activationPolicy": "ALWAYS"}, "state": "X"}, "starting"),
                 ({}, "unknown")]
        for data, want in cases:
            self.assertEqual(skill.state_of(data), want)



class TimeLimitContext(FakeContext):
    """The run's time limit is reached while its `at`-th command (1 for the first, in the
    order of the log: writes, describes and waits) is still running."""

    def __init__(self, at, states):
        FakeContext.__init__(self, dict(ARGS), described(False), states)
        self.at = at

    def _tick(self, argv):
        if len(self.log) + 1 == self.at:
            self.log.append(" ".join(argv))
            raise common.TimeLimit(argv)

    def execute(self, argv, timeout=None):
        self._tick(argv)
        return FakeContext.execute(self, argv, timeout)

    def read(self, argv, timeout=None):
        self._tick(argv)
        return FakeContext.read(self, argv, timeout)


class TestAborted(unittest.TestCase):
    CREATED = ["The instance aleogr-shared was created.",
               "It costs about R$ 50 per month while stopped.",
               "It is not stopped: it runs and is charged by the hour until it is stopped. "
               "Stop it with %s." % STOP_HOW]

    def aborted(self, at, states):
        common.reset_wait_budget()
        ctx = TimeLimitContext(at, states)
        r, code, why = common.run_skill(skill, dict(ARGS), ctx)
        self.assertEqual((code, why), (common.EXIT_SOFTWARE, "time limit reached"))
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.block["cost"], common.ABORTED_COST)
        self.assertEqual(r.block["mode"], "apply")
        self.assertEqual(r.lines[0], common.TIME_LIMIT_SENTENCE)
        self.assertEqual(r.lines[-1], common.READ_STATE_SENTENCE)
        return r, ctx

    def test_after_the_create_the_instance_runs_and_is_charged(self):
        # The describe of step 5 (the second command) is still running.
        r, ctx = self.aborted(2, ["creating"])
        self.assertEqual(r.lines, [
            common.TIME_LIMIT_SENTENCE,
            "Before it stopped, this run had already run these writes: `%s`." % GOLDEN_CREATE,
        ] + self.CREATED + [common.READ_STATE_SENTENCE])
        # While waiting (a wait, then a describe), and at the stop itself.
        for at in (3, 4):
            r, _ = self.aborted(at, ["creating"])
            self.assertEqual(r.lines[2:-1], self.CREATED, at)
        r, ctx = self.aborted(3, ["running"])  # the patch of step 6
        self.assertEqual(ctx.log[-1], GOLDEN_PATCH)
        self.assertEqual(r.lines[2:-1], self.CREATED)
        self.assertIn(GOLDEN_PATCH, r.lines[1])

    def test_the_verification_after_the_patch_still_says_it(self):
        r, ctx = self.aborted(4, ["running"])
        self.assertEqual(ctx.log, [GOLDEN_CREATE, GOLDEN_DESCRIBE, GOLDEN_PATCH,
                                   GOLDEN_DESCRIBE])
        self.assertEqual(r.lines[2:-1], self.CREATED)

    def test_the_create_itself_is_still_running(self):
        r, ctx = self.aborted(1, ["running"])
        self.assertEqual(ctx.log, [GOLDEN_CREATE])
        self.assertEqual(r.lines, [
            common.TIME_LIMIT_SENTENCE,
            "Before it stopped, this run had already run these writes: `%s`." % GOLDEN_CREATE,
            common.READ_STATE_SENTENCE])

    def test_cleared_once_seen_stopped(self):
        # Step 5 sees it stopped; the verification of step 7 is still running.
        r, ctx = self.aborted(3, ["stopped"])
        self.assertEqual(ctx.log, [GOLDEN_CREATE, GOLDEN_DESCRIBE, GOLDEN_DESCRIBE])
        self.assertEqual(len(r.lines), 3)
        self.assertNotIn("charged by the hour", "\n".join(r.lines))

    def test_an_unexpected_error_says_the_same(self):
        common.reset_wait_budget()
        ctx = FakeContext(dict(ARGS), described(False), ["creating"])

        def read(argv, timeout=None):
            raise RecursionError("maximum recursion depth exceeded: s3cr3t")

        ctx.read = read
        r, code, why = common.run_skill(skill, dict(ARGS), ctx)
        self.assertEqual((code, why), (common.EXIT_SOFTWARE, "unexpected error"))
        self.assertEqual(r.lines[0], common.UNEXPECTED_SENTENCE)
        self.assertEqual(r.lines[2:-1], self.CREATED)
        self.assertNotIn("s3cr3t", "\n".join(r.lines))


GOLDEN_OPERATIONS = ("gcloud sql operations list --instance=aleogr-shared "
                     "--project=aleogr-shared-zz99 --sort-by=~insertTime --limit=10 "
                     "--format=value(operationType)")


class ResumeContext(FakeContext):
    """FakeContext whose read also answers the instance's last operations (resume=yes):
    `operations` is their text, or None for a read that fails."""

    def __init__(self, args, found, states, operations="CREATE\n", fail=()):
        FakeContext.__init__(self, args, found, states, fail)
        self.operations = operations

    def read(self, argv, timeout=None):
        if argv[:4] == ["gcloud", "sql", "operations", "list"]:
            assert common.read_refusal(argv) is None, argv
            line = " ".join(argv)
            self.log.append(line)
            if self.operations is None:
                return common.Completed(1, "", "ERROR")
            return common.Completed(0, self.operations, "")
        return FakeContext.read(self, argv, timeout)


def resume(found, states=("running", "stopped"), operations="CREATE\n", **over):
    common.reset_wait_budget()
    args = dict(ARGS, resume="yes", stopJob="aleogr-shared-stop-weeknight")
    args.update(over)
    args = {k: v for k, v in args.items() if v is not None}
    ctx = ResumeContext(args, found, states, operations)
    return skill.run(dict(args), ctx), ctx


class TestResume(unittest.TestCase):
    """resume=yes: given by the caller whose own run asked for this creation in an earlier
    command. The creation is skipped for an instance that exists; the run goes on with the
    wait, the stop by the night job and the verification, only for an instance this skill
    has just created and not stopped yet. The write commands are the same."""

    def test_validated(self):
        for value in ("no", "YES", "true", ""):
            with self.subTest(value=value):
                r, ctx = resume(described(True, "creating"), resume=value)
                self.assertEqual(r.status, "failed")
                self.assertEqual(r.lines, [skill.RESUME_INVALID])
                self.assertEqual((ctx.writes, ctx.called, ctx.log), ([], [], []))
        for over in ({"mode": "plan"}, {"mode": None}, {"confirm": None}):
            with self.subTest(over=over):
                r, ctx = resume(described(True, "creating"), **over)
                self.assertEqual(r.lines, [skill.RESUME_NEEDS_APPLY])
                self.assertEqual((ctx.writes, ctx.log), ([], []))

    def test_without_resume_an_existing_instance_is_never_touched(self):
        for state in ("creating", "running", "starting", "stopped"):
            with self.subTest(state=state):
                r, ctx = run(found=described(True, state), stopJob="aleogr-shared-stop-weeknight")
                self.assertEqual(r.status, "unchanged")
                self.assertEqual((ctx.writes, ctx.log), ([], []))

    def test_it_goes_on_after_the_creation(self):
        r, ctx = resume(described(True, "creating"), states=("creating", "running", "stopped"))
        self.assertEqual(r.status, "created")
        self.assertNotIn(GOLDEN_CREATE, ctx.writes)
        self.assertEqual(ctx.writes, [GOLDEN_JOB])  # the night stop, tested
        self.assertEqual(ctx.log, [GOLDEN_OPERATIONS, GOLDEN_DESCRIBE, "sleep 30",
                                   GOLDEN_DESCRIBE, GOLDEN_JOB, GOLDEN_DESCRIBE])
        self.assertEqual(r.lines[0], skill.RESUME_LINE % ("aleogr-shared", "aleogr-shared-zz99",
                                                          "creating"))
        self.assertIn("The night stop is proven: the job aleogr-shared-stop-weeknight stopped "
                      "the new instance.", r.lines)
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "stopped"})
        self.assertEqual(r.block["cost"], skill.COST)

    def test_running_instance_just_created(self):
        r, ctx = resume(described(True, "running"),
                        operations="BACKUP_VOLUME\nCREATE\n")
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes, [GOLDEN_JOB])

    def test_the_endings_of_the_wait_are_the_creations(self):
        # The budget of waiting spent while it is still being created: pending, it runs.
        r, ctx = resume(described(True, "creating"), states=("creating",))
        self.assertEqual(r.status, "pending")
        self.assertEqual(ctx.writes, [])
        self.assertEqual(r.block["pending"], [{"item": "instance", "reason": "manual",
                                               "how": STOP_HOW}])
        self.assertIn("The night stop was not tested.", r.lines)
        self.assertTrue(any("charged by the hour until it is stopped" in l for l in r.lines))
        self.assertTrue(ctx.wait_refused)

    def test_refused_for_an_instance_it_did_not_just_create(self):
        cases = (("running", "UPDATE\nCREATE\n", skill.RESUME_CHANGED),
                 ("running", "UPDATE\n", skill.RESUME_CHANGED),
                 ("running", "", skill.RESUME_CHANGED),
                 ("starting", "RESTART\nCREATE\n", skill.RESUME_CHANGED),
                 ("running", None, skill.RESUME_UNREAD),
                 ("stopped", "CREATE\n", skill.RESUME_STOPPED))
        for state, ops, why in cases:
            with self.subTest(state=state, ops=ops):
                r, ctx = resume(described(True, state), operations=ops)
                self.assertEqual(r.status, "unchanged")
                self.assertEqual(ctx.writes, [])  # never stopped by resume=yes
                self.assertNotIn("sleep 30", ctx.log)
                self.assertEqual(r.lines[1], skill.RESUME_REFUSED % why)
                self.assertEqual(r.block["outputs"], {"exists": True, "state": state})
                if state != "stopped":
                    self.assertIn(STOP_HOW, r.lines[2])
                    self.assertEqual(ctx.log, [GOLDEN_OPERATIONS])
                else:
                    self.assertEqual(ctx.log, [])  # a stopped instance: nothing read

    def test_a_missing_instance_is_never_created(self):
        # The caller's plan read the instance as existing: a describe that now says
        # missing may lag behind its creation, so with resume=yes it is never created
        # (this replaces the test that pinned "the creation runs as usual").
        r, ctx = resume(described(False), states=("running", "stopped"))
        self.assertEqual(r.status, "failed")
        self.assertEqual((ctx.writes, ctx.log), ([], []))  # no create, no read, no wait
        self.assertEqual(r.lines, [skill.RESUME_NOT_FOUND % (
            "aleogr-shared", "aleogr-shared-zz99", "was not found", DESCRIBE_HOW, STOP_HOW)])
        self.assertIn("nothing was created", r.lines[0])
        self.assertIn("charged by the hour while it runs", r.lines[0])
        self.assertEqual(r.block["outputs"], {"exists": None, "state": None})
        self.assertEqual(r.block["cost"], skill.COST)
        self.assertEqual(r.block["pending"], [])

    def test_a_failed_read_ends_the_same_way(self):
        for found in ({"status": "failed", "outputs": {"exists": None},
                       "answer": ["The instance aleogr-shared could not be read: gcloud "
                                  "failed."]},
                      {"status": "unchanged", "outputs": {}, "answer": []}):
            with self.subTest(found=found):
                r, ctx = resume(found)
                self.assertEqual(r.status, "failed")
                self.assertEqual((ctx.writes, ctx.log), ([], []))
                self.assertEqual(r.lines, [skill.RESUME_NOT_FOUND % (
                    "aleogr-shared", "aleogr-shared-zz99", "could not be read",
                    DESCRIBE_HOW, STOP_HOW)])
                self.assertEqual(r.block["cost"], skill.COST)

    def test_without_resume_a_missing_instance_is_created(self):
        r, ctx = run(found=described(False), stopJob="aleogr-shared-stop-weeknight")
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE, GOLDEN_JOB])
        self.assertNotIn(GOLDEN_OPERATIONS, ctx.log)

    def test_the_operations_read_is_a_read(self):
        argv = skill.operations_command("aleogr-shared-zz99", "aleogr-shared")
        self.assertEqual(" ".join(argv), GOLDEN_OPERATIONS)
        self.assertIsNone(common.read_refusal(argv))
        self.assertEqual(skill.invocation(dict(ARGS, resume="yes")).split(" ")[-1],
                         "resume=yes")

    def test_aborted_after_resume_says_it_runs(self):
        common.reset_wait_budget()
        args = dict(ARGS, resume="yes")
        ctx = ResumeContext(args, described(True, "creating"), ["creating"])
        real = ctx.read

        def read(argv, timeout=None):
            if argv[0] == "sleep":
                raise common.TimeLimit(argv)
            return real(argv, timeout)
        ctx.read = read
        r, code, why = common.run_skill(skill, dict(args), ctx)
        self.assertEqual((code, why), (common.EXIT_SOFTWARE, "time limit reached"))
        self.assertIn("It is not stopped: it runs and is charged by the hour until it is "
                      "stopped. Stop it with %s." % STOP_HOW, r.lines)


if __name__ == "__main__":
    unittest.main()
