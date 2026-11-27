"""Unit tests of github_ci-setup: its arguments, plan and apply, the cases no scenario
covers, and its golden file (the text of step 5, as the SKILL.md writes it).

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs; the local file is read and written in a temporary folder. The scenarios
gh-ci-setup-* cover the rest, in the direct mode.
"""

import contextlib
import io
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
skill = load_skill(PLUGIN, "github_ci-setup")

ARGS = {"owner": "example-org", "name": "example-repo",
        "components": "web:web:go:1.27,api:services/api:go:1.27",
        "workflows": "example-org/tooling"}
DEPLOY = {"deploy": "dev", "deployComponents": "web,api", "project": "demo",
          "region": "us-central1"}
CONTENTS = "gh api repos/example-org/example-repo/contents/.github/workflows/ci.yml"
MARKER1 = "# aleogr-ci 1 api:services/api:go:1.27,web:web:go:1.27"
SHA1 = "1" * 40
SHA2 = "2" * 40


def ok(text):
    return common.Completed(0, text, "")


def fail(text, code=1):
    return common.Completed(code, "", text)


class FakeContext(common.Context):
    def __init__(self, answers, args, written=None):
        common.Context.__init__(self, PLUGIN, ROOT, "github_ci-setup", skill,
                                args.get("mode") or "plan", args)
        self.answers = answers
        self.calls = []
        self.files = []
        self.written = written  # when set, the text actually written in place of the file's

    def write_file(self, path, content):
        self.files.append(path)
        if self.written is not None:
            content = self.written
        with contextlib.redirect_stderr(io.StringIO()):  # its `+ write` line
            return common.Context.write_file(self, path, content)

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.calls.append(line)
        for prefix, c in self.answers.items():
            if line.startswith(prefix):
                return c
        return common.Completed(0, "", "")


def validate(**over):
    args = dict(ARGS, **over)
    args = dict((k, v) for k, v in args.items() if v is not None)
    return skill.validate(args)


class TestArguments(unittest.TestCase):
    def assertProblem(self, sentence, **over):
        declared, problem = validate(**over)
        self.assertIsNone(declared)
        self.assertTrue(problem.startswith(sentence), problem)

    def test_exact_sentences(self):
        self.assertProblem(skill.TWO_ENVIRONMENTS, **dict(DEPLOY, deploy="dev,hom"))
        self.assertProblem(skill.NO_REGION, **dict(DEPLOY, region=""))
        self.assertProblem(skill.NO_REGION, **dict(DEPLOY, region=None))
        self.assertProblem(skill.COMPONENTS_WITHOUT_DEPLOY, deployComponents="api")
        self.assertProblem(skill.UNKNOWN_DEPLOY_COMPONENT % "mobile",
                           **dict(DEPLOY, deployComponents="api,mobile"))
        self.assertProblem(skill.SERVICE_NAME % "demo-long-name-orders-service-api",
                           components="orders-service-api:orders:go:1.27",
                           **dict(DEPLOY, project="demo-long-name",
                                  deployComponents="orders-service-api"))
        self.assertProblem(skill.SERVICE_NAME % "a-web",
                           **dict(DEPLOY, project="a", deployComponents="web"))

    def test_missing(self):
        self.assertProblem("workflows is missing.", workflows=None)
        self.assertProblem("project is missing.", **dict(DEPLOY, project=None))
        self.assertProblem("deployComponents is missing.",
                           **dict(DEPLOY, deployComponents=""))
        declared, problem = validate(components="", workflows=None)
        self.assertIsNone(problem)
        self.assertIsNone(declared.marker)

    def test_components_rules(self):
        for components in ("web:web:rust:1.0", "web:web:go:1", "ci:ci:go:1.27",
                           "deploy-x:x:go:1.27", "on:on:go:1.27", "Web:web:go:1.27",
                           "web:.github:go:1.27", "web:web/:go:1.27", "web:a/../b:go:1.27",
                           "web:web.:go:1.27", "web:-w:go:1.27", "web:web:go",
                           "web:web:go:1.27,,api:api:go:1.27",
                           "web:web:go:1.27,web:other:go:1.27",
                           "web:x:go:1.27,api:x:go:1.27", "web:web:go:1.27,api:web/api:go:1.27",
                           "api:web/api:go:1.27,web::go:1.27"):
            with self.subTest(components=components):
                self.assertProblem("components is not valid", components=components)

    def test_other_rules(self):
        self.assertProblem("workflows is not valid", workflows="a/b/c")
        self.assertProblem("ref is not valid", ref="head")
        self.assertProblem("defaultBranch is not valid", defaultBranch="a..b")
        self.assertProblem("defaultBranch is not valid", defaultBranch="main/")
        self.assertProblem("deploy is not valid", **dict(DEPLOY, deploy="Dev"))
        self.assertProblem("region is not valid", **dict(DEPLOY, region="us-"))
        self.assertProblem("project is not valid", **dict(DEPLOY, project="a" * 15))
        self.assertProblem("deployComponents is not valid",
                           **dict(DEPLOY, deployComponents="web,web"))
        self.assertProblem("mode is not valid", mode="run")

    def test_markers(self):
        declared, _ = validate(components="web::go:1.27,api:services/api:go:1.27")
        self.assertEqual(declared.marker, MARKER1)
        declared, _ = validate(defaultBranch="trunk", **dict(DEPLOY, deployComponents="api"))
        self.assertEqual(declared.marker,
                         "# aleogr-ci 2 api:services/api:go:1.27,web:web:go:1.27 "
                         "deploy=dev:api project=demo branch=trunk region=us-central1")

    def test_failed_outputs(self):
        ctx = FakeContext({}, dict(ARGS, components="web:web:rust:1.0"))
        r = skill.run(dict(ARGS, components="web:web:rust:1.0"), ctx)
        o = r.block["outputs"]
        self.assertEqual((r.status, o["marker"], o["checks"], o["local"], o["written"]),
                         ("failed", None, [], None, False))
        self.assertEqual(ctx.calls, [])


