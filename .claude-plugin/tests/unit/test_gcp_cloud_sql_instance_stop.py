"""Unit tests of gcp-cloud-sql_instance-stop: its golden commands, its gates (every
path that must not write builds no write command), and the paths no scenario covers.

The skill's run() is given a context whose call() answers for the describe skill, whose
read() answers from a dict, and whose execute() (where ctx.write runs a command that
passed the allowlist of writes) records the write. No provider command runs. The
scenarios sql-stop* cover the rest, in the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_instance-stop"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ARGS = {"projectId": "aleogr-shared-zz99", "instance": "aleogr-shared"}
DESCRIBE = "gcloud sql instances describe aleogr-shared --project=aleogr-shared-zz99 --format=json"

# The SKILL.md's commands, word for word (steps 2 and 3).
GOLDEN_PATCH = ("gcloud sql instances patch aleogr-shared --project=aleogr-shared-zz99 "
                "--activation-policy=NEVER --quiet")
GOLDEN_DESCRIBE = DESCRIBE


def described(state, exists=True, status="unchanged"):
    """What the describe skill gives (its --json document)."""
    return {"aleogr-result": 1, "status": status,
            "outputs": {"exists": exists, "state": state}, "answer": []}


def instance(policy, state="RUNNABLE"):
    return common.Completed(0, json.dumps({"state": state,
                                           "settings": {"activationPolicy": policy}}), "")


class FakeContext(common.Context):
    def __init__(self, args, found, answers=None, write_code=0, read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.found = found
        self.answers = answers or {}
        self.write_code = write_code
        self.called = []
        self.reads = []
        self.writes = []

    def call(self, command, name, args=None, timeout=None):
        self.called.append((command, name, dict(args or {})))
        return self.found

    def execute(self, argv, timeout=None):
        # Reached only through ctx.write, after the allowlist of writes accepted argv.
        self.writes.append(list(argv))
        return common.Completed(self.write_code, "", "ERROR: PERMISSION_DENIED"
                                if self.write_code else "")

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.reads.append(line)
        return self.answers.get(line, common.Completed(1, "", "ERROR"))


def run(found=None, answers=None, write_code=0, **over):
    args = dict(ARGS, **over)
    args = {k: v for k, v in args.items() if v is not None}
    ctx = FakeContext(args, found if found is not None else described("running"),
                      answers if answers is not None else {DESCRIBE: instance("NEVER")},
                      write_code)
    return skill.run(dict(args), ctx), ctx


class TestGoldenCommands(unittest.TestCase):
    def test_the_patch_and_the_verification_as_the_skill_writes_them(self):
        r, ctx = run()
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [GOLDEN_PATCH.split(" ")])
        self.assertEqual(ctx.reads, [GOLDEN_DESCRIBE])
        for argv in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))
        self.assertEqual(ctx.called, [(PLUGIN, "gcp-cloud-sql_instance-describe",
                                       {"projectId": "aleogr-shared-zz99",
                                        "instance": "aleogr-shared"})])
        self.assertEqual(skill.patch_command("aleogr-shared-zz99", "aleogr-shared"),
                         GOLDEN_PATCH.split(" "))

    def test_the_patch_is_this_skill_s_and_instance_create_s_only(self):
        argv = skill.patch_command("aleogr-shared-zz99", "aleogr-shared")
        for name in common.WRITE_SHAPES:
            allowed = common.write_refusal(name, argv) is None
            self.assertEqual(allowed, name in (SKILL, "gcp-cloud-sql_instance-create"), name)


class TestGates(unittest.TestCase):
    """No write command is built unless the arguments are valid, the check read the
    instance, and its state calls for a stop."""

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
            self.assertEqual(r.block["resources"], [])

    def test_an_argument_with_another_value(self):
        for over in ({"projectId": "Bad"}, {"projectId": "ab"}, {"projectId": "abcdef-"},
                     {"instance": "Aleogr"}, {"instance": "1x"}, {"instance": "a" * 61}):
            with self.subTest(over=over):
                r, ctx = run(**over)
                self.assert_no_write(r, ctx)
                self.assertEqual((ctx.called, ctx.reads), ([], []))
                self.assertEqual(len(r.lines), 1)
                self.assertTrue(r.lines[0].startswith(list(over)[0] + " is not valid"))

    def test_a_mode_other_than_apply(self):
        # The skill has no mode; one given that is not apply would be a run that may not
        # write: it ends before any command, with one sentence.
        for mode in ("plan", ""):
            r, ctx = run(mode=mode)
            self.assert_no_write(r, ctx)
            self.assertEqual(r.lines, [skill.NO_MODE])
            self.assertEqual(ctx.called, [])
        r, ctx = run(mode="apply")
        self.assertEqual(r.status, "updated")

    def test_read_only_refuses_it(self):
        ctx = FakeContext(ARGS, described("running"), read_only=True)
        self.assertFalse(ctx.writable)
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.patch_command("aleogr-shared-zz99", "aleogr-shared"))
        self.assertEqual(ctx.writes, [])

    def test_the_check_failed(self):
        failed = {"aleogr-result": 1, "status": "failed", "outputs": {"exists": None},
                  "answer": ["The instance aleogr-shared could not be read: gcloud failed."]}
        r, ctx = run(found=failed)
        self.assert_no_write(r, ctx)
        self.assertEqual(r.lines, failed["answer"])
        self.assertEqual(r.block["outputs"], {"exists": None, "state": None})
        self.assertEqual(r.block["resources"], [])
        missing = common._call_failure("not-found", PLUGIN, "x", "The command was not found.")
        r, ctx = run(found=missing)
        self.assert_no_write(r, ctx)
        self.assertEqual(r.lines, ["The command was not found."])

    def test_the_instance_does_not_exist(self):
        r, ctx = run(found=described(None, exists=False))
        self.assert_no_write(r, ctx)
        self.assertEqual(r.block["outputs"], {"exists": False, "state": None})
        self.assertEqual(r.block["resources"], [])
        self.assertIn("does not exist", r.lines[0])

    def test_already_stopped(self):
        r, ctx = run(found=described("stopped"))
        self.assert_no_write(r, ctx, "unchanged")
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "stopped"})
        self.assertEqual(len(r.block["resources"]), 1)
        self.assertEqual(ctx.reads, [])

    def test_still_being_created(self):
        r, ctx = run(found=described("creating"))
        self.assert_no_write(r, ctx)
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "creating"})
        self.assertIn("wait for the creation to end, then run this skill again", r.lines[0])


class TestPaths(unittest.TestCase):
    def test_states_that_are_stopped(self):
        for state in ("running", "starting", "unknown"):
            with self.subTest(state=state):
                r, ctx = run(found=described(state))
                self.assertEqual((r.status, len(ctx.writes)), ("updated", 1))

    def test_a_patch_that_fails_is_not_described_again(self):
        r, ctx = run(write_code=1)
        self.assertEqual(r.status, "failed")
        self.assertEqual(ctx.reads, [])
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "running"})
        self.assertEqual(len(r.block["resources"]), 1)
        self.assertNotIn("PERMISSION_DENIED", "\n".join(r.lines))
        self.assertEqual(r.lines, ["The instance aleogr-shared could not be stopped: the "
                                   "active gcloud account is not allowed to change it."])

    def test_a_verification_that_does_not_show_stopped(self):
        r, ctx = run(answers={DESCRIBE: instance("ALWAYS", "RUNNABLE")})
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "running"})
        self.assertEqual(len(ctx.reads), 1)
        r, ctx = run(answers={})
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.block["outputs"], {"exists": True, "state": "running"})
        self.assertEqual(len(ctx.reads), 1)

    def test_the_state_table(self):
        cases = [({"settings": {"activationPolicy": "NEVER"}, "state": "RUNNABLE"}, "stopped"),
                 ({"settings": {"activationPolicy": "ALWAYS"}, "state": "RUNNABLE"}, "running"),
                 ({"settings": {"activationPolicy": "ALWAYS"}, "state": "PENDING_CREATE"},
                  "creating"),
                 ({"settings": {"activationPolicy": "ALWAYS"}, "state": "MAINTENANCE"},
                  "starting"),
                 ({"settings": {}}, "unknown"), ({}, "unknown")]
        for data, want in cases:
            self.assertEqual(skill.state_of(data), want, data)


if __name__ == "__main__":
    unittest.main()
