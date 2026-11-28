"""Unit tests of the shared module aleogr_common and of the plugins' commands.

Run: python3 -m unittest discover -s .claude-plugin/tests/unit
No provider is reached: the runner's tests use stand-in commands in a temporary folder.
"""

import ast
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGINS = os.path.normpath(os.path.join(HERE, "..", "..", "plugins"))
NAMES = sorted(n for n in os.listdir(PLUGINS)
               if os.path.isfile(os.path.join(PLUGINS, n, ".claude-plugin", "plugin.json")))
sys.path.insert(0, os.path.join(PLUGINS, "aleogr", "scripts"))

import aleogr_common as common  # noqa: E402

sys.path.insert(0, HERE)
from helpers import suite_line  # noqa: E402


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


class TestCopies(unittest.TestCase):
    def test_six_plugins(self):
        self.assertEqual(NAMES, ["aleogr", "aleogr-cloud-gcp", "aleogr-db-gcp-cloud-sql",
                                 "aleogr-registry-gcp-artifact-registry",
                                 "aleogr-repo-github", "aleogr-stack-go"])

    def test_common_module_is_byte_identical(self):
        ref = read_bytes(os.path.join(PLUGINS, "aleogr", "scripts", "aleogr_common.py"))
        for n in NAMES:
            with self.subTest(plugin=n):
                got = read_bytes(os.path.join(PLUGINS, n, "scripts", "aleogr_common.py"))
                self.assertEqual(got, ref, "scripts/aleogr_common.py of %s differs from "
                                           "the copy in aleogr" % n)

    def test_command_is_byte_identical_and_executable(self):
        ref = read_bytes(os.path.join(PLUGINS, "aleogr", "bin", "aleogr"))
        for n in NAMES:
            with self.subTest(plugin=n):
                path = os.path.join(PLUGINS, n, "bin", n)
                self.assertEqual(read_bytes(path), ref)
                self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o755)
                self.assertTrue(ref.startswith(b"#!/usr/bin/env python3\n"))

    def test_python_39_grammar_and_no_bytecode_switch(self):
        for n in NAMES:
            root = os.path.join(PLUGINS, n)
            files = [os.path.join(root, "bin", n)]
            for d, _, fs in os.walk(os.path.join(root, "scripts")):
                files += [os.path.join(d, f) for f in fs if f.endswith(".py")]
            for path in files:
                with self.subTest(path=os.path.relpath(path, PLUGINS)):
                    src = read_bytes(path).decode("utf-8")
                    ast.parse(src, filename=path, feature_version=(3, 9))
            entry = read_bytes(os.path.join(root, "bin", n)).decode("utf-8")
            self.assertIn("sys.dont_write_bytecode = True", entry)


WRITES = [
    "gh api -iXPOST repos/o/n",
    "gh api -iX DELETE repos/o/n",
    "gh api -if title=x repos/o/n",
    "gh auth status -at",
    "gh auth status -t",
    "git ls-remote origin",
    "git ls-remote --upload-pack=x .",
    "gcloud projects create aleogr-dev-demo-ab12",
    "gcloud sql instances patch aleogr-shared --activation-policy=ALWAYS",
    "gcloud sql instances create aleogr-shared",
    "gcloud run services update web --region=us-central1",
    "gcloud run deploy web",
    "gcloud projects add-iam-policy-binding demo --member=user:x --role=roles/viewer",
    "gcloud services enable run.googleapis.com",
    "gcloud iam service-accounts create demo-ci",
    "gcloud iam workload-identity-pools create github --location=global",
    "gcloud iam workload-identity-pools providers update-oidc github",
    "gcloud config set project demo",
    "gcloud auth login",
    "gcloud billing projects link demo --billing-account=000000-000000-000000",
    "gh api -X POST repos/o/r/rulesets",
    "gh api -XPOST repos/o/r/rulesets",
    "gh api --method PUT repos/o/r/topics",
    "gh api --method=PATCH repos/o/r",
    "gh api -X DELETE repos/o/r/rulesets/1",
    "gh api repos/o/r -f name=x",
    "gh api repos/o/r -F private=true",
    "gh api repos/o/r --field name=x",
    "gh api repos/o/r --raw-field name=x",
    "gh api repos/o/r --input body.json",
    "gh api repos/o/r --input=body.json",
    "gh api -fname=x repos/o/r",
    "gh api graphql -f query=x",
    "gh auth status --show-token",
    "gh secret set GCP_PROJECT_ID --repo o/r --body x",
    "gh secret delete X --repo o/r",
    "gh variable set X --repo o/r --body y",
    "gh pr create --repo o/r --base main --head b --title t --body b",
    "gh pr merge 1 --repo o/r",
    "gh pr close 1",
    "gh repo create o/r --private",
    "gh repo edit o/r --add-topic x",
    "gh repo clone o/r",
    "gh auth login",
    "git push -u origin main",
    "git commit -m x -- a",
    "git checkout main",
    "git switch main",
    "git add -- a",
    "git pull --ff-only origin main",
    "git fetch",
    "git init -b main",
    "git remote add origin https://github.com/o/r.git",
    "git remote set-url origin x",
    "git config --local user.name x",
    "git config user.name x",
    "git config --unset --get user.name",
    "git branch new-branch",
    "git branch -D old",
    "git -c core.pager=x log",
    "git -c credential.helper= pull origin main",
    "git diff --output=out.txt",
    "go get example.com/dep@v1.0.0",
    "go -C web get example.com/dep@v1.0.0",
    "go mod tidy",
    "go -C web mod tidy",
    "go env -w GOFLAGS=-mod=mod",
    "go build ./...",
    "rm -rf /",
    "sh -c true",
    "sleep 30 && true",
]

