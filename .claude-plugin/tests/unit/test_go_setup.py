"""Unit tests of go_setup: its plan and apply, the cases no scenario covers, and its
golden commands. Each test runs in a temporary folder of its own. The scenarios go-setup-*
cover the rest, in the direct mode."""

import io
import os
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import aleogr_common as common, load_skill, plugin_root  # noqa: E402

PLUGIN = "aleogr-stack-go"
SKILL = "go_setup"
ROOT = plugin_root(PLUGIN)
skill = load_skill(PLUGIN, SKILL)

MODULES = "cloud.google.com/go/cloudsqlconn@v1.27.1,github.com/jackc/pgx/v5@v5.13.0"
ARGS = {"component": "web", "path": "web", "version": "1.27",
        "module": "github.com/example-org/example-repo/web"}
DB = dict(ARGS, database="yes", modules=MODULES, minVersion="1.26")


class FakeContext(common.Context):
    def __init__(self, args):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill, "plan", args)
        self.calls = []

    def read(self, argv, timeout=None):
        self.calls.append(argv)
        return common.Completed(0, "", "")

    run = read


def template(name, component="web"):
    with open(os.path.join(ROOT, "files", name), "rb") as f:
        return f.read().replace(b"{{COMPONENT}}", component.encode())


class Folder(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.dir = tempfile.mkdtemp()
        os.chdir(self.dir)

    def tearDown(self):
        os.chdir(self.old)
        shutil.rmtree(self.dir)

    def write(self, name, data):
        d = os.path.dirname(name)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(name, "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode())

    def plan(self, args):
        ctx = FakeContext(args)
        before = sorted(os.walk("."))
        r = skill.run(dict(args), ctx)
        self.assertEqual(ctx.calls, [], "plan runs no command")
        self.assertEqual(sorted(os.walk(".")), before, "plan writes nothing")
        self.assertEqual(r.block["mode"], "plan")
        self.assertFalse(r.block["outputs"]["written"])
        return r


class TestArguments(Folder):
    def test_failures(self):
        cases = (
            ({}, "Missing required arguments: component, version, module; nothing was read "
                 "or written."),
            (dict(ARGS, extra="1"), "extra is not an argument of go_setup."),
            (dict(ARGS, version="1.20"), "Go 1.20 is earlier than 1.22, which the template's "
                                         "GET /{$} patterns need."),
            (dict(ARGS, version="1.27.4"), "version must be <major>.<minor>, such as 1.27."),
            (dict(ARGS, module="github.com/example-org/example-repo/other"), None),
            (dict(ARGS, module="github.com/-bad/example-repo/web"), None),
            (dict(ARGS, path="a//b", module="github.com/o/r/a//b"), None),
            (dict(ARGS, path=".github/web", module="github.com/o/r/.github/web"), None),
            (dict(ARGS, path="-R", module="github.com/o/r/-R"), None),
            (dict(ARGS, dockerfile="maybe"), "dockerfile must be yes or no."),
            (dict(ARGS, database="maybe"), "database must be yes or no."),
            (dict(ARGS, modules=MODULES), "modules is only allowed with database=yes."),
            (dict(ARGS, minVersion="1.26"), "minVersion is only allowed with database=yes."),
            (dict(DB, modules=""), "Missing required argument: modules; nothing was read or "
                                   "written."),
            (dict(DB, modules="github.com/jackc/pgx/v5@v5.13.0"), None),
            (dict(DB, modules=MODULES + ",x@v1.0.0"), None),
            (dict(DB, modules="github.com/jackc/pgx/v5@5.13.0"), None),
            (dict(DB, version="1.25"), "Go 1.25 is earlier than 1.26, the earliest version of "
                                       "a component that uses the database; nothing was "
                                       "written."),
            (dict(ARGS, mode="dry"), "mode must be plan or apply."),
        )
        for args, line in cases:
            with self.subTest(args=args):
                r = self.plan(args)
                self.assertEqual(r.status, "failed")
                self.assertEqual(len(r.lines), 1, r.lines)
                if line:
                    self.assertEqual(r.lines, [line])
                o = r.block["outputs"]
                self.assertEqual((o["module"], o["files"], o["dockerfile"], o["ci"]),
                                 (None, [], None, None))

    def test_argument_outputs(self):
        o = self.plan({"component": "web"}).block["outputs"]
        self.assertEqual((o["component"], o["path"], o["database"]), ("web", "web", "not-asked"))
        o = self.plan(dict(DB, component="Web", path="-x")).block["outputs"]
        self.assertEqual((o["component"], o["path"], o["route"]), (None, None, None))

    def test_version_compared_as_numbers(self):
        self.assertEqual(skill.validate(dict(ARGS, version="1.100")), [])
        self.assertEqual(skill.validate(dict(ARGS, path="services/api.v2_x",
                                             module="github.com/o/r.x/services/api.v2_x")), [])


class TestPlan(Folder):
    def test_existing_module_is_unchanged(self):
        self.write("web/go.mod", "")
        r = self.plan(ARGS)
        self.assertEqual((r.status, r.block["outputs"]["dockerfile"]), ("unchanged", "not-asked"))

    def test_pending_go_files_without_go_mod(self):
        self.write("web/handler.go", "package main\n")
        os.makedirs("web/sub.go")
        r = self.plan(dict(DB, dockerfile="yes"))
        o = r.block["outputs"]
        self.assertEqual(r.status, "pending")
        self.assertEqual(r.block["pending"], [{"item": "web has Go files but no go.mod",
                                               "reason": "manual",
                                               "how": "add a go.mod to web, or empty the folder"}])
        self.assertEqual((o["dockerfile"], o["database"], o["route"], o["modules"]),
                         ("would-write", "would-write", "would-add", "would-add"))

    def test_a_go_folder_is_not_a_go_file(self):
        os.makedirs("web/x.go")
        self.assertEqual(self.plan(ARGS).status, "would-create")

    def test_new_component_with_a_dockerfile(self):
        self.write("web/Dockerfile", "FROM scratch\n")
        r = self.plan(dict(ARGS, dockerfile="yes"))
        self.assertEqual((r.status, r.block["outputs"]["dockerfile"]), ("would-create", "present"))
        self.assertEqual(r.block["outputs"]["files"][-1], "web/Dockerfile")

    def test_dockerfile_folder_fails(self):
        self.write("web/go.mod", "module x\n")
        os.makedirs("web/Dockerfile")
        r = self.plan(dict(ARGS, dockerfile="yes"))
        self.assertEqual((r.status, r.block["outputs"]["dockerfile"]), ("failed", None))
        self.assertEqual(r.lines, ["web/Dockerfile is a folder; nothing was written."])

    def test_path_is_a_file_fails(self):
        self.write("web", "x")
        r = self.plan(ARGS)
        self.assertEqual(r.status, "failed")
        self.assertEqual(r.block["outputs"]["ci"]["inputs"]["working-directory"], "web")

    def test_go_mod_is_a_folder_fails(self):
        os.makedirs("web/go.mod")
        self.assertEqual(self.plan(ARGS).status, "failed")

    def test_existing_module_everything_present(self):
        self.write("web/go.mod", "module m\n\ngo 1.27\n\nrequire (\n\tcloud.google.com/go/"
                   "cloudsqlconn v1.0.0\n\tgithub.com/jackc/pgx/v5 v5.0.0 // indirect\n)\n")
        self.write("web/db.go", "")
        self.write("web/db_test.go", "x")
        self.write("web/main.go", template("main-database.go.tmpl"))
        self.write("web/Dockerfile", "x")
        r = self.plan(dict(DB, dockerfile="yes"))
        o = r.block["outputs"]
        self.assertEqual((r.status, o["database"], o["route"], o["modules"], o["dockerfile"]),
                         ("unchanged", "present", "present", "present", "present"))
        self.assertEqual(o["files"], ["web/go.mod", "web/main.go", "web/main_test.go",
                                      "web/go.sum", "web/db.go", "web/db_test.go",
                                      "web/Dockerfile"])

    def test_require_line_form(self):
        self.assertEqual(skill.required_modules(
            "require github.com/jackc/pgx/v5 v5.1.0\nrequire other v1\n",
            ["github.com/jackc/pgx/v5", "cloud.google.com/go/cloudsqlconn"]),
            {"github.com/jackc/pgx/v5"})

    def test_someones_main_is_manual_and_modules_not_needed(self):
        self.write("web/go.mod", "module m\n\ngo 1.27\n")
        self.write("web/db.go", "package main\n")
        self.write("web/db_test.go", "package main\n")
        self.write("web/main.go", template("main.go.tmpl")[:-1])
        r = self.plan(DB)
        o = r.block["outputs"]
        self.assertEqual((r.status, o["database"], o["route"], o["modules"]),
                         ("unchanged", "present", "manual", "not-needed"))
        self.assertEqual(r.block["pending"], [{
            "item": "route", "reason": "manual",
            "how": "add the line mux.HandleFunc(\"GET /db\", dbCheck) to the router in "
                   "web/main.go; until then the tests of web/db_test.go, which expect the "
                   "route, fail"}])

    def test_imports_in_a_subfolder_mean_would_add(self):
        self.write("web/go.mod", "module m\n\ngo 1.27\n")
        self.write("web/db.go", "package main\n")
        self.write("web/db_test.go", "package main\n")
        self.write("web/store/s.go", 'import "github.com/jackc/pgx/v5/pgxpool"\n')
        r = self.plan(DB)
        o = r.block["outputs"]
        self.assertEqual((r.status, o["route"], o["modules"]),
                         ("would-create", "manual", "would-add"))

    def test_import_prefix_must_end_at_a_slash(self):
        self.write("web/x.go", 'import "github.com/jackc/pgx/v50"\n')
        self.assertFalse(skill.imports_any("web", ["github.com/jackc/pgx/v5"]))

    def test_main_with_crlf_is_not_plain(self):
        self.write("web/main.go", template("main.go.tmpl").replace(b"\n", b"\r\n"))
        self.assertFalse(skill.same_bytes("web/main.go",
                                          os.path.join(ROOT, "files", "main.go.tmpl"), "web"))

    def test_apply_is_converted(self):
        self.assertFalse(hasattr(skill, "UNCONVERTED_MODES"))
        self.assertTrue(skill.WRITES)



# ---------------------------------------------------------------------------
# mode=apply

GO_MOD_WITH = ("module github.com/example-org/example-repo/web\n\ngo 1.27\n\nrequire (\n"
               "\tcloud.google.com/go/cloudsqlconn v1.27.1\n\tgithub.com/jackc/pgx/v5 v5.13.0\n)\n")
GET = ["go", "-C", "web", "get", "cloud.google.com/go/cloudsqlconn@v1.27.1",
       "github.com/jackc/pgx/v5@v5.13.0"]
TIDY = ["go", "-C", "web", "mod", "tidy"]


class ApplyContext(common.Context):
    """Reads answer `go version` from `version`; execute() (reached only through
    ctx.write, after the allowlist of writes accepted argv) records each write, answers
    from `answers` (keyed by the subcommand) and runs `effects` (what the real go get or
    go mod tidy does to the folder). `fail_files` are the paths whose write fails."""

    def __init__(self, args, version=common.Completed(0, "go version go1.27.0 linux/amd64\n", ""),
                 answers=None, effects=None, fail_files=(), read_only=False):
        common.Context.__init__(self, PLUGIN, ROOT, SKILL, skill, args.get("mode", "plan"),
                                args, read_only=read_only)
        self.version = version
        self.answers = answers or {}
        self.effects = effects or {}
        self.fail_files = fail_files
        self.reads = []
        self.writes = []
        self.files = []

    def read(self, argv, timeout=None):
        assert common.read_refusal(argv) is None, argv
        self.reads.append(list(argv))
        return self.version

    def execute(self, argv, timeout=None):
        self.writes.append(list(argv))
        key = "tidy" if argv[3] == "mod" else argv[3]
        if key in self.effects:
            self.effects[key]()
        return self.answers.get(key, common.Completed(0, "", ""))

    def write_file(self, path, content):
        self._may_write("write %s" % path)
        self.files.append(path)
        if path in self.fail_files:
            return False
        return common.write_file(SKILL, path, content, stream=io.StringIO())

    def backup(self, paths):
        self._may_write("backup %s" % " ".join(paths))
        return common.Backup(SKILL, paths, stream=io.StringIO())


def apply_args(base=ARGS, **over):
    a = dict(base, mode="apply")
    a.update(over)
    return a


def read(name):
    with open(name, "rb") as f:
        return f.read()


class ApplyFolder(Folder):
    def apply(self, args, **kw):
        ctx = ApplyContext(args, **kw)
        r = skill.run(dict(args), ctx)
        self.assertEqual(r.block["mode"], "apply")
        return r, ctx

    def go_get_writes(self, text=GO_MOD_WITH, go_sum="x h1:y=\n"):
        def effect():
            self.write("web/go.mod", text)
            if go_sum is not None:
                self.write("web/go.sum", go_sum)
        return effect


class TestGoldenCommands(ApplyFolder):
    """Step 6 of the SKILL.md, as it writes the commands:

        go -C <path> get <module>@<version> <module>@<version>
        go -C <path> mod tidy

    and step 0's read, `go version`."""

    def test_new_component_with_the_database(self):
        r, ctx = self.apply(apply_args(DB), effects={"get": self.go_get_writes()})
        self.assertEqual(r.status, "created")
        self.assertEqual(ctx.reads, [["go", "version"]])
        self.assertEqual(ctx.writes, [GET, TIDY])
        for argv in ctx.writes:
            self.assertTrue(all(isinstance(a, str) for a in argv))
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))

    def test_modules_in_the_order_given(self):
        modules = "github.com/jackc/pgx/v5@v5.13.0,cloud.google.com/go/cloudsqlconn@v1.27.1"
        r, ctx = self.apply(apply_args(DB, modules=modules, path="services/web",
                                       module="github.com/o/r/services/web"))
        self.assertEqual(ctx.writes[0], ["go", "-C", "services/web", "get",
                                         "github.com/jackc/pgx/v5@v5.13.0",
                                         "cloud.google.com/go/cloudsqlconn@v1.27.1"])
        self.assertEqual(ctx.writes[1], ["go", "-C", "services/web", "mod", "tidy"])
        for argv in ctx.writes:
            self.assertIsNone(common.write_refusal(SKILL, argv, root=ROOT))


