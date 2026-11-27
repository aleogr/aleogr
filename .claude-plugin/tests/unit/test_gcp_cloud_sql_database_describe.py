"""Unit tests of gcp-cloud-sql_database-describe's rules, the cases no scenario covers.
The scenarios sql-database-describe-* cover the rest, in the direct mode."""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_database-describe"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

WEB = "demo-web@aleogr-dev-demo-ab12.iam.gserviceaccount.com"
API = "demo-api@aleogr-dev-demo-ab12.iam.gserviceaccount.com"
ARGS = {"sharedProjectId": "aleogr-shared-ab12", "instance": "aleogr-shared",
        "project": "my-app", "environment": "dev", "accounts": "%s,%s" % (WEB, API)}

DESCRIBE = "sql instances describe"
OPS = "sql operations list"
IAM = "projects get-iam-policy"
DBS = "sql databases list"
USERS = "sql users list"


class FakeContext(common.Context):
    def __init__(self, answers):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill, "plan", ARGS)
        self.answers = answers
        self.calls = []

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        self.calls.append(" ".join(argv[1:3 if argv[1] == "projects" else 4]))
        for prefix, completed in self.answers.items():
            if " ".join(argv[1:]).startswith(prefix):
                return completed
        return common.Completed(0, "", "")


def ok(obj):
    return common.Completed(0, json.dumps(obj) if not isinstance(obj, str) else obj, "")


def instance(policy="ALWAYS", state="RUNNABLE"):
    settings = {} if policy is None else {"activationPolicy": policy}
    return ok({"state": state, "settings": settings})


FAIL = common.Completed(1, "", "ERROR: boom 403")


