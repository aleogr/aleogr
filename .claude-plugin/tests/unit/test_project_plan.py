"""Unit tests of project-plan's rules, the cases no scenario covers.

gather() is given a caller that answers each invocation from canned result objects and
records it, so no command and no provider runs; the declaration is written in a
temporary folder. The scenarios project-plan-* cover the rest, in the direct mode.
"""

import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402
from helpers import called_commands, run_with_other_suite  # noqa: E402

PLUGIN = "aleogr"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "project-plan")
TC = skill.TC

PID = "aleogr-dev-demo-ab12"
with open(os.path.join(ROOT, "defaults.json"), encoding="utf-8") as _f:
    SERVICES = json.load(_f)["project"]["services"]
SHARED = "aleogr-shared-ab12"

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


def decl(components=None, environments=False, **extra):
    d = copy.deepcopy(BASE)
    if components is not None:
        d["components"] = components
    if environments:
        d["cloud"] = {"provider": "gcp", "region": "us-central1"}
        d["environments"] = {"dev": {}}
    d.update(extra)
    return d


WEB = {"name": "web", "stack": "go", "path": "web", "version": "1.27"}
WEB_DB = dict(WEB, database=True)


def res(status="unchanged", answer=(), pending=(), data=None, **outputs):
    r = {"status": status, "outputs": outputs, "answer": list(answer),
         "pending": list(pending)}
    if data is not None:
        r["data"] = data
    return r


def describe(**over):
    o = {"exists": True, "id": 1, "ownerId": 2, "url": "https://github.com/example-org/demo",
         "visibility": "private", "defaultBranch": "main", "description": "Demo project",
         "topics": ["aleogr-demo", "sample"],
         "settings": dict(BASE["repo"]["settings"]),
         "protection": {"state": "protected", "matches": True}}
    o.update(over)
    return res(**o)


def everything(components=True, database=False):
    """Every invocation answering "as declared", for a declaration with environments."""
    names = (["web"] if components else [])
    services = [{"component": n, "exists": True, "differences": [], "placeholder": False,
                 "url": "https://demo-%s.run.app" % n} for n in names]
    return {
        "github_repo-describe": describe(),
        "github_checkout-setup": res(state="equal", reason=None),
        "github_pull-request-open": res(folder="ready", changed=[], openPullRequest=None),
        "go_setup": res(route="not-asked", modules="not-asked"),
        "gcp_environment-describe": res(exists=True, billingLinked=True, projectId=PID,
                                        enabledServices=SERVICES + ["sqladmin.googleapis.com"]),
        "gcp-artifact-registry_registry-describe": res(
            exists=True, otherRegions=[], format="DOCKER",
            cleanup={"keep": 5, "deletesTheRest": True, "dryRun": False, "rules": 2},
            push=["serviceAccount:demo-ci@%s.iam.gserviceaccount.com" % PID],
            imagePath="us-central1-docker.pkg.dev/%s/demo" % PID),
        "gcp_ci-identity-setup": res(
            account="demo-ci@%s.iam.gserviceaccount.com" % PID,
            ciVariables={"GCP_PROJECT_ID": PID, "GCP_WIF_PROVIDER": "projects/1/p",
                         "GCP_CI_ACCOUNT": "demo-ci@%s.iam.gserviceaccount.com" % PID}),
        "gcp_login-describe": res(prepared=True, readable=True),
        "gcp_deploy-describe": res(services=services, missing=[], differing=[], waiting=[]),
        "gcp-cloud-sql_database-describe": res(instanceState="running", databaseExists=True,
                                               users=[{"user": True, "client": True,
                                                       "instanceUser": True}], read=True),
        "github_variables-set": res(set=[], already=["GCP_PROJECT_ID"]),
        "github_ci-setup": res(local="as-declared", inRepository=True),
    }


class FakeCaller(object):
    def __init__(self, cwd, answers, tools=None):
        self._cwd = cwd
        self.answers = answers  # skill -> result, or a list of results (one per call)
        self.tools_state = tools or {}
        self.calls = []

    def call(self, command, skill_name, args):
        for k, v in args.items():
            assert isinstance(v, str), (skill_name, k, v)
        self.calls.append((skill_name, dict(args)))
        a = self.answers[skill_name]
        if isinstance(a, list):
            return copy.deepcopy(a.pop(0))
        if callable(a):
            return a(args)
        return copy.deepcopy(a)

    def suites(self, commands):
        self.suites_asked = list(commands)  # the versions, before the first read

    def tools(self, command):
        self.calls.append(("tools-check", {"command": command}))
        state = self.tools_state.get(command, "ok")
        fix = None if state == "ok" else {"gh": "gh auth login", "gcloud": "gcloud auth login",
                                          "go": TC.GO_FIX}[command]
        return TC.Check("local", {"name": command, "command": command, "state": state,
                                  "fix": fix})

    def cwd(self):
        return self._cwd

    def defaults_path(self):
        return os.path.join(ROOT, "defaults.json")

    def skills(self):
        return [c[0] for c in self.calls]


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.dir, ".aleogr"))

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, data, path=".aleogr/project.json"):
        full = os.path.join(self.dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))

    def plan(self, data, answers, args=None, tools=None):
        if data is not None:
            self.write(data)
        caller = FakeCaller(self.dir, answers, tools)
        p = skill.decide(skill.gather(args or {}, caller))
        return p, caller

    def rows(self, p):
        return {i: (s, a) for i, s, a in p.items}


# ---------------------------------------------------------------------------
# The declaration's rules


