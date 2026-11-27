"""Unit tests of a run in more than one command (aleogr_common): the status `continue`
and its `next:` line, the carried file and every way it is refused, its removal, the
bound of eight commands, the deadline passed to a called command and what it reports
(`data.waitRefused`, `data.timeLimit`), the step limit and the environment variables
that may only lower a limit, the uncounted wait, the test aid of the harness's clock,
and the harness's loop (on a copy of the harness, with stand-in commands).

Run: python3 -m unittest discover -s .claude-plugin/tests/unit
No provider is reached and no plugin holds a test skill: the skills here are objects
given to the dispatcher, or modules of a stand-in plugin in a temporary folder.
"""

import io
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from helpers import PLUGINS, aleogr_common as common  # noqa: E402

TESTS = os.path.dirname(HERE)


class FakeClock(object):
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def orchestrator(total=5, per=2, declaration=None, seen=None, end_status="created"):
    """A module object that makes `per` tries in each command until `total`, carrying
    the count, and records what each command saw."""
    seen = [] if seen is None else seen
    declaration = {"bytes": b"{}"} if declaration is None else declaration

    def run(args, ctx):
        digest = common.carry_digest(declaration["bytes"], args)
        carry = ctx.carried(digest)
        seen.append({"commands": ctx.commands, "refusal": ctx.carry_refusal,
                     "carry": carry, "args": dict(args),
                     "sentence": ctx.carry_lost_sentence()})
        tries = (carry or {}).get("tries", 0)
        goal = int(args.get("total", total))
        step = int(args.get("per", per))
        tries = min(goal, tries + step)
        if tries < goal:
            if ctx.may_continue():
                return ctx.continue_run("Waiting: try %d of %d." % (tries, goal),
                                        {"tries": tries, "made": ["line %d" % tries]})
            return ctx.result("pending", {}, lines=["Stopped after %d tries." % tries])
        return ctx.result(end_status, {}, lines=["Done after %d tries." % tries])

    return types.SimpleNamespace(FAMILY="orchestrator", PROVIDER="aleogr",
                                 ACTION="project-apply", DEFAULT_MODE="apply",
                                 RESULT_MODE="apply", CONTINUES=True, run=run, seen=seen)


def block_of(out):
    return json.loads(out.split("```aleogr-result\n", 1)[1].split("\n```", 1)[0])


def next_words(out):
    lines = [line for line in out.splitlines() if line.startswith("next: ")]
    return shlex.split(lines[-1][len("next: "):]) if lines else None


class CarryCase(unittest.TestCase):
    """A private temporary folder for the carried files and a stopped clock."""

    def setUp(self):
        self.top = tempfile.mkdtemp()
        common.set_carry_folder(self.top)
        self.folder = common.carry_folder_path()
        self.clock = FakeClock()
        common.set_clock(self.clock, start=None)
        common.reset_wait_budget()

    def tearDown(self):
        common.set_carry_folder()
        common.set_clock()
        common.reset_wait_budget()
        for d, dirs, files in os.walk(self.top):
            for n in dirs:
                p = os.path.join(d, n)
                if not os.path.islink(p):
                    os.chmod(p, 0o700)
        shutil.rmtree(self.top)

    def command(self, module, words, plugin="aleogr", environ=None):
        """Run `<plugin> <words>` in this process with `module`: (code, out, err)."""
        inv = common.parse_command_line(words)
        mode = inv.args.get("mode") or getattr(module, "DEFAULT_MODE", "plan")
        out, err = io.StringIO(), io.StringIO()
        code = common.run_command(plugin, "/x", inv, module, mode, out, err,
                                  environ={} if environ is None else environ)
        return code, out.getvalue(), err.getvalue()

    def whole_run(self, module, words, limit=20):
        """Run the command, then each `next:` command, as the harness does: the list of
        (code, out) of every command."""
        got = []
        while len(got) < limit:
            code, out, _ = self.command(module, words)
            got.append((code, out))
            if code != 0 or block_of(out)["status"] != "continue":
                break
            nxt = next_words(out)
            self.assertEqual(nxt[0], "aleogr")
            words = nxt[1:]
        return got

    def files(self):
        return sorted(os.listdir(self.folder)) if os.path.isdir(self.folder) else []


