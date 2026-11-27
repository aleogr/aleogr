"""Unit tests of go_setup's plan, the cases no scenario covers. Each test runs in a
temporary folder of its own. The scenarios go-setup-*plan cover the rest, in the direct
mode; mode=apply is not converted in step 1."""

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

    def test_apply_is_not_converted(self):
        self.assertEqual(skill.UNCONVERTED_MODES, ("apply",))
        self.assertFalse(getattr(skill, "WRITES", False))


if __name__ == "__main__":
    unittest.main()