class TestDeclarationRules(unittest.TestCase):
    def bad(self, d, words):
        with self.assertRaises(skill.Invalid) as e:
            skill.check_declaration(d, "1.26")
        self.assertIn(words, str(e.exception))

    def test_valid(self):
        self.assertFalse(skill.check_declaration(decl(), "1.26"))
        self.assertTrue(skill.check_declaration(
            decl([WEB_DB], environments=True, notes="free text"), "1.26"))
        self.assertFalse(skill.check_declaration(decl([]), "1.26"))
        d = decl(environments=True)
        d["cloud"]["root"] = "tst"
        skill.check_declaration(d, None)

    def test_unknown_keys_at_any_level(self):
        self.bad(dict(decl(), extra=1), "the top level has the unknown key extra")
        d = decl([dict(WEB, color="x")])
        self.bad(d, "components[0] has the unknown key color")
        d = decl(environments=True)
        d["cloud"]["zone"] = "a"
        self.bad(d, "cloud has the unknown key zone")
        d = decl()
        d["repo"]["settings"]["forks"] = True
        self.bad(d, "repo.settings has the unknown key forks")

    def test_top_level(self):
        self.bad([], "not a JSON object")
        d = decl()
        del d["repo"]
        self.bad(d, "lacks the key repo")
        self.bad(dict(decl(), version=2), "version")
        self.bad(dict(decl(), version=True), "version")
        self.bad(dict(decl(), version="1"), "version")
        self.bad(dict(decl(), **{"$schema": 1}), "$schema")
        self.bad(dict(decl(), notes=3), "notes")

    def test_name(self):
        for name in ("", "Demo", "1demo", "demo-", "abcdefghijklmno", 5):
            with self.subTest(name=name):
                self.bad(dict(decl(), name=name), "name must have")
        for name in ("test", "shared", "test-x"):
            with self.subTest(name=name):
                self.bad(dict(decl(), name=name), "reserved")
        skill.check_declaration(dict(decl(), name="abcdefghijklmn"), None)

    def test_repo(self):
        def with_repo(**over):
            d = decl()
            d["repo"].update(over)
            return d
        self.bad(with_repo(provider="gitlab"), "repo.provider")
        for owner in ("-a", "a-", "a" * 40, "a_b"):
            self.bad(with_repo(owner=owner), "repo.owner")
        for name in (".", "..", "a b", "a" * 101, ""):
            self.bad(with_repo(name=name), "repo.name")
        self.bad(with_repo(visibility="internal"), "repo.visibility")
        for desc in ("", "a" * 351, "two\nlines", 'a "quote"', "a `tick`", "$x", "a\\b",
                     "“x”", "„x"):
            with self.subTest(desc=desc):
                self.bad(with_repo(description=desc), "repo.description")
        skill.check_declaration(with_repo(description="a" * 350), None)

    def test_topics(self):
        def with_topics(t):
            d = decl()
            d["repo"]["topics"] = t
            return d
        self.bad(with_topics("x"), "list of strings")
        self.bad(with_topics(["a", "a"]), "repeated")
        self.bad(with_topics(["-a"]), "the topic -a")
        self.bad(with_topics(["a" * 51]), "the topic")
        self.bad(with_topics(["aleogr-demo"]), "derived")
        d = decl()
        del d["repo"]["topics"]
        skill.check_declaration(d, None)
        skill.check_declaration(with_topics(["1x", "aleogr-other"]), None)

    def test_settings(self):
        d = decl()
        d["repo"]["settings"]["wiki"] = "false"
        self.bad(d, "repo.settings.wiki is not a JSON boolean")
        d = decl()
        del d["repo"]["settings"]["issues"]
        self.bad(d, "repo.settings lacks the key issues")
        d = decl()
        d["repo"]["settings"].update(mergeCommit=False, squash=False, rebase=False)
        self.bad(d, "none of mergeCommit, squash and rebase")

    def test_components(self):
        self.bad(decl({"a": 1}), "components is not a list")
        for name in ("changes", "ci", "deploy-web", "true", "off", "Web", "1web",
                     "a" * 21):
            with self.subTest(name=name):
                self.bad(decl([dict(WEB, name=name)]), "name")
        self.bad(decl([WEB, dict(WEB, path="other")]), "two components are named web")
        self.bad(decl([dict(WEB, stack="rust")]), "stack")
        for path in ("/web", "web/", "a//b", ".github", "a/..", "-x", "a.", "A"):
            with self.subTest(path=path):
                self.bad(decl([dict(WEB, path=path)]), "path")
        self.bad(decl([WEB, dict(WEB, name="api")]), "two components have the path web")
        self.bad(decl([WEB, dict(WEB, name="api", path="web/api")]), "inside")
        self.bad(decl([dict(WEB, name="api", path="web/api"), WEB]), "inside")
        skill.check_declaration(decl([WEB, dict(WEB, name="api", path="webapi")]), None)
        for version in ("1.27.4", "1", "v1.27", "1.21", "1.9"):
            with self.subTest(version=version):
                self.bad(decl([dict(WEB, version=version)]), "version")
        for version in ("1.22", "2.0", "1.100"):
            skill.check_declaration(decl([dict(WEB, version=version)]), None)

    def test_database(self):
        self.bad(decl([dict(WEB, database="true")], environments=True), "JSON boolean")
        self.bad(decl([WEB_DB]), "needs cloud and environments")
        self.bad(decl([dict(WEB_DB, version="1.25")], environments=True), "needs Go 1.26")
        skill.check_declaration(decl([dict(WEB_DB, version="1.26")], environments=True),
                                "1.26")
        # false needs nothing, and the defaults are read only for true.
        skill.check_declaration(decl([dict(WEB, database=False)]),
                                lambda: self.fail("defaults read"))

    def test_cloud_and_environments(self):
        d = decl(environments=True)
        d["cloud"]["provider"] = "aws"
        self.bad(d, "cloud.provider")
        for region in ("us_central1", "US-central1", "us-central", "uscentral1"):
            d = decl(environments=True)
            d["cloud"]["region"] = region
            self.bad(d, "cloud.region")
        d = decl(environments=True)
        d["cloud"]["root"] = "prd"
        self.bad(d, "cloud.root")
        self.bad(dict(decl(), environments={"dev": {}}), "environments needs cloud")
        self.bad(dict(decl(environments=True), environments={}), "at least one key")
        self.bad(dict(decl(environments=True), environments={"hom": {}}), "unknown key hom")
        self.bad(dict(decl(environments=True), environments={"dev": {"x": 1}}),
                 "empty object")
        self.bad(dict(decl(environments=True), name="ab"), "at least three")
        skill.check_declaration(dict(decl(), cloud={"provider": "gcp",
                                                    "region": "us-central1"}), None)
        # <name>-<component> has 6 to 30 characters.
        self.bad(decl([dict(WEB, name="a" * 20)], environments=True, name="abcdefghijkl"),
                 "6 to 30")
        self.bad(decl([dict(WEB, name="w")], environments=True, name="abc"), "6 to 30")
        self.bad(decl([dict(WEB, name="web-")], environments=True), "ends with -")

    def test_layout_does_not_matter(self):
        text = json.dumps(decl([WEB]), indent=7, sort_keys=True)
        skill.check_declaration(skill.parse_json(text), None)
        with self.assertRaises(ValueError):
            skill.parse_json('{"version": NaN}')


