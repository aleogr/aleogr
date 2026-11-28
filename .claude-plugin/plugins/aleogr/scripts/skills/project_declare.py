"""project-declare: write or edit the project's declaration, `.aleogr/project.json` in the
current folder, from `key=value` arguments and the owner's defaults (`defaults.json` of
this plugin). It runs no provider command and calls no other skill: the only thing it
changes is that one file, written through ctx.write_file.

The rules are this module's, pinned by its unit tests
(tests/unit/test_project_declare.py) and its scenarios. It was built from
skills/project-declare/SKILL.md as that text was before the skill became a shell over
this command (the text is in the repository's history, at the commit before that
change): the same steps, in the same order, the same checks, the prescribed sentences
word for word, the canonical form byte for byte and the same result block.

The declaration's rules are not written twice: they are project-plan's
(check_declaration, the patterns, _path_problem, version_tuple, Defaults), loaded from
this plugin's project_plan.py the way project_plan.py loads tools_check.py.

- step 1 and 2: read_defaults(), read_file();
- step 3: check_args() gives every problem, one sentence each;
- step 4: build() gives the result;
- step 5: changes() and canonical_text(); run() writes the file and answers.
"""

import importlib.util
import json
import os
import sys

FAMILY = "orchestrator"
PROVIDER = "aleogr"
ACTION = "project-declare"
# No mode argument: every run writes, or fails before writing. `--read-only` refuses it.
DEFAULT_MODE = "apply"
RESULT_MODE = "apply"
WRITES = True  # the file .aleogr/project.json, through ctx.write_file only
# The block as the SKILL.md's example lays it out: `outputs.declaration` and its `repo`
# one key per line (render_block).
BLOCK_EXPAND = {"outputs": {"declaration": ("repo",)}}
COST = {"fixed": False, "notes": "writes a local file only"}


def _project_plan():
    """This plugin's project_plan module, loaded by its file path (a unit test loads this
    module by path too, where `skills` may be another plugin's package)."""
    name = "aleogr_plugin_project_plan"
    if name not in sys.modules:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project_plan.py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


PP = _project_plan()
common = PP.aleogr_common

DECLARATION = PP.DECLARATION
SCHEMA = PP.SCHEMA
SETTINGS_KEYS = PP.SETTINGS_KEYS

# The arguments of the table, in its order.
ARGUMENTS = ("name", "owner", "repoName", "visibility", "description", "topics") + \
    SETTINGS_KEYS + ("notes", "component", "stack", "path", "version", "database",
                     "environment", "cloudRoot")
COMPONENT_ARGS = ("stack", "path", "version", "database")

# ---------------------------------------------------------------------------
# Sentences: the prescribed ones word for word, with their placeholders; the others
# fixed here.

DESCRIBE_COMPONENT = "%s given without `component`: they describe a component: give `component=<name>`."
DATABASE_VALUE = "`database=%s` must be `yes` or `no`."
VERSION_TOO_OLD = "`version=%s` is too old: a Go component needs Go 1.22 or later."
COMPONENT_RESERVED = ("`component=%s` is a reserved name: `changes` and `ci` are jobs of the "
                      "project's CI file, and YAML does not read `true`, `false`, `null`, "
                      "`yes`, `no`, `on` and `off` as names.")
PATH_CANNOT = "`path=%s` cannot hold a component: %s"
PATH_SHARED = ("`path=%s` is the folder of the component `%s`: no two components share a "
               "folder.")
PATH_NESTED = ("`path=%s` and the folder of the component `%s` are one inside the other: a "
               "component's folder is never inside another component's folder.")
ANOTHER_COMPONENT = ("`%s=%s` is not the %s of the component `%s` (`%s`): that is another "
                     "component.")
ENVIRONMENT_VALUE = ("`environment=%s` is not an environment this tooling builds yet: `dev` "
                     "is the only one.")
ROOT_VALUE = ("`cloudRoot=%s` is not a root: `tst` is the only one, for a project that tests "
              "the tooling.")
SHORT_NAME = ("`environment=dev` needs a project name of at least three characters: the CI "
              "identity's account `%s-ci` needs six.")
