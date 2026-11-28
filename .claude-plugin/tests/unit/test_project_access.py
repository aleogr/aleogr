"""Unit tests of project-access: "Validate first" in its order and with its sentences, the
declaration's reads, every gate before the call it gates (absent, another value, and the
gated call not made), the exact arguments of each invocation, the answer and the block
(which never holds the person's address). The invocations are answered by a stand-in;
no command and no provider runs. The scenarios project-access-* cover the rest in the
direct mode.
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

PLUGIN = "aleogr"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, "project-access")
grant_module = load_skill("aleogr-cloud-gcp", "gcp_access-grant")

PID = "aleogr-dev-demo-ab12"
PERSON = "demo-user@example.com"

DECL = {
    "version": 1, "name": "demo",
    "repo": {"provider": "github", "owner": "example-org", "name": "demo",
             "visibility": "private", "description": "Demo project",
             "settings": {"mergeCommit": True, "squash": True, "rebase": False,
                          "deleteBranchOnMerge": True, "issues": True, "wiki": False,
                          "projects": False}},
    "components": [{"name": "web", "stack": "go", "path": "web", "version": "1.27"},
                   {"name": "api", "stack": "go", "path": "services/api", "version": "1.27"}],
    "cloud": {"provider": "gcp", "region": "us-central1"},
    "environments": {"dev": {}},
}


def res(status="unchanged", answer=(), pending=(), **outputs):
    return {"aleogr-result": 1, "status": status, "outputs": outputs,
            "answer": list(answer), "pending": list(pending)}


def exists(project_id=PID):
    return res("unchanged", exists=True, projectId=project_id)


def granted(names=("api", "web"), already=(), open_=(), pending=()):
    return res("updated" if names else "unchanged", pending=pending, granted=list(names),
               already=list(already), people=None, open=list(open_))


class FakeCalls(object):
    """Answers describe and grant from canned results, per environment, and records
    every invocation as (skill, args)."""

    def __init__(self, describe=None, grant=None):
        self.describe_answers = describe or {}
        self.grant_answers = grant or {}
        self.made = []

    def describe(self, args):
        self.made.append(("describe", dict(args)))
        return self.describe_answers.get(args["environment"], exists())

    def grant(self, args):
        self.made.append(("grant", dict(args)))
        env = [a for s, a in self.made if s == "describe"][-1]["environment"]
        return self.grant_answers.get(env, granted())

    def skills(self):
        return [s for s, _ in self.made]


def context(args):
    return common.Context(PLUGIN, ROOT, "project-access", skill, "apply", args)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="aleogr-test-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, data):
        os.makedirs(os.path.join(self.dir, ".aleogr"), exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data)
        with open(os.path.join(self.dir, ".aleogr", "project.json"), "w") as f:
            f.write(text)

    def run_skill(self, args, calls=None, data=DECL):
        if data is not None:
            self.write(data)
        calls = calls if calls is not None else FakeCalls()
        result = skill.run(dict(args), context(dict(args)), calls=calls, cwd=self.dir)
        return result, calls

    def assertFailed(self, result, sentence):
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.lines, [sentence])


class TestValidateFirst(Base):
    def check(self, args, sentence):
        result, calls = self.run_skill(args, data=None)  # no file: none is read
        self.assertFailed(result, sentence)
        self.assertEqual(calls.made, [])
        self.assertEqual(result.block["pending"][0]["item"], "arguments")
        self.assertEqual(result.block["outputs"], {"project": None, "environments": []})
        self.assertNotIn("@", common.render_block(result.block))

    def test_neither(self):
        self.check({}, "person is missing (or give list=yes).")

    def test_both(self):
        self.check({"person": PERSON, "list": "yes"},
                   "Give either person or list=yes, not both.")

    def test_other_argument(self):
        for k in ("mode", "confirm", "projectId", "run"):
            self.check({"person": PERSON, k: "x"},
                       "%s is not an argument of project-access: give person=<e-mail> or "
                       "list=yes." % k)

    def test_order_of_the_first_rule(self):
        # neither before an unknown argument; both before an unknown argument; an unknown
        # argument before the rule on person or on list.
        self.check({"mode": "apply"}, "person is missing (or give list=yes).")
        self.check({"person": "x", "list": "no", "mode": "apply"},
                   "Give either person or list=yes, not both.")
        self.check({"person": "allUsers", "mode": "apply"},
                   "mode is not an argument of project-access: give person=<e-mail> or "
                   "list=yes.")
        self.check({"list": "no", "mode": "apply"},
                   "mode is not an argument of project-access: give person=<e-mail> or "
                   "list=yes.")

    def test_person_rule(self):
        for value in ("allUsers", "allAuthenticatedUsers", "group:team@example.com",
                      "user:a@example.com", "demo-user", "a@b", "a@@example.com",
                      "a@b@example.com", "a b@example.com", "a,b@example.com",
                      '"a"@example.com', "a'b@example.com", "@example.com",
                      "x" * 65 + "@example.com", "a@-example.com", "a@example-.com",
                      "a@example.c0m", "a@example..com", "sa@demo.iam.gserviceaccount.com",
                      "sa@GSERVICEACCOUNT.COM", "a!b@example.com", "", "a@" + "x" * 64 + ".com"):
            self.check({"person": value}, skill.PERSON_RULE)

    def test_person_rule_sentence_word_for_word(self):
        self.assertEqual(skill.PERSON_RULE,
                         "person must be the e-mail address of one person (such as "
                         "name@example.com): not a group, a domain, a service account or "
                         "everyone.")

    def test_list_rule(self):
        for value in ("no", "true", "", "YES"):
            self.check({"list": value}, "list must be yes.")

    def test_the_rule_is_gcp_access_grants(self):
        samples = ["a@example.com", "A.b_c+d-e@sub.example.org", "x" * 64 + "@example.com",
                   "x" * 65 + "@example.com", "a@example", "a@e.x1", "a@e-.com",
                   "allUsers", "a:b@example.com", "a@x.gserviceaccount.com",
                   "a@gserviceaccount.com.example.com", "a@" + "y" * 63 + ".com",
                   "a@" + "y" * 64 + ".com", "a@b.c", "a@1.com", "a b", "a,b", "a@b@c.com"]
        for v in samples:
            self.assertEqual(skill.person_ok(v), grant_module.person_ok(v), v)

    def test_valid_arguments_pass(self):
        self.assertIsNone(skill.validate_args({"person": PERSON}))
        self.assertIsNone(skill.validate_args({"list": "yes"}))


class TestDeclaration(Base):
    def check(self, data, sentence, project=None):
        result, calls = self.run_skill({"person": PERSON}, data=data)
        self.assertFailed(result, sentence)
        self.assertEqual(calls.made, [])
        self.assertEqual(result.block["outputs"], {"project": project, "environments": []})
        self.assertEqual(result.block["pending"][0]["item"], "declaration")
        return result

    def test_missing(self):
        self.check(None, "There is no .aleogr/project.json in this folder: declare the project "
                         "first with /aleogr:project-declare.")

    def test_unreadable(self):
        os.makedirs(os.path.join(self.dir, ".aleogr", "project.json"))
        self.check(None, skill.UNREADABLE)

    def test_not_json(self):
        for text in ("{", "{\"name\": NaN}", ""):
            self.check(text, skill.NOT_JSON)

    def test_no_environment(self):
        for envs in (None, {}, []):
            d = dict(DECL)
            if envs is None:
                del d["environments"]
            else:
                d["environments"] = envs
            self.check(d, "The declaration has no environment: there is no service to let "
                          "anyone in to.", project="demo")

    def test_no_component(self):
        for comps in (None, []):
            d = dict(DECL)
            if comps is None:
                del d["components"]
            else:
                d["components"] = comps
            self.check(d, "The declaration has no component: there is no service to let "
                          "anyone in to.", project="demo")

    def test_environment_checked_before_component(self):
        d = dict(DECL, components=[])
        del d["environments"]
        self.check(d, skill.NO_ENVIRONMENT, project="demo")

    def test_keys_it_reads_of_another_kind(self):
        for change in ({"name": 3}, {"cloud": {"provider": "gcp"}}, {"environments": "dev"},
                       {"components": [{"stack": "go"}]}, {"components": "api"}):
            d = dict(DECL, **change)
            self.check(d, skill.NOT_VALID, project="demo" if "name" not in change else None)
        self.check([1], skill.NOT_VALID)

    def test_other_rules_are_the_plans(self):
        # A declaration the plan would refuse (no repo, version 2) is still read: this
        # skill reads only its keys.
        d = dict(DECL, version=2)
        del d["repo"]
        result, calls = self.run_skill({"person": PERSON}, data=d)
        self.assertEqual(result.status, "updated")

    def test_values(self):
        self.write(DECL)
        self.assertEqual(skill.read_declaration(self.dir),
                         ("demo", "us-central1", ["api", "web"], ["dev"]))


class TestInvocations(Base):
    def test_describe_then_grant_with_exactly_the_arguments(self):
        result, calls = self.run_skill({"person": PERSON})
        self.assertEqual(calls.made, [
            ("describe", {"project": "demo", "environment": "dev"}),
            ("grant", {"projectId": PID, "project": "demo", "region": "us-central1",
                       "components": "api,web", "person": PERSON, "mode": "apply"})])
        self.assertEqual(list(calls.made[1][1]),
                         ["projectId", "project", "region", "components", "person", "mode"])

    def test_list_in_place_of_person(self):
        result, calls = self.run_skill({"list": "yes"})
        self.assertEqual(calls.made[1], (
            "grant", {"projectId": PID, "project": "demo", "region": "us-central1",
                      "components": "api,web", "list": "yes", "mode": "apply"}))
        self.assertEqual(list(calls.made[1][1]),
                         ["projectId", "project", "region", "components", "list", "mode"])

    def test_describe_is_called_read_only(self):
        seen = []

        def fake(command, skill_name, args=None, timeout=None, read_only=False, caller=None):
            seen.append((command, skill_name, dict(args), read_only, caller))
            return exists()
        saved = skill.common.call_plugin
        skill.common.call_plugin = fake
        try:
            skill.Calls(context({})).describe({"project": "demo", "environment": "dev"})
        finally:
            skill.common.call_plugin = saved
        self.assertEqual(seen, [("aleogr-cloud-gcp", "gcp_environment-describe",
                                 {"project": "demo", "environment": "dev"}, True, "aleogr")])

    def test_grant_goes_through_ctx_call(self):
        seen = []

        class Ctx(object):
            plugin = "aleogr"

            def call(self, command, skill_name, args=None, timeout=None):
                seen.append((command, skill_name, args))
                return granted()
        skill.Calls(Ctx()).grant({"a": "b"})
        self.assertEqual(seen, [("aleogr-cloud-gcp", "gcp_access-grant", {"a": "b"})])

    def test_describe_of_another_suite_ends_the_run(self):
        def fake(*a, **kw):
            return {"status": "failed", "callError": "version", "answer": ["V."]}
        saved = skill.common.call_plugin
        skill.common.call_plugin = fake
        try:
            with self.assertRaises(common.PluginVersion):
                skill.Calls(context({})).describe({"project": "demo", "environment": "dev"})
        finally:
            skill.common.call_plugin = saved

    def test_module_runs_and_writes_nothing_itself(self):
        with open(skill.__file__) as f:
            text = f.read()
        for word in ("ctx.read(", "ctx.write", "ctx.run(", "subprocess", "write_file",
                     "open(", "ctx.wait", "sleep"):
            self.assertNotIn(word, text)
        self.assertFalse(skill.WRITES)
        self.assertFalse(getattr(skill, "CONTINUES", False))
        self.assertEqual(skill.DEFAULT_MODE, "apply")
        self.assertEqual(skill.RESULT_MODE, "apply")


class TestGates(Base):
    """The grant is invoked only for an environment whose GCP project exists: its gate is
    outputs.exists true of gcp_environment-describe, which did not fail."""

    def test_describe_failed(self):
        calls = FakeCalls(describe={"dev": res("failed", answer=["x."], exists=None)})
        result, calls = self.run_skill({"person": PERSON}, calls)
        self.assertFailed(result, "The GCP project of dev could not be read; nothing was "
                                  "changed. Run /aleogr:project-plan to see why.")
        self.assertEqual(calls.skills(), ["describe"])
        self.assertEqual(result.block["pending"],
                         [{"item": "environment dev", "reason": "manual",
                           "how": "run /aleogr:project-plan to see why"}])
        self.assertEqual(result.block["outputs"], {"project": "demo", "environments": []})

    def test_exists_absent_or_another_value(self):
        for value in (False, None, "true", 1):
            o = {"projectId": PID}
            if value is not None:
                o["exists"] = value
            calls = FakeCalls(describe={"dev": res("unchanged", **o)})
            result, calls = self.run_skill({"person": PERSON}, calls)
            self.assertFailed(result, "The GCP project of dev does not exist yet: run "
                                      "/aleogr:project-apply confirm=yes first.")
            self.assertEqual(calls.skills(), ["describe"], value)

    def test_no_project_id(self):
        calls = FakeCalls(describe={"dev": res("unchanged", exists=True, projectId=None)})
        result, calls = self.run_skill({"person": PERSON}, calls)
        self.assertEqual(result.status, "failed")
        self.assertEqual(calls.skills(), ["describe"])

    def test_list_needs_the_project_too(self):
        calls = FakeCalls(describe={"dev": res("unchanged", exists=False)})
        result, calls = self.run_skill({"list": "yes"}, calls)
        self.assertEqual(result.status, "failed")
        self.assertEqual(calls.skills(), ["describe"])

    def test_a_failed_environment_does_not_stop_the_others(self):
        d = dict(DECL, environments={"dev": {}, "hom": {}})
        calls = FakeCalls(grant={"dev": res("failed", answer=["Broken."], granted=[],
                                            already=[], people=None, open=[])})
        result, calls = self.run_skill({"person": PERSON}, calls, data=d)
        self.assertEqual(calls.skills(), ["describe", "grant", "describe", "grant"])
        self.assertEqual(result.status, "updated")
        self.assertEqual(result.lines[:3], ["dev: failed", "hom: updated", "Broken."])

    def test_a_later_describe_failure_stops(self):
        d = dict(DECL, environments={"dev": {}, "hom": {}})
        calls = FakeCalls(describe={"hom": res("failed")})
        result, calls = self.run_skill({"person": PERSON}, calls, data=d)
        self.assertEqual(calls.skills(), ["describe", "grant", "describe"])
        self.assertFailed(result, skill.NOT_READ % "hom")
        self.assertEqual([e["name"] for e in result.block["outputs"]["environments"]], ["dev"])


class TestAnswer(Base):
    def block_text(self, result):
        return common.render_block(result.block)

    def test_grant(self):
        remove = grant_module.open_remove_command(
            "demo-web", {"region": "us-central1", "projectId": PID}, "allUsers",
            "roles/iap.httpsResourceAccessor")
        calls = FakeCalls(grant={"dev": granted(
            ["web"], already=["api"], open_=["web"],
            pending=[{"item": "access", "reason": "manual", "how": remove}])})
        result, _ = self.run_skill({"person": PERSON}, calls)
        self.assertEqual(result.status, "updated")
        self.assertEqual(result.lines, [
            "dev: updated",
            "%s already had access to the service demo-api in dev." % PERSON,
            "%s was let in to the service demo-web in dev by this run." % PERSON,
            "%s opens each service's address and signs in with that Google account." % PERSON,
            "The addresses are in the answer of /aleogr:project-plan.",
            "The address must be a person's Google account: a group's address is not "
            "supported and would let nobody in.",
            "Anyone on the internet who signs in with any Google account gets through the "
            "login of the service demo-web in dev.",
            "To close it, the owner runs:",
            remove,
            "/aleogr:project-apply confirm=yes also closes it.",
            "To undo a grant, the owner runs by hand:",
            skill.UNDO_COMMAND % ("demo-api", "us-central1", PID),
            skill.UNDO_COMMAND % ("demo-web", "us-central1", PID)])
        self.assertEqual(result.block["outputs"]["environments"], [
            {"name": "dev", "status": "updated", "granted": ["web"], "already": ["api"],
             "people": None, "open": ["web"]}])
        self.assertEqual(result.block["pending"],
                         [{"item": "access", "reason": "manual", "how": remove}])
        self.assertEqual(result.block["cost"], skill.COST)
        self.assertEqual(result.block["mode"], "apply")
        self.assertEqual(result.block["family"], "orchestrator")
        self.assertNotIn(PERSON, self.block_text(result))

    def test_undo_command_as_the_skill_writes_it(self):
        self.assertEqual(skill.UNDO_COMMAND % ("demo-api", "us-central1", PID),
                         'gcloud iap web remove-iam-policy-binding --resource-type=cloud-run '
                         '--service=demo-api --region=us-central1 --project=%s '
                         '--member="user:<e-mail>" --role="roles/iap.httpsResourceAccessor" '
                         '--condition=None' % PID)

    def test_already_everywhere_is_unchanged(self):
        calls = FakeCalls(grant={"dev": granted([], already=["api", "web"])})
        result, _ = self.run_skill({"person": PERSON}, calls)
        self.assertEqual(result.status, "unchanged")
        self.assertEqual(result.lines[0], "dev: unchanged")

    def test_could_not_be_let_in(self):
        how = grant_module.pending_how("web", {"projectId": PID, "project": "demo",
                                               "region": "us-central1"})
        calls = FakeCalls(grant={"dev": granted(
            ["api"], pending=[{"item": "web: access", "reason": "x", "how": how}])})
        result, _ = self.run_skill({"person": PERSON}, calls)
        self.assertIn("%s could not be let in to the service demo-web in dev." % PERSON,
                      result.lines)
        self.assertEqual(result.block["pending"],
                         [{"item": "web: access", "reason": "x", "how": how}])
        self.assertNotIn(PERSON, self.block_text(result))

    def test_service_missing(self):
        sentence = grant_module.SERVICE_MISSING % ("web", "demo-web", "us-central1")
        calls = FakeCalls(grant={"dev": res("failed", answer=[sentence], granted=[],
                                            already=[], people=None, open=[])})
        result, _ = self.run_skill({"person": PERSON}, calls)
        self.assertFailed(result, "The service of web does not exist yet in dev: run "
                                  "/aleogr:project-apply confirm=yes first, then this skill "
                                  "again.")
        self.assertEqual(result.block["pending"], [
            {"item": "web: service", "reason": "manual",
             "how": "run /aleogr:project-apply confirm=yes first, then /aleogr:project-access "
                    "again"}])
        self.assertNotIn("gcp_", "\n".join(result.lines) + self.block_text(result))

    def test_failed_grant_relays_its_cause_without_the_person(self):
        answer = [grant_module.OPEN_SENTENCE % "demo-web", "gcloud iap web remove ...",
                  grant_module.COST_LINE, grant_module.GRANT_FAILED % "demo-api",
                  "%s was not let in to the service demo-api." % PERSON,
                  "%s opens each service's address and signs in with that Google account."
                  % PERSON, grant_module.GROUP_SENTENCE]
        calls = FakeCalls(grant={"dev": res("failed", answer=answer, granted=[], already=[],
                                            people=None, open=["web"])})
        result, _ = self.run_skill({"person": PERSON}, calls)
        self.assertFailed(result, grant_module.GRANT_FAILED % "demo-api")
        self.assertEqual(result.block["pending"][-1],
                         {"item": "environment dev", "reason": "manual",
                          "how": skill._how(grant_module.GRANT_FAILED % "demo-api")})
        self.assertNotIn(PERSON, self.block_text(result))

    def test_failed_grant_with_no_answer(self):
        calls = FakeCalls(grant={"dev": {"status": "failed"}})
        result, _ = self.run_skill({"person": PERSON}, calls)
        self.assertFailed(result, "gcp_access-grant ended failed in dev.")

    def test_list(self):
        answer = [grant_module.OPEN_SENTENCE % "demo-web", "gcloud iap web remove x",
                  "The service demo-api lets in 1 person.", "user:owner@example.com",
                  "The service demo-web lets in 2 people.", "user:owner@example.com",
                  "Other members: allAuthenticatedUsers.",
                  "To remove a person from the service demo-api, the owner runs by hand:",
                  "gcloud iap web remove-iam-policy-binding x", "This run changed nothing."]
        calls = FakeCalls(grant={"dev": res("unchanged", answer=answer, granted=[],
                                            already=[], people={"api": 1, "web": 2},
                                            open=["web"])})
        result, _ = self.run_skill({"list": "yes"}, calls)
        self.assertEqual(result.status, "unchanged")
        self.assertEqual(result.lines[:7], [
            "dev: unchanged", "The service demo-api lets in 1 person.",
            "user:owner@example.com", "The service demo-web lets in 2 people.",
            "user:owner@example.com", "Other members: allAuthenticatedUsers.",
            "Anyone on the internet who signs in with any Google account gets through the "
            "login of the service demo-web in dev."])
        self.assertNotIn(skill.UNDO_LEAD, result.lines)
        self.assertNotIn(skill.ADDRESSES, result.lines)
        self.assertEqual(result.block["outputs"]["environments"][0]["people"],
                         {"api": 1, "web": 2})

    def test_on_abort_names_no_person(self):
        ctx = context({"person": PERSON})
        self.write(DECL)
        skill.run({"person": PERSON}, ctx, calls=FakeCalls(), cwd=self.dir)
        self.assertEqual(ctx.abort_lines, ["dev: updated"])


if __name__ == "__main__":
    unittest.main()