class TestArguments(unittest.TestCase):
    def test_rules(self):
        self.assertIsNone(skill.validate_args({}))
        self.assertIsNone(skill.validate_args({"projectId": PID, "readCloud": "yes"}))
        self.assertIn("projectId", skill.validate_args({"projectId": "Bad"}))
        self.assertIn("projectId", skill.validate_args({"projectId": "abcde"}))
        self.assertIn("projectId", skill.validate_args({"projectId": "abcdef-"}))
        self.assertIn("readCloud", skill.validate_args({"readCloud": "no"}))


# ---------------------------------------------------------------------------
# The database's settings: one rule in code (database_settings), used by both commands.
# Until part 3a it was a paragraph that project-plan/SKILL.md and project-apply/SKILL.md
# had to hold byte for byte; both skills are commands now, and the rule is pinned here.


class TestDatabaseSettings(unittest.TestCase):
    def test_one_rule_for_both_commands(self):
        # project-apply builds the settings only through this function, never a copy.
        path = os.path.join(ROOT, "scripts", "skills", "project_apply.py")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("PP.database_settings(", text)
        for name in ("DB_INSTANCE", "DB_NAME", "DB_USER"):
            self.assertNotIn(name, text)

    def test_each_sentence_of_the_rule(self):
        one = skill.database_settings("demo", ["web"], SHARED, "us-central1",
                                      "aleogr-shared", PID).split(";")
        # Exactly three settings, each <NAME>=<value>, after `<c>:`.
        self.assertEqual(one, [
            # the shared instance's connection name
            "web:DB_INSTANCE=%s:us-central1:aleogr-shared" % SHARED,
            # <project>_<environment>
            "web:DB_NAME=demo_dev",
            # the database user of the component's service account
            "web:DB_USER=demo-web@%s.iam" % PID])
        # Every `-` of the project's name is written `_` in the database's name only.
        got = skill.database_settings("my-app", ["web"], SHARED, "r", "i", PID)
        self.assertIn("web:DB_NAME=my_app_dev", got)
        self.assertIn("web:DB_USER=my-app-web@%s.iam" % PID, got)
        # The environment is part of the database's name.
        self.assertIn("web:DB_NAME=demo_hom",
                      skill.database_settings("demo", ["web"], SHARED, "r", "i", PID, "hom"))

    def test_settings(self):
        got = skill.database_settings("my-app", ["web", "api"], SHARED, "us-central1",
                                      "aleogr-shared", PID)
        self.assertEqual(got, ";".join([
            "api:DB_INSTANCE=%s:us-central1:aleogr-shared" % SHARED,
            "api:DB_NAME=my_app_dev",
            "api:DB_USER=my-app-api@%s.iam" % PID,
            "web:DB_INSTANCE=%s:us-central1:aleogr-shared" % SHARED,
            "web:DB_NAME=my_app_dev",
            "web:DB_USER=my-app-web@%s.iam" % PID]))
        self.assertEqual(skill.database_settings("demo", [], SHARED, "r", "i", PID), "")


# ---------------------------------------------------------------------------
# The steps


