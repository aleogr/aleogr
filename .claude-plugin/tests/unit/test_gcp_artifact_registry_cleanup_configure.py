"""Unit tests of gcp-artifact-registry_cleanup-configure: its golden commands, its gates
(every path that must not write builds no write command and writes no file), the
comparison, and the paths no scenario covers. The scenarios registry-cleanup-* cover the
rest, in the direct mode.

The context's read() answers from a list, execute() (reached only through ctx.write,
after the allowlist of writes) records the write, and write_temp_file() writes into a
folder of the test instead of the system's temporary folder. No provider command runs.
"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-registry-gcp-artifact-registry"
SKILL = "gcp-artifact-registry_cleanup-configure"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

P = "aleogr-dev-demo-ab12"
ARGS = {"projectId": P, "project": "demo", "region": "us-central1", "keep": "5",
        "mode": "apply"}
SHIPPED = os.path.join(ROOT, "files", "cleanup-policy.json")
TEMP = common.system_temp_dir()

# The SKILL.md's commands, word for word (steps 1, 3 and 4), the quotes of a value removed.
GOLDEN_DESCRIBE = ("gcloud artifacts repositories describe demo --location=us-central1 "
                   "--project=%s --format=json" % P)
GOLDEN_SET = ("gcloud artifacts repositories set-cleanup-policies demo --location=us-central1 "
              "--project=%s --policy=%%s --no-dry-run" % P)


def keep_rule(n=5, **extra):
    rule = {"action": "KEEP", "id": "keep-most-recent", "mostRecentVersions": {"keepCount": n}}
    rule.update(extra)
    return rule


def delete_rule(**extra):
    rule = {"action": "DELETE", "id": "delete-the-rest", "condition": {"tagState": "ANY"}}
    rule.update(extra)
    return rule


def repo(policies=None, dry_run=None):
    data = {"format": "DOCKER",
            "name": "projects/%s/locations/us-central1/repositories/demo" % P}
    if policies is not None:
        data["cleanupPolicies"] = dict(("r%d" % i, p) for i, p in enumerate(policies))
    if dry_run is not None:
        data["cleanupPolicyDryRun"] = dry_run
    return common.Completed(0, "Encryption: Google-managed key\n" + json.dumps(data), "")


DECLARED = [keep_rule(), delete_rule()]


class FakeContext(common.Context):
    def __init__(self, args, reads, write=None, read_only=False, folder=None):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.answers = list(reads)
        self.write_answer = write or common.Completed(0, "Dry run is disabled.", "")
        self.folder = folder
        self.reads = []
        self.writes = []
        self.files = []

    def execute(self, argv, timeout=None):
        self.writes.append(list(argv))
        return self.write_answer

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        self.reads.append(" ".join(argv))
        return self.answers.pop(0) if self.answers else common.Completed(1, "", "ERROR")

    def write_temp_file(self, name, content):
        self._may_write("write %s" % name)
        written = common.write_temp_file(self.skill, name, content, stream=io.StringIO(),
                                         folder=self.folder)
        self.files.append((name, content))
        return os.path.join(TEMP, name) if written else None


class Base(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def run_skill(self, reads=None, write=None, **over):
        args = dict(ARGS, **over)
        args = {k: v for k, v in args.items() if v is not None}
        ctx = FakeContext(args, reads if reads is not None else [repo(), repo(DECLARED)],
                          write, folder=self.folder)
        return skill.run(dict(args), ctx), ctx


class TestGoldenCommands(Base):
    def test_keep_5_uses_the_plugin_s_own_file(self):
        r, ctx = self.run_skill()
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [(GOLDEN_SET % SHIPPED).split(" ")])
        self.assertEqual(ctx.reads, [GOLDEN_DESCRIBE, GOLDEN_DESCRIBE])
        self.assertEqual(ctx.files, [])
        for argv in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))
        self.assertEqual(r.block["outputs"], {"keep": 5, "dryRun": False})
        self.assertEqual(r.block["pending"], [])
        self.assertEqual(r.block["cost"], skill.COST)
        self.assertEqual(r.block["resources"], [
            {"type": "cleanup-policy", "id": "%s/us-central1/demo" % P, "name": "demo"}])

    def test_another_keep_writes_the_temporary_file_right_before_the_set(self):
        r, ctx = self.run_skill(keep="12", reads=[repo(), repo([keep_rule(12), delete_rule()])])
        self.assertEqual(r.status, "updated")
        path = os.path.join(TEMP, "aleogr-cleanup-policy-keep-12.json")
        self.assertEqual(ctx.writes, [(GOLDEN_SET % path).split(" ")])
        self.assertIsNone(common.write_refusal(SKILL, ctx.writes[0], root=ROOT))
        with open(SHIPPED, encoding="utf-8") as f:
            shipped = f.read()
        want = shipped.replace('"keepCount": 5', '"keepCount": 12')
        self.assertEqual(ctx.files, [("aleogr-cleanup-policy-keep-12.json", want)])
        with open(os.path.join(self.folder, "aleogr-cleanup-policy-keep-12.json"),
                  encoding="utf-8") as f:
            self.assertEqual(f.read(), want)
        self.assertEqual(json.loads(want)[0]["mostRecentVersions"]["keepCount"], 12)
        self.assertIn('    "mostRecentVersions": { "keepCount": 12 }', r.lines)

    def test_the_set_is_this_skill_s_only(self):
        argv = skill.set_command(P, "demo", "us-central1", SHIPPED)
        for name in common.WRITE_SHAPES:
            self.assertEqual(common.write_refusal(name, argv, root=ROOT) is None,
                             name == SKILL, name)

    def test_never_dry_run(self):
        argv = skill.set_command(P, "demo", "us-central1", SHIPPED)
        self.assertIn("--no-dry-run", argv)
        self.assertNotIn("--dry-run", argv)


class TestGates(Base):
    def assert_no_write(self, r, ctx, status="failed"):
        self.assertEqual(r.status, status)
        self.assertEqual(ctx.writes, [])
        self.assertEqual(ctx.files, [])
        self.assertEqual(os.listdir(self.folder), [])
        self.assertEqual(r.block["cost"], skill.COST)

    def test_mode_absent_is_a_plan(self):
        for keep in ("5", "3"):
            r, ctx = self.run_skill(mode=None, keep=keep)
            self.assert_no_write(r, ctx, "would-update")
            self.assertEqual(r.block["mode"], "plan")
            self.assertEqual(ctx.reads, [GOLDEN_DESCRIBE])
            self.assertIn('    "mostRecentVersions": { "keepCount": %s }' % keep, r.lines)

    def test_mode_with_another_value(self):
        for mode in ("Apply", "", "yes"):
            with self.subTest(mode=mode):
                r, ctx = self.run_skill(mode=mode)
                self.assert_no_write(r, ctx)
                self.assertEqual(r.lines, ["mode must be plan or apply."])
                self.assertEqual(ctx.reads, [])
                self.assertEqual(r.block["outputs"], {"keep": None, "dryRun": None})

    def test_read_only_refuses_the_writes(self):
        ctx = FakeContext(ARGS, [], read_only=True, folder=self.folder)
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.set_command(P, "demo", "us-central1", SHIPPED))
        with self.assertRaises(common.WriteRefused):
            ctx.write_temp_file("aleogr-cleanup-policy-keep-3.json", "[]")
        self.assertEqual((ctx.writes, ctx.files), ([], []))

    def test_arguments(self):
        cases = [({"projectId": None}, "projectId is missing."),
                 ({"region": ""}, "region is missing."),
                 ({"keep": None}, "keep is missing."),
                 ({"projectId": "1abcdef"}, "projectId is not a GCP project id."),
                 ({"project": "Demo"}, "project must have 1 to 14"),
                 ({"region": "europe"}, "region is not a Google Cloud region name")]
        for keep in ("0", "abc", "5.0", "-1", "051", "51", "05", "100"):
            cases.append(({"keep": keep}, "keep must be a whole number from 1 to 50."))
        for over, line in cases:
            with self.subTest(over=over):
                r, ctx = self.run_skill(**over)
                self.assert_no_write(r, ctx)
                self.assertTrue(r.lines[0].startswith(line), r.lines)
                self.assertEqual(ctx.reads, [])
        for keep in ("1", "50", "9", "10"):
            r, ctx = self.run_skill(keep=keep, mode="plan")
            self.assertEqual(r.status, "would-update")

    def test_missing_repository_and_failed_read(self):
        missing = common.Completed(1, "ERROR: NOT_FOUND: Requested entity was not found.", "")
        r, ctx = self.run_skill(reads=[missing])
        self.assert_no_write(r, ctx)
        self.assertEqual(r.lines, [skill.MISSING % ("demo", "us-central1")])
        for answer in (common.Completed(1, "", "ERROR: PERMISSION_DENIED (or it may not exist)"),
                       common.Completed(0, "not json", "")):
            r, ctx = self.run_skill(reads=[answer])
            self.assert_no_write(r, ctx)
            self.assertEqual(r.lines, [skill.READ_FAILED % P])
            self.assertEqual(r.block["resources"], [])

    def test_as_declared_runs_nothing_more(self):
        for mode in ("plan", "apply"):
            r, ctx = self.run_skill(reads=[repo(DECLARED, dry_run=False)], mode=mode)
            self.assert_no_write(r, ctx, "unchanged")
            self.assertEqual(ctx.reads, [GOLDEN_DESCRIBE])
            self.assertEqual(r.block["outputs"], {"keep": 5, "dryRun": False})


class TestComparing(unittest.TestCase):
    def policy(self, policies, dry_run=None, keep=5):
        data = json.loads(repo(policies, dry_run).out.split("\n", 1)[1])
        return skill.Policy(data, keep)

    def test_as_declared(self):
        self.assertTrue(self.policy(DECLARED).as_declared)
        self.assertTrue(self.policy([delete_rule(), keep_rule()]).as_declared)
        self.assertTrue(self.policy([keep_rule(action="keep"),
                                     delete_rule(condition={"tagState": "any"})]).as_declared)
        self.assertTrue(self.policy([keep_rule(mostRecentVersions={"keepCount": "5"}),
                                     delete_rule()]).as_declared)
        self.assertTrue(self.policy(DECLARED, dry_run=False).as_declared)

    def test_differs(self):
        cases = [
            ([keep_rule(3), delete_rule()], None),
            ([keep_rule()], None),
            ([delete_rule()], None),
            (DECLARED + [delete_rule(id="x")], None),
            (DECLARED, True),
            ([keep_rule(condition={"tagState": "TAGGED"}), delete_rule()], None),
            ([keep_rule(mostRecentVersions={"keepCount": 5, "packageNamePrefixes": ["a"]}),
              delete_rule()], None),
            ([keep_rule(), delete_rule(condition={"tagState": "ANY", "olderThan": "1d"})], None),
            ([keep_rule(), delete_rule(mostRecentVersions={"keepCount": 1})], None),
            ([], None),
        ]
        for policies, dry in cases:
            with self.subTest(policies=policies, dry=dry):
                p = self.policy(policies, dry)
                self.assertFalse(p.as_declared)
                self.assertTrue(p.differences(5))
        p = skill.Policy({"format": "DOCKER"}, 5)
        self.assertFalse(p.as_declared)
        self.assertEqual(p.outputs(), {"keep": None, "dryRun": False})

    def test_outputs(self):
        self.assertEqual(self.policy([keep_rule(3), delete_rule()]).outputs(),
                         {"keep": 3, "dryRun": False})
        self.assertEqual(self.policy([keep_rule(3), keep_rule(4, id="k2")]).outputs()["keep"],
                         None)
        self.assertEqual(self.policy(DECLARED, dry_run=True).outputs(),
                         {"keep": 5, "dryRun": True})


class TestPaths(Base):
    def test_a_failed_set_says_only_the_sentence(self):
        r, ctx = self.run_skill(write=common.Completed(1, "", "ERROR: PERMISSION_DENIED"))
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.lines, [skill.SET_FAILED])
        self.assertEqual(ctx.reads, [GOLDEN_DESCRIBE])
        self.assertEqual(r.block["outputs"], {"keep": None, "dryRun": None})
        self.assertEqual(r.block["resources"], [])

    def test_a_temporary_file_that_cannot_be_written(self):
        os.symlink(os.path.join(self.folder, "elsewhere"),
                   os.path.join(self.folder, "aleogr-cleanup-policy-keep-3.json"))
        r, ctx = self.run_skill(keep="3")
        self.assertEqual(r.status, "failed")
        self.assertEqual(ctx.writes, [])
        self.assertTrue(r.lines[0].startswith("The policy file "))

    def test_a_read_back_that_differs_or_fails_is_pending(self):
        how = ("/aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_cleanup-configure "
               "projectId=%s project=demo region=us-central1 keep=5 mode=plan" % P)
        r, ctx = self.run_skill(reads=[repo([keep_rule(3)]), repo(DECLARED, dry_run=True)])
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.block["outputs"], {"keep": 5, "dryRun": True})
        self.assertEqual(r.block["pending"], [{"item": "cleanup policy of demo read back",
                                               "reason": "manual", "how": how}])
        # A failed read back: the outputs are step 1's.
        r, ctx = self.run_skill(reads=[repo([keep_rule(3)])])
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.block["outputs"], {"keep": 3, "dryRun": False})
        self.assertEqual(len(r.block["pending"]), 1)
        self.assertEqual(len(ctx.reads), 2)


if __name__ == "__main__":
    unittest.main()
