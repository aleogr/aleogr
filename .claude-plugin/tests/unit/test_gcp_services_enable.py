"""Unit tests of gcp_services-enable: its golden commands, its gate (nothing is enabled
without mode=apply), the check of the enable against the allowlist in both modes, and
the paths no scenario covers. The scenarios services-* cover the rest, in the direct
mode.
"""

import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_services-enable"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

OK = common.Completed
P = "aleogr-dev-demo-ab12"
ARGS = {"project": "demo", "environment": "dev",
        "services": "run.googleapis.com,artifactregistry.googleapis.com,iam.googleapis.com"}
VERIFY = "gcloud services list --enabled --project=%s --format=value(config.name)" % P

# The SKILL.md's commands, word for word (steps 3 and 4).
GOLDEN_ENABLE = ("gcloud services enable run.googleapis.com artifactregistry.googleapis.com "
                 "--project=" + P)
GOLDEN_VERIFY = VERIFY


def described(enabled, exists=True, status="unchanged"):
    return {"aleogr-result": 1, "status": status, "answer": [],
            "outputs": {"exists": exists, "projectId": P if exists else None,
                        "enabledServices": enabled,
                        "labels": {"aleogr-project": "demo", "aleogr-environment": "dev"}}}


ALL = "run.googleapis.com\nartifactregistry.googleapis.com\niam.googleapis.com\n"


class FakeContext(common.Context):
    def __init__(self, args, found, answers, write_code=0, read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.found = found
        self.answers = answers
        self.write_code = write_code
        self.called, self.reads, self.writes = [], [], []

    def call(self, command, name, args=None, timeout=None):
        self.called.append((command, name, dict(args or {})))
        return self.found

    def execute(self, argv, timeout=None):
        self.writes.append(list(argv))
        return OK(self.write_code, "", "ERROR: PERMISSION_DENIED" if self.write_code else "")

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        self.reads.append(" ".join(argv))
        return self.answers.get(" ".join(argv), OK(1, "", "ERROR"))


def run(found=None, answers=None, write_code=0, mode="apply", **over):
    args = dict(ARGS, **over)
    if mode is not None:
        args["mode"] = mode
    args = {k: v for k, v in args.items() if v is not None}
    ctx = FakeContext(args, found if found is not None else described(["iam.googleapis.com"]),
                      answers if answers is not None else {VERIFY: OK(0, ALL, "")}, write_code)
    return skill.run(dict(args), ctx), ctx


class TestGoldenCommands(unittest.TestCase):
    def test_one_enable_for_the_missing_then_the_verification(self):
        r, ctx = run()
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [GOLDEN_ENABLE.split(" ")])
        self.assertEqual(ctx.reads, [GOLDEN_VERIFY])
        self.assertIsNone(common.write_refusal(SKILL, ctx.writes[0], root=ROOT))
        self.assertEqual(r.block["outputs"], {
            "projectId": P, "enabled": ["run.googleapis.com", "artifactregistry.googleapis.com"],
            "alreadyEnabled": ["iam.googleapis.com"]})
        self.assertEqual(ctx.called, [(PLUGIN, "gcp_environment-describe",
                                       {"project": "demo", "environment": "dev"})])

    def test_the_describe_is_asked_as_the_project_is_named(self):
        _, ctx = run(project=None, environment=None, projectId=P)
        self.assertEqual(ctx.called[0][2], {"projectId": P})
        _, ctx = run(project="shared", environment=None, platform="shared")
        self.assertEqual(ctx.called[0][2], {"project": "shared", "platform": "shared"})

    def test_duplicates_are_removed(self):
        r, ctx = run(services="run.googleapis.com,run.googleapis.com")
        self.assertEqual(ctx.writes, [["gcloud", "services", "enable", "run.googleapis.com",
                                       "--project=" + P]])


