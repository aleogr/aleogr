"""Unit tests of project-declare: the canonical form against the SKILL.md's examples, the
one file it writes and the rules no scenario covers.

Each test runs in a temporary folder (the current folder of the run). The context's
execute() fails the test: the skill runs no command at all. Its write_file() is the
shared one, so the allowlist of files is checked as in a real run.
"""

import contextlib
import copy
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "project-declare")
PATH = ".aleogr/project.json"

# The SKILL.md as it was before it became a shell over the command: the specification
# the canonical form is checked against.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden",
                       "project-declare.md"), encoding="utf-8") as _f:
    SKILL_MD = _f.read()
with open(os.path.join(ROOT, "defaults.json"), encoding="utf-8") as _f:
    DEFAULTS = json.load(_f)

BASE = {
    "$schema": skill.SCHEMA,
    "version": 1,
    "name": "demo",
    "repo": {
        "provider": "github", "owner": "example-org", "name": "demo",
        "visibility": "private", "description": "Demo project", "topics": ["sample"],
        "settings": {"mergeCommit": True, "squash": True, "rebase": False,
                     "deleteBranchOnMerge": True, "issues": True, "wiki": False,
                     "projects": False},
    },
}
WEB = {"name": "web", "stack": "go", "path": "web", "version": "1.27"}


def decl(components=None, environments=False, **extra):
    d = copy.deepcopy(BASE)
    if components is not None:
        d["components"] = components
    if environments:
        d["cloud"] = {"provider": "gcp", "region": "us-central1"}
        d["environments"] = {"dev": {}}
    d.update(extra)
    return d


class FakeContext(common.Context):
    def __init__(self, args, root=ROOT, mode="apply", read_only=False):
        common.Context.__init__(self, PLUGIN, root, "project-declare", skill, mode, args,
                                read_only=read_only)
        self.files = []

    def execute(self, argv, timeout=None):
        raise AssertionError("project-declare ran a command: %r" % (argv,))

    def write_file(self, path, content):
        self.files.append((path, content))
        return common.Context.write_file(self, path, content)


class Folder(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.dir = tempfile.mkdtemp()
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.dir)

    def put(self, data):
        os.makedirs(".aleogr", exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data, indent=2) + "\n"
        with open(PATH, "w", encoding="utf-8") as f:
            f.write(text)
        return text

    def content(self):
        with open(PATH, encoding="utf-8") as f:
            return f.read()

    def run_skill(self, root=ROOT, **args):
        ctx = FakeContext(dict(args), root=root)
        with contextlib.redirect_stderr(io.StringIO()):
            r = skill.run(dict(args), ctx)
        self.assertEqual(r.block["mode"], "apply")
        self.assertEqual(r.block["resources"], [])
        self.assertEqual(r.block["pending"], [])
        self.assertEqual(r.block["outputs"]["path"], PATH)
        return r, ctx

    def failed(self, *sentences, **args):
        before = self.content() if os.path.exists(PATH) else None
        r, ctx = self.run_skill(**args)
        self.assertEqual(r.status, "failed", r.lines)
        self.assertEqual(ctx.files, [])
        self.assertEqual(r.block["outputs"]["declaration"], None)
        self.assertEqual(r.block["outputs"]["changes"], [])
        after = self.content() if os.path.exists(PATH) else None
        self.assertEqual(before, after)
        if sentences:
            self.assertEqual(r.lines, list(sentences))
        return r


def _examples():
    return re.findall(r"```json\n(.*?)```", SKILL_MD, re.S)