class TestSteps(Base):
    def test_arguments_fail_before_any_invocation(self):
        p, c = self.plan(decl(), {}, args={"readCloud": "maybe"})
        self.assertEqual((p.status, c.calls), ("failed", []))
        self.assertEqual(p.pending, [{"item": "arguments", "reason": "manual",
                                      "how": "readCloud is not valid: it must be yes"}])
        self.assertEqual(p.outputs["project"], "demo")
        self.assertEqual(p.outputs["items"], [])
        self.assertIsNone(p.outputs["repositoryEnvironments"])

    def test_no_declaration(self):
        shutil.rmtree(os.path.join(self.dir, ".aleogr"))
        p, c = self.plan(None, {})
        self.assertEqual((p.status, c.calls), ("failed", []))
        self.assertEqual(p.failure.sentence, skill.NO_DECLARATION)
        self.assertEqual((p.outputs["project"], p.outputs["repository"],
                          p.outputs["visibility"], p.outputs["exposes"]),
                         (None, None, None, False))

    def test_defaults_missing_a_value(self):
        self.write(decl([WEB_DB], environments=True))
        caller = FakeCaller(self.dir, {})
        caller.defaults_path = lambda: os.path.join(self.dir, "nothing.json")
        r = skill.gather({}, caller)
        self.assertEqual((r.failure.item, caller.calls), ("defaults", []))
        with open(os.path.join(self.dir, "d.json"), "w") as f:
            json.dump({"ci": {"workflowsRepository": "a/b"}}, f)
        caller = FakeCaller(self.dir, {})
        caller.defaults_path = lambda: os.path.join(self.dir, "d.json")
        r = skill.gather({}, caller)
        self.assertEqual(r.failure.item, "defaults")
        self.assertIn("stacks.go.database.minVersion", r.failure.sentence)

    def test_order_without_components_or_environments(self):
        p, c = self.plan(decl(), everything())
        self.assertEqual(c.skills(), ["tools-check", "github_repo-describe",
                                      "github_checkout-setup", "github_pull-request-open"])
        self.assertNotIn("checks", c.calls[1][1])
        self.assertNotIn("head", c.calls[2][1])
        self.assertEqual(c.calls[3][1]["paths"], ".aleogr/project.json")
        self.assertEqual([i for i, _, _ in p.items],
                         ["repository", "settings", "visibility", "declaration", "protection"])
        self.assertEqual(p.status, "unchanged")

    def test_every_called_mode_is_a_read_mode(self):
        self.write("# aleogr-ci 2 web:web:go:1.27 deploy=dev:web\n", ".github/workflows/ci.yml")
        p, c = self.plan(decl([WEB_DB], environments=True), everything(database=True))
        self.assertEqual(p.status, "unchanged")
        for name, args in c.calls:
            if "mode" in args:
                self.assertEqual(args["mode"], "plan", name)
        self.assertEqual(c.skills(), [
            "tools-check", "tools-check", "github_repo-describe", "github_checkout-setup",
            "github_pull-request-open", "go_setup", "gcp_environment-describe",
            "gcp-artifact-registry_registry-describe", "gcp_ci-identity-setup",
            "gcp_login-describe", "gcp_environment-describe", "gcp_deploy-describe",
            "gcp-cloud-sql_database-describe", "github_variables-set", "github_ci-setup"])
        deploy = dict(c.calls)["gcp_deploy-describe"]
        self.assertIn("env", deploy)
        self.assertEqual(len(p.items), 14)
        block = json.dumps(p.outputs)
        self.assertNotIn(SHARED, block)
        self.assertNotIn("demo-web@", block)

    def test_go_setup_arguments(self):
        self.write("# aleogr-ci 1 web:web:go:1.27\n", ".github/workflows/ci.yml")
        p, c = self.plan(decl([WEB_DB, dict(WEB, name="api", path="services/api")],
                              environments=True), everything(database=True))
        calls = [a for n, a in c.calls if n == "go_setup"]
        self.assertEqual([a["component"] for a in calls], ["api", "web"])
        self.assertEqual(calls[0], {"component": "api", "path": "services/api",
                                    "version": "1.27",
                                    "module": "github.com/example-org/demo/services/api",
                                    "mode": "plan", "dockerfile": "yes"})
        self.assertEqual(calls[1]["database"], "yes")
        self.assertEqual(calls[1]["minVersion"], "1.26")
        self.assertIn("cloud.google.com/go/cloudsqlconn", calls[1]["modules"])
        self.assertEqual(dict(c.calls)["github_repo-describe"]["checks"], "ci")

    def test_tooling_paths(self):
        d = skill.Declaration(decl([WEB_DB, dict(WEB, name="api", path="services/api")],
                                   environments=True))
        self.assertEqual(d.tooling_paths(), [
            ".aleogr/project.json", ".github/workflows/ci.yml",
            "services/api/go.mod", "services/api/main.go", "services/api/main_test.go",
            "services/api/Dockerfile",
            "web/go.mod", "web/main.go", "web/main_test.go", "web/go.sum", "web/db.go",
            "web/db_test.go", "web/Dockerfile"])
        self.assertEqual(d.components_arg(), "api:services/api:go:1.27,web:web:go:1.27")
        self.assertEqual(skill.Declaration(decl(name="my-app")).database, "my_app_dev")

    def test_gh_failure_stops_everything(self):
        p, c = self.plan(decl(environments=True), {}, tools={"gh": "not-authenticated"})
        self.assertEqual(c.skills(), ["tools-check"])
        self.assertEqual(p.pending, [{"item": "gh", "reason": "manual",
                                      "how": "gh auth login"}])
        self.assertIsNone(p.outputs["environment"])

    def test_a_tool_names_the_skill_the_owner_ran(self):
        # The plan run by itself names itself; invoked by project-apply, the sentence
        # names the command the owner ran.
        p, _ = self.plan(decl(environments=True), {}, tools={"gh": "not-authenticated"})
        self.assertEqual(p.failure.sentence, "gh is not authenticated: the fix is gh auth "
                         "login, then run /aleogr:project-plan again.")
        self.assertFalse(p.failure.called)
        caller = FakeCaller(self.dir, {}, {"gcloud": "missing"})
        p = skill.decide(skill.gather({}, caller, again="/aleogr:project-apply confirm=yes"))
        self.assertTrue(p.failure.sentence.endswith(
            ", then run /aleogr:project-apply confirm=yes again."), p.failure.sentence)

    def test_a_command_of_another_suite_ends_the_plan_at_once(self):
        a = everything()
        sentence = common.VERSION_SENTENCE.format(callee="aleogr-cloud-gcp", caller="aleogr")

        def mismatch(args):
            raise common.PluginVersion({"status": "failed", "answer": [sentence],
                                        "callError": "version"})

        a["gcp_environment-describe"] = mismatch
        p, c = self.plan(decl(environments=True), a)
        self.assertEqual(c.skills()[-1], "gcp_environment-describe")
        self.assertEqual((p.status, p.items), ("failed", []))
        self.assertEqual(skill.answer_lines(p), [sentence])
        self.assertEqual(p.pending, [{"item": "plugins", "reason": "manual",
                                      "how": sentence[:-1]}])
        self.assertTrue(p.failure.called)

    def test_tools_check_go_never_fails_the_plan(self):
        a = everything(database=True)
        a["go_setup"] = res(status="would-create", route="present", modules="would-add")
        p, c = self.plan(decl([WEB_DB], environments=True), a, tools={"go": "missing"})
        self.assertIn(("tools-check", {"command": "go"}), c.calls)
        rows = self.rows(p)
        self.assertEqual(rows["components"], (skill.NEEDS_GO, "fix by hand"))
        self.assertIn({"item": "go", "reason": "manual", "how": skill.GO_HOW}, p.pending)
        self.assertEqual(p.status, "pending")

    def test_ambiguous_shared_project(self):
        a = everything(database=True)
        a["gcp_environment-describe"] = [
            a["gcp_environment-describe"],
            res(status="failed", answer=["More than one GCP project has the labels x (a, b): "
                                         "none was picked."], exists=None)]
        p, _ = self.plan(decl([WEB_DB], environments=True), a)
        self.assertEqual(p.failure.sentence, skill.SHARED_AMBIGUOUS)
        a = everything(database=True)
        a["gcp_environment-describe"] = [
            a["gcp_environment-describe"], res(status="failed", answer=["boom " + SHARED])]
        p, _ = self.plan(decl([WEB_DB], environments=True), a)
        self.assertEqual(p.failure.sentence, skill.SHARED_UNREADABLE)
        self.assertNotIn(SHARED, json.dumps(p.pending))

    def test_instance_missing_needs_the_shared_platform(self):
        a = everything(database=True)
        a["gcp-cloud-sql_database-describe"] = res(status="failed", answer=["x"],
                                                   instanceState=None)
        a["gcp-cloud-sql_instance-describe"] = res(exists=False)
        p, c = self.plan(decl([WEB_DB], environments=True), a)
        self.assertEqual(self.rows(p)["database"], (skill.SHARED_PLATFORM, "none"))
        self.assertEqual(p.status, "pending")
        self.assertEqual(skill.answer_lines(p)[-1], skill.NOTHING_FOR_DATABASE)
        # Any other ending of the instance's read: failed with the database's sentence.
        a["gcp-cloud-sql_database-describe"] = res(status="failed", answer=["Not read."],
                                                   instanceState=None)
        a["gcp-cloud-sql_instance-describe"] = res(exists=True, state="running")
        p, c = self.plan(decl([WEB_DB], environments=True), a)
        self.assertEqual((p.status, p.failure.sentence, p.failure.item),
                         ("failed", "Not read.", "database"))

    def test_user_too_long_skips_12a(self):
        a = everything(database=True)
        long_pid = "aleogr-dev-demo-" + "x" * 14
        a["gcp_environment-describe"]["outputs"]["projectId"] = long_pid
        name = "w" * 16  # demolongname1-<name> has 30 characters, the most allowed
        comp = {"name": name, "stack": "go", "path": "web", "version": "1.27",
                "database": True}
        p, c = self.plan(decl([comp], environments=True, name="demolongname1"), a)
        self.assertEqual(c.skills().count("gcp_environment-describe"), 1)
        self.assertNotIn("env", dict(c.calls)["gcp_deploy-describe"])
        self.assertEqual(self.rows(p)["database"], (skill.TOO_LONG, "fix by hand"))
        n = len("demolongname1-%s@%s.iam" % (name, long_pid))
        self.assertEqual(n, 65)
        self.assertEqual(p.pending, [{"item": "database", "reason": "manual",
                                      "how": skill.TOO_LONG_HOW % (name, n)}])

    def test_repository_copy_notes(self):
        for state, data, envs, dbs in (
                ("equal", None, ["dev"], ["web"]),
                ("not-sent", None, [], []),
                ("missing", None, [], []),
                ("differs", {"repositoryCopy": {"json": True, "value": {
                    "environments": {"dev": {}},
                    "components": [{"name": "b", "database": True}, {"name": "a"}]}}},
                 ["dev"], ["b"]),
                ("behind", {"repositoryCopy": {"json": True, "value": {"name": "x"}}}, [], []),
                ("needs-attention", {"repositoryCopy": {"json": False, "value": None}},
                 None, None),
                ("differs", None, None, None)):
            with self.subTest(state=state, data=data):
                r = skill.Reads({})
                r.decl = skill.Declaration(decl([WEB_DB], environments=True))
                r.checkout = res(state=state, data=data)
                skill.note_repository_copy(r)
                self.assertEqual((r.repository_environments,
                                  r.repository_database_components), (envs, dbs))

    def test_second_read_of_the_protection(self):
        self.write("# aleogr-ci 1 web:web:go:1.27\n", ".github/workflows/ci.yml")
        a = everything()
        a["github_ci-setup"] = res(local="as-declared", inRepository=False)
        a["github_repo-describe"] = [describe(), describe(protection={"state": "protected",
                                                                      "matches": False})]
        p, c = self.plan(decl([WEB]), a)
        describes = [args for n, args in c.calls if n == "github_repo-describe"]
        self.assertEqual(describes, [{"owner": "example-org", "name": "demo", "checks": "ci"},
                                     {"owner": "example-org", "name": "demo"}])
        self.assertEqual(self.rows(p)["protection"], ("differs", "update"))
        self.assertEqual(p.outputs["checks"], "none")

    def test_deploy_list_from_the_local_file(self):
        r = skill.Reads({})
        r.decl = skill.Declaration(decl([WEB, dict(WEB, name="api", path="api")],
                                        environments=True))
        r.local_ci_first = "# aleogr-ci 2 x deploy=dev:web+gone+web project=demo"
        self.assertEqual(skill.deploy_list(r), ["web"])
        r.local_ci_first = "# aleogr-ci 1 x"
        self.assertEqual(skill.deploy_list(r), [])
        r.deploy = res(missing=["web"])
        self.assertEqual(skill.deploy_list(r), ["api"])
        r.decl = skill.Declaration(decl([WEB]))
        self.assertEqual(skill.deploy_list(r), [])


