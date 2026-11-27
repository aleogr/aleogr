"""Unit tests of github_pull-request-open's plan, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs. The scenarios gh-pr-open-* of mode=plan cover the rest, in the direct mode.
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
skill = load_skill(PLUGIN, "github_pull-request-open")

ARGS = {"owner": "example-org", "name": "example-repo", "paths": "a.json,b/c.json"}
REPO = "gh api repos/example-org/example-repo"
PRS = "gh pr list --repo example-org/example-repo"
SHA1 = "1" * 40


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def fail(text, code=1):
    return common.Completed(code, "", text)


class FakeContext(common.Context):
    def __init__(self, answers, args):
        common.Context.__init__(self, PLUGIN, ROOT, "github_pull-request-open", skill,
                                args.get("mode") or "plan", args)
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


def ready(**over):
    a = {REPO: ok({"default_branch": "main"}), PRS: ok([]),
         "git rev-parse --is-inside-work-tree": ok("true\n"),
         "git remote get-url origin": ok("https://github.com/example-org/example-repo.git\n"),
         "git branch --show-current": ok("main\n"),
         "git rev-parse HEAD": ok(SHA1 + "\n"),
         REPO + "/commits/" + SHA1: ok({"sha": SHA1}),
         "git status --porcelain --": ok("")}
    a.update(over)
    return a


def run(answers, **extra):
    args = dict(ARGS, **extra)
    ctx = FakeContext(answers, args)
    return skill.run(dict(args), ctx), ctx


class TestArguments(unittest.TestCase):
    def test_invalid_values_run_nothing(self):
        cases = [({"paths": ""}, "paths is missing."),
                 ({"paths": "a,,b"}, "paths is not valid"),
                 ({"paths": "./a"}, "paths is not valid"),
                 ({"paths": "a/"}, "paths is not valid"),
                 ({"paths": "a//b"}, "paths is not valid"),
                 ({"paths": "../a"}, "paths is not valid"),
                 ({"title": "x" * 101}, "title is not valid"),
                 ({"body": "a`b"}, "body is not valid"),
                 ({"note": "n" * 301}, "note is not valid"),
                 ({"note": "a“b"}, "note is not valid"),
                 ({"mode": "now"}, "mode is not valid")]
        for extra, sentence in cases:
            with self.subTest(extra=extra):
                r, ctx = run({}, **extra)
                self.assertEqual(r.status, "failed")
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertEqual(ctx.calls, [])
                self.assertEqual(r.block["outputs"], {
                    "folder": None, "changed": [], "openPullRequest": None,
                    "pullRequest": None, "defaultBranch": None})

    def test_title_is_not_required_in_plan(self):
        r, _ = run(ready())
        self.assertEqual(r.status, "unchanged")

    def test_paths_named_twice_count_once(self):
        self.assertEqual(skill.split_paths("a,b,a"), ["a", "b"])

    def test_full_body(self):
        self.assertEqual(skill.full_body({}), "Proposed by aleogr.")
        self.assertEqual(skill.full_body({"body": "B.", "note": "N."}), "B. N.")


class TestPlan(unittest.TestCase):
    def test_repository_absent_fails(self):
        r, ctx = run({REPO: fail("gh: Not Found (HTTP 404)")})
        self.assertEqual(r.status, "failed")
        self.assertIn("github_repo-create", r.lines[0])
        self.assertEqual(len(ctx.calls), 1)

    def test_tooling_pull_request_is_the_lowest_of_the_repository(self):
        listed = [{"number": 9, "url": "u9", "headRefName": "aleogr/change-b",
                   "isCrossRepository": False},
                  {"number": 4, "url": "u4", "headRefName": "aleogr/change-a",
                   "isCrossRepository": False},
                  {"number": 2, "url": "u2", "headRefName": "aleogr/change-c",
                   "isCrossRepository": True},
                  {"number": 1, "url": "u1", "headRefName": "feature",
                   "isCrossRepository": False}]
        r, _ = run(ready(**{PRS: ok(listed)}))
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.block["outputs"]["openPullRequest"],
                         {"number": 4, "url": "u4", "branch": "aleogr/change-a"})
        self.assertEqual(r.block["pending"], [{"item": "pull request #4 is open",
                                               "reason": "manual", "how": "merge or close u4"}])

    def test_both_items_in_order_and_no_status_read(self):
        listed = [{"number": 4, "url": "u4", "headRefName": "aleogr/change-a",
                   "isCrossRepository": False}]
        r, ctx = run(ready(**{PRS: ok(listed), "git branch --show-current": ok("dev\n")}))
        self.assertEqual([p["item"] for p in r.block["pending"]],
                         ["pull request #4 is open", "this folder needs attention"])
        self.assertEqual(r.block["pending"][1]["how"], "git switch main")
        self.assertEqual(r.block["outputs"]["folder"], "other-branch")
        self.assertFalse(any(c.startswith("git status") or c.startswith("git rev-parse HEAD")
                             for c in ctx.calls))

    def test_pr_list_not_a_list_fails(self):
        r, _ = run(ready(**{PRS: ok({"x": 1})}))
        self.assertEqual((r.status, r.block["outputs"]["defaultBranch"]), ("failed", "main"))

    def test_changed_follow_the_order_of_paths(self):
        r, ctx = run(ready(**{"git status --porcelain --":
                              ok(" M b/c.json\n?? a.json\n")}))
        self.assertEqual(ctx.calls[-1], "git status --porcelain -- a.json b/c.json")
        self.assertEqual((r.status, r.block["outputs"]["changed"]),
                         ("would-create", ["a.json", "b/c.json"]))
        self.assertTrue(any('--body "Proposed by aleogr."' in line for line in r.lines))

    def test_rename_takes_the_new_path(self):
        r, _ = run(ready(**{"git status --porcelain --": ok("R  old.json -> a.json\n")}))
        self.assertEqual(r.block["outputs"]["changed"], ["a.json"])

    def test_a_folder_is_refused(self):
        for out in ("?? b/\n", "?? b/c.json/d\n"):
            with self.subTest(out=out):
                r, _ = run(ready(**{"git status --porcelain --": ok(out)}), paths="b")
                self.assertEqual((r.status, r.block["outputs"]["changed"]), ("failed", []))
                self.assertIn("paths must be files", r.lines[0])

    def test_local_commits(self):
        r, _ = run(ready(**{REPO + "/commits/" + SHA1: fail("gh: No commit (HTTP 422)")}))
        self.assertEqual((r.status, r.block["outputs"]["folder"]),
                         ("pending", "local-commits"))


if __name__ == "__main__":
    unittest.main()
