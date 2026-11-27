"""Unit tests of gcp_login-describe's rules, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs. The scenarios login-describe-* cover the rest, in the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_login-describe"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ORG = common.Completed(0, "organizations/111111111111\n", "")


class FakeContext(common.Context):
    def __init__(self, answers, args):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill, "plan", args)
        self.answers = answers
        self.calls = []

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv[1:])
        self.calls.append(line)
        for prefix, completed in self.answers.items():
            if line.startswith(prefix):
                return completed
        return common.Completed(0, "", "")


def run_skill(args, setting):
    ctx = FakeContext({"organizations list": ORG, "iap settings get": setting}, args)
    return skill.run(dict(args), ctx), ctx


class TestLoginDescribe(unittest.TestCase):
    def test_invalid_project_runs_nothing(self):
        for bad in ("Bad", "", "a-b", "aleogr-shared-"):
            with self.subTest(projectId=bad):
                ctx = FakeContext({}, {"projectId": bad})
                r = skill.run({"projectId": bad}, ctx)
                self.assertEqual((r.status, r.lines, ctx.calls),
                                 ("failed", [skill.INVALID_PROJECT], []))
                self.assertEqual(r.block["outputs"],
                                 {"prepared": None, "readable": None, "organization": False})

    def test_failed_organization_list(self):
        ctx = FakeContext({"organizations list": common.Completed(1, "", "ERROR")}, {})
        r = skill.run({}, ctx)
        self.assertEqual((r.status, r.lines, len(ctx.calls)),
                         ("failed", [skill.NO_ORGANIZATION], 1))

    def test_rules_in_order(self):
        """SERVICE_DISABLED wins over PERMISSION_DENIED, which wins over NOT_FOUND."""
        for text, outputs, line in (
                ("PERMISSION_DENIED ... reason: SERVICE_DISABLED NOT_FOUND",
                 (False, False, True), skill.API_OFF),
                ("reason: IAM_PERMISSION_DENIED NOT_FOUND", (False, False, True), skill.NOT_YET),
                ("NOT_FOUND: Requested entity", (False, True, True), skill.NOT_PREPARED),
                ("network unreachable", (None, None, True), skill.READ_FAILED)):
            with self.subTest(text=text):
                r, _ = run_skill({}, common.Completed(1, "", "ERROR: " + text))
                o = r.block["outputs"]
                self.assertEqual((o["prepared"], o["readable"], o["organization"]), outputs)
                self.assertEqual(r.lines, [line])
                self.assertEqual(r.status, "failed" if outputs[0] is None else "unchanged")

    def test_text_without_a_non_zero_exit_is_not_a_refusal(self):
        r, _ = run_skill({}, common.Completed(0, "", "PERMISSION_DENIED"))
        self.assertEqual((r.status, r.block["outputs"]["readable"]), ("unchanged", True))

    def test_not_prepared_shapes(self):
        for data in ({}, {"accessSettings": {}}, {"accessSettings": {"oauthSettings": {}}},
                     {"accessSettings": {"oauthSettings": {"clientId": ""}}},
                     {"accessSettings": {"reauthSettings": {"method": "LOGIN"}}}):
            with self.subTest(data=data):
                r, _ = run_skill({}, common.Completed(0, json.dumps(data), ""))
                self.assertEqual((r.status, r.block["outputs"]["prepared"]),
                                 ("unchanged", False))

    def test_billing_project_only_with_project_id(self):
        _, ctx = run_skill({"projectId": "aleogr-shared-ab12"}, common.Completed(0, "", ""))
        self.assertEqual(ctx.calls[1], "iap settings get --organization=111111111111 "
                         "--billing-project=aleogr-shared-ab12 --format=json")
        _, ctx = run_skill({}, common.Completed(0, "", ""))
        self.assertEqual(ctx.calls[1], "iap settings get --organization=111111111111 "
                         "--format=json")

    def test_nothing_of_the_setting_is_printed(self):
        data = {"accessSettings": {"oauthSettings": {"clientId": "1-abc.apps.example",
                                                     "clientSecretSha256": "0f1e"}}}
        r, _ = run_skill({}, common.Completed(0, json.dumps(data), ""))
        text = common.render_answer(r)
        self.assertEqual(r.block["outputs"]["prepared"], True)
        for word in ("1-abc", "0f1e", "111111111111"):
            self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
