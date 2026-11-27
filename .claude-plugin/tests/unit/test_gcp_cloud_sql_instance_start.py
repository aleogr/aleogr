"""Unit tests of gcp-cloud-sql_instance-start: its golden commands, its gates (a start is
charged by the hour: no patch is built unless the arguments are valid, the check read the
instance and its state is stopped), and the paths no scenario covers.

The skill's run() is given a context whose call() answers for the describe skill, whose
read() answers the describe from a dict, and whose execute() (reached only through
ctx.write) records the write. No provider command runs. The scenarios sql-start* cover
the rest, in the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_instance-start"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ARGS = {"projectId": "aleogr-shared-zz99", "instance": "aleogr-shared"}
GOLDEN_PATCH = ("gcloud sql instances patch aleogr-shared --project=aleogr-shared-zz99 "
                "--activation-policy=ALWAYS --async --quiet")
GOLDEN_DESCRIBE = ("gcloud sql instances describe aleogr-shared --project=aleogr-shared-zz99 "
                   "--format=json")
STOP_HOW = ("/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-stop "
            "projectId=aleogr-shared-zz99 instance=aleogr-shared")
COST_LINE = "While it runs it is charged by the hour, until it is stopped with %s." % STOP_HOW
DESCRIBE_HOW = ("/aleogr-db-gcp-cloud-sql:gcp-cloud-sql_instance-describe "
                "projectId=aleogr-shared-zz99 instance=aleogr-shared")


def described(state, exists=True, status="unchanged", answer=()):
    return {"aleogr-result": 1, "status": status, "outputs": {"exists": exists, "state": state},
            "answer": list(answer)}


def instance(policy, state="RUNNABLE"):
    return common.Completed(0, json.dumps({"state": state,
                                           "settings": {"activationPolicy": policy}}), "")


class FakeContext(common.Context):
    def __init__(self, args, found, answer=None, write_code=0, read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.found = found
        self.answer = answer
        self.write_code = write_code
        self.called = []
        self.reads = []
        self.writes = []

    def call(self, command, name, args=None, timeout=None):
        self.called.append((command, name, dict(args or {})))
        return self.found

    def execute(self, argv, timeout=None):
        self.writes.append(" ".join(argv))
        return common.Completed(self.write_code, "", "ERROR: PERMISSION_DENIED"
                                if self.write_code else "")

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        self.reads.append(" ".join(argv))
        return self.answer if self.answer is not None else common.Completed(1, "", "ERROR")


def run(found=None, answer=None, write_code=0, **over):
    args = dict(ARGS, **over)
    args = {k: v for k, v in args.items() if v is not None}
    ctx = FakeContext(args, found if found is not None else described("stopped"),
                      answer if answer is not None else instance("ALWAYS", "MAINTENANCE"),
                      write_code)
    return skill.run(dict(args), ctx), ctx


class TestGoldenCommands(unittest.TestCase):
    def test_the_patch_and_the_verification_as_the_skill_writes_them(self):
        r, ctx = run()
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [GOLDEN_PATCH])
        self.assertEqual(ctx.reads, [GOLDEN_DESCRIBE])
        self.assertEqual(skill.patch_command("aleogr-shared-zz99", "aleogr-shared"),
                         GOLDEN_PATCH.split(" "))
        self.assertIsNone(common.write_refusal(SKILL, GOLDEN_PATCH.split(" "), root=ROOT))
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "starting"})
        self.assertEqual(r.block["cost"], skill.COST)
        # The cost sentence comes before the lines that report the start.
        self.assertIn("charged by the hour", r.lines[0])
        self.assertIn("twelve minutes", "\n".join(r.lines))

    def test_always_is_this_skill_s_only(self):
        argv = GOLDEN_PATCH.split(" ")
        for name in common.WRITE_SHAPES:
            self.assertEqual(common.write_refusal(name, argv) is None, name == SKILL, name)


class TestGates(unittest.TestCase):
    def assert_no_write(self, r, ctx, status="failed"):
        self.assertEqual(r.status, status)
        self.assertEqual(ctx.writes, [])
        self.assertEqual(r.block["mode"], "apply")
        self.assertEqual(r.block["cost"], skill.COST)

    def test_an_argument_missing(self):
        for key in ("projectId", "instance"):
            r, ctx = run(**{key: None})
            self.assert_no_write(r, ctx)
            self.assertEqual(r.lines, ["%s is missing." % key])
            self.assertEqual((ctx.called, ctx.reads), ([], []))
            self.assertEqual(r.block["outputs"], {"exists": None, "state": None})

    def test_an_argument_with_another_value(self):
        for over in ({"projectId": "Bad"}, {"projectId": "abcdef-"}, {"instance": "1x"},
                     {"instance": "a" * 61}):
            with self.subTest(over=over):
                r, ctx = run(**over)
                self.assert_no_write(r, ctx)
                self.assertEqual((ctx.called, ctx.reads), ([], []))

    def test_a_mode_other_than_apply(self):
        for mode in ("plan", ""):
            r, ctx = run(mode=mode)
            self.assert_no_write(r, ctx)
            self.assertEqual(r.lines, [skill.NO_MODE])
            self.assertEqual(ctx.called, [])

    def test_read_only_refuses_it(self):
        ctx = FakeContext(ARGS, described("stopped"), read_only=True)
        with self.assertRaises(common.WriteRefused):
            ctx.write(GOLDEN_PATCH.split(" "))
        self.assertEqual(ctx.writes, [])

    def test_the_check_failed_or_missing(self):
        r, ctx = run(found=described(None, exists=None, status="failed"))
        self.assert_no_write(r, ctx)
        self.assertEqual(r.lines, [skill.NOT_READ])
        r, ctx = run(found=described(None, exists=False))
        self.assert_no_write(r, ctx)
        self.assertEqual(r.lines, [skill.MISSING])
        self.assertEqual(r.block["outputs"], {"exists": False, "state": None})

    def test_already_running_starting_or_creating(self):
        for state in ("running", "starting", "creating"):
            with self.subTest(state=state):
                r, ctx = run(found=described(state))
                self.assert_no_write(r, ctx, "unchanged")
                self.assertEqual(r.block["outputs"], {"exists": True, "state": state})
                self.assertEqual(ctx.reads, [])
                self.assertIn("charged by the hour", "\n".join(r.lines))

    def test_an_unknown_state(self):
        r, ctx = run(found=described("unknown", answer=[
            "The Cloud SQL instance aleogr-shared in aleogr-shared-zz99 is unknown.",
            "Its activation policy is ON_DEMAND, which is not a known value."]))
        self.assert_no_write(r, ctx)
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "unknown"})
        self.assertEqual(r.lines, ["The instance aleogr-shared was not started: its activation "
                                   "policy is ON_DEMAND, which is not a known value."])
        r, ctx = run(found=described("unknown", answer=["Its activation policy is absent."]))
        self.assertEqual(r.lines, ["The instance aleogr-shared was not started: its activation "
                                   "policy is absent."])


class TestPaths(unittest.TestCase):
    def test_a_failed_patch_read_back(self):
        r, ctx = run(write_code=1, answer=instance("ALWAYS"))
        self.assertEqual((r.status, r.block["outputs"]["state"]), ("updated", "starting"))
        self.assertIn(skill.FAILED_BUT_STARTING, r.lines)
        self.assertEqual(len(ctx.reads), 1)
        r, ctx = run(write_code=1, answer=instance("NEVER"))
        self.assertEqual((r.status, r.block["outputs"]["state"]), ("failed", "stopped"))
        self.assertEqual(r.lines, [skill.FAILED_STILL_STOPPED])
        for answer in (common.Completed(1, "", "x"), instance("OTHER")):
            r, ctx = run(write_code=1, answer=answer)
            self.assertEqual((r.status, r.block["outputs"]), ("failed",
                                                              {"exists": True, "state": None}))
            # It may run: the hourly cost and the command that stops it come first.
            self.assertEqual(r.lines[0], COST_LINE)
            self.assertEqual(r.lines[1], skill.FAILED_UNREAD)
            self.assertIn(DESCRIBE_HOW, r.lines[2])
            self.assertNotIn("PERMISSION_DENIED", "\n".join(r.lines))
        self.assertEqual(len(ctx.writes), 1)

    def test_the_verification(self):
        r, ctx = run(answer=instance("NEVER"))
        self.assertEqual((r.status, r.block["outputs"]["state"]), ("updated", "stopped"))
        self.assertIn("for a moment", "\n".join(r.lines))
        r, ctx = run(answer=instance("ALWAYS", "RUNNABLE"))
        self.assertEqual(r.block["outputs"]["state"], "starting")
        r, ctx = run(answer=common.Completed(1, "", "x"))
        self.assertEqual((r.status, r.block["outputs"]["state"]), ("updated", None))
        self.assertIn("could not be read", "\n".join(r.lines))



class TimeLimitContext(FakeContext):
    """The run's time limit is reached while the patch (`at="patch"`) or the read after
    it (`at="read"`) is still running."""

    def __init__(self, at):
        FakeContext.__init__(self, dict(ARGS), described("stopped"))
        self.at = at

    def execute(self, argv, timeout=None):
        self.writes.append(" ".join(argv))
        if self.at == "patch":
            raise common.TimeLimit(argv)
        return common.Completed(0, "", "")

    def read(self, argv, timeout=None):
        raise common.TimeLimit(argv)


class TestAborted(unittest.TestCase):
    def test_the_time_limit_after_the_patch_names_the_hourly_cost(self):
        for at in ("patch", "read"):
            with self.subTest(at=at):
                ctx = TimeLimitContext(at)
                r, code, why = common.run_skill(skill, dict(ARGS), ctx)
                self.assertEqual((code, why), (common.EXIT_SOFTWARE, "time limit reached"))
                self.assertEqual(r.status, "failed")
                self.assertEqual(r.block["cost"], common.ABORTED_COST)
                self.assertEqual(r.block["mode"], "apply")
                self.assertEqual(r.lines, [
                    common.TIME_LIMIT_SENTENCE,
                    "Before it stopped, this run had already run these writes: `%s`."
                    % GOLDEN_PATCH,
                    COST_LINE, common.READ_STATE_SENTENCE])

    def test_a_run_that_ends_normally_clears_it(self):
        r, ctx = run()
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.abort_lines, [])

    def test_before_the_patch_nothing_is_registered(self):
        ctx = FakeContext(dict(ARGS), described("stopped"))

        def call(*a, **k):
            raise common.TimeLimit(["aleogr-db-gcp-cloud-sql", "--json", "x"])

        ctx.call = call
        r, code, _ = common.run_skill(skill, dict(ARGS), ctx)
        self.assertEqual(r.lines, [common.TIME_LIMIT_SENTENCE, common.REFUSED_NOTHING_WRITTEN,
                                   common.READ_STATE_SENTENCE])


if __name__ == "__main__":
    unittest.main()