class TestCanonicalForm(Folder):
    """The golden file: what the skill writes, byte for byte, against the SKILL.md."""

    def test_the_example_of_the_skill_md(self):
        example = _examples()[0]
        self.assertEqual(skill.canonical_text(skill.canonical(json.loads(example))), example)

    def test_the_endings_of_the_skill_md(self):
        two, env = _examples()[1], _examples()[2]
        comps = [{"name": "web", "stack": "go", "path": "web", "version": "1.27"},
                 {"name": "api", "stack": "go", "path": "services/api", "version": "1.27"}]
        text = skill.canonical_text(skill.canonical(decl(comps)))
        self.assertTrue(text.endswith(two), text)
        d = decl(comps, environments=True)
        d["cloud"]["root"] = "tst"
        text = skill.canonical_text(skill.canonical(d))
        self.assertTrue(text.endswith(env), text)

    def test_the_database_key_and_notes(self):
        d = decl([dict(WEB, database=True), {"name": "api", "stack": "go", "path": "api",
                                             "version": "1.27", "database": False}],
                 environments=True, notes='Free "text"\nhere')
        text = skill.canonical_text(skill.canonical(d))
        self.assertIn('    { "name": "api", "stack": "go", "path": "api", "version": "1.27" },\n'
                      '    { "name": "web", "stack": "go", "path": "web", "version": "1.27", '
                      '"database": true }\n  ],\n', text)
        self.assertTrue(text.endswith('  "environments": { "dev": {} },\n'
                                      '  "notes": "Free \\"text\\"\\nhere"\n}\n'))

    def test_a_new_declaration_is_written_exactly(self):
        r, ctx = self.run_skill(name="demo", owner="example-org", description="Demo project",
                                topics="sample")
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.files, [(PATH, _examples()[0])])
        self.assertEqual(self.content(), _examples()[0])
        self.assertEqual(r.lines[2], "```json")
        self.assertEqual("\n".join(r.lines[3:-1]) + "\n", _examples()[0])

    def test_the_only_file_is_on_the_allowlist(self):
        self.assertIsNone(common.file_refusal("project-declare", PATH))
        self.assertEqual(skill.DEFAULT_MODE, "apply")
        self.assertEqual(skill.RESULT_MODE, "apply")
        self.assertTrue(skill.WRITES)


class TestNoWriteWithoutApply(Folder):
    def test_read_only_and_plan_runs_write_nothing(self):
        for mode, ro in (("plan", False), ("apply", True)):
            ctx = FakeContext({"mode": mode} if mode == "plan" else {}, mode=mode,
                              read_only=ro)
            with self.assertRaises(common.WriteRefused):
                ctx.write_file(PATH, "{}\n")
        # mode= is not an argument of the skill: refused before anything is written.
        r = self.failed("`mode` is not an argument of project-declare.",
                        name="demo", owner="example-org", description="Demo project",
                        mode="plan")
        self.assertFalse(os.path.exists(".aleogr"))

    def test_the_dispatcher_refuses_read_only(self):
        out, err = io.StringIO(), io.StringIO()
        code = common.main(PLUGIN, ROOT, ["--read-only", "project-declare", "name=demo",
                                          "owner=example-org", "description=Demo"],
                           stdout=out, stderr=err)
        self.assertEqual(code, 0)
        self.assertIn(common.READ_ONLY_APPLY_SENTENCE, out.getvalue())
        self.assertFalse(os.path.exists(".aleogr"))


class TestUnchanged(Folder):
    def test_another_layout_is_left_byte_for_byte(self):
        d = decl([WEB])
        d["repo"]["topics"] = ["zeta", "sample"]
        del d["$schema"]
        text = self.put(json.dumps(d, indent=4))  # no final newline either
        r, ctx = self.run_skill(topics="sample,zeta,sample", visibility="private")
        self.assertEqual(r.status, "unchanged")
        self.assertEqual(ctx.files, [])
        self.assertEqual(self.content(), text)
        self.assertEqual(r.block["outputs"]["declaration"], d)
        self.assertEqual(r.block["outputs"]["changes"], [])
        self.assertEqual("\n".join(r.lines[3:-1]), text)

    def test_empty_components_absent_topics_and_false_database(self):
        d = decl([dict(WEB, database=False)])
        del d["repo"]["topics"]
        text = self.put(d)
        r, _ = self.run_skill(topics="", component="web", database="no")
        self.assertEqual(r.status, "unchanged")
        self.assertEqual(self.content(), text)
        d = decl([])
        text = self.put(d)
        r, _ = self.run_skill()
        self.assertEqual(r.status, "unchanged")
        self.assertEqual(self.content(), text)

    def test_a_rewrite_drops_an_empty_components_list(self):
        self.put(decl([]))
        r, _ = self.run_skill(wiki="true")
        self.assertEqual(r.status, "updated")
        self.assertNotIn("components", self.content())
        self.assertEqual(r.block["outputs"]["changes"], ["repo.settings.wiki"])