SERVICE_NAME = ("The service name `%s` breaks the rule on service names (6 to 30 characters, "
                "not ending with `-`): with an environment, each component runs as that "
                "service; choose another component name.")
DATABASE_NEEDS_ENVIRONMENT = ("`database=yes` needs an environment: a database lives in an "
                              "environment; give `environment=dev` in the same call.")
NO_MIN_VERSION = ("The defaults have no `stacks.%s.database.minVersion`, which a component "
                  "that uses the database needs.")
DATABASE_VERSION = ("The component `%s` uses the database and declares Go `%s`: a component "
                    "that uses the database needs Go %s or later; give `version=%s` or later "
                    "in the same call.")
ROOT_NEEDS_CLOUD = ("`cloudRoot=tst` needs the declaration's `cloud`: give `environment=dev` "
                    "in the same call.")
ANOTHER_PROJECT = "`%s=%s` is not the declaration's %s (`%s`): that is another project."

# Fixed here (the SKILL.md leaves the wording free).
UNKNOWN_ARGUMENT = "`%s` is not an argument of project-declare."
MISSING_ONE = "This required argument is missing: %s."
MISSING_MANY = "These required arguments are missing: %s."
NAME_INVALID = ("`name=%s` is not a valid project name: it must have 1 to 14 characters of "
                "a-z, 0-9 and -, start with a letter and not end with -.")
NAME_RESERVED = ("`name=%s` is a reserved name: `test`, `shared` and names that start with "
                 "`test-` are for tests and the shared platform.")
OWNER_INVALID = ("`owner=%s` is not a valid owner: it must have 1 to 39 characters of A-Z, "
                 "a-z, 0-9 and -, and not start or end with -.")
REPO_NAME_INVALID = ("`repoName=%s` is not a valid repository name: it must have 1 to 100 "
                     "characters of A-Z, a-z, 0-9, ., _ and -, and not be `.` or `..`.")
VISIBILITY_INVALID = "`visibility=%s` must be `public` or `private`."
DESCRIPTION_INVALID = ("The description is not valid: it must have 1 to 350 characters, no "
                       "line break and none of \" ` $ \\ “ ” „.")
SETTING_INVALID = "`%s=%s` must be `true` or `false`."
TOPIC_EMPTY = "`topics=%s` has an empty item."
TOPIC_INVALID = ("The topic `%s` is not valid: a topic has 1 to 50 characters of a-z, 0-9 "
                 "and -, and starts with a letter or a digit.")
TOPIC_DERIVED = ("The topic `aleogr-%s` is derived from the project name and never written: "
                 "leave it out of `topics`.")
COMPONENT_INVALID = ("`component=%s` is not a valid component name: it must have 1 to 20 "
                     "characters of a-z, 0-9 and -, starting with a letter.")
COMPONENT_DEPLOY = ("`component=%s` is a reserved name: names that start with `deploy-` are "
                    "the deploy jobs of the project's CI file.")
STACK_INVALID = "`stack=%s` is not a stack this tooling implements: `go` is the only one."
VERSION_INVALID = ("`version=%s` is not a version: it must be major.minor, digits, a dot, "
                   "digits, such as `1.27`.")
NO_MERGE_METHOD = ("The declaration would have none of `mergeCommit`, `squash` and `rebase` "
                   "set to `true`: at least one merge method is needed.")
CLOUD_DEFAULTS = ("The defaults' `cloud` is not one this tooling implements: its `provider` "
                  "must be `gcp` and its `region` a GCP region name such as `us-central1`.")
PROVIDER_DEFAULTS = "The defaults' `repo.provider` is not `github`: only GitHub is implemented."
NOT_JSON = "The declaration .aleogr/project.json is not valid JSON."
NOT_VALID = "The declaration .aleogr/project.json is not valid: %s."
NOT_READABLE = "The declaration .aleogr/project.json could not be read."
RESULT_INVALID = "The declaration would not be valid: %s."
NOT_WRITTEN = "The file .aleogr/project.json could not be written; it is as it was."
PUBLIC_LINE = ("The declaration only states the visibility: nothing is public until "
               "project-apply runs with confirmVisibility=public.")