# ---------------------------------------------------------------------------
# The rows


def reads(**kw):
    r = skill.Reads(kw.pop("args", {}))
    r.decl = skill.Declaration(kw.pop("declaration", decl([WEB], environments=True)))
    r.values = {"keep": 5}
    a = everything()
    r.describe = a["github_repo-describe"]
    r.checkout = a["github_checkout-setup"]
    r.pull_request = a["github_pull-request-open"]
    for k, v in kw.items():
        setattr(r, k, v)
    return r


class TestDeclarationRow(unittest.TestCase):
    def row(self, state, folder="ready", changed=(), open_pr=None, protected=False):
        r = reads(checkout=res(state=state),
                  pull_request=res(folder=folder, changed=list(changed),
                                   openPullRequest=open_pr),
                  describe=describe(protection={"state": "protected" if protected
                                                else "unprotected", "matches": True}))
        return skill.declaration_row(r)[1:]

    def test_cases_in_order(self):
        pr = {"number": 7, "url": "u"}
        self.assertEqual(self.row("needs-attention", open_pr=pr),
                         ("proposed in pull request #7", "merge it"))
        self.assertEqual(self.row("equal"), ("in the repository", "none"))
        self.assertEqual(self.row("equal", changed=[".aleogr/project.json"]),
                         ("in the repository", "none"))
        self.assertEqual(self.row("not-sent", folder="other-branch"), ("not sent yet", "send"))
        self.assertEqual(self.row("behind", folder="other-branch"),
                         ("this folder is behind", "update"))
        self.assertEqual(self.row("needs-attention"),
                         ("this folder needs attention", "fix the folder"))
        for state in ("differs", "missing"):
            self.assertEqual(self.row(state, folder="local-commits"),
                             ("this folder needs attention", "fix the folder"))
        self.assertEqual(self.row("not-sent", folder="other-remote", protected=True),
                         ("this folder needs attention", "fix the folder"))
        self.assertEqual(self.row("differs"), ("changed here", "propose"))
        self.assertEqual(self.row("equal", changed=["web/go.mod"]), ("changed here", "propose"))
        self.assertEqual(self.row("missing"), ("not in the repository", "propose"))
        self.assertEqual(self.row("not-sent", protected=True),
                         ("not in the repository", "propose"))

    def test_read_cloud(self):
        r = reads(checkout=res(state="equal"),
                  pull_request=res(folder="ready", changed=["web/db.go"]))
        self.assertFalse(skill.counts_in_repository(r))
        r.args = {"readCloud": "yes"}
        self.assertTrue(skill.counts_in_repository(r))
        r.checkout = res(state="differs")
        self.assertFalse(skill.counts_in_repository(r))