class TestGate(unittest.TestCase):
    def test_the_gate_absent(self):
        r, ctx = run(mode=None)
        self.assertEqual((r.status, r.block["mode"], ctx.writes), ("would-update", "plan", []))
        self.assertEqual(ctx.reads, [])
        self.assertEqual(r.block["outputs"]["enabled"],
                         ["run.googleapis.com", "artifactregistry.googleapis.com"])

    def test_the_gate_with_another_value(self):
        for mode in ("plan", "yes", "Apply", ""):
            with self.subTest(mode=mode):
                r, ctx = run(mode=mode)
                self.assertEqual(ctx.writes, [])
                if mode != "plan":
                    self.assertEqual((r.status, r.lines), ("failed",
                                                           ["mode must be plan or apply."]))
                    self.assertEqual(ctx.called, [])

    def test_read_only_refuses_the_enable(self):
        ctx = FakeContext(dict(ARGS, mode="apply"), described([]), {}, read_only=True)
        with self.assertRaises(common.WriteRefused):
            ctx.write(GOLDEN_ENABLE.split(" "))
        self.assertEqual(ctx.writes, [])

    def test_validation_builds_nothing(self):
        cases = [
            ({"services": None}, "services is missing."),
            ({"environment": None}, "environment is missing."),
            ({"project": None}, "project is missing."),
            ({"environment": "qa"}, "environment must be dev, hom or prd."),
            ({"project": "shared"}, "project=shared needs platform=shared."),
            ({"platform": "shared"}, "platform=shared needs project=shared and no environment."),
            ({"services": "billingbudgets"}, skill.SERVICES_INVALID),
            ({"services": "Run.googleapis.com"}, skill.SERVICES_INVALID),
            ({"services": "run.googleapis.com,"}, skill.SERVICES_INVALID),
            ({"projectId": "Bad"}, None),
        ]
        for over, sentence in cases:
            with self.subTest(over=over):
                r, ctx = run(**over)
                self.assertEqual(r.status, "failed")
                self.assertEqual((ctx.called, ctx.reads, ctx.writes), ([], [], []))
                self.assertEqual(r.block["outputs"],
                                 {"projectId": None, "enabled": [], "alreadyEnabled": []})
                if sentence:
                    self.assertEqual(r.lines, [sentence])


class TestWriteShapesInBothModes(unittest.TestCase):
    def test_a_name_the_allowlist_does_not_take(self):
        # It passes the SKILL.md's rule (only a-z, 0-9, - and . before the suffix), not
        # the shape of the enable: failed in both modes, nothing enabled.
        for mode in ("plan", "apply"):
            with self.subTest(mode=mode):
                r, ctx = run(mode=mode, services=".run.googleapis.com")
                self.assertEqual((r.status, r.lines, ctx.writes),
                                 ("failed", [skill.UNUSABLE], []))


class TestPaths(unittest.TestCase):
    def test_nothing_missing(self):
        r, ctx = run(found=described(["run.googleapis.com", "artifactregistry.googleapis.com",
                                      "iam.googleapis.com", "x.googleapis.com"]))
        self.assertEqual((r.status, ctx.writes, ctx.reads), ("unchanged", [], []))

    def test_the_project_does_not_exist(self):
        r, ctx = run(found=described([], exists=False))
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertIn("gcp_environment-create", r.lines[0])

    def test_the_describe_failed(self):
        failed = {"aleogr-result": 1, "status": "failed", "outputs": {"exists": None},
                  "answer": ["The GCP projects could not be listed: gcloud failed."]}
        r, ctx = run(found=failed)
        self.assertEqual((r.status, r.lines, ctx.writes), ("failed", failed["answer"], []))

    def test_a_failed_enable_is_not_verified(self):
        r, ctx = run(write_code=1)
        self.assertEqual((r.status, ctx.reads), ("failed", []))
        self.assertNotIn("PERMISSION_DENIED", "\n".join(r.lines))
        self.assertEqual(r.block["resources"], [])

    def test_a_verification_that_fails(self):
        for answers in ({}, {VERIFY: OK(0, "iam.googleapis.com\n", "")}):
            with self.subTest(answers=answers):
                r, ctx = run(answers=answers)
                self.assertEqual(r.status, "pending")
                self.assertEqual(r.block["pending"][0]["how"],
                                 'gcloud services list --enabled --project=%s '
                                 '--format="value(config.name)"' % P)
                self.assertEqual(r.block["outputs"]["projectId"], P)


if __name__ == "__main__":
    unittest.main()
