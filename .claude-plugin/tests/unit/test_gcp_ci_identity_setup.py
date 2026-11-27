"""Unit tests of gcp_ci-identity-setup: the golden commands of mode=apply, its gates (no
write unless mode=apply), and the cases no scenario covers, in both modes.

The skill's run() is given a context whose read() answers from a dict and whose
execute() (where ctx.write runs a command that passed the allowlist of writes) records
the write, so no provider command runs. The scenarios ci-identity-* cover the rest, in
the direct mode.
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
    """answers: {prefix: Completed or [Completed, ...] (one per call, the last repeated)};
    writes: the same, for the writes (a write with no answer exits 0)."""

    def __init__(self, answers, args, writes=None, read_only=False):
        mode = args.get("mode") or "plan"
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                mode if mode in ("plan", "apply") else "plan", args,
                                read_only=read_only)
        self.answers = {k: list(v) if isinstance(v, list) else v for k, v in answers.items()}
        self.write_answers = {k: list(v) if isinstance(v, list) else v
                              for k, v in (writes or {}).items()}
        self.calls = []
        self.writes = []
        self.waits = 0

    @staticmethod
    def _pick(table, line):
        best = None
        for prefix in table:
            if line.startswith(prefix) and (best is None or len(prefix) > len(best)):
                best = prefix
        if best is None:
            return common.Completed(0, "", "")
        v = table[best]
        if isinstance(v, list):
            return v.pop(0) if len(v) > 1 else v[0]
        return v

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        if argv[0] == "sleep":
            self.waits += 1
            return common.Completed(0, "", "")
        line = " ".join(argv[1:])
        self.calls.append(line)
        return self._pick(self.answers, line)

    def execute(self, argv, timeout=None):
        # Reached only through ctx.write, after the allowlist of writes accepted argv.
        self.writes.append(list(argv))
        return self._pick(self.write_answers, " ".join(argv[1:]))

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
        self.assertEqual(r.lines, ["ownerId is missing.", "branch is missing."])

    def test_every_broken_argument_has_its_sentence(self):
        args = dict(ARGS, projectId="Aleogr_dev", repository="example-repo",
                    repositoryId="abc", branch="my branch", mode="apply")
        ctx = FakeContext({}, args)
        r = skill.run(args, ctx)
        self.assertEqual([x.split(" ")[0] for x in r.lines],
                         ["projectId", "repository", "repositoryId", "branch"])
        self.assertEqual((r.status, ctx.calls, ctx.writes, r.block["mode"]),
                         ("failed", [], [], "apply"))

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

    def test_apply_is_converted(self):
        self.assertFalse(hasattr(skill, "UNCONVERTED_MODES"))
        self.assertTrue(common._converted(skill, "apply"))
        self.assertTrue(common._converted(skill, "plan"))
        self.assertTrue(skill.WRITES)


# ---------------------------------------------------------------------------
# mode=apply

APPLY = dict(ARGS, mode="apply")
CONDITION = ("assertion.repository=='example-org/example-repo' && "
             "assertion.repository_id=='7654321' && assertion.repository_owner_id=='2345678' && "
             "assertion.ref=='refs/heads/main' && assertion.job_workflow_ref.startsWith("
             "'aleogr/aleogr/.github/workflows/deploy-cloud-run.yml@')")
MAPPING = ("google.subject=assertion.sub,attribute.repository=assertion.repository,"
           "attribute.ref=assertion.ref,attribute.repository_id=assertion.repository_id,"
           "attribute.repository_owner_id=assertion.repository_owner_id,"
           "attribute.job_workflow_ref=assertion.job_workflow_ref")
MEMBER = ("principalSet://iam.googleapis.com/projects/123456789012/locations/global/"
          "workloadIdentityPools/github/attribute.repository/example-org/example-repo")
# The SKILL.md's commands of step 4, word for word (a double-quoted value is one argument,
# without its quotes).
GOLDEN = {
    "account": ["gcloud", "iam", "service-accounts", "create", "demo-ci", "--project=" + PID,
                "--display-name=demo CI", "--quiet"],
    "pool": ["gcloud", "iam", "workload-identity-pools", "create", "github", "--project=" + PID,
             "--location=global", "--display-name=GitHub", "--quiet"],
    "create": ["gcloud", "iam", "workload-identity-pools", "providers", "create-oidc", "github",
               "--project=" + PID, "--location=global", "--workload-identity-pool=github",
               "--issuer-uri=https://token.actions.githubusercontent.com",
               "--attribute-mapping=" + MAPPING, "--attribute-condition=" + CONDITION,
               "--quiet"],
    "update": ["gcloud", "iam", "workload-identity-pools", "providers", "update-oidc", "github",
               "--project=" + PID, "--location=global", "--workload-identity-pool=github",
               "--issuer-uri=https://token.actions.githubusercontent.com",
               "--attribute-mapping=" + MAPPING, "--attribute-condition=" + CONDITION,
               "--quiet"],
    "binding": ["gcloud", "iam", "service-accounts", "add-iam-policy-binding",
                "demo-ci@%s.iam.gserviceaccount.com" % PID, "--project=" + PID,
                "--member=" + MEMBER, "--role=roles/iam.workloadIdentityUser", "--quiet"],
}
NOT_VISIBLE = common.Completed(1, "", "ERROR: NOT_FOUND: Service account does not exist.")


def nothing_yet(**after):
    """Nothing exists at the first read; each read after that answers `after` (by part)."""
    first = {"account": MISSING, "pool": MISSING}
    a = answers(**first)
    later = answers(**after)
    for key in a:
        a[key] = [a[key], later[key]]
    return a


def apply_run(reads_, writes=None, args=None):
    a = dict(APPLY if args is None else args)
    common.reset_wait_budget()
    ctx = FakeContext(reads_, a, writes)
    r = skill.run(a, ctx)
    common.reset_wait_budget()
    return r, ctx


class TestApplyGolden(unittest.TestCase):
    def test_each_command_as_the_skill_writes_it(self):
        self.assertEqual(skill.account_command(APPLY), GOLDEN["account"])
        self.assertEqual(skill.pool_command(APPLY), GOLDEN["pool"])
        self.assertEqual(skill.provider_command(APPLY, N, "create-oidc"), GOLDEN["create"])
        self.assertEqual(skill.provider_command(APPLY, N, "update-oidc"), GOLDEN["update"])
        self.assertEqual(skill.binding_command(APPLY, N), GOLDEN["binding"])
        for key, argv in GOLDEN.items():
            with self.subTest(key=key):
                self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))
                self.assertNotIn("projects", argv[1:3])

    def test_nothing_exists_four_creates_in_order_then_the_reads_again(self):
        r, ctx = apply_run(nothing_yet())
        self.assertEqual(ctx.writes, [GOLDEN[k] for k in ("account", "pool", "create",
                                                          "binding")])
        self.assertEqual(r.status, "created")
        self.assertEqual(len(ctx.calls), 1 + 2 + 5)  # number, the first reads, the reads again
        self.assertEqual(r.block["pending"], [])
        self.assertIsNotNone(r.block["outputs"]["ciVariables"])
        self.assertIn(skill.COST_LINE, r.lines)

    def test_a_provider_that_differs_is_updated_once(self):
        a = answers()
        a["iam workload-identity-pools providers describe"] = [
            ok(dict(PROVIDER, attributeCondition="x")), ok(PROVIDER)]
        r, ctx = apply_run(a)
        self.assertEqual(ctx.writes, [GOLDEN["update"]])
        self.assertEqual((r.status, r.block["outputs"]["condition"]), ("updated", "as-declared"))


class TestApplyGates(unittest.TestCase):
    def test_no_write_unless_mode_apply(self):
        for mode in (None, "plan"):
            with self.subTest(mode=mode):
                args = dict(ARGS)
                if mode is None:
                    del args["mode"]
                else:
                    args["mode"] = mode
                ctx = FakeContext(nothing_yet(), args)
                r = skill.run(args, ctx)
                self.assertEqual((r.status, ctx.writes), ("would-create", []))
        args = dict(ARGS, mode="Apply")
        ctx = FakeContext(nothing_yet(), args)
        r = skill.run(args, ctx)
        self.assertEqual((r.status, ctx.writes, ctx.calls), ("failed", [], []))

    def test_read_only_refuses_every_write(self):
        ctx = FakeContext({}, APPLY, read_only=True)
        self.assertFalse(ctx.writable)
        for argv in GOLDEN.values():
            with self.assertRaises(common.WriteRefused):
                ctx.write(argv)
        self.assertEqual(ctx.writes, [])

    def test_a_failed_check_writes_nothing(self):
        for over in ({"pool": {"state": "DELETED"}}, {"provider": dict(PROVIDER, disabled=True)},
                     {"account": common.Completed(1, "", "PERMISSION_DENIED")}):
            with self.subTest(over=over):
                r, ctx = apply_run(answers(**over))
                self.assertEqual((r.status, ctx.writes), ("failed", []))


class TestApplyPaths(unittest.TestCase):
    def test_unchanged_writes_and_reads_again_nothing(self):
        r, ctx = apply_run(answers())
        self.assertEqual((r.status, ctx.writes, len(ctx.calls)), ("unchanged", [], 6))
        self.assertIn("This run changed nothing.", r.lines)

    def test_a_stop_at_the_first_change_is_failed(self):
        r, ctx = apply_run(nothing_yet(), writes={"iam service-accounts create":
                                                  common.Completed(1, "", "secret-text")})
        self.assertEqual((r.status, len(ctx.writes)), ("failed", 1))
        self.assertEqual(r.lines, [skill._FAILED["account"] % N])
        self.assertNotIn("secret-text", common.render_answer(r))
        self.assertEqual(r.block["pending"], [])

    def test_a_stop_after_a_change_keeps_what_was_made(self):
        r, ctx = apply_run(nothing_yet(account=MISSING),
                           writes={"iam workload-identity-pools create":
                                   common.Completed(1, "", "ERROR")})
        self.assertEqual(r.status, "created")
        self.assertEqual(len(ctx.writes), 2)
        items = [p["item"] for p in r.block["pending"]]
        self.assertEqual(items[:3], ["pool", "provider", "binding"])
        for p in r.block["pending"]:
            self.assertTrue(p["how"].endswith(" mode=apply"))
            self.assertTrue(p["how"].startswith("/aleogr-cloud-gcp:gcp_ci-identity-setup "))

    def test_permission_denied_is_polled_only_after_this_run_created_the_account(self):
        denied = common.Completed(1, "", "ERROR: PERMISSION_DENIED")
        r, ctx = apply_run(nothing_yet(), writes={"iam service-accounts add-iam-policy-binding":
                                                  [denied, denied, common.Completed(0, "", "")]})
        self.assertEqual((ctx.waits, r.status), (2, "created"))
        # The account exists: a binding refused is not polled.
        r, ctx = apply_run(answers(policy={"bindings": []}),
                           writes={"iam service-accounts add-iam-policy-binding": NOT_VISIBLE})
        self.assertEqual((ctx.waits, r.status, len(ctx.writes)), (0, "failed", 1))
        self.assertIn("refused after 1 try.", r.lines[0])

    def test_the_poll_stops_at_ten_tries(self):
        r, ctx = apply_run(nothing_yet(policy={"bindings": []}),
                           writes={"iam service-accounts add-iam-policy-binding": NOT_VISIBLE})
        self.assertEqual((len([w for w in ctx.writes if "add-iam-policy-binding" in w]),
                          ctx.waits), (10, 9))
        self.assertEqual(r.status, "created")
        self.assertIn("binding", [p["item"] for p in r.block["pending"]])

    def test_the_wait_budget_ends_the_poll_as_the_tenth_refusal(self):
        a = dict(APPLY)
        common.reset_wait_budget()
        ctx = FakeContext(nothing_yet(), a, {"iam service-accounts add-iam-policy-binding":
                                             NOT_VISIBLE})
        for _ in range(15):
            common._waited[0] += common.WAIT_SECONDS
        r = skill.run(a, ctx)
        common.reset_wait_budget()
        self.assertEqual((ctx.waits, r.status), (1, "created"))
        self.assertIn(common.WAIT_BUDGET_SENTENCE, r.lines)
        self.assertIn("binding", [p["item"] for p in r.block["pending"]])
        self.assertIsNone(r.block["outputs"]["ciVariables"])

    def test_a_failed_read_after_the_change(self):
        a = nothing_yet()
        a["iam workload-identity-pools describe"] = [MISSING,
                                                     common.Completed(1, "", "PERMISSION_DENIED")]
        r, ctx = apply_run(a)
        self.assertEqual(r.status, "created")
        items = [p["item"] for p in r.block["pending"]]
        # The reads stop at the first that fails: the parts after it were not read.
        self.assertEqual(items, ["pool", "provider", "binding"])
        self.assertIn("The condition could not be read after the change.", r.lines)


if __name__ == "__main__":
    unittest.main()
