"""Unit tests of gcp_login-setup: its golden commands, its gate (no role is granted and
no API enabled without mode=apply), the check of the grant against the allowlist in
both modes, the poll after the grant (at most 10 reads, 9 waits) and a wait that cannot
run, the list of what is left (byte for byte the SKILL.md's), and that no secret, client
id, organization id or e-mail reaches the answer or the block. The scenarios
login-setup-* cover the rest, in the direct mode.
"""

import os
import re
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_login-setup"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

OK = common.Completed
P = "aleogr-shared-ab12"
ORG_ID = "111111111111"
EMAIL = "demo-user@example.com"
MEMBER = "user:" + EMAIL
CLIENT = "123456789012-abc.apps.googleusercontent.com"

ORG = "gcloud organizations list --format=value(name)"
ACCOUNT = "gcloud config get-value account"
POLICY = ("gcloud organizations get-iam-policy %s --flatten=bindings[].members "
          "--filter=bindings.role=roles/iap.settingsAdmin AND bindings.members=%s "
          "--format=value(bindings.members)" % (ORG_ID, MEMBER))
API = ("gcloud services list --enabled --project=%s --filter=config.name=iap.googleapis.com "
       "--format=value(config.name)" % P)
SETTINGS = ("gcloud iap settings get --organization=%s --billing-project=%s --format=json"
            % (ORG_ID, P))

# The SKILL.md's writes, word for word (step 7), quotes removed.
GOLDEN_GRANT = ("gcloud organizations add-iam-policy-binding %s --member=%s "
                "--role=roles/iap.settingsAdmin --condition=None --quiet" % (ORG_ID, MEMBER))
GOLDEN_ENABLE = "gcloud services enable iap.googleapis.com --project=" + P

PREPARED = OK(0, '{"accessSettings": {"oauthSettings": {"clientId": "%s", '
                 '"clientSecretSha256": "0f1e"}}, "name": "organizations/%s"}'
              % (CLIENT, ORG_ID), "")
NOT_PREPARED = OK(0, '{"name": "organizations/%s"}' % ORG_ID, "")
DENIED = OK(1, "", "ERROR: PERMISSION_DENIED: Permission denied. reason: IAM_PERMISSION_DENIED")
DISABLED = OK(1, "", "ERROR: PERMISSION_DENIED: API disabled. reason: SERVICE_DISABLED")
NOT_FOUND = OK(1, "", "ERROR: NOT_FOUND: no settings")


class FakeContext(common.Context):
    """read() answers SETTINGS from a list, one per call (the last one repeats)."""

    def __init__(self, args, role=False, api=False, settings=(DENIED,), write_codes=(),
                 read_only=False, account=EMAIL):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                args.get("mode") or skill.DEFAULT_MODE, args,
                                read_only=read_only)
        member = skill.member_of(account)
        self.answers = {
            ORG: OK(0, "organizations/%s\n" % ORG_ID, ""),
            ACCOUNT: OK(0, account + "\n", ""),
            POLICY.replace(MEMBER, member): OK(0, (member + "\n") if role else "", ""),
            API: OK(0, "iap.googleapis.com\n" if api else "", ""),
        }
        self.settings = list(settings)
        self.write_codes = list(write_codes)
        self.reads, self.writes = [], []

    def execute(self, argv, timeout=None):
        self.writes.append(list(argv))
        code = self.write_codes.pop(0) if self.write_codes else 0
        return OK(code, "", "ERROR: does not have permission setIamPolicy" if code else "")

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        line = " ".join(argv)
        self.reads.append(line)
        if argv[0] == "sleep":
            return OK(0, "", "")
        if line == SETTINGS:
            return self.settings.pop(0) if len(self.settings) > 1 else self.settings[0]
        return self.answers.get(line, OK(1, "", "ERROR"))


def run(mode="apply", **kw):
    common.reset_wait_budget()
    args = {"projectId": P}
    if mode is not None:
        args["mode"] = mode
    ctx = FakeContext(args, **kw)
    r = skill.run(dict(args), ctx)
    return r, ctx


def answer_text(r):
    return "\n".join(r.lines) + "\n" + common.render_block(r.block)


def block_text(r):
    return common.render_block(r.block)