class TestRepositoryRows(unittest.TestCase):
    def test_settings_names_in_order(self):
        o = everything()["github_repo-describe"]
        o["outputs"].update(description="Other", topics=["sample", "aleogr-demo", "x"])
        o["outputs"]["settings"].update(rebase=True, projects=None)
        r = reads(describe=o)
        self.assertEqual(skill.settings_row(r)[1:],
                         ("differs: description, topics, rebase, projects", "update"))
        o["outputs"].update(description="Demo project", topics=["sample", "aleogr-demo"])
        o["outputs"]["settings"].update(rebase=False, projects=False)
        self.assertEqual(skill.settings_row(r)[1:], ("as declared", "none"))

    def test_protection(self):
        def row(state, matches=True, in_repo=None):
            r = reads(describe=describe(protection={"state": state, "matches": matches}))
            if in_repo is not None:
                r.ci = res(local="as-declared", inRepository=in_repo)
            return skill.protection_row(r)[1:]
        self.assertEqual(row("protected"), ("protected", "none"))
        self.assertEqual(row("protected", in_repo=True), ("protected, requires ci", "none"))
        self.assertEqual(row("protected", in_repo=False), ("protected", "none"))
        self.assertEqual(row("protected", False), ("differs", "update"))
        self.assertEqual(row("unprotected"), ("unprotected", "create"))
        self.assertEqual(row("unavailable"), ("not available on this plan", "none"))

    def test_components_and_ci(self):
        def comp(*statuses, go=None):
            r = reads()
            r.go_setup = [({"name": n}, res(status=s)) for n, s in zip("cab", statuses)]
            if go:
                r.go = TC.Check("local", {"name": "go", "command": "go", "state": go,
                                          "fix": None})
            return skill.components_row(r)[1:]
        self.assertEqual(comp("pending", "would-create", "pending"),
                         ("needs attention: b, c", "fix the folder"))
        self.assertEqual(comp("would-create", "unchanged", go="missing"),
                         (skill.NEEDS_GO, "fix by hand"))
        self.assertEqual(comp("would-create", "unchanged", "would-create"),
                         ("to generate: b, c", "generate"))
        self.assertEqual(comp("unchanged", go="ok"), ("as declared", "none"))
        for local, want in (("as-declared", ("as declared", "none")),
                            ("missing", ("missing", "generate")),
                            ("differs", ("differs", "generate"))):
            self.assertEqual(skill.ci_row(reads(ci=res(local=local)))[1:], want)

    def test_repository_missing_rows(self):
        r = reads(declaration=decl([WEB_DB], environments=True, repo=dict(
            BASE["repo"], visibility="public")), describe=res(exists=False))
        r.repository_environments = []
        p = skill.decide(r)
        self.assertEqual(p.items[:7], [
            ("repository", "missing", "create"), ("settings", skill.FOLLOWS_CREATION, "update"),
            ("visibility", skill.FOLLOWS_CREATION, "none"),
            ("declaration", skill.FOLLOWS_CREATION, "send"),
            ("components", skill.FOLLOWS_CREATION, "none"),
            ("ci", skill.FOLLOWS_CREATION, "none"),
            ("protection", skill.FOLLOWS_CREATION, "create")])
        self.assertEqual([x[0] for x in p.items[7:]],
                         ["environment dev", "apis", "registry", "ci identity", "services",
                          "database", "ci secrets"])
        self.assertTrue(all(x[1:] == (skill.FOLLOWS_CREATION, "none") for x in p.items[7:]))
        self.assertEqual((p.status, p.outputs["exposes"], p.resources), ("would-create", True,
                                                                         []))
        self.assertIn(skill.BEFORE_START_LINE, skill.answer_lines(p))

    def test_declaration_being_changed(self):
        r = reads(declaration=decl([WEB], environments=True, repo=dict(
            BASE["repo"], visibility="public")), checkout=res(state="behind"),
            describe=describe(visibility="private"))
        p = skill.decide(r)
        rows = dict((i, (s, a)) for i, s, a in p.items)
        for item in ("settings", "visibility", "protection", "components", "ci",
                     "environment dev", "services", "ci secrets"):
            self.assertEqual(rows[item], (skill.NOT_CHECKED_MERGE, "none"), item)
        self.assertFalse(p.outputs["exposes"])
        r.checkout = res(state="not-sent")
        r.describe = describe(visibility="private", protection={"state": "unprotected"})
        rows = dict((i, (s, a)) for i, s, a in skill.rows(r))
        self.assertEqual(rows["components"], (skill.NOT_CHECKED_SENT, "none"))
        self.assertEqual(rows["visibility"], ("differs", "update"))
        self.assertEqual(rows["apis"], (skill.NOT_CHECKED_MERGE, "none"))


