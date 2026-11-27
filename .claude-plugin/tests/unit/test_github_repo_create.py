"""Unit tests of github_repo-create: its arguments, the stop before a public create, the
cases no scenario covers, and its golden commands.

The skill's run() is given a context whose read() answers from a dict (a list answers
the calls of one command in turn) and whose execute() (reached only through ctx.write,
after the allowlist of writes accepted the command) records the write and answers from
another dict, so no provider command runs. The scenarios gh-create-* cover the rest, in
the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-repo-github"
SKILL = "github_repo-create"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ARGS = {"owner": "example-org", "name": "example-repo"}
READ = "gh api repos/example-org/example-repo"
NOT_FOUND = common.Completed(1, '{"message":"Not Found"}', "gh: Not Found (HTTP 404)\n")


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def fail(text, code=1):
    return common.Completed(code, "", text)


def repo(**over):
    r = {"html_url": "https://github.com/example-org/example-repo",
         "ssh_url": "git@github.com:example-org/example-repo.git",
         "visibility": "private", "default_branch": "main", "description": None,
         "topics": []}
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
        for prefix, answer in self.write_answers.items():
            if line.startswith(prefix):
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
        cases = [({"owner": ""}, "owner is missing."),
                 ({"name": ""}, "name is missing."),
                 ({"owner": "-x"}, "owner is not valid"),
                 ({"name": ".."}, "name is not valid"),
                 ({"visibility": "internal"}, "visibility is not valid"),
                 ({"confirmVisibility": "public"}, "confirmVisibility is not valid"),
                 ({"visibility": "private", "confirmVisibility": "public"},
                  "confirmVisibility is not valid"),
                 ({"visibility": "private", "confirmVisibility": "private"},
                  "confirmVisibility is not valid"),
                 ({"description": ""}, "description is not valid"),
                 ({"description": "Status $(whoami)"}, "description is not valid"),
                 ({"description": "a “b”"}, "description is not valid"),
                 ({"topics": "Bad_Topic"}, "topics is not valid"),
                 ({"topics": "a,,b"}, "topics is not valid"),
                 ({"topics": ""}, "topics is not valid"),
                 ({"topics": "-a"}, "topics is not valid"),
                 ({"topics": "a" * 51}, "topics is not valid"),
                 ({"mode": "later"}, "mode is not valid"),
                 # the first rule broken wins, in the order of the SKILL.md
                 ({"visibility": "x", "topics": "Bad"}, "visibility is not valid")]
        for over, sentence in cases:
            with self.subTest(over=over):
                r, ctx = run({}, **over)
                self.assertEqual(r.status, "failed")
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertEqual((ctx.calls, ctx.writes), ([], []))
                self.assertEqual(r.block["outputs"], skill.failed_outputs())
                self.assertEqual(r.block["resources"], [])
                self.assertEqual(r.block["cost"]["notes"], "no cost: nothing was created")

    def test_repeated_topics_count_once(self):
        parsed, problem = skill.validate(dict(ARGS, topics="b,a,b"))
        self.assertIsNone(problem)
        self.assertEqual(parsed, ("private", ["b", "a"]))


class TestGoldenCommands(unittest.TestCase):
    """Steps 4 and 5 of the SKILL.md, as it writes the commands:

        gh repo create <owner>/<name> --private --add-readme --description "<description>"
        (--public instead of --private when visibility=public)
        gh repo edit <owner>/<name> --add-topic <t1> --add-topic <t2>
    """

    def test_private_with_description_and_topics(self):
        r, ctx = run({READ: [NOT_FOUND, ok(repo(description="Status pages, per tenant",
                                                topics=["demo", "aleogr-example"]))]},
                     mode="apply", description="Status pages, per tenant",
                     topics="aleogr-example,demo")
        self.assertEqual(ctx.writes, [
            ["gh", "repo", "create", "example-org/example-repo", "--private", "--add-readme",
             "--description", "Status pages, per tenant"],
            ["gh", "repo", "edit", "example-org/example-repo", "--add-topic", "aleogr-example",
             "--add-topic", "demo"]])
        self.assertEqual(ctx.calls, [READ, READ])
        self.assertEqual((r.status, r.block["pending"]), ("created", []))

    def test_public_confirmed_without_description(self):
        r, ctx = run({READ: [NOT_FOUND, ok(repo(visibility="public"))]}, mode="apply",
                     visibility="public", confirmVisibility="public")
        self.assertEqual(ctx.writes, [
            ["gh", "repo", "create", "example-org/example-repo", "--public", "--add-readme"]])
        self.assertEqual((r.status, r.block["cost"]["notes"]), ("created", "no cost"))

    def test_each_golden_command_is_on_the_allowlist(self):
        for argv in (skill.create_command("o/n", "private", None),
                     skill.create_command("o/n", "public", "A text, with words"),
                     skill.topics_command("o/n", ["a", "b-2"])):
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT), argv)
            self.assertTrue(all(isinstance(a, str) for a in argv))


class TestPublicNeedsConfirmation(unittest.TestCase):
    def test_apply_public_without_confirmation_creates_nothing(self):
        # The `how` is this same invocation (its arguments in the order given), plus
        # confirmVisibility=public.
        r, ctx = run({READ: NOT_FOUND}, mode="apply", visibility="public",
                     description="A b", topics="x,y")
        self.assertEqual(ctx.writes, [])
        self.assertEqual(ctx.calls, [READ])
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.lines[0], "Create `example-org/example-repo` as PUBLIC?")
        self.assertEqual(r.block["pending"], [{
            "item": "confirm visibility public", "reason": "manual",
            "how": "/aleogr-repo-github:github_repo-create owner=example-org "
                   "name=example-repo mode=apply visibility=public description=\"A b\" "
                   "topics=\"x,y\" confirmVisibility=public"}])
        self.assertEqual(r.block["resources"], [])
        self.assertEqual(r.block["outputs"]["topics"], ["x", "y"])

    def test_plan_never_writes(self):
        r, ctx = run({READ: NOT_FOUND}, visibility="public", confirmVisibility="public")
        self.assertEqual((r.status, ctx.writes), ("would-create", []))
        self.assertIn("    gh repo create example-org/example-repo --public --add-readme",
                      r.lines)
        ctx = FakeContext({}, dict(ARGS))
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.create_command("example-org/example-repo", "private", None))

    def test_read_only_option_refuses_apply(self):
        ctx = common.Context(PLUGIN, ROOT, SKILL, skill, "apply", dict(ARGS, mode="apply"),
                             read_only=True)
        self.assertFalse(ctx.writable)
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.create_command("example-org/example-repo", "private", None))


class TestSteps(unittest.TestCase):
    def test_existing_is_never_changed_and_differences_in_order(self):
        r, ctx = run({READ: ok(repo(visibility="public", description="Old",
                                    topics=["b", "a"]))},
                     mode="apply", visibility="private", description="New", topics="a,b")
        self.assertEqual((r.status, ctx.writes, ctx.calls), ("unchanged", [], [READ]))
        self.assertEqual(r.block["outputs"]["differences"], ["visibility", "description"])
        self.assertEqual(r.block["outputs"]["topics"], ["a", "b"])
        self.assertIn("github_repo-configure corrects these differences.", r.lines)

    def test_default_private_is_not_compared(self):
        r, _ = run({READ: ok(repo(visibility="public"))})
        self.assertEqual(r.block["outputs"]["differences"], [])
        self.assertEqual(r.block["cost"]["notes"], "no cost")
        r, _ = run({READ: ok(repo(visibility="internal"))})
        self.assertEqual(r.block["cost"]["notes"], skill.PRIVATE_COST)

    def test_read_failures_never_say_absent_and_never_create(self):
        cases = [(fail("gh: command not found", 127), "gh is not installed"),
                 (fail("To get started with GitHub CLI, please run:  gh auth login"),
                  "gh is not logged in"),
                 (fail("gh: Forbidden (HTTP 403)"), "The repository example-org/example-repo "
                  "could not be read: this account is not allowed to read it"),
                 (ok("not json"), "The repository example-org/example-repo could not be "
                  "read: gh did not give a JSON object")]
        for c, sentence in cases:
            with self.subTest(sentence=sentence[:40]):
                r, ctx = run({READ: c}, mode="apply")
                self.assertEqual((r.status, ctx.writes), ("failed", []))
                self.assertTrue(r.lines[0].startswith(sentence), r.lines)
                self.assertNotIn("403", "\n".join(r.lines))
                self.assertEqual(r.block["outputs"], skill.failed_outputs())

    def test_exit_0_with_a_404_line_is_absent(self):
        r, ctx = run({READ: common.Completed(0, "", "gh: Not Found (HTTP 404)\n")})
        self.assertEqual(r.status, "would-create")
        self.assertIn(skill.G.UNTRUSTED, r.lines)

    def test_verification_failed_gives_built_outputs_and_verify_item(self):
        r, _ = run({READ: [NOT_FOUND, fail("gh: Server Error (HTTP 502)")]}, mode="apply")
        self.assertEqual(r.status, "created")
        self.assertEqual(r.block["outputs"],
                         skill.built_outputs("example-org", "example-repo", "private"))
        self.assertEqual(r.block["pending"], [{
            "item": "verify", "reason": "manual",
            "how": "/aleogr-repo-github:github_repo-describe owner=example-org "
                   "name=example-repo"}])

    def test_verification_differs_gives_one_configure_item(self):
        r, _ = run({READ: [NOT_FOUND, ok(repo(visibility="public", description="x",
                                               topics=["a"]))]},
                   mode="apply", description="Wanted text", topics="a,b")
        self.assertEqual(r.status, "created")
        self.assertEqual(r.block["outputs"]["differences"], [])
        self.assertEqual(r.block["pending"], [{
            "item": "configure", "reason": "manual",
            "how": "/aleogr-repo-github:github_repo-configure owner=example-org "
                   "name=example-repo description=\"Wanted text\" topics=\"a,b\" "
                   "visibility=private mode=apply"}])

    def test_topics_refused_then_no_topics_in_configure(self):
        r, _ = run({READ: [NOT_FOUND, ok(repo(visibility="public"))]},
                   {"gh repo edit": fail("HTTP 403: Resource not accessible")},
                   mode="apply", topics="a")
        self.assertEqual([p["item"] for p in r.block["pending"]], ["topics", "configure"])
        self.assertEqual(r.block["pending"][0]["how"],
                         "/aleogr-repo-github:github_repo-configure owner=example-org "
                         "name=example-repo topics=\"a\" mode=apply")
        self.assertEqual(r.block["pending"][1]["how"],
                         "/aleogr-repo-github:github_repo-configure owner=example-org "
                         "name=example-repo visibility=private mode=apply")

    def test_create_refused_runs_nothing_else(self):
        r, ctx = run({READ: NOT_FOUND},
                     {"gh repo create": fail("HTTP 403: You need admin access to the org")},
                     mode="apply", topics="a")
        self.assertEqual((r.status, len(ctx.writes), ctx.calls), ("failed", 1, [READ]))
        self.assertNotIn("admin access", "\n".join(r.lines))
        self.assertEqual(r.block["resources"], [])

    def test_create_exit_0_with_an_error_line_is_a_refusal(self):
        r, ctx = run({READ: NOT_FOUND}, {"gh repo create": common.Completed(
            0, "", "gh: Forbidden (HTTP 403)\n")}, mode="apply")
        self.assertEqual(r.status, "failed")
        self.assertIn(skill.G.UNTRUSTED, r.lines)


if __name__ == "__main__":
    unittest.main()
