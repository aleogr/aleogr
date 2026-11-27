"""Unit tests of gcp_environment-create: its golden commands, its gate (no project is
created and no billing linked without mode=apply), the check of the writes against the
allowlist in both modes, and the paths no scenario covers.

The skill's run() is given a context whose call() answers for the describe skill, whose
read() answers from a dict, and whose execute() (where ctx.write runs a command that
passed the allowlist of writes) records the write. No provider command runs. The
scenarios create-* cover the rest, in the direct mode.
"""

import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_environment-create"
ROOT = plugin_root(PLUGIN)
# The SKILL.md as it was before it became a shell over the command: the specification
# these tests check the module against.
SKILL_MD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden",
                        "gcp_environment-create.md")
skill = load_skill(PLUGIN, SKILL)

OK = common.Completed
ORG = "gcloud organizations list --format=value(name)"
FOLDER = ("gcloud resource-manager folders list --organization=111111111111 "
          "--filter=displayName=dev --format=value(name)")
TST = ("gcloud resource-manager folders list --organization=111111111111 "
       "--filter=displayName=tst --format=value(name)")
IN_TST = ("gcloud resource-manager folders list --folder=333333333333 "
          "--filter=displayName=dev --format=value(name)")
SEARCH_FOLDER = ("gcloud projects list --filter=parent.type=folder AND parent.id=222222222222 "
                 "AND labels.aleogr-project=demo AND labels.aleogr-environment=dev "
                 "--format=value(projectId)")
SEARCH_ORG = ("gcloud projects list --filter=parent.type=organization AND "
              "parent.id=111111111111 AND labels.aleogr-project=shared AND "
              "labels.aleogr-platform=shared --format=value(projectId)")
ACCOUNTS = "gcloud billing accounts list --filter=open=true --format=value(name)"

# The SKILL.md's writes, word for word (steps 6 and 7), with <random> as RANDOM.
GOLDEN_CREATE_ENV = ["gcloud", "projects", "create", "aleogr-dev-demo-RANDOM",
                     "--folder=222222222222", "--name=dev demo",
                     "--labels=aleogr-project=demo,aleogr-environment=dev"]
GOLDEN_CREATE_SHARED = ["gcloud", "projects", "create", "aleogr-shared-RANDOM",
                        "--organization=111111111111", "--name=shared",
                        "--labels=aleogr-project=shared,aleogr-platform=shared"]
GOLDEN_LINK = ("gcloud billing projects link {p} --billing-account=0X0X0X-0X0X0X-0X0X0X")

ENV = {"project": "demo", "environment": "dev"}
SHARED = {"project": "shared", "platform": "shared"}


def missing():
    return {"aleogr-result": 1, "status": "unchanged", "answer": [],
            "outputs": {"exists": False, "projectId": None, "billingLinked": False}}


def existing(linked, project_id="aleogr-dev-demo-ab12", parent="folders/222222222222"):
    return {"aleogr-result": 1, "status": "unchanged", "answer": [],
            "outputs": {"exists": True, "projectId": project_id, "billingLinked": linked,
                        "parent": parent}}


def discovery(shared=False, search="", accounts="billingAccounts/0X0X0X-0X0X0X-0X0X0X\n"):
    answers = {ORG: OK(0, "organizations/111111111111\n", ""), ACCOUNTS: OK(0, accounts, "")}
    if shared:
        answers[SEARCH_ORG] = OK(0, search, "")
    else:
        answers[FOLDER] = OK(0, "folders/222222222222\n", "")
        answers[SEARCH_FOLDER] = OK(0, search, "")
    return answers


def verified(project_id):
    return {"gcloud projects describe %s --format=value(lifecycleState)" % project_id:
            OK(0, "ACTIVE\n", ""),
            "gcloud billing projects describe %s --format=value(billingEnabled)" % project_id:
            OK(0, "True\n", "")}


