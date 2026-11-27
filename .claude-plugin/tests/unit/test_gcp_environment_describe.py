"""Unit tests of gcp_environment-describe's rules, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs. The scenarios describe-* cover the rest, in the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_environment-describe"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)


class FakeContext(common.Context):
    def __init__(self, answers, args):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill, "plan", args)
        self.answers = answers
        self.calls = []

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv[1:])
        self.calls.append(line)
        best = None
        for prefix in self.answers:
            if line.startswith(prefix) and (best is None or len(prefix) > len(best)):
                best = prefix
        return self.answers[best] if best is not None else common.Completed(0, "", "")


def ok(text):
    return common.Completed(0, text, "")


DESCRIBE = ok(json.dumps({"labels": {"aleogr-project": "demo", "aleogr-environment": "dev"},
                          "parent": {"type": "folder", "id": "222"}}))


class TestEnvironmentDescribe(unittest.TestCase):
    def run_skill(self, args, answers=None):
        ctx = FakeContext(answers or {}, args)
        return skill.run(dict(args), ctx), ctx

    def test_invalid_arguments_run_nothing(self):
        for args, line in (
                ({"project": "demo"}, "environment is missing."),
                ({"environment": "dev"}, "project is missing."),
                ({"project": "demo", "environment": "qa"}, "environment must be dev, hom or prd."),
                ({"project": "demo", "platform": "x"}, "platform must be shared."),
                ({"project": "demo", "platform": "shared"},
                 "platform=shared needs project=shared and no environment."),
                ({"project": "shared", "platform": "shared", "environment": "dev"},
                 "platform=shared needs project=shared and no environment."),
                ({"project": "shared", "environment": "dev"},
                 "project=shared needs platform=shared."),
                ({"projectId": "Bad_id"}, None)):
            with self.subTest(args=args):
                r, ctx = self.run_skill(args)
                self.assertEqual((r.status, r.block["outputs"], r.block["resources"], ctx.calls),
                                 ("failed", {"exists": None}, [], []))
                self.assertEqual(len(r.lines), 1)
                if line:
                    self.assertEqual(r.lines, [line])

    def test_project_and_environment_filter(self):
        r, ctx = self.run_skill({"project": "demo", "environment": "dev"},
                                {"projects list": ok("aleogr-dev-demo-ab12\n"),
                                 "projects describe": DESCRIBE,
                                 "billing projects describe": ok("False\n"),
                                 "services list": ok("b.googleapis.com\na.googleapis.com\n")})
        self.assertEqual(ctx.calls[0], "projects list --filter=labels.aleogr-project=demo AND "
                         "labels.aleogr-environment=dev --format=value(projectId)")
        o = r.block["outputs"]
        self.assertEqual(r.status, "unchanged")
        self.assertEqual((o["parent"], o["billingLinked"], o["enabledServices"]),
                         ("folders/222", False, ["a.googleapis.com", "b.googleapis.com"]))
        self.assertEqual(r.block["resources"][0]["name"], "demo")
        self.assertIn("Billing is not linked.", r.lines)
        self.assertIn("2 services are enabled.", r.lines)

    def test_two_projects_is_failed(self):
        r, ctx = self.run_skill({"project": "demo", "environment": "dev"},
                                {"projects list": ok("aleogr-a-111111\naleogr-b-222222\n")})
        self.assertEqual((r.status, r.block["outputs"], len(ctx.calls)),
                         ("failed", {"exists": None}, 1))
        self.assertIn("aleogr-a-111111, aleogr-b-222222", r.lines[0])

    def test_no_parent_and_empty_billing(self):
        r, _ = self.run_skill({"projectId": "aleogr-dev-demo-ab12"},
                              {"projects describe": ok(json.dumps({"labels": {}})),
                               "billing projects describe": ok(""),
                               "services list": ok("x.googleapis.com\n")})
        o = r.block["outputs"]
        self.assertEqual((o["parent"], o["billingLinked"], o["labels"]), (None, False, {}))
        self.assertIn("1 service is enabled.", r.lines)

    def test_a_failed_read_stops_at_once(self):
        fail = common.Completed(1, "", "ERROR: PERMISSION_DENIED: boom 403")
        for failing, calls in (("projects describe", 1), ("billing projects describe", 2),
                               ("services list", 3)):
            with self.subTest(failing=failing):
                answers = {"projects describe": DESCRIBE, "billing projects": ok("True"),
                           failing: fail}
                r, ctx = self.run_skill({"projectId": "aleogr-dev-demo-ab12"}, answers)
                self.assertEqual((r.status, r.block["outputs"], r.block["resources"]),
                                 ("failed", {"exists": None}, []))
                self.assertEqual(len(ctx.calls), calls)
                self.assertNotIn("boom", "\n".join(r.lines))
                self.assertIn("not allowed", r.lines[0])


if __name__ == "__main__":
    unittest.main()