class TestGoldenCommands(unittest.TestCase):
    def test_the_grant_and_the_enable(self):
        r, ctx = run(settings=(DENIED, NOT_PREPARED))
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [GOLDEN_GRANT.split(" "), GOLDEN_ENABLE.split(" ")])
        for argv in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))
        self.assertEqual(ctx.reads, [ORG, ACCOUNT, POLICY, API, SETTINGS, SETTINGS])
        self.assertEqual(r.block["outputs"]["prepared"], False)
        self.assertEqual((r.block["outputs"]["roleGranted"], r.block["outputs"]["apiEnabled"]),
                         (True, True))

    def test_a_service_account_is_granted_as_one(self):
        sa = "deployer@%s.iam.gserviceaccount.com" % P
        r, ctx = run(settings=(NOT_PREPARED,), api=True, account=sa)
        self.assertEqual(ctx.writes[0][4], "--member=serviceAccount:" + sa)
        self.assertIsNone(common.write_refusal(SKILL, ctx.writes[0], root=ROOT))

    def test_the_commands_are_the_skill_s(self):
        with open(os.path.join(ROOT, "skills", SKILL, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        written = (GOLDEN_GRANT.replace(ORG_ID, "<organizationId>")
                   .replace("--member=" + MEMBER, '--member="<member>"')
                   .replace("--role=roles/iap.settingsAdmin", '--role="roles/iap.settingsAdmin"'))
        self.assertIn(written, text)
        self.assertIn(GOLDEN_ENABLE.replace(P, "<projectId>"), text)


class TestGate(unittest.TestCase):
    def test_the_gate_absent(self):
        r, ctx = run(mode=None, settings=(DENIED,))
        self.assertEqual((r.status, r.block["mode"], ctx.writes), ("would-update", "plan", []))
        self.assertEqual(r.block["outputs"], {"prepared": None, "roleGranted": True,
                                              "apiEnabled": True, "steps": []})
        self.assertEqual(r.block["pending"], [])
        self.assertNotIn("sleep 30", ctx.reads)

    def test_the_gate_with_another_value(self):
        for mode in ("plan", "yes", "APPLY", ""):
            with self.subTest(mode=mode):
                r, ctx = run(mode=mode, settings=(NOT_PREPARED,))
                self.assertEqual(ctx.writes, [])
                if mode == "plan":
                    self.assertEqual(r.status, "would-update")
                else:
                    self.assertEqual((r.status, r.lines), ("failed", [skill.MODE_INVALID]))
                    self.assertEqual(ctx.reads, [])

    def test_read_only_refuses_the_writes(self):
        ctx = FakeContext({"projectId": P, "mode": "apply"}, read_only=True)
        for argv in (GOLDEN_GRANT, GOLDEN_ENABLE):
            with self.assertRaises(common.WriteRefused):
                ctx.write(argv.split(" "))
        self.assertEqual(ctx.writes, [])

    def test_validation(self):
        for args, sentence in (({}, skill.PROJECT_MISSING),
                               ({"projectId": "Aleogr_Shared"}, skill.PROJECT_INVALID)):
            ctx = FakeContext(args)
            r = skill.run(args, ctx)
            self.assertEqual((r.status, r.lines, ctx.reads, ctx.writes),
                             ("failed", [sentence], [], []))
            self.assertEqual(r.block["outputs"], {"prepared": None, "roleGranted": False,
                                                  "apiEnabled": False, "steps": []})


class TestWriteShapesInBothModes(unittest.TestCase):
    def test_an_account_the_grant_cannot_name(self):
        for mode in ("plan", "apply"):
            with self.subTest(mode=mode):
                r, ctx = run(mode=mode, account="not an e-mail", settings=(NOT_PREPARED,))
                self.assertEqual((r.status, r.lines, ctx.writes),
                                 ("failed", [skill.UNUSABLE], []))

    def test_no_grant_needed_no_check(self):
        r, ctx = run(role=True, api=True, account="odd", settings=(NOT_PREPARED,))
        self.assertEqual((r.status, ctx.writes), ("pending", []))


class TestPoll(unittest.TestCase):
    def test_at_most_ten_reads_after_the_grant(self):
        r, ctx = run(settings=(DENIED,))
        self.assertEqual(ctx.reads.count(SETTINGS), 11)
        self.assertEqual(ctx.reads.count("sleep 30"), 9)
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.lines[-1], skill.AFTER_STILL_REFUSED)
        self.assertEqual(r.block["pending"], [skill.NOT_READ_ITEM])
        self.assertEqual(r.block["outputs"]["prepared"], None)

    def test_the_poll_ends_on_another_answer(self):
        r, ctx = run(settings=(DENIED, DENIED, DENIED, NOT_PREPARED))
        self.assertEqual((ctx.reads.count(SETTINGS), ctx.reads.count("sleep 30")), (4, 2))
        self.assertEqual(r.block["outputs"]["prepared"], False)
        self.assertEqual(r.block["pending"], [skill.login_item(P)])

    def test_a_wait_that_cannot_run(self):
        common.reset_wait_budget()
        args = {"projectId": P, "mode": "apply"}
        ctx = FakeContext(args, settings=(DENIED,))
        while common.wait_allowed():
            ctx.wait()
        r = skill.run(dict(args), ctx)
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.lines[-1], skill.AFTER_NO_WAIT)
        self.assertEqual(r.block["pending"], [skill.NOT_READ_ITEM])
        self.assertEqual(ctx.reads[-1], SETTINGS)  # one read after the change, no wait
        common.reset_wait_budget()

    def test_no_poll_when_this_run_did_not_grant(self):
        r, ctx = run(role=True, settings=(DISABLED, DENIED))
        self.assertEqual(ctx.writes, [GOLDEN_ENABLE.split(" ")])
        self.assertEqual(ctx.reads.count(SETTINGS), 2)
        self.assertNotIn("sleep 30", ctx.reads)
        self.assertEqual(r.lines[-1], skill.AFTER_FAILED)

    def test_service_disabled_after_the_change_is_never_polled(self):
        r, ctx = run(settings=(DENIED, DISABLED))
        self.assertEqual(ctx.reads.count(SETTINGS), 2)
        self.assertEqual(r.lines[-1], skill.AFTER_API_OFF % P)

    def test_a_client_after_the_change(self):
        r, ctx = run(settings=(DENIED, PREPARED))
        self.assertEqual((r.status, r.block["outputs"]["prepared"], r.block["pending"]),
                         ("updated", True, []))
        self.assertEqual(r.block["outputs"]["steps"], [])


