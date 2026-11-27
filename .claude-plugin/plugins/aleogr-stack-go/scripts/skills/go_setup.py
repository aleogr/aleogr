"""go_setup: the starting point of a Go component. Step 1 converts mode=plan only.

The specification is skills/go_setup/SKILL.md. The reads (steps 1, 2 and the reads of
step 5) are done by survey(), which mode=apply will reuse: plan only turns what survey()
found into the statuses of the result block, and never writes or runs anything.

The SKILL.md has the model use the Read tool, one `ls`, two `cmp` and the Grep tool. They
are not provider commands (the read-only runner refuses them), so this module does each
one in Python, with the same meaning: the files are read here, the folder is listed with
the meaning of `ls -1Ap -- <path>/`, and main.go is compared byte for byte with the
filled template as `cmp -s` does.
"""

import errno
import os
import re

FAMILY = "stack"
PROVIDER = "go"
ACTION = "setup"
DEFAULT_MODE = "plan"
UNCONVERTED_MODES = ("apply",)

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
    return plan(args, ctx, s)