class Failed(Exception):
    """A step ended the run with `failed`: its sentences."""

    def __init__(self, lines):
        Exception.__init__(self, lines)
        self.lines = [lines] if isinstance(lines, str) else list(lines)


def _capital(s):
    return s[:1].upper() + s[1:]


def _code(names):
    return ", ".join("`%s`" % n for n in names)


# ---------------------------------------------------------------------------
# Steps 1 and 2


class Defaults(object):
    """defaults.json of this plugin (project-plan's reader): get() raises Failed with
    the sentence naming what is missing."""

    def __init__(self, path):
        self._d = PP.Defaults(path)

    def get(self, dotted, kind):
        try:
            return self._d.get(dotted, kind)
        except PP.Invalid as e:
            raise Failed("%s." % _capital(str(e)))

    def raw(self, dotted):
        """The value at `dotted`, or None (the defaults are known to be readable)."""
        v = self._d._load()
        for part in dotted.split("."):
            v = v.get(part) if isinstance(v, dict) else None
        return v

    def min_version(self, stack):
        v = self.raw("stacks.%s.database.minVersion" % stack)
        if PP.version_tuple(v) is None:
            raise Failed(NO_MIN_VERSION % stack)
        return v


def read_defaults(path):
    """Step 1."""
    d = Defaults(path)
    if d.get("repo.provider", "str") != "github":
        raise Failed(PROVIDER_DEFAULTS)
    return d


def _check(data, defaults):
    """The declaration's rules (project-plan's check_declaration); Failed on a problem."""
    try:
        PP.check_declaration(data, lambda: defaults.min_version("go"))
    except PP.Invalid as e:
        return str(e)
    return None


def read_file(folder, defaults):
    """Step 2: (text, data), or (None, None) for a new declaration."""
    text, exists = PP._read_text(os.path.join(folder, DECLARATION))
    if exists is False:
        return None, None
    if text is None:
        raise Failed(NOT_READABLE)
    try:
        data = PP.parse_json(text)
    except ValueError:
        raise Failed(NOT_JSON)
    problem = _check(data, defaults)
    if problem:
        raise Failed(NOT_VALID % problem)
    return text, data


# ---------------------------------------------------------------------------
# Step 3


def _split_topics(value):
    return value.split(",") if value != "" else []


def _component_name_problem(v):
    if not PP._COMPONENT.match(v):
        return COMPONENT_INVALID % v
    if v in PP._RESERVED_COMPONENTS:
        return COMPONENT_RESERVED % v
    if v.startswith("deploy-"):
        return COMPONENT_DEPLOY % v
    return None


def _description_problem(v):
    """The rule of repo.description, as project-plan checks it."""
    probe = {"version": 1, "name": "probe",
             "repo": {"provider": "github", "owner": "probe", "name": "probe",
                      "visibility": "private", "description": v,
                      "settings": dict((k, True) for k in SETTINGS_KEYS)}}
    try:
        PP.check_declaration(probe)
    except PP.Invalid:
        return DESCRIPTION_INVALID
    return None


def _inside(a, b):
    return a.startswith(b + "/") or b.startswith(a + "/")


