"""Unit tests of gcp_deploy-describe's rules, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs. The scenarios deploy-describe-* cover the rest, in the direct mode.
"""

import copy
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_deploy-describe"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

PID = "aleogr-dev-demo-ab12"
CI = "demo-ci@%s.iam.gserviceaccount.com" % PID
ARGS = {"projectId": PID, "project": "demo", "region": "us-central1", "components": "web",
        "maxInstances": "2", "cpu": "1", "memory": "512Mi", "ciAccount": CI}
AGENT = "serviceAccount:service-123456789012@gcp-sa-iap.iam.gserviceaccount.com"

SERVICE = {
    "metadata": {
        "labels": {"aleogr-project": "demo", "aleogr-environment": "dev",
                   "aleogr-component": "web"},
        "annotations": {"run.googleapis.com/maxScale": "2",
                        "run.googleapis.com/iap-enabled": "true"},
    },
    "spec": {"template": {
        "metadata": {"annotations": {"run.googleapis.com/cpu-throttling": "true"}},
        "spec": {
            "serviceAccountName": "demo-web@%s.iam.gserviceaccount.com" % PID,
            "containers": [{"image": "us-docker.pkg.dev/cloudrun/container/hello",
                            "resources": {"limits": {"cpu": "1", "memory": "512Mi"}},
                            "env": [{"name": "A", "value": "1"}]}],
        }}},
    "status": {"url": "https://demo-web.example.run.app"},
}
POLICY = {"bindings": [
    {"role": "roles/run.developer", "members": ["serviceAccount:" + CI]},
    {"role": "roles/run.invoker", "members": [AGENT]},
]}
ACCOUNT_POLICY = {"bindings": [
    {"role": "roles/iam.serviceAccountUser", "members": ["serviceAccount:" + CI]}]}


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


class FakeContext(common.Context):
    def __init__(self, answers, args):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill, "plan", args)
        self.answers = answers
        self.calls = []

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv[1:])
        self.calls.append(line)
        best = None
        for prefix in self.answers:
            if line.startswith(prefix) and (best is None or len(prefix) > len(best)):
                best = prefix
        return self.answers[best] if best is not None else common.Completed(0, "", "")


def answers(service=None, policy=None, account_policy=None, login_policy=None):
    return {
        "projects describe": ok("123456789012\n"),
        "run services describe": ok(SERVICE if service is None else service),
        "run services get-iam-policy": ok(POLICY if policy is None else policy),
        "iam service-accounts get-iam-policy":
            account_policy if isinstance(account_policy, common.Completed)
            else ok(ACCOUNT_POLICY if account_policy is None else account_policy),
        "iap web get-iam-policy": ok({} if login_policy is None else login_policy),
    }


def run_skill(args=None, **kw):
    a = dict(ARGS if args is None else args)
    ctx = FakeContext(answers(**kw), a)
    return skill.run(a, ctx), ctx


def changed(path, value):
    """SERVICE with the value at `path` (keys) replaced, or deleted when value is None."""
    s = copy.deepcopy(SERVICE)
    obj = s
    for k in path[:-1]:
        obj = obj[k]
    if value is None:
        obj.pop(path[-1], None)
    else:
        obj[path[-1]] = value
    return s


ANN = ("metadata", "annotations")
TANN = ("spec", "template", "metadata", "annotations")
CONTAINER = ("spec", "template", "spec", "containers")


