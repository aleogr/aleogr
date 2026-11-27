"""Unit tests of the endings a command reaches when the input or a refusal stops it: an
argument given twice, a read or a write that the tooling does not allow, and the
layout of a nested object of the block (BLOCK_EXPAND).

Run: python3 -m unittest discover -s .claude-plugin/tests/unit
No provider is reached: a stand-in plugin runs against stand-in commands.
"""

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

SECRET = "s3cr3t-value"

# Stand-in skills, under the names of real skills so that their allowlists apply.
STAND_INS = {
    # A plan that tries a write through the read-only runner.
    "github_repo_describe": '''
FAMILY, PROVIDER, ACTION = "repo", "github", "repo-describe"
def run(args, ctx):
    ctx.read(["gh", "repo", "view", "example-org/example-repo"])
    ctx.read(["gh", "repo", "edit", "other-org/other-repo", "--enable-wiki=true"])
    return ctx.result("unchanged", {})
''',
    # An apply that writes, then tries a write no skill names.
    "github_variables_set": '''
import aleogr_common as common
FAMILY, PROVIDER, ACTION = "repo", "github", "variables-set"
DEFAULT_MODE = "plan"
WRITES = True
def run(args, ctx):
    ctx.write(["gh", "variable", "set", "GCP_REGION", "--repo", "example-org/example-repo",
               "--body", common.Hidden("%s")])
    ctx.write(["gh", "repo", "delete", "other-org/other-repo", "--yes"])
    return ctx.result("updated", {})
''' % SECRET,
    # An apply that writes a file, then tries one it may not write.
    "project_declare": '''
FAMILY, PROVIDER, ACTION = "orchestrator", "aleogr", "project-declare"
DEFAULT_MODE = RESULT_MODE = "apply"
WRITES = True
def run(args, ctx):
    ctx.write_file(".aleogr/project.json", "{}\\n")
    ctx.write_file("other-file.txt", "x\\n")
    return ctx.result("created", {})
''',
}


class StandInPlugin(object):
    """A plugin folder `demo` with the real bin/ and shared module, and the stand-in
    skills above."""

    def __enter__(self):
        self.top = tempfile.mkdtemp()
        root = os.path.join(self.top, "demo")
        os.makedirs(os.path.join(root, "bin"))
        os.makedirs(os.path.join(root, "scripts", "skills"))
        shutil.copy(os.path.join(PLUGINS, "aleogr", "bin", "aleogr"),
                    os.path.join(root, "bin", "demo"))
        shutil.copy(os.path.join(PLUGINS, "aleogr", "scripts", "aleogr_common.py"),
                    os.path.join(root, "scripts"))
        open(os.path.join(root, "scripts", "skills", "__init__.py"), "w").close()
        for name, text in STAND_INS.items():
            with open(os.path.join(root, "scripts", "skills", name + ".py"), "w") as f:
                f.write(text)
        self.command = os.path.join(root, "bin", "demo")
        self.cwd = os.path.join(self.top, "cwd")
        os.makedirs(self.cwd)
        return self

    def run(self, *args):
        with StandIns() as s:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       PATH=s.dir + os.pathsep + os.path.dirname(sys.executable))
            p = subprocess.run([sys.executable, self.command] + list(args),
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env, cwd=self.cwd)
            return p.returncode, p.stdout.decode(), p.stderr.decode(), s.ran()

    def __exit__(self, *exc):
        shutil.rmtree(self.top)


def block_of(out):
    return json.loads(out.split("```aleogr-result\n", 1)[1].split("\n```", 1)[0])