def check_args(args, data, defaults):
    """Step 3: the sentences of every problem, in the order of the SKILL.md's list. An
    argument that already failed is not checked again by a later rule."""
    problems = []
    bad = set()
    new = data is None
    repo = {} if new else data["repo"]
    components = [] if new else list(data.get("components", []))
    by_name = dict((c["name"], c) for c in components)

    # Every argument is one of the table (one given twice is refused by the command line).
    for k in args:
        if k not in ARGUMENTS:
            problems.append(UNKNOWN_ARGUMENT % k)

    comp = args.get("component")
    comp_new = comp is not None and comp not in by_name

    # Missing arguments of a new declaration, and the stack of a new component.
    missing = [k for k in ("name", "owner", "description") if new and k not in args]
    if comp_new and "stack" not in args:
        missing.append("stack")
    if missing:
        problems.append((MISSING_ONE if len(missing) == 1 else MISSING_MANY) % _code(missing))

    # The values of the project's keys.
    if "name" in args:
        v = args["name"]
        if not PP._NAME.match(v):
            problems.append(NAME_INVALID % v)
            bad.add("name")
        elif v in ("test", "shared") or v.startswith("test-"):
            problems.append(NAME_RESERVED % v)
            bad.add("name")
    if "owner" in args and not PP._OWNER.match(args["owner"]):
        problems.append(OWNER_INVALID % args["owner"])
        bad.add("owner")
    if "repoName" in args:
        v = args["repoName"]
        if not PP._REPO_NAME.match(v) or v in (".", ".."):
            problems.append(REPO_NAME_INVALID % v)
            bad.add("repoName")
    if "visibility" in args and args["visibility"] not in ("public", "private"):
        problems.append(VISIBILITY_INVALID % args["visibility"])
    if "description" in args:
        p = _description_problem(args["description"])
        if p:
            problems.append(p)
    for k in SETTINGS_KEYS:
        if k in args and args[k] not in ("true", "false"):
            problems.append(SETTING_INVALID % (k, args[k]))
            bad.add(k)

    project = args.get("name") if new else data["name"]
    project_ok = project is not None and "name" not in bad

    if "topics" in args:
        items = _split_topics(args["topics"])
        if "" in items:
            problems.append(TOPIC_EMPTY % args["topics"])
        for t in items:
            if t != "" and not PP._TOPIC.match(t):
                problems.append(TOPIC_INVALID % t)
        if project_ok and project is not None and "aleogr-%s" % project in items:
            problems.append(TOPIC_DERIVED % project)

    # The component's arguments.
    if comp is None:
        given = [k for k in COMPONENT_ARGS if k in args]
        if given:
            problems.append(DESCRIBE_COMPONENT % _code(given))
            bad.update(given)
    if "database" in args and "database" not in bad and args["database"] not in ("yes", "no"):
        problems.append(DATABASE_VALUE % args["database"])
        bad.add("database")
    if comp is not None:
        p = _component_name_problem(comp)
        if p:
            problems.append(p)
            bad.add("component")
    if "stack" in args and "stack" not in bad and args["stack"] != "go":
        problems.append(STACK_INVALID % args["stack"])
        bad.add("stack")
    if "path" in args and "path" not in bad:
        why = PP._path_problem(args["path"])
        if why:
            detail = "it %s" % why
            problems.append(PATH_CANNOT % (args["path"], detail if detail.endswith(".")
                                           else detail + "."))
            bad.add("path")
    if "version" in args and "version" not in bad:
        v = args["version"]
        vt = PP.version_tuple(v)
        if vt is None:
            problems.append(VERSION_INVALID % v)
            bad.add("version")
        else:
            stack = args.get("stack") if comp_new else (by_name[comp]["stack"]
                                                         if comp in by_name else None)
            if stack == "go" and vt < (1, 22):
                problems.append(VERSION_TOO_OLD % v)
                bad.add("version")

    if comp is not None and "component" not in bad:
        if comp_new:
            path = args.get("path", comp)
            if "path" not in bad:
                others = sorted(components, key=lambda c: c["name"])
                same = [c for c in others if c["path"] == path]
                nested = [c for c in others if _inside(path, c["path"])]
                if same:
                    problems.append(PATH_SHARED % (path, same[0]["name"]))
                    bad.add("path")
                elif nested:
                    problems.append(PATH_NESTED % (path, nested[0]["name"]))
                    bad.add("path")
        else:
            c = by_name[comp]
            for k, word in (("stack", "stack"), ("path", "path")):
                if k in args and k not in bad and args[k] != c[k]:
                    problems.append(ANOTHER_COMPONENT % (k, args[k], word, comp, c[k]))
                    bad.add(k)

    if "environment" in args and args["environment"] != "dev":
        problems.append(ENVIRONMENT_VALUE % args["environment"])
        bad.add("environment")
    if "cloudRoot" in args and args["cloudRoot"] != "tst":
        problems.append(ROOT_VALUE % args["cloudRoot"])
        bad.add("cloudRoot")

    env_arg = args.get("environment") == "dev"
    if env_arg and project_ok and project is not None and len(project) < 3:
        problems.append(SHORT_NAME % project)

    with_env = env_arg or (not new and "environments" in data)
    if with_env and project_ok and project is not None:
        names = [c["name"] for c in components]
        if comp_new and "component" not in bad:
            names.append(comp)
        for n in sorted(names):
            service = "%s-%s" % (project, n)
            if n.endswith("-") or not 6 <= len(service) <= 30:
                problems.append(SERVICE_NAME % service)
                break

    has_env = not new and "environments" in data
    if args.get("database") == "yes" and not has_env and "environment" not in args:
        problems.append(DATABASE_NEEDS_ENVIRONMENT)

    # The components of the result that use the database, with their version.
    users = []
    for c in components:
        if c["name"] == comp:
            continue
        if c.get("database") is True:
            users.append((c["name"], c["stack"], c["version"]))
    if comp is not None and "component" not in bad and "database" not in bad:
        old = by_name.get(comp)
        uses = (args.get("database") == "yes" or
                (old is not None and old.get("database") is True
                 and args.get("database") != "no"))
        stack = old["stack"] if old else args.get("stack")
        if uses and stack == "go" and "version" not in bad:
            if "version" in args:
                version = args["version"]
            elif old is not None:
                version = old["version"]
            else:
                version = defaults.get("stacks.%s.version" % stack, "version")
            users.append((comp, stack, version))
    for name, stack, version in sorted(users):
        try:
            minimum = defaults.min_version(stack)
        except Failed as e:
            problems.extend(e.lines)
            break
        if PP.version_tuple(version) < PP.version_tuple(minimum):
            problems.append(DATABASE_VERSION % (name, version, minimum, minimum))
            break

    if (args.get("cloudRoot") == "tst" and "environment" not in args
            and (new or "cloud" not in data)):
        problems.append(ROOT_NEEDS_CLOUD)

    if not new:
        for k, have, word in (("name", data["name"], "name"),
                              ("owner", repo["owner"], "owner"),
                              ("repoName", repo["name"], "repository name")):
            if k in args and k not in bad and args[k] != have:
                problems.append(ANOTHER_PROJECT % (k, args[k], word, have))
    return problems


