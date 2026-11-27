"""Unit tests of gcp-cloud-sql_database-create: its golden command, the paths where no
write may be built (plan, an instance that is not running, a database that exists,
invalid arguments), and the decisions of the list after the create.

The context answers each read from a table of command prefixes (a list answers the calls
in order, its last item the later ones) and records each write that passed the allowlist.
No provider command runs. The scenarios sql-database-create-* cover the rest.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_database-create"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ARGS = {"sharedProjectId": "aleogr-shared-ab12", "instance": "aleogr-shared", "project": "demo",
        "environment": "dev", "mode": "apply"}
GOLDEN_CREATE = ("gcloud sql databases create demo_dev --instance=aleogr-shared "
                 "--project=aleogr-shared-ab12 --quiet")
DESCRIBE = "gcloud sql instances describe aleogr-shared --project=aleogr-shared-ab12 --format=json"
OPERATIONS = ("gcloud sql operations list --instance=aleogr-shared --project=aleogr-shared-ab12 "
              "--filter=status!=DONE --limit=10 --format=value(operationType,status)")
LIST = ("gcloud sql databases list --instance=aleogr-shared --project=aleogr-shared-ab12 "
        "--format=value(name)")
OK = common.Completed(0, "", "")
FAIL = common.Completed(1, "", "ERROR: some text")


def instance(policy="ALWAYS", state="RUNNABLE"):
    return common.Completed(0, json.dumps({"state": state,
                                           "settings": {"activationPolicy": policy}}), "")


def listing(*names):
    return common.Completed(0, "\n".join(("postgres",) + names) + "\n", "")


class FakeContext(common.Context):
    def __init__(self, args, answers, write=OK):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args)
        self.answers = {k: list(v) if isinstance(v, list) else [v] for k, v in answers.items()}
        self.write_answer = write
        self.log = []
        self.writes = []

    def execute(self, argv, timeout=None):
        self.writes.append(" ".join(argv))
        self.log.append(" ".join(argv))
        return self.write_answer

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.log.append(line)
        seq = self.answers.get(line)
        if not seq:
            return FAIL
        return seq.pop(0) if len(seq) > 1 else seq[0]


def run(answers=None, write=OK, **over):
    args = dict(ARGS, **over)
    args = {k: v for k, v in args.items() if v is not None}
    base = {DESCRIBE: instance(), OPERATIONS: OK, LIST: [listing(), listing("demo_dev")]}
    base.update(answers or {})
    ctx = FakeContext(args, base, write)
    return skill.run(dict(args), ctx), ctx


class TestGoldenCommand(unittest.TestCase):
    def test_the_create_as_the_skill_writes_it(self):
        r, ctx = run()
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE])
        self.assertEqual(ctx.log, [DESCRIBE, OPERATIONS, LIST, GOLDEN_CREATE, LIST])
        self.assertIsNone(common.write_refusal(SKILL, GOLDEN_CREATE.split(" "), root=ROOT))
        self.assertEqual(r.block["outputs"], {"instanceState": "running", "database": "demo_dev",
                                              "exists": True})
        self.assertEqual(len(r.block["resources"]), 2)

    def test_the_hyphen_of_the_project(self):
        self.assertEqual(skill.database_name("my-app", "dev"), "my_app_dev")
        argv = skill.create_command("my_app_dev", "aleogr-shared-ab12", "aleogr-shared")
        self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))


class TestNoWrite(unittest.TestCase):
    def test_plan(self):
        for mode in ("plan", None):
            r, ctx = run(mode=mode)
            self.assertEqual((r.status, ctx.writes), ("would-create", []))
            self.assertEqual(r.block["mode"], "plan")

    def test_invalid(self):
        r, ctx = run(project="My", environment="qa", mode="yes")
        self.assertEqual((r.status, ctx.log), ("failed", []))
        self.assertEqual(r.lines, ["project must have 1 to 14 lowercase letters, digits and "
                                   "hyphens, starting with a letter and not ending with a hyphen.",
                                   "environment must be dev, hom or prd.",
                                   "mode must be plan or apply."])
        self.assertEqual(r.block["mode"], "plan")
        self.assertIsNone(r.block["outputs"]["database"])
        r, ctx = run(sharedProjectId=None)
        self.assertEqual(r.lines, ["sharedProjectId is missing."])
        self.assertEqual(r.block["outputs"]["database"], "demo_dev")

    def test_an_instance_that_is_not_running(self):
        cases = [(instance("NEVER"), "stopped", "/aleogr:project-apply confirm=yes"),
                 (instance("ALWAYS", "PENDING_CREATE"), "creating",
                  "Wait a few minutes, then /aleogr:project-plan."),
                 (instance("ALWAYS", "MAINTENANCE"), "starting",
                  "Wait a few minutes, then /aleogr:project-plan."),
                 (instance("OTHER"), "unknown", "/aleogr:platform-plan")]
        for answer, state, how in cases:
            with self.subTest(state=state):
                r, ctx = run({DESCRIBE: answer})
                self.assertEqual((r.status, ctx.writes), ("pending", []))
                self.assertNotIn(LIST, ctx.log)
                self.assertEqual(r.block["pending"][0]["how"], how)
                self.assertEqual(r.block["outputs"]["instanceState"], state)

    def test_an_update_operation_means_starting(self):
        r, ctx = run({OPERATIONS: common.Completed(0, "UPDATE\tRUNNING\n", "")})
        self.assertEqual((r.status, ctx.writes), ("pending", []))
        self.assertEqual(r.block["outputs"]["instanceState"], "starting")

    def test_the_operations_cannot_be_checked(self):
        r, ctx = run({OPERATIONS: FAIL})
        self.assertEqual(r.status, "created")
        self.assertIn(skill.OPS_NOT_CHECKED, r.lines)

    def test_the_database_exists(self):
        r, ctx = run({LIST: listing("demo_dev")})
        self.assertEqual((r.status, ctx.writes), ("unchanged", []))

    def test_reads_that_fail(self):
        r, ctx = run({DESCRIBE: FAIL})
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertEqual(r.lines, [skill.INSTANCE_FAILED % "aleogr-shared"])
        self.assertEqual(r.block["resources"], [])
        r, ctx = run({LIST: FAIL})
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertIn(skill.LIST_FAILED % "aleogr-shared", r.lines)


class TestTheListDecides(unittest.TestCase):
    def test_every_case(self):
        cases = [
            (OK, [listing(), listing("demo_dev")], "created", None),
            (FAIL, [listing(), listing("demo_dev")], "created",
             skill.CREATE_FAILED_BUT_EXISTS % "demo_dev"),
            (OK, [listing()], "failed", skill.NOT_FOUND_AFTER % "demo_dev"),
            (FAIL, [listing()], "failed", skill.NOT_CREATED % ("demo_dev", "aleogr-shared")),
            (OK, [listing(), FAIL], "created", None),
            (FAIL, [listing(), FAIL], "failed", skill.FAILED_UNREAD % "demo_dev"),
        ]
        for write, lists, status, sentence in cases:
            with self.subTest(write=write.code, lists=len(lists), status=status):
                r, ctx = run({LIST: lists}, write=write)
                self.assertEqual(r.status, status)
                self.assertEqual(ctx.writes, [GOLDEN_CREATE])  # once, whatever its exit
                self.assertEqual(ctx.log.count(LIST), 2)
                if sentence:
                    self.assertIn(sentence, r.lines)
                self.assertNotIn("some text", "\n".join(r.lines))
        r, ctx = run({LIST: [listing(), FAIL]})
        self.assertEqual(r.block["pending"][0]["item"], "database")
        self.assertIsNone(r.block["outputs"]["exists"])


if __name__ == "__main__":
    unittest.main()
