"""Unit tests of github_variables-set's arguments and plan, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs. The scenarios gh-variables-plan and gh-secrets-plan cover the rest, in the
direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-repo-github"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "github_variables-set")

ARGS = {"owner": "example-org", "name": "example-repo",
        "variables": "B_VAR=secret-two,A_VAR=secret-one"}
VARS = "gh variable list --repo example-org/example-repo --json name,value"
SECRETS = "gh secret list --repo example-org/example-repo --json name"


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def fail(text, code=1):
    return common.Completed(code, "", text)


class FakeContext(common.Context):
    def __init__(self, answers, args):
        common.Context.__init__(self, PLUGIN, ROOT, "github_variables-set", skill,
                                args.get("mode") or "plan", args)
        self.answers = answers
        self.calls = []

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.calls.append(line)
        return self.answers.get(line, common.Completed(0, "", ""))


def run(answers, **over):
    args = dict(ARGS, **over)
    ctx = FakeContext(answers, args)
    return skill.run(dict(args), ctx), ctx


def text_of(r):
    return "\n".join(r.lines) + "\n" + common.render_block(r.block)


class TestArguments(unittest.TestCase):
    def test_rules_in_order_never_naming_a_value(self):
        cases = [({"variables": ""}, "variables is missing."),
                 ({"owner": "a_b"}, "owner is not valid"),
                 ({"variables": "A=1,,B=2"}, "variables is not valid: it has an empty"),
                 ({"variables": "A"}, "variables is not valid: an entry has no ="),
                 ({"variables": "a=1"}, "variables is not valid: the variable name a"),
                 ({"variables": "GITHUB_TOKEN=x"}, "variables is not valid: the variable "
                  "name GITHUB_TOKEN starts with GITHUB_"),
                 ({"variables": "A=1,A=2"}, "variables is not valid: the variable A is"),
                 ({"variables": "A="}, "variables is not valid: the value of A"),
                 ({"variables": "A=x\ty"}, "variables is not valid: the value of A"),
                 ({"variables": "A=$HOME"}, "variables is not valid: the value of A"),
                 ({"kind": "tokens", "variables": "A=1,a=2"},
                  "variables is not valid: the variable name a"),
                 ({"kind": "tokens"}, "kind is not valid"),
                 ({"replace": "yes"}, "replace is not valid: it is given only"),
                 ({"kind": "secrets", "replace": "always"}, "replace is not valid: it must"),
                 ({"mode": "later"}, "mode is not valid")]
        for over, sentence in cases:
            with self.subTest(over=over):
                r, ctx = run({}, **over)
                self.assertEqual(r.status, "failed")
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertEqual(ctx.calls, [])
                self.assertEqual(r.block["outputs"], {"set": [], "already": []})
                self.assertEqual(r.block["resources"], [])
                self.assertNotIn("$HOME", r.lines[0])

    def test_a_value_may_hold_equals(self):
        parsed, problem = skill.validate(dict(ARGS, variables="A=x=y"))
        self.assertIsNone(problem)
        self.assertEqual(parsed[1], [("A", "x=y")])


class TestPlan(unittest.TestCase):
    def test_unchanged_and_names_only(self):
        r, ctx = run({VARS: ok([{"name": "A_VAR", "value": "secret-one"},
                                {"name": "B_VAR", "value": "secret-two"},
                                {"name": "OTHER", "value": "x"}])})
        self.assertEqual(ctx.calls, [VARS])
        self.assertEqual((r.status, r.block["outputs"]),
                         ("unchanged", {"set": [], "already": ["A_VAR", "B_VAR"]}))
        self.assertNotIn("secret-", text_of(r))
        self.assertNotIn("OTHER", text_of(r))

    def test_values_compared_byte_for_byte(self):
        r, _ = run({VARS: ok([{"name": "A_VAR", "value": "secret-one "}])})
        self.assertEqual((r.status, r.block["outputs"]),
                         ("would-update", {"set": ["A_VAR", "B_VAR"], "already": []}))

    def test_secrets_replace_sets_every_one(self):
        r, ctx = run({SECRETS: ok([{"name": "A_VAR"}, {"name": "B_VAR"}])},
                     kind="secrets", replace="yes")
        self.assertEqual(ctx.calls, [SECRETS])
        self.assertEqual((r.status, r.block["outputs"]),
                         ("would-update", {"set": ["A_VAR", "B_VAR"], "already": []}))
        r, _ = run({SECRETS: ok([{"name": "A_VAR"}, {"name": "B_VAR"}])}, kind="secrets")
        self.assertEqual((r.status, r.block["outputs"]["already"]),
                         ("unchanged", ["A_VAR", "B_VAR"]))

    def test_read_failures(self):
        cases = [(fail("gh: Not Found (HTTP 404)"), "variables",
                  skill.NOT_FOUND % "example-org/example-repo"),
                 (fail("gh: Server Error (HTTP 500)"), "variables", skill.READ_REFUSED["variables"]),
                 (ok([{"name": "A_VAR"}]), "variables", skill.READ_REFUSED["variables"]),
                 (ok({"name": "A_VAR"}), "secrets", skill.READ_REFUSED["secrets"]),
                 (fail("gh: command not found", 127), "secrets", "gh is not installed")]
        for c, kind, sentence in cases:
            with self.subTest(sentence=sentence[:30], kind=kind):
                cmd = SECRETS if kind == "secrets" else VARS
                r, _ = run({cmd: c}, kind=kind)
                self.assertEqual(r.status, "failed")
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertEqual(r.block["resources"], [])
                self.assertEqual(r.block["outputs"], {"set": [], "already": []})


if __name__ == "__main__":
    unittest.main()