class TestContinue(CarryCase):
    def test_a_continue_answer_and_its_next_line(self):
        code, out, err = self.command(orchestrator(), ["project-apply", "confirm=yes"])
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual(lines[0], "Waiting: try 2 of 5.")
        self.assertTrue(lines[1].startswith("next: aleogr project-apply 'confirm=yes' 'run="))
        self.assertEqual(lines[2], "")
        self.assertEqual(lines[3], "```aleogr-result")
        block = block_of(out)
        self.assertEqual((block["status"], block["action"], block["mode"]),
                         ("continue", "project-apply", "apply"))
        words = next_words(out)
        self.assertEqual(words[:3], ["aleogr", "project-apply", "confirm=yes"])
        run_id = words[3][len("run="):]
        self.assertRegex(run_id, r"^[a-z0-9]{12}$")
        self.assertEqual(self.files(), [run_id + ".json"])
        self.assertEqual(stat.S_IMODE(os.stat(self.folder).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(self.folder, run_id + ".json"))
                                      .st_mode), 0o600)

    def test_json_mode_keeps_the_two_lines(self):
        code, out, _ = self.command(orchestrator(), ["--json", "project-apply"])
        obj = json.loads(out)
        self.assertEqual((code, obj["status"]), (0, "continue"))
        self.assertEqual(obj["answer"][0], "Waiting: try 2 of 5.")
        self.assertTrue(obj["answer"][1].startswith("next: aleogr --json project-apply 'run="))

    def test_quoting_of_the_next_line(self):
        value = "a b=c 'd' $HOME `x` \"q\""
        code, out, _ = self.command(orchestrator(),
                                    ["project-apply", "confirm=yes", "note=" + value])
        line = [x for x in out.splitlines() if x.startswith("next: ")][0]
        self.assertIn(" 'note=a b=c '\\''d'\\'' $HOME `x` \"q\"' ", line)
        words = next_words(out)
        self.assertEqual(words[2:4], ["confirm=yes", "note=" + value])
        self.assertEqual(common.quote_argument("it's"), "'it'\\''s'")
        # The second command's next line keeps the same arguments and replaces run=.
        code, out2, _ = self.command(orchestrator(total=9), words[1:])
        words2 = next_words(out2)
        self.assertEqual(words2, words)
        self.assertEqual(sum(1 for w in words2 if w.startswith("run=")), 1)

    def test_the_carry_round_trip_and_its_removal_at_the_end(self):
        m = orchestrator(total=5, per=2)
        got = self.whole_run(m, ["project-apply", "confirm=yes"])
        self.assertEqual([block_of(o)["status"] for _, o in got],
                         ["continue", "continue", "created"])
        self.assertEqual(got[-1][1].splitlines()[0], "Done after 5 tries.")
        self.assertEqual([s["commands"] for s in m.seen], [1, 2, 3])
        self.assertEqual([s["carry"] for s in m.seen],
                         [None, {"tries": 2, "made": ["line 2"]},
                          {"tries": 4, "made": ["line 4"]}])
        self.assertEqual([s["refusal"] for s in m.seen], [None, None, None])
        self.assertTrue(all(s["args"] == {"confirm": "yes"} for s in m.seen),
                        "run= reaches the module")
        self.assertEqual(self.files(), [], "the carried file is removed at the end")
        ids = {next_words(o)[-1] for _, o in got[:-1]}
        self.assertEqual(len(ids), 1, "one id for the whole run")

    def test_a_rewrite_leaves_one_file_and_no_temporary(self):
        m = orchestrator(total=7, per=2)
        _, out, _ = self.command(m, ["project-apply"])
        _, out, _ = self.command(m, next_words(out)[1:])
        run_id = next_words(out)[-1][len("run="):]
        self.assertEqual(self.files(), [run_id + ".json"])
        with open(os.path.join(self.folder, run_id + ".json")) as f:
            record = json.load(f)
        self.assertEqual((record["commands"], record["carry"]["tries"], record["skill"],
                          record["plugin"]), (2, 4, "project-apply", "aleogr"))

    def test_every_other_ending_removes_the_file(self):
        for status in ("failed", "pending", "unchanged"):
            with self.subTest(status=status):
                m = orchestrator(total=3, per=2, end_status=status)
                got = self.whole_run(m, ["project-apply"])
                self.assertEqual(block_of(got[-1][1])["status"], status)
                self.assertEqual(self.files(), [])

    def test_an_aborted_run_removes_the_file(self):
        _, out, _ = self.command(orchestrator(), ["project-apply"])
        self.assertEqual(len(self.files()), 1)

        def run(args, ctx):
            ctx.carried(common.carry_digest(b"{}", args))  # this run's own file
            raise common.TimeLimit(["gcloud", "sql", "instances", "describe", "x"])

        m = types.SimpleNamespace(FAMILY="orchestrator", PROVIDER="aleogr",
                                  ACTION="project-apply", CONTINUES=True, run=run)
        code, out2, _ = self.command(m, next_words(out)[1:])
        self.assertEqual((code, block_of(out2)["status"]), (70, "failed"))
        self.assertEqual(self.files(), [])

    def test_the_bound_of_eight_commands(self):
        m = orchestrator(total=100, per=1)
        got = self.whole_run(m, ["project-apply"])
        self.assertEqual(len(got), common.MAX_COMMANDS)
        self.assertEqual(common.MAX_COMMANDS, 8)
        self.assertEqual([block_of(o)["status"] for _, o in got], ["continue"] * 7 + ["pending"])
        self.assertEqual(got[-1][1].splitlines()[0], "Stopped after 8 tries.")
        self.assertEqual([s["commands"] for s in m.seen], list(range(1, 9)))
        self.assertEqual(self.files(), [])

    def test_continue_run_refuses_past_the_bound(self):
        ctx = common.Context("aleogr", "/x", "project-apply", orchestrator(), "apply", {})
        ctx.carried("d")
        ctx.commands = common.MAX_COMMANDS
        self.assertFalse(ctx.may_continue())
        with self.assertRaises(common.CarryNotSaved):
            ctx.continue_run("x", {})

    def test_a_continue_without_continue_run_is_an_unexpected_error(self):
        def run(args, ctx):
            return ctx.result("continue", {}, lines=["Waiting."])

        m = types.SimpleNamespace(FAMILY="orchestrator", PROVIDER="aleogr",
                                  ACTION="project-apply", CONTINUES=True, run=run)
        code, out, err = self.command(m, ["project-apply"])
        self.assertEqual((code, block_of(out)["status"]), (70, "failed"))
        self.assertIn(common.UNEXPECTED_SENTENCE, out)
        m.CONTINUES = False
        code, out, _ = self.command(m, ["project-apply"])
        self.assertEqual((code, block_of(out)["status"]), (70, "failed"))

    def test_continue_run_needs_carried_first(self):
        def run(args, ctx):
            return ctx.continue_run("Waiting.", {})

        m = types.SimpleNamespace(FAMILY="orchestrator", PROVIDER="aleogr",
                                  ACTION="project-apply", CONTINUES=True, run=run)
        code, out, _ = self.command(m, ["project-apply"])
        self.assertEqual((code, block_of(out)["status"]), (70, "failed"))
        self.assertEqual(self.files(), [])

    def test_run_is_an_ordinary_argument_of_a_skill_that_does_not_continue(self):
        seen = []

        def run(args, ctx):
            seen.append(dict(args))
            return ctx.failed("The argument run is not known.", {})

        m = types.SimpleNamespace(FAMILY="orchestrator", PROVIDER="aleogr",
                                  ACTION="project-plan", run=run)
        _, out, _ = self.command(m, ["project-plan", "run=abcdefabcdef"])
        self.assertEqual(seen, [{"run": "abcdefabcdef"}])
        self.assertEqual(self.files(), [])

    def test_old_files_are_removed_when_a_run_starts(self):
        os.mkdir(self.folder, 0o700)
        old = os.path.join(self.folder, "aaaaaaaaaaaa.json")
        young = os.path.join(self.folder, "bbbbbbbbbbbb.json")
        for p in (old, young):
            with open(p, "w") as f:
                f.write("{}")
        two_days = 2 * 24 * 60 * 60
        os.utime(old, (os.path.getmtime(old) - two_days,) * 2)
        self.command(orchestrator(total=2, per=2), ["project-apply"])
        self.assertEqual(self.files(), ["bbbbbbbbbbbb.json"])


