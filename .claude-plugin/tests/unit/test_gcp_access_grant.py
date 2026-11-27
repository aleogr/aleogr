"""Unit tests of gcp_access-grant: its golden command (the grant exactly as the SKILL.md
writes it), its gates (no write unless mode=apply with person, and the reads hold), the
rule of one person, and the cases no scenario covers.

The skill's run() is given a context whose read() answers from a dict (longest prefix of
the command, after `gcloud`) and whose execute() (where ctx.write runs a command that
passed the allowlist of writes) records the write. No provider command runs. The
scenarios access-grant-* cover the rest, in the direct mode.
"""

import json
import os
import sys
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-cloud-gcp"
SKILL = "gcp_access-grant"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

PID = "aleogr-dev-demo-ab12"
PERSON = "demo-user@example.com"
ARGS = {"projectId": PID, "project": "demo", "region": "us-central1", "components": "web,api",
        "person": PERSON, "mode": "apply"}
# The SKILL.md's command of step 4, word for word (its double-quoted values are one
# argument each, without their quotes).
GOLDEN_GRANT = ("gcloud iap web add-iam-policy-binding --resource-type=cloud-run "
                "--service=demo-web --region=us-central1 --project=%s "
                "--member=user:%s --role=roles/iap.httpsResourceAccessor --condition=None "
                "--quiet" % (PID, PERSON))
DENIED = common.Completed(1, "", "ERROR: PERMISSION_DENIED: secret-text")
MISSING = common.Completed(1, "", "ERROR: Cannot find service [demo-web]")


def ok(obj):
    return common.Completed(0, obj if isinstance(obj, str) else json.dumps(obj), "")


def login(*members, **kw):
    b = {"role": kw.get("role", "roles/iap.httpsResourceAccessor"), "members": list(members)}
    if kw.get("condition"):
        b["condition"] = {"title": kw["condition"], "expression": "true"}
    return {"bindings": [b]}


def reads(web=None, api=None, **over):
    a = {
        "run services describe demo-web": ok("demo-web\n"),
        "run services describe demo-api": ok("demo-api\n"),
        "iap web get-iam-policy --resource-type=cloud-run --service=demo-web":
            ok(web if web is not None else login("user:owner@example.com")),
        "iap web get-iam-policy --resource-type=cloud-run --service=demo-api":
            ok(api if api is not None else login("user:" + PERSON)),
    }
    a.update(over)
    return a


class FakeContext(common.Context):
    def __init__(self, args, reads_, writes=None, read_only=False):
        mode = args.get("mode") or skill.DEFAULT_MODE
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill,
                                mode if mode in ("plan", "apply") else "plan", args,
                                read_only=read_only)
        self.reads_ = {k: list(v) if isinstance(v, list) else v for k, v in reads_.items()}
        self.writes_ = dict(writes or {})
        self.calls = []
        self.writes = []

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
        line = " ".join(argv[1:])
        self.calls.append(line)
        return self._pick(self.reads_, line)

    def execute(self, argv, timeout=None):
        # Reached only through ctx.write, after the allowlist of writes accepted argv.
        self.writes.append(list(argv))
        return self._pick(self.writes_, " ".join(argv[1:]))


def run(reads_=None, writes=None, **over):
    args = dict(ARGS, **over)
    args = {k: v for k, v in args.items() if v is not None}
    ctx = FakeContext(args, reads_ if reads_ is not None else reads(), writes)
    return skill.run(dict(args), ctx), ctx