class TestUpdates(Folder):
    def test_only_the_given_keys_change(self):
        d = decl([WEB], environments=True, notes="keep me")
        d["cloud"]["region"] = "europe-west1"
        self.put(d)
        r, _ = self.run_skill(issues="false")
        self.assertEqual(r.status, "updated")
        want = skill.canonical(d)
        want["repo"]["settings"]["issues"] = False
        self.assertEqual(json.loads(self.content()), want)
        self.assertEqual(r.block["outputs"]["changes"], ["repo.settings.issues"])

    def test_the_order_of_changes(self):
        self.put(decl([WEB], notes="old"))
        r, _ = self.run_skill(notes="new", component="api", stack="go", description="X",
                              environment="dev", cloudRoot="tst", topics="")
        self.assertEqual(r.block["outputs"]["changes"],
                         ["repo.description", "repo.topics", "components.api", "cloud",
                          "environments.dev", "notes"])

    def test_root_on_an_existing_cloud_is_cloud_root(self):
        d = decl([WEB])
        d["cloud"] = {"provider": "gcp", "region": "us-east1"}
        self.put(d)
        r, _ = self.run_skill(cloudRoot="tst")
        self.assertEqual(r.block["outputs"]["changes"], ["cloud.root"])
        self.assertIn('"cloud": { "provider": "gcp", "region": "us-east1", "root": "tst" }',
                      self.content())
        self.assertNotIn("environments", self.content())

    def test_environment_keeps_an_existing_region(self):
        d = decl([WEB])
        d["cloud"] = {"provider": "gcp", "region": "us-east1"}
        self.put(d)
        r, _ = self.run_skill(environment="dev")
        self.assertEqual(r.block["outputs"]["changes"], ["environments.dev"])
        self.assertIn('"region": "us-east1"', self.content())

    def test_notes_empty_removes_the_key(self):
        self.put(decl(notes="x"))
        r, _ = self.run_skill(notes="")
        self.assertEqual(r.block["outputs"]["changes"], ["notes"])
        self.assertNotIn("notes", self.content())

    def test_topics_replace_the_list(self):
        self.put(decl())
        r, _ = self.run_skill(topics="docs,docs,api")
        self.assertIn('"topics": ["api", "docs"]', self.content())
        r, _ = self.run_skill(topics="")
        self.assertIn('"topics": []', self.content())

    def test_version_and_database_of_an_existing_component(self):
        self.put(decl([dict(WEB, database=True)], environments=True))
        r, _ = self.run_skill(component="web", version="1.26")
        self.assertEqual(r.status, "updated")
        self.assertIn('"version": "1.26", "database": true }', self.content())
        r, _ = self.run_skill(component="web", database="no", version="1.22")
        self.assertIn('{ "name": "web", "stack": "go", "path": "web", "version": "1.22" }',
                      self.content())

    def test_the_public_line(self):
        r, _ = self.run_skill(name="demo", owner="example-org", description="D",
                              visibility="public")
        self.assertEqual(r.lines[-1], skill.PUBLIC_LINE)
        r, _ = self.run_skill(wiki="true")  # already public: no line
        self.assertNotIn(skill.PUBLIC_LINE, r.lines)
        r, _ = self.run_skill(visibility="private")
        self.assertNotIn(skill.PUBLIC_LINE, r.lines)
        r, _ = self.run_skill(visibility="public")
        self.assertEqual(r.block["outputs"]["changes"], ["repo.visibility"])
        self.assertEqual(r.lines[-1], skill.PUBLIC_LINE)
        r, _ = self.run_skill(visibility="public")
        self.assertEqual(r.status, "unchanged")
        self.assertNotIn(skill.PUBLIC_LINE, r.lines)

    def test_new_declaration_defaults(self):
        r, _ = self.run_skill(name="demo", owner="example-org", description="D",
                              component="web", stack="go", database="yes",
                              environment="dev", notes="n", squash="false")
        self.assertEqual(r.status, "created")
        got = json.loads(self.content())
        self.assertEqual(got["repo"]["name"], "demo")
        self.assertEqual(got["repo"]["visibility"], DEFAULTS["repo"]["visibility"])
        self.assertIs(got["repo"]["settings"]["squash"], False)
        self.assertEqual(got["components"], [dict(WEB, database=True)])
        self.assertEqual(got["cloud"], DEFAULTS["cloud"])
        self.assertEqual(r.block["outputs"]["changes"][-4:],
                         ["components.web", "cloud", "environments.dev", "notes"])