class TestCarryRefusals(CarryCase):
    def first(self, module=None):
        """Run a first command: (the module, the words of its next command, the file)."""
        m = module or orchestrator(total=9)
        _, out, _ = self.command(m, ["project-apply", "confirm=yes"])
        words = next_words(out)
        path = os.path.join(self.folder, words[-1][len("run="):] + ".json")
        self.assertTrue(os.path.isfile(path))
        return m, words[1:], path

    def refused(self, m, words, why):
        code, out, _ = self.command(m, words)
        last = m.seen[-1]
        self.assertEqual(code, 0)
        self.assertEqual((last["refusal"], last["carry"], last["commands"]), (why, None, 1))
        self.assertEqual(last["sentence"], "An earlier part of this run could not be "
                         "recalled: %s." % common.CARRY_REFUSALS[why])
        return out

    def test_the_id_must_be_well_formed(self):
        m = orchestrator(total=9)
        for bad in ("", "ABCDEFABCDEF", "abc", "abcdefabcdefa", "../../../etc",
                    "abcdefabcde/", "abcdefabcdeF"):
            with self.subTest(run=bad):
                out = self.refused(m, ["project-apply", "confirm=yes", "run=" + bad],
                                   "malformed")
                # It goes on as a new run, under a new id.
                self.assertNotEqual(next_words(out)[-1], "run=" + bad)

    def test_a_missing_file(self):
        self.refused(orchestrator(), ["project-apply", "run=abcdefabcdef"], "missing")
        m, words, path = self.first()
        os.remove(path)
        self.refused(m, words, "missing")

    def test_invalid_json_and_an_invalid_record(self):
        for content in (b"not json", b"\xff\xfe", b"[]", b'{"aleogr-run": 1}',
                        json.dumps({"aleogr-run": 1, "plugin": "aleogr",
                                    "skill": "project-apply", "digest": "d",
                                    "commands": 8, "carry": {}}).encode(),
                        json.dumps({"aleogr-run": 1, "plugin": "aleogr",
                                    "skill": "project-apply", "digest": "d",
                                    "commands": True, "carry": {}}).encode(),
                        b" " * (common.MAX_CARRY_BYTES + 1)):
            with self.subTest(content=content[:40]):
                m, words, path = self.first()
                with open(path, "wb") as f:
                    f.write(content)
                self.refused(m, words, "invalid")

    def test_a_file_open_to_others(self):
        m, words, path = self.first()
        os.chmod(path, 0o644)
        self.refused(m, words, "not-private")

    def test_a_link_at_the_file_s_name(self):
        m, words, path = self.first()
        real = os.path.join(self.top, "elsewhere.json")
        shutil.move(path, real)
        os.symlink(real, path)
        self.refused(m, words, "not-private")
        self.assertTrue(os.path.isfile(real), "the target of a link is never removed")

    def test_a_folder_open_to_others_is_neither_read_nor_written(self):
        m, words, path = self.first()
        os.chmod(self.folder, 0o755)
        out = self.refused(m, words, "not-private")
        # The run cannot be carried on: it ends as at its limit, and writes nothing.
        self.assertEqual(block_of(out)["status"], "pending")
        self.assertEqual(self.files(), [os.path.basename(path)])

    def test_a_link_in_place_of_the_folder(self):
        m, words, path = self.first()
        real = os.path.join(self.top, "real-folder")
        shutil.move(self.folder, real)
        os.symlink(real, self.folder)
        out = self.refused(m, words, "not-private")
        self.assertEqual(block_of(out)["status"], "pending")
        self.assertEqual(sorted(os.listdir(real)), [os.path.basename(path)])

    def test_a_file_of_another_user(self):
        if not hasattr(os, "getuid") or os.getuid() != 0:
            self.skipTest("only root can give a file to another user")
        m, words, path = self.first()
        os.chown(path, 12345, -1)
        self.refused(m, words, "not-private")

    def test_a_different_digest(self):
        declaration = {"bytes": b'{"name": "demo"}'}
        m, words, path = self.first(orchestrator(total=9, declaration=declaration))
        declaration["bytes"] = b'{"name": "other"}'
        out = self.refused(m, words, "mismatch")
        # A new run under a new id; the file `run=` named is another run's (its digest
        # differs): it is never removed by this one, only by the sweep.
        self.assertNotEqual(next_words(out)[-1], words[-1])
        self.assertTrue(os.path.exists(path))
        self.assertEqual(len(self.files()), 2)

    def test_a_file_of_another_skill(self):
        m, words, path = self.first()
        with open(path) as f:
            record = json.load(f)
        record["skill"] = "platform-apply"
        with open(path, "w") as f:
            json.dump(record, f)
        self.refused(m, words, "mismatch")