# ---------------------------------------------------------------------------
# Step 4


def build(args, data, defaults):
    """Step 4: the result, canonical (Failed on a check of step 4)."""
    new = data is None
    if new:
        d_settings = defaults.raw("repo.settings")
        if not isinstance(d_settings, dict):
            raise Failed("Defaults.json of the plugin aleogr has no repo.settings.")
        out = {
            "name": args["name"],
            "repo": {
                "provider": defaults.get("repo.provider", "str"),
                "owner": args["owner"],
                "name": args.get("repoName", args["name"]),
                "visibility": (args["visibility"] if "visibility" in args
                               else defaults.get("repo.visibility", "str")),
                "description": args["description"],
                "topics": [],
                "settings": {},
            },
            "components": [],
        }
        for k in SETTINGS_KEYS:
            if k in args:
                out["repo"]["settings"][k] = args[k] == "true"
            elif k in d_settings:
                out["repo"]["settings"][k] = d_settings[k]
            else:
                raise Failed("Defaults.json of the plugin aleogr has no repo.settings.%s." % k)
    else:
        repo = data["repo"]
        out = {
            "name": data["name"],
            "repo": {
                "provider": repo["provider"],
                "owner": repo["owner"],
                "name": repo["name"],
                "visibility": repo["visibility"],
                "description": repo["description"],
                "topics": list(repo.get("topics", [])),
                "settings": dict((k, repo["settings"][k]) for k in SETTINGS_KEYS),
            },
            "components": [dict(c) for c in data.get("components", [])],
        }
        if "cloud" in data:
            out["cloud"] = dict(data["cloud"])
        if "environments" in data:
            out["environments"] = {"dev": {}}
        if "notes" in data:
            out["notes"] = data["notes"]
        for k in ("visibility", "description"):
            if k in args:
                out["repo"][k] = args[k]
        for k in SETTINGS_KEYS:
            if k in args:
                out["repo"]["settings"][k] = args[k] == "true"

    if "topics" in args:
        out["repo"]["topics"] = sorted(set(_split_topics(args["topics"])))
    if "notes" in args:
        if args["notes"] == "":
            out.pop("notes", None)
        else:
            out["notes"] = args["notes"]

    comp = args.get("component")
    if comp is not None:
        found = [c for c in out["components"] if c["name"] == comp]
        if found:
            c = found[0]
            if "version" in args:
                c["version"] = args["version"]
        else:
            stack = args["stack"]
            c = {"name": comp, "stack": stack, "path": args.get("path", comp),
                 "version": (args["version"] if "version" in args
                             else defaults.get("stacks.%s.version" % stack, "version"))}
            out["components"].append(c)
        if args.get("database") == "yes":
            c["database"] = True
        elif args.get("database") == "no":
            c.pop("database", None)

    cloud_from_defaults = False
    if args.get("environment") == "dev":
        out["environments"] = {"dev": {}}
        if "cloud" not in out:
            out["cloud"] = {"provider": defaults.raw("cloud.provider"),
                            "region": defaults.raw("cloud.region")}
            cloud_from_defaults = True
    if args.get("cloudRoot") == "tst":
        out["cloud"]["root"] = "tst"

    s = out["repo"]["settings"]
    if not (s["mergeCommit"] is True or s["squash"] is True or s["rebase"] is True):
        raise Failed(NO_MERGE_METHOD)
    if cloud_from_defaults:
        cloud = out["cloud"]
        if (cloud["provider"] != "gcp" or not isinstance(cloud["region"], str)
                or not PP._REGION.match(cloud["region"])):
            raise Failed(CLOUD_DEFAULTS)
    result = canonical(out)
    problem = _check(result, defaults)
    if problem:
        raise Failed(RESULT_INVALID % problem)
    return result