class TestFailures(Folder):
    def test_one_sentence_per_problem(self):
        self.failed("`color` is not an argument of project-declare.",
                    "These required arguments are missing: `owner`, `description`.",
                    skill.NAME_RESERVED % "shared",
                    name="shared", color="red")

    def test_the_prescribed_sentences(self):
        self.put(decl([WEB]))
        self.failed(skill.DATABASE_VALUE % "maybe", component="web", database="maybe")
        self.failed(skill.ROOT_VALUE % "", environment="dev", cloudRoot="")
        self.failed(skill.ENVIRONMENT_VALUE % "prd", environment="prd")
        self.failed(skill.VERSION_INVALID % "1.27.4", component="web", version="1.27.4")
        self.failed(skill.PATH_NESTED % ("web/api", "web"), component="api", stack="go",
                    path="web/api")
        self.failed(skill.ANOTHER_COMPONENT % ("path", "x", "path", "web", "web"),
                    component="web", path="x")
        self.failed(skill.ANOTHER_PROJECT % ("owner", "other", "owner", "example-org"),
                    owner="other")
        self.failed(skill.DESCRIBE_COMPONENT % "`path`, `version`", path="x", version="1.27")

    def test_a_folder_inside_the_new_one(self):
        self.put(decl([{"name": "api", "stack": "go", "path": "web/api", "version": "1.27"}]))
        self.failed(skill.PATH_NESTED % ("web", "api"), component="web", stack="go")

    def test_the_path_rule(self):
        self.put(decl())
        r = self.failed(component="web", stack="go", path="web/")
        self.assertTrue(r.lines[0].startswith("`path=web/` cannot hold a component: it "))

    def test_database_version_and_defaults(self):
        self.put(decl([dict(WEB, version="1.22")], environments=True))
        self.failed(skill.DATABASE_VERSION % ("web", "1.22", "1.26", "1.26"),
                    component="web", database="yes")
        r, _ = self.run_skill(component="web", database="yes", version="1.26")
        self.assertEqual(r.status, "updated")
        root = self.defaults_root(lambda d: d["stacks"]["go"].pop("database"))
        # The file itself now breaks the rule: the defaults' value is needed to read it.
        r, _ = self.run_skill(root=root, wiki="true")
        self.assertEqual(r.lines, [skill.NO_MIN_VERSION % "go"])

    def test_defaults_provider_and_cloud(self):
        root = self.defaults_root(lambda d: d["repo"].update(provider="gitlab"))
        r, _ = self.run_skill(root=root, name="demo", owner="o", description="D")
        self.assertEqual(r.lines, [skill.PROVIDER_DEFAULTS])
        root = self.defaults_root(lambda d: d["cloud"].update(region="Moon"))
        r, _ = self.run_skill(root=root, name="demo", owner="o", description="D",
                              environment="dev")
        self.assertEqual(r.lines, [skill.CLOUD_DEFAULTS])
        self.assertFalse(os.path.exists(".aleogr"))

    def test_an_invalid_file(self):
        d = decl()
        d["repo"]["color"] = "red"
        self.put(d)
        self.failed(skill.NOT_VALID % "repo has the unknown key color", wiki="true")

    def test_the_merge_method(self):
        self.put(decl())
        self.failed(skill.NO_MERGE_METHOD, squash="false", mergeCommit="false")

    def defaults_root(self, change):
        root = tempfile.mkdtemp(dir=self.dir)
        d = copy.deepcopy(DEFAULTS)
        change(d)
        with open(os.path.join(root, "defaults.json"), "w") as f:
            json.dump(d, f)
        return root


if __name__ == "__main__":
    unittest.main()