class FakeContext(common.Context):
    def __init__(self, args, found, answers, write_codes=(), read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.found = found
        self.answers = answers
        self.write_codes = list(write_codes)
        self.called = []
        self.reads = []
        self.writes = []

    def call(self, command, name, args=None, timeout=None):
        self.called.append((command, name, dict(args or {})))
        return self.found

    def execute(self, argv, timeout=None):
        # Reached only through ctx.write, after the allowlist of writes accepted argv.
        self.writes.append(list(argv))
        code = self.write_codes.pop(0) if self.write_codes else 0
        if code == 0 and argv[1] == "projects" and argv[2] == "create":
            self.answers.update(verified(argv[3]))
        return OK(code, "", "ERROR: (gcloud) Operation did not complete" if code else "")

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.reads.append(line)
        return self.answers.get(line, OK(1, "", "ERROR"))


def run(args, found=None, answers=None, write_codes=(), mode="apply"):
    args = dict(args)
    if mode is not None:
        args["mode"] = mode
    ctx = FakeContext(args, found if found is not None else missing(),
                      answers if answers is not None else discovery(args.get("platform")),
                      write_codes)
    return skill.run(dict(args), ctx), ctx


def random_part(project_id):
    return project_id.rsplit("-", 1)[-1]


class TestGoldenCommands(unittest.TestCase):
    def test_create_and_link_in_an_environment_s_folder(self):
        r, ctx = run(ENV)
        self.assertEqual(r.status, "created")
        self.assertEqual(len(ctx.writes), 2)
        create, link = ctx.writes
        rnd = random_part(create[3])
        self.assertRegex(rnd, r"^[a-z0-9]{4}$")
        self.assertEqual(create, [a.replace("RANDOM", rnd) for a in GOLDEN_CREATE_ENV])
        self.assertEqual(link, GOLDEN_LINK.format(p=create[3]).split(" "))
        for argv in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))
        self.assertEqual(r.block["outputs"], {"projectId": create[3]})
        self.assertEqual(ctx.called, [(PLUGIN, "gcp_environment-describe", ENV)])
        # The reads, in the SKILL.md's order, the verification after the link.
        self.assertEqual(ctx.reads, [ORG, FOLDER, SEARCH_FOLDER, ACCOUNTS] + list(
            verified(create[3])))

    def test_create_and_link_the_shared_project(self):
        r, ctx = run(SHARED)
        self.assertEqual(r.status, "created")
        create, link = ctx.writes
        rnd = random_part(create[3])
        self.assertEqual(create, [a.replace("RANDOM", rnd) for a in GOLDEN_CREATE_SHARED])
        self.assertEqual(link, GOLDEN_LINK.format(p=create[3]).split(" "))
        self.assertEqual(ctx.reads[:3], [ORG, SEARCH_ORG, ACCOUNTS])
        self.assertEqual(r.block["resources"][0]["labels"],
                         {"aleogr-project": "shared", "aleogr-platform": "shared"})

    def test_root_tst_creates_in_the_folder_inside_tst(self):
        answers = discovery()
        del answers[FOLDER]
        answers[TST] = OK(0, "folders/333333333333\n", "")
        answers[IN_TST] = OK(0, "folders/444444444444\n", "")
        answers[SEARCH_FOLDER.replace("222222222222", "444444444444")] = OK(0, "", "")
        r, ctx = run(dict(ENV, root="tst"), answers=answers)
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes[0][4], "--folder=444444444444")
        self.assertNotIn("444444444444", str(r.block))

    def test_the_repair_links_only(self):
        answers = {ACCOUNTS: OK(0, "billingAccounts/0X0X0X-0X0X0X-0X0X0X\n", "")}
        answers.update(verified("aleogr-dev-demo-ab12"))
        r, ctx = run(ENV, found=existing(False), answers=answers)
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [GOLDEN_LINK.format(p="aleogr-dev-demo-ab12").split(" ")])
        self.assertEqual(ctx.reads[0], ACCOUNTS)


