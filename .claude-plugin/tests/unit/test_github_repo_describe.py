"""Unit tests of github_repo-describe's rules, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs. The scenarios gh-describe-* cover the rest, in the direct mode.
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
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "github_repo-describe")

ARGS = {"owner": "example-org", "name": "example-repo"}
REPO = {"id": 7, "owner": {"id": 8}, "html_url": "https://github.com/example-org/example-repo",
        "visibility": "public", "default_branch": "main", "description": "",
        "topics": ["b", "a"], "allow_merge_commit": True, "allow_squash_merge": True,
        "allow_rebase_merge": False, "delete_branch_on_merge": True, "has_issues": True,
        "has_wiki": False, "has_projects": False}


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def fail(text, code=1):
    return common.Completed(code, "", text)


class FakeContext(common.Context):
    def __init__(self, answers, args=ARGS):
        common.Context.__init__(self, PLUGIN, ROOT, "github_repo-describe", skill, "plan",
                                args)
        self.answers = answers
        self.calls = []

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.calls.append(line)
        best = None
        for prefix in self.answers:
            if line == prefix or line.startswith(prefix + " "):
                if best is None or len(prefix) > len(best):
                    best = prefix
        return self.answers[best] if best else common.Completed(0, "", "")


def ruleset_file(name="ruleset-main.json"):
    with open(os.path.join(ROOT, "files", name), encoding="utf-8") as f:
        return json.load(f)


def answers(ruleset, listed=None):
    return {
        "gh api repos/example-org/example-repo": ok(REPO),
        "gh api repos/example-org/example-repo/rulesets": ok(
            listed if listed is not None else [{"id": 5, "name": "main"}]),
        "gh api repos/example-org/example-repo/rulesets/5": ok(ruleset),
    }


def run(ans, args=ARGS):
    ctx = FakeContext(ans, args)
    return skill.run(dict(args), ctx), ctx


class TestArguments(unittest.TestCase):
    def test_missing_and_invalid_run_nothing(self):
        cases = [({"name": "x"}, "owner is missing."),
                 ({"owner": "", "name": "x"}, "owner is missing."),
                 ({"owner": "o"}, "name is missing."),
                 ({"owner": "-o", "name": "x"}, "owner is not valid"),
                 ({"owner": "o" * 40, "name": "x"}, "owner is not valid"),
                 ({"owner": "o", "name": ".."}, "name is not valid"),
                 ({"owner": "o", "name": "a b"}, "name is not valid"),
                 ({"owner": "o", "name": "x", "checks": "all"}, "checks is not valid")]
        for args, sentence in cases:
            with self.subTest(args=args):
                r, ctx = run({}, args)
                self.assertEqual(r.status, "failed")
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertEqual(ctx.calls, [])
                self.assertIsNone(r.block["outputs"]["exists"])
                self.assertEqual(r.block["resources"], [])


class TestReads(unittest.TestCase):
    def test_outputs_of_step_1(self):
        r, _ = run(answers(ruleset_file(), listed=[]))
        o = r.block["outputs"]
        self.assertEqual((o["id"], o["ownerId"], o["description"], o["topics"]),
                         (7, 8, None, ["a", "b"]))
        self.assertEqual(list(o["settings"]), ["mergeCommit", "squash", "rebase",
                                               "deleteBranchOnMerge", "issues", "wiki",
                                               "projects"])
        self.assertEqual(o["protection"], {"state": "unprotected", "rulesetId": None,
                                           "matches": None, "requiredChecks": [],
                                           "otherRulesets": []})

    def test_gh_missing_or_not_logged_in(self):
        for c, word in ((fail("gh: command not found", 127), "installed"),
                        (fail("HTTP 401: Bad credentials"), "gh auth login")):
            with self.subTest(word=word):
                r, ctx = run({"gh api repos/example-org/example-repo": c})
                self.assertEqual(r.status, "failed")
                self.assertIn(word, r.lines[0])
                self.assertEqual(len(ctx.calls), 1)

    def test_exit_0_with_an_error_line_is_that_error(self):
        r, ctx = run({"gh api repos/example-org/example-repo":
                      ok("gh: Not Found (HTTP 404)\n")})
        self.assertEqual((r.status, r.block["outputs"]["exists"]), ("unchanged", False))
        self.assertTrue(any("could not be trusted" in line for line in r.lines))
        self.assertEqual(len(ctx.calls), 1)

    def test_failures_after_step_1_keep_the_repository(self):
        cases = [
            {"gh api repos/example-org/example-repo/rulesets": ok({"not": "a list"})},
            {"gh api repos/example-org/example-repo/rulesets": ok(
                [{"id": 5, "name": "main"}, {"id": 6, "name": "main"}])},
            {"gh api repos/example-org/example-repo/rulesets":
             fail("gh: Server Error (HTTP 500)")},
            {"gh api repos/example-org/example-repo/rulesets/5":
             fail("gh: Forbidden (HTTP 403)")},
        ]
        for extra in cases:
            with self.subTest(extra=list(extra.values())[0]):
                ans = answers(ruleset_file())
                ans.update(extra)
                r, _ = run(ans)
                o = r.block["outputs"]
                self.assertEqual(r.status, "failed")
                self.assertIs(o["exists"], True)
                self.assertEqual(o["url"], REPO["html_url"])
                self.assertEqual(o["protection"], {"state": None, "rulesetId": None,
                                                   "matches": None, "requiredChecks": [],
                                                   "otherRulesets": []})
                self.assertEqual(len(r.block["resources"]), 1)
                self.assertNotIn("500", "\n".join(r.lines))

    def test_unavailable_needs_upgrade(self):
        ans = answers(ruleset_file())
        ans["gh api repos/example-org/example-repo/rulesets"] = fail(
            "gh: Upgrade to GitHub Team to enable this feature. (HTTP 403)")
        r, ctx = run(ans)
        self.assertEqual((r.status, r.block["outputs"]["protection"]["state"]),
                         ("unchanged", "unavailable"))
        self.assertEqual(len(ctx.calls), 2)


class TestMatches(unittest.TestCase):
    def matches(self, mutate, name="ruleset-main.json", args=ARGS):
        got = copy.deepcopy(ruleset_file(name))
        got.update({"id": 5, "source": "x", "node_id": "n", "current_user_can_bypass": "never"})
        mutate(got)
        r, _ = run(answers(got), args)
        return r.block["outputs"]["protection"]["matches"]

    def test_order_and_extra_keys_are_ignored(self):
        def m(got):
            got["rules"].reverse()
            pr = [x for x in got["rules"] if x["type"] == "pull_request"][0]
            pr["parameters"]["allowed_merge_methods"].reverse()
            pr["parameters"]["required_reviewers"] = []
            got["bypass_actors"] = None
        self.assertIs(self.matches(m), True)

    def test_absent_bypass_actors_is_none(self):
        self.assertIs(self.matches(lambda got: got.pop("bypass_actors")), True)

    def test_differences(self):
        cases = [
            lambda got: got.update(enforcement="disabled"),
            lambda got: got["rules"].append({"type": "deletion"}),
            lambda got: got["rules"].pop(0),
            lambda got: got["conditions"]["ref_name"]["include"].append("main"),
            lambda got: got.update(bypass_actors=[{"actor_id": 1}]),
            lambda got: got["rules"][2]["parameters"].update(
                required_approving_review_count=False),
        ]
        for i, m in enumerate(cases):
            with self.subTest(case=i):
                self.assertIs(self.matches(m), False)

    def test_checks_ci_compares_contexts_as_a_set(self):
        args = dict(ARGS, checks="ci")

        def m(got):
            rsc = [x for x in got["rules"] if x["type"] == "required_status_checks"][0]
            rsc["parameters"]["required_status_checks"] = [{"context": "ci",
                                                            "integration_id": 1}]
        self.assertIs(self.matches(m, "ruleset-main-ci.json", args), True)

        def other(got):
            rsc = [x for x in got["rules"] if x["type"] == "required_status_checks"][0]
            rsc["parameters"]["required_status_checks"] = [{"context": "build"}]
        self.assertIs(self.matches(other, "ruleset-main-ci.json", args), False)

    def test_required_checks_are_sorted(self):
        got = ruleset_file("ruleset-main-ci.json")
        got["rules"][-1]["parameters"]["required_status_checks"] = [
            {"context": "z"}, {"context": "ci"}]
        self.assertEqual(skill.required_checks(got), ["ci", "z"])


if __name__ == "__main__":
    unittest.main()
