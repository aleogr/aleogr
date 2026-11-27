"""Unit tests of github_branch-protect: its arguments, the comparison with the ruleset
file, the cases no scenario covers, and its golden commands.

The skill's run() is given a context whose read() answers from a dict (a list answers
the calls of one command in turn) and whose execute() (reached only through ctx.write,
after the allowlist of writes accepted the command) records the write and answers from
another dict, so no provider command runs. The scenarios gh-protect-* cover the rest, in
the direct mode.
"""

import copy
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-repo-github"
SKILL = "github_branch-protect"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ARGS = {"owner": "example-org", "name": "example-repo"}
FULL = "example-org/example-repo"
REPO = "gh api repos/example-org/example-repo"
LIST = "gh api repos/example-org/example-repo/rulesets"
ONE = "gh api repos/example-org/example-repo/rulesets/123"


def load(name):
    with open(os.path.join(ROOT, "files", name), encoding="utf-8") as f:
        return json.load(f)


MAIN = load("ruleset-main.json")
MAIN_CI = load("ruleset-main-ci.json")


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def fail(text, code=1):
    return common.Completed(code, "", text)


def read_back(want, **over):
    """A ruleset as GitHub gives it back: the file plus keys of its own."""
    r = copy.deepcopy(want)
    r.update({"id": 123, "source": FULL, "node_id": "RRS_x", "current_user_can_bypass":
              "never"})
    r.update(over)
    return r


UPGRADE = fail("gh: Upgrade to GitHub Pro or make this repository public to enable this "
               "feature. (HTTP 403)")


class FakeContext(common.Context):
    def __init__(self, answers, args, writes=None):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or "plan", args)
        self.answers = dict((k, list(v) if isinstance(v, list) else [v])
                            for k, v in answers.items())
        self.write_answers = writes or {}
        self.calls = []
        self.writes = []

    def execute(self, argv, timeout=None):
        self.writes.append(list(argv))
        return self.write_answers.get(argv[4], common.Completed(0, "", ""))

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.calls.append(line)
        queue = self.answers.get(line)
        if not queue:
            return common.Completed(0, "", "")
        return queue.pop(0) if len(queue) > 1 else queue[0]


def run(answers, writes=None, **over):
    args = dict(ARGS, **over)
    ctx = FakeContext(answers, args, writes)
    return skill.run(dict(args), ctx), ctx


def existing(ruleset, others=()):
    listed = [{"id": 123, "name": "main"}] + [{"id": 400 + i, "name": n}
                                               for i, n in enumerate(others)]
    return {REPO: ok({"visibility": "public"}), LIST: ok(listed), ONE: ok(ruleset)}


class TestArguments(unittest.TestCase):
    def test_rules_in_order_and_no_command(self):
        cases = [({"owner": ""}, "owner is missing."),
                 ({"name": ""}, "name is missing."),
                 ({"owner": "a--"}, "owner is not valid"),
                 ({"name": "a b"}, "name is not valid"),
                 ({"mode": "later", "checks": "lint"}, "mode is not valid"),
                 ({"checks": "lint"}, "checks is not valid: it must be ci or none.")]
        for over, sentence in cases:
            with self.subTest(over=over):
                r, ctx = run({}, **over)
                self.assertEqual(r.status, "failed")
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertEqual((ctx.calls, ctx.writes), ([], []))
                self.assertEqual(r.block["outputs"], {
                    "rulesetId": None, "rules": [], "requiredApprovals": None,
                    "requiredChecks": [], "otherRulesets": []})
                self.assertEqual(r.block["cost"], {"fixed": False, "notes": "no cost"})


