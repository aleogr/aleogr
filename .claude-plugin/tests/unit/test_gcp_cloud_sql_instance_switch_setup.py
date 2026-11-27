"""Unit tests of gcp-cloud-sql_instance-switch-setup: its golden commands (every change
command exactly as the SKILL.md writes it, the jobs' body from the plugin's own file),
mode=plan only reading, the comparison of a job, the parts no command can change, the
stop at a failed change, the single retry of a job's creation and its waits, and that
the result block holds no e-mail and no project number.

The context answers each read from a table (a list answers the calls in order, its last
item the later ones; a read not in the table is NOT_FOUND), answers each write from a
list, and logs `sleep 30`. No provider command runs. The scenarios switch-* cover the
rest.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_instance-switch-setup"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)
BODY = os.path.join(ROOT, "files", "stop-body.json")

ARGS = {"projectId": "aleogr-shared-zz99", "instance": "aleogr-shared",
        "region": "southamerica-east1", "timeZone": "America/Sao_Paulo",
        "weeknightStop": "30 22 * * 0-4", "weekendStop": "0 4 * * 6,0",
        "repository": "aleogr/aleogr", "mode": "apply"}
SA = "aleogr-shared-sql-switch@aleogr-shared-zz99.iam.gserviceaccount.com"
NUMBER = "123456789012"
ACTIVE = "owner@example.com"

# The SKILL.md's change commands, word for word, each as its argv (double quotes removed
# as the shell removes them; ${CLAUDE_PLUGIN_ROOT} written as the plugin's real folder).
P = "--project=aleogr-shared-zz99"
GOLDEN = {
    "role": ["gcloud", "iam", "roles", "create", "aleogrSharedSqlSwitch", P,
             "--title=aleogr shared SQL switch",
             "--permissions=cloudsql.instances.get,cloudsql.instances.update", "--stage=GA",
             "--quiet"],
    "account": ["gcloud", "iam", "service-accounts", "create", "aleogr-shared-sql-switch", P,
                "--display-name=aleogr shared SQL switch", "--quiet"],
    "role-grant": ["gcloud", "projects", "add-iam-policy-binding", "aleogr-shared-zz99",
                   "--member=serviceAccount:" + SA,
                   "--role=projects/aleogr-shared-zz99/roles/aleogrSharedSqlSwitch",
                   "--condition=None", "--quiet"],
    "act-as": ["gcloud", "iam", "service-accounts", "add-iam-policy-binding", SA, P,
               "--member=user:" + ACTIVE, "--role=roles/iam.serviceAccountUser", "--quiet"],
    "pool": ["gcloud", "iam", "workload-identity-pools", "create", "github", P,
             "--location=global", "--display-name=GitHub", "--quiet"],
    "provider": ["gcloud", "iam", "workload-identity-pools", "providers", "create-oidc",
                 "aleogr", P, "--location=global", "--workload-identity-pool=github",
                 "--issuer-uri=https://token.actions.githubusercontent.com",
                 "--attribute-mapping=google.subject=assertion.sub,"
                 "attribute.repository=assertion.repository,attribute.ref=assertion.ref",
                 "--attribute-condition=assertion.repository=='aleogr/aleogr' && "
                 "assertion.ref=='refs/heads/main'", "--quiet"],
    "federation-grant": ["gcloud", "iam", "service-accounts", "add-iam-policy-binding", SA, P,
                         "--member=principalSet://iam.googleapis.com/projects/123456789012/"
                         "locations/global/workloadIdentityPools/github/attribute.repository/"
                         "aleogr/aleogr", "--role=roles/iam.workloadIdentityUser", "--quiet"],
}
URI = "https://sqladmin.googleapis.com/v1/projects/aleogr-shared-zz99/instances/aleogr-shared"


def job_create(job, cron):
    return ["gcloud", "scheduler", "jobs", "create", "http", job, P,
            "--location=southamerica-east1", "--schedule=" + cron,
            "--time-zone=America/Sao_Paulo", "--uri=" + URI, "--http-method=POST",
            "--headers=Content-Type=application/json,X-HTTP-Method-Override=PATCH",
            "--message-body-from-file=" + BODY, "--oauth-service-account-email=" + SA,
            "--oauth-token-scope=https://www.googleapis.com/auth/cloud-platform",
            "--max-retry-attempts=5", "--min-backoff=5m", "--max-backoff=15m",
            "--max-doublings=2", "--attempt-deadline=60s", "--quiet"]


def job_update(job, cron):
    return ["gcloud", "scheduler", "jobs", "update", "http", job, P,
            "--location=southamerica-east1", "--schedule=" + cron,
            "--time-zone=America/Sao_Paulo", "--uri=" + URI, "--http-method=POST",
            "--update-headers=Content-Type=application/json,X-HTTP-Method-Override=PATCH",
            "--message-body-from-file=" + BODY, "--oauth-service-account-email=" + SA,
            "--oauth-token-scope=https://www.googleapis.com/auth/cloud-platform", "--quiet"]


def job_resume(job):
    return ["gcloud", "scheduler", "jobs", "resume", job, P, "--location=southamerica-east1",
            "--quiet"]


WEEKNIGHT, WEEKEND = "aleogr-shared-stop-weeknight", "aleogr-shared-stop-weekend"
GOLDEN_JOBS = [job_create(WEEKNIGHT, "30 22 * * 0-4"), job_create(WEEKEND, "0 4 * * 6,0")]

OK = common.Completed(0, "", "")
NOT_FOUND = common.Completed(1, "", "ERROR: (gcloud) NOT_FOUND: Resource not found.")
FAIL = common.Completed(1, "", "ERROR: PERMISSION_DENIED")
STOP_B64 = "eyJzZXR0aW5ncyI6eyJhY3RpdmF0aW9uUG9saWN5IjoiTkVWRVIifX0="


def job_line(cron, state="ENABLED", uri=URI, method="POST",
             headers="Content-Type=application/json;User-Agent=Google-Cloud-Scheduler;"
                     "X-HTTP-Method-Override=PATCH", body=STOP_B64, tail=()):
    fields = [cron, "America/Sao_Paulo", state, uri, SA, method, headers, body,
              "https://www.googleapis.com/auth/cloud-platform"] + list(tail)
    return common.Completed(0, "\t".join(fields) + "\n", "")


def sa_policy(act_as=True, federation=True):
    b = []
    if act_as:
        b.append({"members": ["user:" + ACTIVE], "role": "roles/iam.serviceAccountUser"})
    if federation:
        b.append({"members": [GOLDEN["federation-grant"][6][len("--member="):]],
                  "role": "roles/iam.workloadIdentityUser"})
    return common.Completed(0, json.dumps({"bindings": b}), "")


def reads(n=None):
    """The read commands, by part, built by the module (checked against the SKILL.md in
    TestGoldenReads)."""
    names = skill.Names(ARGS, NUMBER, ACTIVE, BODY)
    out = skill.read_commands(names)
    for part, job, _c in skill.JOBS:
        out[part] = skill.job_describe_command(names, job)
    return {k: " ".join(v) for k, v in out.items()}


R = reads()
NUMBER_READ = "gcloud projects describe aleogr-shared-zz99 --format=value(projectNumber)"
ACCOUNT_READ = "gcloud config get-value account"


def ready():
    return {NUMBER_READ: common.Completed(0, NUMBER + "\n", ""),
            ACCOUNT_READ: common.Completed(0, ACTIVE + "\n", ""),
            R["role"]: common.Completed(0, "cloudsql.instances.get;cloudsql.instances.update\n",
                                        ""),
            R["account"]: common.Completed(0, SA + "\n", ""),
            R["role-grant"]: common.Completed(0, "serviceAccount:%s\n" % SA, ""),
            R["account-policy"]: sa_policy(),
            R["pool"]: common.Completed(0, "ACTIVE\n", ""),
            R["provider"]: common.Completed(0, "assertion.repository=='aleogr/aleogr' && "
                                               "assertion.ref=='refs/heads/main'\n", ""),
            R["job-weeknight"]: job_line("30 22 * * 0-4"),
            R["job-weekend"]: job_line("0 4 * * 6,0")}


def nothing():
    """Only the project and the active account: every part is NOT_FOUND."""
    a = ready()
    return {NUMBER_READ: a[NUMBER_READ], ACCOUNT_READ: a[ACCOUNT_READ]}


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
        self.writes.append(list(argv))
        self.log.append(" ".join(argv))
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
            return NOT_FOUND
        return seq.pop(0) if len(seq) > 1 else seq[0]


def run(answers, writes=(), **over):
    common.reset_wait_budget()
    args = dict(ARGS, **over)
    args = {k: v for k, v in args.items() if v is not None}
    ctx = FakeContext(args, answers, writes)
    return skill.run(dict(args), ctx), ctx


def then(first, after):
    """Answers that read `first` at the check and `after` at the verification."""
    out = {}
    for k in set(first) | set(after):
        a, b = first.get(k, NOT_FOUND), after.get(k, NOT_FOUND)
        out[k] = [a, b] if k not in (NUMBER_READ, ACCOUNT_READ) else a
    return out


class TestGoldenReads(unittest.TestCase):
    def test_the_reads_as_the_skill_writes_them(self):
        self.assertEqual(R, {
            "role": "gcloud iam roles describe aleogrSharedSqlSwitch --project=aleogr-shared-zz99 "
                    "--format=value(includedPermissions)",
            "account": "gcloud iam service-accounts describe %s --project=aleogr-shared-zz99 "
                       "--format=value(email)" % SA,
            "role-grant": "gcloud projects get-iam-policy aleogr-shared-zz99 "
                          "--flatten=bindings[].members "
                          "--filter=bindings.role:roles/aleogrSharedSqlSwitch "
                          "--format=value(bindings.members)",
            "account-policy": "gcloud iam service-accounts get-iam-policy %s "
                              "--project=aleogr-shared-zz99 --format=json" % SA,
            "pool": "gcloud iam workload-identity-pools describe github "
                    "--project=aleogr-shared-zz99 --location=global --format=value(state)",
            "provider": "gcloud iam workload-identity-pools providers describe aleogr "
                        "--project=aleogr-shared-zz99 --location=global "
                        "--workload-identity-pool=github --format=value(attributeCondition)",
            "job-weeknight": "gcloud scheduler jobs describe %s --project=aleogr-shared-zz99 "
                             "--location=southamerica-east1 %s" % (WEEKNIGHT, skill.JOB_FORMAT),
            "job-weekend": "gcloud scheduler jobs describe %s --project=aleogr-shared-zz99 "
                           "--location=southamerica-east1 %s" % (WEEKEND, skill.JOB_FORMAT),
        })
        self.assertEqual(skill.JOB_FORMAT,
                         "--format=value(schedule,timeZone,state,httpTarget.uri,"
                         "httpTarget.oauthToken.serviceAccountEmail,httpTarget.httpMethod,"
                         "httpTarget.headers,httpTarget.body,httpTarget.oauthToken.scope,"
                         "lastAttemptTime,status.code)")


class TestGoldenCommands(unittest.TestCase):
    def test_everything_missing(self):
        # Only the role, the account and the pool are read at the check (the others
        # depend on a missing part); the verification reads every part.
        answers = ready()
        for part in ("role", "account", "pool"):
            answers[R[part]] = [NOT_FOUND, answers[R[part]]]
        r, ctx = run(answers)
        self.assertEqual(r.status, "created")
        want = [GOLDEN[p] for p in ("role", "account", "role-grant", "act-as", "pool",
                                    "provider", "federation-grant")] + GOLDEN_JOBS
        self.assertEqual(ctx.writes, want)
        for argv in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT), argv)
        self.assertTrue(r.block["outputs"]["ready"])
        block = json.dumps(r.block)
        self.assertNotIn("@", block)
        self.assertNotIn(NUMBER, block)
        text = "\n".join(r.lines)
        self.assertIn("GitHub secrets", text)
        self.assertIn("GCP_SHARED_WIF_PROVIDER: projects/%s/locations/global/"
                      "workloadIdentityPools/github/providers/aleogr" % NUMBER, text)

    def test_the_updates_and_the_resume(self):
        first = ready()
        first[R["job-weeknight"]] = job_line("0 23 * * *", state="PAUSED")
        first[R["job-weekend"]] = job_line("0 4 * * 6,0", state="PAUSED")
        r, ctx = run(then(first, ready()))
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [job_update(WEEKNIGHT, "30 22 * * 0-4"),
                                      job_resume(WEEKNIGHT), job_resume(WEEKEND)])
        for argv in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT), argv)

    def test_the_body_is_the_plugin_s_file(self):
        self.assertEqual(common.base64_of_file(BODY), STOP_B64)
        with open(BODY) as f:
            self.assertEqual(json.load(f), skill.STOP_BODY)


class TestPlanOnlyReads(unittest.TestCase):
    def test_plan(self):
        for answers, status in ((nothing(), "would-create"), (ready(), "unchanged")):
            r, ctx = run(answers, mode="plan")
            self.assertEqual((r.status, ctx.writes), (status, []))
            self.assertEqual(r.block["mode"], "plan")
        first = ready()
        first[R["job-weekend"]] = job_line("1 4 * * 6,0")
        r, ctx = run(first, mode="plan")
        self.assertEqual((r.status, ctx.writes), ("would-update", []))
        self.assertEqual(r.block["outputs"]["missing"], ["job-weekend"])

    def test_the_parts_that_depend_on_a_missing_part_are_not_read(self):
        r, ctx = run(nothing(), mode="plan")
        self.assertEqual(ctx.log, [NUMBER_READ, ACCOUNT_READ, R["role"], R["account"], R["pool"]])
        self.assertEqual(r.block["outputs"]["missing"], list(skill.PARTS))
        self.assertEqual(r.block["resources"], [])

    def test_validation_and_step_one(self):
        r, ctx = run({}, repository="not-a-repo")
        self.assertEqual((r.status, ctx.log), ("failed", []))
        r, ctx = run({}, repository=None)
        self.assertEqual(r.lines, ["repository is missing."])
        r, ctx = run({NUMBER_READ: OK})
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertEqual(r.block["outputs"], {"ready": False, "missing": [], "lastRunFailed": []})

    def test_a_check_that_fails(self):
        answers = ready()
        answers[R["pool"]] = FAIL
        for mode in ("plan", "apply"):
            r, ctx = run(answers, mode=mode)
            self.assertEqual((r.status, ctx.writes), ("failed", []))

    def test_values_no_command_takes(self):
        for over in ({"region": "a" * 64}, {"timeZone": "America/" + "x" * 65},
                     {"weeknightStop": "1" * 41 + " 22 * * 0-4"}):
            for mode in ("plan", "apply"):
                with self.subTest(over=over, mode=mode):
                    r, ctx = run(nothing(), mode=mode, **over)
                    self.assertEqual((r.status, ctx.writes), ("failed", []))
                    self.assertEqual(r.lines, [skill.NOT_RUNNABLE])


class TestTheJobs(unittest.TestCase):
    def test_what_makes_a_job_different(self):
        cases = {
            "extra headers are fine": (job_line("30 22 * * 0-4"), "equal"),
            "no override header": (job_line("30 22 * * 0-4",
                                            headers="Content-Type=application/json"),
                                   "different"),
            "another instance": (job_line("30 22 * * 0-4", uri=URI + "x"), "different"),
            "PUT": (job_line("30 22 * * 0-4", method="PUT"), "different"),
            "an empty body": (job_line("30 22 * * 0-4", body="e30="), "different"),
            "paused": (job_line("30 22 * * 0-4", state="PAUSED"), "different"),
        }
        for name, (answer, state) in cases.items():
            with self.subTest(name=name):
                answers = ready()
                answers[R["job-weeknight"]] = answer
                r, ctx = run(answers, mode="plan")
                self.assertEqual(r.block["outputs"]["missing"] == ["job-weeknight"],
                                 state == "different")

    def test_a_last_run_that_failed(self):
        answers = ready()
        answers[R["job-weekend"]] = job_line("0 4 * * 6,0", tail=("2026-11-15T07:00:01Z", "7"))
        r, ctx = run(answers)
        self.assertEqual((r.status, ctx.writes), ("unchanged", []))
        self.assertEqual(r.block["outputs"]["lastRunFailed"], ["job-weekend"])
        self.assertTrue(r.block["outputs"]["ready"])
        answers[R["job-weekend"]] = job_line("0 4 * * 6,0", tail=("2026-11-15T07:00:01Z", "0"))
        r, ctx = run(answers)
        self.assertEqual(r.block["outputs"]["lastRunFailed"], [])

    def test_one_retry_after_about_one_minute(self):
        first = ready()
        first[R["job-weeknight"]] = NOT_FOUND
        r, ctx = run(then(first, ready()), writes=(FAIL, OK))
        self.assertEqual(ctx.writes, [GOLDEN_JOBS[0], GOLDEN_JOBS[0]])
        self.assertEqual(ctx.log.count("sleep 30"), 2)
        self.assertEqual(r.status, "created")
        r, ctx = run(then(first, ready()), writes=(FAIL,))
        self.assertEqual(ctx.writes, [GOLDEN_JOBS[0], GOLDEN_JOBS[0]])
        self.assertEqual(r.status, "pending")
        self.assertIn("job-weeknight", r.block["outputs"]["missing"])

    def test_the_budget_spent_before_the_retry(self):
        first = ready()
        first[R["job-weeknight"]] = NOT_FOUND
        common.reset_wait_budget()
        ctx = FakeContext(ARGS, then(first, ready()), (FAIL, OK))
        common._waited[0] = common.WAIT_BUDGET_SECONDS
        r = skill.run(dict(ARGS), ctx)
        self.assertEqual(ctx.writes, [GOLDEN_JOBS[0]])
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.block["pending"], [ctx.wait_budget_item()])
        self.assertIn(common.WAIT_BUDGET_SENTENCE, r.lines)


class TestPartsNoCommandChanges(unittest.TestCase):
    def test_a_role_with_other_permissions(self):
        answers = ready()
        answers[R["role"]] = common.Completed(0, "cloudsql.instances.get\n", "")
        for mode in ("plan", "apply"):
            r, ctx = run(answers, mode=mode)
            self.assertEqual((r.status, ctx.writes), ("pending", []))
            self.assertEqual(r.block["outputs"]["missing"], ["role"])
            self.assertIn("by hand", r.block["pending"][0]["how"])
            self.assertNotIn("GitHub secrets", "\n".join(r.lines))

    def test_a_provider_with_another_condition(self):
        answers = ready()
        answers[R["provider"]] = common.Completed(0, "true\n", "")
        r, ctx = run(answers)
        self.assertEqual((r.status, ctx.writes), ("pending", []))
        self.assertEqual(r.block["outputs"]["missing"], ["provider"])


class TestAFailedChange(unittest.TestCase):
    def test_nothing_exists(self):
        r, ctx = run(nothing(), writes=(FAIL,))
        self.assertEqual(ctx.writes, [GOLDEN["role"]])
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.block["outputs"]["missing"], list(skill.PARTS))
        self.assertNotIn("PERMISSION_DENIED", "\n".join(r.lines))

    def test_something_exists(self):
        r, ctx = run(nothing(), writes=(OK, FAIL))
        self.assertEqual(ctx.writes, [GOLDEN["role"], GOLDEN["account"]])
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.block["outputs"]["missing"], list(skill.PARTS[1:]))
        self.assertEqual([x["type"] for x in r.block["resources"]], ["role"])
        for item in r.block["pending"]:
            self.assertTrue(item["how"].endswith(" mode=apply"))
            self.assertIn('weeknightStop="30 22 * * 0-4"', item["how"])


if __name__ == "__main__":
    unittest.main()