class TestPaths(unittest.TestCase):
    def test_already_prepared_grants_nothing(self):
        r, ctx = run(settings=(PREPARED,))
        self.assertEqual((r.status, ctx.writes), ("unchanged", []))
        self.assertEqual(r.block["outputs"]["prepared"], True)
        self.assertNotIn(CLIENT, answer_text(r))

    def test_not_found_is_not_prepared(self):
        r, ctx = run(role=True, api=True, settings=(NOT_FOUND,))
        self.assertEqual((r.status, ctx.writes), ("pending", []))
        self.assertEqual(r.block["outputs"]["steps"], skill.steps_of(P))

    def test_a_refused_first_read_with_nothing_missing(self):
        r, ctx = run(role=True, api=True, settings=(DISABLED,))
        self.assertEqual((r.status, r.lines), ("failed", [skill.READ_API_OFF % P]))
        r, ctx = run(role=True, api=True, settings=(DENIED,))
        self.assertEqual((r.status, r.lines), ("failed", [skill.READ_FAILED]))

    def test_a_refused_grant(self):
        r, ctx = run(settings=(DENIED,), write_codes=[1])
        self.assertEqual((r.status, r.lines, len(ctx.writes)),
                         ("failed", [skill.GRANT_FAILED], 1))
        self.assertEqual(ctx.reads.count(SETTINGS), 1)

    def test_a_refused_enable_after_the_grant(self):
        r, ctx = run(settings=(DENIED,), write_codes=[0, 1])
        self.assertEqual(r.status, "updated")
        self.assertEqual(r.lines[-1], skill.ENABLE_FAILED_AFTER_GRANT % P)
        self.assertEqual(r.block["pending"], [skill.api_item(P)])
        self.assertEqual(ctx.reads.count(SETTINGS), 1)

    def test_a_refused_enable_alone(self):
        r, ctx = run(role=True, settings=(DISABLED,), write_codes=[1])
        self.assertEqual((r.status, r.lines), ("failed", [skill.ENABLE_FAILED_ALONE % P]))

    def test_the_first_reads(self):
        for answers, sentence in (({ORG: OK(1, "", "")}, skill.NO_ORGANIZATION),
                                  ({ORG: OK(0, "organizations/1\norganizations/2\n", "")},
                                   "2 organizations were found and none was picked."),
                                  ({ACCOUNT: OK(0, "\n", "")}, skill.NO_ACCOUNT),
                                  ({POLICY: OK(1, "", "")}, skill.POLICY_FAILED),
                                  ({API: OK(1, "", "")}, skill.APIS_FAILED % P)):
            with self.subTest(sentence=sentence):
                common.reset_wait_budget()
                args = {"projectId": P, "mode": "apply"}
                ctx = FakeContext(args)
                ctx.answers.update(answers)
                r = skill.run(dict(args), ctx)
                self.assertEqual((r.status, r.lines, ctx.writes), ("failed", [sentence], []))


