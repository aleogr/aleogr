"""Unit tests of gcp-artifact-registry_access-grant: its golden commands, its gates (every
path that must not write builds no write command), the poll and its waits, and the paths
no scenario covers. The scenarios registry-access-* cover the rest, in the direct mode.

The context's read() answers from a list (a wait's `sleep 30` is recorded, not run), and
execute() (reached only through ctx.write, after the allowlist of writes) records the
write and answers from a list. No provider command runs.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-registry-gcp-artifact-registry"
SKILL = "gcp-artifact-registry_access-grant"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

P = "aleogr-dev-demo-ab12"
SA = "demo-ci@%s.iam.gserviceaccount.com" % P
ARGS = {"projectId": P, "project": "demo", "region": "us-central1", "identity": SA,
        "role": "push", "mode": "apply"}

# The SKILL.md's commands, word for word (steps 1, 3 and 4), the quotes of a value removed.
GOLDEN_POLICY = ("gcloud artifacts repositories get-iam-policy demo --location=us-central1 "
                 "--project=%s --format=json" % P)
GOLDEN_GRANT = ("gcloud artifacts repositories add-iam-policy-binding demo "
                "--location=us-central1 --project=%s --member=serviceAccount:%s "
                "--role=roles/artifactregistry.writer --condition=None --quiet" % (P, SA))

READER = {"role": "roles/artifactregistry.reader",
          "members": ["serviceAccount:123456789012-compute@developer.gserviceaccount.com"]}
WRITER = {"role": "roles/artifactregistry.writer", "members": ["serviceAccount:" + SA]}

NOT_YET = common.Completed(1, "", "ERROR: INVALID_ARGUMENT: Service account %s does not "
                                  "exist." % SA)
DENIED = common.Completed(1, "", "ERROR: PERMISSION_DENIED: Permission "
                                 "'artifactregistry.repositories.setIamPolicy' denied")
DONE = common.Completed(0, "Updated IAM policy for repository [demo].", "")


def policy(*bindings):
    return common.Completed(0, json.dumps({"bindings": list(bindings), "version": 1}), "")


class FakeContext(common.Context):
    def __init__(self, args, reads, writes=None, read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.answers = list(reads)
        self.write_answers = list(writes or [DONE])
        self.reads = []
        self.writes = []
        self.log = []

    def execute(self, argv, timeout=None):
        self.writes.append(list(argv))
        self.log.append("write")
        return self.write_answers.pop(0) if self.write_answers else DONE

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.reads.append(line)
        if argv[0] == "sleep":
            self.log.append("sleep")
            return common.Completed(0, "", "")
        self.log.append("read")
        return self.answers.pop(0) if self.answers else common.Completed(1, "", "ERROR")


class Base(unittest.TestCase):
    def setUp(self):
        common.reset_wait_budget()

    def tearDown(self):
        common.reset_wait_budget()

    def run_skill(self, reads=None, writes=None, **over):
        args = dict(ARGS, **over)
        args = {k: v for k, v in args.items() if v is not None}
        ctx = FakeContext(args, reads if reads is not None
                          else [policy(READER), policy(READER, WRITER)], writes)
        return skill.run(dict(args), ctx), ctx

    def assert_no_write(self, r, ctx, status="failed"):
        self.assertEqual(r.status, status)
        self.assertEqual(ctx.writes, [])
        self.assertEqual(r.block["cost"], skill.COST)


class TestGoldenCommands(Base):
    def test_the_read_the_grant_and_the_read_back_as_the_skill_writes_them(self):
        r, ctx = self.run_skill()
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [GOLDEN_GRANT.split(" ")])
        self.assertEqual(ctx.reads, [GOLDEN_POLICY, GOLDEN_POLICY])
        self.assertIsNone(common.write_refusal(SKILL, ctx.writes[0], root=ROOT))
        self.assertEqual(r.block["outputs"], {"granted": True})
        self.assertEqual(r.block["pending"], [])
        self.assertEqual(r.block["resources"], [
            {"type": "repository-binding", "id": "%s/us-central1/demo" % P, "name": "demo",
             "member": "serviceAccount:" + SA, "role": "roles/artifactregistry.writer"}])

    def test_the_grant_is_this_skill_s_only(self):
        argv = skill.grant_command(P, "demo", "us-central1", "serviceAccount:" + SA)
        for name in common.WRITE_SHAPES:
            self.assertEqual(common.write_refusal(name, argv) is None, name == SKILL, name)

    def test_never_on_the_project_never_another_role(self):
        argv = skill.grant_command(P, "demo", "us-central1", "serviceAccount:" + SA)
        self.assertEqual(argv[1:4], ["artifacts", "repositories", "add-iam-policy-binding"])
        self.assertEqual([a for a in argv if a.startswith("--role")],
                         ["--role=roles/artifactregistry.writer"])


class TestGates(Base):
    def test_mode_absent_is_a_plan(self):
        r, ctx = self.run_skill(mode=None)
        self.assert_no_write(r, ctx, "would-update")
        self.assertEqual(r.block["mode"], "plan")
        self.assertEqual(r.block["outputs"], {"granted": False})
        self.assertEqual(r.block["resources"], [])
        self.assertEqual(ctx.reads, [GOLDEN_POLICY])

    def test_mode_with_another_value(self):
        for mode in ("Apply", "", "grant"):
            with self.subTest(mode=mode):
                r, ctx = self.run_skill(mode=mode)
                self.assert_no_write(r, ctx)
                self.assertEqual(r.lines, ["mode must be plan or apply."])
                self.assertEqual(ctx.reads, [])
                self.assertEqual(r.block["outputs"], {"granted": None})

    def test_read_only_refuses_the_write(self):
        ctx = FakeContext(ARGS, [], read_only=True)
        with self.assertRaises(common.WriteRefused):
            ctx.write(skill.grant_command(P, "demo", "us-central1", "serviceAccount:" + SA))
        self.assertEqual(ctx.writes, [])

    def test_arguments(self):
        cases = [({"projectId": None}, "projectId is missing."),
                 ({"identity": None}, "identity is missing."),
                 ({"role": ""}, "role is missing."),
                 ({"projectId": "abc"}, "projectId is not a GCP project id."),
                 ({"project": "a" * 15}, "project must have 1 to 14"),
                 ({"region": "us"}, "region is not a Google Cloud region name"),
                 ({"identity": "demo-ci"}, "identity must be a service account e-mail"),
                 ({"identity": "serviceAccount:" + SA}, "identity must be a service account e-mail"),
                 ({"identity": SA.upper()}, "identity must be a service account e-mail"),
                 ({"identity": "owner@example.com"}, "identity must be a service account e-mail"),
                 ({"identity": "ab@%s.iam.gserviceaccount.com" % P},
                  "identity must be a service account e-mail"),
                 ({"identity": "demo-ci@aleogr-lab-shared-zz99.iam.gserviceaccount.com"},
                  "identity must be a service account of the project %s." % P),
                 ({"role": "pull"}, "role=pull is not needed"),
                 ({"role": "admin"}, "role must be push."),
                 ({"role": "writer"}, "role must be push.")]
        for over, line in cases:
            with self.subTest(over=over):
                r, ctx = self.run_skill(**over)
                self.assert_no_write(r, ctx)
                self.assertTrue(r.lines[0].startswith(line), r.lines)
                self.assertEqual(ctx.reads, [])

    def test_missing_repository_and_failed_read(self):
        missing = common.Completed(1, "ERROR: NOT_FOUND: Requested entity was not found.", "")
        r, ctx = self.run_skill(reads=[missing])
        self.assert_no_write(r, ctx)
        self.assertEqual(r.lines, [skill.MISSING % ("demo", "us-central1")])
        for answer in (DENIED, common.Completed(0, "", "")):
            r, ctx = self.run_skill(reads=[answer])
            self.assert_no_write(r, ctx)
            self.assertEqual(r.lines, [skill.READ_FAILED % P])

    def test_already_granted(self):
        for mode in ("plan", "apply"):
            r, ctx = self.run_skill(reads=[policy(READER, WRITER)], mode=mode)
            self.assert_no_write(r, ctx, "unchanged")
            self.assertEqual(r.block["outputs"], {"granted": True})
            self.assertEqual(len(r.block["resources"]), 1)

    def test_what_counts_as_granted(self):
        member = "serviceAccount:" + SA
        self.assertFalse(skill.granted({}, member))
        self.assertFalse(skill.granted({"bindings": [READER]}, member))
        self.assertFalse(skill.granted(
            {"bindings": [dict(WRITER, role="roles/artifactregistry.admin")]}, member))
        self.assertFalse(skill.granted(
            {"bindings": [dict(WRITER, condition={"expression": "x"})]}, member))
        self.assertTrue(skill.granted({"bindings": [READER, WRITER]}, member))


class TestPoll(Base):
    def test_one_refusal_then_granted(self):
        r, ctx = self.run_skill(writes=[NOT_YET, DONE])
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.log, ["read", "write", "sleep", "write", "read"])
        self.assertIn("sleep 30", ctx.reads)

    def test_another_refusal_ends_the_poll_at_once(self):
        r, ctx = self.run_skill(writes=[NOT_YET, DENIED])
        self.assertEqual(r.status, "failed")
        self.assertEqual(ctx.log, ["read", "write", "sleep", "write"])
        self.assertEqual(r.lines, [skill.GRANT_FAILED % SA])
        self.assertEqual(r.block["outputs"], {"granted": None})
        self.assertEqual(r.block["resources"], [])
        r, ctx = self.run_skill(writes=[DENIED])
        self.assertEqual(ctx.log, ["read", "write"])

    def test_not_found_is_the_refusal_that_waiting_cures(self):
        nf = common.Completed(1, "", "ERROR: NOT_FOUND: account")
        r, ctx = self.run_skill(writes=[nf, DONE])
        self.assertEqual((r.status, ctx.log.count("sleep")), ("updated", 1))

    def test_ten_tries_nine_waits(self):
        r, ctx = self.run_skill(writes=[NOT_YET] * 10 + [DONE])
        self.assertEqual(r.status, "failed")
        self.assertEqual(len(ctx.writes), 10)
        self.assertEqual(ctx.log.count("sleep"), 9)
        self.assertEqual(r.lines, [skill.GRANT_FAILED % SA])
        self.assertNotIn("INVALID_ARGUMENT", "\n".join(r.lines))

    def test_a_spent_budget_ends_as_the_tenth_refusal(self):
        common._waited[0] = common.WAIT_BUDGET_SECONDS
        r, ctx = self.run_skill(writes=[NOT_YET, DONE])
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.lines, [skill.GRANT_FAILED % SA])
        self.assertEqual(ctx.log, ["read", "write"])

    def test_the_longest_path_fits_the_budget(self):
        self.assertLessEqual((skill.TRIES - 1) * common.WAIT_SECONDS,
                             common.WAIT_BUDGET_SECONDS)


class TestReadBack(Base):
    def test_a_read_back_that_fails_or_does_not_show_it_is_pending(self):
        how = ("/aleogr-registry-gcp-artifact-registry:gcp-artifact-registry_access-grant "
               "projectId=%s project=demo region=us-central1 identity=%s role=push mode=plan"
               % (P, SA))
        for after in ([], [policy(READER)]):
            with self.subTest(after=after):
                r, ctx = self.run_skill(reads=[policy(READER)] + after)
                self.assertEqual(r.status, "updated")
                self.assertEqual(r.block["outputs"], {"granted": False})
                self.assertEqual(r.block["pending"], [{
                    "item": "push access of %s read back" % SA, "reason": "manual",
                    "how": how}])
                self.assertEqual(len(r.block["resources"]), 1)


if __name__ == "__main__":
    unittest.main()