class TestApplyWrites(ApplyFolder):
    def test_order_of_writes_and_bytes(self):
        r, ctx = self.apply(apply_args(DB, dockerfile="yes"),
                            effects={"get": self.go_get_writes()})
        self.assertEqual(ctx.files, ["web/db_test.go", "web/db.go", "web/main_test.go",
                                     "web/main.go", "web/go.mod", "web/Dockerfile"])
        self.assertEqual(read("web/db.go"), read(os.path.join(ROOT, "files", "db.go.tmpl")))
        self.assertEqual(read("web/main.go"), template("main-database.go.tmpl"))
        self.assertEqual(read("web/main_test.go"), template("main_test.go.tmpl"))
        self.assertEqual(r.block["outputs"]["dockerfile"], "written")
        self.assertTrue(r.block["outputs"]["written"])

    def test_new_component_without_the_database_runs_nothing(self):
        r, ctx = self.apply(apply_args())
        self.assertEqual((ctx.reads, ctx.writes), ([], []))
        self.assertEqual(ctx.files, ["web/main_test.go", "web/main.go", "web/go.mod"])
        self.assertEqual(read("web/go.mod"),
                         b"module github.com/example-org/example-repo/web\n\ngo 1.27\n")
        self.assertEqual(read("web/main.go"), template("main.go.tmpl"))
        self.assertEqual(r.lines, ["web/go.mod, web/main.go and web/main_test.go were "
                                   "written."])

    def test_dockerfile_lines(self):
        self.write("web/go.mod", "module x\n")
        r, ctx = self.apply(apply_args(dockerfile="yes", version="1.26"))
        self.assertEqual(read("web/Dockerfile").decode(), skill.DOCKERFILE.replace(
            "{{GO_VERSION}}", "1.26"))
        self.assertTrue(read("web/Dockerfile").endswith(b'ENTRYPOINT ["/app"]\n'))
        self.assertEqual(ctx.files, ["web/Dockerfile"])

    def test_a_present_dockerfile_is_never_written(self):
        self.write("web/Dockerfile", "mine\n")
        r, ctx = self.apply(apply_args(dockerfile="yes"))
        self.assertEqual((r.status, r.block["outputs"]["dockerfile"]), ("created", "present"))
        self.assertNotIn("web/Dockerfile", ctx.files)
        self.assertEqual(read("web/Dockerfile"), b"mine\n")

    def test_write_that_fails_names_the_files_written(self):
        r, ctx = self.apply(apply_args(), fail_files=("web/main.go",))
        self.assertEqual(r.status, "failed")
        self.assertEqual(ctx.files, ["web/main_test.go", "web/main.go"])
        self.assertEqual(r.lines, ["web/main_test.go was written; web/main.go could not be "
                                   "written."])
        self.assertEqual(r.block["pending"], [{"item": "web has Go files but no go.mod",
                                               "reason": "manual",
                                               "how": "add a go.mod to web, or empty the folder"}])
        self.assertFalse(r.block["outputs"]["written"])

    def test_first_write_fails(self):
        r, ctx = self.apply(apply_args(dockerfile="yes"), fail_files=("web/main_test.go",))
        self.assertEqual(r.lines, ["web/main_test.go could not be written; nothing was "
                                   "written."])
        self.assertEqual((r.block["pending"], r.block["outputs"]["dockerfile"]), ([], None))

    def test_dockerfile_fails_after_the_three_files(self):
        r, ctx = self.apply(apply_args(dockerfile="yes"), fail_files=("web/Dockerfile",))
        self.assertEqual(r.lines, ["web/go.mod, web/main.go and web/main_test.go were "
                                   "written; web/Dockerfile could not be written."])
        o = r.block["outputs"]
        self.assertEqual((r.status, o["dockerfile"], o["written"], r.block["pending"]),
                         ("failed", None, False, []))

    def test_dockerfile_fails_after_the_five_files(self):
        r, ctx = self.apply(apply_args(DB, dockerfile="yes"), fail_files=("web/Dockerfile",))
        self.assertEqual(r.lines, ["web/go.mod, web/main.go, web/main_test.go, web/db.go and "
                                   "web/db_test.go were written; web/Dockerfile could not be "
                                   "written."])
        self.assertEqual(ctx.writes, [], "step 6 is not reached")
        o = r.block["outputs"]
        self.assertEqual((o["database"], o["route"], o["modules"]), ("written", "added", None))

    def test_dockerfile_fails_with_nothing_written(self):
        self.write("web/go.mod", "module x\n")
        r, ctx = self.apply(apply_args(dockerfile="yes"), fail_files=("web/Dockerfile",))
        self.assertEqual(r.lines, ["web/Dockerfile could not be written; nothing was written."])

    def test_database_write_fails_midway_keeps_what_was_reached(self):
        r, ctx = self.apply(apply_args(DB), fail_files=("web/main.go",))
        o = r.block["outputs"]
        self.assertEqual((o["database"], o["route"], o["modules"]), ("written", None, None))
        self.assertEqual(r.lines, ["web/db_test.go, web/db.go and web/main_test.go were "
                                   "written; web/main.go could not be written."])
        self.assertEqual(r.block["pending"][0]["item"], "web has Go files but no go.mod")
        self.assertEqual(ctx.writes, [])

    def test_pending_writes_nothing(self):
        self.write("web/handler.go", "package main\n")
        r, ctx = self.apply(apply_args(DB, dockerfile="yes"))
        self.assertEqual((r.status, ctx.files, ctx.reads, ctx.writes),
                         ("pending", [], [], []))