class Base(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.dir = tempfile.mkdtemp()
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.dir)

    def local(self, text):
        os.makedirs(".github/workflows", exist_ok=True)
        with open(".github/workflows/ci.yml", "w", encoding="utf-8") as f:
            f.write(text)

    def run_skill(self, answers, written=None, **over):
        args = dict(ARGS, **over)
        args = dict((k, v) for k, v in args.items() if v is not None)
        ctx = FakeContext(answers, args, written)
        return skill.run(dict(args), ctx), ctx


def ci_file(marker, sha, deploy_sha=None):
    text = marker + "\r\nname: ci\n"
    text += "    uses: example-org/tooling/.github/workflows/ci-go.yml@%s\n" % sha
    if deploy_sha:
        text += ("    uses: example-org/tooling/.github/workflows/deploy-cloud-run.yml@%s\n"
                 % deploy_sha)
    return text


class TestPlan(Base):
    def test_as_declared_with_a_carriage_return(self):
        self.local(ci_file(MARKER1, SHA1))
        r, ctx = self.run_skill({CONTENTS: ok(ci_file(MARKER1, SHA1))})
        o = r.block["outputs"]
        self.assertEqual((r.status, o["local"], o["inRepository"], o["repositoryAsDeclared"]),
                         ("unchanged", "as-declared", True, True))
        self.assertEqual(len(ctx.calls), 1)

    def test_kept_commit(self):
        declared, _ = validate()
        self.assertEqual(skill.kept_commit(declared, ci_file("# old", SHA1)), SHA1)
        self.assertIsNone(skill.kept_commit(declared, ci_file("# old", SHA1) +
                                            ci_file("", SHA2)))
        self.assertIsNone(skill.kept_commit(declared, "# old\nno uses\n"))
        self.assertIsNone(skill.kept_commit(declared, None))
        latest, _ = validate(ref="latest")
        self.assertIsNone(skill.kept_commit(latest, ci_file("# old", SHA1)))
        deployed, _ = validate(**DEPLOY)
        self.assertIsNone(skill.kept_commit(deployed, ci_file(MARKER1, SHA1)))
        v2 = "# aleogr-ci 2 web:web:go:1.27 deploy=dev:web project=demo branch=main region=x"
        self.assertEqual(skill.kept_commit(deployed, ci_file(v2, SHA1, SHA1)), SHA1)
        self.assertIsNone(skill.kept_commit(deployed, ci_file(v2, SHA1, SHA2)))
        self.assertIsNone(skill.kept_commit(deployed, ci_file(v2, SHA1)))

    def test_would_update_says_the_kept_commit(self):
        self.local(ci_file("# aleogr-ci 1 web:web:go:1.27", SHA1))
        r, _ = self.run_skill({CONTENTS: fail("gh: Not Found (HTTP 404)")})
        o = r.block["outputs"]
        self.assertEqual((r.status, o["local"], o["inRepository"], o["repositoryAsDeclared"],
                          o["ref"]), ("would-update", "differs", False, None, None))
        self.assertTrue(any(SHA1 in line for line in r.lines))

    def test_no_component(self):
        r, _ = self.run_skill({CONTENTS: ok(ci_file(MARKER1, SHA1))}, components="",
                              workflows=None)
        o = r.block["outputs"]
        self.assertEqual((r.status, o["local"], o["repositoryAsDeclared"]),
                         ("unchanged", "not-needed", False))
        self.local("anything")
        r, _ = self.run_skill({CONTENTS: fail("gh: Not Found (HTTP 404)")}, components="")
        self.assertEqual((r.status, r.block["outputs"]["local"]), ("pending", "differs"))
        self.assertEqual(r.block["pending"], [{"item": "ci.yml is not needed",
                                               "reason": "manual",
                                               "how": skill.NOT_NEEDED_HOW}])

    def test_read_refused_says_only_the_sentence(self):
        r, _ = self.run_skill({CONTENTS: ok("gh: Bad Gateway (HTTP 502)\n")})
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.lines, [skill.READ_REFUSED])
        o = r.block["outputs"]
        self.assertEqual((o["local"], o["inRepository"], o["marker"], o["checks"]),
                         (None, None, MARKER1, ["ci"]))

    def test_not_logged_in(self):
        r, _ = self.run_skill({CONTENTS: fail("To get started, run: gh auth login")})
        self.assertEqual(r.status, "failed")
        self.assertIn("gh auth login", r.lines[0])


