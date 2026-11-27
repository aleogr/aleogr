"""Unit tests of gcp-cloud-sql_instance-describe's rules, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs. The scenarios sql-describe-* cover the rest, in the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-db-gcp-cloud-sql"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "gcp-cloud-sql_instance-describe")

ARGS = {"projectId": "aleogr-shared-zz99", "instance": "aleogr-shared"}


class FakeContext(common.Context):
    def __init__(self, answers):
        common.Context.__init__(self, PLUGIN, ROOT,
                                "gcp-cloud-sql_instance-describe", skill, "plan", ARGS)
        self.answers = answers
        self.calls = []

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        self.calls.append(" ".join(argv[1:4]))
        for prefix, completed in self.answers.items():
            if " ".join(argv[1:]).startswith(prefix):
                return completed
        return common.Completed(0, "", "")


def describe(settings, state="RUNNABLE"):
    return common.Completed(0, json.dumps({"state": state, "databaseVersion": "POSTGRES_17",
                                           "region": "us-central1", "settings": settings}), "")


class TestInstanceDescribe(unittest.TestCase):
    def test_absent_booleans_are_false_and_unknown_policy(self):
        ctx = FakeContext({"sql instances describe": describe({"tier": "db-f1-micro"})})
        r = skill.run(dict(ARGS), ctx)
        o = r.block["outputs"]
        self.assertEqual(r.status, "unchanged")
        self.assertEqual(o["state"], "unknown")
        self.assertIn("Its activation policy is absent.", r.lines)
        for k in ("storageAutoIncrease", "publicAddress", "backupEnabled",
                  "deletionProtection", "knowledgeCatalog"):
            self.assertIs(o[k], False, k)
        self.assertEqual((o["authorizedNetworks"], o["diskSizeGb"], o["backupStartUtc"]),
                         (0, None, None))
        self.assertEqual(ctx.calls, ["sql instances describe", "sql backups list"])

    def test_states(self):
        for policy, state, want in (("NEVER", "RUNNABLE", "stopped"),
                                    ("ALWAYS", "PENDING_CREATE", "creating"),
                                    ("ALWAYS", "MAINTENANCE", "starting"),
                                    ("ON_DEMAND", "RUNNABLE", "unknown")):
            with self.subTest(policy=policy, state=state):
                ctx = FakeContext({"sql instances describe":
                                   describe({"activationPolicy": policy}, state)})
                r = skill.run(dict(ARGS), ctx)
                self.assertEqual(r.block["outputs"]["state"], want)
                self.assertNotIn("sql operations list", ctx.calls)

    def test_operations_or_backups_failing_keep_unchanged(self):
        fail = common.Completed(1, "", "ERROR: boom")
        ctx = FakeContext({"sql instances describe": describe({"activationPolicy": "ALWAYS"}),
                           "sql operations list": fail, "sql backups list": fail})
        r = skill.run(dict(ARGS), ctx)
        self.assertEqual((r.status, r.block["outputs"]["state"],
                          r.block["outputs"]["lastBackup"]), ("unchanged", "running", None))
        self.assertIn("Pending operations could not be checked.", r.lines)
        self.assertIn("The last backup could not be read.", r.lines)
        self.assertNotIn("boom", "\n".join(r.lines))

    def test_invalid_arguments_run_nothing(self):
        for args, line in (({"instance": "a"}, "projectId is missing."),
                           ({"projectId": "aleogr-shared-zz99"}, "instance is missing."),
                           ({"projectId": "Bad", "instance": "a"}, None),
                           ({"projectId": "aleogr-shared-zz99", "instance": "a" * 61}, None)):
            with self.subTest(args=args):
                ctx = FakeContext({})
                r = skill.run(args, ctx)
                self.assertEqual((r.status, r.block["outputs"], r.block["resources"], ctx.calls),
                                 ("failed", {"exists": None}, [], []))
                if line:
                    self.assertEqual(r.lines, [line])

    def test_missing_instance_outputs(self):
        ctx = FakeContext({"sql instances describe": common.Completed(
            1, "", "ERROR: (gcloud.sql.instances.describe) HTTPError 404: not found")})
        r = skill.run(dict(ARGS), ctx)
        o = r.block["outputs"]
        self.assertEqual((r.status, o["exists"], o["state"], o["authorizedNetworks"]),
                         ("unchanged", False, None, 0))
        self.assertEqual(r.block["resources"], [])
        self.assertEqual(ctx.calls, ["sql instances describe"])


if __name__ == "__main__":
    unittest.main()