class TestValidation(unittest.TestCase):
    def check(self, extra, sentences, drop=()):
        args = dict(ARGS)
        args.update(extra)
        for k in drop:
            args.pop(k)
        ctx = FakeContext({}, args)
        r = skill.run(args, ctx)
        self.assertEqual((r.status, ctx.calls, r.block["resources"]), ("failed", [], []))
        self.assertEqual(r.block["outputs"],
                         {"services": [], "missing": [], "differing": [], "waiting": []})
        self.assertEqual(r.lines, sentences)

    def test_missing_in_table_order(self):
        self.check({}, ["projectId is missing.", "memory is missing."],
                   drop=("memory", "projectId"))

    def test_value_rules(self):
        self.check({"environment": "qa", "maxInstances": "02", "cpu": "4", "memory": "1G",
                    "region": "us_central1"},
                   ["environment must be dev, hom or prd.",
                    "region is not a Google Cloud region name (such as us-central1).",
                    "maxInstances must be a whole number from 1 to 10.",
                    "cpu must be 1 or 2.",
                    "memory must be 512Mi, 1Gi or 2Gi."])
        self.check({"maxInstances": "11"}, ["maxInstances must be a whole number from 1 to 10."])

    def test_project_and_components(self):
        self.check({"project": "demo-"}, [
            "project must have 1 to 14 lowercase letters, digits and hyphens, starting with "
            "a letter and not ending with a hyphen."])
        self.check({"project": "a", "components": "web,web,api"}, [
            "component web is given twice.",
            "a-web has 5 characters: a service's name, which is also its account's, must "
            "have 6 to 30.",
            "a-api has 5 characters: a service's name, which is also its account's, must "
            "have 6 to 30."])

    def test_ci_account(self):
        sentence = ("ciAccount must be a service account of the project %s "
                    "(<id>@%s.iam.gserviceaccount.com)." % (PID, PID))
        for bad in ("serviceAccount:" + CI, "demo-ci@other-project-1.iam.gserviceaccount.com",
                    CI.upper(), "ci@%s.iam.gserviceaccount.com" % PID):
            with self.subTest(ciAccount=bad):
                self.check({"ciAccount": bad}, [sentence])

    def test_env_rules(self):
        self.check({"env": "web:A=1;;nocolon;web:a=1;api:B=2;web:C=has space;web:A=2"}, [
            "env entry 2 must be <component>:<NAME>=<value>.",
            "env entry 3 must be <component>:<NAME>=<value>.",
            "env entry 4 has a name that is not 1 to 64 characters of A-Z, 0-9 and _, "
            "starting with a letter.",
            "env setting B names api, which is not one of components.",
            "env setting web:C must have a value of 1 to 200 characters of a-z, A-Z, 0-9, -, "
            "_, ., : and @.",
            "env setting web:A is given twice."])

    def test_env_in_double_quotes(self):
        r, _ = run_skill(dict(ARGS, env='"web:A=1"'))
        self.assertEqual(r.block["outputs"]["services"][0]["differences"], [])


class TestDifferences(unittest.TestCase):
    def words(self, **kw):
        r, _ = run_skill(**kw)
        self.assertEqual(r.status, "unchanged")
        return r.block["outputs"]["services"][0]["differences"]

    def test_as_declared_and_placeholder(self):
        r, ctx = run_skill()
        o = r.block["outputs"]
        self.assertEqual((o["services"][0]["asDeclared"], o["waiting"], o["differing"]),
                         (True, ["web"], []))
        self.assertEqual([c.split(" ")[0:3] for c in ctx.calls],
                         [["projects", "describe", PID], ["run", "services", "describe"],
                          ["run", "services", "get-iam-policy"],
                          ["iam", "service-accounts", "get-iam-policy"],
                          ["iap", "web", "get-iam-policy"]])

    def test_scaling(self):
        for path, value in ((ANN + ("run.googleapis.com/maxScale",), None),
                            (ANN + ("run.googleapis.com/minScale",), "1"),
                            (ANN + ("run.googleapis.com/scalingMode",), "manual"),
                            (TANN + ("autoscaling.knative.dev/minScale",), "2")):
            with self.subTest(path=path[-1]):
                self.assertEqual(self.words(service=changed(path, value)), ["scaling"])
        self.assertEqual(self.words(service=changed(ANN + ("run.googleapis.com/minScale",),
                                                    "0")), [])

    def test_size(self):
        def limits(cpu, memory):
            s = copy.deepcopy(SERVICE)
            s["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"] = {
                "cpu": cpu, "memory": memory}
            return s
        r, _ = run_skill(dict(ARGS, cpu="2", memory="1Gi"), service=limits("2000m", "1024Mi"))
        self.assertEqual(r.block["outputs"]["services"][0]["differences"], [])
        self.assertEqual(self.words(service=limits("2", "512Mi")), ["size"])
        self.assertEqual(self.words(service=changed(TANN + ("run.googleapis.com/cpu-throttling",),
                                                    "false")), ["size"])
        self.assertEqual(self.words(service=changed(TANN + ("run.googleapis.com/cpu-throttling",),
                                                    None)), [])

    def test_public_open_login(self):
        self.assertEqual(self.words(service=changed(
            ANN + ("run.googleapis.com/invoker-iam-disabled",), "true")), ["public"])
        policy = copy.deepcopy(POLICY)
        policy["bindings"].append({"role": "roles/viewer", "members": ["allAuthenticatedUsers"]})
        self.assertEqual(self.words(policy=policy), ["public"])
        self.assertEqual(self.words(login_policy={"bindings": [
            {"role": "roles/iap.httpsResourceAccessor", "members": ["allUsers"],
             "condition": {"expression": "true"}}]}), ["open"])
        self.assertEqual(self.words(service=changed(ANN + ("run.googleapis.com/iap-enabled",),
                                                    "True")), ["login"])

    def test_conditioned_bindings_do_not_count(self):
        policy = {"bindings": [dict(b, condition={"expression": "x"})
                               for b in POLICY["bindings"]]}
        self.assertEqual(self.words(policy=policy), ["agent", "ci"])

    def test_missing_account(self):
        missing = common.Completed(1, "", "ERROR: NOT_FOUND: ... does not exist.")
        self.assertEqual(self.words(account_policy=missing), ["account", "ci"])

    def test_labels_without_environment(self):
        for env, want in (("prd", []), ("qa", ["labels"])):
            s = changed(("metadata", "labels", "aleogr-environment"), env)
            self.assertEqual(self.words(service=s), want)
        s = changed(("metadata", "labels", "aleogr-component"), "api")
        self.assertEqual(self.words(service=s), ["labels"])

    def test_env_value_from_is_another_value(self):
        s = copy.deepcopy(SERVICE)
        s["spec"]["template"]["spec"]["containers"][0]["env"] = [
            {"name": "A", "valueFrom": {"secretKeyRef": {"name": "x"}}}]
        r, _ = run_skill(dict(ARGS, env="web:A=1"), service=s)
        self.assertEqual(r.block["outputs"]["services"][0]["differences"], ["env"])
        self.assertIn("Its setting A holds another value.", r.lines)
        self.assertNotIn("1", " ".join(r.lines).replace("123456789012", ""))

    def test_placeholder_forms(self):
        for image, want in (("us-docker.pkg.dev/cloudrun/container/hello:latest", True),
                            ("us-docker.pkg.dev/cloudrun/container/hello@sha256:abc123", True),
                            ("us-docker.pkg.dev/cloudrun/container/hello2", False),
                            ("example.com/us-docker.pkg.dev/cloudrun/container/hello", False)):
            with self.subTest(image=image):
                s = copy.deepcopy(SERVICE)
                s["spec"]["template"]["spec"]["containers"][0]["image"] = image
                r, _ = run_skill(service=s)
                self.assertEqual(r.block["outputs"]["services"][0]["placeholder"], want)
                self.assertEqual(r.block["outputs"]["waiting"], ["web"] if want else [])