class TestEnvironmentRows(unittest.TestCase):
    def env_reads(self, with_database=False, **over):
        a = everything()
        r = reads(declaration=decl([WEB_DB if with_database else WEB], environments=True))
        r.environment = a["gcp_environment-describe"]
        r.apis = []
        r.registry = a["gcp-artifact-registry_registry-describe"]
        r.identity = a["gcp_ci-identity-setup"]
        r.login = a["gcp_login-describe"]
        r.deploy = a["gcp_deploy-describe"]
        r.secrets = a["github_variables-set"]
        r.ci = a["github_ci-setup"]
        if with_database:
            r.shared = res(exists=True)
            r.shared_project_id = SHARED
            r.database = a["gcp-cloud-sql_database-describe"]
        for k, v in over.items():
            setattr(r, k, v)
        return r

    def rows(self, r):
        return dict((i, (s, a)) for i, s, a in skill.rows(r))

    def test_environment_and_apis(self):
        r = self.env_reads(environment=res(exists=False))
        rows = self.rows(r)
        self.assertEqual(rows["environment dev"], ("missing", "create"))
        self.assertEqual(rows["ci secrets"], (skill.FOLLOWS_ENVIRONMENT, "none"))
        r = self.env_reads(environment=res(exists=True, billingLinked=False))
        self.assertEqual(self.rows(r)["environment dev"], ("billing not linked", "repair"))
        r = self.env_reads(apis=["x", "y"])
        rows = self.rows(r)
        self.assertEqual(rows["apis"], ("to enable: 2", "enable"))
        self.assertEqual(rows["registry"], (skill.FOLLOWS_APIS, "none"))

    def registry(self, **o):
        base = everything()["gcp-artifact-registry_registry-describe"]
        base["outputs"].update(o)
        return base

    def test_registry(self):
        cases = (
            ({"exists": False, "otherRegions": []}, ("missing", "create")),
            ({"exists": False, "otherRegions": ["europe-west1"]},
             ("in another region", "fix by hand")),
            ({"format": "MAVEN", "cleanup": {}}, ("not a Docker repository", "fix by hand")),
            ({"cleanup": {"keep": 4, "deletesTheRest": True, "dryRun": False, "rules": 2}},
             ("cleanup differs", "configure")),
            ({"cleanup": {"keep": 5, "deletesTheRest": False, "dryRun": False, "rules": 2}},
             ("cleanup differs", "configure")),
            ({"cleanup": {"keep": 5, "deletesTheRest": True, "dryRun": True, "rules": 2}},
             ("cleanup differs", "configure")),
            ({"cleanup": {"keep": 5, "deletesTheRest": True, "dryRun": False, "rules": 3}},
             ("cleanup differs", "configure")),
            ({}, ("as declared", "none")))
        for o, want in cases:
            with self.subTest(o=o):
                r = self.env_reads(registry=self.registry(**o))
                self.assertEqual(skill.registry_row(r)[1:], want)

    def test_identity(self):
        account = "demo-ci@%s.iam.gserviceaccount.com" % PID
        mine = ["serviceAccount:" + account]

        def row(status, registry, push=()):
            r = self.env_reads(registry=self.registry(**registry))
            r.registry["outputs"]["push"] = list(push)
            r.identity = res(status=status, account=account, ciVariables=None)
            return skill.identity_row(r)[1:]
        declared, missing = {}, {"exists": False, "otherRegions": []}
        other = {"exists": False, "otherRegions": ["x"]}
        maven = {"format": "MAVEN"}
        differs = {"cleanup": {"keep": 1}}
        self.assertEqual(row("would-create", declared), ("missing", "create"))
        self.assertEqual(row("would-update", missing), ("differs", "update"))
        self.assertEqual(row("unchanged", declared, mine), ("as declared", "none"))
        self.assertEqual(row("unchanged", differs, mine), ("as declared", "none"))
        self.assertEqual(row("unchanged", declared), ("cannot push", "grant"))
        self.assertEqual(row("unchanged", missing, mine), ("cannot push", "grant"))
        self.assertEqual(row("unchanged", other), ("as declared", "none"))
        self.assertEqual(row("unchanged", maven), ("as declared", "none"))
        self.assertEqual(row("would-create", maven), ("missing", "create"))
        self.assertEqual(row("failed", declared), ("needs attention", "fix by hand"))

    def test_identity_how(self):
        r = self.env_reads(identity=res(status="failed", answer=[
            "The pool github is disabled: enable it, then run this again.",
            "The part x could not be read: gcloud failed."], account="a"))
        self.assertEqual(skill.identity_how(r),
                         "The pool github is disabled: enable it; The part x could not be "
                         "read: gcloud failed, then run /aleogr:project-plan again")

    def test_services(self):
        def svc(name, differences=(), placeholder=False, exists=True):
            return {"component": name, "exists": exists, "differences": list(differences),
                    "placeholder": placeholder, "url": None}
        r = self.env_reads(login=res(prepared=False, readable=False))
        self.assertEqual(skill.services_row(r)[1:], ("waits for the login",
                                                     "prepare the login"))
        r = self.env_reads(login=res(status="failed"))
        self.assertEqual(skill.services_row(r)[2], "prepare the login")
        r = self.env_reads(deploy=res(services=[svc("a", exists=False), svc("b", ["cpu"])],
                                      missing=["a"], differing=["b"], waiting=[]))
        self.assertEqual(skill.services_row(r)[1:], ("missing: a", "create"))
        r = self.env_reads(deploy=res(services=[svc("b", ["open"]), svc("c", ["env"], True)],
                                      missing=[], differing=["b", "c"], waiting=[]))
        self.assertEqual(skill.services_row(r)[1:], ("differs: b", "update"))
        r = self.env_reads(deploy=res(services=[svc("c", ["env"], True), svc("a", [], True)],
                                      missing=[], differing=["c"], waiting=["a"]))
        self.assertEqual(skill.services_row(r)[1:],
                         ("waiting for the first deploy: a, c", "none"))
        r = self.env_reads(deploy=res(services=[svc("c", ["env"])], missing=[],
                                      differing=["c"], waiting=[]))
        self.assertEqual(skill.services_row(r)[1:], ("as declared", "none"))

    def db(self, **o):
        return res(**dict({"instanceState": "running", "databaseExists": True, "read": True,
                           "users": [{"user": True, "client": True, "instanceUser": True}]},
                          **o))

    def test_database(self):
        def row(**over):
            return self.rows(self.env_reads(with_database=True, **over))["database"]
        self.assertEqual(row(), ("as declared", "none"))
        self.assertEqual(row(database=self.db(databaseExists=False, users=[
            {"user": False, "client": False, "instanceUser": True}])),
            ("missing: database, user, roles", "create"))
        self.assertEqual(row(database=self.db(instanceState="stopped", databaseExists=None,
                                              read=False, users=[
                                                  {"user": None, "client": True,
                                                   "instanceUser": False}]),
                             deploy=res(services=[{"component": "web", "exists": True,
                                                   "differences": ["env"]}],
                                        missing=[], differing=["web"], waiting=[])),
                         ("missing: roles, settings", "create"))
        self.assertEqual(row(deploy=res(services=[{"component": "web", "exists": True,
                                                   "differences": ["env"]}],
                                        missing=[], differing=["web"], waiting=[])),
                         ("differs: settings", "update"))
        self.assertEqual(row(deploy=res(services=[], missing=["web"], differing=[],
                                        waiting=[])), (skill.FOLLOWS_SERVICES, "none"))
        self.assertEqual(row(registry=self.registry(cleanup={"keep": 1})),
                         (skill.FOLLOWS_SERVICES, "none"))
        self.assertEqual(row(shared=res(exists=False), shared_project_id=None,
                             database=None), (skill.SHARED_PLATFORM, "none"))
        self.assertEqual(row(database=None, instance=res(exists=False)),
                         (skill.SHARED_PLATFORM, "none"))

    def test_database_output_and_lines(self):
        def plan(state, **o):
            r = self.env_reads(with_database=True)
            r.database = self.db(instanceState=state, **o)
            return skill.decide(r)
        p = plan("stopped", users=[{"user": True, "client": False, "instanceUser": True}])
        self.assertEqual(p.outputs["database"], {"name": "demo_dev", "instanceState": "stopped",
                                                 "start": True, "components": ["web"]})
        self.assertIn(skill.START_LINE, skill.answer_lines(p))
        p = plan("stopped")
        self.assertFalse(p.outputs["database"]["start"])
        self.assertIn(skill.NOT_READ_LINE % "stopped", skill.answer_lines(p))
        self.assertEqual(p.status, "unchanged")
        p = plan("unknown")
        self.assertIn(skill.NOT_READ_UNKNOWN_LINE, skill.answer_lines(p))
        p = plan("creating", databaseExists=False)
        self.assertIn(skill.CREATING_LINE, skill.answer_lines(p))
        p = plan("unknown", databaseExists=False)
        self.assertIn(skill.UNKNOWN_LINE, skill.answer_lines(p))
        self.assertNotIn(skill.START_LINE, skill.answer_lines(p))

    def test_secrets(self):
        r = self.env_reads(secrets=res(status="would-update", set=["A", "B"]))
        self.assertEqual(skill.secrets_row(r)[1:], ("missing: A, B", "set"))
        self.assertIn(skill.SECRETS_LINE, skill.answer_lines(skill.decide(r)))
        r = self.env_reads(secrets=None, identity=res(status="would-create", account="a"))
        self.assertEqual(skill.secrets_row(r)[1:], ("follows the ci identity", "none"))
        r = self.env_reads(secrets=None, registry=self.registry(format="MAVEN"))
        self.assertEqual(skill.secrets_row(r)[1:], ("follows the registry", "none"))
        self.assertNotIn(skill.SECRETS_LINE, skill.answer_lines(skill.decide(r)))

    def test_ci_variables_and_urls(self):
        r = self.env_reads(deploy=res(services=[
            {"component": "web", "exists": True, "differences": [], "url": "https://w"}],
            missing=[], differing=[], waiting=[]))
        p = skill.decide(r)
        self.assertEqual(list(p.outputs["ciVariables"]),
                         ["GCP_PROJECT_ID", "GCP_WIF_PROVIDER", "GCP_CI_ACCOUNT",
                          "GCP_IMAGE_PATH"])
        self.assertEqual(p.outputs["urls"], {"web": "https://w"})
        r.registry["outputs"]["imagePath"] = None
        self.assertIsNone(skill.decide(r).outputs["ciVariables"])
        r.deploy = None
        self.assertIsNone(skill.decide(r).outputs["urls"])