class TestTheReviewOfPart3a(CarryCase):
    """The shared module's part of the review's findings: the digest saved at the end of
    a command (C1), only this run's own file removed (M3), a carry the module refuses
    (M1), and the aborted answer of a module that calls others (I2)."""

    def test_the_digest_given_to_continue_run_is_the_one_saved(self):
        declaration = {"bytes": b"before"}

        def run(args, ctx):
            carry = ctx.carried(common.carry_digest(declaration["bytes"], args))
            if carry is None:
                declaration["bytes"] = b"after"  # the command rewrites what it is made of
                return ctx.continue_run("Waiting.", {"n": 1}, digest=common.carry_digest(
                    declaration["bytes"], args))
            return ctx.result("updated", {}, lines=["carried %d" % carry["n"]])

        m = types.SimpleNamespace(FAMILY="orchestrator", PROVIDER="aleogr",
                                  ACTION="project-apply", DEFAULT_MODE="apply",
                                  RESULT_MODE="apply", CONTINUES=True, run=run)
        got = self.whole_run(m, ["project-apply", "confirm=yes"])
        self.assertEqual(len(got), 2)
        self.assertTrue(got[-1][1].startswith("carried 1\n"))
        self.assertEqual(self.files(), [])

    def test_a_carry_the_module_refuses_goes_on_as_a_new_run_and_is_kept(self):
        seen = []

        def run(args, ctx):
            carry = ctx.carried(common.carry_digest(b"{}", args))
            if carry is not None and carry.get("tries") != 1:
                ctx.refuse_carry("invalid")
                carry = None
            seen.append((ctx.carry_refusal, ctx.commands, ctx.carry_lost_sentence()))
            if carry is None and ctx.carry_refusal is None:
                return ctx.continue_run("Waiting.", {"tries": 1})
            return ctx.result("updated", {}, lines=["done"])

        m = types.SimpleNamespace(FAMILY="orchestrator", PROVIDER="aleogr",
                                  ACTION="project-apply", DEFAULT_MODE="apply",
                                  RESULT_MODE="apply", CONTINUES=True, run=run)
        _, out, _ = self.command(m, ["project-apply"])
        words = next_words(out)
        path = os.path.join(self.folder, words[-1][len("run="):] + ".json")
        with open(path) as f:
            record = json.load(f)
        record["carry"]["tries"] = 99  # edited by hand
        with open(path, "w") as f:
            json.dump(record, f)
        self.command(m, words[1:])
        self.assertEqual(seen[-1], ("invalid", 1, common.CARRY_LOST_SENTENCE.format(
            why=common.CARRY_REFUSALS["invalid"])))
        self.assertTrue(os.path.isfile(path), "a refused file is not this run's: kept")

    def test_an_accepted_file_is_removed_and_a_refused_one_kept(self):
        m, words, path = TestCarryRefusals.first(self, orchestrator(total=4))
        self.command(m, words)  # accepted, and the run ends
        self.assertFalse(os.path.exists(path))

    def test_an_aborted_module_that_calls_others_never_says_nothing_was_written(self):
        class Orchestrator(object):
            FAMILY, PROVIDER, ACTION, CONTINUES = "orchestrator", "aleogr", "project-apply", True

        class Caller(object):
            FAMILY, PROVIDER, ACTION, CALLS_OTHERS = "x", "aleogr", "x", True

        for module in (Orchestrator, Caller):
            with self.subTest(module=module.__name__):
                ctx = common.Context("aleogr", "/x", "project-apply", module, "apply", {})
                self.assertEqual(common.aborted_result(ctx, common.TIME_LIMIT_SENTENCE).lines,
                                 [common.TIME_LIMIT_SENTENCE, common.REFUSED_UNKNOWN,
                                  common.READ_STATE_SENTENCE])
                self.assertEqual(common.refused_result(ctx).lines,
                                 [common.REFUSED_SENTENCE, common.REFUSED_UNKNOWN])
                ctx.on_abort(["github_repo-create: created", "This run started it."])
                self.assertEqual(common.aborted_result(ctx, common.UNEXPECTED_SENTENCE).lines,
                                 [common.UNEXPECTED_SENTENCE, "github_repo-create: created",
                                  "This run started it.", common.READ_STATE_SENTENCE])
                self.assertEqual(common.refused_result(ctx).lines,
                                 [common.REFUSED_SENTENCE, "github_repo-create: created",
                                  "This run started it."])


