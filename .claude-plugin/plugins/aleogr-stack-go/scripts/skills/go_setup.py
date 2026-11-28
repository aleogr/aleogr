"""go_setup: the starting point of a Go component, in mode=plan and mode=apply.

The rules are this module's, pinned by its unit tests (tests/unit/test_go_setup.py) and
its scenarios. It was built from skills/go_setup/SKILL.md as that text was before the
skill became a shell over this command (the text is in the repository's history, at the
commit before that change). The reads (steps 1, 2 and the reads of step 5) are done by
survey(), shared by both modes: plan only turns what survey() found into the statuses of
the result block, and never writes or runs anything; apply() then does the writes of
steps 3, 4 and 5, the Go check of step 0 and the modules of step 6.

The SKILL.md has the model use the Read tool, the Write tool, one `ls`, two `cmp`, the
Grep tool and, in step 6, `mktemp -d`, `cp -p`, `rm -f` and `rm -rf`. None of them is a
provider command, so this module does each one in Python, with the same meaning: the
files are read here, the folder is listed with the meaning of `ls -1Ap -- <path>/`,
main.go is compared byte for byte with the filled template as `cmp -s` does, files are
written through ctx.write_file, and the copies of go.mod and go.sum are taken, put back
and removed through ctx.backup. The commands it runs are `go version` (a read) and
`go -C <path> get ...` and `go -C <path> mod tidy` (writes, through ctx.write).
"""

import errno
import os
import re

FAMILY = "stack"
PROVIDER = "go"
ACTION = "setup"
DEFAULT_MODE = "plan"
WRITES = True

COST = {"fixed": False, "notes": "writes local files only"}

ARGUMENTS = ("component", "path", "version", "module", "dockerfile", "database", "modules",
             "minVersion", "mode")
DB_MODULES = ("cloud.google.com/go/cloudsqlconn", "github.com/jackc/pgx/v5")
EARLIEST_GO = (1, 22)

_COMPONENT = re.compile(r"^[a-z][a-z0-9-]{0,19}$")
_PATH_PART = re.compile(r"^[a-z0-9_]([a-z0-9._-]*[a-z0-9_-])?$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+$")
_OWNER = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_MODULE_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._~/-]*$")
_MODULE_VERSION = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")


class StepFailed(Exception):
    """A read that ends the run `failed`, with its one sentence and the survey so far."""

    def __init__(self, sentence, survey):
        Exception.__init__(self, sentence)
        self.survey = survey


# ---------------------------------------------------------------------------
# Arguments


def _version_tuple(v):
    return tuple(int(x) for x in v.split("."))


def _path_ok(path):
    return all(_PATH_PART.match(part) for part in path.split("/"))


def _module_ok(module, path):
    prefix = "github.com/"
    if not module.startswith(prefix):
        return False
    parts = module[len(prefix):].split("/", 2)
    if len(parts) != 3:
        return False
    owner, repository, rest = parts
    return (bool(_OWNER.match(owner)) and bool(_REPOSITORY.match(repository))
            and repository not in (".", "..") and rest == path)


def _modules_problems(value):
    elements = value.split(",")
    names = []
    for e in elements:
        pieces = e.split("@")
        if len(pieces) != 2:
            return ["modules must be <module>@<version> elements separated by \",\", with no "
                    "space, such as cloud.google.com/go/cloudsqlconn@v1.27.1."]
        name, version = pieces
        if (not _MODULE_PATH.match(name) or "//" in name or name.endswith("/")
                or not _MODULE_VERSION.match(version)):
            return ["modules must be <module>@<version> elements separated by \",\", with no "
                    "space, such as cloud.google.com/go/cloudsqlconn@v1.27.1."]
        names.append(name)
    if sorted(names) != sorted(DB_MODULES):
        return ["modules must be exactly cloud.google.com/go/cloudsqlconn and "
                "github.com/jackc/pgx/v5, each once."]
    return []