class TestGoldenCommands(unittest.TestCase):
    """Step 6 of the SKILL.md, as it writes the commands:

        gh api --method POST repos/<owner>/<name>/rulesets --input "${CLAUDE_PLUGIN_ROOT}/files/<ruleset file>"
        gh api --method PUT repos/<owner>/<name>/rulesets/<id> --input "${CLAUDE_PLUGIN_ROOT}/files/<ruleset file>"
    """

    def test_post(self):
        r, ctx = run({REPO: ok({}), LIST: ok([]), ONE: ok(read_back(MAIN))},
                     {"repos/%s/rulesets" % FULL: ok({"id": 123})}, mode="apply")
        self.assertEqual(ctx.writes, [
            ["gh", "api", "--method", "POST", "repos/example-org/example-repo/rulesets",
             "--input", os.path.join(ROOT, "files", "ruleset-main.json")]])
        self.assertEqual(ctx.calls, [REPO, LIST, ONE])
        self.assertEqual((r.status, r.block["outputs"]["rulesetId"], r.block["pending"]),
                         ("created", 123, []))

    def test_put_with_checks(self):
        answers = existing(read_back(MAIN))
        answers[ONE] = [answers[ONE], ok(read_back(MAIN_CI))]
        r, ctx = run(answers, mode="apply", checks="ci")
        self.assertEqual(ctx.writes, [
            ["gh", "api", "--method", "PUT", "repos/example-org/example-repo/rulesets/123",
             "--input", os.path.join(ROOT, "files", "ruleset-main-ci.json")]])
        self.assertEqual(ctx.calls, [REPO, LIST, ONE, ONE])
        self.assertEqual((r.status, r.block["outputs"]["requiredChecks"]), ("updated", ["ci"]))

    def test_each_golden_command_is_on_the_allowlist(self):
        for name in ("ruleset-main.json", "ruleset-main-ci.json"):
            path = os.path.join(ROOT, "files", name)
            for rid in (None, 123):
                argv = skill.write_command(FULL, rid, path)
                self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT), argv)
        other = skill.write_command(FULL, None, "/tmp/ruleset-main.json")
        self.assertIsNotNone(common.write_refusal(SKILL, other, root=ROOT))

    def test_shown_command_quotes_the_file(self):
        r, _ = run({REPO: ok({}), LIST: ok([])})
        self.assertEqual(r.status, "would-create")
        self.assertIn('    gh api --method POST repos/example-org/example-repo/rulesets '
                      '--input "%s"' % os.path.join(ROOT, "files", "ruleset-main.json"),
                      r.lines)


class TestNoWriteWithoutApply(unittest.TestCase):
    def test_plan_never_writes(self):
        for answers in ({REPO: ok({}), LIST: ok([])},
                        existing(read_back(MAIN, enforcement="disabled"))):
            r, ctx = run(answers)
            self.assertEqual(ctx.writes, [])
            self.assertIn(r.status, ("would-create", "would-update"))
        ctx = FakeContext({}, dict(ARGS))
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.write_command(FULL, None,
                                          os.path.join(ROOT, "files", "ruleset-main.json")))

    def test_read_only_option_refuses_the_write(self):
        ctx = common.Context(PLUGIN, ROOT, SKILL, skill, "apply", dict(ARGS, mode="apply"),
                             read_only=True)
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.write_command(FULL, 123,
                                          os.path.join(ROOT, "files", "ruleset-main.json")))


class TestComparison(unittest.TestCase):
    def test_equal_ignores_extra_keys_and_order(self):
        got = read_back(MAIN)
        got["rules"] = list(reversed(got["rules"]))
        got["rules"][0]["parameters"]["required_reviewers"] = []
        got["rules"][0]["parameters"]["allowed_merge_methods"] = ["rebase", "merge", "squash"]
        got["conditions"]["ref_name"] = {"exclude": [], "include": ["~DEFAULT_BRANCH"]}
        self.assertEqual(skill.differences(MAIN, got), [])

    def test_bypass_actors_none_forms_are_equal(self):
        for v in (None, [], "absent"):
            got = read_back(MAIN)
            if v == "absent":
                del got["bypass_actors"]
            else:
                got["bypass_actors"] = v
            self.assertEqual(skill.differences(MAIN, got), [], v)

    def test_rule_types_exactly_once(self):
        got = read_back(MAIN_CI)
        self.assertEqual(skill.differences(MAIN, got),
                         ["the rule required_status_checks is not in the file"])
        self.assertEqual(skill.differences(MAIN_CI, read_back(MAIN)),
                         ["the rule required_status_checks is missing"])
        got = read_back(MAIN)
        got["rules"].append({"type": "deletion"})
        self.assertEqual(skill.differences(MAIN, got),
                         ["the rule deletion is there more than once"])

    def test_required_checks_compared_by_context(self):
        got = read_back(MAIN_CI)
        got["rules"][3]["parameters"]["required_status_checks"] = [
            {"context": "ci", "integration_id": 1}]
        self.assertEqual(skill.differences(MAIN_CI, got), [])
        got["rules"][3]["parameters"]["required_status_checks"] = [{"context": "lint"}]
        self.assertEqual(len(skill.differences(MAIN_CI, got)), 1)

    def test_a_scalar_difference_names_both_values(self):
        got = read_back(MAIN, enforcement="evaluate")
        self.assertEqual(skill.differences(MAIN, got),
                         ['enforcement: found "evaluate", the file has "active"'])