class TestArgumentGivenTwice(unittest.TestCase):
    def test_parse(self):
        repeated = []
        self.assertEqual(common.parse_args(["a=1", "b=2", "a=3", "a=4", "b=5"], repeated),
                         {"a": "1", "b": "2"})
        self.assertEqual(repeated, ["a", "b"])
        with self.assertRaises(common.UsageError):
            common.parse_args(["a=1", "a=2"])
        inv = common.parse_command_line(["s", "a=1", "a=2"])
        self.assertEqual((inv.args, inv.repeated), ({"a": "1"}, ["a"]))
        self.assertEqual(common.parse_command_line(["s", "a=1"]).repeated, [])

    def test_a_failed_result_and_nothing_runs(self):
        plugin = "aleogr-repo-github"
        command = os.path.join(PLUGINS, plugin, "bin", plugin)
        args = ["github_variables-set", "owner=example-org", "name=example-repo",
                "variables=GCP_REGION=us-central1", "owner=other-org", "mode=apply"]
        with StandIns() as s:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       PATH=s.dir + os.pathsep + os.path.dirname(sys.executable))
            for extra in ([], ["--json"]):
                p = subprocess.run([sys.executable, command] + extra + args,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=env, cwd=tempfile.gettempdir())
                out = p.stdout.decode()
                self.assertEqual((p.returncode, p.stderr.decode()), (0, ""))
                if extra:
                    obj = json.loads(out)
                    self.assertEqual(obj["answer"], ["The argument owner is given twice."])
                else:
                    self.assertTrue(out.startswith(
                        "The argument owner is given twice.\n\n```aleogr-result\n"))
                    obj = block_of(out)
                self.assertEqual((obj["status"], obj["mode"], obj["action"], obj["outputs"],
                                  obj["cost"], obj["pending"]),
                                 ("failed", "apply", "variables-set", {},
                                  common.NOTHING_RUN_COST, []))
                self.assertNotIn("us-central1", out)
            self.assertEqual(s.ran(), [])

    def test_one_sentence_per_key(self):
        with StandInPlugin() as p:
            code, out, err, ran = p.run("github_repo-describe", "a=1", "b=2", "a=3", "b=4",
                                        "a=5")
        self.assertEqual((code, err, ran), (0, "", []))
        self.assertTrue(out.startswith("The argument a is given twice.\n"
                                       "The argument b is given twice.\n\n"))

    def test_project_declare_writes_nothing(self):
        plugin = "aleogr"
        command = os.path.join(PLUGINS, plugin, "bin", plugin)
        folder = tempfile.mkdtemp()
        try:
            p = subprocess.run([sys.executable, command, "project-declare", "name=demo",
                                "owner=example-org", "description=Demo project",
                                "name=other"], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=folder,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
            out = p.stdout.decode()
            self.assertEqual(p.returncode, 0)
            self.assertTrue(out.startswith("The argument name is given twice.\n\n"))
            block = block_of(out)
            self.assertEqual((block["status"], block["mode"]), ("failed", "apply"))
            self.assertEqual(os.listdir(folder), [])
        finally:
            shutil.rmtree(folder)

    def test_not_converted_still_comes_first(self):
        sql = "aleogr-db-gcp-cloud-sql"
        p = subprocess.run([sys.executable, os.path.join(PLUGINS, sql, "bin", sql),
                            "gcp-cloud-sql_instance-create", "a=1", "a=2"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual((p.returncode, p.stdout), (64, b""))


class TestRefusedCommand(unittest.TestCase):
    def test_refused_read_gives_a_result_and_exits_70(self):
        with StandInPlugin() as p:
            code, out, err, ran = p.run("github_repo-describe")
            jcode, jout, _, _ = p.run("--json", "github_repo-describe")
        self.assertEqual(code, common.EXIT_SOFTWARE)
        self.assertEqual(err.splitlines()[-1],
                         "demo: github_repo-describe: refused, not a read")
        self.assertEqual(out.split("\n\n")[0].splitlines(),
                         [common.REFUSED_SENTENCE, common.REFUSED_NOTHING_WRITTEN])
        block = block_of(out)
        self.assertEqual((block["status"], block["mode"], block["outputs"], block["cost"],
                          block["pending"]),
                         ("failed", "plan", {}, common.REFUSED_COST, []))
        self.assertEqual(len(ran), 1)  # the first read ran, the refused one did not
        self.assertNotIn("other-org", out + err)
        self.assertEqual(jcode, common.EXIT_SOFTWARE)
        self.assertEqual(json.loads(jout)["answer"],
                         [common.REFUSED_SENTENCE, common.REFUSED_NOTHING_WRITTEN])

    def test_refused_write_names_what_was_written(self):
        with StandInPlugin() as p:
            code, out, err, ran = p.run("github_variables-set", "mode=apply")
        self.assertEqual(code, common.EXIT_SOFTWARE)
        self.assertEqual(err.splitlines()[-1],
                         "demo: github_variables-set: refused, not an allowed write")
        self.assertEqual(out.split("\n\n")[0].splitlines(), [
            common.REFUSED_SENTENCE,
            "Before it stopped, this run had already run these writes: `gh variable set "
            "GCP_REGION --repo example-org/example-repo --body <value>`."])
        self.assertEqual(block_of(out)["mode"], "apply")
        self.assertEqual(len(ran), 1)
        for never in (SECRET, "other-org", "delete"):
            self.assertNotIn(never, out + err)

    def test_refused_file_names_the_file_written(self):
        with StandInPlugin() as p:
            code, out, err, _ = p.run("project-declare")
            written = os.listdir(p.cwd)
        self.assertEqual(code, common.EXIT_SOFTWARE)
        self.assertEqual(out.split("\n\n")[0].splitlines(), [
            common.REFUSED_SENTENCE,
            "Before it stopped, this run had already run these writes: "
            "`write .aleogr/project.json`."])
        self.assertNotIn("other-file", out + err)
        self.assertEqual(written, [".aleogr"])

    def test_restore_is_recorded(self):
        folder = tempfile.mkdtemp()
        old = os.getcwd()
        try:
            os.chdir(folder)
            os.makedirs("web")
            with open("web/go.mod", "w") as f:
                f.write("module x\n")

            class Writer(object):
                FAMILY, PROVIDER, ACTION, WRITES = "stack", "go", "setup", True

            ctx = common.Context("p", "/x", "go_setup", Writer, "apply", {})
            import contextlib
            import io
            with contextlib.redirect_stderr(io.StringIO()):
                b = ctx.backup(["web/go.mod", "web/go.sum"])
                self.assertTrue(b.restore())
                b.discard()
            self.assertEqual(ctx.writes_run, ["restore web/go.mod web/go.sum"])
        finally:
            os.chdir(old)
            shutil.rmtree(folder)

    def test_cannot_tell(self):
        class Reader(object):
            FAMILY, PROVIDER, ACTION = "repo", "github", "repo-describe"

        ctx = common.Context("p", "/x", "s", Reader, "plan", {})
        del ctx.writes_run
        self.assertEqual(common.refused_result(ctx).lines,
                         [common.REFUSED_SENTENCE, common.REFUSED_UNKNOWN])


class TestBlockLayout(unittest.TestCase):
    BLOCK = {"aleogr-result": 1, "status": "updated",
             "outputs": {"path": "p", "declaration": {"name": "demo", "repo": {
                 "topics": ["a"], "settings": {"wiki": False}}}, "changes": ["x"]},
             "pending": []}

    def test_default_is_unchanged(self):
        self.assertEqual(common.render_block(self.BLOCK), "\n".join([
            '{',
            '  "aleogr-result": 1,',
            '  "status": "updated",',
            '  "outputs": {',
            '    "path": "p",',
            '    "declaration": { "name": "demo", "repo": { "topics": ["a"], "settings": '
            '{ "wiki": false } } },',
            '    "changes": ["x"]',
            '  },',
            '  "pending": []',
            '}']))
        self.assertEqual(common.render_block(self.BLOCK, ("outputs",)),
                         common.render_block(self.BLOCK, {"outputs": ()}))

    def test_nested(self):
        self.assertEqual(common.render_block(
            self.BLOCK, {"outputs": {"declaration": ("repo",)}}), "\n".join([
                '{',
                '  "aleogr-result": 1,',
                '  "status": "updated",',
                '  "outputs": {',
                '    "path": "p",',
                '    "declaration": {',
                '      "name": "demo",',
                '      "repo": {',
                '        "topics": ["a"],',
                '        "settings": { "wiki": false }',
                '      }',
                '    },',
                '    "changes": ["x"]',
                '  },',
                '  "pending": []',
                '}']))

    def test_project_declare_matches_its_skill(self):
        """The block of project-declare is laid out as its SKILL.md's example."""
        skill_md = os.path.join(HERE, "golden", "project-declare.md")
        with open(skill_md, encoding="utf-8") as f:
            text = f.read()
        example = text.split("```aleogr-result\n", 1)[1].split("\n```", 1)[0]

        class Declare(object):
            FAMILY, PROVIDER, ACTION = "orchestrator", "aleogr", "project-declare"
            RESULT_MODE = "apply"
            BLOCK_EXPAND = {"outputs": {"declaration": ("repo",)}}

        ctx = common.Context("aleogr", "/x", "project-declare", Declare, "apply", {})
        block = json.loads(example)
        r = ctx.result(block["status"], block["outputs"],
                       cost={"fixed": False, "notes": "writes a local file only"})
        self.assertEqual(common.render_answer(r), "```aleogr-result\n" + example + "\n```\n")
        from helpers import load_skill
        self.assertEqual(load_skill("aleogr", "project-declare").BLOCK_EXPAND,
                         Declare.BLOCK_EXPAND)


if __name__ == "__main__":
    unittest.main()