def canonical(d):
    """The declaration `d` (valid) with its keys in the canonical order and the values
    the canonical form writes: $schema always, topics sorted, components sorted by name
    and only when there are some, a component's database only when true."""
    repo = d["repo"]
    out = {"$schema": SCHEMA, "version": 1, "name": d["name"]}
    out["repo"] = {
        "provider": repo["provider"],
        "owner": repo["owner"],
        "name": repo["name"],
        "visibility": repo["visibility"],
        "description": repo["description"],
        "topics": sorted(repo.get("topics", [])),
        "settings": dict((k, repo["settings"][k]) for k in SETTINGS_KEYS),
    }
    comps = []
    for c in sorted(d.get("components", []), key=lambda c: c["name"]):
        x = dict((k, c[k]) for k in ("name", "stack", "path", "version"))
        if c.get("database") is True:
            x["database"] = True
        comps.append(x)
    if comps:
        out["components"] = comps
    if "cloud" in d:
        cloud = d["cloud"]
        out["cloud"] = dict((k, cloud[k]) for k in ("provider", "region", "root") if k in cloud)
    if "environments" in d:
        out["environments"] = {"dev": {}}
    if "notes" in d:
        out["notes"] = d["notes"]
    return out


def _j(v):
    return json.dumps(v, ensure_ascii=False)


def _inline(obj):
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        return "{ " + ", ".join("%s: %s" % (_j(k), _inline(v)) for k, v in obj.items()) + " }"
    if isinstance(obj, list):
        return "[" + ", ".join(_inline(v) for v in obj) + "]"
    return _j(obj)


def canonical_text(d):
    """The canonical form of the canonical declaration `d`, byte for byte."""
    def block(pairs, indent):
        pad = " " * indent
        lines = []
        for i, (k, v) in enumerate(pairs):
            comma = "," if i < len(pairs) - 1 else ""
            lines.append("%s%s: %s%s" % (pad, _j(k), v, comma))
        return lines

    repo = d["repo"]
    settings = ["{"] + block([(k, _j(repo["settings"][k])) for k in SETTINGS_KEYS], 6) + \
        ["    }"]
    repo_pairs = [(k, _j(repo[k])) for k in ("provider", "owner", "name", "visibility",
                                             "description")]
    repo_pairs.append(("topics", _inline(repo["topics"])))
    repo_pairs.append(("settings", "\n".join(settings)))
    pairs = [("$schema", _j(d["$schema"])), ("version", _j(d["version"])),
             ("name", _j(d["name"])),
             ("repo", "\n".join(["{"] + block(repo_pairs, 4) + ["  }"]))]
    if "components" in d:
        items = d["components"]
        body = ["    %s%s" % (_inline(c), "," if i < len(items) - 1 else "")
                for i, c in enumerate(items)]
        pairs.append(("components", "\n".join(["["] + body + ["  ]"])))
    if "cloud" in d:
        pairs.append(("cloud", _inline(d["cloud"])))
    if "environments" in d:
        pairs.append(("environments", _inline(d["environments"])))
    if "notes" in d:
        pairs.append(("notes", _j(d["notes"])))
    return "\n".join(["{"] + block(pairs, 2) + ["}"]) + "\n"