class TestGolden(unittest.TestCase):
    def test_the_grant_as_the_skill_writes_it(self):
        r, ctx = run()
        self.assertEqual(r.status, "updated")
        self.assertEqual(ctx.writes, [GOLDEN_GRANT.split(" ")])
        self.assertEqual(skill.grant_command("demo-web", ARGS), GOLDEN_GRANT.split(" "))
        self.assertIsNone(common.write_refusal(SKILL, ctx.writes[0], root=ROOT))
        self.assertNotIn("@", common.render_block(r.block))

    def test_the_grant_is_on_the_login_policy_only(self):
        argv = skill.grant_command("demo-web", ARGS)
        self.assertEqual(argv[1:4], ["iap", "web", "add-iam-policy-binding"])
        for name in ("gcp_deploy-setup", SKILL):
            self.assertIsNone(common.write_refusal(name, argv, root=ROOT))
        # Never a service account, a group, a domain or everyone, even past the validation.
        for member in ("serviceAccount:x@%s.iam.gserviceaccount.com" % PID, "group:t@example.com",
                       "domain:example.com", "allUsers", "allAuthenticatedUsers"):
            bad = [a if not a.startswith("--member=") else "--member=" + member for a in argv]
            self.assertIsNotNone(common.write_refusal(SKILL, bad, root=ROOT), member)


class TestGates(unittest.TestCase):
    def assert_no_write(self, r, ctx, status):
        self.assertEqual(r.status, status)
        self.assertEqual(ctx.writes, [])

    def test_mode_absent_or_plan(self):
        for mode in (None, "plan"):
            with self.subTest(mode=mode):
                r, ctx = run(mode=mode)
                self.assert_no_write(r, ctx, "would-update")
                self.assertEqual(r.block["outputs"]["granted"], ["web"])
                self.assertEqual(r.block["mode"], "plan")

    def test_mode_with_another_value(self):
        for mode in ("APPLY", "yes", ""):
            with self.subTest(mode=mode):
                r, ctx = run(mode=mode)
                self.assert_no_write(r, ctx, "failed")
                self.assertEqual(ctx.calls, [])

    def test_list_never_writes(self):
        for mode in ("plan", "apply"):
            r, ctx = run(person=None, list="yes", mode=mode)
            self.assert_no_write(r, ctx, "unchanged")
            self.assertEqual(r.block["outputs"]["people"], {"web": 1, "api": 1})

    def test_read_only_refuses_the_grant(self):
        ctx = FakeContext(dict(ARGS), reads(), read_only=True)
        with self.assertRaises(common.WriteRefused):
            ctx.write(GOLDEN_GRANT.split(" "))
        self.assertEqual(ctx.writes, [])

    def test_a_missing_service_reads_every_one_then_grants_nothing(self):
        r, ctx = run(reads(**{"run services describe demo-web": MISSING}))
        self.assert_no_write(r, ctx, "failed")
        self.assertEqual(ctx.calls, ["run services describe demo-web --project=%s "
                                     "--region=us-central1 --format=value(metadata.name)" % PID,
                                     "run services describe demo-api --project=%s "
                                     "--region=us-central1 --format=value(metadata.name)" % PID])

    def test_a_failed_read_grants_nothing(self):
        for key in ("run services describe demo-api",
                    "iap web get-iam-policy --resource-type=cloud-run --service=demo-api"):
            r, ctx = run(reads(**{key: DENIED}))
            self.assert_no_write(r, ctx, "failed")
            self.assertEqual(r.lines, [skill.READ_FAILED % ("demo-api", PID)])
            self.assertEqual(r.block["outputs"], {"granted": [], "already": [], "people": None,
                                                  "open": []})


