"""Unit tests of github_repo-configure: its arguments, the stop before a visibility
change, the cases no scenario covers, and its golden commands.

The skill's run() is given a context whose read() answers from a dict (a list answers
the calls of one command in turn) and whose execute() (reached only through ctx.write,
after the allowlist of writes accepted the command) records the write and answers from
another dict, so no provider command runs. The scenarios gh-configure-* cover the rest,
in the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-repo-github"
SKILL = "github_repo-configure"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ARGS = {"owner": "example-org", "name": "example-repo"}
FULL = "example-org/example-repo"
READ = "gh api repos/example-org/example-repo"


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def fail(text, code=1):
    return common.Completed(code, "", text)


def repo(**over):
    r = {"visibility": "private", "description": "An example repository",
         "topics": ["keep", "old"], "allow_merge_commit": True, "allow_squash_merge": True,
         "allow_rebase_merge": True, "delete_branch_on_merge": False, "has_issues": True,
         "has_wiki": True, "has_projects": True}
    r.update(over)
    return r


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
        line = " ".join(str(a) for a in argv)
        for part, answer in self.write_answers.items():
            if part in line:
                return answer
        return common.Completed(0, "", "")

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


class TestArguments(unittest.TestCase):
    def test_rules_in_order_and_no_command(self):
        cases = [({"name": "", "wiki": "x"}, "name is missing."),
                 ({}, "Nothing to configure was given."),
                 ({"owner": "a_b"}, "Nothing to configure was given."),
                 ({"owner": "a_b", "wiki": "x"}, "owner is not valid"),
                 ({"description": ""}, "description is not valid"),
                 ({"description": "a`b`"}, "description is not valid"),
                 ({"topics": "Keep"}, "topics is not valid"),
                 ({"topics": "a,"}, "topics is not valid"),
                 ({"wiki": "yes"}, "wiki is not valid: it must be true or false."),
                 ({"visibility": "internal"}, "visibility is not valid"),
                 ({"wiki": "true", "confirmVisibility": "public"},
                  "confirmVisibility is not valid"),
                 ({"visibility": "private", "confirmVisibility": "public"},
                  "confirmVisibility is not valid"),
                 ({"visibility": "public", "confirmVisibility": "internal"},
                  "confirmVisibility is not valid"),
                 ({"mergeCommit": "false", "squash": "false", "rebase": "false"},
                  "mergeCommit, squash and rebase are not valid"),
                 ({"wiki": "true", "mode": "later"}, "mode is not valid")]
        for over, sentence in cases:
            with self.subTest(over=over):
                r, ctx = run({}, **over)
                self.assertEqual(r.status, "failed")
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertEqual((ctx.calls, ctx.writes), ([], []))
                self.assertEqual(r.block["outputs"], skill.failed_outputs())
                self.assertEqual(r.block["cost"]["notes"], "no cost: nothing was changed")

    def test_empty_topics_is_a_setting(self):
        wanted, problem = skill.validate(dict(ARGS, topics=""))
        self.assertIsNone(problem)
        self.assertEqual(wanted, [("topics", [])])


class TestGoldenCommands(unittest.TestCase):
    """Steps 4 and 5 of the SKILL.md, as it writes the commands (only the flags of the
    settings that differ, in this order; the visibility in its own command, after):

        gh repo edit <owner>/<name> --description "<description>"
            --enable-merge-commit=<bool> --enable-squash-merge=<bool>
            --enable-rebase-merge=<bool> --delete-branch-on-merge=<bool>
            --enable-issues=<bool> --enable-wiki=<bool> --enable-projects=<bool>
            --add-topic <t> --remove-topic <t>
        gh repo edit <owner>/<name> --visibility <value> --accept-visibility-change-consequences
    """

    def test_every_flag_in_order_then_visibility(self):
        r, ctx = run({READ: [ok(repo(visibility="public", allow_merge_commit=False,
                                     allow_squash_merge=False)),
                             ok(repo(visibility="private", description="New text, here",
                                     topics=["keep", "new"], allow_merge_commit=True,
                                     allow_squash_merge=True, allow_rebase_merge=False,
                                     delete_branch_on_merge=True, has_issues=False,
                                     has_wiki=False, has_projects=False))]},
                     mode="apply", projects="false", topics="new,keep", wiki="false",
                     issues="false", deleteBranchOnMerge="true", rebase="false",
                     squash="true", mergeCommit="true", description="New text, here",
                     visibility="private", confirmVisibility="private")
        self.assertEqual(ctx.writes, [
            ["gh", "repo", "edit", FULL, "--description", "New text, here",
             "--enable-merge-commit=true", "--enable-squash-merge=true",
             "--enable-rebase-merge=false", "--delete-branch-on-merge=true",
             "--enable-issues=false", "--enable-wiki=false", "--enable-projects=false",
             "--add-topic", "new", "--remove-topic", "old"],
            ["gh", "repo", "edit", FULL, "--visibility", "private",
             "--accept-visibility-change-consequences"]])
        self.assertEqual(ctx.calls, [READ, READ])
        self.assertEqual((r.status, r.block["pending"]), ("updated", []))
        self.assertEqual([c["setting"] for c in r.block["outputs"]["changes"]],
                         ["description", "topics", "mergeCommit", "squash", "rebase",
                          "deleteBranchOnMerge", "issues", "wiki", "projects", "visibility"])
        for w in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, w, root=ROOT), w)

    def test_one_flag_only(self):
        r, ctx = run({READ: ok(repo())}, mode="apply", wiki="false", issues="true")
        self.assertEqual(ctx.writes, [["gh", "repo", "edit", FULL, "--enable-wiki=false"]])

    def test_removing_every_topic(self):
        r, ctx = run({READ: ok(repo())}, mode="apply", topics="")
        self.assertEqual(ctx.writes, [["gh", "repo", "edit", FULL, "--remove-topic", "keep",
                                       "--remove-topic", "old"]])


class TestVisibilityNeedsConfirmation(unittest.TestCase):
    def test_only_visibility_unconfirmed_changes_nothing(self):
        r, ctx = run({READ: ok(repo())}, mode="apply", visibility="public")
        self.assertEqual((r.status, ctx.writes, ctx.calls), ("pending", [], [READ]))
        self.assertEqual(r.lines[0], "Make `example-org/example-repo` PUBLIC? Its whole "
                                     "history becomes visible.")
        self.assertEqual(r.block["pending"], [{
            "item": "confirm visibility public", "reason": "manual",
            "how": "/aleogr-repo-github:github_repo-configure owner=example-org "
                   "name=example-repo visibility=public confirmVisibility=public "
                   "mode=apply"}])
        self.assertEqual(r.block["outputs"]["changes"], [])

    def test_private_question(self):
        r, ctx = run({READ: ok(repo(visibility="public"))}, mode="apply",
                     visibility="private")
        self.assertEqual(r.lines[0], "Make `example-org/example-repo` PRIVATE? Branch "
                                     "protection stops being enforced on the free plan.")
        self.assertEqual(ctx.writes, [])

    def test_never_visibility_in_the_settings_command(self):
        r, ctx = run({READ: ok(repo())}, mode="apply", wiki="false", visibility="public")
        self.assertEqual(len(ctx.writes), 1)
        self.assertNotIn("--visibility", ctx.writes[0])
        argv = ["gh", "repo", "edit", FULL, "--enable-wiki=false", "--visibility", "public"]
        self.assertIsNotNone(common.write_refusal(SKILL, argv, root=ROOT))

    def test_plan_and_read_only_never_write(self):
        r, ctx = run({READ: ok(repo())}, wiki="false", visibility="public",
                     confirmVisibility="public")
        self.assertEqual((r.status, ctx.writes), ("would-update", []))
        self.assertIn("    gh repo edit example-org/example-repo --enable-wiki=false", r.lines)
        ctx = common.Context(PLUGIN, ROOT, SKILL, skill, "apply", dict(ARGS, mode="apply"),
                             read_only=True)
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.visibility_command(FULL, "public"))


class TestSteps(unittest.TestCase):
    def test_merge_methods_read_all_off(self):
        r, ctx = run({READ: ok(repo(allow_merge_commit=False, allow_squash_merge=False))},
                     mode="apply", rebase="false")
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertEqual(r.lines[0], skill.MERGE_READ)
        self.assertEqual(r.block["resources"][0]["id"], FULL)
        self.assertEqual(r.block["outputs"]["changes"], [])
        self.assertEqual(r.block["outputs"]["settings"]["rebase"], True)

    def test_null_description_differs(self):
        r, _ = run({READ: ok(repo(description=None))}, description="Text")
        self.assertEqual(r.block["outputs"]["changes"],
                         [{"setting": "description", "from": None, "to": "Text"}])

    def test_read_failures(self):
        cases = [(fail("gh: Not Found (HTTP 404)"), "The repository example-org/example-repo "
                  "does not exist, or this account cannot see it; github_repo-create"),
                 (fail("gh: Server Error (HTTP 500)"), "The repository example-org/"
                  "example-repo could not be read: GitHub answered"),
                 (fail("bad credentials (HTTP 401)"), "gh is not logged in")]
        for c, sentence in cases:
            with self.subTest(sentence=sentence[:40]):
                r, ctx = run({READ: c}, mode="apply", wiki="false")
                self.assertEqual((r.status, ctx.writes), ("failed", []))
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertEqual(r.block["resources"], [])

    def test_visibility_refused_after_settings_is_updated_with_item(self):
        r, ctx = run({READ: [ok(repo()), ok(repo(has_wiki=False))]},
                     {"--visibility": fail("HTTP 422: cannot")}, mode="apply",
                     wiki="false", visibility="public", confirmVisibility="public")
        self.assertEqual(len(ctx.writes), 2)
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.block["outputs"]["changes"],
                         [{"setting": "wiki", "from": True, "to": False}])
        self.assertEqual(r.block["pending"], [{
            "item": "visibility", "reason": "manual",
            "how": "/aleogr-repo-github:github_repo-configure owner=example-org "
                   "name=example-repo visibility=public confirmVisibility=public "
                   "mode=apply"}])
        self.assertNotIn("422", "\n".join(r.lines))

    def test_visibility_refused_alone_is_failed(self):
        r, ctx = run({READ: ok(repo())}, {"--visibility": fail("HTTP 403: admin")},
                     mode="apply", visibility="public", confirmVisibility="public")
        self.assertEqual((r.status, len(ctx.writes), ctx.calls), ("failed", 1, [READ]))
        self.assertEqual(r.block["outputs"]["changes"], [])

    def test_still_differs_after_verification(self):
        r, _ = run({READ: [ok(repo()), ok(repo(has_wiki=True, has_issues=False))]},
                   mode="apply", wiki="false", issues="false", description="A b")
        self.assertEqual(r.status, "updated")
        # Sent: description, issues, wiki; still differing: description, wiki.
        self.assertEqual([c["setting"] for c in r.block["outputs"]["changes"]], ["issues"])
        self.assertEqual(r.block["pending"], [{
            "item": "configure", "reason": "manual",
            "how": "/aleogr-repo-github:github_repo-configure owner=example-org "
                   "name=example-repo description=\"A b\" wiki=false mode=apply"}])
        self.assertEqual(r.block["outputs"]["settings"]["wiki"], True)
        r, _ = run({READ: [ok(repo()), ok(repo(description="other"))]},
                   mode="apply", wiki="false", description="A b")
        self.assertEqual(r.block["outputs"]["changes"], [])
        self.assertEqual(r.block["pending"], [{
            "item": "configure", "reason": "manual",
            "how": "/aleogr-repo-github:github_repo-configure owner=example-org "
                   "name=example-repo description=\"A b\" wiki=false mode=apply"}])

    def test_verification_read_failed(self):
        r, _ = run({READ: [ok(repo()), fail("gh: Server Error (HTTP 503)")]},
                   mode="apply", wiki="false")
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.block["outputs"]["settings"]["wiki"], False)
        self.assertEqual(r.block["pending"][0]["item"], "verify")

    def test_unconfirmed_visibility_not_verified(self):
        r, _ = run({READ: [ok(repo()), ok(repo(has_wiki=False))]}, mode="apply",
                   wiki="false", visibility="public")
        self.assertEqual([p["item"] for p in r.block["pending"]],
                         ["confirm visibility public"])

    def test_edit_exit_0_with_an_error_line_is_a_refusal(self):
        r, ctx = run({READ: ok(repo())}, {"--enable-wiki": common.Completed(
            0, "", "gh: Must have admin rights to Repository. (HTTP 403)\n")},
            mode="apply", wiki="false")
        self.assertEqual((r.status, ctx.calls), ("failed", [READ]))
        self.assertIn(skill.G.UNTRUSTED, r.lines)


if __name__ == "__main__":
    unittest.main()
