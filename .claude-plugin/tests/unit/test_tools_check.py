"""Unit tests of tools-check's rules, the cases no scenario covers.

The skill's check() is given a reader that answers from a dict, so no provider command
runs. The scenarios tools-* cover the rest, in the direct mode.
"""

import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "tools-check")

OK = common.Completed(0, "", "")


class Reader(object):
    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def __call__(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.calls.append(line)
        best = None
        for prefix in self.answers:
            if line.startswith(prefix) and (best is None or len(prefix) > len(best)):
                best = prefix
        return self.answers[best] if best is not None else OK


class FakeContext(common.Context):
    def __init__(self, args, reader):
        common.Context.__init__(self, PLUGIN, ROOT, "tools-check", skill, "plan", args)
        self.reader = reader

    def read(self, argv, timeout=None):
        return self.reader(argv)

    def run(self, argv, timeout=None):
        raise AssertionError("tools-check uses only the read-only runner")


class TestWhere(unittest.TestCase):
    def test_where(self):
        self.assertEqual(skill.where({"CLAUDE_CODE_REMOTE": "true", "CODESPACES": "true"}),
                         "cloud-session")
        self.assertEqual(skill.where({"CODESPACES": "true"}), "codespace")
        self.assertEqual(skill.where({"CLAUDE_CODE_REMOTE": "1"}), "local")
        self.assertEqual(skill.where({}), "local")


class TestGcloud(unittest.TestCase):
    def test_not_found_skips_the_rest(self):
        r = Reader({"gcloud --version": common.Completed(127, "", "")})
        c = skill.check("gcloud", r, {})
        self.assertEqual((c.tool["state"], c.tool["fix"]),
                         ("missing", "https://cloud.google.com/sdk/docs/install"))
        self.assertEqual(r.calls, ["gcloud --version"])
        self.assertEqual(c.status, "failed")

    def test_gcloud_cmd_when_only_it_starts(self):
        r = Reader({"gcloud --version": common.Completed(1, "", "it failed to start"),
                    "gcloud.cmd auth list": common.Completed(0, "someone@example.com\n", "")})
        c = skill.check("gcloud", r, {})
        self.assertEqual(r.calls[:2], ["gcloud --version", "gcloud.cmd --version"])
        self.assertEqual(r.calls[2], "gcloud.cmd auth list --filter=status:ACTIVE "
                                     "--format=value(account)")
        self.assertEqual((c.tool["command"], c.tool["state"]), ("gcloud.cmd", "ok"))
        lines = skill.answer(c)
        self.assertIn(skill.GCLOUD_CMD, lines)
        self.assertFalse(any("someone@" in l for l in lines))

    def test_both_fail_shows_the_first_error_line(self):
        r = Reader({"gcloud --version": common.Completed(1, "", "\nboom one\nboom two"),
                    "gcloud.cmd --version": common.Completed(1, "", "")})
        c = skill.check("gcloud", r, {})
        self.assertEqual((c.tool["command"], c.tool["state"]), ("gcloud", "missing"))
        self.assertIn("gcloud --version failed: boom one", c.notes)
        self.assertEqual(len(r.calls), 2)

    def test_auth_check_failing_is_not_authenticated(self):
        r = Reader({"gcloud auth list": common.Completed(1, "user@example.com", "ERROR")})
        c = skill.check("gcloud", r, {})
        self.assertEqual((c.tool["state"], c.tool["fix"]),
                         ("not-authenticated", "gcloud auth login"))
        lines = skill.answer(c)
        self.assertIn(skill.AUTH_CHECK_FAILED, lines)
        self.assertFalse(any("ERROR" in l or "user@" in l for l in lines))

    def test_ok_has_null_fix_and_says_no_account(self):
        r = Reader({"gcloud auth list": common.Completed(0, "user@example.com\n", "")})
        c = skill.check("gcloud", r, {"CLAUDE_CODE_REMOTE": "true"})
        self.assertEqual(c.outputs(), {"where": "cloud-session", "tools": [
            {"name": "gcloud", "command": "gcloud", "state": "ok", "fix": None}]})
        lines = skill.answer(c)
        self.assertEqual(lines[0], "gcloud: ok.")
        self.assertIn(skill.CLOUD_SESSION, lines)
        self.assertFalse(any("user@" in l for l in lines))


class TestGhAndGo(unittest.TestCase):
    def test_gh_any_failure_of_version_is_missing(self):
        r = Reader({"gh --version": common.Completed(2, "", "weird")})
        c = skill.check("gh", r, {})
        self.assertEqual((c.tool["state"], c.tool["fix"]), ("missing", "https://cli.github.com"))
        self.assertEqual(r.calls, ["gh --version"])
        self.assertIn(skill.BLOCKED["gh"], skill.answer(c))

    def test_gh_auth_reads_the_exit_code_only(self):
        r = Reader({"gh auth status": common.Completed(0, "Logged in to github.com as x", "")})
        c = skill.check("gh", r, {})
        self.assertEqual(c.tool, {"name": "gh", "command": "gh", "state": "ok", "fix": None})
        self.assertFalse(any("Logged" in l for l in skill.answer(c)))

    def test_go_output_must_start_with_go_version_go(self):
        for out, state in (("go version go1.27.1 linux/amd64\n", "ok"),
                           ("something else\n", "missing"), ("", "missing")):
            with self.subTest(out=out):
                c = skill.check("go", Reader({"go version": common.Completed(0, out, "")}), {})
                self.assertEqual(c.tool["state"], state)
        c = skill.check("go", Reader({"go version": common.Completed(1, "", "")}), {})
        self.assertEqual((c.tool["state"], c.tool["fix"]), ("missing",
                                                            "https://go.dev/doc/install"))


class TestRun(unittest.TestCase):
    def test_unknown_command_runs_nothing(self):
        for value in ("bash", ""):
            with self.subTest(value=value):
                r = Reader({})
                res = skill.run({"command": value}, FakeContext({"command": value}, r))
                self.assertEqual(res.status, "failed")
                self.assertEqual(r.calls, [])
                self.assertEqual(res.lines, [skill.INVALID_COMMAND])

    def test_block(self):
        r = Reader({"gcloud auth list": common.Completed(0, "", "")})
        res = skill.run({}, FakeContext({}, r))
        b = res.block
        self.assertEqual((b["family"], b["provider"], b["action"], b["mode"], b["status"]),
                         ("orchestrator", "aleogr", "tools-check", "plan", "failed"))
        self.assertEqual(b["cost"], {"fixed": False, "notes": "read-only check"})
        self.assertEqual((b["resources"], b["pending"]), ([], []))
        self.assertEqual(b["outputs"]["tools"][0]["state"], "not-authenticated")


if __name__ == "__main__":
    unittest.main()
