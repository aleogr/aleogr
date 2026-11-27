"""Unit tests of github_variables-set: its arguments, plan and apply, the cases no
scenario covers, and its golden commands.

The skill's run() is given a context whose read() answers from a dict and whose
execute() (where ctx.write runs a command that passed the allowlist of writes) records
the write and answers from another dict, so no provider command runs. The scenarios
gh-variables-* and gh-secrets-* cover the rest, in the direct mode.
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
    def __init__(self, answers, args, writes=None):
        common.Context.__init__(self, PLUGIN, ROOT, "github_variables-set", skill,
                                args.get("mode") or "plan", args)
        self.answers = answers
        self.write_answers = writes or {}
        self.calls = []
        self.writes = []

    def execute(self, argv, timeout=None):
        # Reached only through ctx.write, after the allowlist of writes accepted argv.
        self.writes.append(list(argv))
        return self.write_answers.get(argv[3], common.Completed(0, "", ""))

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.calls.append(line)
        return self.answers.get(line, common.Completed(0, "", ""))


def run(answers, writes=None, **over):
    args = dict(ARGS, **over)
    ctx = FakeContext(answers, args, writes)
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


def plain(argv):
    return [a.value if isinstance(a, common.Hidden) else a for a in argv]


class TestGoldenCommands(unittest.TestCase):
    """Step 3 of the SKILL.md, as it writes the commands:

        gh variable set <NAME> --repo <owner>/<name> --body "<value>"
        gh secret set <NAME> --repo <owner>/<name> --body "<value>"
    """

    def test_variable_set(self):
        r, ctx = run({VARS: ok([])}, mode="apply")
        self.assertEqual([plain(w) for w in ctx.writes], [
            ["gh", "variable", "set", "A_VAR", "--repo", "example-org/example-repo", "--body",
             "secret-one"],
            ["gh", "variable", "set", "B_VAR", "--repo", "example-org/example-repo", "--body",
             "secret-two"]])
        for w in ctx.writes:
            self.assertIsInstance(w[-1], common.Hidden)
            self.assertTrue(all(isinstance(a, str) for a in w[:-1]))
            self.assertEqual(common.show_command(w).split(" --body ")[1], "<value>")
        self.assertEqual(ctx.calls, [VARS])

    def test_secret_set(self):
        r, ctx = run({SECRETS: ok([])}, mode="apply", kind="secrets")
        self.assertEqual([plain(w) for w in ctx.writes], [
            ["gh", "secret", "set", "A_VAR", "--repo", "example-org/example-repo", "--body",
             "secret-one"],
            ["gh", "secret", "set", "B_VAR", "--repo", "example-org/example-repo", "--body",
             "secret-two"]])
        self.assertIsInstance(ctx.writes[0][-1], common.Hidden)

    def test_each_golden_command_is_on_the_allowlist(self):
        for kind in ("variables", "secrets"):
            argv = skill.set_command(kind, "A_VAR", "example-org/example-repo", "v=1")
            self.assertIsNone(common.write_refusal("github_variables-set", argv))


class TestApply(unittest.TestCase):
    def test_all_set_names_only(self):
        r, ctx = run({VARS: ok([{"name": "A_VAR", "value": "secret-one"}])}, mode="apply")
        self.assertEqual([w[3] for w in ctx.writes], ["B_VAR"])
        self.assertEqual((r.status, r.block["outputs"], r.block["pending"]),
                         ("updated", {"set": ["B_VAR"], "already": ["A_VAR"]}, []))
        self.assertEqual(r.block["mode"], "apply")
        self.assertEqual(r.lines, ["These variables were set: B_VAR.",
                                   "These variables already held the given value: A_VAR."])
        self.assertNotIn("secret-", text_of(r))

    def test_unchanged_writes_nothing(self):
        r, ctx = run({VARS: ok([{"name": "A_VAR", "value": "secret-one"},
                                {"name": "B_VAR", "value": "secret-two"}])}, mode="apply")
        self.assertEqual((r.status, ctx.writes, r.block["mode"]), ("unchanged", [], "apply"))

    def test_first_set_refused_is_failed(self):
        r, ctx = run({VARS: ok([])}, {"A_VAR": fail("HTTP 403: Resource not accessible")},
                     mode="apply")
        self.assertEqual([w[3] for w in ctx.writes], ["A_VAR"])
        self.assertEqual((r.status, r.block["outputs"], r.block["pending"]),
                         ("failed", {"set": [], "already": []}, []))
        self.assertEqual(r.lines[0], skill.refused_first("variables", "A_VAR"))
        self.assertEqual(r.block["resources"][0]["id"], "example-org/example-repo")
        self.assertNotIn("403", text_of(r))
        self.assertNotIn("secret-", text_of(r))

    def test_later_set_refused_is_updated_with_the_item(self):
        r, ctx = run({SECRETS: ok([])}, {"B_VAR": fail("HTTP 403")}, mode="apply",
                     kind="secrets")
        self.assertEqual([w[3] for w in ctx.writes], ["A_VAR", "B_VAR"])
        self.assertEqual((r.status, r.block["outputs"]),
                         ("updated", {"set": ["A_VAR"], "already": []}))
        self.assertEqual(r.block["pending"], [{
            "item": "secrets", "reason": "manual",
            "how": "run github_variables-set again with the same arguments and mode=apply "
                   "once gh may change the repository's Actions secrets"}])
        self.assertEqual(r.lines[1], "GitHub refused to set the secret B_VAR; the secrets "
                         "before it were set and the rest were not. Check that gh may change "
                         "the repository's Actions secrets (it needs write access to the "
                         "repository), then run this skill again with the same arguments.")
        self.assertEqual(r.lines[-1], skill.SECRETS_NOTE)

    def test_exit_0_with_an_error_line_is_a_refusal(self):
        r, ctx = run({VARS: ok([])}, {"A_VAR": common.Completed(
            0, "", "gh: Resource not accessible by integration (HTTP 403)\n")}, mode="apply")
        self.assertEqual(r.status, "failed")
        self.assertIn(G_UNTRUSTED, r.lines)
        self.assertEqual(len(ctx.writes), 1)

    def test_plan_never_writes(self):
        ctx = FakeContext({VARS: ok([])}, dict(ARGS))
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.set_command("variables", "A_VAR", "example-org/example-repo", "x"))
        r, ctx = run({VARS: ok([])})
        self.assertEqual((r.status, ctx.writes), ("would-update", []))

    def test_read_only_option_refuses_apply_before_reading(self):
        args = dict(ARGS, mode="apply")
        ctx = common.Context(PLUGIN, ROOT, "github_variables-set", skill, "apply", args,
                             read_only=True)
        self.assertFalse(ctx.writable)
        r = common.read_only_refusal(ctx)
        self.assertEqual((r.status, r.lines, r.block["outputs"], r.block["mode"]),
                         ("failed", [common.READ_ONLY_APPLY_SENTENCE], {}, "apply"))


G_UNTRUSTED = skill.G.UNTRUSTED


if __name__ == "__main__":
    unittest.main()
