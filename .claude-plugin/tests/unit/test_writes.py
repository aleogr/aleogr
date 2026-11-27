"""Unit tests of what aleogr_common gives a writing skill: the writing runner and its
allowlist of writes, `--read-only`, the file helper, the copies (Backup), the waits
and their budget, and hidden values.

Run: python3 -m unittest discover -s .claude-plugin/tests/unit
No provider is reached: commands run as stand-ins in a temporary folder.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from helpers import PLUGINS, aleogr_common as common  # noqa: E402
from test_common import StandIns  # noqa: E402

REPO_GITHUB = os.path.join(PLUGINS, "aleogr-repo-github")
RULESET = os.path.join(REPO_GITHUB, "files", "ruleset-main.json")
RULESET_CI = os.path.join(REPO_GITHUB, "files", "ruleset-main-ci.json")
CRED = list(common.GIT_CREDENTIAL)
TITLE = "Change the project declaration"

# Every write shape of every skill of step 2a, as its SKILL.md writes it, with sample
# values: each must be accepted for its skill, and refused for every other skill unless
# that skill prescribes the same command.
ALLOWED = {
    "github_repo-create": [
        ["gh", "repo", "create", "example-org/example-repo", "--private", "--add-readme"],
        ["gh", "repo", "create", "example-org/example-repo", "--public", "--add-readme"],
        ["gh", "repo", "create", "example-org/example-repo", "--private", "--add-readme",
         "--description", "Status pages, per tenant"],
        ["gh", "repo", "create", "example-org/example-repo", "--public", "--add-readme",
         "--description", "Status pages"],
        ["gh", "repo", "edit", "example-org/example-repo", "--add-topic", "status-page"],
        ["gh", "repo", "edit", "example-org/example-repo", "--add-topic", "a", "--add-topic",
         "b-2"],
    ],
    "github_repo-configure": [
        ["gh", "repo", "edit", "example-org/example-repo", "--description", "New text",
         "--enable-merge-commit=true", "--enable-squash-merge=true",
         "--enable-rebase-merge=false", "--delete-branch-on-merge=true",
         "--enable-issues=true", "--enable-wiki=false", "--enable-projects=false",
         "--add-topic", "a", "--add-topic", "b", "--remove-topic", "c"],
        ["gh", "repo", "edit", "example-org/example-repo", "--enable-rebase-merge=false"],
        ["gh", "repo", "edit", "example-org/example-repo", "--remove-topic", "old"],
        # The same commands as github_repo-create's topics, when only topics are added.
        ["gh", "repo", "edit", "example-org/example-repo", "--add-topic", "status-page"],
        ["gh", "repo", "edit", "example-org/example-repo", "--add-topic", "a", "--add-topic",
         "b-2"],
        ["gh", "repo", "edit", "example-org/example-repo", "--visibility", "public",
         "--accept-visibility-change-consequences"],
        ["gh", "repo", "edit", "example-org/example-repo", "--visibility", "private",
         "--accept-visibility-change-consequences"],
    ],
    "github_branch-protect": [
        ["gh", "api", "--method", "POST", "repos/example-org/example-repo/rulesets",
         "--input", RULESET],
        ["gh", "api", "--method", "POST", "repos/example-org/example-repo/rulesets",
         "--input", RULESET_CI],
        ["gh", "api", "--method", "PUT", "repos/example-org/example-repo/rulesets/123",
         "--input", RULESET],
    ],
    "github_checkout-setup": [
        ["git", "init", "-b", "main"],
        ["git", "remote", "add", "origin", "https://github.com/example-org/example-repo.git"],
        ["git", "config", "--local", "user.name", "octo-cat"],
        ["git", "config", "--local", "user.email", "1234+octo-cat@users.noreply.github.com"],
        ["git"] + CRED + ["pull", "origin", "main"],
        ["git", "add", "--", ".aleogr/project.json"],
        ["git", "commit", "-m", "Add the project declaration", "--", ".aleogr/project.json"],
        ["git"] + CRED + ["push", "-u", "origin", "main"],
        ["git"] + CRED + ["pull", "--ff-only", "origin", "main"],
    ],
    "github_pull-request-open": [
        ["git", "config", "--local", "user.name", "octo-cat"],
        ["git", "config", "--local", "user.email", "1234+octo-cat@users.noreply.github.com"],
        ["git"] + CRED + ["pull", "--ff-only", "origin", "main"],
        ["git", "switch", "-c", "aleogr/change-ab12cd"],
        ["git", "add", "--", ".aleogr/project.json"],
        ["git", "commit", "-m", "Add the project declaration", "--", ".aleogr/project.json"],
        ["git", "add", "--", ".aleogr/project.json", "web/go.mod"],
        ["git", "commit", "-m", TITLE, "--", ".aleogr/project.json", "web/go.mod"],
        ["git"] + CRED + ["push", "-u", "origin", "aleogr/change-ab12cd"],
        ["gh", "pr", "create", "--repo", "example-org/example-repo", "--base", "main",
         "--head", "aleogr/change-ab12cd", "--title", TITLE, "--body",
         "Proposed by aleogr. It adds one topic."],
        ["git", "switch", "main"],
    ],
    "github_variables-set": [
        ["gh", "variable", "set", "GCP_REGION", "--repo", "example-org/example-repo",
         "--body", "us-central1"],
        ["gh", "secret", "set", "GCP_PROJECT_ID", "--repo", "example-org/example-repo",
         "--body", "aleogr-dev-demo-ab12"],
    ],
    "go_setup": [
        ["go", "-C", "web", "get", "cloud.google.com/go/cloudsqlconn@v1.27.1",
         "github.com/jackc/pgx/v5@v5.13.0"],
        ["go", "-C", "services/api", "get", "github.com/jackc/pgx/v5@v5.13.0",
         "cloud.google.com/go/cloudsqlconn@v1.27.1"],
        ["go", "-C", "web", "mod", "tidy"],
    ],
}

# Refused for every skill, whatever an entry of WRITE_SHAPES says.
ALWAYS_REFUSED = [
    "gh repo delete example-org/example-repo --yes",
    "gh variable delete GCP_REGION --repo example-org/example-repo",
    "gh secret delete GCP_PROJECT_ID --repo example-org/example-repo",
    "gh api -X DELETE repos/example-org/example-repo/rulesets/1",
    "gh api -XDELETE repos/example-org/example-repo/rulesets/1",
    "gh api --method DELETE repos/example-org/example-repo/rulesets/1",
    "gh api --method=delete repos/example-org/example-repo/rulesets/1",
    "gh api -iXDELETE repos/example-org/example-repo/rulesets/1",
    "gh pr merge 1 --repo example-org/example-repo",
    "gh pr merge --squash",
    "gh auth login",
    "gh auth logout",
    "gh auth token",
    "gh auth status -t",
    "gh auth setup-git",
    "gh release delete v1",
    "git push --force origin main",
    "git push -f origin main",
    "git push -uf origin main",
    "git push --force-with-lease origin main",
    "git push --force-with-lease=main origin main",
    "git push --force-if-includes origin main",
    "git push origin +main",
    "git push origin :main",
    "git push --delete origin aleogr/change-ab12cd",
    "git push -d origin aleogr/change-ab12cd",
    "git push --mirror origin",
    "git push --all origin",
    "git push --tags origin",
    "git -c credential.helper= push --force -u origin main",
    "git reset --hard",
    "git reset --hard origin/main",
    "git -C web reset --hard HEAD",
    "git clean -fdx",
    "git clean -n",
    "git branch -D aleogr/change-ab12cd",
    "git branch -d aleogr/change-ab12cd",
    "gcloud projects delete demo",
    "gcloud sql instances delete aleogr-shared",
    "gcloud projects set-iam-policy demo policy.json",
]

# Refused by the allowlist itself: writes no skill names, or a shape of a skill
# changed in one way (a flag, an order, a value).
NOT_ON_THE_LIST = {
    "github_variables-set": [
        "gh variable set GCP_REGION --repo example-org/example-repo --env dev --body x",
        "gh variable set gcp_region --repo example-org/example-repo --body x",
        "gh variable set GCP_REGION --body x --repo example-org/example-repo",
        "gh variable set GCP_REGION --repo example-org/example-repo",
        "gh variable set GCP_REGION --repo example-org/example-repo --body x --org o",
        "gh secret set GCP_REGION --repo example-org --body x",
        "gh secret set GCP_REGION --org example-org --body x",
        "gh api -X POST repos/example-org/example-repo/actions/variables",
        "git push -u origin main",
    ],
    "github_repo-create": [
        "gh repo create example-org/example-repo --internal --add-readme",
        "gh repo create example-org/example-repo --private",
        "gh repo create example-org/example-repo --private --add-readme --clone",
        "gh repo edit example-org/example-repo --remove-topic a",
        "gh repo edit example-org/example-repo --visibility public "
        "--accept-visibility-change-consequences",
        "gh repo edit example-org/example-repo",
        "gh repo edit example-org/example-repo --add-topic Bad_Topic",
    ],
    "github_repo-configure": [
        "gh repo edit example-org/example-repo --enable-rebase-merge=false --description x",
        "gh repo edit example-org/example-repo --enable-rebase-merge",
        "gh repo edit example-org/example-repo --enable-wiki=yes",
        "gh repo edit example-org/example-repo --visibility public",
        "gh repo edit example-org/example-repo --description x --visibility public "
        "--accept-visibility-change-consequences",
        "gh repo edit example-org/example-repo --remove-topic a --add-topic b",
        "gh repo edit example-org/example-repo --default-branch dev",
        "gh repo edit example-org/example-repo --enable-issues=true --enable-issues=false",
        "gh repo edit example-org/example-repo",
        "gh repo archive example-org/example-repo",
        "gh repo rename x",
    ],
    "github_branch-protect": [
        "gh api --method PATCH repos/example-org/example-repo/rulesets/123 --input " + RULESET,
        "gh api --method POST repos/example-org/example-repo/rulesets --input /tmp/body.json",
        "gh api --method POST repos/example-org/example-repo/rulesets -f name=main",
        "gh api --method POST repos/example-org/example-repo/rulesets",
        "gh api -X POST repos/example-org/example-repo/rulesets --input " + RULESET,
        "gh api --method PUT repos/example-org/example-repo/rulesets/abc --input " + RULESET,
        "gh api --method PUT repos/example-org/example-repo/collaborators/x",
        "gh api --method POST repos/example-org/example-repo/branches/main/protection",
    ],
    "github_checkout-setup": [
        "git push -u origin main",
        "git -c credential.helper= push -u origin main",
        "git remote set-url origin https://github.com/example-org/example-repo.git",
        "git remote add origin git@github.com:example-org/example-repo.git",
        "git remote add upstream https://github.com/example-org/example-repo.git",
        "git config --global user.name octo-cat",
        "git config user.name octo-cat",
        "git config --local user.email someone@example.com",
        "git config --local core.hooksPath x",
        "git add .",
        "git add -A",
        "git add -- ../outside",
        "git add -- /etc/passwd",
        "git commit -m x",
        "git commit --amend -m x -- a",
        "git fetch",
        "git clone https://github.com/example-org/example-repo.git",
        "git init",
        "git init -b -x",
        "git add -- .aleogr/project.json web/go.mod",
        "git commit -m x -- .aleogr/project.json web/go.mod",
        "git -c credential.helper= -c credential.helper=!gh_auth_git-credential push -u "
        "origin main",
        "git pull --rebase origin main",
        "git merge origin/main",
        "git checkout main",
        "git stash",
        "gh repo clone example-org/example-repo",
    ],
    "github_pull-request-open": [
        "git -c credential.helper= -c credential.helper=!gh_auth_git-credential push -u "
        "origin aleogr/change-ab12cd",
        "git switch -c aleogr/change-AB12CD",
        "git switch -c feature",
        "git switch -c aleogr/change-ab12cd7",
        "git checkout -b aleogr/change-ab12cd",
        "gh pr create --repo example-org/example-repo --base main --head main --title t "
        "--body b",
        "gh pr create --repo example-org/example-repo --base main --head aleogr/change-ab12cd "
        "--title t",
        "gh pr create --repo example-org/example-repo --base main --head aleogr/change-ab12cd "
        "--title t --body b --draft",
        "gh pr close 1",
        "gh pr comment 1 --body x",
        "git switch -",
        "git switch --discard-changes main",
        "git init -b main",
        "git remote add origin https://github.com/example-org/example-repo.git",
    ],
    "go_setup": [
        "go -C web get example.com/other@v1.0.0 github.com/jackc/pgx/v5@v5.13.0",
        "go -C web get github.com/jackc/pgx/v5@v5.13.0",
        "go -C web get github.com/jackc/pgx/v5@v5.13.0 github.com/jackc/pgx/v5@v5.13.0",
        "go -C web get github.com/jackc/pgx/v5@latest cloud.google.com/go/cloudsqlconn@v1.27.1",
        "go get cloud.google.com/go/cloudsqlconn@v1.27.1 github.com/jackc/pgx/v5@v5.13.0",
        "go -C ../web mod tidy",
        "go -C /tmp mod tidy",
        "go -C .github mod tidy",
        "go mod tidy",
        "go mod download",
        "go install example.com/x@latest",
        "go env -w GOFLAGS=-mod=mod",
        "go build ./...",
        "go run .",
    ],
    "github_ci-setup": [
        "git add -- .github/workflows/ci.yml",
        "gh api --method PUT repos/example-org/example-repo/contents/.github/workflows/ci.yml",
    ],
    "project-declare": [
        "git add -- .aleogr/project.json",
    ],
    "no-such-skill": [
        "gh variable set GCP_REGION --repo example-org/example-repo --body us-central1",
    ],
    "github_repo-describe": [
        "gh repo create example-org/example-repo --private --add-readme",
    ],
}

# Commands named by a skill only as a thing never to run, or not named at all: refused
# for every skill of step 2a.
NEVER = [
    "rm -rf web",
    "cp -p -- web/go.mod /tmp/x/go.mod",
    "mktemp -d",
    "sh -c true",
    "bash -c true",
    "cmp -s -- a b",
    "ls -1Ap -- web/",
    "sleep 30",
    "gh repo create example-org/example-repo --private --add-readme && true",
]


def words(cmd):
    return cmd.split(" ") if isinstance(cmd, str) else list(cmd)


def refusal(skill, cmd):
    return common.write_refusal(skill, words(cmd), root=REPO_GITHUB)


class TestAllowlistOfWrites(unittest.TestCase):
    def test_every_prescribed_write_is_allowed_for_its_skill(self):
        for skill, cmds in ALLOWED.items():
            for cmd in cmds:
                with self.subTest(skill=skill, cmd=" ".join(cmd)):
                    self.assertIsNone(refusal(skill, cmd))

    def test_a_write_of_one_skill_is_refused_for_the_others(self):
        for skill, cmds in ALLOWED.items():
            for cmd in cmds:
                for other in list(ALLOWED) + ["github_ci-setup", "project-declare"]:
                    if other == skill or any(cmd == c for c in ALLOWED.get(other, ())):
                        continue
                    with self.subTest(skill=other, cmd=" ".join(cmd)):
                        self.assertIsNotNone(refusal(other, cmd))

    def test_refused_always(self):
        skills = list(common.WRITE_SHAPES) + ["github_ci-setup", "project-declare"]
        for cmd in ALWAYS_REFUSED:
            with self.subTest(cmd=cmd):
                self.assertIsNotNone(common.always_refused(words(cmd)))
                for skill in skills:
                    self.assertIsNotNone(refusal(skill, cmd), skill)

    def test_refused_when_not_on_the_list(self):
        for skill, cmds in NOT_ON_THE_LIST.items():
            for cmd in cmds:
                with self.subTest(skill=skill, cmd=cmd):
                    self.assertIsNotNone(refusal(skill, cmd))

    def test_never(self):
        for skill in list(common.WRITE_SHAPES) + ["github_ci-setup", "project-declare"]:
            for cmd in NEVER:
                with self.subTest(skill=skill, cmd=cmd):
                    self.assertIsNotNone(refusal(skill, cmd))

    def test_push_to_the_default_branch(self):
        # Only github_checkout-setup pushes a branch that is not aleogr/change-<random>
        # (the birth of the repository); github_pull-request-open never does.
        push_main = ["git"] + CRED + ["push", "-u", "origin", "main"]
        push_change = ["git"] + CRED + ["push", "-u", "origin", "aleogr/change-ab12cd"]
        self.assertIsNone(refusal("github_checkout-setup", push_main))
        self.assertIsNotNone(refusal("github_pull-request-open", push_main))
        self.assertIsNone(refusal("github_pull-request-open", push_change))
        pushers = [s for s, cmds in ALLOWED.items()
                   if any("push" in c for c in cmds)]
        self.assertEqual(sorted(pushers), ["github_checkout-setup", "github_pull-request-open"])

    def test_ruleset_input_must_be_the_plugin_file(self):
        cmd = ALLOWED["github_branch-protect"][0]
        self.assertIsNotNone(common.write_refusal("github_branch-protect", cmd))  # no root
        other = os.path.join(PLUGINS, "aleogr", "files", "ruleset-main.json")
        self.assertIsNotNone(refusal("github_branch-protect", cmd[:-1] + [other]))

    def test_no_read_is_a_write_and_no_write_is_a_read(self):
        for skill, cmds in ALLOWED.items():
            for cmd in cmds:
                with self.subTest(cmd=" ".join(cmd)):
                    self.assertIsNotNone(common.read_refusal(cmd))

    def test_a_refused_write_is_not_shown_and_not_run(self):
        with StandIns() as s:
            for cmd in ALWAYS_REFUSED + NOT_ON_THE_LIST["github_variables-set"]:
                with self.subTest(cmd=cmd):
                    err = io.StringIO()
                    with self.assertRaises(common.WriteRefused):
                        common.run_write("github_variables-set", words(cmd), stream=err)
                    self.assertEqual(err.getvalue(), "")
            self.assertEqual(s.ran(), [])

    def test_an_allowed_write_is_shown_then_run(self):
        with StandIns() as s:
            err = io.StringIO()
            c = common.run_write("github_variables-set", ALLOWED["github_variables-set"][0],
                                 stream=err)
            self.assertEqual(c.code, 3)
            self.assertEqual(err.getvalue(), "+ gh variable set GCP_REGION --repo "
                                             "example-org/example-repo --body us-central1\n")
            self.assertEqual(len(s.ran()), 1)


class Writer(object):
    FAMILY = "repo"
    PROVIDER = "github"
    ACTION = "variables-set"
    WRITES = True


class Reader(object):
    FAMILY = "repo"
    PROVIDER = "github"
    ACTION = "variables-set"


SET = ["gh", "variable", "set", "GCP_REGION", "--repo", "example-org/example-repo", "--body",
       "us-central1"]


class TestWritingRunnerOfTheContext(unittest.TestCase):
    def ctx(self, module=Writer, mode="apply", read_only=False, skill="github_variables-set"):
        return common.Context("aleogr-repo-github", REPO_GITHUB, skill, module, mode, {},
                              read_only=read_only)

    def test_writable_only_in_apply_without_read_only(self):
        self.assertTrue(self.ctx().writable)
        self.assertFalse(self.ctx(mode="plan").writable)
        self.assertFalse(self.ctx(mode="later").writable)
        self.assertFalse(self.ctx(read_only=True).writable)
        self.assertFalse(self.ctx(module=Reader).writable)
        self.assertEqual(self.ctx(mode="plan").read_only, True)

    def test_refused_outside_apply_before_anything_runs(self):
        with StandIns() as s:
            for ctx in (self.ctx(mode="plan"), self.ctx(read_only=True),
                        self.ctx(module=Reader)):
                with self.assertRaises(common.WriteRefused):
                    ctx.write(SET)
                with self.assertRaises(common.ReadRefused):
                    ctx.run(SET)
            self.assertEqual(s.ran(), [])

    def test_ctx_write_checks_the_skill_s_list(self):
        with StandIns() as s, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(common.WriteRefused):
                self.ctx(skill="github_repo-create").write(SET)
            with self.assertRaises(common.WriteRefused):
                self.ctx().write(["gh", "pr", "merge", "1"])
            self.assertEqual(s.ran(), [])
            c = self.ctx().write(SET)
            self.assertEqual(c.code, 3)
            c = self.ctx().run(SET)  # ctx.run routes a write to ctx.write
            self.assertEqual(len(s.ran()), 2)

    def test_reads_stay_on_the_read_only_runner_in_apply(self):
        with StandIns() as s, contextlib.redirect_stderr(io.StringIO()):
            ctx = self.ctx()
            ctx.read(["gh", "variable", "list", "--repo", "o/r", "--json", "name,value"])
            with self.assertRaises(common.ReadRefused):
                ctx.read(SET)
            self.assertEqual(len(s.ran()), 1)


class TestHiddenValues(unittest.TestCase):
    def test_shown_as_value_and_run_with_the_value(self):
        argv = SET[:-1] + [common.Hidden("us-central1")]
        self.assertEqual(common.show_command(argv),
                         "gh variable set GCP_REGION --repo example-org/example-repo --body "
                         "<value>")
        self.assertEqual(common._plain(argv)[-1], "us-central1")
        self.assertEqual(str(argv[-1]), "<value>")
        self.assertEqual(repr(argv[-1]), "<value>")
        self.assertNotIn("us-central1", "%s %r" % (argv[-1], argv))

    def test_runner_shows_value_and_runs_with_the_value(self):
        with StandIns() as s:
            err = io.StringIO()
            common.run_write("github_variables-set", SET[:-1] + [common.Hidden("s3cr3t x")],
                             stream=err)
            self.assertEqual(err.getvalue(), "+ gh variable set GCP_REGION --repo "
                                             "example-org/example-repo --body <value>\n")
            self.assertEqual(s.ran()[0].split(" ", 1)[1],
                             "variable set GCP_REGION --repo example-org/example-repo --body "
                             "s3cr3t x")

    def test_shown_text_of_choice(self):
        argv = ["git", "config", "--local", "user.name", common.Hidden("octo", "<login>")]
        self.assertEqual(common.show_command(argv), "git config --local user.name <login>")
        self.assertIsNone(common.write_refusal("github_checkout-setup", argv))

    def test_a_refusal_does_not_show_the_value(self):
        argv = ["gh", "variable", "delete", common.Hidden("s3cr3t")]
        with self.assertRaises(common.WriteRefused) as e:
            common.run_write("github_variables-set", argv)
        self.assertNotIn("s3cr3t", str(e.exception))
        argv = ["gh", "variable", "set", "A", "--repo", "o/r", "--body", common.Hidden("s3cr3t")]
        with self.assertRaises(common.ReadRefused) as e:
            common.run_read(argv)
        self.assertNotIn("s3cr3t", str(e.exception))


class Folder(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.top = tempfile.mkdtemp()
        self.dir = os.path.join(self.top, "work")
        self.outside = os.path.join(self.top, "outside")
        os.makedirs(self.dir)
        os.makedirs(self.outside)
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.top)

    def read(self, path):
        with open(path, "rb") as f:
            return f.read()


class TestWriteFile(Folder):
    def test_writes_exact_bytes_creating_folders_and_says_so(self):
        err = io.StringIO()
        text = "line one\r\nline two\n\ttab é\n"
        self.assertTrue(common.write_file("github_ci-setup", ".github/workflows/ci.yml",
                                          text, stream=err))
        self.assertEqual(err.getvalue(), "+ write .github/workflows/ci.yml\n")
        self.assertEqual(self.read(".github/workflows/ci.yml"), text.encode("utf-8"))
        self.assertTrue(common.write_file("go_setup", "web/main.go", b"package main\n",
                                          stream=io.StringIO()))
        self.assertEqual(self.read("web/main.go"), b"package main\n")
        common.write_file("go_setup", "web/main.go", b"x", stream=io.StringIO())
        self.assertEqual(self.read("web/main.go"), b"x")

    def refused(self, skill, path):
        err = io.StringIO()
        with self.assertRaises(common.WriteRefused):
            common.write_file(skill, path, "x", stream=err)
        self.assertEqual(err.getvalue(), "", "a refused write is not shown")

    def test_refuses_an_absolute_path(self):
        self.refused("project-declare", os.path.join(self.dir, ".aleogr", "project.json"))
        self.refused("project-declare", "/.aleogr/project.json")
        self.assertEqual(os.listdir(self.dir), [])

    def test_refuses_a_path_that_leaves_the_folder(self):
        self.refused("go_setup", "../outside/go.mod")
        self.refused("go_setup", "web/../../outside/go.mod")
        self.refused("go_setup", "web/./go.mod")
        self.refused("go_setup", "web//go.mod")
        self.assertEqual(os.listdir(self.outside), [])

    def test_refuses_a_link_that_leads_outside(self):
        os.symlink(self.outside, os.path.join(self.dir, "web"))
        self.refused("go_setup", "web/go.mod")
        os.makedirs(".github")
        os.symlink(self.outside, os.path.join(self.dir, ".github", "workflows"))
        self.refused("github_ci-setup", ".github/workflows/ci.yml")
        os.makedirs(".aleogr")
        os.symlink(os.path.join(self.outside, "project.json"),
                   os.path.join(self.dir, ".aleogr", "project.json"))  # dangling, outside
        self.refused("project-declare", ".aleogr/project.json")
        self.assertEqual(os.listdir(self.outside), [])

    def test_a_link_that_stays_inside_is_followed(self):
        os.makedirs("real")
        os.symlink(os.path.join(self.dir, "real"), os.path.join(self.dir, "web"))
        self.assertTrue(common.write_file("go_setup", "web/go.mod", "module x\n",
                                          stream=io.StringIO()))
        self.assertEqual(self.read("real/go.mod"), b"module x\n")

    def test_refuses_a_file_the_skill_does_not_name(self):
        self.refused("github_ci-setup", ".github/workflows/deploy.yml")
        self.refused("project-declare", "project.json")
        self.refused("go_setup", "web/other.go")
        self.refused("go_setup", ".github/go.mod")
        self.refused("github_variables-set", "x.txt")
        self.refused("no-such-skill", ".aleogr/project.json")

    def test_a_system_refusal_is_false(self):
        with open("web", "w") as f:
            f.write("a file where a folder is wanted")
        self.assertFalse(common.write_file("go_setup", "web/go.mod", "x",
                                           stream=io.StringIO()))

    def test_ctx_write_file_only_when_the_run_may_write(self):
        for mode, read_only in (("plan", False), ("apply", True)):
            ctx = common.Context("aleogr", "/x", "project-declare", Writer, mode, {},
                                 read_only=read_only)
            with self.assertRaises(common.WriteRefused):
                ctx.write_file(".aleogr/project.json", "{}\n")
        self.assertEqual(os.listdir(self.dir), [])
        ctx = common.Context("aleogr", "/x", "project-declare", Writer, "apply", {})
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertTrue(ctx.write_file(".aleogr/project.json", "{}\n"))
        self.assertEqual(err.getvalue(), "+ write .aleogr/project.json\n")


class TestBackup(Folder):
    def setUp(self):
        Folder.setUp(self)
        os.makedirs("web")
        with open("web/go.mod", "wb") as f:
            f.write(b"module x\n\ngo 1.27\n")
        os.chmod("web/go.mod", 0o640)
        os.utime("web/go.mod", (1000000000, 1000000000))

    def test_copies_and_puts_back_byte_for_byte(self):
        err = io.StringIO()
        b = common.Backup("go_setup", ["web/go.mod", "web/go.sum"], stream=err)
        self.assertTrue(b.ok)
        self.assertTrue(os.path.isdir(b.dir))
        self.assertTrue(b.existed("web/go.mod"))
        self.assertFalse(b.existed("web/go.sum"))
        self.assertEqual(os.listdir(b.dir), ["go.mod"])
        with open("web/go.mod", "wb") as f:
            f.write(b"module x\n\ngo 1.28\n")
        with open("web/go.sum", "wb") as f:
            f.write(b"sum\n")
        self.assertTrue(b.restore())
        self.assertEqual(self.read("web/go.mod"), b"module x\n\ngo 1.27\n")
        self.assertEqual(os.stat("web/go.mod").st_mode & 0o777, 0o640)
        self.assertEqual(int(os.stat("web/go.mod").st_mtime), 1000000000)
        self.assertFalse(os.path.exists("web/go.sum"))
        backup = b.dir
        b.discard()
        self.assertFalse(os.path.exists(backup))
        self.assertIsNone(b.dir)
        self.assertEqual(err.getvalue().splitlines(), [
            "+ backup web/go.mod web/go.sum", "+ restore web/go.mod web/go.sum",
            "+ remove " + backup])

    def test_go_sum_that_existed_is_put_back(self):
        with open("web/go.sum", "wb") as f:
            f.write(b"old sum\n")
        b = common.Backup("go_setup", ["web/go.mod", "web/go.sum"], stream=io.StringIO())
        with open("web/go.sum", "wb") as f:
            f.write(b"new sum\n")
        self.assertTrue(b.restore())
        self.assertEqual(self.read("web/go.sum"), b"old sum\n")
        b.discard()

    def test_a_file_that_cannot_be_copied(self):
        os.makedirs("web/go.sum")  # a folder: it cannot be copied as a file
        b = common.Backup("go_setup", ["web/go.mod", "web/go.sum"], stream=io.StringIO())
        self.assertFalse(b.ok)
        self.assertIsNone(b.dir)
        self.assertFalse(b.restore())

    def test_a_restore_that_fails_keeps_the_copies(self):
        b = common.Backup("go_setup", ["web/go.mod"], stream=io.StringIO())
        os.remove("web/go.mod")
        os.makedirs("web/go.mod")  # a folder where the file goes back
        self.assertFalse(b.restore())
        self.assertTrue(os.path.isfile(os.path.join(b.dir, "go.mod")))
        b.discard()

    def test_refuses_the_paths_the_file_helper_refuses(self):
        for paths in (["../outside/go.mod"], ["web/other.go"], ["/tmp/go.mod"],
                      ["web/go.mod", "api/go.mod"]):
            with self.subTest(paths=paths):
                err = io.StringIO()
                with self.assertRaises(common.WriteRefused):
                    common.Backup("go_setup", paths, stream=err)
                self.assertEqual(err.getvalue(), "")

    def test_ctx_backup_only_when_the_run_may_write(self):
        ctx = common.Context("aleogr-stack-go", "/x", "go_setup", Writer, "plan", {})
        with self.assertRaises(common.WriteRefused):
            ctx.backup(["web/go.mod"])


class TestWaits(unittest.TestCase):
    def setUp(self):
        common.reset_wait_budget()

    def tearDown(self):
        common.reset_wait_budget()

    def test_sixteen_waits_of_thirty_seconds_then_the_budget_is_spent(self):
        ctx = common.Context("aleogr-cloud-gcp", "/x", "gcp_login-setup", Writer, "apply", {})
        with StandIns() as s, contextlib.redirect_stderr(io.StringIO()):
            got = [ctx.wait() for _ in range(18)]
            self.assertEqual(got, [True] * 16 + [False] * 2)
            self.assertEqual([line.split(" ", 1)[1] for line in s.ran()], ["30"] * 16)
            self.assertTrue(all(line.endswith("/sleep 30") for line in s.ran()))
        self.assertEqual(common.waited_seconds(), 480)
        self.assertEqual(common.WAIT_BUDGET_SECONDS, 480)
        self.assertFalse(common.wait_allowed())

    def test_the_wait_is_shown_and_in_plan_too(self):
        ctx = common.Context("aleogr-cloud-gcp", "/x", "gcp_login-setup", Reader, "plan", {})
        shown = []

        def execute(argv, timeout=None):
            shown.append(common.show_command(argv))
            return common.Completed(0, "", "")

        ctx.execute = execute
        self.assertTrue(ctx.wait())
        self.assertEqual(shown, ["sleep 30"])

    def test_the_budget_counts_across_contexts_of_one_process(self):
        a = common.Context("p", "/x", "a", Writer, "apply", {})
        b = common.Context("p", "/x", "b", Writer, "apply", {})
        a.execute = b.execute = lambda argv, timeout=None: common.Completed(0, "", "")
        for _ in range(10):
            self.assertTrue(a.wait())
        self.assertEqual([b.wait() for _ in range(7)], [True] * 6 + [False])

    def test_fixed_sentence_and_item(self):
        self.assertIn("eight minutes", common.WAIT_BUDGET_SENTENCE)
        self.assertEqual(common.wait_budget_item("gcp_login-setup"), {
            "item": "run again", "reason": "manual",
            "how": "run gcp_login-setup again with the same arguments: it goes on from "
                   "where this run stopped"})
        ctx = common.Context("p", "/x", "go_setup", Writer, "apply", {})
        self.assertEqual(ctx.wait_budget_item(), common.wait_budget_item("go_setup"))


class TestReadOnlyOption(unittest.TestCase):
    def test_command_line(self):
        for argv in (["--read-only", "--json", "s"], ["--json", "--read-only", "s"]):
            inv = common.parse_command_line(argv + ["mode=apply"])
            self.assertEqual((inv.read_only, inv.json, inv.skill, inv.args),
                             (True, True, "s", {"mode": "apply"}))
        inv = common.parse_command_line(["--read-only", "s"])
        self.assertEqual((inv.read_only, inv.json), (True, False))
        self.assertFalse(common.parse_command_line(["s"]).read_only)
        for bad in (["--read-only"], ["--read-only", "--read-only", "s"],
                    ["--json", "--json", "s"], ["--read-only", "--has", "s"]):
            with self.subTest(argv=bad):
                with self.assertRaises(common.UsageError):
                    common.parse_command_line(bad)

    def command(self, *args, **kw):
        """Run aleogr-repo-github with stand-ins of gh and git that record each call."""
        plugin = "aleogr-repo-github"
        with StandIns() as s:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       PATH=s.dir + os.pathsep + os.path.dirname(sys.executable))
            p = subprocess.run([sys.executable, os.path.join(PLUGINS, plugin, "bin", plugin)]
                               + list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env, cwd=tempfile.gettempdir())
            return p.returncode, p.stdout.decode(), p.stderr.decode(), s.ran()

    def test_apply_is_refused_and_nothing_runs(self):
        args = ["github_variables-set", "owner=example-org", "name=example-repo",
                "variables=GCP_REGION=us-central1", "mode=apply"]
        code, out, err, ran = self.command("--read-only", *args)
        self.assertEqual((code, err, ran), (0, "", []))
        self.assertTrue(out.startswith(common.READ_ONLY_APPLY_SENTENCE + "\n\n```aleogr-result\n"))
        self.assertIn('"status": "failed"', out)
        self.assertIn('"mode": "apply"', out)
        self.assertIn('"cost": { "fixed": false, "notes": "nothing was run" }', out)
        self.assertNotIn("us-central1", out)
        code, out, err, ran = self.command("--json", "--read-only", *args)
        obj = json.loads(out)
        self.assertEqual((code, obj["status"], obj["answer"], obj["action"], ran),
                         (0, "failed", [common.READ_ONLY_APPLY_SENTENCE], "variables-set", []))

    def test_plan_runs_as_without_it(self):
        args = ["github_variables-set", "owner=example-org", "name=example-repo",
                "variables=GCP_REGION=us-central1"]
        a = self.command("--read-only", *args)
        b = self.command(*args)
        self.assertEqual(a[:3], b[:3])
        self.assertEqual([x.split("/gh ", 1)[1] for x in a[3]],
                         ["variable list --repo example-org/example-repo --json name,value"])
        self.assertEqual(len(b[3]), 1)

    def test_call_plugin_passes_it_on(self):
        with StandIns() as s:
            p = os.path.join(s.dir, "aleogr-fake")
            with open(p, "w") as f:
                f.write('#!/bin/sh\necho \'{"aleogr-result": 1, "args": "\'"$*"\'"}\'\n')
            os.chmod(p, 0o755)
            self.assertEqual(common.call_plugin("aleogr-fake", "x", {"a": "1"},
                                                read_only=True)["args"],
                             "--read-only --json x a=1")
            ctx = common.Context("p", "/x", "s", Reader, "plan", {}, read_only=True)
            self.assertEqual(ctx.call("aleogr-fake", "x")["args"], "--read-only --json x")
            ctx = common.Context("p", "/x", "s", Reader, "plan", {})
            self.assertEqual(ctx.call("aleogr-fake", "x")["args"], "--json x")


class TestDirectModeWithFiles(unittest.TestCase):
    """run.sh in the direct mode checks FILE, SAME_FILE, NO_FILE and FILE_NOT lines
    against the scenario's working folder after the command wrote in it. Checked on a
    copy of the harness with a stand-in plugin whose command writes and removes files."""

    def test_file_lines_see_what_the_command_wrote(self):
        tests = os.path.normpath(os.path.join(HERE, ".."))
        top = tempfile.mkdtemp()
        try:
            t = os.path.join(top, ".claude-plugin", "tests")
            shutil.copytree(os.path.join(tests, "bin"), os.path.join(t, "bin"))
            shutil.copy(os.path.join(tests, "run.sh"), t)
            bin_dir = os.path.join(top, ".claude-plugin", "plugins", "demo", "bin")
            os.makedirs(bin_dir)
            with open(os.path.join(bin_dir, "demo"), "w") as f:
                f.write("#!/bin/sh\n[ \"$1\" = write ] || exit 64\nmkdir -p out\n"
                        "printf 'hello\\n' > out/a.txt\nrm -f gone.txt\n"
                        "echo '```aleogr-result'\necho '{}'\necho '```'\n")
            os.chmod(os.path.join(bin_dir, "demo"), 0o755)
            with open(os.path.join(top, "ref.txt"), "w") as f:
                f.write("hello\n")
            sc = os.path.join(t, "scenarios", "demo-write")
            os.makedirs(os.path.join(sc, "files"))
            with open(os.path.join(sc, "files", "gone.txt"), "w") as f:
                f.write("x\n")
            with open(os.path.join(sc, "prompt.txt"), "w") as f:
                f.write("/demo:write mode=apply\n")
            with open(os.path.join(sc, "expect.txt"), "w") as f:
                f.write("FILE out/a.txt ^hello$\nSAME_FILE out/a.txt ref.txt\n"
                        "NO_FILE gone.txt\nFILE_NOT out/a.txt bye\nNOT_CALLED .\n")
            env = dict(os.environ, RUN_MODE="direct")
            p = subprocess.run(["bash", os.path.join(t, "run.sh"), "demo-write"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            self.assertEqual((p.returncode, p.stdout.decode()), (0, "PASS demo-write\n"))
            with open(os.path.join(sc, "expect.txt"), "w") as f:
                f.write("FILE out/a.txt ^bye$\n")
            p = subprocess.run(["bash", os.path.join(t, "run.sh"), "demo-write"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
            self.assertEqual(p.returncode, 1)
        finally:
            shutil.rmtree(top)


if __name__ == "__main__":
    unittest.main()