def validate(args):
    """Every broken rule's sentence, in the order of the table of arguments."""
    problems = []
    for key in args:
        if key not in ARGUMENTS:
            problems.append("%s is not an argument of go_setup." % key)
    database = args.get("database")
    required = ["component", "version", "module"]
    if database == "yes":
        required += ["modules", "minVersion"]
    missing = [k for k in required if not args.get(k)]
    if missing:
        problems.append("Missing required argument%s: %s; nothing was read or written."
                        % ("" if len(missing) == 1 else "s", ", ".join(missing)))
    component = args.get("component")
    if component and not _COMPONENT.match(component):
        problems.append("component must have 1 to 20 characters of a-z, 0-9 and -, "
                        "starting with a letter.")
    path = _path(args)
    if "path" in args and not (path and _path_ok(path)):
        problems.append("path must be a folder relative to the current folder: parts of a-z, "
                        "0-9, -, _ and . separated by /, none of them starting with - or . "
                        "and none ending with .")
    version = args.get("version")
    if version:
        if not _VERSION.match(version):
            problems.append("version must be <major>.<minor>, such as 1.27.")
        elif _version_tuple(version) < EARLIEST_GO:
            problems.append("Go %s is earlier than 1.22, which the template's GET /{$} "
                            "patterns need." % version)
    module = args.get("module")
    if module and path and not _module_ok(module, path):
        problems.append("module must be github.com/<owner>/<repository>/%s, ending with the "
                        "path %s." % (path, path))
    if "dockerfile" in args and args["dockerfile"] not in ("yes", "no"):
        problems.append("dockerfile must be yes or no.")
    if "database" in args and database not in ("yes", "no"):
        problems.append("database must be yes or no.")
    if database != "yes":
        for key in ("modules", "minVersion"):
            if key in args:
                problems.append("%s is only allowed with database=yes." % key)
    else:
        if args.get("modules"):
            problems.extend(_modules_problems(args["modules"]))
        min_version = args.get("minVersion")
        if min_version:
            if not _VERSION.match(min_version):
                problems.append("minVersion must be <major>.<minor>, such as 1.26.")
            elif (version and _VERSION.match(version)
                  and _version_tuple(version) < _version_tuple(min_version)):
                problems.append("Go %s is earlier than %s, the earliest version of a component "
                                "that uses the database; nothing was written."
                                % (version, min_version))
    if "mode" in args and args["mode"] not in ("plan", "apply"):
        problems.append("mode must be plan or apply.")
    return problems


def _path(args):
    if "path" in args:
        return args["path"]
    return args.get("component")


# ---------------------------------------------------------------------------
# Reads (shared by plan and, later, apply)