class TestValidation(unittest.TestCase):
    def test_one_person_only(self):
        for person in ("group:t@example.com", "a@b", "allUsers", "x,y@example.com",
                       "a b@example.com", "a@-example.com", "a@example.c0m",
                       "ci@%s.iam.gserviceaccount.com" % PID, "a@gserviceaccount.com",
                       "a@@example.com", "'a'@example.com", "a" * 65 + "@example.com",
                       "user:a@example.com"):
            with self.subTest(person=person):
                r, ctx = run(person=person)
                self.assertEqual((r.status, ctx.calls), ("failed", []))
                self.assertEqual(r.lines, [skill.PERSON_RULE])
        for person in ("a+b@example.com", "A.B_c-d@sub.example.org"):
            self.assertTrue(skill.person_ok(person), person)

    def test_person_and_list(self):
        r, _ = run(person=None)
        self.assertEqual(r.lines, ["person is missing (or give list=yes)."])
        r, _ = run(list="yes")
        self.assertEqual(r.lines, ["Give either person or list=yes, not both."])
        r, _ = run(person=None, list="no")
        self.assertEqual(r.lines, ["list must be yes."])

    def test_a_service_name_too_long(self):
        r, _ = run(project="reference-proj", components="administration-ui")
        self.assertEqual(r.lines, ["reference-proj-administration-ui has 32 characters: a "
                                   "service's name must have 6 to 30."])


class TestPaths(unittest.TestCase):
    def test_a_conditional_binding_does_not_count(self):
        web = login("user:" + PERSON.upper(), condition="until-2027")
        r, ctx = run(reads(web=web, **{
            "iap web get-iam-policy --resource-type=cloud-run --service=demo-web":
                [ok(web), ok(login("user:" + PERSON))]}))
        self.assertEqual(r.status, "updated")
        self.assertIn("A conditional binding already named the person; an unconditional one "
                      "was added.", r.lines)

    def test_case_does_not_count_for_has(self):
        r, ctx = run(reads(web=login("user:" + PERSON.upper())))
        self.assertEqual((r.status, ctx.writes), ("unchanged", []))

    def test_a_read_back_that_fails_or_does_not_show_the_grant(self):
        key = "iap web get-iam-policy --resource-type=cloud-run --service=demo-web"
        for second, reason in ((DENIED, skill.REASON_UNREAD),
                               (ok(login("user:owner@example.com")), skill.REASON_NOT_SEEN)):
            r, _ = run(reads(**{key: [ok(login()), second]}))
            self.assertEqual(r.status, "updated")
            self.assertEqual(r.block["pending"][0]["item"], "web: access")
            self.assertEqual(r.block["pending"][0]["reason"], reason)
            self.assertIn("person=<e-mail> mode=apply", r.block["pending"][0]["how"])
            self.assertNotIn("@", common.render_block(r.block))

    def test_a_stop_after_a_grant_leaves_the_rest_pending(self):
        args_components = "web,api,admin"
        a = reads(api=login(), **{
            "iap web get-iam-policy --resource-type=cloud-run --service=demo-web":
                [ok(login()), ok(login("user:" + PERSON))],
            "run services describe demo-admin": ok("demo-admin\n"),
            "iap web get-iam-policy --resource-type=cloud-run --service=demo-admin":
                ok(login())})
        r, ctx = run(a, writes={"iap web add-iam-policy-binding --resource-type=cloud-run "
                                "--service=demo-api": DENIED}, components=args_components)
        self.assertEqual(r.status, "updated")
        self.assertEqual(len(ctx.writes), 2)
        self.assertEqual([p["item"] for p in r.block["pending"]],
                         ["api: access", "admin: access"])

    def test_an_open_service_is_flagged_never_closed(self):
        web = {"bindings": [{"role": "roles/iap.httpsResourceAccessor",
                             "members": ["allAuthenticatedUsers", "user:" + PERSON]},
                            {"role": "roles/iap.other", "members": ["allUsers"]}]}
        r, ctx = run(reads(web=web))
        self.assertEqual((r.status, ctx.writes), ("unchanged", []))
        self.assertEqual(r.block["outputs"]["open"], ["web"])
        hows = [p["how"] for p in r.block["pending"]]
        self.assertEqual(len(hows), 2)
        self.assertIn("--member=allAuthenticatedUsers --role=roles/iap.httpsResourceAccessor "
                      "--all", hows[0])
        self.assertIn("--member=allUsers --role=roles/iap.other --all", hows[1])


if __name__ == "__main__":
    unittest.main()
