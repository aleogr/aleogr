"""Unit tests of gcp-cloud-sql_access-grant: its golden commands (the user of the IAM
service-account type, never a password; the two roles, to serviceAccount:<account> only,
on the shared project only, with --condition=None), the paths where no write may be built,
the user before the roles, the poll of a grant and its budget of waiting, and that the
result block holds no e-mail.

The context answers each read from a table (a list answers the calls in order, its last
item the later ones), answers each write from a list in order, and logs `sleep 30`. No
provider command runs. The scenarios sql-access-* cover the rest.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_access-grant"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

ACCOUNT = "demo-web@aleogr-dev-demo-ab12.iam.gserviceaccount.com"
ARGS = {"sharedProjectId": "aleogr-shared-ab12", "instance": "aleogr-shared",
        "account": ACCOUNT, "mode": "apply"}
GOLDEN_USER = ("gcloud sql users create demo-web@aleogr-dev-demo-ab12.iam --instance=aleogr-shared "
               "--project=aleogr-shared-ab12 --type=cloud_iam_service_account --quiet")
GOLDEN_CLIENT = ("gcloud projects add-iam-policy-binding aleogr-shared-ab12 "
                 "--member=serviceAccount:demo-web@aleogr-dev-demo-ab12.iam.gserviceaccount.com "
                 "--role=roles/cloudsql.client --condition=None --quiet")
GOLDEN_INSTANCE_USER = GOLDEN_CLIENT.replace("roles/cloudsql.client", "roles/cloudsql.instanceUser")
DESCRIBE = "gcloud sql instances describe aleogr-shared --project=aleogr-shared-ab12 --format=json"
OPERATIONS = ("gcloud sql operations list --instance=aleogr-shared --project=aleogr-shared-ab12 "
              "--filter=status!=DONE --limit=10 --format=value(operationType,status)")
POLICY = "gcloud projects get-iam-policy aleogr-shared-ab12 --format=json"
USERS = ("gcloud sql users list --instance=aleogr-shared --project=aleogr-shared-ab12 "
         "--format=value(name)")
OK = common.Completed(0, "", "")
DENIED = common.Completed(1, "", "ERROR: PERMISSION_DENIED: Policy update access denied.")
NOT_VISIBLE = common.Completed(1, "", "ERROR: INVALID_ARGUMENT: Service account %s does not "
                                      "exist." % ACCOUNT)
FAIL = common.Completed(1, "", "ERROR")


def instance(policy="ALWAYS", state="RUNNABLE"):
    return common.Completed(0, json.dumps({"state": state,
                                           "settings": {"activationPolicy": policy}}), "")


def policy(*roles, condition=False):
    bindings = [{"members": ["user:owner@example.com"], "role": "roles/owner"}]
    for r in roles:
        b = {"members": ["serviceAccount:%s" % ACCOUNT], "role": r}
        if condition:
            b["condition"] = {"expression": "true", "title": "t"}
        bindings.append(b)
    return common.Completed(0, json.dumps({"bindings": bindings}), "")


def users(*names):
    return common.Completed(0, "\n".join(("postgres",) + names) + "\n", "")


USER = "demo-web@aleogr-dev-demo-ab12.iam"
BOTH = (skill.CLIENT, skill.INSTANCE_USER)


class FakeContext(common.Context):
    def __init__(self, args, answers, writes=(), read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.answers = {k: list(v) if isinstance(v, list) else [v] for k, v in answers.items()}
        self.write_answers = list(writes)
        self.log = []
        self.writes = []

    def execute(self, argv, timeout=None):
        line = " ".join(argv)
        self.writes.append(line)
        self.log.append(line)
        if not self.write_answers:
            return OK
        return self.write_answers.pop(0) if len(self.write_answers) > 1 else self.write_answers[0]

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.log.append(line)
        if argv[0] == "sleep":
            return OK
        seq = self.answers.get(line)
        if not seq:
            return FAIL
        return seq.pop(0) if len(seq) > 1 else seq[0]


def run(answers=None, writes=(), **over):
    common.reset_wait_budget()
    args = dict(ARGS, **over)
    args = {k: v for k, v in args.items() if v is not None}
    base = {DESCRIBE: instance(), OPERATIONS: OK, POLICY: [policy(), policy(*BOTH)],
            USERS: [users(), users(USER)]}
    base.update(answers or {})
    ctx = FakeContext(args, base, writes)
    return skill.run(dict(args), ctx), ctx


def sleeps(ctx):
    return ctx.log.count("sleep 30")


class TestGoldenCommands(unittest.TestCase):
    def test_the_user_then_the_two_roles(self):
        r, ctx = run()
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [GOLDEN_USER, GOLDEN_CLIENT, GOLDEN_INSTANCE_USER])
        self.assertEqual(ctx.log, [DESCRIBE, OPERATIONS, POLICY, USERS, GOLDEN_USER, USERS,
                                   GOLDEN_CLIENT, GOLDEN_INSTANCE_USER, POLICY])
        for line in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, line.split(" "), root=ROOT))
            self.assertNotIn("password", line)
        self.assertEqual(r.block["outputs"], {
            "instanceState": "running", "user": True, "client": True, "instanceUser": True,
            "granted": list(BOTH), "userCreated": True})
        self.assertEqual(r.block["pending"], [])

    def test_no_e_mail_in_the_block(self):
        for answers, writes in (({}, ()), ({}, (DENIED,)), ({USERS: [users(), FAIL]}, ())):
            r, ctx = run(answers, writes)
            self.assertNotIn("@", json.dumps(r.block))

    def test_the_grant_is_refused_for_another_member_or_role(self):
        bad = [GOLDEN_CLIENT.replace("serviceAccount:", "user:"),
               GOLDEN_CLIENT.replace("roles/cloudsql.client", "roles/cloudsql.admin"),
               GOLDEN_CLIENT.replace(" --condition=None", ""),
               GOLDEN_USER.replace("cloud_iam_service_account", "built_in")]
        for line in bad:
            self.assertIsNotNone(common.write_refusal(SKILL, line.split(" "), root=ROOT), line)


class TestNoWrite(unittest.TestCase):
    def test_plan(self):
        r, ctx = run(mode="plan")
        self.assertEqual((r.status, ctx.writes), ("would-update", []))
        self.assertEqual(r.block["outputs"]["granted"], list(BOTH))
        self.assertFalse(r.block["outputs"]["userCreated"])
        r, ctx = run({POLICY: policy(*BOTH), USERS: users(USER)}, mode="plan")
        self.assertEqual((r.status, ctx.writes), ("unchanged", []))

    def test_invalid(self):
        for over in ({"account": "serviceAccount:%s" % ACCOUNT}, {"account": None},
                     {"mode": "yes"}, {"sharedProjectId": "X"}):
            with self.subTest(over=over):
                r, ctx = run(**over)
                self.assertEqual((r.status, ctx.log), ("failed", []))
                self.assertEqual(r.block["resources"], [])
        long = "a" * 30 + "@" + "b" * 30 + ".iam.gserviceaccount.com"
        r, ctx = run(account=long)
        self.assertEqual(r.lines, ["The database user of account would have 65 characters: "
                                   "PostgreSQL allows 63."])

    def test_an_instance_that_is_not_running(self):
        for answer, state in ((instance("NEVER"), "stopped"),
                              (instance("ALWAYS", "MAINTENANCE"), "starting"),
                              (instance("X"), "unknown")):
            with self.subTest(state=state):
                r, ctx = run({DESCRIBE: answer})
                self.assertEqual((r.status, ctx.writes), ("pending", []))
                self.assertNotIn(USERS, ctx.log)
                self.assertIsNone(r.block["outputs"]["user"])
                self.assertEqual(r.block["pending"][0]["item"], "instance")

    def test_reads_that_fail(self):
        for answers, sentence in (({DESCRIBE: FAIL}, skill.INSTANCE_FAILED % "aleogr-shared"),
                                  ({POLICY: FAIL}, skill.POLICY_FAILED),
                                  ({USERS: FAIL}, skill.USERS_FAILED % "aleogr-shared")):
            r, ctx = run(answers)
            self.assertEqual((r.status, ctx.writes), ("failed", []))
            self.assertIn(sentence, r.lines)

    def test_unchanged_and_a_conditional_binding(self):
        r, ctx = run({POLICY: policy(*BOTH, condition=True), USERS: users(USER)})
        self.assertEqual((r.status, ctx.writes), ("unchanged", []))


class TestTheUserFirst(unittest.TestCase):
    def test_a_user_not_listed_after_its_create(self):
        for write in (OK, FAIL):
            r, ctx = run({USERS: users()}, (write,))
            self.assertEqual(r.status, "failed")
            self.assertEqual(ctx.writes, [GOLDEN_USER])  # no role
            self.assertIn(skill.USER_NOT_CREATED % "aleogr-shared", r.lines)
            self.assertEqual(r.block["pending"][0]["item"], "access")

    def test_users_unread_after_the_create(self):
        r, ctx = run({USERS: [users(), FAIL]}, (FAIL,))
        self.assertEqual((r.status, ctx.writes), ("failed", [GOLDEN_USER]))
        self.assertIn(skill.USER_FAILED_UNREAD, r.lines)
        r, ctx = run({USERS: [users(), FAIL]})
        self.assertEqual((r.status, ctx.writes), ("updated", [GOLDEN_USER]))
        self.assertTrue(r.block["outputs"]["userCreated"])
        self.assertIsNone(r.block["outputs"]["user"])

    def test_a_create_that_failed_but_the_user_exists(self):
        r, ctx = run(writes=(FAIL, OK))
        self.assertEqual(r.status, "updated")
        self.assertIn(skill.USER_FAILED_BUT_EXISTS, r.lines)


class TestThePoll(unittest.TestCase):
    def test_a_plain_denial_is_never_waited_on(self):
        r, ctx = run({USERS: users(USER)}, (DENIED,))
        self.assertEqual(r.status, "failed")
        self.assertEqual((ctx.writes, sleeps(ctx)), ([GOLDEN_CLIENT], 0))
        self.assertIn(skill.GRANT_REFUSED % skill.CLIENT, r.lines)
        self.assertNotIn("PERMISSION_DENIED", "\n".join(r.lines))
        self.assertNotIn(POLICY, ctx.log[3:])  # no role granted before it: no read back

    def test_ten_tries_nine_waits(self):
        r, ctx = run({USERS: users(USER)}, [NOT_VISIBLE] * 10 + [OK])
        self.assertEqual(r.status, "failed")
        self.assertEqual(ctx.writes, [GOLDEN_CLIENT] * 10)
        self.assertEqual(sleeps(ctx), 9)
        self.assertIn("The grant of the role roles/cloudsql.client was refused after 10 tries.",
                      r.lines)
        text = "\n".join(r.lines)
        for word in ("does not exist", "Service account", "NOT_FOUND", "INVALID_ARGUMENT"):
            self.assertNotIn(word, text)

    def test_the_second_role_refused_reads_back(self):
        r, ctx = run({USERS: users(USER), POLICY: [policy(), policy(skill.CLIENT)]},
                     (OK, DENIED))
        self.assertEqual(r.status, "failed")
        self.assertEqual(ctx.log.count(POLICY), 2)
        self.assertEqual((r.block["outputs"]["client"], r.block["outputs"]["instanceUser"]),
                         (True, False))
        self.assertEqual(r.block["outputs"]["granted"], [skill.CLIENT])
        self.assertEqual(r.block["pending"][0]["item"], "access")

    def test_the_budget_of_waiting_ends_the_poll(self):
        # The first role takes 10 tries (9 waits); the second gets 7 waits, then the
        # eighth is refused by the budget: it counts as the refusal that ends the poll.
        r, ctx = run({USERS: users(USER), POLICY: [policy(), policy(skill.CLIENT)]},
                     [NOT_VISIBLE] * 9 + [OK] + [NOT_VISIBLE] * 20)
        self.assertEqual(sleeps(ctx), 16)
        self.assertEqual(ctx.writes.count(GOLDEN_CLIENT), 10)
        self.assertEqual(ctx.writes.count(GOLDEN_INSTANCE_USER), 8)
        self.assertEqual(r.status, "failed")
        self.assertIn("The grant of the role roles/cloudsql.instanceUser was refused after 8 "
                      "tries.", r.lines)
        self.assertEqual(r.block["pending"][0]["item"], "access")

    def test_a_role_not_seen_after_its_grant(self):
        r, ctx = run({USERS: users(USER), POLICY: [policy(), policy(skill.CLIENT)]})
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.block["pending"][0]["item"], "access")


if __name__ == "__main__":
    unittest.main()