class TestFailures(unittest.TestCase):
    def test_project_number(self):
        for c in (common.Completed(1, "", "ERROR"), common.Completed(0, "", "")):
            a = answers()
            a["projects describe"] = c
            ctx = FakeContext(a, dict(ARGS))
            r = skill.run(dict(ARGS), ctx)
            self.assertEqual((r.status, r.lines, len(ctx.calls)),
                             ("failed", [skill.PROJECT_UNREADABLE % PID], 1))

    def test_a_refused_access_read_is_failed(self):
        refused = common.Completed(1, "", "ERROR: PERMISSION_DENIED")
        for read in ("run services get-iam-policy", "iam service-accounts get-iam-policy",
                     "iap web get-iam-policy"):
            with self.subTest(read=read):
                a = answers()
                a[read] = refused
                ctx = FakeContext(a, dict(ARGS))
                r = skill.run(dict(ARGS), ctx)
                self.assertEqual((r.status, r.lines, r.block["resources"]),
                                 ("failed", [skill.ACCESS_UNREADABLE % ("demo-web", PID)], []))

    def test_order_with_two_components(self):
        a = answers()
        a["run services describe demo-api"] = common.Completed(1, "", "Cannot find service")
        args = dict(ARGS, components="web,api")
        ctx = FakeContext(a, args)
        r = skill.run(args, ctx)
        self.assertEqual([c.split(" --")[0] for c in ctx.calls[1:4]],
                         ["run services describe demo-web", "run services describe demo-api",
                          "run services get-iam-policy demo-web"])
        self.assertEqual(len(ctx.calls), 6)
        self.assertEqual(r.block["outputs"]["missing"], ["api"])
        self.assertEqual([x["id"] for x in r.block["resources"]],
                         ["%s/us-central1/demo-web" % PID])

    def test_no_email_in_the_block(self):
        r, _ = run_skill()
        self.assertNotIn("@", common.render_block(r.block))


if __name__ == "__main__":
    unittest.main()