class TestStatusAndLastLine(unittest.TestCase):
    def plan(self, items):
        r = reads()
        p = skill.Plan(r, items, skill.status(r, items), {}, [], [])
        return p.status, skill._last_line(p)

    def test_status(self):
        base = [("repository", "exists", "none"), ("settings", "as declared", "none")]
        self.assertEqual(self.plan(base), ("unchanged", skill.NOTHING_TO_DO))
        self.assertEqual(self.plan(base + [("database", skill.SHARED_PLATFORM, "none")]),
                         ("pending", skill.NOTHING_FOR_DATABASE))
        self.assertEqual(self.plan([("repository", "missing", "create")])[0], "would-create")
        status, line = self.plan(base + [("declaration", "x", "merge it"),
                                         ("services", "x", "prepare the login")])
        self.assertEqual(status, "pending")
        self.assertNotIn("nothing to do", line)
        self.assertIn("owner's to do (declaration, services)", line)
        status, line = self.plan(base + [("ci identity", "x", "grant"),
                                         ("registry", "x", "fix by hand")])
        self.assertEqual(status, "would-update")
        self.assertIn("project-apply makes 1 of them, and 1 is the owner's to do (registry)",
                      line)
        for action in skill.WRITE_ACTIONS:
            self.assertEqual(self.plan(base + [("x", "y", action)])[0], "would-update")


class TestCommand(unittest.TestCase):
    def test_run_never_uses_the_plain_runner_and_prints_the_failure_alone(self):
        d = tempfile.mkdtemp()
        old = os.getcwd()
        try:
            os.chdir(d)

            class Ctx(common.Context):
                def run(self, argv, timeout=None):
                    raise AssertionError("project-plan only reads")

                def call(self, *a, **k):
                    raise AssertionError("no declaration: nothing is invoked")
            ctx = Ctx(PLUGIN, ROOT, "project-plan", skill, "plan", {})
            result = skill.run({}, ctx)
        finally:
            os.chdir(old)
            shutil.rmtree(d)
        self.assertEqual(result.lines, [skill.NO_DECLARATION])
        b = result.block
        self.assertEqual((b["action"], b["mode"], b["status"], b["cost"]),
                         ("project-plan", "plan", "failed",
                          {"fixed": False, "notes": "read-only plan"}))
        self.assertEqual(list(b["outputs"]), [
            "project", "repository", "visibility", "exposes", "items", "generate", "checks",
            "changed", "environment", "repositoryEnvironments",
            "repositoryDatabaseComponents", "ciVariables", "urls", "ciDeployComponents",
            "defaultBranch", "database"])


class TestSuites(unittest.TestCase):
    """The versions are checked before the first read: every plugin command this
    orchestrator can call is asked `--suite` right after its arguments are validated."""

    def test_every_command_it_calls_is_in_its_list(self):
        listed = list(skill.SUITE_COMMANDS)
        self.assertEqual(len(listed), len(set(listed)))
        self.assertEqual(called_commands(skill) - set(listed), set())
        self.assertEqual(set(listed) - called_commands(skill), set())

    def test_another_suite_on_the_last_plugin_ends_before_anything(self):
        other = skill.SUITE_COMMANDS[-1]
        result, logs, ran = run_with_other_suite(PLUGIN, "project-plan", skill, {},
                                                 other, declaration=decl([WEB], environments=True))
        sentence = common.VERSION_SENTENCE.format(callee=other, caller="aleogr")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.lines.count(sentence), 1)
        self.assertEqual([l for l in result.lines if l.startswith("|")], [])  # no table
        # Each command asked once for its suite, and nothing invoked or run.
        self.assertEqual(logs, dict((c, ["--suite"]) for c in skill.SUITE_COMMANDS))
        self.assertEqual(ran, [])


if __name__ == "__main__":
    unittest.main()