class TestApplyExisting(ApplyFolder):
    def existing(self, go_mod="module github.com/example-org/example-repo/web\n\ngo 1.27\n"):
        self.write("web/go.mod", go_mod)
        self.write("web/main.go", template("main.go.tmpl"))
        self.write("web/main_test.go", "package main\n")

    def test_step5_order_then_dockerfile_then_modules(self):
        self.existing()
        r, ctx = self.apply(apply_args(DB, dockerfile="yes"),
                            effects={"get": self.go_get_writes()})
        self.assertEqual(ctx.files, ["web/db_test.go", "web/db.go", "web/main.go",
                                     "web/Dockerfile"])
        self.assertEqual(ctx.writes, [GET, TIDY])
        self.assertEqual(read("web/main.go"), template("main-database.go.tmpl"))
        self.assertEqual(r.lines[1], "The database check: web/db_test.go and web/db.go were "
                                     "written; the route GET /db was added to web/main.go; the "
                                     "modules were added to web/go.mod.")

    def test_everything_there_is_the_plan_with_mode_apply(self):
        self.existing(GO_MOD_WITH)
        self.write("web/main.go", template("main-database.go.tmpl"))
        self.write("web/db.go", "package main\n")
        self.write("web/db_test.go", "package main\n")
        r, ctx = self.apply(apply_args(DB))
        self.assertEqual((r.status, ctx.reads, ctx.writes, ctx.files),
                         ("unchanged", [], [], []))

    def test_go_check_comes_before_any_write(self):
        self.existing()
        r, ctx = self.apply(apply_args(DB),
                            version=common.Completed(1, "", "go: something else\n"))
        self.assertEqual(r.lines, [skill.GO_NOT_STARTED])
        self.assertEqual((ctx.files, ctx.writes), ([], []))
        o = r.block["outputs"]
        self.assertEqual((o["database"], o["route"], o["modules"]), (None, None, None))

    def test_go_check_text_says_not_found(self):
        r, ctx = self.apply(apply_args(DB), version=common.Completed(1, "", "go: not found\n"))
        self.assertEqual(r.lines, [skill.GO_NOT_INSTALLED])

    def test_tidy_fails_puts_back_go_sum(self):
        self.existing()
        self.write("web/go.sum", "kept\n")
        os.utime("web/go.sum", (1000000000, 1000000000))
        r, ctx = self.apply(apply_args(DB), effects={"tidy": self.go_get_writes()},
                            answers={"tidy": common.Completed(1, "", "boom\n")})
        self.assertEqual(r.lines, [
            "go mod tidy could not complete in web; web/go.mod and web/go.sum were put back "
            "as they were.",
            "The check (web/db.go, and the route when main.go has it) is in web, which does "
            "not build until the modules are added; running this skill again repairs it."])
        self.assertEqual(read("web/go.sum"), b"kept\n")
        self.assertEqual(int(os.stat("web/go.sum").st_mtime), 1000000000)
        self.assertEqual(read("web/go.mod"),
                         b"module github.com/example-org/example-repo/web\n\ngo 1.27\n")
        o = r.block["outputs"]
        self.assertEqual((r.status, o["database"], o["route"], o["modules"]),
                         ("failed", "written", "added", None))

    def test_go_get_fails_runs_no_tidy(self):
        self.existing()
        r, ctx = self.apply(apply_args(DB), answers={"get": common.Completed(1, "", "x")})
        self.assertEqual(ctx.writes, [GET])
        self.assertEqual(r.lines[0], "The database modules could not be added to web/go.mod; "
                                     "web/go.mod and web/go.sum are as they were.")
        self.assertFalse(os.path.exists("web/go.sum"))

    def test_go_line_patch_other_than_zero_moved(self):
        self.existing()
        r, ctx = self.apply(apply_args(DB), effects={"get": self.go_get_writes(
            GO_MOD_WITH.replace("go 1.27", "go 1.27.1"))})
        self.assertEqual(r.lines[0], "The database modules need a newer Go than web/go.mod "
                                     "declares (go 1.27); web/go.mod and web/go.sum were put "
                                     "back as they were.")
        self.assertTrue(r.lines[1].endswith("repairs it once web/go.mod declares a Go version "
                                            "the modules accept."))
        self.assertFalse(os.path.exists("web/go.sum"))

    def test_kept_toolchain_line_must_stay(self):
        self.existing("module m\n\ngo 1.27\n\ntoolchain go1.27.2\n")
        r, ctx = self.apply(apply_args(DB), effects={"get": self.go_get_writes(
            "module m\n\ngo 1.27.0\n\ntoolchain go1.27.2\n" + GO_MOD_WITH.split("\n", 3)[3])})
        self.assertEqual((r.status, r.block["outputs"]["modules"]), ("created", "added"))

    def test_copy_fails_runs_nothing(self):
        self.existing()
        os.makedirs("web/go.sum")
        r, ctx = self.apply(apply_args(DB))
        self.assertEqual(ctx.writes, [])
        self.assertEqual(r.lines, [
            "web/go.mod could not be copied before adding the modules; nothing was run in web.",
            "The check (web/db.go, and the route when main.go has it) is in web, which does "
            "not build until the modules are added; running this skill again repairs it."])

    def test_put_back_that_fails_keeps_the_copies(self):
        self.existing()

        def tidy():
            os.makedirs("web/go.sum")  # go.sum did not exist: rm -f of a folder fails

        r, ctx = self.apply(apply_args(DB), effects={"tidy": tidy},
                            answers={"tidy": common.Completed(1, "", "")})
        self.assertEqual(len(r.lines), 1)
        self.assertTrue(r.lines[0].startswith("web/go.mod and web/go.sum could not be put back "
                                              "as they were; the copies are in "), r.lines)
        backup = r.lines[0].rsplit(" ", 1)[1][:-1]
        self.assertTrue(os.path.isfile(os.path.join(backup, "go.mod")))
        shutil.rmtree(backup)

    def test_route_manual_with_db_present_and_imports(self):
        self.existing()
        self.write("web/main.go", "package main\n")
        self.write("web/db.go", 'import "github.com/jackc/pgx/v5"\n')
        self.write("web/db_test.go", "package main\n")
        r, ctx = self.apply(apply_args(DB), effects={"get": self.go_get_writes()})
        o = r.block["outputs"]
        self.assertEqual((r.status, o["database"], o["route"], o["modules"]),
                         ("created", "present", "manual", "added"))
        self.assertEqual(ctx.files, [])
        self.assertEqual(r.block["pending"][0]["item"], "route")


class TestApplyNeedsTheMode(ApplyFolder):
    def test_plan_context_refuses_every_write(self):
        ctx = ApplyContext(dict(DB))
        for call in (lambda: ctx.write(GET), lambda: ctx.write_file("web/go.mod", "x"),
                     lambda: ctx.backup(["web/go.mod"])):
            self.assertRaises(common.WriteRefused, call)

    def test_read_only_refuses_writes_in_apply(self):
        ctx = ApplyContext(apply_args(DB), read_only=True)
        self.assertFalse(ctx.writable)
        self.assertRaises(common.WriteRefused, ctx.write, GET)
        r = common.read_only_refusal(ctx)
        self.assertEqual((r.status, r.lines), ("failed", [common.READ_ONLY_APPLY_SENTENCE]))

    def test_plan_with_database_runs_no_go(self):
        ctx = ApplyContext(dict(DB, mode="plan"))
        r = skill.run(dict(DB, mode="plan"), ctx)
        self.assertEqual((r.status, ctx.reads, ctx.writes, ctx.files),
                         ("would-create", [], [], []))
        self.assertFalse(os.path.exists("web"))


if __name__ == "__main__":
    unittest.main()
