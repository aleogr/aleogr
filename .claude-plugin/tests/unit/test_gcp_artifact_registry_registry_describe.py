"""Unit tests of gcp-artifact-registry_registry-describe's rules, the cases no scenario
covers. The scenarios registry-describe-* cover the rest, in the direct mode."""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-registry-gcp-artifact-registry"
SKILL = "gcp-artifact-registry_registry-describe"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ARGS = {"projectId": "aleogr-dev-demo-ab12", "project": "demo", "region": "us-central1"}
NAME = "projects/aleogr-dev-demo-ab12/locations/us-central1/repositories/demo"


class FakeContext(common.Context):
    def __init__(self, answers):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill, "plan", ARGS)
        self.answers = answers
        self.calls = []

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        self.calls.append(" ".join(argv[1:4]))
        for prefix, completed in self.answers.items():
            if " ".join(argv[1:]).startswith(prefix):
                return completed
        return common.Completed(0, "", "")


def ok(obj):
    return common.Completed(0, json.dumps(obj), "")


DESCRIBE = "artifacts repositories describe"
IAM = "artifacts repositories get-iam-policy"
LIST = "artifacts repositories list"


class TestRegistryDescribe(unittest.TestCase):
    def test_invalid_arguments_run_nothing(self):
        for args, line in (({"project": "demo", "region": "us-central1"},
                            "projectId is missing."),
                           (dict(ARGS, project=""), "project is missing."),
                           ({"projectId": "aleogr-dev-demo-ab12", "project": "demo"},
                            "region is missing."),
                           (dict(ARGS, project="a" * 15), None),
                           (dict(ARGS, project="demo-"), None),
                           (dict(ARGS, region="us"), None),
                           (dict(ARGS, region="US-central1"), None),
                           (dict(ARGS, projectId="Bad"), None)):
            with self.subTest(args=args):
                ctx = FakeContext({})
                r = skill.run(args, ctx)
                self.assertEqual((r.status, r.block["outputs"], r.block["resources"], ctx.calls),
                                 ("failed", {"exists": None}, [], []))
                self.assertEqual(len(r.lines), 1)
                if line:
                    self.assertEqual(r.lines, [line])

    def test_regions_accepted(self):
        for region in ("us-central1", "southamerica-east1", "europe-west10"):
            self.assertIsNone(skill._validate(dict(ARGS, region=region)), region)

    def test_no_cleanup_policies_and_no_bindings(self):
        ctx = FakeContext({DESCRIBE: ok({"name": NAME, "format": "DOCKER"}), IAM: ok({})})
        r = skill.run(dict(ARGS), ctx)
        o = r.block["outputs"]
        self.assertEqual(r.status, "unchanged")
        self.assertEqual(o["cleanup"], {"keep": None, "deletesTheRest": False, "dryRun": False,
                                        "rules": 0})
        self.assertEqual((o["push"], o["labels"]), ([], {}))
        self.assertEqual(ctx.calls, [DESCRIBE, IAM])

    def test_cleanup_rules(self):
        policies = {
            "a": {"action": "KEEP", "mostRecentVersions": {"keepCount": "3"}},
            "b": {"action": "KEEP", "mostRecentVersions": {"keepCount": 9,
                                                           "packageNamePrefixes": ["x"]}},
            "c": {"action": "DELETE", "condition": {"tagState": "any"}},
        }
        ctx = FakeContext({DESCRIBE: ok({"name": NAME, "format": "DOCKER",
                                         "cleanupPolicies": policies}), IAM: ok({})})
        o = skill.run(dict(ARGS), ctx).block["outputs"]
        self.assertEqual(o["cleanup"], {"keep": 3, "deletesTheRest": True, "dryRun": False,
                                        "rules": 3})

    def test_two_keep_rules_or_a_narrow_delete(self):
        policies = {
            "a": {"action": "KEEP", "mostRecentVersions": {"keepCount": 5}},
            "b": {"action": "KEEP", "mostRecentVersions": {"keepCount": 2}},
            "c": {"action": "DELETE", "condition": {"tagState": "ANY", "olderThan": "1d"}},
        }
        ctx = FakeContext({DESCRIBE: ok({"name": NAME, "format": "DOCKER",
                                         "cleanupPolicies": policies}), IAM: ok({})})
        o = skill.run(dict(ARGS), ctx).block["outputs"]
        self.assertEqual((o["cleanup"]["keep"], o["cleanup"]["deletesTheRest"]), (None, False))

    def test_push_members(self):
        writer = "roles/artifactregistry.writer"
        policy = {"bindings": [
            {"role": writer, "members": ["serviceAccount:a@x", "serviceAccount:b@x"]},
            {"role": writer, "members": ["serviceAccount:c@x"], "condition": {"title": "t"}},
            {"role": "roles/artifactregistry.admin", "members": ["user:d@x"]},
            {"role": writer, "members": ["serviceAccount:a@x"]},
        ]}
        ctx = FakeContext({DESCRIBE: ok({"name": NAME, "format": "DOCKER"}), IAM: ok(policy)})
        o = skill.run(dict(ARGS), ctx).block["outputs"]
        self.assertEqual(o["push"], ["serviceAccount:a@x", "serviceAccount:b@x"])

    def test_other_format_has_no_image_path(self):
        ctx = FakeContext({DESCRIBE: ok({"name": NAME, "format": "MAVEN"}), IAM: ok({})})
        r = skill.run(dict(ARGS), ctx)
        self.assertIsNone(r.block["outputs"]["imagePath"])
        self.assertIn("Image path: none, the format is not DOCKER.", r.lines)

    def test_iam_failure(self):
        ctx = FakeContext({DESCRIBE: ok({"name": NAME, "format": "DOCKER"}),
                           IAM: common.Completed(1, "", "ERROR: PERMISSION_DENIED")})
        r = skill.run(dict(ARGS), ctx)
        self.assertEqual((r.status, r.block["outputs"], r.block["resources"]),
                         ("failed", {"exists": None}, []))
        self.assertEqual(r.lines, [skill.ACCESS_FAILED])

    def test_list_failure_after_missing(self):
        missing = common.Completed(1, "", "ERROR: NOT_FOUND: Requested entity was not found.")
        ctx = FakeContext({DESCRIBE: missing, LIST: common.Completed(1, "", "ERROR: boom")})
        r = skill.run(dict(ARGS), ctx)
        self.assertEqual((r.status, r.block["outputs"]), ("failed", {"exists": None}))
        self.assertNotIn("boom", "\n".join(r.lines))
        self.assertEqual(ctx.calls, [DESCRIBE, LIST])

    def test_other_regions_need_the_exact_id(self):
        missing = common.Completed(1, "", "ERROR: NOT_FOUND: Requested entity was not found.")
        listing = "\n".join([
            "Listing items under project aleogr-dev-demo-ab12, across all locations.",
            "projects/aleogr-dev-demo-ab12/locations/europe-west1/repositories/demo-x",
            "projects/aleogr-dev-demo-ab12/locations/us-central1/repositories/demo",
            "projects/aleogr-dev-demo-ab12/locations/us-east1/repositories/demo",
        ])
        ctx = FakeContext({DESCRIBE: missing, LIST: common.Completed(0, listing, "")})
        r = skill.run(dict(ARGS), ctx)
        self.assertEqual((r.status, r.block["outputs"]["otherRegions"]),
                         ("unchanged", ["us-east1"]))


if __name__ == "__main__":
    unittest.main()
