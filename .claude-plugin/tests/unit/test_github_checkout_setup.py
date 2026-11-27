"""Unit tests of github_checkout-setup: its plan and apply, the cases no scenario
covers, and its golden commands.

The skill's run() is given a context whose read() answers from a dict and whose
execute() (where ctx.write runs a command that passed the allowlist of writes) records
the write and answers from another dict, so no provider command runs; the local file is
written in a temporary folder. The scenarios gh-checkout-* cover the rest, in the direct
mode.
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


def plain(argv):
    return [a.value if isinstance(a, common.Hidden) else str(a) for a in argv]


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def fail(text, code=1):
    return common.Completed(code, "", text)


class FakeContext(common.Context):
    def __init__(self, answers, args, writes=None):
        common.Context.__init__(self, PLUGIN, ROOT, "github_checkout-setup", skill,
                                args.get("mode") or "plan", args)
        self.answers = answers
        self.write_answers = writes or {}
        self.calls = []
        self.writes = []
        self.log = []  # reads and writes, in order, as run (plain values)

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
        if line in self.answers and isinstance(self.answers[line], list):
            queue = self.answers[line]
            return queue.pop(0) if len(queue) > 1 else queue[0]
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

    def run_skill(self, answers, writes=None, **extra):
        args = dict(ARGS, **extra)
        ctx = FakeContext(answers, args, writes)
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

    def test_apply_is_converted(self):
        self.assertFalse(hasattr(skill, "UNCONVERTED_MODES"))
        self.assertTrue(skill.WRITES)


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


# ---------------------------------------------------------------------------
# mode=apply

USER = "gh api user"
COMMITS2 = REPO + "/commits?per_page=2"
CRED = ["-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential"]
CRED_LINE = " ".join(["git"] + CRED)
NOREPLY = "1234567+example-user@users.noreply.github.com"
NOT_FOUND = fail("gh: Not Found (HTTP 404)")


def birth_answers(**over):
    """A repository at its birth, in a folder that is not a git checkout yet; the
    verification of step 16 reads the file back equal."""
    a = {REPO: ok({"default_branch": "main"}),
         CONTENTS + " -H Accept: application/vnd.github.raw": [NOT_FOUND, ok(DECL)],
         COMMITS2: ok([{"sha": SHA1}]),
         USER: ok({"login": "example-user", "id": 1234567, "email": "owner@example.com"}),
         "git rev-parse --is-inside-work-tree":
         fail("fatal: not a git repository (or any of the parent directories): .git", 128),
         "git remote get-url origin": fail("error: No such remote 'origin'", 2),
         "git branch --show-current": ok("main\n"),
         "git rev-list --count origin/main..HEAD": ok("0\n")}
    a.update(over)
    return a


def behind_answers(after=None):
    return {REPO: ok({"default_branch": "main"}),
            CONTENTS + " -H Accept: application/vnd.github.raw":
            [ok({"other": 1}), after or ok({"other": 1})],
            "git rev-parse --is-inside-work-tree": ok("true\n"),
            "git remote get-url origin": ok("https://github.com/example-org/example-repo\n"),
            "git branch --show-current": ok("main\n"),
            "git status --porcelain -- .aleogr/project.json": ok(""),
            "git rev-parse HEAD": ok(SHA1 + "\n"),
            REPO + "/commits/main": ok({"sha": SHA2}),
            REPO + "/commits/" + SHA1: ok({"sha": SHA1})}


def text_of(r):
    return "\n".join(r.lines) + "\n" + common.render_block(r.block)


class TestGoldenCommands(Base):
    """Steps 8 to 15 and 17 of the SKILL.md, as it writes the commands:

        git init -b <branch>
        git remote add origin https://github.com/<owner>/<name>.git
        git config --local user.name <login>
        git config --local user.email <id>+<login>@users.noreply.github.com
        git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull origin <branch>
        git add -- <path>
        git commit -m "<message>" -- <path>
        git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push -u origin <branch>
        git -c credential.helper= -c 'credential.helper=!gh auth git-credential' pull --ff-only origin <branch>
    """

    def test_birth(self):
        r, ctx = self.run_skill(birth_answers(), mode="apply")
        self.assertEqual([plain(w) for w in ctx.writes], [
            ["git", "init", "-b", "main"],
            ["git", "remote", "add", "origin", "https://github.com/example-org/example-repo.git"],
            ["git", "config", "--local", "user.name", "example-user"],
            ["git", "config", "--local", "user.email", NOREPLY],
            ["git"] + CRED + ["pull", "origin", "main"],
            ["git", "add", "--", ".aleogr/project.json"],
            ["git", "commit", "-m", "Add the project declaration", "--", ".aleogr/project.json"],
            ["git"] + CRED + ["push", "-u", "origin", "main"]])
        name_cmd, email_cmd = ctx.writes[2], ctx.writes[3]
        self.assertIsInstance(name_cmd[-1], common.Hidden)
        self.assertIsInstance(email_cmd[-1], common.Hidden)
        self.assertEqual(common.show_command(name_cmd), "git config --local user.name <login>")
        self.assertEqual(common.show_command(email_cmd), "git config --local user.email "
                         "<id>+<login>@users.noreply.github.com")
        for w in ctx.writes:
            self.assertIsNone(common.write_refusal("github_checkout-setup", w, root=ROOT), w)
        # The order of every command, reads included (steps 1, 3, 5, 7 to 16).
        self.assertEqual(ctx.log, [
            REPO, CONTENTS + " -H Accept: application/vnd.github.raw", COMMITS2, USER,
            "git rev-parse --is-inside-work-tree", "git init -b main",
            "git remote get-url origin",
            "git remote add origin https://github.com/example-org/example-repo.git",
            "git branch --show-current",
            "git config --local user.name example-user",
            "git config --local user.email " + NOREPLY,
            CRED_LINE + " pull origin main", "git rev-list --count origin/main..HEAD",
            "git add -- .aleogr/project.json",
            "git commit -m Add the project declaration -- .aleogr/project.json",
            CRED_LINE + " push -u origin main",
            CONTENTS + " -H Accept: application/vnd.github.raw"])
        self.assertEqual((r.status, r.block["mode"], r.block["pending"]),
                         ("created", "apply", []))
        o = r.block["outputs"]
        self.assertEqual((o["state"], o["pushed"], o["updated"], o["defaultBranch"]),
                         ("equal", True, False, "main"))
        self.assertNotIn("example-user", text_of(r))
        self.assertNotIn("1234567", text_of(r))
        self.assertNotIn("owner@example.com", text_of(r))

    def test_message_and_path(self):
        os.makedirs("conf")
        with open("conf/x.json", "w") as f:
            f.write(json.dumps(DECL))
        c = REPO + "/contents/conf/x.json -H Accept: application/vnd.github.raw"
        answers = birth_answers(**{c: [NOT_FOUND, ok(DECL)],
                                   "git rev-parse --is-inside-work-tree": ok("true\n"),
                                   "git remote get-url origin":
                                   ok("https://github.com/example-org/example-repo.git\n")})
        r, ctx = self.run_skill(answers, mode="apply", path="conf/x.json",
                                message="Send the file")
        self.assertEqual([plain(w) for w in ctx.writes][3:5], [
            ["git", "add", "--", "conf/x.json"],
            ["git", "commit", "-m", "Send the file", "--", "conf/x.json"]])
        self.assertEqual(r.status, "created")

    def test_fast_forward(self):
        r, ctx = self.run_skill(behind_answers(after=ok(DECL)), mode="apply")
        self.assertEqual([plain(w) for w in ctx.writes],
                         [["git"] + CRED + ["pull", "--ff-only", "origin", "main"]])
        self.assertIsNone(common.write_refusal("github_checkout-setup", ctx.writes[0]))
        o = r.block["outputs"]
        self.assertEqual((r.status, o["state"], o["updated"], o["pushed"], r.block["pending"]),
                         ("updated", "equal", True, False, []))
        self.assertEqual(ctx.calls[-1], CONTENTS + " -H Accept: application/vnd.github.raw")

    def test_every_golden_command_is_on_the_allowlist(self):
        name_cmd, email_cmd = skill.identity_commands("example-user", 1234567)
        for argv in (skill.init_command("main"),
                     skill.remote_add_command("example-org", "example-repo"),
                     name_cmd, email_cmd, skill.pull_command("main"),
                     skill.add_command(".aleogr/project.json"),
                     skill.commit_command("Add the project declaration",
                                          ".aleogr/project.json"),
                     skill.push_command("main"), skill.fast_forward_command("main")):
            self.assertIsNone(common.write_refusal("github_checkout-setup", argv), argv)


class TestApply(Base):
    def test_plan_never_writes(self):
        ctx = FakeContext({}, dict(ARGS))
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.init_command("main"))
        r, ctx = self.run_skill(birth_answers())
        self.assertEqual((r.status, ctx.writes), ("would-create", []))
        r, ctx = self.run_skill(behind_answers())
        self.assertEqual((r.status, ctx.writes), ("would-update", []))

    def test_read_only_option_refuses_apply(self):
        ctx = common.Context(PLUGIN, ROOT, "github_checkout-setup", skill, "apply",
                             dict(ARGS, mode="apply"), read_only=True)
        self.assertFalse(ctx.writable)
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.push_command("main"))

    def test_repository_absent_fails_without_writing(self):
        r, ctx = self.run_skill({REPO: NOT_FOUND}, mode="apply")
        self.assertEqual((r.status, ctx.writes, ctx.calls), ("failed", [], [REPO]))
        self.assertEqual(r.lines[0], skill.NOT_CREATED % "example-org/example-repo")
        o = r.block["outputs"]
        self.assertEqual((o["state"], o["defaultBranch"], r.block["resources"]),
                         ("not-sent", None, []))

    def test_states_that_do_not_act_end_as_in_plan(self):
        r, ctx = self.run_skill(birth_answers(**{
            CONTENTS + " -H Accept: application/vnd.github.raw": ok(DECL)}), mode="apply")
        self.assertEqual((r.status, r.block["mode"], ctx.writes), ("unchanged", "apply", []))
        r, ctx = self.run_skill(birth_answers(**{COMMITS2: ok([{"sha": SHA2}, {"sha": SHA1}])}),
                                mode="apply")
        self.assertEqual((r.status, r.block["outputs"]["state"], ctx.writes),
                         ("pending", "missing", []))

    def test_account_not_a_login_writes_nothing(self):
        for answer in (ok({"login": "a b", "id": 1}), ok({"login": "x", "id": True}),
                       ok({"login": "x"}), fail("gh: Forbidden (HTTP 403)")):
            with self.subTest(answer=answer):
                r, ctx = self.run_skill(birth_answers(**{USER: answer}), mode="apply")
                self.assertEqual((r.status, ctx.writes), ("failed", []))
                self.assertEqual(r.block["outputs"]["state"], "not-sent")
                self.assertIn("No local change was made in this folder.", r.lines)
                self.assertNotIn("403", text_of(r))

    def test_init_refused_names_git_2_28(self):
        r, ctx = self.run_skill(birth_answers(), {"git init": fail("error: unknown switch")},
                                mode="apply")
        self.assertEqual((r.status, len(ctx.writes)), ("failed", 1))
        self.assertIn("git init -b needs git 2.28 or later", r.lines[0])
        self.assertNotIn("unknown switch", text_of(r))

    def test_other_answer_of_step_8_fails(self):
        r, ctx = self.run_skill(birth_answers(**{
            "git rev-parse --is-inside-work-tree": fail("fatal: dubious ownership", 128)}),
            mode="apply")
        self.assertEqual((r.status, ctx.writes), ("failed", []))

    def test_other_origin_is_never_changed(self):
        r, ctx = self.run_skill(birth_answers(**{
            "git rev-parse --is-inside-work-tree": ok("true\n"),
            "git remote get-url origin": ok("https://token@github.com/other/x.git\n")}),
            mode="apply")
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertNotIn("token", text_of(r))

    def test_other_branch_is_named(self):
        r, ctx = self.run_skill(birth_answers(**{"git branch --show-current": ok("dev\n")}),
                                mode="apply")
        self.assertEqual(r.status, "failed")
        self.assertIn("This folder is on the branch dev, and it must be on main.", r.lines)
        self.assertEqual(len(ctx.writes), 2)  # the init and the remote, listed as changes
        self.assertIn("Local changes already made in this folder: a new git checkout, the "
                      "remote origin.", r.lines)

    def test_identity_refused(self):
        r, ctx = self.run_skill(birth_answers(), {"git config --local user.email":
                                                  fail("error")}, mode="apply")
        self.assertEqual((r.status, len(ctx.writes)), ("failed", 4))
        self.assertNotIn("example-user", text_of(r))

    def test_pull_refused_in_a_checkout_names_a_merge(self):
        answers = birth_answers(**{"git rev-parse --is-inside-work-tree": ok("true\n"),
                                   "git remote get-url origin":
                                   ok("https://github.com/example-org/example-repo.git\n")})
        r, ctx = self.run_skill(answers, {CRED_LINE + " pull": fail("CONFLICT (add/add)")},
                                mode="apply")
        self.assertEqual(r.status, "failed")
        self.assertIn("An interrupted merge may be left in this folder.", r.lines)
        self.assertNotIn("CONFLICT", text_of(r))
        r, ctx = self.run_skill(birth_answers(), {CRED_LINE + " pull": fail("x")},
                                mode="apply")
        self.assertNotIn("An interrupted merge may be left in this folder.", r.lines)

    def test_one_local_commit_of_another_file_is_not_resumed(self):
        r, ctx = self.run_skill(birth_answers(**{
            "git rev-list --count origin/main..HEAD": ok("1\n"),
            "git diff --name-only origin/main HEAD": ok(".aleogr/project.json\nother\n")}),
            mode="apply")
        self.assertEqual(r.status, "failed")
        self.assertNotIn("git log -1 --format=%ae HEAD", ctx.calls)
        self.assertFalse(any("push" in " ".join(plain(w)) for w in ctx.writes))

    def test_resume_skips_the_commit(self):
        r, ctx = self.run_skill(birth_answers(**{
            "git rev-list --count origin/main..HEAD": ok("1\n"),
            "git diff --name-only origin/main HEAD": ok(".aleogr/project.json\n"),
            "git log -1 --format=%ae HEAD": ok(NOREPLY + "\n")}), mode="apply")
        self.assertEqual(r.status, "created")
        lines = [" ".join(plain(w)) for w in ctx.writes]
        self.assertFalse(any(l.startswith("git add") or l.startswith("git commit")
                             for l in lines))
        self.assertNotIn(NOREPLY, text_of(r))

    def test_push_refused_by_rules_is_pending(self):
        for text in ("remote: error: GH006: Protected branch update failed",
                     "remote: PROTECTED BRANCH hook declined"):
            with self.subTest(text=text):
                r, _ = self.run_skill(birth_answers(), {CRED_LINE + " push": fail(text)},
                                      mode="apply")
                self.assertEqual((r.status, r.block["outputs"]["pushed"]), ("pending", False))
                self.assertEqual(r.block["pending"], [{
                    "item": "declaration is not in the repository", "reason": "manual",
                    "how": "open a pull request that adds .aleogr/project.json"}])
        r, _ = self.run_skill(birth_answers(), {CRED_LINE + " push": fail("fatal: 503")},
                              mode="apply")
        self.assertEqual((r.status, r.block["outputs"]["state"]), ("failed", "not-sent"))
        self.assertNotIn("503", text_of(r))

    def test_verification_failed_or_differs(self):
        os.makedirs("conf")
        with open("conf/x.json", "w") as f:
            f.write(json.dumps(DECL))
        c = REPO + "/contents/conf/x.json -H Accept: application/vnd.github.raw"
        for after, state in ((fail("gh: Bad Gateway (HTTP 502)"), None),
                             (ok({"other": 1}), "differs")):
            with self.subTest(state=state):
                r, _ = self.run_skill(birth_answers(**{c: [NOT_FOUND, after]}),
                                      mode="apply", path="conf/x.json")
                self.assertEqual((r.status, r.block["outputs"]["state"]), ("created", state))
                self.assertEqual(r.block["pending"], [{
                    "item": "verify", "reason": "manual",
                    "how": "/aleogr-repo-github:github_checkout-setup owner=example-org "
                           "name=example-repo path=conf/x.json mode=plan"}])

    def test_fast_forward_refused(self):
        for text, words in (("fatal: Not possible to fast-forward, aborting.", True),
                            ("fatal: unable to access: 503", False)):
            with self.subTest(text=text):
                r, ctx = self.run_skill(behind_answers(), {CRED_LINE + " pull": fail(text)},
                                        mode="apply")
                o = r.block["outputs"]
                self.assertEqual((r.status, o["state"], o["updated"], o["defaultBranch"]),
                                 ("failed", "behind", False, "main"))
                self.assertNotIn("fast-forward, aborting", text_of(r))
                self.assertNotIn("503", text_of(r))
                self.assertEqual(r.lines[0].startswith("This folder cannot be brought up to "
                                                       "date by a fast-forward"), words)
                self.assertIn("nothing was changed on GitHub", r.lines[0])

    def test_fast_forward_verification_item_keeps_head_check(self):
        answers = behind_answers()
        r, ctx = self.run_skill(answers, mode="apply", head="check")
        self.assertEqual((r.status, r.block["outputs"]["state"]), ("updated", "differs"))
        self.assertEqual(r.block["pending"][0]["how"],
                         "/aleogr-repo-github:github_checkout-setup owner=example-org "
                         "name=example-repo head=check mode=plan")


if __name__ == "__main__":
    unittest.main()