class TestNothingSecret(unittest.TestCase):
    def test_no_identifier_in_any_answer(self):
        for kw in ({"settings": (DENIED, NOT_PREPARED)}, {"settings": (PREPARED,)},
                   {"settings": (DENIED,)}, {"mode": "plan", "settings": (NOT_PREPARED,)}):
            with self.subTest(kw=kw):
                r, ctx = run(**kw)
                for ident in (ORG_ID, EMAIL, CLIENT, "0f1e"):
                    self.assertNotIn(ident, answer_text(r))
                self.assertNotIn("set", [w[2] for w in ctx.writes if len(w) > 2])

    def test_the_settings_set_is_never_run(self):
        for kw in ({"settings": (DENIED, NOT_PREPARED)}, {"settings": (NOT_PREPARED,)}):
            r, ctx = run(**kw)
            for argv in ctx.writes:
                self.assertNotEqual(argv[1:4], ["iap", "settings", "set"])
            for line in ctx.reads:
                self.assertNotIn("settings set", line)


class TestTheList(unittest.TestCase):
    def test_the_list_is_the_skill_s_byte_for_byte(self):
        with open(os.path.join(ROOT, "skills", SKILL, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        block = re.search(r"## The list of what is left\n\n.*?\n```\n(.*?)\n```", text,
                          re.S).group(1)
        self.assertEqual(block.split("\n"), [line.replace("{p}", "<projectId>")
                                             for line in skill.LIST])

    def test_the_answer_prints_the_command_in_a_bash_block(self):
        r, _ = run(role=True, api=True, settings=(NOT_PREPARED,))
        steps = skill.steps_of(P)
        i = r.lines.index("```bash")
        self.assertEqual(r.lines[i + 1:i + 3], [steps[skill.COMMAND_LINE], "```"])
        self.assertIn("--billing-project=%s )" % P, steps[skill.COMMAND_LINE])
        self.assertEqual(r.block["pending"], [skill.login_item(P)])

    def test_the_item_s_how(self):
        with open(os.path.join(ROOT, "skills", SKILL, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn('"how": "%s"' % skill.LOGIN_HOW.replace("{p}", "<projectId>"), text)
        self.assertIn('"how": "%s"' % skill.NOT_READ_ITEM["how"], text)
        for name in ("NO_ORGANIZATION", "NO_ACCOUNT", "POLICY_FAILED", "READ_FAILED",
                     "GRANT_FAILED", "AFTER_STILL_REFUSED", "AFTER_NO_WAIT", "AFTER_FAILED"):
            self.assertIn("`%s`" % getattr(skill, name), text, name)
        for name in ("APIS_FAILED", "READ_API_OFF", "ENABLE_FAILED_ALONE",
                     "ENABLE_FAILED_AFTER_GRANT", "AFTER_API_OFF"):
            self.assertIn("`%s`" % (getattr(skill, name) % "<projectId>"), text, name)
        self.assertIn("`%s`" % (skill.SEVERAL_ORGANIZATIONS % 0).replace("0", "<n>", 1), text)


if __name__ == "__main__":
    unittest.main()