class TestGate(unittest.TestCase):
    """mode=apply is the gate: without it no write is built, and a plan reads only."""

    def test_the_gate_absent(self):
        r, ctx = run(ENV, mode=None)
        self.assertEqual((r.status, r.block["mode"]), ("would-create", "plan"))
        self.assertEqual(ctx.writes, [])
        self.assertEqual(r.block["outputs"], {"projectId": None})
        self.assertEqual(r.block["resources"][0]["id"], "aleogr-dev-demo-xxxx")
        self.assertNotIn("111111111111", "\n".join(r.lines))
        self.assertNotIn("0X0X0X", "\n".join(r.lines))

    def test_the_gate_with_another_value(self):
        for mode in ("plan", "yes", "APPLY", ""):
            with self.subTest(mode=mode):
                r, ctx = run(ENV, mode=mode)
                self.assertEqual(ctx.writes, [])
                if mode == "plan":
                    self.assertEqual(r.status, "would-create")
                else:
                    self.assertEqual(r.status, "failed")
                    self.assertEqual(r.lines, ["mode must be plan or apply."])
                    self.assertEqual((ctx.called, ctx.reads), ([], []))

    def test_a_plan_of_a_repair_writes_nothing(self):
        r, ctx = run(ENV, found=existing(False), mode="plan",
                     answers={ACCOUNTS: OK(0, "billingAccounts/0X0X0X-0X0X0X-0X0X0X\n", "")})
        self.assertEqual((r.status, ctx.writes), ("would-update", []))

    def test_read_only_refuses_the_writes(self):
        ctx = FakeContext(dict(ENV, mode="apply"), missing(), discovery(), read_only=True)
        self.assertFalse(ctx.writable)
        with self.assertRaises(common.WriteRefused):
            ctx.write(GOLDEN_LINK.format(p="aleogr-dev-demo-ab12").split(" "))
        self.assertEqual(ctx.writes, [])

    def test_validation_builds_nothing(self):
        cases = [
            ({"environment": "dev"}, "project is missing."),
            ({"project": "demo"}, "environment is missing."),
            ({"project": "demo", "environment": "qa"}, "environment must be dev, hom or prd."),
            ({"project": "test", "environment": "dev"}, "project must not be test or shared."),
            ({"project": "shared", "environment": "dev"}, "project must not be test or shared."),
            ({"project": "a" * 15, "environment": "dev"}, None),
            ({"project": "demo-", "environment": "dev"}, None),
            ({"project": "demo", "platform": "shared"}, "platform=shared needs project=shared."),
            ({"project": "shared", "platform": "shared", "environment": "dev"},
             "platform=shared takes no environment."),
            ({"project": "shared", "platform": "shared", "root": "tst"},
             "root is not allowed with platform=shared."),
            ({"project": "demo", "environment": "dev", "root": "sandbox"},
             "root must be absent or tst."),
            ({"project": "demo", "environment": "dev", "platform": "x"},
             "platform must be absent or shared."),
        ]
        for args, sentence in cases:
            with self.subTest(args=args):
                r, ctx = run(args)
                self.assertEqual(r.status, "failed")
                self.assertEqual((ctx.called, ctx.reads, ctx.writes), ([], [], []))
                self.assertEqual(r.block["outputs"], {"projectId": None})
                self.assertEqual(r.block["resources"], [])
                if sentence:
                    self.assertEqual(r.lines, [sentence])
                else:
                    self.assertIn("14", r.lines[0])


class TestWriteShapesInBothModes(unittest.TestCase):
    """An identifier read from Google Cloud that the allowlist of writes does not take
    ends the run failed, before any write, in plan as in apply."""

    def test_a_billing_account_of_another_form(self):
        for mode in ("plan", "apply"):
            with self.subTest(mode=mode):
                r, ctx = run(ENV, mode=mode, answers=discovery(
                    accounts="billingAccounts/not-an-account\n"))
                self.assertEqual(r.status, "failed")
                self.assertEqual(r.lines, [skill.UNUSABLE])
                self.assertEqual(ctx.writes, [])

    def test_a_folder_id_of_another_form(self):
        answers = discovery()
        answers[FOLDER] = OK(0, "folders/abc\n", "")
        answers[SEARCH_FOLDER.replace("222222222222", "abc")] = OK(0, "", "")
        r, ctx = run(ENV, answers=answers)
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertEqual(r.lines, [skill.UNUSABLE])

    def test_a_repair_with_an_account_of_another_form(self):
        r, ctx = run(ENV, found=existing(False), answers={ACCOUNTS: OK(0, "x/y\n", "")})
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertEqual(r.block["outputs"], {"projectId": None})