READS = [
    "gcloud --version",
    "gcloud auth list --filter=status:ACTIVE --format=value(account)",
    "gcloud projects list --filter=labels.aleogr-project=demo --format=value(projectId)",
    "gcloud projects describe demo --format=json",
    "gcloud projects get-iam-policy demo --format=json",
    "gcloud billing projects describe demo --format=value(billingEnabled)",
    "gcloud services list --enabled --project=demo --format=value(config.name)",
    "gcloud organizations list --format=value(name)",
    "gcloud iap settings get --organization=1 --format=json",
    "gcloud iap web get-iam-policy --resource-type=cloud-run --service=web",
    "gcloud iam service-accounts describe a --project=demo --format=value(email)",
    "gcloud iam service-accounts get-iam-policy a --project=demo --format=json",
    "gcloud iam workload-identity-pools describe github --project=demo --location=global",
    "gcloud iam workload-identity-pools providers describe github --workload-identity-pool=github",
    "gcloud iam workload-identity-pools providers list --workload-identity-pool=github",
    "gcloud run services describe web --project=demo --region=us-central1 --format=json",
    "gcloud run services get-iam-policy web --project=demo --region=us-central1",
    "gcloud artifacts repositories describe demo --location=us-central1 --format=json",
    "gcloud artifacts repositories list --location=all --project=demo",
    "gcloud artifacts repositories get-iam-policy demo --location=us-central1",
    "gcloud sql instances describe aleogr-shared --project=demo --format=json",
    "gcloud sql operations list --instance=aleogr-shared --filter=status!=DONE",
    "gcloud sql backups list --instance=aleogr-shared --limit=1",
    "gcloud sql databases list --instance=aleogr-shared --format=value(name)",
    "gcloud sql users list --instance=aleogr-shared --format=value(name)",
    "gcloud.cmd --version",
    "gh --version",
    "gh auth status",
    "gh api repos/o/r",
    "gh api repos/o/r/rulesets",
    "gh api user",
    "gh api repos/o/r/commits?per_page=2",
    "gh api repos/o/r/contents/.aleogr/project.json -H Accept:application/vnd.github.raw",
    "gh api -X GET search/repositories -f q=x",
    "gh api --method GET repos/o/r -F per_page=2",
    "gh api --method=get repos/o/r",
    "gh api --paginate repos/o/r/rulesets --jq .[].id",
    "gh repo view o/r --json name",
    "gh pr list --repo o/r --state open --json number,url,headRefName,isCrossRepository",
    "gh pr view 1 --repo o/r",
    "gh secret list --repo o/r --json name",
    "gh variable list --repo o/r --json name,value",
    "git status --porcelain -- a",
    "git rev-parse --is-inside-work-tree",
    "git rev-parse HEAD",
    "git diff --name-only origin/main HEAD",
    "git log -1 --format=%ae HEAD",
    "git ls-files --error-unmatch a",
    "git remote get-url origin",
    "git config --get remote.origin.url",
    "git config --local --get user.name",
    "git branch --show-current",
    "git rev-list --count origin/main..HEAD",
    "git -C web status --short",
    "go version",
    "go env GOVERSION",
    "go -C web version",
    "sleep 30",
]