class TestTheClockAcrossCommands(unittest.TestCase):
    def setUp(self):
        common.reset_wait_budget()
        self.clock = FakeClock()
        self.wall = FakeClock(1800000000.0)
        common.set_clock(self.clock, start=self.clock.t, wall=self.wall)

    def tearDown(self):
        common.set_clock()
        common.reset_wait_budget()

    def test_limits(self):
        self.assertEqual((common.STEP_LIMIT, common.CALL_MARGIN), (240, 30))
        self.assertEqual((common.run_deadline(), common.wait_clock_limit(),
                          common.step_limit()), (570, 420, 240))

    def test_the_step_limit(self):
        self.assertTrue(common.step_allowed())
        self.clock.t += 240
        self.assertTrue(common.step_allowed())
        self.clock.t += 0.5
        self.assertFalse(common.step_allowed())
        ctx = common.Context("aleogr", "/x", "project-apply", object(), "apply", {})
        self.assertFalse(ctx.step_allowed())

    def test_the_environment_may_only_lower_the_step_and_wait_limits(self):
        common.start_clock({"ALEOGR_STEP_LIMIT": "100", "ALEOGR_WAIT_CLOCK_LIMIT": "60"})
        self.assertEqual((common.step_limit(), common.wait_clock_limit(),
                          common.run_deadline()), (100, 60, 570))
        self.clock.t += 30
        self.assertTrue(common.wait_allowed())
        self.clock.t += 0.5
        self.assertFalse(common.wait_allowed())
        self.clock.t += 69.5
        self.assertTrue(common.step_allowed())
        self.clock.t += 0.5
        self.assertFalse(common.step_allowed())
        for value in ("241", "600", "0", "-5", "abc", "1.5", "", " 100", "100s", "1e2"):
            with self.subTest(value=value):
                common.start_clock({"ALEOGR_STEP_LIMIT": value,
                                    "ALEOGR_WAIT_CLOCK_LIMIT": value.replace("241", "421")})
                self.assertEqual((common.step_limit(), common.wait_clock_limit()), (240, 420))
        common.start_clock({"ALEOGR_STEP_LIMIT": "1", "ALEOGR_WAIT_CLOCK_LIMIT": "420"})
        self.assertEqual((common.step_limit(), common.wait_clock_limit()), (1, 420))

    def test_a_caller_s_deadline_lowers_the_limits(self):
        limits = common.clock_limits({"ALEOGR_RUN_ENDS": "%.3f" % (self.wall.t + 300)},
                                     self.wall.t)
        self.assertEqual(limits, {"deadline": 300, "wait": 150, "step": 0})
        limits = common.clock_limits({"ALEOGR_RUN_ENDS": "%.3f" % (self.wall.t + 500)},
                                     self.wall.t)
        self.assertEqual(limits, {"deadline": 500, "wait": 350, "step": 170})
        limits = common.clock_limits({"ALEOGR_RUN_ENDS": "%.3f" % (self.wall.t - 50)},
                                     self.wall.t)
        self.assertEqual(limits, {"deadline": 0, "wait": 0, "step": 0})
        own = {"deadline": 570, "wait": 420, "step": 240}
        for value in ("%.3f" % (self.wall.t + 5000), "soon", "-1", "1e12", ""):
            with self.subTest(value=value):
                self.assertEqual(common.clock_limits({"ALEOGR_RUN_ENDS": value}, self.wall.t),
                                 own)
        both = common.clock_limits({"ALEOGR_RUN_ENDS": "%.3f" % (self.wall.t + 500),
                                    "ALEOGR_WAIT_CLOCK_LIMIT": "100"}, self.wall.t)
        self.assertEqual(both["wait"], 100)
        common.start_clock({"ALEOGR_RUN_ENDS": "%.3f" % (self.wall.t + 300)})
        self.assertEqual(common.remaining_seconds(), 300)
        self.assertTrue(common.step_allowed())
        self.clock.t += 0.5
        self.assertFalse(common.step_allowed(), "no step is left to a callee with 300 s")
        self.clock.t += 124.5
        self.assertFalse(common.wait_allowed())

    def test_call_plugin_passes_the_deadline(self):
        top = tempfile.mkdtemp()
        old = os.environ["PATH"]
        try:
            cmd = os.path.join(top, "aleogr-demo")
            with open(cmd, "w") as f:
                f.write('#!/bin/sh\necho "{\\"aleogr-result\\": 1, \\"status\\": '
                        '\\"unchanged\\", \\"ends\\": \\"$ALEOGR_RUN_ENDS\\"}"\n')
            os.chmod(cmd, 0o755)
            os.environ["PATH"] = top + os.pathsep + "/bin" + os.pathsep + "/usr/bin"
            self.clock.t += 100
            got = common.call_plugin("aleogr-demo", "demo_skill")
            self.assertEqual(float(got["ends"]), self.wall.t + 570 - 100 - 30)
            # A command that was itself called passes on what is left of its own.
            common.start_clock({"ALEOGR_RUN_ENDS": "%.3f" % (self.wall.t + 200)})
            self.clock.t += 50
            got = common.call_plugin("aleogr-demo", "demo_skill")
            self.assertEqual(float(got["ends"]), self.wall.t + 200 - 50 - 30)
            self.clock.t += 1000
            got = common.call_plugin("aleogr-demo", "demo_skill")
            self.assertEqual(float(got["ends"]), self.wall.t)
        finally:
            os.environ["PATH"] = old
            shutil.rmtree(top)

    def test_the_uncounted_wait(self):
        ctx = common.Context("aleogr", "/x", "project-apply", object(), "apply", {})
        ran = []
        ctx.execute = lambda argv, timeout=None: ran.append(argv) or common.Completed(0, "", "")
        self.assertEqual([ctx.wait(counted=False) for _ in range(30)], [True] * 30)
        self.assertEqual(common.waited_seconds(), 0)
        self.assertEqual(ran, [["sleep", "30"]] * 30)
        self.assertFalse(ctx.wait_refused)
        self.assertEqual([ctx.wait() for _ in range(17)], [True] * 16 + [False])
        self.assertTrue(ctx.wait_refused)
        self.assertTrue(ctx.wait(counted=False), "the count does not limit it")

    def test_the_uncounted_wait_ends_on_the_clock(self):
        ctx = common.Context("aleogr", "/x", "project-apply", object(), "apply", {})

        def execute(argv, timeout=None):
            self.clock.t += 30
            return common.Completed(0, "", "")

        ctx.execute = execute
        got = [ctx.wait(counted=False) for _ in range(16)]
        self.assertEqual(got, [True] * 14 + [False] * 2)
        self.assertTrue(ctx.wait_refused)

    def test_the_test_aid_of_the_harness_s_clock(self):
        top = tempfile.mkdtemp()
        try:
            log = os.path.join(top, "calls.log")
            with open(log, "w") as f:
                f.write("sleep 30\n")
            aid = {"ALEOGR_TEST_SLEEP_CLOCK": "1", "FAKE_LOG": log}
            common.start_clock(aid)
            self.assertEqual(common.elapsed_seconds(), 0)
            with open(log, "a") as f:
                f.write("sleep 30\nprojects list\nsleep 30\ngh sleep 30\nsleep 30 x\n")
            self.assertEqual(common.elapsed_seconds(), 60)
            self.clock.t += 5
            self.assertEqual(common.elapsed_seconds(), 65)
            with open(log, "w") as f:
                f.write("")  # a shorter log never moves the clock back
            self.assertEqual(common.elapsed_seconds(), 5)
            with open(log, "a") as f:
                f.write("sleep 30\n" * 10)
            for env in ({"ALEOGR_TEST_SLEEP_CLOCK": "1"},
                        {"ALEOGR_TEST_SLEEP_CLOCK": "yes", "FAKE_LOG": log},
                        {"FAKE_LOG": log}):
                with self.subTest(env=env):
                    common.start_clock(env)
                    with open(log, "a") as f:
                        f.write("sleep 30\n")
                    self.assertEqual(common.elapsed_seconds(), 0)
        finally:
            shutil.rmtree(top)


