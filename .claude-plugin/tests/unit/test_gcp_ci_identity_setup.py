"""Unit tests of gcp_ci-identity-setup's mode=plan, the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict, so no provider
command runs. The scenarios ci-identity-* of mode=plan cover the rest, in the direct mode;
those of mode=apply are not converted in step 1.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_ci-identity-setup"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

PID = "aleogr-dev-demo-ab12"
ARGS = {"projectId": PID, "project": "demo", "repository": "example-org/example-repo",
        "repositoryId": "7654321", "ownerId": "2345678", "branch": "main",
        "workflow": "aleogr/aleogr/.github/workflows/deploy-cloud-run.yml", "mode": "plan"}
N = skill.names(ARGS, "123456789012")
PROVIDER = {"state": "ACTIVE", "attributeCondition": N["condition"],
            "oidc": {"issuerUri": skill.ISSUER}, "attributeMapping": dict(skill.MAPPING)}
POLICY = {"bindings": [{"role": "roles/iam.workloadIdentityUser", "members": [N["member"]]}]}
MISSING = common.Completed(1, "", "ERROR: (gcloud) NOT_FOUND: Resource not found.")


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def answers(**over):
    a = {
        "projects describe": ok("123456789012\n"),
        "iam service-accounts describe": ok(N["account"] + "\n"),
        "iam workload-identity-pools describe": ok({"state": "ACTIVE"}),
        "iam workload-identity-pools providers list": ok(N["provider"] + "\n"),
        "iam workload-identity-pools providers describe": ok(PROVIDER),
        "iam service-accounts get-iam-policy": ok(POLICY),
    }
    for k, v in over.items():
        key = {"account": "iam service-accounts describe",
               "pool": "iam workload-identity-pools describe",
               "providers": "iam workload-identity-pools providers list",
               "provider": "iam workload-identity-pools providers describe",
               "policy": "iam service-accounts get-iam-policy",
               "number": "projects describe"}[k]
        a[key] = v if isinstance(v, common.Completed) else ok(v)
    return a


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

    def run(self, argv, timeout=None):
        raise AssertionError("plan never calls the plain runner: %s" % argv)


def run_skill(args=None, **over):
    a = dict(ARGS if args is None else args)
    ctx = FakeContext(answers(**over), a)
    return skill.run(a, ctx), ctx


NULL = {"account": None, "provider": None, "condition": None, "otherMembers": None,
        "ciVariables": None}


class TestValidation(unittest.TestCase):
    def test_each_rule_fails_alone_with_no_command(self):
        for key, value in (("projectId", "Aleogr_dev"), ("project", "ab"),
                           ("project", "demo-"), ("repository", "example-repo"),
                           ("repository", "a/b/c"), ("repository", "-a/b"),
                           ("repository", "a/.."), ("repositoryId", "0123"),
                           ("ownerId", "abc"), ("ownerId", "1" * 21),
                           ("branch", "my branch"), ("branch", "/main"),
                           ("branch", "a..b"), ("branch", "main'||true"),
                           ("workflow", ARGS["workflow"] + "@main"),
                           ("workflow", "aleogr/aleogr/.github/workflows/Deploy.yml"),
                           ("workflow", "aleogr/aleogr/workflows/deploy.yml"),
                           ("mode", "check")):
            with self.subTest(key=key, value=value):
                args = dict(ARGS)
                args[key] = value
                ctx = FakeContext({}, args)
                r = skill.run(args, ctx)
                self.assertEqual((r.status, r.block["outputs"], r.block["resources"],
                                  ctx.calls), ("failed", NULL, [], []))
                self.assertEqual(len(r.lines), 1)
                self.assertTrue(r.lines[0].startswith(key), r.lines[0])
                self.assertEqual(r.block["mode"], "plan")

    def test_missing_in_table_order(self):
        args = dict(ARGS)
        del args["ownerId"]
        del args["branch"]
        r = skill.run(args, FakeContext({}, args))
        self.assertEqual(r.lines, ["ownerId is missing."])

    def test_valid_edge_values(self):
        args = dict(ARGS, project="abc", branch="release/v1.2_x",
                    repository="A-b/x.y_z", repositoryId="9" * 20)
        r = skill.run(args, FakeContext(answers(), args))
        self.assertNotEqual(r.status, "failed")


class TestPlan(unittest.TestCase):
    def test_unchanged_with_ci_variables(self):
        r, ctx = run_skill()
        o = r.block["outputs"]
        self.assertEqual((r.status, o["condition"], o["otherMembers"]),
                         ("unchanged", "as-declared", 0))
        self.assertEqual(o["ciVariables"], {"GCP_PROJECT_ID": PID,
                                            "GCP_WIF_PROVIDER": N["provider"],
                                            "GCP_CI_ACCOUNT": N["account"]})
        self.assertEqual(len(ctx.calls), 6)
        self.assertEqual(r.block["cost"]["notes"],
                         "service accounts and workload identity federation are free")

    def test_condition_spaces_at_the_ends_do_not_count(self):
        p = dict(PROVIDER, attributeCondition="  %s \n" % N["condition"])
        r, _ = run_skill(provider=p)
        self.assertEqual(r.block["outputs"]["condition"], "as-declared")

    def test_provider_differs(self):
        old = dict(PROVIDER, attributeMapping={k: v for k, v in skill.MAPPING[:3]})
        extra = dict(PROVIDER, attributeMapping=dict(skill.MAPPING, **{"attribute.x": "y"}))
        for p in (dict(PROVIDER, oidc={"issuerUri": "https://example.com"}), old, extra,
                  dict(PROVIDER, attributeCondition=N["condition"] + " && true")):
            with self.subTest(p=p):
                r, _ = run_skill(provider=p)
                self.assertEqual((r.status, r.block["outputs"]["condition"],
                                  r.block["outputs"]["ciVariables"]),
                                 ("would-update", "differs", None))

    def test_missing_parts(self):
        r, ctx = run_skill(account=MISSING)
        self.assertEqual((r.status, r.block["outputs"]["otherMembers"]), ("would-create", None))
        self.assertFalse(any("get-iam-policy" in c for c in ctx.calls))
        self.assertEqual([x["type"] for x in r.block["resources"]],
                         ["workload-identity-pool", "workload-identity-provider"])

        r, ctx = run_skill(pool=MISSING)
        self.assertEqual((r.status, r.block["outputs"]["condition"]), ("would-create", "missing"))
        self.assertFalse(any("providers" in c for c in ctx.calls))

        r, _ = run_skill(policy={"bindings": []})
        self.assertEqual((r.status, r.block["outputs"]["otherMembers"]), ("would-create", 0))

    def test_missing_wins_over_differs(self):
        r, _ = run_skill(policy={}, provider=dict(PROVIDER, attributeCondition="x"))
        self.assertEqual(r.status, "would-create")

    def test_other_members_by_number_only(self):
        policy = {"bindings": [{"role": "roles/iam.workloadIdentityUser",
                                "members": [N["member"], "user:helper@example.com",
                                            "group:team@example.com"]}]}
        r, _ = run_skill(policy=policy)
        self.assertEqual(r.block["outputs"]["otherMembers"], 2)
        self.assertIn("2 other members may also act as the account; this skill does not "
                      "remove them.", r.lines)
        self.assertNotIn("example.com", common.render_answer(r))


class TestFailures(unittest.TestCase):
    def test_project_number(self):
        r, ctx = run_skill(number=common.Completed(0, "", ""))
        self.assertEqual((r.status, r.block["outputs"], len(ctx.calls)), ("failed", NULL, 1))

    def test_a_refused_read_is_not_missing(self):
        refused = common.Completed(1, "", "ERROR: PERMISSION_DENIED 403 secret-text")
        for part, calls in (("account", 2), ("pool", 3), ("providers", 4), ("provider", 5),
                            ("policy", 6)):
            with self.subTest(part=part):
                r, ctx = run_skill(**{part: refused})
                o = r.block["outputs"]
                self.assertEqual((r.status, len(ctx.calls), o["account"], o["ciVariables"]),
                                 ("failed", calls, N["account"], None))
                self.assertEqual(len(r.lines), 1)
                self.assertNotIn("secret-text", r.lines[0])

    def test_deleted_disabled_other(self):
        cases = (
            ({"pool": {"state": "DELETED"}}, "undelete github --project="),
            ({"provider": dict(PROVIDER, state="DELETED")}, "providers undelete github"),
            ({"pool": {"state": "ACTIVE", "disabled": True}}, "pool github is disabled"),
            ({"provider": dict(PROVIDER, disabled=True)}, "provider github is disabled"),
            ({"providers": N["provider"] + "\n" + N["provider"][:-len("github")] + "legacy"},
             "another provider legacy"),
        )
        for over, words in cases:
            with self.subTest(over=over):
                r, _ = run_skill(**over)
                self.assertEqual(r.status, "failed")
                self.assertEqual(len(r.lines), 1, r.lines)
                self.assertIn(words, r.lines[0])
                self.assertNotIn("workloadIdentityPools/github/providers/legacy",
                                 common.render_answer(r))
                self.assertIsNone(r.block["outputs"]["ciVariables"])

    def test_apply_is_not_converted(self):
        self.assertEqual(skill.UNCONVERTED_MODES, ("apply",))
        self.assertFalse(common._converted(skill, "apply"))
        self.assertTrue(common._converted(skill, "plan"))


if __name__ == "__main__":
    unittest.main()