def argv(cmd):
    return cmd.split(" ")


class StandIns(object):
    """A folder of stand-in gcloud, gh, git, go and sleep that record being run."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp()
        self.marks = os.path.join(self.dir, "ran")
        for tool in ("gcloud", "gcloud.cmd", "gh", "git", "go", "sleep", "rm", "sh"):
            p = os.path.join(self.dir, tool)
            with open(p, "w") as f:
                f.write('#!/bin/sh\necho "$0 $*" >> "%s"\necho out\necho err >&2\nexit 3\n'
                        % self.marks)
            os.chmod(p, 0o755)
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = self.dir
        common.reset_suite_checks()
        return self

    def ran(self):
        if not os.path.exists(self.marks):
            return []
        with open(self.marks) as f:
            return f.read().splitlines()

    def __exit__(self, *exc):
        os.environ["PATH"] = self.old_path
        for f in os.listdir(self.dir):
            os.remove(os.path.join(self.dir, f))
        os.rmdir(self.dir)


class TestReadOnlyRunner(unittest.TestCase):
    def test_refuses_writes_before_running_them(self):
        with StandIns() as s:
            for cmd in WRITES:
                with self.subTest(cmd=cmd):
                    err = io.StringIO()
                    with self.assertRaises(common.ReadRefused):
                        common.run_read(argv(cmd), stream=err)
                    self.assertEqual(err.getvalue(), "", "a refused command is not shown")
            self.assertEqual(s.ran(), [], "a refused command ran")

    def test_accepts_reads_and_runs_them(self):
        with StandIns() as s:
            for cmd in READS:
                with self.subTest(cmd=cmd):
                    self.assertIsNone(common.read_refusal(argv(cmd)))
                    err = io.StringIO()
                    c = common.run_read(argv(cmd), stream=err)
                    self.assertEqual(c, (3, "out\n", "err\n"))
                    self.assertEqual((c.code, c.out, c.err), (3, "out\n", "err\n"))
                    self.assertFalse(c.ok)
                    self.assertTrue(err.getvalue().startswith("+ " + argv(cmd)[0]))
            self.assertEqual(len(s.ran()), len(READS))

    def test_runner_shows_then_runs_and_reports_a_missing_command(self):
        with StandIns():
            err = io.StringIO()
            c = common.run(["no-such-command-here", "x y"], stream=err)
            self.assertEqual(err.getvalue(), "+ no-such-command-here 'x y'\n")
            self.assertEqual(c.code, 127)
            self.assertEqual(c.out, "")

    def test_context_is_read_only_unless_the_module_writes(self):
        class Reader(object):
            pass

        class Writer(object):
            WRITES = True

        self.assertTrue(common.Context("p", "/x", "s", Reader, "apply", {}).read_only)
        self.assertTrue(common.Context("p", "/x", "s", Writer, "plan", {}).read_only)
        self.assertFalse(common.Context("p", "/x", "s", Writer, "apply", {}).read_only)
        with StandIns() as s:
            ctx = common.Context("p", "/x", "s", Reader, "apply", {})
            with self.assertRaises(common.ReadRefused):
                ctx.run(argv("gcloud projects create x"))
            self.assertEqual(s.ran(), [])


class TestArguments(unittest.TestCase):
    def test_key_value(self):
        self.assertEqual(common.parse_args(["projectId=demo-12", "instance=aleogr-shared"]),
                         {"projectId": "demo-12", "instance": "aleogr-shared"})
        self.assertEqual(common.parse_args(["variables=A=1,B=2", "empty="]),
                         {"variables": "A=1,B=2", "empty": ""})
        self.assertEqual(common.parse_args(["description=Status $(whoami)"]),
                         {"description": "Status $(whoami)"})
        self.assertEqual(list(common.parse_args(["b=1", "a=2"])), ["b", "a"])

    def test_bad_arguments(self):
        for tokens in (["noequals"], ["=x"], ["1a=x"], ["a-b=x"], ["a=1", "a=2"]):
            with self.subTest(tokens=tokens):
                with self.assertRaises(common.UsageError):
                    common.parse_args(tokens)

    def test_format_args(self):
        self.assertEqual(common.format_args({"a": "1", "b": None}), ["a=1", "b="])

    def test_command_line(self):
        inv = common.parse_command_line(["--json", "gcp_environment-describe", "project=x"])
        self.assertEqual((inv.json, inv.has, inv.skill, inv.args),
                         (True, False, "gcp_environment-describe", {"project": "x"}))
        inv = common.parse_command_line(["--has", "go_setup", "plan"])
        self.assertEqual((inv.has, inv.skill, inv.mode), (True, "go_setup", "plan"))
        inv = common.parse_command_line(["--has", "go_setup"])
        self.assertIsNone(inv.mode)
        for bad in ([], ["--json"], ["--has"], ["--has", "a", "b", "c"], ["--verbose", "x"],
                    ["Bad"], ["x", "y"]):
            with self.subTest(argv=bad):
                with self.assertRaises(common.UsageError):
                    common.parse_command_line(bad)

    def test_module_name(self):
        self.assertEqual(common.module_name("gcp-cloud-sql_instance-describe"),
                         "gcp_cloud_sql_instance_describe")


class TestCallPlugin(unittest.TestCase):
    def test_missing_command(self):
        with StandIns():
            got = common.call_plugin("aleogr-not-installed", "x_describe", {"a": "1"})
        self.assertEqual(got["status"], "failed")
        self.assertEqual(got["callError"], "not-found")
        self.assertEqual(got["answer"], [common.NOT_FOUND_SENTENCE.format(
            command="aleogr-not-installed")])
        self.assertIn("aleogr-not-installed", got["answer"][0])

    def test_found_command(self):
        with StandIns() as s:
            p = os.path.join(s.dir, "aleogr-fake")
            with open(p, "w") as f:
                f.write('#!/bin/sh\n' + suite_line() +
                        'echo \'{"aleogr-result": 1, "status": "unchanged", "args": "\'"$*"\'"}\'\n')
            os.chmod(p, 0o755)
            got = common.call_plugin("aleogr-fake", "y_describe", {"a": "1", "b": "x y"})
            self.assertEqual(got["status"], "unchanged")
            self.assertEqual(got["args"], "--json y_describe a=1 b=x y")
            with open(p, "w") as f:
                f.write("#!/bin/sh\nexit 64\n")
            self.assertEqual(common.call_plugin("aleogr-fake", "z")["callError"],
                             "not-converted")
            with open(p, "w") as f:
                f.write("#!/bin/sh\necho not json\n")
            self.assertEqual(common.call_plugin("aleogr-fake", "z")["callError"], "no-result")


class TestSuite(unittest.TestCase):
    """`<command> --suite` and the check call_plugin makes before its first call to a
    command of another plugin."""

    def stand_in(self, s, name, suite):
        """A command that logs every run and answers `--suite` with `suite`."""
        p = os.path.join(s.dir, name)
        with open(p, "w") as f:
            f.write('#!/bin/sh\necho "$*" >> "%s/%s.log"\n'
                    '[ "$1" = --suite ] && { printf "%%s" \'%s\'; exit 0; }\n'
                    'echo \'{"aleogr-result": 1, "status": "unchanged"}\'\n'
                    % (s.dir, name, suite))
        os.chmod(p, 0o755)
        return os.path.join(s.dir, name + ".log")

    def log(self, path):
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return f.read().splitlines()

    def test_the_digest_and_the_option(self):
        with open(common.__file__, "rb") as f:
            import hashlib
            digest = hashlib.sha256(f.read()).hexdigest()[:12]
        self.assertEqual(common.suite_digest(), digest)
        self.assertTrue(common.parse_command_line(["--suite"]).suite)
        for bad in (["--suite", "x"], ["--json", "--suite"]):
            with self.assertRaises(common.UsageError):
                common.parse_command_line(bad)
        for n in NAMES:
            p = subprocess.run([os.path.join(PLUGINS, n, "bin", n), "--suite"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual((p.returncode, p.stdout, p.stderr),
                             (0, (digest + "\n").encode(), b""), n)

    def test_the_same_suite_is_asked_once(self):
        with StandIns() as s:
            log = self.stand_in(s, "aleogr-fake", common.suite_digest() + "\n")
            for _ in range(3):
                self.assertEqual(common.call_plugin("aleogr-fake", "x")["status"],
                                 "unchanged")
            self.assertEqual(self.log(log), ["--suite"] + ["--json x"] * 3)

    def test_another_suite_runs_nothing_on_that_command(self):
        for answer in ("0123456789ab\n", "", "%s\n%s\n" % (common.suite_digest(),
                                                            common.suite_digest()),
                       common.suite_digest().upper(), common.suite_digest() + "0",
                       "usage: aleogr-fake <skill>\n"):
            with self.subTest(answer=answer), StandIns() as s:
                log = self.stand_in(s, "aleogr-fake", answer)
                sentence = common.VERSION_SENTENCE.format(callee="aleogr-fake",
                                                          caller="aleogr")
                for _ in range(2):
                    got = common.call_plugin("aleogr-fake", "x", {"a": "1"},
                                             caller="aleogr")
                    self.assertEqual((got["status"], got["callError"], got["answer"]),
                                     ("failed", "version", [sentence]))
                self.assertEqual(self.log(log), ["--suite"])  # no skill was invoked
                self.assertIn("/plugin marketplace update aleogr", sentence)
                # ctx.call raises it, with this plugin as the caller.
                ctx = common.Context("aleogr-db-gcp-cloud-sql", "/x", "s", object(),
                                     "plan", {})
                with self.assertRaises(common.PluginVersion) as cm:
                    ctx.call("aleogr-fake", "x")
                self.assertIn("as the plugin aleogr-db-gcp-cloud-sql:", cm.exception.sentence)
                self.assertEqual(self.log(log), ["--suite"])

    def test_a_missing_command_is_not_asked(self):
        with StandIns() as s:
            got = common.call_plugin("aleogr-not-installed", "x")
            self.assertEqual(got["callError"], "not-found")
            self.assertEqual(s.ran(), [])

    def test_check_suites_probes_each_command_once_before_any_call(self):
        with StandIns() as s:
            logs = [self.stand_in(s, n, common.suite_digest() + "\n")
                    for n in ("aleogr-fa", "aleogr-fb")]
            self.assertIsNone(common.check_suites(["aleogr-fa", "aleogr-fb", "aleogr-fa"]))
            self.assertIsNone(common.check_suites(["aleogr-fa", "aleogr-fb"]))
            self.assertEqual([self.log(l) for l in logs], [["--suite"], ["--suite"]])
            # The probe is the one call_plugin makes: it is not asked again.
            common.call_plugin("aleogr-fb", "x")
            self.assertEqual(self.log(logs[1]), ["--suite", "--json x"])

    def test_check_suites_a_mismatch_is_the_version_failure(self):
        with StandIns() as s:
            good = self.stand_in(s, "aleogr-fa", common.suite_digest() + "\n")
            bad = self.stand_in(s, "aleogr-fb", "0123456789ab\n")
            got = common.check_suites(["aleogr-fa", "aleogr-fb"], caller="aleogr")
            self.assertEqual((got["status"], got["callError"], got["answer"]),
                             ("failed", "version", [common.VERSION_SENTENCE.format(
                                 callee="aleogr-fb", caller="aleogr")]))
            self.assertEqual((self.log(good), self.log(bad)), (["--suite"], ["--suite"]))
            # call_plugin keeps the answer: nothing is ever run on that command.
            self.assertEqual(common.call_plugin("aleogr-fb", "x")["callError"], "version")
            self.assertEqual(self.log(bad), ["--suite"])
            ctx = common.Context("aleogr", "/x", "s", object(), "plan", {})
            with self.assertRaises(common.PluginVersion) as cm:
                ctx.check_suites(["aleogr-fa", "aleogr-fb"])
            self.assertEqual(cm.exception.sentence, common.VERSION_SENTENCE.format(
                callee="aleogr-fb", caller="aleogr"))
            self.assertEqual(s.ran(), [])

    def test_check_suites_a_command_not_installed_is_not_a_failure(self):
        with StandIns() as s:
            log = self.stand_in(s, "aleogr-fa", common.suite_digest() + "\n")
            self.assertIsNone(common.check_suites(["aleogr-not-installed", "aleogr-fa"]))
            ctx = common.Context("aleogr", "/x", "s", object(), "plan", {})
            self.assertIsNone(ctx.check_suites(["aleogr-not-installed", "aleogr-fa"]))
            self.assertEqual(self.log(log), ["--suite"])
            # Unless the module names it as required: then its not-found failure.
            got = ctx.check_suites(["aleogr-fa", "aleogr-not-installed"],
                                   required=["aleogr-not-installed"])
            self.assertEqual((got["callError"], got["answer"]), ("not-found", [
                common.NOT_FOUND_SENTENCE.format(command="aleogr-not-installed")]))

    def test_a_module_that_meets_another_suite_ends_failed(self):
        # Any module that calls another plugin: the run ends failed with the sentence
        # alone, exit 0, and the module runs nothing after the call.
        after = []

        def run(args, ctx):
            ctx.call("aleogr-fake", "x")
            after.append(True)
            return ctx.result("unchanged", {})

        module = type("M", (), {"FAMILY": "cloud", "PROVIDER": "gcp", "ACTION": "x",
                                "run": staticmethod(run)})
        with StandIns() as s:
            self.stand_in(s, "aleogr-fake", "ffffffffffff\n")
            out, err = io.StringIO(), io.StringIO()
            inv = common.parse_command_line(["--json", "x"])
            code = common.run_command("aleogr-cloud-gcp", "/x", inv, module, "plan", out,
                                      err, environ={})
        obj = json.loads(out.getvalue())
        self.assertEqual((code, obj["status"], after), (0, "failed", []))
        self.assertEqual(obj["answer"], [common.VERSION_SENTENCE.format(
            callee="aleogr-fake", caller="aleogr-cloud-gcp")])
        self.assertEqual(obj["cost"], common.VERSION_COST)


class TestAnswer(unittest.TestCase):
    def test_block_layout(self):
        block = common.result_block(
            "orchestrator", "aleogr", "project-plan", "would-create",
            {"items": [{"item": "repository", "state": "missing", "action": "create"},
                       {"item": "ci", "state": "as declared", "action": "none"}],
             "topics": ["a", "b"], "settings": {"squash": True}, "empty": [], "none": None},
            resources=[{"type": "repository", "id": "o/r", "name": "r", "labels": {}}])
        text = common.render_block(block)
        self.assertEqual(text, "\n".join([
            '{',
            '  "aleogr-result": 1,',
            '  "family": "orchestrator",',
            '  "provider": "aleogr",',
            '  "action": "project-plan",',
            '  "mode": "plan",',
            '  "status": "would-create",',
            '  "resources": [',
            '    { "type": "repository", "id": "o/r", "name": "r", "labels": {} }',
            '  ],',
            '  "outputs": {',
            '    "items": [',
            '      { "item": "repository", "state": "missing", "action": "create" },',
            '      { "item": "ci", "state": "as declared", "action": "none" }',
            '    ],',
            '    "topics": ["a", "b"],',
            '    "settings": { "squash": true },',
            '    "empty": [],',
            '    "none": null',
            '  },',
            '  "cost": { "fixed": false, "notes": "read-only" },',
            '  "pending": []',
            '}']))
        self.assertEqual(json.loads(text), block)

    def test_answer_and_json(self):
        r = common.Result(common.result_block("db", "p", "a", "unchanged", {"exists": False}),
                          ["One line."])
        text = common.render_answer(r)
        self.assertTrue(text.startswith("One line.\n\n```aleogr-result\n{\n"))
        self.assertTrue(text.endswith("\n}\n```\n"))
        obj = json.loads(common.render_json(r))
        self.assertEqual(obj["answer"], ["One line."])
        self.assertEqual(obj["outputs"], {"exists": False})
        self.assertNotIn("data", obj)

    def test_data_goes_only_into_the_json_document(self):
        r = common.Result(common.result_block("db", "p", "a", "unchanged", {}), ["Line."],
                          data={"copy": {"secret-ish": 1}})
        self.assertNotIn("secret-ish", common.render_answer(r))
        self.assertEqual(json.loads(common.render_json(r))["data"], {"copy": {"secret-ish": 1}})

    def test_table(self):
        self.assertEqual(common.render_table(["item", "state", "action"],
                                             [["repository", "a|b", None]]),
                         ["| item | state | action |", "|---|---|---|",
                          "| repository | a\\|b |  |"])


UNCONVERTED = "demo-not-converted"


class UnconvertedPlugin(object):
    """A plugin folder `demo` built for the test: the real bin/ and shared module, and one
    skill, UNCONVERTED, that has a SKILL.md and no module: the example of a skill that is
    not converted, which no real skill has to stay."""

    def __enter__(self):
        import shutil
        self.top = tempfile.mkdtemp()
        root = os.path.join(self.top, "demo")
        os.makedirs(os.path.join(root, "bin"))
        os.makedirs(os.path.join(root, "scripts", "skills"))
        os.makedirs(os.path.join(root, "skills", UNCONVERTED))
        shutil.copy(os.path.join(PLUGINS, "aleogr", "bin", "aleogr"),
                    os.path.join(root, "bin", "demo"))
        shutil.copy(os.path.join(PLUGINS, "aleogr", "scripts", "aleogr_common.py"),
                    os.path.join(root, "scripts"))
        open(os.path.join(root, "scripts", "skills", "__init__.py"), "w").close()
        with open(os.path.join(root, "skills", UNCONVERTED, "SKILL.md"), "w") as f:
            f.write("---\ndescription: a skill with no module.\n---\n")
        self.command = os.path.join(root, "bin", "demo")
        return self

    def run(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([sys.executable, self.command] + list(args),
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env, cwd=tempfile.gettempdir())
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def __exit__(self, *exc):
        import shutil
        shutil.rmtree(self.top)


class TestCommands(unittest.TestCase):
    def call(self, plugin, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([os.path.join(PLUGINS, plugin, "bin", plugin)] + list(args),
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=env, cwd=tempfile.gettempdir())
        return p.returncode, p.stdout.decode(), p.stderr.decode()

    def test_exit_codes(self):
        sql = "aleogr-db-gcp-cloud-sql"
        self.assertEqual(self.call(sql, "--has", "gcp-cloud-sql_instance-describe")[0], 0)
        self.assertEqual(self.call(sql, "--has", "gcp-cloud-sql_instance-describe",
                                   "plan")[0], 0)
        # A skill with a SKILL.md and no module, in a plugin built for the test: the
        # example of a skill not converted.
        with UnconvertedPlugin() as demo:
            self.assertEqual(demo.run("--has", UNCONVERTED)[0], 64)
            code, out, err = demo.run(UNCONVERTED)
            self.assertEqual((code, out), (64, ""))
            self.assertEqual(len(err.splitlines()), 1)
            self.assertEqual(demo.run("no-such-skill")[0], 2)
        for converted in ("project-apply", "platform-plan", "platform-apply"):
            self.assertEqual(self.call("aleogr", "--has", converted)[0], 0, converted)
        self.assertEqual(self.call(sql, "no-such-skill")[0], 2)
        self.assertEqual(self.call(sql, "--bogus")[0], 2)
        self.assertEqual(self.call(sql, "gcp-cloud-sql_instance-describe", "x")[0], 2)
        self.assertEqual(self.call(sql)[0], 2)
        for n in NAMES:
            with self.subTest(plugin=n):
                self.assertEqual(self.call(n, "--has", "no-such-skill")[0], 2)

    def test_failed_result_is_exit_0(self):
        sql = "aleogr-db-gcp-cloud-sql"
        code, out, err = self.call(sql, "gcp-cloud-sql_instance-describe", "projectId=demo-12")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(out.startswith("instance is missing.\n"))
        self.assertIn('"status": "failed"', out)
        code, out, _ = self.call(sql, "--json", "gcp-cloud-sql_instance-describe")
        obj = json.loads(out)
        self.assertEqual((code, obj["status"], obj["answer"]),
                         (0, "failed", ["projectId is missing."]))
        self.assertEqual(obj["outputs"], {"exists": None})


if __name__ == "__main__":
    unittest.main()