# A stand-in plugin (in a temporary folder, never under plugins/) for what a called
# command reports, and for the harness's loop.
STAND_INS = {
    "demo_wait": '''
FAMILY, PROVIDER, ACTION = "db", "demo", "demo-wait"
def run(args, ctx):
    if not ctx.wait():
        return ctx.result("pending", {}, lines=["The wait was refused."])
    return ctx.result("unchanged", {}, lines=["Waited."])
''',
    "demo_slow": '''
FAMILY, PROVIDER, ACTION = "db", "demo", "demo-slow"
def run(args, ctx):
    ctx.read(["gcloud", "projects", "describe", "demo"])
    return ctx.result("unchanged", {})
''',
    "demo_apply": '''
import aleogr_common as common
FAMILY, PROVIDER, ACTION = "orchestrator", "demo", "demo-apply"
DEFAULT_MODE = RESULT_MODE = "apply"
CONTINUES = True
def run(args, ctx):
    carry = ctx.carried(common.carry_digest(args)) or {"tries": 0}
    total = int(args.get("total", "30"))
    tries = carry["tries"]
    while tries < total:
        if not ctx.step_allowed() or not ctx.wait(counted=False):
            if ctx.may_continue():
                return ctx.continue_run("Waiting: try %d of %d." % (tries, total),
                                        {"tries": tries})
            return ctx.result("pending", {}, lines=["Stopped after %d tries." % tries])
        tries += 1
    return ctx.result("created", {}, lines=["Ready after %d tries in %d commands."
                                            % (tries, ctx.commands)])
''',
}