class TestPaths(unittest.TestCase):
    def test_existing_with_billing_runs_nothing_else(self):
        r, ctx = run(ENV, found=existing(True), answers={})
        self.assertEqual((r.status, ctx.reads, ctx.writes), ("unchanged", [], []))
        self.assertEqual(r.block["outputs"], {"projectId": "aleogr-dev-demo-ab12"})

    def test_the_describe_failed(self):
        failed = {"aleogr-result": 1, "status": "failed", "outputs": {"exists": None},
                  "answer": ["The GCP projects could not be listed: gcloud failed."]}
        r, ctx = run(ENV, found=failed)
        self.assertEqual((r.status, r.lines), ("failed", failed["answer"]))
        self.assertEqual((ctx.reads, ctx.writes), ([], []))

    def test_several_organizations_or_folders(self):
        answers = discovery()
        answers[ORG] = OK(0, "organizations/1\norganizations/2\n", "")
        r, ctx = run(ENV, answers=answers)
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertIn("2 organizations were found", r.lines[0])
        self.assertNotIn("organizations/1", r.lines[0])
        answers = discovery()
        answers[FOLDER] = OK(0, "folders/1\nfolders/2\n", "")
        r, ctx = run(ENV, answers=answers)
        self.assertIn("2 folders dev were found", r.lines[0])

    def test_no_folder(self):
        answers = discovery()
        answers[FOLDER] = OK(0, "", "")
        r, ctx = run(ENV, answers=answers)
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertIn("folder dev must be created first", r.lines[0])

    def test_the_search_by_parent_fails(self):
        answers = discovery()
        answers[SEARCH_FOLDER] = OK(1, "", "ERROR: PERMISSION_DENIED")
        r, ctx = run(ENV, answers=answers)
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertNotIn("PERMISSION_DENIED", r.lines[0])
        self.assertNotIn(ACCOUNTS, ctx.reads)

    def test_found_by_parent_without_billing_is_repaired(self):
        answers = discovery(search="aleogr-dev-demo-ab12\n")
        answers["gcloud billing projects describe aleogr-dev-demo-ab12 "
                "--format=value(billingEnabled)"] = OK(0, "False\n", "")
        r, ctx = run(ENV, answers=answers)
        self.assertEqual(r.status, "pending")  # the verification reads False again
        self.assertEqual(ctx.writes,
                         [GOLDEN_LINK.format(p="aleogr-dev-demo-ab12").split(" ")])
        self.assertEqual(r.lines[0], skill.PARENT_FOUND % "aleogr-dev-demo-ab12")

    def test_a_failed_create_that_left_nothing(self):
        r, ctx = run(ENV, write_codes=[1])
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.lines, [skill.CREATE_FAILED])
        self.assertEqual(len(ctx.writes), 1)
        self.assertEqual(r.block["outputs"], {"projectId": None})
        self.assertNotIn("Operation", "\n".join(r.lines))

    def test_a_failed_create_with_a_project_not_active(self):
        class Ctx(FakeContext):
            def read(self, argv, timeout=None):
                if argv[1:3] == ["projects", "describe"]:
                    self.reads.append(" ".join(argv))
                    return OK(0, "DELETE_REQUESTED\n", "")
                return FakeContext.read(self, argv)
        args = dict(ENV, mode="apply")
        ctx = Ctx(args, missing(), discovery(), write_codes=[1])
        r = skill.run(args, ctx)
        self.assertEqual(r.status, "pending")
        self.assertEqual(len(ctx.writes), 1)
        how = r.block["pending"][0]["how"]
        self.assertRegex(how, r'^gcloud projects describe aleogr-dev-demo-[a-z0-9]{4} '
                              r'--format="value\(lifecycleState\)"$')

    def test_a_refused_link_is_pending_with_the_command(self):
        r, ctx = run(ENV, write_codes=[0, 1])
        self.assertEqual(r.status, "pending")
        pid = ctx.writes[0][3]
        self.assertEqual(r.block["pending"][0]["how"], GOLDEN_LINK.format(p=pid))
        self.assertEqual(r.block["outputs"], {"projectId": pid})
        self.assertEqual(len(r.block["resources"]), 1)

    def test_a_verification_that_fails_is_pending(self):
        class Ctx(FakeContext):
            def read(self, argv, timeout=None):
                if argv[1:4] == ["billing", "projects", "describe"]:
                    self.reads.append(" ".join(argv))
                    return OK(0, "False\n", "")
                return FakeContext.read(self, argv)
        args = dict(ENV, mode="apply")
        ctx = Ctx(args, missing(), discovery())
        r = skill.run(args, ctx)
        self.assertEqual(r.status, "pending")
        self.assertIn('--format="value(billingEnabled)"', r.block["pending"][0]["how"])

    def test_no_identifier_in_the_block(self):
        r, ctx = run(ENV)
        text = str(r.block) + "\n".join(r.lines)
        for ident in ("111111111111", "222222222222", "0X0X0X"):
            self.assertNotIn(ident, text)

    def test_lifecycle_state(self):
        self.assertEqual(skill.lifecycle_state(OK(0, "ACTIVE\n", "")), "ACTIVE")
        self.assertEqual(skill.lifecycle_state(OK(0, '{"lifecycleState": "ACTIVE"}', "")),
                         "ACTIVE")
        self.assertEqual(skill.lifecycle_state(OK(0, '{"name": "x"}', "")), "")


