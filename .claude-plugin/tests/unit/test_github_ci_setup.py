"""Unit tests of github_ci-setup's arguments and plan, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs; the local file is written in a temporary folder. The scenarios
gh-ci-setup-* of mode=plan cover the rest, in the direct mode.
"""

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
    def __init__(self, answers, args):
        common.Context.__init__(self, PLUGIN, ROOT, "github_ci-setup", skill,
                                args.get("mode") or "plan", args)
        self.answers = answers
        self.calls = []

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

    def run_skill(self, answers, **over):
        args = dict(ARGS, **over)
        ctx = FakeContext(answers, args)
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


if __name__ == "__main__":
    unittest.main()
