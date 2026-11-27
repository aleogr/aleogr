"""Unit tests of gcp_budget-alert-setup: its golden commands, its gate (nothing is created
or updated without mode=apply), the check of the writes against the allowlist in both
modes, the retry of the list (two waits) and the wait budget, and the paths no scenario
covers. The scenarios budget-* cover the rest, in the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_budget-alert-setup"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

OK = common.Completed
B = "0X0X0X-0X0X0X-0X0X0X"
Q = "aleogr-shared-zz99"
BUDGET = "b1b1b1b1-0000-4000-8000-000000000001"
ARGS = {"displayName": "aleogr", "amount": "100", "currency": "BRL",
        "thresholds": "0.5,0.9,1.0", "quotaProject": Q}
ACCOUNTS = "gcloud billing accounts list --filter=open=true --format=value(name)"
LIST = ("gcloud billing budgets list --billing-account=%s --billing-project=%s "
        "--format=value(displayName,name)" % (B, Q))
DESCRIBE = ("gcloud billing budgets describe %s --billing-account=%s --billing-project=%s "
            "--format=json" % (BUDGET, B, Q))

# The SKILL.md's writes, word for word (step 3 and step d).
GOLDEN_CREATE = ("gcloud billing budgets create --billing-account=%s --display-name=aleogr "
                 "--budget-amount=100BRL --threshold-rule=percent=0.5 "
                 "--threshold-rule=percent=0.9 --threshold-rule=percent=1.0 "
                 "--billing-project=%s" % (B, Q))
GOLDEN_UPDATE = ("gcloud billing budgets update %s --billing-account=%s --budget-amount=100BRL "
                 "--clear-threshold-rules --add-threshold-rule=percent=0.5 "
                 "--add-threshold-rule=percent=0.9 --add-threshold-rule=percent=1.0 "
                 "--billing-project=%s" % (BUDGET, B, Q))


def budget(units="100", currency="BRL", thresholds=(0.5, 0.9, 1.0), nanos=None):
    spec = {"currencyCode": currency, "units": units}
    if nanos is not None:
        spec["nanos"] = nanos
    return OK(0, json.dumps({"amount": {"specifiedAmount": spec},
                             "thresholdRules": [{"thresholdPercent": t} for t in thresholds]}),
              "")


class FakeContext(common.Context):
    """read() answers each command from a list of answers, one per call (the last one
    repeats)."""

    def __init__(self, args, answers, write_codes=(), after_write=None, read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        self.answers = answers
        self.after_write = after_write or {}
        self.write_codes = list(write_codes)
        self.reads, self.writes = [], []

    def execute(self, argv, timeout=None):
        self.writes.append(list(argv))
        code = self.write_codes.pop(0) if self.write_codes else 0
        if code == 0:
            self.answers.update(self.after_write)
        return OK(code, "", "ERROR: PERMISSION_DENIED" if code else "")

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.reads.append(line)
        if argv[0] == "sleep":
            return OK(0, "", "")
        a = self.answers.get(line, OK(1, "", "ERROR"))
        if isinstance(a, list):
            return a.pop(0) if len(a) > 1 else a[0]
        return a


def run(answers=None, mode="apply", write_codes=(), after_write=None, **over):
    common.reset_wait_budget()
    args = dict(ARGS, **over)
    if mode is not None:
        args["mode"] = mode
    args = {k: v for k, v in args.items() if v is not None}
    if answers is None:
        answers = {ACCOUNTS: OK(0, "billingAccounts/%s\n" % B, ""), LIST: OK(0, "", "")}
    if after_write is None:
        after_write = {LIST: OK(0, "aleogr\tbillingAccounts/%s/budgets/new\n" % B, "")}
    ctx = FakeContext(args, answers, write_codes, after_write)
    return skill.run(dict(args), ctx), ctx


def existing_answers(held):
    return {ACCOUNTS: OK(0, "billingAccounts/%s\n" % B, ""),
            LIST: OK(0, "other\tbillingAccounts/%s/budgets/x\naleogr\tbillingAccounts/%s/"
                        "budgets/%s\n" % (B, B, BUDGET), ""),
            DESCRIBE: held}


class TestGoldenCommands(unittest.TestCase):
    def test_the_create_and_its_verification(self):
        r, ctx = run()
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.writes, [GOLDEN_CREATE.split(" ")])
        self.assertEqual(ctx.reads, [ACCOUNTS, LIST, LIST])
        self.assertIsNone(common.write_refusal(SKILL, ctx.writes[0], root=ROOT))
        self.assertEqual(r.block["outputs"], {"displayName": "aleogr", "amount": 100,
                                              "currency": "BRL", "thresholds": [0.5, 0.9, 1.0],
                                              "compared": None})

    def test_the_update_and_its_verification(self):
        r, ctx = run(answers=existing_answers(budget(units="80")),
                     after_write={DESCRIBE: budget()})
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [GOLDEN_UPDATE.split(" ")])
        self.assertEqual(ctx.reads, [ACCOUNTS, LIST, DESCRIBE, DESCRIBE])
        self.assertIsNone(common.write_refusal(SKILL, ctx.writes[0], root=ROOT))
        self.assertEqual(r.block["outputs"]["compared"], True)


class TestGate(unittest.TestCase):
    def test_the_gate_absent(self):
        r, ctx = run(mode=None)
        self.assertEqual((r.status, r.block["mode"], ctx.writes), ("would-create", "plan", []))
        self.assertEqual(r.block["resources"], [])
        r, ctx = run(mode=None, answers=existing_answers(budget(units="80")))
        self.assertEqual((r.status, ctx.writes), ("would-update", []))
        self.assertEqual(r.block["outputs"]["differs"], ["amount 80 → 100"])

    def test_the_gate_with_another_value(self):
        for mode in ("plan", "yes", "APPLY", ""):
            with self.subTest(mode=mode):
                r, ctx = run(mode=mode)
                self.assertEqual(ctx.writes, [])
                if mode != "plan":
                    self.assertEqual((r.status, r.lines),
                                     ("failed", ["mode must be plan or apply."]))
                    self.assertEqual(ctx.reads, [])

    def test_a_plan_does_not_retry_the_list(self):
        answers = {ACCOUNTS: OK(0, "billingAccounts/%s\n" % B, ""), LIST: OK(1, "", "ERROR")}
        r, ctx = run(mode="plan", answers=answers)
        self.assertEqual((r.status, ctx.reads), ("failed", [ACCOUNTS, LIST]))

    def test_read_only_refuses_the_writes(self):
        ctx = FakeContext(dict(ARGS, mode="apply"), {}, read_only=True)
        with self.assertRaises(common.WriteRefused):
            ctx.write(GOLDEN_CREATE.split(" "))
        self.assertEqual(ctx.writes, [])

    def test_validation_builds_nothing(self):
        cases = [({k: None}, "%s is missing." % k) for k in skill.REQUIRED] + [
            ({"displayName": "my budget"}, None), ({"displayName": "-x"}, None),
            ({"displayName": "a" * 61}, None),
            ({"amount": "0"}, "amount must be a number greater than 0."),
            ({"amount": "-5"}, "amount must be a number greater than 0."),
            ({"amount": "ten"}, "amount must be a number greater than 0."),
            ({"amount": "inf"}, "amount must be a number greater than 0."),
            ({"currency": "brl"}, "currency must be three uppercase letters."),
            ({"thresholds": "0.5,1.5"}, None), ({"thresholds": "0"}, None),
            ({"thresholds": "0.5,"}, None),
            ({"quotaProject": "Bad"}, None),
        ]
        for over, sentence in cases:
            with self.subTest(over=over):
                r, ctx = run(**over)
                self.assertEqual(r.status, "failed")
                self.assertEqual((ctx.reads, ctx.writes), ([], []))
                self.assertEqual(r.block["outputs"], skill.FAILED_OUTPUTS)
                self.assertEqual(r.block["resources"], [])
                if sentence:
                    self.assertEqual(r.lines, [sentence])
                else:
                    self.assertTrue(r.lines[0].startswith(list(over)[0]), r.lines)


class TestWriteShapesInBothModes(unittest.TestCase):
    def test_numbers_the_allowlist_does_not_take(self):
        # A number by the SKILL.md's rule, but not in the form of the budget command.
        for over in ({"amount": "1e3"}, {"thresholds": ".5"}, {"thresholds": "5e-1"}):
            for mode in ("plan", "apply"):
                with self.subTest(over=over, mode=mode):
                    r, ctx = run(mode=mode, **over)
                    self.assertEqual((r.status, r.lines, ctx.writes),
                                     ("failed", [skill.UNUSABLE], []))

    def test_an_update_with_a_billing_account_of_another_form(self):
        answers = existing_answers(budget(units="80"))
        answers[ACCOUNTS] = OK(0, "billingAccounts/odd_account\n", "")
        answers[LIST.replace(B, "odd_account")] = answers[LIST]
        answers[DESCRIBE.replace(B, "odd_account")] = answers[DESCRIBE]
        for mode in ("plan", "apply"):
            with self.subTest(mode=mode):
                r, ctx = run(mode=mode, answers=dict(answers))
                self.assertEqual((r.status, r.lines, ctx.writes),
                                 ("failed", [skill.UNUSABLE], []))


class TestWaits(unittest.TestCase):
    def test_one_retry_after_two_waits(self):
        answers = {ACCOUNTS: OK(0, "billingAccounts/%s\n" % B, ""),
                   LIST: [OK(1, "", "ERROR"), OK(0, "", "")]}
        r, ctx = run(answers=answers)
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.reads, [ACCOUNTS, LIST, "sleep 30", "sleep 30", LIST, LIST])

    def test_a_second_failure_is_failed(self):
        answers = {ACCOUNTS: OK(0, "billingAccounts/%s\n" % B, ""), LIST: OK(1, "", "ERROR")}
        r, ctx = run(answers=answers)
        self.assertEqual((r.status, ctx.writes), ("failed", []))
        self.assertEqual(ctx.reads.count(LIST), 2)
        self.assertNotIn("ERROR", "\n".join(r.lines))

    def test_the_wait_budget_spent(self):
        answers = {ACCOUNTS: OK(0, "billingAccounts/%s\n" % B, ""), LIST: OK(1, "", "ERROR")}
        common.reset_wait_budget()
        args = dict(ARGS, mode="apply")
        ctx = FakeContext(args, answers)
        while common.wait_allowed():
            ctx.wait()
        n = len(ctx.reads)
        r = skill.run(dict(args), ctx)
        self.assertEqual(r.status, "pending")
        self.assertIn(common.WAIT_BUDGET_SENTENCE, r.lines)
        self.assertEqual(r.block["pending"], [common.wait_budget_item(SKILL)])
        self.assertEqual(ctx.reads[n:], [ACCOUNTS, LIST])
        self.assertEqual(ctx.writes, [])
        common.reset_wait_budget()


class TestPaths(unittest.TestCase):
    def test_ambiguous_billing_names_no_identifier(self):
        answers = {ACCOUNTS: OK(0, "billingAccounts/%s\nbillingAccounts/1Y1Y1Y-1Y1Y1Y-1Y1Y1Y\n"
                                % B, "")}
        r, ctx = run(answers=answers)
        self.assertEqual((r.status, ctx.reads), ("failed", [ACCOUNTS]))
        self.assertIn("2 open billing accounts", r.lines[0])
        self.assertNotIn(B, r.lines[0])

    def test_a_failed_create(self):
        r, ctx = run(write_codes=[1])
        self.assertEqual((r.status, ctx.reads), ("failed", [ACCOUNTS, LIST]))
        self.assertNotIn("PERMISSION", "\n".join(r.lines))

    def test_a_create_not_confirmed(self):
        r, ctx = run(after_write={LIST: OK(0, "other\n", "")})
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.block["pending"][0]["how"],
                         'gcloud billing budgets list --billing-account=%s --billing-project=%s '
                         '--format="value(displayName,name)"' % (B, Q))
        self.assertNotIn(B, "\n".join(r.lines))
        self.assertNotIn(B, json.dumps(r.block["outputs"]))

    def test_equal_budgets(self):
        for held in (budget(), budget(thresholds=(1, 0.9, 0.5)),
                     budget(units="99", nanos=1000000000)):
            with self.subTest(held=held.out):
                r, ctx = run(answers=existing_answers(held))
                self.assertEqual((r.status, ctx.writes), ("unchanged", []))
                self.assertEqual(r.block["outputs"]["compared"], True)
                self.assertNotIn(BUDGET, str(r.block) + "\n".join(r.lines))

    def test_what_differs(self):
        r, _ = run(mode="plan", answers=existing_answers(
            budget(units="150", currency="USD", thresholds=(0.5,))))
        self.assertEqual(r.block["outputs"]["differs"], [
            "amount 150 → 100", "currency USD → BRL",
            "thresholds 0.5 → 0.5, 0.9, 1"])

    def test_cannot_be_compared(self):
        for held, what in ((OK(1, "", "ERROR"), "could not be read"),
                           (OK(0, "", ""), "was empty"),
                           (OK(0, "{}", ""), "its amount was not found"),
                           (OK(0, json.dumps({"amount": {"specifiedAmount": {"units": "1"}}}), ""),
                            "its currency was not found"),
                           (budget(thresholds=()), "its thresholds were not found")):
            with self.subTest(what=what):
                r, ctx = run(answers=existing_answers(held))
                self.assertEqual((r.status, ctx.writes), ("unchanged", []))
                self.assertEqual(r.block["outputs"]["compared"], False)
                self.assertIn(what, r.lines[-1])

    def test_an_update_that_still_differs(self):
        r, ctx = run(answers=existing_answers(budget(units="80")),
                     after_write={DESCRIBE: budget(units="80")})
        self.assertEqual(r.status, "pending")
        self.assertIn("amount 80 → 100", r.block["pending"][0]["how"])
        self.assertNotIn(BUDGET, json.dumps(r.block))
        self.assertNotIn(B, json.dumps(r.block))

    def test_a_failed_update_is_not_read_again(self):
        r, ctx = run(answers=existing_answers(budget(units="80")), write_codes=[1])
        self.assertEqual(r.status, "failed")
        self.assertEqual(ctx.reads.count(DESCRIBE), 1)


if __name__ == "__main__":
    unittest.main()