# A command that misbehaves: `loopy wrong` names another skill in its next: line,
# `loopy forever` always continues.
LOOPY = r'''#!/bin/sh
echo "loopy $*" >> "$FAKE_LOG"
case "$1" in wrong) next="loopy other 'a=1' 'run=aaaaaaaaaaaa'" ;; *) next="loopy $1 'a=1' 'run=aaaaaaaaaaaa'" ;; esac
printf 'Waiting.\nnext: %s\n\n```aleogr-result\n{ "aleogr-result": 1, "status": "continue" }\n```\n' "$next"
'''


def make_plugin(root, name):
    os.makedirs(os.path.join(root, "bin"))
    os.makedirs(os.path.join(root, "scripts", "skills"))
    shutil.copy(os.path.join(PLUGINS, "aleogr", "bin", "aleogr"),
                os.path.join(root, "bin", name))
    shutil.copy(os.path.join(PLUGINS, "aleogr", "scripts", "aleogr_common.py"),
                os.path.join(root, "scripts"))
    open(os.path.join(root, "scripts", "skills", "__init__.py"), "w").close()
    for skill, text in STAND_INS.items():
        with open(os.path.join(root, "scripts", "skills", skill + ".py"), "w") as f:
            f.write(text)


class TestWhatACalledCommandReports(unittest.TestCase):
    def setUp(self):
        self.top = tempfile.mkdtemp()
        make_plugin(os.path.join(self.top, "demo"), "demo")
        self.bin = os.path.join(self.top, "tools")
        os.makedirs(self.bin)
        with open(os.path.join(self.bin, "gcloud"), "w") as f:
            f.write("#!/bin/sh\nexec %s -c 'import time; time.sleep(5)'\n" % sys.executable)
        os.chmod(os.path.join(self.bin, "gcloud"), 0o755)
        with open(os.path.join(self.bin, "sleep"), "w") as f:
            f.write("#!/bin/sh\nexit 0\n")
        os.chmod(os.path.join(self.bin, "sleep"), 0o755)
        self.old_path = os.environ["PATH"]
        os.environ["PATH"] = os.pathsep.join([os.path.join(self.top, "demo", "bin"), self.bin,
                                              os.path.dirname(sys.executable), "/bin",
                                              "/usr/bin"])
        self.clock = FakeClock()
        common.set_clock(self.clock, start=self.clock.t)

    def tearDown(self):
        os.environ["PATH"] = self.old_path
        common.set_clock()
        shutil.rmtree(self.top)

    def test_a_wait_refused_by_the_caller_s_clock(self):
        got = common.call_plugin("demo", "demo_wait")
        self.assertEqual(got["status"], "unchanged")
        self.assertFalse(common.ended_by_limit(got))
        self.assertNotIn("data", got)
        # 60 s are left to the callee: its waits end 150 s before its deadline, so none.
        self.clock.t += 570 - 30 - 60
        got = common.call_plugin("demo", "demo_wait")
        self.assertEqual((got["status"], got["answer"]), ("pending", ["The wait was refused."]))
        self.assertEqual(got["data"], {"waitRefused": True})
        self.assertTrue(common.ended_by_limit(got))
        self.assertNotIn("callError", got)

    def test_a_callee_stopped_by_its_deadline(self):
        self.clock.t += 570 - 30 - 2  # the callee has two seconds
        got = common.call_plugin("demo", "demo_slow")
        self.assertEqual((got["status"], got["callError"]), ("failed", "time-limit"))
        self.assertEqual(got["data"], {"timeLimit": True})
        self.assertIn(common.TIME_LIMIT_SENTENCE, got["answer"])
        self.assertTrue(common.ended_by_limit(got))
        self.assertFalse(common.ended_by_limit({"status": "failed", "callError": "refused"}))