# ---------------------------------------------------------------------------
# mode=apply

SKILL_MD = os.path.join(ROOT, "skills", "github_ci-setup", "SKILL.md")
HEAD = "gh api repos/example-org/tooling/commits/main"
NOT_FOUND = fail("gh: Not Found (HTTP 404)")


def _skill_block(after):
    """The yaml block of the SKILL.md that follows the text `after`, as written in the
    file (the list's three spaces of indentation removed)."""
    with open(SKILL_MD, encoding="utf-8") as f:
        text = f.read()
    rest = text[text.index(after):]
    body = rest.split("```yaml\n", 1)[1].split("\n   ```", 1)[0]
    return "\n".join(line[3:] for line in body.split("\n")) + "\n"


def read_ci():
    with open(".github/workflows/ci.yml", encoding="utf-8", newline="") as f:
        return f.read()


class TestGoldenFile(Base):
    """Step 5: the file is exactly the SKILL.md's text."""

    def test_the_whole_file_of_the_skill(self):
        declared, _ = validate()
        self.assertEqual(skill.ci_yml(declared, SHA2), _skill_block("the whole file is:"))

    def test_the_deploy_job_of_the_skill(self):
        declared, _ = validate(**DEPLOY)
        text = skill.ci_yml(declared, SHA2)
        whole = _skill_block("the whole file is:")
        fragment = _skill_block("and the job `api` is followed by:")
        self.assertTrue(fragment.startswith("\n  deploy-api-dev:\n"))
        api_job = whole.split("\n  web:\n")[0]  # the head and the job api
        api_job = api_job.replace(MARKER1, declared.marker)
        self.assertTrue(text.startswith(api_job + fragment), text)
        web_fragment = fragment.replace("api", "web").replace('"services/web"', '"web"')
        self.assertIn('    go-version: "1.27"\n' + web_fragment, text)
        self.assertTrue(text.endswith(whole[whole.index("\n  ci:\n"):]))
        self.assertNotIn("vars.", text)
        self.assertNotIn("\t", text)
        self.assertFalse(any(line != line.rstrip() for line in text.split("\n")))

    def test_one_listed_component_of_two(self):
        declared, _ = validate(**dict(DEPLOY, deployComponents="api"))
        text = skill.ci_yml(declared, SHA2)
        self.assertIn("\n  deploy-api-dev:\n", text)
        self.assertNotIn("deploy-web", text)
        self.assertIn('      go-version: "1.27"\n\n  ci:\n', text)

    def test_the_file_is_the_only_write(self):
        self.assertIsNone(common.file_refusal("github_ci-setup", ".github/workflows/ci.yml"))
        r, ctx = self.run_skill({CONTENTS: NOT_FOUND, HEAD: ok('{"sha": "%s"}' % SHA2)},
                                mode="apply")
        self.assertEqual(ctx.files, [".github/workflows/ci.yml"])
        declared, _ = validate()
        self.assertEqual(read_ci(), skill.ci_yml(declared, SHA2))