# ---------------------------------------------------------------------------
# Step 5


def _repo_paths():
    return (["repo.provider", "repo.owner", "repo.name", "repo.visibility",
             "repo.description", "repo.topics"] +
            ["repo.settings.%s" % k for k in SETTINGS_KEYS])


def _value(d, path):
    repo = d["repo"]
    if path == "repo.topics":
        return set(repo["topics"])
    if path.startswith("repo.settings."):
        return repo["settings"][path.split(".")[2]]
    return repo[path.split(".")[1]]


def changes(old, new):
    """Step 5: the key paths of `new` (canonical) written (old None) or whose value
    differs from `old` (canonical), in the canonical order."""
    if old is None:
        out = ["$schema", "version", "name"] + _repo_paths()
        out += ["components.%s" % c["name"] for c in new.get("components", [])]
        if "cloud" in new:
            out.append("cloud")
        if "environments" in new:
            out.append("environments.dev")
        if "notes" in new:
            out.append("notes")
        return out
    out = [p for p in _repo_paths() if _value(old, p) != _value(new, p)]
    before = dict((c["name"], c) for c in old.get("components", []))
    for c in new.get("components", []):
        o = before.get(c["name"])
        if (o is None or o["version"] != c["version"]
                or o.get("database", False) != c.get("database", False)):
            out.append("components.%s" % c["name"])
    if "cloud" in new:
        if "cloud" not in old:
            out.append("cloud")
        elif new["cloud"].get("root") != old["cloud"].get("root"):
            out.append("cloud.root")
    if "environments" in new and "environments" not in old:
        out.append("environments.dev")
    if old.get("notes") != new.get("notes"):
        out.append("notes")
    return out


def _outputs(declaration, changed):
    return {"path": DECLARATION, "declaration": declaration, "changes": list(changed)}


def _failed(ctx, lines):
    return ctx.failed(lines, _outputs(None, []), cost=dict(COST))


def _answer(sentence, text, extra=()):
    return [sentence, "", "```json"] + text.rstrip("\n").split("\n") + ["```"] + list(extra)


def run(args, ctx):
    try:
        defaults = read_defaults(ctx.plugin_path("defaults.json"))
        text, data = read_file(os.getcwd(), defaults)
        problems = check_args(args, data, defaults)
        if problems:
            return _failed(ctx, problems)
        result = build(args, data, defaults)
    except Failed as e:
        return _failed(ctx, e.lines)

    old = None if data is None else canonical(data)
    changed = changes(old, result)
    if old is not None and not changed:
        sentence = "The declaration .aleogr/project.json is unchanged: no key changed."
        return ctx.result("unchanged", _outputs(data, []), cost=dict(COST),
                          lines=_answer(sentence, text))

    content = canonical_text(result)
    if not ctx.write_file(DECLARATION, content):
        return _failed(ctx, NOT_WRITTEN)
    public = result["repo"]["visibility"] == "public" and (
        old is None or old["repo"]["visibility"] != "public")
    extra = ["", PUBLIC_LINE] if public else []
    if old is None:
        status = "created"
        sentence = ("The declaration .aleogr/project.json was created, with these keys: %s."
                    % ", ".join(changed))
    else:
        status = "updated"
        sentence = ("The declaration .aleogr/project.json was updated; these keys changed: "
                    "%s." % ", ".join(changed))
    return ctx.result(status, _outputs(result, changed), cost=dict(COST),
                      lines=_answer(sentence, content, extra))
