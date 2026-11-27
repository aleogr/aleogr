"""Unit tests of gcp-artifact-registry_repository-create: its golden commands, its gates
(every path that must not write builds no write command), and the paths no scenario
covers. The scenarios registry-create-* cover the rest, in the direct mode.

The skill's run() is given a context whose call() answers for the describe skill, whose
read() answers from a dict, and whose execute() (where ctx.write runs a command that
passed the allowlist of writes) records the write. No provider command runs.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-registry-gcp-artifact-registry"
SKILL = "gcp-artifact-registry_repository-create"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

P = "aleogr-dev-demo-ab12"
ARGS = {"projectId": P, "project": "demo", "environment": "dev", "region": "us-central1",
        "mode": "apply"}
PATH = "us-central1-docker.pkg.dev/%s/demo" % P

# The SKILL.md's commands, word for word (steps 3 and 4), the quotes of a value removed.
GOLDEN_CREATE = ("gcloud artifacts repositories create demo --project=%s "
                 "--location=us-central1 --repository-format=docker "
                 "--labels=aleogr-project=demo,aleogr-environment=dev" % P)
GOLDEN_READ_BACK = ("gcloud artifacts repositories describe demo --location=us-central1 "
                    "--project=%s --format=json(name,format,labels)" % P)

REPO = {"name": "projects/%s/locations/us-central1/repositories/demo" % P,
        "format": "DOCKER", "labels": {"aleogr-project": "demo", "aleogr-environment": "dev"}}


def described(exists=False, fmt="DOCKER", others=(), status="unchanged"):
    out = {"exists": exists, "otherRegions": list(others), "format": fmt if exists else None,
           "region": "us-central1" if exists else None,
           "labels": dict(REPO["labels"]) if exists else {},
           "imagePath": PATH if exists and fmt == "DOCKER" else None}
    return {"aleogr-result": 1, "status": status, "outputs": out, "answer": []}


def ok(obj):
    return common.Completed(0, "Encryption: Google-managed key\n" + json.dumps(obj), "")


class FakeContext(common.Context):
    def __init__(self, args, found, answers=None, write=None, read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.found = found
        self.answers = answers or {}
        self.write_answer = write or common.Completed(0, "Created repository [demo].", "")
        self.called = []
        self.reads = []
        self.writes = []

    def call(self, command, name, args=None, timeout=None):
        self.called.append((command, name, dict(args or {})))
        return self.found

    def execute(self, argv, timeout=None):
        # Reached only through ctx.write, after the allowlist of writes accepted argv.
        self.writes.append(list(argv))
        return self.write_answer

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.reads.append(line)
        return self.answers.get(line, common.Completed(1, "", "ERROR"))


def run(found=None, answers=None, write=None, **over):
    args = dict(ARGS, **over)
    args = {k: v for k, v in args.items() if v is not None}
    ctx = FakeContext(args, found if found is not None else described(),
                      answers if answers is not None else {GOLDEN_READ_BACK: ok(REPO)}, write)
    return skill.run(dict(args), ctx), ctx


class TestGoldenCommands(unittest.TestCase):
    def test_the_create_and_the_read_back_as_the_skill_writes_them(self):
        r, ctx = run()
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE.split(" ")])
        self.assertEqual(ctx.reads, [GOLDEN_READ_BACK])
        for argv in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))
        self.assertEqual(ctx.called, [(PLUGIN, "gcp-artifact-registry_registry-describe",
                                       {"projectId": P, "project": "demo",
                                        "region": "us-central1"})])
        self.assertEqual(r.block["outputs"], {"imagePath": PATH})
        self.assertEqual(r.block["resources"], [
            {"type": "repository", "id": "%s/us-central1/demo" % P, "name": "demo",
             "labels": {"aleogr-project": "demo", "aleogr-environment": "dev"}}])
        self.assertEqual(r.block["pending"], [])
        self.assertEqual(r.block["cost"], skill.COST)

    def test_the_create_is_this_skill_s_only(self):
        argv = skill.create_command(P, "demo", "dev", "us-central1")
        for name in common.WRITE_SHAPES:
            self.assertEqual(common.write_refusal(name, argv) is None, name == SKILL, name)

    def test_no_async(self):
        self.assertNotIn("--async", skill.create_command(P, "demo", "prd", "us-central1"))


class TestGates(unittest.TestCase):
    """No write command is built unless mode=apply, the arguments are valid and the check
    found no repository of that id anywhere."""

    def assert_no_write(self, r, ctx, status="failed"):
        self.assertEqual(r.status, status)
        self.assertEqual(ctx.writes, [])
        self.assertEqual(r.block["cost"], skill.COST)

    def test_mode_absent_is_a_plan(self):
        r, ctx = run(mode=None)
        self.assert_no_write(r, ctx, "would-create")
        self.assertEqual(r.block["mode"], "plan")
        self.assertEqual(r.block["outputs"], {"imagePath": PATH})
        self.assertEqual(r.block["resources"], [])
        self.assertEqual(ctx.reads, [])

    def test_mode_plan(self):
        r, ctx = run(mode="plan")
        self.assert_no_write(r, ctx, "would-create")
        self.assertIn(skill.COST_LINE, r.lines)

    def test_mode_with_another_value(self):
        for mode in ("Apply", "yes", "", "dry-run"):
            with self.subTest(mode=mode):
                r, ctx = run(mode=mode)
                self.assert_no_write(r, ctx)
                self.assertEqual(r.block["mode"], "plan")
                self.assertEqual(r.lines, ["mode must be plan or apply."])
                self.assertEqual(ctx.called, [])

    def test_read_only_refuses_the_write(self):
        ctx = FakeContext(ARGS, described(), read_only=True)
        self.assertFalse(ctx.writable)
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.create_command(P, "demo", "dev", "us-central1"))
        self.assertEqual(ctx.writes, [])

    def test_arguments(self):
        cases = [({"projectId": None}, "projectId is missing."),
                 ({"project": ""}, "project is missing."),
                 ({"environment": None}, "environment is missing."),
                 ({"region": None}, "region is missing."),
                 ({"projectId": "Bad-id"}, "projectId is not a GCP project id."),
                 ({"project": "a" * 15}, "project must have 1 to 14"),
                 ({"project": "demo-"}, "project must have 1 to 14"),
                 ({"environment": "test"}, "environment must be dev, hom or prd."),
                 ({"region": "us"}, "region is not a Google Cloud region name"),
                 ({"region": "US-central1"}, "region is not a Google Cloud region name")]
        for over, line in cases:
            with self.subTest(over=over):
                r, ctx = run(**over)
                self.assert_no_write(r, ctx)
                self.assertTrue(r.lines[0].startswith(line), r.lines)
                self.assertEqual((ctx.called, ctx.reads), ([], []))
                self.assertEqual(r.block["outputs"], {"imagePath": None})

    def test_the_check_failed(self):
        failed = {"aleogr-result": 1, "status": "failed", "outputs": {"exists": None},
                  "answer": ["The repository could not be read; nothing was changed."]}
        r, ctx = run(found=failed)
        self.assert_no_write(r, ctx)
        self.assertEqual(r.lines, failed["answer"])
        missing = common._call_failure("not-found", PLUGIN, "x", "The command was not found.")
        r, ctx = run(found=missing)
        self.assert_no_write(r, ctx)
        self.assertEqual(r.lines, ["The command was not found."])

    def test_existing_docker_is_never_touched(self):
        for mode in ("plan", "apply"):
            r, ctx = run(found=described(True), mode=mode)
            self.assert_no_write(r, ctx, "unchanged")
            self.assertEqual(r.block["outputs"], {"imagePath": PATH})
            self.assertEqual(len(r.block["resources"]), 1)

    def test_existing_with_another_format(self):
        for mode in ("plan", "apply"):
            r, ctx = run(found=described(True, fmt="MAVEN"), mode=mode)
            self.assert_no_write(r, ctx, "pending")
            self.assertEqual(r.block["pending"], [{
                "item": "repository demo", "reason": "manual",
                "how": "fix by hand: the repository demo in us-central1 is not a Docker "
                       "repository; delete it, then run this skill again"}])
            self.assertEqual(r.block["outputs"], {"imagePath": None})
            self.assertEqual(r.block["resources"], [])

    def test_other_regions(self):
        r, ctx = run(found=described(others=["europe-west1", "southamerica-east1"]))
        self.assert_no_write(r, ctx, "pending")
        self.assertEqual(r.block["pending"][0]["item"],
                         "repository demo in europe-west1, southamerica-east1")
        self.assertEqual(len(r.lines), 1)


class TestPaths(unittest.TestCase):
    def test_another_failure_says_only_the_sentence(self):
        r, ctx = run(write=common.Completed(1, "", "ERROR: PERMISSION_DENIED: denied"))
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.lines, [skill.CREATE_FAILED % P])
        self.assertEqual(ctx.reads, [])
        self.assertEqual(r.block["outputs"], {"imagePath": None})

    def test_appeared_but_not_confirmed(self):
        exists = common.Completed(1, "", "ERROR: ALREADY_EXISTS: the repository exists")
        for answer in (common.Completed(1, "", "ERROR"),
                       ok(dict(REPO, format="NPM")),
                       ok(dict(REPO, name=REPO["name"].replace("us-central1", "us-east1")))):
            with self.subTest(answer=answer):
                r, ctx = run(write=exists, answers={GOLDEN_READ_BACK: answer})
                self.assertEqual(r.status, "failed")
                self.assertEqual(r.lines, [skill.NOT_CONFIRMED % ("demo", "us-central1")])
                self.assertEqual(ctx.reads, [GOLDEN_READ_BACK])
                self.assertNotIn("ALREADY_EXISTS", "\n".join(r.lines))

    def test_appeared_and_confirmed(self):
        exists = common.Completed(1, "", "ERROR: ALREADY_EXISTS: the repository exists")
        r, ctx = run(write=exists)
        self.assertEqual(r.status, "unchanged")
        self.assertEqual(r.lines[0], skill.APPEARED)
        self.assertEqual(len(ctx.writes), 1)

    def test_a_read_back_that_differs_is_pending(self):
        for answer in (common.Completed(1, "", "ERROR"),
                       ok(dict(REPO, labels={"aleogr-project": "demo"}))):
            r, ctx = run(answers={GOLDEN_READ_BACK: answer})
            self.assertEqual(r.status, "created")
            self.assertEqual(r.block["pending"], [{
                "item": "repository demo read back", "reason": "manual",
                "how": "/aleogr-registry-gcp-artifact-registry:"
                       "gcp-artifact-registry_registry-describe projectId=%s project=demo "
                       "region=us-central1" % P}])
            self.assertEqual(r.block["outputs"], {"imagePath": PATH})

    def test_the_cost_line_comes_before_the_create_is_reported(self):
        r, _ = run()
        self.assertLess(r.lines.index(skill.COST_LINE),
                        [i for i, l in enumerate(r.lines) if l.startswith("Created")][0])


if __name__ == "__main__":
    unittest.main()