class TestSteps(unittest.TestCase):
    def test_upgrade_on_the_list_is_pending_in_both_modes(self):
        for mode in ("plan", "apply"):
            r, ctx = run({REPO: ok({}), LIST: UPGRADE}, mode=mode, checks="ci")
            self.assertEqual((r.status, ctx.writes, ctx.calls), ("pending", [], [REPO, LIST]))
            self.assertEqual(r.block["pending"], [{
                "item": "branch protection needs a paid plan or a public repository",
                "reason": "plan-limit",
                "how": "make example-org/example-repo public (/aleogr-repo-github:"
                       "github_repo-configure owner=example-org name=example-repo "
                       "visibility=public mode=apply) or move the owner to a paid plan, "
                       "then run /aleogr-repo-github:github_branch-protect "
                       "owner=example-org name=example-repo mode=apply checks=ci"}])

    def test_403_without_upgrade_is_failed(self):
        r, _ = run({REPO: ok({}), LIST: fail("gh: Must have admin rights (HTTP 403)")})
        self.assertEqual((r.status, r.block["pending"]), ("failed", []))

    def test_name_is_case_sensitive_and_others_are_listed(self):
        r, ctx = run({REPO: ok({}), LIST: ok([{"id": 7, "name": "Main"},
                                             {"id": 8, "name": "main-2"}])})
        self.assertEqual(r.status, "would-create")
        self.assertEqual(r.block["outputs"]["otherRulesets"], ["Main", "main-2"])
        self.assertEqual(ctx.calls, [REPO, LIST])

    def test_two_main_failed_with_the_others(self):
        r, ctx = run({REPO: ok({}), LIST: ok([{"id": 1, "name": "main"},
                                             {"id": 2, "name": "main"},
                                             {"id": 3, "name": "tags"}])}, mode="apply")
        self.assertEqual((r.status, ctx.calls), ("failed", [REPO, LIST]))
        self.assertEqual(r.block["outputs"]["otherRulesets"], ["tags"])
        self.assertEqual(r.block["resources"], [])

    def test_not_a_list_is_failed(self):
        r, _ = run({REPO: ok({}), LIST: ok({"id": 1})})
        self.assertEqual(r.status, "failed")

    def test_unreadable_file_is_failed(self):
        original = skill.G.read_local
        skill.G.read_local = lambda path: (None, "unreadable")
        try:
            r, ctx = run({REPO: ok({}), LIST: ok([])}, mode="apply")
        finally:
            skill.G.read_local = original
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertEqual(r.lines[0], "The plugin's file ruleset-main.json could not be read; "
                                     "nothing was changed.")

    def test_post_answer_without_id_is_verify(self):
        r, ctx = run({REPO: ok({}), LIST: ok([])}, mode="apply")
        self.assertEqual((r.status, ctx.calls), ("created", [REPO, LIST]))
        self.assertEqual(r.block["outputs"]["rulesetId"], None)
        self.assertEqual(r.block["resources"], [])
        self.assertEqual(r.block["outputs"]["rules"],
                         ["deletion", "non_fast_forward", "pull_request"])
        self.assertEqual(r.block["pending"][0]["item"], "verify")

    def test_verification_differs(self):
        answers = existing(read_back(MAIN, enforcement="disabled"))
        answers[ONE] = [answers[ONE], ok(read_back(MAIN, enforcement="evaluate"))]
        r, _ = run(answers, mode="apply")
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.block["pending"], [{
            "item": "branch protection differs", "reason": "manual",
            "how": "/aleogr-repo-github:github_branch-protect owner=example-org "
                   "name=example-repo mode=apply"}])

    def test_verification_read_failed_takes_the_file(self):
        bad = read_back(MAIN)
        bad["rules"] = bad["rules"][:1]
        answers = existing(bad)
        answers[ONE] = [answers[ONE], fail("gh: Server Error (HTTP 500)")]
        r, _ = run(answers, mode="apply", checks="ci")
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.block["outputs"]["requiredChecks"], ["ci"])
        self.assertEqual(r.block["pending"], [{
            "item": "verify", "reason": "manual",
            "how": "/aleogr-repo-github:github_repo-describe owner=example-org "
                   "name=example-repo checks=ci"}])

    def test_put_refused_keeps_the_read_ruleset(self):
        r, _ = run(existing(read_back(MAIN, enforcement="disabled")),
                   {"repos/%s/rulesets/123" % FULL: fail("gh: Validation Failed (HTTP 422)")},
                   mode="apply")
        self.assertEqual((r.status, r.block["outputs"]["rulesetId"]), ("failed", 123))
        self.assertNotIn("422", "\n".join(r.lines))
        self.assertNotIn("Validation Failed", "\n".join(r.lines))

    def test_write_exit_0_with_an_error_line_is_a_refusal(self):
        r, _ = run({REPO: ok({}), LIST: ok([])}, {"repos/%s/rulesets" % FULL:
                   common.Completed(0, "", "gh: Validation Failed (HTTP 422)\n")},
                   mode="apply")
        self.assertEqual(r.status, "failed")
        self.assertIn(skill.G.UNTRUSTED, r.lines)


if __name__ == "__main__":
    unittest.main()