class TestSkillText(unittest.TestCase):
    def test_the_sentences_the_skill_writes(self):
        with open(SKILL_MD, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("`%s`" % skill.CREATE_FAILED, text)
        self.assertIn("`%s`" % (skill.PARENT_FOUND % "<projectId>"), text)
        self.assertIn("`%s`" % (skill.CREATED_BUT % "<projectId>"), text)
        # The golden writes are the SKILL.md's, quotes removed.
        self.assertIn('gcloud projects create <projectId> --folder=<id> --name="<environment> '
                      '<project>" --labels="aleogr-project=<project>,aleogr-environment='
                      '<environment>"', text)
        self.assertIn('gcloud projects create <projectId> --organization=<id> --name="shared" '
                      '--labels="aleogr-project=shared,aleogr-platform=shared"', text)
        self.assertIn("gcloud billing projects link <projectId> --billing-account=<id>", text)



class TimeLimitContext(FakeContext):
    """The run's time limit is reached while its `at`-th write is still running, or
    (`at` 0) while the first read after the writes is."""

    def __init__(self, at):
        args = dict(ENV, mode="apply")
        FakeContext.__init__(self, args, missing(), discovery())
        self.at = at

    def execute(self, argv, timeout=None):
        if len(self.writes) + 1 == self.at:
            self.writes.append(list(argv))
            raise common.TimeLimit(argv)
        return FakeContext.execute(self, argv, timeout)

    def read(self, argv, timeout=None):
        if self.at == 0 and len(self.writes) == 2:
            raise common.TimeLimit(argv)
        return FakeContext.read(self, argv, timeout)


class TestAborted(unittest.TestCase):
    def aborted(self, at):
        ctx = TimeLimitContext(at)
        r, code, why = common.run_skill(skill, dict(ENV, mode="apply"), ctx)
        self.assertEqual((code, why), (common.EXIT_SOFTWARE, "time limit reached"))
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.block["cost"], common.ABORTED_COST)
        self.assertEqual((r.lines[0], r.lines[-1]),
                         (common.TIME_LIMIT_SENTENCE, common.READ_STATE_SENTENCE))
        return r, ctx

    def test_after_the_create_the_project_exists(self):
        for at in (2, 0):  # the link, then the verification
            with self.subTest(at=at):
                r, ctx = self.aborted(at)
                project_id = ctx.writes[0][3]
                self.assertEqual(r.lines[2:-1], [
                    "The GCP project %s now exists; running this skill again with the same "
                    "arguments goes on from it." % project_id])
                self.assertIn("projects create %s" % project_id, r.lines[1])

    def test_the_create_itself_is_still_running(self):
        r, ctx = self.aborted(1)
        self.assertEqual(len(ctx.writes), 1)
        self.assertEqual(len(r.lines), 3)
        self.assertNotIn("now exists", "\n".join(r.lines))


if __name__ == "__main__":
    unittest.main()