class TestTheHarnessLoop(unittest.TestCase):
    """The direct mode of a copy of run.sh, with the real fakes and stand-in plugins."""

    def setUp(self):
        self.top = tempfile.mkdtemp()
        tests = os.path.join(self.top, "tests")
        os.makedirs(os.path.join(tests, "scenarios"))
        shutil.copy(os.path.join(TESTS, "run.sh"), tests)
        shutil.copytree(os.path.join(TESTS, "bin"), os.path.join(tests, "bin"))
        make_plugin(os.path.join(self.top, "plugins", "demo"), "demo")
        loopy = os.path.join(self.top, "plugins", "loopy", "bin", "loopy")
        os.makedirs(os.path.dirname(loopy))
        with open(loopy, "w") as f:
            f.write(LOOPY)
        os.chmod(loopy, 0o755)
        self.tests = tests

    def tearDown(self):
        shutil.rmtree(self.top)

    def scenario(self, name, prompt, expect, clock=None):
        d = os.path.join(self.tests, "scenarios", name)
        os.makedirs(os.path.join(d, "responses"))
        with open(os.path.join(d, "prompt.txt"), "w") as f:
            f.write(prompt + "\n")
        with open(os.path.join(d, "expect.txt"), "w") as f:
            f.write("\n".join(expect) + "\n")
        if clock is not None:
            with open(os.path.join(d, "clock"), "w") as f:
                f.write(clock)
        env = dict(os.environ, RUN_MODE="direct", PYTHONDONTWRITEBYTECODE="1")
        for k in ("ALEOGR_RUN_ENDS", "ALEOGR_STEP_LIMIT", "ALEOGR_WAIT_CLOCK_LIMIT",
                  "ALEOGR_TEST_SLEEP_CLOCK"):
            env.pop(k, None)
        p = subprocess.run(["bash", os.path.join(self.tests, "run.sh"), name],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, env=env)
        return p.returncode, p.stdout.decode()

    def test_one_command_without_the_clock_file(self):
        code, out = self.scenario("one", "/demo:demo_apply total=30", [
            "OUTPUT ^Ready after 30 tries in 1 commands\\.$",
            "COUNT 30 ^sleep 30$", "AT_MOST 30 ^sleep 30$"])
        self.assertEqual((code, out), (0, "PASS one\n"))

    def test_the_clock_file_makes_the_run_continue_until_it_ends(self):
        # Each wait is 30 s of the clock: 8 tries per command (after the eighth the clock
        # is just past the step limit of 240 s), so 8 + 8 + 8 + 6 in four commands.
        code, out = self.scenario("clocked", "/demo:demo_apply total=30", [
            "OUTPUT ^Ready after 30 tries in 4 commands\\.$",
            "OUTPUT_NOT ^next: ", "OUTPUT_NOT Waiting",
            "COUNT 30 ^sleep 30$", "AT_MOST 30 ^sleep 30$"], clock="sleep-counts\n")
        self.assertEqual((code, out), (0, "PASS clocked\n"))
        # The answer checked is the last command's, the call log is the whole run's.
        code, out = self.scenario("clocked-fails", "/demo:demo_apply total=30", [
            "OUTPUT ^Waiting: try 8 of 30\\.$"], clock="sleep-counts\n")
        self.assertEqual(code, 1)
        self.assertIn("commands (4):", out)
        self.assertIn("  demo demo_apply total=30 run=", out)

    def test_the_bound_of_eight_commands(self):
        code, out = self.scenario("bound", "/demo:demo_apply total=100", [
            "OUTPUT ^Stopped after 64 tries\\.$", "COUNT 64 ^sleep 30$",
            "AT_MOST 64 ^sleep 30$"], clock="sleep-counts")
        self.assertEqual((code, out), (0, "PASS bound\n"))

    def test_a_next_line_of_another_skill_fails(self):
        code, out = self.scenario("wrong", "/loopy:wrong a=1", ["CALLED ^loopy wrong"])
        self.assertEqual(code, 1)
        self.assertIn("(the answer says continue, but its next: line is not this command)",
                      out)
        self.assertIn("commands (1):", out)

    def test_a_run_that_never_ends_fails_after_eight_commands(self):
        code, out = self.scenario("forever", "/loopy:forever a=1",
                                  ["AT_MOST 8 ^loopy forever", "COUNT 8 ^loopy forever"])
        self.assertEqual(code, 1)
        self.assertIn("(the run did not end within eight commands)", out)
        self.assertIn("commands (8):", out)

    def test_a_bad_clock_file(self):
        code, out = self.scenario("bad-clock", "/demo:demo_apply total=1", ["CALLED ."],
                                  clock="fast\n")
        self.assertEqual(code, 2)
        self.assertIn("bad clock file", out)


if __name__ == "__main__":
    unittest.main()
