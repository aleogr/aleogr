"""Unit tests of github_checkout-setup's plan, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs; the local file is written in a temporary folder. The scenarios
gh-checkout-* of mode=plan cover the rest, in the direct mode.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-repo-github"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "github_checkout-setup")

ARGS = {"owner": "example-org", "name": "example-repo", "mode": "plan"}
REPO = "gh api repos/example-org/example-repo"
CONTENTS = REPO + "/contents/.aleogr/project.json"
DECL = {"version": 1, "name": "demo", "list": [1, 2]}
SHA1 = "1" * 40
SHA2 = "2" * 40


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def fail(text, code=1):
    return common.Completed(code, "", text)


class FakeContext(common.Context):
    def __init__(self, answers, args):
        common.Context.__init__(self, PLUGIN, ROOT, "github_checkout-setup", skill,
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


class Base(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.dir = tempfile.mkdtemp()
        os.chdir(self.dir)
        os.makedirs(".aleogr")
        self.write(json.dumps(DECL, indent=2))

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.dir)

    def write(self, text):
        with open(".aleogr/project.json", "w", encoding="utf-8") as f:
            f.write(text)

    def run_skill(self, answers, **extra):
        args = dict(ARGS, **extra)
        ctx = FakeContext(answers, args)
        return skill.run(dict(args), ctx), ctx


class TestArguments(Base):
    def test_invalid_values_run_nothing(self):
        cases = [({"owner": ""}, "owner is missing."),
                 ({"path": "/etc/x"}, "path is not valid"),
                 ({"path": "a/../b"}, "path is not valid"),
                 ({"path": "a b"}, "path is not valid"),
                 ({"path": ""}, "path is not valid"),
                 ({"message": "a\"b"}, "message is not valid"),
                 ({"message": "cost $5"}, "message is not valid"),
                 ({"message": ""}, "message is not valid"),
                 ({"head": "yes"}, "head is not valid"),
                 ({"mode": "dry"}, "mode is not valid")]
        for extra, sentence in cases:
            with self.subTest(extra=extra):
                r, ctx = self.run_skill({}, **extra)
                self.assertEqual(r.status, "failed")
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertEqual(ctx.calls, [])
                o = r.block["outputs"]
                self.assertEqual(o["path"], extra.get("path", ".aleogr/project.json"))
                self.assertIsNone(o["state"])

    def test_apply_is_not_converted(self):
        self.assertIn("apply", skill.UNCONVERTED_MODES)
        self.assertNotIn("plan", skill.UNCONVERTED_MODES)


class TestPlan(Base):
    def test_equal_ignores_key_order_and_spacing(self):
        remote = json.dumps({"list": [1, 2], "name": "demo", "version": 1}).replace(
            "\n", "\r\n")
        r, ctx = self.run_skill({REPO: ok({"default_branch": "main"}), CONTENTS: ok(remote)})
        self.assertEqual((r.status, r.block["outputs"]["state"]), ("unchanged", "equal"))
        self.assertEqual(len(ctx.calls), 2)

    def test_repository_copy_is_given_to_a_caller_only(self):
        # project-plan notes the environments of the repository's copy from this.
        remote = {"version": 1, "name": "demo", "environments": {"dev": {}}}
        r, _ = self.run_skill({REPO: ok({"default_branch": "main"}), CONTENTS: ok(remote),
                               "git rev-parse --is-inside-work-tree": fail("fatal: no")})
        self.assertEqual(r.data, {"repositoryCopy": {"json": True, "value": remote}})
        self.assertNotIn("environments", common.render_answer(r))
        r, _ = self.run_skill({REPO: ok({"default_branch": "main"}), CONTENTS: ok("not json"),
                               "git rev-parse --is-inside-work-tree": fail("fatal: no")})
        self.assertEqual(r.data, {"repositoryCopy": {"json": False, "value": None}})
        r, _ = self.run_skill({REPO: ok({"default_branch": "main"}),
                               CONTENTS: fail("gh: Not Found (HTTP 404)"),
                               REPO + "/commits?per_page=2": ok([{"sha": SHA1}])})
        self.assertEqual(r.data, {"repositoryCopy": None})

    def test_list_order_and_booleans_matter(self):
        for remote in ({"version": 1, "name": "demo", "list": [2, 1]},
                       {"version": True, "name": "demo", "list": [1, 2]}, "not json"):
            with self.subTest(remote=remote):
                r, ctx = self.run_skill({REPO: ok({"default_branch": "main"}),
                                         CONTENTS: ok(remote),
                                         "git rev-parse --is-inside-work-tree":
                                         fail("fatal: not a git repository")})
                self.assertEqual(r.block["outputs"]["reason"], "not-a-checkout")

    def test_repository_absent_is_a_birth(self):
        r, ctx = self.run_skill({REPO: fail("gh: Not Found (HTTP 404)")})
        o = r.block["outputs"]
        self.assertEqual((r.status, o["state"], o["defaultBranch"]),
                         ("would-create", "not-sent", None))
        self.assertEqual(r.block["resources"], [])
        self.assertEqual(ctx.calls, [REPO])
        self.assertTrue(any("github_repo-create" in line for line in r.lines))

    def test_local_file_missing_or_invalid(self):
        for text in (None, "{not json"):
            with self.subTest(text=text):
                if text is None:
                    os.remove(".aleogr/project.json")
                else:
                    self.write(text)
                r, ctx = self.run_skill({REPO: ok({"default_branch": "trunk"})})
                o = r.block["outputs"]
                self.assertEqual((r.status, o["state"], o["defaultBranch"]),
                                 ("failed", None, "trunk"))
                self.assertEqual(ctx.calls, [REPO])
                self.write("{}")

    def test_commit_count(self):
        cases = [([{"sha": SHA1}, {"sha": SHA2}], "pending", "missing"),
                 ([], "failed", None)]
        for listed, status, state in cases:
            with self.subTest(listed=listed):
                r, _ = self.run_skill({REPO: ok({"default_branch": "main"}),
                                       CONTENTS: fail("gh: Not Found (HTTP 404)"),
                                       REPO + "/commits?per_page=2": ok(listed)})
                self.assertEqual((r.status, r.block["outputs"]["state"]), (status, state))
        r, _ = self.run_skill({REPO: ok({"default_branch": "main"}),
                               CONTENTS: fail("gh: Not Found (HTTP 404)"),
                               REPO + "/commits?per_page=2":
                               fail("gh: Git Repository is empty. (HTTP 409)")})
        self.assertEqual(r.status, "failed")
        self.assertIn("no commit", r.lines[0])
        self.assertEqual(r.block["pending"], [])

    def test_missing_pending_item(self):
        r, _ = self.run_skill({REPO: ok({"default_branch": "main"}),
                               CONTENTS: fail("gh: Not Found (HTTP 404)"),
                               REPO + "/commits?per_page=2": ok([{}, {}])},
                              path="conf/a.json")
        self.assertEqual(r.block["pending"], [])  # the local file is missing: failed
        os.makedirs("conf")
        with open("conf/a.json", "w") as f:
            f.write("{}")
        r, _ = self.run_skill({REPO: ok({"default_branch": "main"}),
                               CONTENTS.replace(".aleogr/project.json", "conf/a.json"):
                               fail("gh: Not Found (HTTP 404)"),
                               REPO + "/commits?per_page=2": ok([{}, {}])},
                              path="conf/a.json")
        self.assertEqual(r.block["pending"], [{
            "item": "declaration is not in the repository", "reason": "manual",
            "how": "open a pull request that adds conf/a.json"}])

    def test_head_check_not_a_checkout_is_equal(self):
        r, ctx = self.run_skill({REPO: ok({"default_branch": "main"}),
                                 CONTENTS: ok(DECL),
                                 "git rev-parse --is-inside-work-tree":
                                 fail("fatal: not a git repository")}, head="check")
        self.assertEqual((r.status, r.block["outputs"]["state"],
                          r.block["outputs"]["reason"]), ("unchanged", "equal", None))
        self.assertEqual(ctx.calls[-1], "git rev-parse --is-inside-work-tree")

    def test_head_check_never_runs_status(self):
        r, ctx = self.run_skill({REPO: ok({"default_branch": "main"}),
                                 CONTENTS: ok(DECL),
                                 "git rev-parse --is-inside-work-tree": ok("true\n"),
                                 "git remote get-url origin":
                                 ok("https://GitHub.com/Example-Org/example-repo.git/\n"),
                                 "git branch --show-current": ok("main\n"),
                                 "git rev-parse HEAD": ok(SHA1 + "\n"),
                                 REPO + "/commits/main": ok({"sha": SHA2}),
                                 REPO + "/commits/" + SHA1:
                                 fail("gh: No commit found (HTTP 422)")}, head="check")
        self.assertEqual((r.status, r.block["outputs"]["reason"]),
                         ("pending", "local-commits"))
        self.assertFalse(any(c.startswith("git status") for c in ctx.calls))

    def test_no_such_remote_and_git_missing(self):
        base = {REPO: ok({"default_branch": "main"}), CONTENTS: ok({"other": 1}),
                "git rev-parse --is-inside-work-tree": ok("true\n")}
        r, _ = self.run_skill(dict(base, **{"git remote get-url origin":
                                            fail("error: No such remote 'origin'", 2)}))
        self.assertEqual(r.block["outputs"]["reason"], "other-remote")
        self.assertEqual(r.block["pending"][0]["how"],
                         "this folder's origin is another repository")
        r, _ = self.run_skill(dict(base, **{"git rev-parse --is-inside-work-tree":
                                            fail("git: command not found", 127)}))
        self.assertEqual((r.status, r.block["outputs"]["state"]), ("failed", None))
        self.assertIn("git", r.lines[0])

    def test_other_branch_how_names_the_default_branch(self):
        r, _ = self.run_skill({REPO: ok({"default_branch": "trunk"}),
                               CONTENTS: ok({"other": 1}),
                               "git rev-parse --is-inside-work-tree": ok("true\n"),
                               "git remote get-url origin":
                               ok("https://github.com/example-org/example-repo\n"),
                               "git branch --show-current": ok("\n")})
        self.assertEqual(r.block["pending"][0]["how"], "git switch trunk")

    def test_raw_errors_are_never_repeated(self):
        r, _ = self.run_skill({REPO: fail("gh: Internal Server Error (HTTP 500)")})
        self.assertEqual(r.status, "failed")
        self.assertNotIn("Internal", "\n".join(r.lines))
        self.assertNotIn("500", "\n".join(r.lines))


if __name__ == "__main__":
    unittest.main()