class TestApply(Base):
    def test_missing_is_created_with_the_head(self):
        r, ctx = self.run_skill({CONTENTS: NOT_FOUND, HEAD: ok('{"sha": "%s"}' % SHA2)},
                                mode="apply")
        self.assertEqual(ctx.calls, [CONTENTS + " -H Accept: application/vnd.github.raw",
                                     HEAD])
        o = r.block["outputs"]
        self.assertEqual((r.status, o["local"], o["ref"], o["written"], r.block["pending"],
                          r.block["mode"]), ("created", "missing", SHA2, True, [], "apply"))

    def test_differs_keeps_the_commit_without_a_command(self):
        self.local(ci_file("# aleogr-ci 1 web:web:go:1.27", SHA1))
        r, ctx = self.run_skill({CONTENTS: NOT_FOUND}, mode="apply")
        self.assertEqual(len(ctx.calls), 1)
        self.assertEqual((r.status, r.block["outputs"]["ref"]), ("updated", SHA1))
        self.assertIn("ci-go.yml@" + SHA1, read_ci())

    def test_deploy_from_version_1_reads_the_head(self):
        self.local(ci_file(MARKER1, SHA1))
        r, ctx = self.run_skill({CONTENTS: NOT_FOUND, HEAD: ok('{"sha": "%s"}' % SHA2)},
                                mode="apply", **DEPLOY)
        self.assertEqual(ctx.calls[-1], HEAD)
        self.assertEqual((r.status, r.block["outputs"]["ref"]), ("updated", SHA2))

    def test_head_refused_writes_nothing(self):
        for answer, words in ((NOT_FOUND, "example-org/tooling or its branch main was not "
                               "found"), (fail("gh: Server Error (HTTP 500)"), "could not be "
                                          "read"), (ok('{"sha": "abc"}'), "could not be read")):
            with self.subTest(answer=answer):
                r, ctx = self.run_skill({CONTENTS: NOT_FOUND, HEAD: answer}, mode="apply")
                o = r.block["outputs"]
                self.assertEqual((r.status, o["local"], o["ref"], o["written"], ctx.files),
                                 ("failed", "missing", None, False, []))
                self.assertIn(words, r.lines[0])
                self.assertNotIn("500", "\n".join(r.lines))
                self.assertFalse(os.path.exists(".github/workflows/ci.yml"))

    def test_write_refused(self):
        with open(".github", "w") as f:
            f.write("a file where the folder should be")
        r, ctx = self.run_skill({CONTENTS: NOT_FOUND, HEAD: ok('{"sha": "%s"}' % SHA2)},
                                mode="apply")
        o = r.block["outputs"]
        self.assertEqual((r.status, o["written"], o["ref"]), ("failed", False, None))

    def test_verification_failed_adds_the_item(self):
        r, ctx = self.run_skill({CONTENTS: NOT_FOUND, HEAD: ok('{"sha": "%s"}' % SHA2)},
                                written="# something else\n", mode="apply", **DEPLOY)
        self.assertEqual((r.status, r.block["outputs"]["written"]), ("created", True))
        self.assertEqual(r.block["pending"], [{
            "item": "verify", "reason": "manual",
            "how": "/aleogr-repo-github:github_ci-setup owner=example-org name=example-repo "
                   "components=web:web:go:1.27,api:services/api:go:1.27 "
                   "workflows=example-org/tooling deploy=dev deployComponents=web,api "
                   "project=demo region=us-central1 mode=plan"}])

    def test_nothing_to_write(self):
        self.local(ci_file(MARKER1, SHA1))
        r, ctx = self.run_skill({CONTENTS: NOT_FOUND}, mode="apply")
        self.assertEqual((r.status, ctx.files, r.block["outputs"]["ref"]),
                         ("unchanged", [], None))
        r, ctx = self.run_skill({CONTENTS: NOT_FOUND}, mode="apply", components="",
                                workflows=None)
        self.assertEqual((r.status, ctx.files), ("pending", []))
        self.assertEqual(read_ci(), ci_file(MARKER1, SHA1))

    def test_plan_never_writes(self):
        ctx = FakeContext({}, dict(ARGS))
        with self.assertRaises(common.WriteRefused):
            ctx.write_file(".github/workflows/ci.yml", "x")
        r, ctx = self.run_skill({CONTENTS: NOT_FOUND})
        self.assertEqual((r.status, os.path.exists(".github")), ("would-create", False))

    def test_read_only_option_refuses_apply(self):
        ctx = common.Context(PLUGIN, ROOT, "github_ci-setup", skill, "apply",
                             dict(ARGS, mode="apply"), read_only=True)
        self.assertFalse(ctx.writable)
        with self.assertRaises(common.WriteRefused):
            ctx.write_file(".github/workflows/ci.yml", "x")


if __name__ == "__main__":
    unittest.main()