class TestDatabaseDescribe(unittest.TestCase):
    def test_database_name(self):
        self.assertEqual(skill.database_name("my-app", "dev"), "my_app_dev")
        self.assertEqual(skill.user_name(WEB), "demo-web@aleogr-dev-demo-ab12.iam")

    def test_validation_sentences_one_per_rule(self):
        args = {"sharedProjectId": "X", "instance": "1a", "project": "a-",
                "environment": "qa", "accounts": "%s,%s,,serviceAccount:%s" % (WEB, WEB, API)}
        ctx = FakeContext({})
        r = skill.run(args, ctx)
        self.assertEqual(r.lines, [
            "sharedProjectId is not a GCP project id.",
            "instance must have 1 to 60 lowercase letters, digits and hyphens, starting with "
            "a letter.",
            "project must have 1 to 14 lowercase letters, digits and hyphens, starting with a "
            "letter and not ending with a hyphen.",
            "environment must be dev, hom or prd.",
            "Entry 2 of accounts is given twice.",
            "Entry 3 of accounts is not the address of a service account "
            "(<id>@<project id>.iam.gserviceaccount.com).",
            "Entry 4 of accounts is not the address of a service account "
            "(<id>@<project id>.iam.gserviceaccount.com).",
        ])
        self.assertEqual(r.block["outputs"], {"instanceState": None, "database": None,
                                              "databaseExists": None, "users": [],
                                              "read": False})
        self.assertEqual((r.status, r.block["resources"], ctx.calls), ("failed", [], []))

    def test_missing_arguments_keep_the_database(self):
        r = skill.run({"project": "my-app", "environment": "prd"}, FakeContext({}))
        self.assertEqual(r.lines, ["sharedProjectId is missing.", "instance is missing.",
                                   "accounts is missing."])
        self.assertEqual(r.block["outputs"]["database"], "my_app_prd")

    def test_user_name_too_long(self):
        long = "a" * 30 + "@" + "b" * 30 + ".iam.gserviceaccount.com"
        r = skill.run(dict(ARGS, accounts=long), FakeContext({}))
        self.assertEqual(r.lines, ["The database user of entry 1 of accounts would have 65 "
                                   "characters: PostgreSQL allows 63."])

    def test_instance_failure(self):
        ctx = FakeContext({DESCRIBE: FAIL})
        r = skill.run(dict(ARGS), ctx)
        self.assertEqual((r.status, r.block["resources"], r.block["outputs"]["database"]),
                         ("failed", [], "my_app_dev"))
        self.assertEqual(r.lines, [skill.INSTANCE_FAILED % "aleogr-shared"])
        self.assertEqual(ctx.calls, [DESCRIBE])

    def test_policy_failure_keeps_the_state(self):
        ctx = FakeContext({DESCRIBE: instance("NEVER"), IAM: FAIL})
        r = skill.run(dict(ARGS), ctx)
        o = r.block["outputs"]
        self.assertEqual((r.status, o["instanceState"], o["users"], len(r.block["resources"])),
                         ("failed", "stopped", [], 1))
        self.assertEqual(r.lines, [skill.POLICY_FAILED])

    def test_users_failure_keeps_the_databases(self):
        ctx = FakeContext({DESCRIBE: instance(), IAM: ok({}), DBS: ok("my_app_dev\n"),
                           USERS: FAIL})
        r = skill.run(dict(ARGS), ctx)
        o = r.block["outputs"]
        self.assertEqual((r.status, o["databaseExists"], o["read"]), ("failed", True, False))
        self.assertEqual([u["user"] for u in o["users"]], [None, None])
        self.assertEqual(ctx.calls, [DESCRIBE, OPS, IAM, DBS, USERS])

    def test_conditional_binding_counts_and_case_is_ignored(self):
        policy = {"bindings": [
            {"role": "roles/cloudsql.client", "members": ["serviceAccount:" + WEB.upper()],
             "condition": {"title": "only the shared instance"}},
            {"role": "roles/cloudsql.instanceUserX", "members": ["serviceAccount:" + WEB]},
        ]}
        ctx = FakeContext({DESCRIBE: instance("NEVER"), IAM: ok(policy)})
        o = skill.run(dict(ARGS), ctx).block["outputs"]
        self.assertEqual(o["users"][0], {"account": 1, "user": None, "client": True,
                                         "instanceUser": False})

    def test_other_states_read_nothing_more(self):
        for policy, state, want in (("ALWAYS", "PENDING_CREATE", "creating"),
                                    ("ALWAYS", "MAINTENANCE", "starting"),
                                    ("ON_DEMAND", "RUNNABLE", "unknown"),
                                    (None, "RUNNABLE", "unknown")):
            with self.subTest(policy=policy, state=state):
                ctx = FakeContext({DESCRIBE: instance(policy, state), IAM: ok({})})
                r = skill.run(dict(ARGS), ctx)
                self.assertEqual((r.status, r.block["outputs"]["instanceState"]),
                                 ("unchanged", want))
                self.assertEqual(ctx.calls, [DESCRIBE, IAM])
                self.assertIn(skill.NOT_READ % want, r.lines)
        r = skill.run(dict(ARGS), FakeContext({DESCRIBE: instance(None), IAM: ok({})}))
        self.assertIn("Its activation policy is absent.", r.lines)

    def test_operations_failure_keeps_running(self):
        ctx = FakeContext({DESCRIBE: instance(), OPS: FAIL, IAM: ok({}),
                           DBS: ok("postgres\n"), USERS: ok("postgres\n")})
        r = skill.run(dict(ARGS), ctx)
        o = r.block["outputs"]
        self.assertEqual((r.status, o["instanceState"], o["databaseExists"], o["read"]),
                         ("unchanged", "running", False, True))
        self.assertIn(skill.OPS_NOT_CHECKED, r.lines)
        self.assertNotIn("boom", "\n".join(r.lines))

    def test_block_holds_no_address(self):
        ctx = FakeContext({DESCRIBE: instance("NEVER"), IAM: ok({})})
        r = skill.run(dict(ARGS), ctx)
        self.assertNotIn("@", common.render_block(r.block))


if __name__ == "__main__":
    unittest.main()