def read_file(name):
    """The Read tool: the file's text, or None when it does not exist. StepFailed's
    sentence is left to the caller: this raises OSError for any other answer."""
    try:
        with open(name, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError as e:
        if e.errno == errno.ENOENT and not os.path.isdir(name):
            return None
        raise


def list_folder(path):
    """`ls -1Ap -- <path>/`: the folder's own entries, a folder's name ending with `/`,
    or None when the folder does not exist. Raises OSError for any other failure."""
    try:
        names = os.listdir(path + "/")
    except OSError as e:
        if e.errno == errno.ENOENT:
            return None
        raise
    out = []
    for n in sorted(names):
        try:
            is_dir = os.path.isdir(os.path.join(path, n)) and not os.path.islink(
                os.path.join(path, n))
        except OSError:
            is_dir = False
        out.append(n + "/" if is_dir else n)
    return out


def same_bytes(name, template, component):
    """`cmp -s -- <name> <(sed -e 's/{{COMPONENT}}/<component>/g' -- <template>)`: True
    only for exit 0. A file that cannot be read is exit 2, never equal."""
    try:
        with open(name, "rb") as f:
            have = f.read()
        with open(template, "rb") as f:
            want = f.read().replace(b"{{COMPONENT}}", component.encode("utf-8"))
    except OSError:
        return False
    return have == want


def required_modules(go_mod, modules):
    """The modules of `modules` that go.mod requires (any version)."""
    found = set()
    inside = False
    for raw in (go_mod or "").splitlines():
        words = raw.split()
        if not words:
            continue
        if inside:
            if words[0] == ")":
                inside = False
            elif words[0] in modules:
                found.add(words[0])
            continue
        if words == ["require", "("]:
            inside = True
        elif words[0] == "require" and len(words) >= 3 and words[1] in modules:
            found.add(words[1])
    return found


def imports_any(path, modules):
    """The one Grep of step 5: a quoted import path, in a *.go file of <path> or a
    subfolder, that is a module of `modules` or starts with one followed by `/`."""
    pattern = re.compile(r'"(%s)(/[^"]*)?"' % "|".join(re.escape(m) for m in modules))
    for top, dirs, files in os.walk(path):
        # Hidden folders are not searched, as the search of the prose skill does not.
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if not f.endswith(".go"):
                continue
            try:
                with open(os.path.join(top, f), "rb") as fh:
                    text = fh.read().decode("utf-8", "replace")
            except OSError:
                continue
            if pattern.search(text):
                return True
    return False


class Survey(object):
    """What steps 1, 2 and the reads of step 5 found.

    kind: "existing" (the module exists), "new" (no module and no Go file) or "pending"
    (Go files and no go.mod). dockerfile: "present", "missing" or None (not looked at).
    For database=yes on an existing module: db_go and db_test_go ("present" or
    "missing"), route ("plain", "present" or "manual") and modules ("present",
    "to-add" or "not-needed").
    """

    def __init__(self):
        self.kind = None
        self.go_mod = None
        self.listing = None
        self.dockerfile = None
        self.db_go = None
        self.db_test_go = None
        self.route = None
        self.modules = None


def survey(args, ctx):
    path = _path(args)
    docker = args.get("dockerfile") == "yes"
    database = args.get("database") == "yes"
    s = Survey()

    # Step 1: <path>/go.mod.
    try:
        s.go_mod = read_file(os.path.join(path, "go.mod"))
    except OSError:
        raise StepFailed("%s/go.mod could not be read; nothing was written." % path, s)
    has_module = s.go_mod is not None
    if has_module and not docker and not database:
        s.kind = "existing"
        return s

    # Step 2: the listing, unless step 1 sends the run straight to step 5.
    if not has_module or docker:
        try:
            s.listing = list_folder(path)
        except OSError as e:
            if e.errno == errno.ENOTDIR:
                raise StepFailed("%s is not a folder; nothing was written." % path, s)
            raise StepFailed("%s could not be listed; nothing was written." % path, s)
        if s.listing is None:
            if has_module:
                raise StepFailed("%s could not be listed; nothing was written." % path, s)
            s.kind = "new"
            if docker:
                s.dockerfile = "missing"
            return s
        if docker:
            if "Dockerfile/" in s.listing:
                raise StepFailed("%s/Dockerfile is a folder; nothing was written." % path, s)
            s.dockerfile = "present" if "Dockerfile" in s.listing else "missing"
        if has_module or "go.mod" in s.listing:
            has_module = True
        elif any(n.endswith(".go") for n in s.listing):
            s.kind = "pending"
            return s
        else:
            s.kind = "new"
            return s

    s.kind = "existing"
    if database:
        _survey_check(args, ctx, path, s)
    return s


def _survey_check(args, ctx, path, s):
    """The reads of step 5: db.go, db_test.go, main.go against the templates, the
    modules."""
    component = args["component"]
    for attr, name in (("db_go", "db.go"), ("db_test_go", "db_test.go")):
        try:
            text = read_file(os.path.join(path, name))
        except OSError:
            raise StepFailed("%s/%s could not be read; nothing was written." % (path, name), s)
        setattr(s, attr, "missing" if text is None else "present")
    main = os.path.join(path, "main.go")
    files = ctx.plugin_path("files")
    if same_bytes(main, os.path.join(files, "main.go.tmpl"), component):
        s.route = "plain"
    elif same_bytes(main, os.path.join(files, "main-database.go.tmpl"), component):
        s.route = "present"
    else:
        s.route = "manual"
    names = [e.split("@")[0] for e in args["modules"].split(",")]
    if required_modules(s.go_mod, names) == set(names):
        s.modules = "present"
    elif s.db_go == "missing" or imports_any(path, names):
        s.modules = "to-add"
    else:
        s.modules = "not-needed"


# ---------------------------------------------------------------------------
# The result


def _files(path, docker, database):
    files = ["%s/go.mod" % path, "%s/main.go" % path, "%s/main_test.go" % path]
    if database:
        files += ["%s/go.sum" % path, "%s/db.go" % path, "%s/db_test.go" % path]
    if docker:
        files.append("%s/Dockerfile" % path)
    return files


def _outputs(args, path, docker, database, dockerfile=None, check=(None, None, None)):
    db, route, modules = check if database else ("not-asked",) * 3
    return {
        "component": args["component"],
        "path": path,
        "module": args["module"],
        "files": _files(path, docker, database),
        "written": False,
        "dockerfile": dockerfile if docker else "not-asked",
        "database": db,
        "route": route,
        "modules": modules,
        "ci": {"workflow": "ci-go.yml",
               "inputs": {"working-directory": path, "go-version": args["version"]}},
    }


def _argument_outputs(args):
    component = args.get("component")
    component = component if component and _COMPONENT.match(component) else None
    if "path" in args:
        path = args["path"] if args["path"] and _path_ok(args["path"]) else None
    else:
        path = component
    nulls = (None,) * 3 if args.get("database") == "yes" else ("not-asked",) * 3
    return {
        "component": component,
        "path": path,
        "module": None,
        "files": [],
        "written": False,
        "dockerfile": None,
        "database": nulls[0],
        "route": nulls[1],
        "modules": nulls[2],
        "ci": None,
    }


def _route_item(path):
    return {"item": "route", "reason": "manual",
            "how": "add the line mux.HandleFunc(\"GET /db\", dbCheck) to the router in "
                   "%s/main.go; until then the tests of %s/db_test.go, which expect the "
                   "route, fail" % (path, path)}


def _pending_item(path):
    return {"item": "%s has Go files but no go.mod" % path, "reason": "manual",
            "how": "add a go.mod to %s, or empty the folder" % path}


def _dockerfile_clause(path, dockerfile, would):
    if dockerfile == "present":
        return "%s/Dockerfile is already there and is left as it is" % path
    if would:
        return "%s/Dockerfile would be written" % path
    return "%s/Dockerfile is not written" % path


def plan(args, ctx, s):
    path = _path(args)
    docker = args.get("dockerfile") == "yes"
    database = args.get("database") == "yes"
    dockerfile = None
    if docker:
        dockerfile = "present" if s.dockerfile == "present" else "would-write"
    pending = []
    lines = []

    if s.kind == "pending":
        check = ("would-write", "would-add", "would-add")
        clauses = ["%s holds Go files and no go.mod, so nothing was written" % path]
        if docker:
            clauses.append(_dockerfile_clause(path, dockerfile, False))
        lines.append("; ".join(clauses) + ".")
        pending.append(_pending_item(path))
        return ctx.result("pending", _outputs(args, path, docker, database, dockerfile, check),
                          pending=pending, cost=COST, lines=lines)

    if s.kind == "new":
        check = ("would-write", "would-add", "would-add")
        clauses = ["%s/go.mod, %s/main.go and %s/main_test.go would be written"
                   % (path, path, path)]
        if docker:
            clauses.append(_dockerfile_clause(path, dockerfile, True))
        lines.append("; ".join(clauses) + "; nothing was written.")
        if database:
            lines.append("The database check would be written with them: %s/db.go and "
                         "%s/db_test.go, the route GET /db in %s/main.go, and the modules "
                         "added to %s/go.mod." % (path, path, path, path))
        return ctx.result("would-create",
                          _outputs(args, path, docker, database, dockerfile, check),
                          cost=COST, lines=lines)

    # The module exists.
    changes = docker and dockerfile == "would-write"
    clauses = ["%s/go.mod exists, so its files are not written" % path]
    if docker:
        clauses.append(_dockerfile_clause(path, dockerfile, True))
    check = (None, None, None)
    if database:
        missing = [n for n, v in (("db.go", s.db_go), ("db_test.go", s.db_test_go))
                   if v == "missing"]
        db = "would-write" if missing else "present"
        route = {"plain": "would-add", "present": "present", "manual": "manual"}[s.route]
        modules = {"to-add": "would-add", "present": "present",
                   "not-needed": "not-needed"}[s.modules]
        check = (db, route, modules)
        changes = changes or db == "would-write" or route == "would-add" or \
            modules == "would-add"
    lines.append("; ".join(clauses) + "; nothing was written.")
    if database:
        parts = []
        if check[0] == "would-write":
            parts.append(" and ".join("%s/%s" % (path, n) for n in missing) + " would be written")
        else:
            parts.append("%s/db.go and %s/db_test.go are already there" % (path, path))
        if check[1] == "would-add":
            parts.append("the route GET /db would be added to %s/main.go" % path)
        elif check[1] == "present":
            parts.append("%s/main.go already has the route GET /db" % path)
        else:
            parts.append("%s/main.go is left as it is, and the line "
                         "mux.HandleFunc(\"GET /db\", dbCheck) is to be added to its router"
                         % path)
            pending.append(_route_item(path))
        if check[2] == "would-add":
            parts.append("the modules would be added to %s/go.mod" % path)
        elif check[2] == "present":
            parts.append("the modules are already required")
        else:
            parts.append("the modules are not needed, since the component's code does not "
                         "import them")
        lines.append("The database check: " + "; ".join(parts) + ".")
    status = "would-create" if changes else "unchanged"
    return ctx.result(status, _outputs(args, path, docker, database, dockerfile, check),
                      pending=pending, cost=COST, lines=lines)


# ---------------------------------------------------------------------------
# mode=apply: steps 0, 3, 4, 5 (its writes) and 6

# Step 4: the Dockerfile, the lines of the SKILL.md without the indentation of its list.
DOCKERFILE = (
    "# Generated by aleogr. Written once and never overwritten: it is yours to change.\n"
    "FROM golang:{{GO_VERSION}} AS build\n"
    "WORKDIR /src\n"
    "COPY go.mod go.sum* ./\n"
    "RUN go mod download\n"
    "COPY . .\n"
    "RUN CGO_ENABLED=0 go build -trimpath -o /out/app .\n"
    "\n"
    "FROM gcr.io/distroless/static-debian13:nonroot\n"
    "COPY --from=build /out/app /app\n"
    "USER nonroot:nonroot\n"
    "ENTRYPOINT [\"/app\"]\n"
)

GO_NOT_INSTALLED = "Go is not installed where this skill runs; nothing was written."
GO_NOT_STARTED = "Go could not be started where this skill runs; nothing was written."


class _Stop(Exception):
    """A step of apply that ends the run `failed`, with its sentences."""

    def __init__(self, lines):
        Exception.__init__(self, lines[0])
        self.lines = lines


def _join(names):
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def _were(names):
    return "%s %s written" % (_join(names), "was" if len(names) == 1 else "were")


def _write_failed(failed, written):
    """The one sentence of a write that fails, naming the files written before it."""
    if not written:
        return "%s could not be written; nothing was written." % failed
    return "%s; %s could not be written." % (_were(written), failed)


def fill(data, args, names=("{{MODULE}}", "{{COMPONENT}}", "{{GO_VERSION}}")):
    """A template's bytes with its placeholders replaced, and nothing else changed."""
    values = {"{{MODULE}}": args["module"], "{{COMPONENT}}": args["component"],
              "{{GO_VERSION}}": args["version"]}
    for name in names:
        data = data.replace(name.encode("utf-8"), values[name].encode("utf-8"))
    return data


def go_lines(text):
    """The `go` line and the `toolchain` line of a go.mod (None when it has none)."""
    go = toolchain = None
    for raw in (text or "").splitlines():
        words = raw.split()
        if not words:
            continue
        if words[0] == "go" and go is None:
            go = " ".join(words)
        elif words[0] == "toolchain" and toolchain is None:
            toolchain = " ".join(words)
    return go, toolchain


def go_check(ctx):
    """Step 0: `go version`. None when Go can run, otherwise the failure sentence."""
    c = ctx.read(["go", "version"])
    if c.code == 0 and c.out.startswith("go version go"):
        return None
    if c.code == 127 or "not found" in c.text:
        return GO_NOT_INSTALLED
    return GO_NOT_STARTED


class Apply(object):
    """What the apply has done so far: the result's outputs follow from it."""

    def __init__(self, args, ctx, s):
        self.args = args
        self.ctx = ctx
        self.s = s
        self.path = _path(args)
        self.docker = args.get("dockerfile") == "yes"
        self.database = args.get("database") == "yes"
        self.new = s.kind == "new"
        self.starting = []    # the files of step 3 this run wrote, in order
        self.check = []       # the files of step 5 this run wrote, in order
        self.dockerfile = "present" if s.dockerfile == "present" else None
        self.db = self.route = self.modules = None
        self.modules_removed = False
        if self.database and not self.new:
            if s.db_go == "present" and s.db_test_go == "present":
                self.db = "present"
            self.route = {"present": "present", "manual": "manual"}.get(s.route)
            self.modules = {"present": "present", "not-needed": "not-needed"}.get(s.modules)

    def p(self, name):
        return "%s/%s" % (self.path, name)

    def template(self, name):
        try:
            with open(self.ctx.plugin_path("files", name), "rb") as f:
                return f.read()
        except OSError:
            return None

    def write(self, name, data):
        return self.ctx.write_file(self.p(name), data)

    def to_add(self):
        return self.database and (self.new or self.s.modules == "to-add")

    # The result

    def outputs(self, failed):
        check = (self.db, self.route, self.modules)
        o = _outputs(self.args, self.path, self.docker, self.database,
                     self.dockerfile, check)
        o["written"] = (not failed) and self.new and "go.mod" in self.starting
        return o

    def pending(self):
        items = []
        if self.new and self.starting and "go.mod" not in self.starting:
            items.append(_pending_item(self.path))
        if self.route == "manual":
            items.append(_route_item(self.path))
        return items

    def failed(self, lines):
        return self.ctx.result("failed", self.outputs(True), pending=self.pending(),
                               cost=COST, lines=lines)

    def done(self):
        wrote = bool(self.starting or self.check or self.dockerfile == "written"
                     or self.modules == "added"
                     or getattr(self, "modules_removed", False))
        status = "created" if wrote else "unchanged"
        return self.ctx.result(status, self.outputs(False), pending=self.pending(),
                               cost=COST, lines=self.answer())

    def answer(self):
        path = self.path
        if self.new:
            first = "%s/go.mod, %s/main.go and %s/main_test.go were written" % (
                path, path, path)
        else:
            first = "%s/go.mod exists, so its files are not written" % path
        if self.docker:
            if self.dockerfile == "written":
                first += "; %s/Dockerfile was written" % path
            else:
                first += "; " + _dockerfile_clause(path, self.dockerfile, False)
        lines = [first + "."]
        if not self.database:
            return lines
        if self.modules == "added":
            modules = "the modules were added to %s/go.mod" % path
        elif self.modules_removed:
            modules = ("the modules were not added to %s/go.mod, because the component's "
                       "code does not import them" % path)
        elif self.modules == "present":
            modules = "the modules are already required"
        else:
            modules = ("the modules are not needed, since the component's code does not "
                       "import them")
        if self.new:
            lines.append("The database check was written with them: %s/db.go and "
                         "%s/db_test.go, and the route GET /db in %s/main.go; %s."
                         % (path, path, path, modules))
            return lines
        parts = []
        written = [self.p(n) for n in self.check if n != "main.go"]
        if written:
            parts.append(_were(written))
        else:
            parts.append("%s/db.go and %s/db_test.go are already there" % (path, path))
        if self.route == "added":
            parts.append("the route GET /db was added to %s/main.go" % path)
        elif self.route == "present":
            parts.append("%s/main.go already has the route GET /db" % path)
        else:
            parts.append("%s/main.go is left as it is, and the line "
                         "mux.HandleFunc(\"GET /db\", dbCheck) is to be added to its router"
                         % path)
        parts.append(modules)
        lines.append("The database check: " + "; ".join(parts) + ".")
        return lines

    # The steps

    def step0(self):
        if self.to_add():
            sentence = go_check(self.ctx)
            if sentence:
                raise _Stop([sentence])

    def step3(self):
        """The starting files of a new component (with the check, with database=yes)."""
        files = []
        if self.database:
            files += [("db_test.go", "db_test.go.tmpl"), ("db.go", "db.go.tmpl")]
        files += [("main_test.go", "main_test.go.tmpl"),
                  ("main.go", "main-database.go.tmpl" if self.database else "main.go.tmpl"),
                  ("go.mod", "go.mod.tmpl")]
        contents = []
        for name, tmpl in files:
            data = self.template(tmpl)
            if data is None:
                raise _Stop(["The plugin's template %s could not be read; nothing was "
                             "written." % tmpl])
            contents.append((name, fill(data, self.args)))
        for name, data in contents:
            if not self.write(name, data):
                raise _Stop([_write_failed(self.p(name),
                                           [self.p(n) for n in self.starting])])
            self.starting.append(name)
            if name in ("db_test.go", "db.go"):
                self.db = "written"
            elif name == "main.go" and self.database:
                self.route = "added"

    def step5(self):
        """The writes of step 5: the check's files in a module that already existed."""
        s = self.s
        for name, state in (("db_test.go", s.db_test_go), ("db.go", s.db_go)):
            if state != "missing":
                continue
            self.write_check(name, name + ".tmpl", ())
            self.db = "written"
        if self.db is None:
            self.db = "present"
        if s.route == "plain":
            self.write_check("main.go", "main-database.go.tmpl", ("{{COMPONENT}}",))
            self.route = "added"

    def write_check(self, name, tmpl, names):
        written = [self.p(n) for n in self.check]
        data = self.template(tmpl)
        if data is None:
            if written:
                raise _Stop(["%s; the plugin's template %s could not be read."
                             % (_were(written), tmpl)])
            raise _Stop(["The plugin's template %s could not be read; nothing was written."
                         % tmpl])
        if not self.write(name, fill(data, self.args, names)):
            raise _Stop([_write_failed(self.p(name), written)])
        self.check.append(name)

    def step4(self):
        if not self.docker or self.dockerfile == "present":
            return
        data = DOCKERFILE.replace("{{GO_VERSION}}", self.args["version"])
        if self.write("Dockerfile", data):
            self.dockerfile = "written"
            return
        self.dockerfile = None
        path = self.path
        if self.new and self.database:
            sentence = ("%s/go.mod, %s/main.go, %s/main_test.go, %s/db.go and %s/db_test.go "
                        "were written; %s/Dockerfile could not be written."
                        % ((path,) * 6))
        elif self.new:
            sentence = ("%s/go.mod, %s/main.go and %s/main_test.go were written; "
                        "%s/Dockerfile could not be written." % ((path,) * 4))
        else:
            sentence = _write_failed(self.p("Dockerfile"), [self.p(n) for n in self.check])
        raise _Stop([sentence])

    def step6(self):
        """The modules: copies, go get, go mod tidy, the go and toolchain lines."""
        path = self.path
        repairs = ("The check (%s/db.go, and the route when main.go has it) is in %s, which "
                   "does not build until the modules are added; running this skill again "
                   "repairs it." % (path, path))
        if self.new:
            kept = ("go %s" % self.args["version"], None)
        else:
            kept = go_lines(self.s.go_mod)
        backup = self.ctx.backup([self.p("go.mod"), self.p("go.sum")])
        if not backup.ok or not backup.existed(self.p("go.mod")):
            backup.discard()
            raise _Stop(["%s/go.mod could not be copied before adding the modules; nothing "
                         "was run in %s." % (path, path), repairs])
        elements = self.args["modules"].split(",")
        names = [e.split("@")[0] for e in elements]
        c = self.ctx.write(["go", "-C", path, "get"] + elements)
        if not c.ok:
            self.put_back(backup, [
                "The database modules could not be added to %s/go.mod; %s/go.mod and "
                "%s/go.sum are as they were." % (path, path, path), repairs])
        c = self.ctx.write(["go", "-C", path, "mod", "tidy"])
        if not c.ok:
            self.put_back(backup, [
                "go mod tidy could not complete in %s; %s/go.mod and %s/go.sum were put "
                "back as they were." % (path, path, path), repairs])
        try:
            text = read_file(self.p("go.mod"))
        except OSError:
            text = None
        go, toolchain = go_lines(text)
        go_held = go == kept[0] or (kept[0] is not None and go == kept[0] + ".0")
        if not go_held or toolchain != kept[1]:
            self.put_back(backup, [
                "The database modules need a newer Go than %s/go.mod declares (%s); "
                "%s/go.mod and %s/go.sum were put back as they were."
                % (path, kept[0] or "no go line", path, path),
                "The check (%s/db.go, and the route when main.go has it) is in %s, which "
                "does not build until the modules are added; running this skill again "
                "repairs it once %s/go.mod declares a Go version the modules accept."
                % (path, path, path)])
        backup.discard()
        if required_modules(text, names) == set(names):
            self.modules = "added"
        else:
            self.modules = "not-needed"
            self.modules_removed = True

    def put_back(self, backup, lines):
        self.modules = None
        if not backup.restore():
            raise _Stop(["%s/go.mod and %s/go.sum could not be put back as they were; the "
                         "copies are in %s." % (self.path, self.path, backup.dir)])
        backup.discard()
        raise _Stop(lines)


def has_work(args, s):
    """Whether apply writes or runs anything: otherwise its result is the plan's."""
    if s.kind == "new":
        return True
    if s.kind != "existing":
        return False
    if args.get("dockerfile") == "yes" and s.dockerfile == "missing":
        return True
    return args.get("database") == "yes" and (
        "missing" in (s.db_go, s.db_test_go) or s.route == "plain" or s.modules == "to-add")


def apply(args, ctx, s):
    """mode=apply after the reads. A run with nothing to write or run (pending, or a
    module where everything is there) gives what plan gives, with mode apply."""
    if not has_work(args, s):
        return plan(args, ctx, s)
    a = Apply(args, ctx, s)
    try:
        a.step0()
        if a.new:
            a.step3()
        elif a.database:
            a.step5()
        a.step4()
        if a.to_add():
            a.step6()
    except _Stop as e:
        return a.failed(e.lines)
    return a.done()


def run(args, ctx):
    problems = validate(args)
    if problems:
        mode = args.get("mode") if args.get("mode") in ("plan", "apply") else "plan"
        return ctx.result("failed", _argument_outputs(args), cost=COST, lines=problems,
                          mode=mode)
    path = _path(args)
    docker = args.get("dockerfile") == "yes"
    database = args.get("database") == "yes"
    try:
        s = survey(args, ctx)
    except StepFailed as e:
        found = "present" if e.survey.dockerfile == "present" else None
        return ctx.result("failed", _outputs(args, path, docker, database, found),
                          cost=COST, lines=[str(e)])
    if args.get("mode") == "apply":
        return apply(args, ctx, s)
    return plan(args, ctx, s)
