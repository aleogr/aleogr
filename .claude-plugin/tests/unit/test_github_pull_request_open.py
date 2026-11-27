"""Unit tests of github_pull-request-open: its plan and apply, the cases no scenario
covers, and its golden commands.

The skill's run() is given a context whose read() answers from a dict and whose
execute() (where ctx.write runs a command that passed the allowlist of writes) records
the write and answers from another dict, so no provider command runs. The scenarios
gh-pr-open-* cover the rest, in the direct mode.
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


def plain(argv):
    return [a.value if isinstance(a, common.Hidden) else str(a) for a in argv]


class FakeContext(common.Context):
    def __init__(self, answers, args, writes=None):
        common.Context.__init__(self, PLUGIN, ROOT, "github_pull-request-open", skill,
                                args.get("mode") or "plan", args)
        self.answers = answers
        self.write_answers = writes or {}
        self.calls = []
        self.writes = []
        self.log = []

    def execute(self, argv, timeout=None):
        # Reached only through ctx.write, after the allowlist of writes accepted argv.
        self.writes.append(list(argv))
        line = " ".join(plain(argv))
        self.log.append(line)
        best = None
        for prefix in self.write_answers:
            if line == prefix or line.startswith(prefix + " "):
                if best is None or len(prefix) > len(best):
                    best = prefix
        return self.write_answers[best] if best else common.Completed(0, "", "")

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.calls.append(line)
        self.log.append(line)
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


def run(answers, writes=None, **extra):
    args = dict(ARGS, **extra)
    ctx = FakeContext(answers, args, writes)
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


# ---------------------------------------------------------------------------
# mode=apply

USER = "gh api user"
CRED = ["-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential"]
CRED_LINE = " ".join(["git"] + CRED)
NOREPLY = "1234567+example-user@users.noreply.github.com"
APPLY = {"mode": "apply", "title": "Change the files"}
CREATED = common.Completed(0, "\nCreating pull request into main in example-org/example-repo"
                              "\n\nhttps://github.com/example-org/example-repo/pull/7\n", "")


def changed_answers(**over):
    a = ready(**{"git status --porcelain --": ok(" M b/c.json\n M a.json\n"),
                 USER: ok({"login": "example-user", "id": 1234567,
                           "email": "owner@example.com"})})
    a.update(over)
    return a


def apply_run(answers=None, writes=None, **extra):
    w = {"gh pr create": CREATED}
    w.update(writes or {})
    return run(answers or changed_answers(), w, **dict(APPLY, **extra))


def text_of(r):
    return "\n".join(r.lines) + "\n" + common.render_block(r.block)


def head_of(ctx):
    return [plain(w) for w in ctx.writes if w[:3] == ["git", "switch", "-c"]][0][3]


class TestGoldenCommands(unittest.TestCase):
    """Steps 9 to 15 of the SKILL.md, as it writes the commands:

        git config --local user.name <login>
        git config --local user.email <id>+<login>@users.noreply.github.com
        git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull --ff-only origin <branch>
        git switch -c aleogr/change-<random>
        git add -- <changed>
        git commit -m "<title>" -- <changed>
        git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin aleogr/change-<random>
        gh pr create --repo <owner>/<name> --base <branch> --head aleogr/change-<random> --title "<title>" --body "<full body>"
        git switch <branch>
    """

    def test_apply(self):
        r, ctx = apply_run(note="Applying this creates a project.")
        head = head_of(ctx)
        self.assertRegex(head, r"^aleogr/change-[a-z0-9]{6}$")
        self.assertEqual([plain(w) for w in ctx.writes], [
            ["git", "config", "--local", "user.name", "example-user"],
            ["git", "config", "--local", "user.email", NOREPLY],
            ["git"] + CRED + ["pull", "--ff-only", "origin", "main"],
            ["git", "switch", "-c", head],
            ["git", "add", "--", "a.json", "b/c.json"],
            ["git", "commit", "-m", "Change the files", "--", "a.json", "b/c.json"],
            ["git"] + CRED + ["push", "-u", "origin", head],
            ["gh", "pr", "create", "--repo", "example-org/example-repo", "--base", "main",
             "--head", head, "--title", "Change the files", "--body",
             "Proposed by aleogr. Applying this creates a project."],
            ["git", "switch", "main"]])
        self.assertIsInstance(ctx.writes[0][-1], common.Hidden)
        self.assertIsInstance(ctx.writes[1][-1], common.Hidden)
        self.assertEqual(common.show_command(ctx.writes[0]),
                         "git config --local user.name <login>")
        self.assertEqual(common.show_command(ctx.writes[1]), "git config --local user.email "
                         "<id>+<login>@users.noreply.github.com")
        for w in ctx.writes:
            self.assertIsNone(common.write_refusal("github_pull-request-open", w, root=ROOT),
                              w)
        # Reads of steps 1 to 7, then gh api user, before any write.
        self.assertEqual(ctx.log.index(USER), len(ctx.calls) - 1)
        self.assertEqual(ctx.log[len(ctx.calls)], "git config --local user.name example-user")
        self.assertEqual(r.status, "created")
        o = r.block["outputs"]
        self.assertEqual(o["pullRequest"], {
            "number": 7, "url": "https://github.com/example-org/example-repo/pull/7",
            "branch": head})
        self.assertEqual((o["folder"], o["changed"], o["openPullRequest"], o["defaultBranch"]),
                         ("ready", ["a.json", "b/c.json"], None, "main"))
        self.assertEqual(r.block["resources"], [{
            "type": "pull-request", "id": "example-org/example-repo#7", "name": head}])
        self.assertEqual((r.block["mode"], r.block["pending"]), ("apply", []))
        for word in ("example-user", "1234567", "owner@example.com"):
            self.assertNotIn(word, text_of(r))

    def test_every_golden_command_is_on_the_allowlist(self):
        head = skill.new_branch()
        name_cmd, email_cmd = skill.identity_commands("example-user", 1234567)
        for argv in (name_cmd, email_cmd, skill.fast_forward_command("main"),
                     skill.switch_new_command(head), skill.add_command(["a", "b/c"]),
                     skill.commit_command("T", ["a", "b/c"]), skill.push_command(head),
                     skill.pr_create_command("example-org/example-repo", "main", head, "T",
                                             "B."),
                     skill.switch_back_command("main")):
            self.assertIsNone(common.write_refusal("github_pull-request-open", argv), argv)
        # Never the default branch: a push of main is refused by shape.
        self.assertIsNotNone(common.write_refusal("github_pull-request-open",
                                                  skill.push_command("main")))

    def test_random_branch(self):
        names = set(skill.new_branch() for _ in range(20))
        self.assertGreater(len(names), 1)
        for n in names:
            self.assertRegex(n, r"^aleogr/change-[a-z0-9]{6}$")


class TestApply(unittest.TestCase):
    def test_plan_never_writes(self):
        ctx = FakeContext({}, dict(ARGS))
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.switch_back_command("main"))
        r, ctx = run(changed_answers())
        self.assertEqual((r.status, ctx.writes), ("would-create", []))

    def test_read_only_option_refuses_apply(self):
        ctx = common.Context(PLUGIN, ROOT, "github_pull-request-open", skill, "apply",
                             dict(ARGS, **APPLY), read_only=True)
        self.assertFalse(ctx.writable)

    def test_title_is_required_before_any_command(self):
        r, ctx = run(changed_answers(), mode="apply")
        self.assertEqual((r.status, r.lines[0], ctx.calls), ("failed", "title is missing.", []))

    def test_nothing_to_do_writes_nothing(self):
        r, ctx = apply_run(ready())
        self.assertEqual((r.status, ctx.writes, r.block["mode"]), ("unchanged", [], "apply"))
        r, ctx = apply_run(changed_answers(**{PRS: ok([{
            "number": 4, "url": "u", "headRefName": "aleogr/change-abc123",
            "isCrossRepository": False}])}))
        self.assertEqual((r.status, ctx.writes), ("pending", []))
        self.assertNotIn(USER, ctx.calls)

    def test_account_refused(self):
        r, ctx = apply_run(changed_answers(**{USER: fail("gh: Forbidden (HTTP 403)")}))
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertNotIn("403", text_of(r))
        self.assertEqual(r.block["outputs"]["changed"], ["a.json", "b/c.json"])

    def test_identity_refused_names_the_change(self):
        r, ctx = apply_run(writes={"git config --local user.email": fail("error")})
        self.assertEqual((r.status, len(ctx.writes)), ("failed", 2))
        self.assertIn("Local changes made in this folder: this checkout's commit name.",
                      r.lines)
        self.assertNotIn("example-user", text_of(r))

    def test_fast_forward_refused(self):
        for text, conflict in (("error: Your local changes would be overwritten by merge",
                                True), ("fatal: unable to access (503)", False)):
            with self.subTest(text=text):
                r, ctx = apply_run(writes={CRED_LINE + " pull": fail(text)})
                self.assertEqual((r.status, len(ctx.writes)), ("failed", 3))
                self.assertEqual(r.lines[0].startswith("The change in this folder conflicts "
                                                       "with what the repository has now"),
                                 conflict)
                self.assertIn("nothing was committed", r.lines[0])
                self.assertNotIn("overwritten", text_of(r))
                self.assertNotIn("503", text_of(r))

    def test_branch_not_created_runs_no_switch_back(self):
        r, ctx = apply_run(writes={"git switch -c": fail("fatal: exists")})
        self.assertEqual((r.status, ctx.writes[-1][:3]), ("failed", ["git", "switch", "-c"]))

    def test_commit_refused_still_switches_back(self):
        r, ctx = apply_run(writes={"git commit": fail("error")})
        head = head_of(ctx)
        self.assertEqual(plain(ctx.writes[-1]), ["git", "switch", "main"])
        self.assertFalse(any("push" in plain(w) for w in ctx.writes))
        self.assertEqual((r.status, r.block["outputs"]["pullRequest"]), ("failed", None))
        self.assertIn("The named files stay staged in this folder, and the empty local branch "
                      "%s is kept." % head, r.lines)

    def test_push_refused_keeps_the_commit(self):
        r, ctx = apply_run(writes={CRED_LINE + " push": fail("fatal: 503")})
        head = head_of(ctx)
        self.assertEqual(plain(ctx.writes[-1]), ["git", "switch", "main"])
        self.assertFalse(any(w[:2] == ["gh", "pr"] for w in ctx.writes))
        self.assertEqual(r.status, "failed")
        self.assertIn("the commit is kept in the local branch %s" % head, r.lines[0])
        self.assertNotIn("503", text_of(r))

    def test_pr_not_opened_is_updated_with_the_command(self):
        for answer in (fail("GraphQL: error"), common.Completed(0, "done\n", ""),
                       common.Completed(0, "", "gh: Validation Failed (HTTP 422)\n")):
            with self.subTest(answer=answer):
                r, ctx = apply_run(writes={"gh pr create": answer}, body="B.")
                head = head_of(ctx)
                self.assertEqual(r.status, "updated")
                self.assertEqual(r.block["pending"], [{
                    "item": "open the pull request", "reason": "manual",
                    "how": 'gh pr create --repo example-org/example-repo --base main --head '
                           '%s --title "Change the files" --body "B."' % head}])
                self.assertEqual((r.block["outputs"]["pullRequest"], r.block["resources"]),
                                 (None, []))
                self.assertEqual(plain(ctx.writes[-1]), ["git", "switch", "main"])
                self.assertNotIn("GraphQL", text_of(r))

    def test_switch_back_refused_adds_the_item(self):
        r, ctx = apply_run(writes={"git switch main": fail("error: would be overwritten")})
        head = head_of(ctx)
        self.assertEqual(r.status, "created")
        self.assertEqual(r.block["pending"], [{
            "item": "return this folder to the default branch", "reason": "manual",
            "how": "git switch main"}])
        self.assertTrue(any(l.startswith("This folder is still on %s" % head)
                            for l in r.lines))
        r, ctx = apply_run(writes={"git switch main": fail("x"), "gh pr create": fail("x")})
        self.assertEqual([p["item"] for p in r.block["pending"]],
                         ["open the pull request", "return this folder to the default branch"])



class TestValuesNoWriteTakes(unittest.TestCase):
    """Values the SKILL.md's rules let through but that the shapes of the allowlist of
    writes refuse: the run ends failed, with one fixed sentence, before any write."""

    def apply(self, branch="main", changed=("a.json",)):
        args = dict(ARGS, mode="apply", title="Change")
        ctx = FakeContext({}, args)
        found = skill.Found(branch, None, "ready", list(changed))
        return skill.apply(args, ctx, skill.G.Reader(ctx), found), ctx

    def test_a_dot_part_inside_a_path(self):
        for path in ("a/./b.json", "a/.", "."):
            with self.subTest(path=path):
                self.assertIsNotNone(skill.split_paths(path))  # the skill's rule lets it by
                r, ctx = self.apply(changed=["x.json", path])
                self.assertEqual((r.status, ctx.calls, ctx.writes), ("failed", [], []))
                self.assertEqual(r.lines, [skill.PATH_UNUSABLE.format(path=path),
                                           "No local change was made in this folder."])

    def test_the_rule_already_refuses_the_others(self):
        for path in ("./a.json", "a//b.json", "conf/"):
            with self.subTest(path=path):
                self.assertIsNone(skill.split_paths(path))
                self.assertEqual(skill._validate(dict(ARGS, paths=path), "plan"),
                                 skill.PATHS_RULE)

    def test_default_branch_the_shapes_refuse(self):
        for branch in ("main+x", "rélease", "-main", "a..b", "a/"):
            with self.subTest(branch=branch):
                r, ctx = self.apply(branch=branch)
                self.assertEqual((r.status, ctx.calls, ctx.writes), ("failed", [], []))
                self.assertTrue(r.lines[0].startswith(
                    "The default branch %s of example-org/example-repo has a name" % branch))
                self.assertEqual(r.block["outputs"]["defaultBranch"], branch)
        for branch in ("main", "release/1.2", "aleogr/change-abc123"):
            self.assertTrue(skill.branch_usable(branch), branch)
            self.assertIsNone(common.write_refusal("github_pull-request-open",
                                                   skill.switch_back_command(branch)))


class TestPlanEndsAsTheApplyWould(unittest.TestCase):
    """mode=plan runs the same checks: a plan never announces a write the apply refuses
    (docs/DESIGN.md, section 18)."""

    def plan(self, branch="main", changed=("a.json",), mode="plan"):
        args = dict(ARGS, title="Change")
        if mode:
            args["mode"] = mode
        ctx = FakeContext({}, args)
        found = skill.Found(branch, None, "ready", list(changed))
        examine = skill.examine
        skill.examine = lambda a, c, r: found
        try:
            return skill.run(dict(args), ctx), ctx
        finally:
            skill.examine = examine

    def test_a_path_the_apply_refuses(self):
        for mode in ("plan", None, "apply"):
            with self.subTest(mode=mode):
                r, ctx = self.plan(changed=["x.json", "a/./b.json"], mode=mode)
                self.assertEqual((r.status, ctx.writes), ("failed", []))
                self.assertEqual(r.block["mode"], mode or "plan")
                self.assertEqual(r.lines, [skill.PATH_UNUSABLE.format(path="a/./b.json"),
                                           "No local change was made in this folder."])

    def test_a_branch_the_apply_refuses(self):
        r, ctx = self.plan(branch="main+x")
        self.assertEqual((r.status, r.block["mode"], ctx.writes), ("failed", "plan", []))
        self.assertTrue(r.lines[0].startswith(
            "The default branch main+x of example-org/example-repo has a name"))
        self.assertNotIn("apply would run, without anything run now:", r.lines)

    def test_a_usable_proposal_is_still_announced(self):
        r, ctx = self.plan()
        self.assertEqual(r.status, "would-create")
        self.assertIn("apply would run, without anything run now:", r.lines)


if __name__ == "__main__":
    unittest.main()
