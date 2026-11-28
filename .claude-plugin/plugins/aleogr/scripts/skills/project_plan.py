"""project-plan: compare the project's declaration with its GitHub repository and, when
environments are declared, with its GCP environment dev; print a table of items, state
and action. Read-only: it runs no provider command of its own, only tools-check (in this
plugin, called as a function) and the read modes of the other plugins' commands.

The specification is skills/project-plan/SKILL.md: the same invocations, in the same
order, the same items, states, actions, lines and result block.

The module keeps three things apart, so that project-apply (step 3) can call the plan
as a function and get the same object:

- reading: gather(args, ctx_or_caller) runs steps 1 to 16 and returns a Reads, which holds
  every input (the declaration, the defaults, each called skill's result) and, when a
  step ended the plan, its Failure;
- deciding: the row functions (declaration_row, ..., secrets_row), rows(), status(),
  outputs() and pending() are pure functions of a Reads; decide() returns a Plan;
- printing: answer_lines(plan) and run().

plan(args, ctx) gives the Plan; run(args, ctx) prints it.
"""

import importlib.util
import json
import os
import re
import sys

import aleogr_common

FAMILY = "orchestrator"
PROVIDER = "aleogr"
ACTION = "project-plan"
RESULT_MODE = "plan"  # mode is always plan
COST = {"fixed": False, "notes": "read-only plan"}

DECLARATION = ".aleogr/project.json"
LOCAL_CI = ".github/workflows/ci.yml"
SCHEMA = ("https://raw.githubusercontent.com/aleogr/aleogr/main/.claude-plugin/schemas/"
          "project.schema.json")

GH = "aleogr-repo-github"
CLOUD = "aleogr-cloud-gcp"
REGISTRY = "aleogr-registry-gcp-artifact-registry"
DB = "aleogr-db-gcp-cloud-sql"
GO = "aleogr-stack-go"


def _tools_check():
    """This plugin's tools-check module, loaded by its file path (a unit test loads this
    module by path too, where `skills` may be another plugin's package)."""
    name = "aleogr_plugin_tools_check"
    if name not in sys.modules:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools_check.py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


TC = _tools_check()

# ---------------------------------------------------------------------------
# Fixed sentences (prescribed ones word for word; the others fixed here)

NO_DECLARATION = ("There is no .aleogr/project.json in this folder: declare the project first "
                  "with /aleogr:project-declare.")
NO_DECLARATION_HOW = "declare the project first with /aleogr:project-declare"
LOGIN_JUST_ENABLED = ("The login of the organization could not be read yet: the IAP API of the "
                      "GCP project of dev was just enabled; wait a minute, then run "
                      "/aleogr:project-plan again.")
LOGIN_JUST_ENABLED_HOW = ("the IAP API of the GCP project of dev was just enabled: wait a "
                          "minute, then run /aleogr:project-plan again")
SHARED_AMBIGUOUS = ("More than one GCP project carries the labels of the shared platform: keep "
                    "one, then run /aleogr:project-plan again.")
SHARED_UNREADABLE = ("The shared project could not be read: check that the active gcloud "
                     "account may list and read projects, then run /aleogr:project-plan again.")

EXPOSES_LINE = ("This plan makes the repository public: project-apply runs it only with "
                "confirmVisibility=public.")
UNAVAILABLE_LINE = "main is held by the working rule, not by GitHub."
UNAVAILABLE_PUBLIC_LINE = ("main is held by the working rule, not by GitHub; protection is "
                           "checked again once the repository is public.")
GENERATE_LINE = ("project-apply writes the files in this folder and proposes them, with the "
                 "declaration, in one pull request.")
LOGIN_LINE = ("The services wait for the login of the organization: /aleogr:platform-plan "
              "shows what preparing it makes and what it costs. project-apply creates no "
              "service until it is prepared.")
WAITING_LINE = ("The services of %s still run the placeholder image until CI deploys them: "
                "merge the pull request that carries the deploy jobs, or, once it is merged, "
                "merge a change to the component (re-running an older run deploys nothing "
                "new).")
ROUTE_LINE = ("The route GET /db is not in %s/main.go, which is not the file the tooling "
              "wrote: add the line mux.HandleFunc(\"GET /db\", dbCheck) to its router.")
NOT_READ_LINE = "The database itself was not read: the shared instance is %s."
NOT_READ_UNKNOWN_LINE = ("The database itself was not read: the state of the shared instance "
                         "is not known; /aleogr:platform-plan shows it.")
START_LINE = ("project-apply starts the shared instance (about twelve minutes); it then runs, "
              "charged by the hour, until the night stop.")
STARTING_LINE = ("The shared instance is starting: project-apply confirm=yes waits until it "
                 "accepts calls, then makes what is missing.")
CREATING_LINE = ("The shared instance is creating: wait some minutes, then run "
                 "/aleogr:project-plan again.")
UNKNOWN_LINE = "The state of the shared instance is not known: /aleogr:platform-plan shows it."
BEFORE_START_LINE = ("If parts of the database are missing and the shared instance is stopped, "
                     "project-apply starts it: it then runs, charged by the hour, until the "
                     "night stop.")
SETTINGS_ONLY_LINE = ("project-apply writes the services' settings; the shared instance is not "
                      "needed for that.")
GO_LINE = ("Go is not installed on this machine, and the database modules of %s are added "
           "with it: install Go (https://go.dev/doc/install), or run from Cloud Shell, which "
           "has it.")
SHARED_PLATFORM_LINE = ("The database of %s needs the shared platform, which was not found or "
                        "is not ready: /aleogr:platform-plan shows what it makes and what it "
                        "costs.")
TOO_LONG_LINE = ("The name of the component %s is too long for a database user in this GCP "
                 "project: its user would have %d characters, and PostgreSQL allows 63; "
                 "choose a shorter component name.")
SECRETS_LINE = "The CI secrets are compared by name only: a secret's value cannot be read back."
NOTHING_TO_DO = "nothing to do"
NOTHING_FOR_DATABASE = "Nothing can be made for the database until the shared platform is ready."

GO_HOW = ("install Go (https://go.dev/doc/install), or run from Cloud Shell, which has it; "
          "then run /aleogr:project-plan again")
LOGIN_HOW = ("prepare the login of the organization: /aleogr:platform-plan shows what it makes "
             "and what it costs; then run /aleogr:project-plan again")
SHARED_HOW = ("the database of %s needs the shared platform: /aleogr:platform-plan shows what "
              "it makes and what it costs; then run /aleogr:project-plan")
TOO_LONG_HOW = ("the name of the component %s is too long for a database user in the GCP "
                "project of dev (its user would have %d characters; PostgreSQL allows 63): "
                "choose a shorter component name, then run /aleogr:project-plan again")
OTHER_REGION_HOW = ("the image repository %s exists in %s and not in the declared region %s: "
                    "delete or move it by hand, then run /aleogr:project-plan again")
NOT_DOCKER_HOW = ("the repository %s in %s is not a Docker repository (its format is %s) and "
                  "a format never changes: remove it by hand, then run /aleogr:project-plan "
                  "again")

# Actions
NONE = "none"
OWNER_ACTIONS = ("merge it", "fix the folder", "fix by hand", "prepare the login")
WRITE_ACTIONS = ("create", "update", "send", "propose", "generate", "repair", "enable",
                 "configure", "grant", "set")

# States of the rows that a case replaces
FOLLOWS_CREATION = "follows the creation"
NOT_CHECKED_MERGE = "not checked until the change is merged"
NOT_CHECKED_SENT = "not checked until the declaration is sent"
FOLLOWS_ENVIRONMENT = "follows the environment"
FOLLOWS_APIS = "follows the apis"
FOLLOWS_SERVICES = "follows the services"
SHARED_PLATFORM = "needs the shared platform"
TOO_LONG = "user name too long"
NEEDS_GO = "needs Go on this machine"
POSTGRES_NAME_LIMIT = 63


class Failure(object):
    """A step that ended the plan with failed: the sentence of the answer and the one
    pending item."""

    def __init__(self, sentence, item, how):
        self.sentence = sentence
        self.item = item
        self.how = how


def pending_item(item, how):
    return {"item": item, "reason": "manual", "how": how}


# ---------------------------------------------------------------------------
# The declaration's rules (step 1)

_TOP_KEYS = ("$schema", "version", "name", "repo", "components", "cloud", "environments",
             "notes")
_REPO_KEYS = ("provider", "owner", "name", "visibility", "description", "topics", "settings")
SETTINGS_KEYS = ("mergeCommit", "squash", "rebase", "deleteBranchOnMerge", "issues", "wiki",
                 "projects")
_COMPONENT_KEYS = ("name", "stack", "path", "version", "database")
_CLOUD_KEYS = ("provider", "region", "root")

_NAME = re.compile(r"^[a-z](?:[a-z0-9-]{0,12}[a-z0-9])?$")
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPO_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_TOPIC = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")
_COMPONENT = re.compile(r"^[a-z][a-z0-9-]{0,19}$")
_PATH_PART = re.compile(r"^[a-z0-9_][a-z0-9_.-]*$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+$")
_REGION = re.compile(r"^[a-z]+-[a-z]+[0-9]+$")
_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_DESCRIPTION_REFUSED = ('"', "`", "$", "\\", "“", "”", "„")
_RESERVED_COMPONENTS = ("changes", "ci", "true", "false", "null", "yes", "no", "on", "off")


class Invalid(Exception):
    """The declaration breaks a rule: the problem, as a phrase."""


def _is_bool(v):
    return isinstance(v, bool)


def _is_str(v):
    return isinstance(v, str)


def version_tuple(v):
    """`major.minor` as (major, minor) numbers, or None."""
    if not isinstance(v, str) or not _VERSION.match(v):
        return None
    major, minor = v.split(".")
    return int(major), int(minor)


def _unknown_keys(obj, allowed, where):
    for k in obj:
        if k not in allowed:
            raise Invalid("%s has the unknown key %s" % (where, k))


def _required(obj, keys, where):
    for k in keys:
        if k not in obj:
            raise Invalid("%s lacks the key %s" % (where, k))


def _path_problem(path):
    if not isinstance(path, str) or path == "":
        return "is not a non-empty string"
    parts = path.split("/")
    for part in parts:
        if part == "":
            return "has an empty part (it must not start or end with / or hold //)"
        if part in (".", ".."):
            return "has the part %s" % part
        if not _PATH_PART.match(part):
            return ("has the part %s, which must use only a-z, 0-9, -, _ and ., and not "
                    "start with - or ." % part)
        if part.endswith("."):
            return "has the part %s, which ends with ." % part
    return None


def check_declaration(data, min_version=None):
    """Raise Invalid with the first problem of `data` (the parsed file), by the rules of
    "The declaration's rules". `min_version` is stacks.go.database.minVersion of the
    defaults, needed only when a component has "database": true (it is a callable that
    returns the value or raises Invalid... see validate_declaration)."""
    if not isinstance(data, dict):
        raise Invalid("the file is not a JSON object")
    _unknown_keys(data, _TOP_KEYS, "the top level")
    _required(data, ("version", "name", "repo"), "the top level")
    if "$schema" in data and not _is_str(data["$schema"]):
        raise Invalid("$schema is not a string")
    v = data["version"]
    if _is_bool(v) or not isinstance(v, (int, float)) or v != 1:
        raise Invalid("version is not the number 1")
    name = data["name"]
    if not _is_str(name) or not _NAME.match(name):
        raise Invalid("name must have 1 to 14 characters of a-z, 0-9 and -, start with a "
                      "letter and not end with -")
    if name in ("test", "shared") or name.startswith("test-"):
        raise Invalid("name %s is reserved (test, shared and test-... are for tests and the "
                      "shared platform)" % name)
    repo = data["repo"]
    if not isinstance(repo, dict):
        raise Invalid("repo is not an object")
    _unknown_keys(repo, _REPO_KEYS, "repo")
    _required(repo, ("provider", "owner", "name", "visibility", "description", "settings"),
              "repo")
    if repo["provider"] != "github":
        raise Invalid("repo.provider must be github")
    if not _is_str(repo["owner"]) or not _OWNER.match(repo["owner"]):
        raise Invalid("repo.owner must have 1 to 39 characters of A-Z, a-z, 0-9 and -, and "
                      "not start or end with -")
    rname = repo["name"]
    if not _is_str(rname) or not _REPO_NAME.match(rname) or rname in (".", ".."):
        raise Invalid("repo.name must have 1 to 100 characters of A-Z, a-z, 0-9, ., _ and -, "
                      "and not be . or ..")
    if repo["visibility"] not in ("public", "private") or not _is_str(repo["visibility"]):
        raise Invalid("repo.visibility must be public or private")
    d = repo["description"]
    if (not _is_str(d) or not 1 <= len(d) <= 350 or "\n" in d or "\r" in d
            or " " in d or " " in d or any(c in d for c in _DESCRIPTION_REFUSED)):
        raise Invalid("repo.description must have 1 to 350 characters, no line break and "
                      "none of \" ` $ \\ “ ” „")
    if "topics" in repo:
        topics = repo["topics"]
        if not isinstance(topics, list) or not all(_is_str(t) for t in topics):
            raise Invalid("repo.topics is not a list of strings")
        if len(set(topics)) != len(topics):
            raise Invalid("repo.topics has a repeated item")
        for t in topics:
            if not _TOPIC.match(t):
                raise Invalid("the topic %s must have 1 to 50 characters of a-z, 0-9 and -, "
                              "and start with a letter or a digit" % t)
        if "aleogr-%s" % name in topics:
            raise Invalid("repo.topics holds aleogr-%s, which is derived, not typed" % name)
    settings = repo["settings"]
    if not isinstance(settings, dict):
        raise Invalid("repo.settings is not an object")
    _unknown_keys(settings, SETTINGS_KEYS, "repo.settings")
    _required(settings, SETTINGS_KEYS, "repo.settings")
    for k in SETTINGS_KEYS:
        if not _is_bool(settings[k]):
            raise Invalid("repo.settings.%s is not a JSON boolean" % k)
    if not (settings["mergeCommit"] or settings["squash"] or settings["rebase"]):
        raise Invalid("repo.settings has none of mergeCommit, squash and rebase true")

    components = data.get("components", [])
    if not isinstance(components, list):
        raise Invalid("components is not a list")
    names, paths = [], []
    database_any = False
    for i, c in enumerate(components):
        where = "components[%d]" % i
        if not isinstance(c, dict):
            raise Invalid("%s is not an object" % where)
        _unknown_keys(c, _COMPONENT_KEYS, where)
        _required(c, ("name", "stack", "path", "version"), where)
        cname = c["name"]
        if not _is_str(cname) or not _COMPONENT.match(cname):
            raise Invalid("the name of %s must have 1 to 20 characters of a-z, 0-9 and -, "
                          "starting with a letter" % where)
        if cname in _RESERVED_COMPONENTS or cname.startswith("deploy-"):
            raise Invalid("the component name %s is reserved" % cname)
        if cname in names:
            raise Invalid("two components are named %s" % cname)
        names.append(cname)
        if c["stack"] != "go":
            raise Invalid("the stack of the component %s must be go" % cname)
        why = _path_problem(c["path"])
        if why:
            raise Invalid("the path of the component %s %s" % (cname, why))
        path = c["path"]
        for other in paths:
            if path == other:
                raise Invalid("two components have the path %s" % path)
            if path.startswith(other + "/") or other.startswith(path + "/"):
                raise Invalid("the path %s is inside another component's path" %
                              (path if path.startswith(other + "/") else other))
        paths.append(path)
        vt = version_tuple(c["version"])
        if vt is None:
            raise Invalid("the version of the component %s must be major.minor, such as "
                          "1.27" % cname)
        if vt < (1, 22):
            raise Invalid("the version of the component %s is earlier than 1.22, which the Go "
                          "starting point's routes need" % cname)
        if "database" in c:
            if not _is_bool(c["database"]):
                raise Invalid("the database of the component %s is not a JSON boolean"
                              % cname)
            if c["database"]:
                database_any = True
                if "cloud" not in data or "environments" not in data:
                    raise Invalid("the component %s uses the database, which needs cloud "
                                  "and environments" % cname)
                minimum = min_version() if callable(min_version) else min_version
                if vt < version_tuple(minimum):
                    raise Invalid("the component %s uses the database, which needs Go %s or "
                                  "later" % (cname, minimum))

    if "cloud" in data:
        cloud = data["cloud"]
        if not isinstance(cloud, dict):
            raise Invalid("cloud is not an object")
        _unknown_keys(cloud, _CLOUD_KEYS, "cloud")
        _required(cloud, ("provider", "region"), "cloud")
        if cloud["provider"] != "gcp":
            raise Invalid("cloud.provider must be gcp")
        if not _is_str(cloud["region"]) or not _REGION.match(cloud["region"]):
            raise Invalid("cloud.region must be a GCP region name such as us-central1")
        if "root" in cloud and cloud["root"] != "tst":
            raise Invalid("cloud.root must be tst")
    if "environments" in data:
        envs = data["environments"]
        if not isinstance(envs, dict) or not envs:
            raise Invalid("environments must be an object with at least one key")
        _unknown_keys(envs, ("dev",), "environments")
        if envs["dev"] != {} or not isinstance(envs["dev"], dict):
            raise Invalid("environments.dev must be an empty object")
        if "cloud" not in data:
            raise Invalid("environments needs cloud")
        if len(name) < 3:
            raise Invalid("name must have at least three characters with environments")
        for cname in names:
            if cname.endswith("-"):
                raise Invalid("the component name %s ends with -" % cname)
            service = "%s-%s" % (name, cname)
            if not 6 <= len(service) <= 30:
                raise Invalid("the service name %s must have 6 to 30 characters" % service)
    if "notes" in data and not _is_str(data["notes"]):
        raise Invalid("notes is not a string")
    return database_any


def _reject_constant(word):
    raise ValueError("not JSON: %s" % word)


def parse_json(text):
    """json.loads, refusing NaN and Infinity (they are not JSON)."""
    return json.loads(text, parse_constant=_reject_constant)


# ---------------------------------------------------------------------------
# The declaration, with the values the steps use


class Declaration(object):
    def __init__(self, data):
        self.data = data
        self.name = data["name"]
        repo = data["repo"]
        self.owner = repo["owner"]
        self.repo_name = repo["name"]
        self.full = "%s/%s" % (self.owner, self.repo_name)
        self.visibility = repo["visibility"]
        self.description = repo["description"]
        self.topics = list(repo.get("topics", []))
        self.settings = repo["settings"]
        self.components = sorted(data.get("components", []), key=lambda c: c["name"])
        self.environments = "environments" in data
        self.cloud = data.get("cloud")
        self.region = self.cloud["region"] if self.cloud else None

    @property
    def declared_topics(self):
        out = ["aleogr-%s" % self.name]
        for t in self.topics:
            if t not in out:
                out.append(t)
        return out

    @property
    def names(self):
        return [c["name"] for c in self.components]

    @property
    def database_components(self):
        return [c for c in self.components if c.get("database") is True]

    @property
    def database_names(self):
        return [c["name"] for c in self.database_components]

    @property
    def database(self):
        """<database>: <name>_dev with every - written _."""
        return "%s_dev" % self.name.replace("-", "_")

    def module(self, component):
        return "github.com/%s/%s/%s" % (self.owner, self.repo_name, component["path"])

    def components_arg(self):
        return ",".join("%s:%s:%s:%s" % (c["name"], c["path"], c["stack"], c["version"])
                        for c in self.components)

    def tooling_paths(self):
        paths = [DECLARATION, LOCAL_CI]
        for c in self.components:
            p = c["path"]
            paths += ["%s/go.mod" % p, "%s/main.go" % p, "%s/main_test.go" % p]
            if c.get("database") is True:
                paths += ["%s/go.sum" % p, "%s/db.go" % p, "%s/db_test.go" % p]
            if self.environments:
                paths.append("%s/Dockerfile" % p)
        return paths

    def user(self, component_name, project_id):
        """The database user of a component's service account (never printed)."""
        return "%s-%s@%s.iam" % (self.name, component_name, project_id)

    def account(self, component_name, project_id):
        return "%s-%s@%s.iam.gserviceaccount.com" % (self.name, component_name, project_id)


def database_settings(project, components, shared_project_id, region, instance, project_id,
                      environment="dev"):
    """The database's settings: the `env` argument of the service skills, the one rule
    project-plan (step 13) and project-apply (sub-step 12a, step e) both use.

    A component <c> that uses the database gets exactly three settings on its service:
    DB_INSTANCE=<shared project id>:<region>:<instance> (the shared instance's connection
    name), DB_NAME=<project>_<environment> with every `-` of the project's name written
    `_` (`demo_dev`; `my-app` gives `my_app_dev`), and DB_USER=<project>-<c>@<project
    id>.iam (the database user of the component's service account). They are written
    `<c>:DB_INSTANCE=...;<c>:DB_NAME=...;<c>:DB_USER=...` for each such component, the
    components sorted by name, all joined by `;`; a component that does not use the
    database gets none, and no other setting is given."""
    database = "%s_%s" % (project.replace("-", "_"), environment)
    entries = []
    for c in sorted(components):
        entries += ["%s:DB_INSTANCE=%s:%s:%s" % (c, shared_project_id, region, instance),
                    "%s:DB_NAME=%s" % (c, database),
                    "%s:DB_USER=%s-%s@%s.iam" % (c, project, c, project_id)]
    return ";".join(entries)


# ---------------------------------------------------------------------------
# The defaults


class Defaults(object):
    """defaults.json of this plugin, read once; get() raises Invalid naming what is
    missing."""

    def __init__(self, path):
        self.path = path
        self._data = None
        self._read = False

    def _load(self):
        if not self._read:
            self._read = True
            try:
                with open(self.path, encoding="utf-8") as f:
                    self._data = parse_json(f.read())
            except (OSError, ValueError, UnicodeDecodeError):
                self._data = None
        if not isinstance(self._data, dict):
            raise Invalid("defaults.json of the plugin aleogr could not be read")
        return self._data

    def get(self, dotted, kind):
        v = self._load()
        for part in dotted.split("."):
            v = v.get(part) if isinstance(v, dict) else None
        ok = {
            "str": lambda x: isinstance(x, str) and x != "",
            "list": lambda x: isinstance(x, list) and all(isinstance(i, str) for i in x),
            "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
            "scalar": lambda x: (isinstance(x, (int, float, str)) and not isinstance(x, bool)
                                 and x != ""),
            "version": lambda x: version_tuple(x) is not None,
        }[kind](v)
        if not ok:
            raise Invalid("defaults.json of the plugin aleogr has no %s" % dotted)
        return v


def _scalar_text(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


# ---------------------------------------------------------------------------
# Reading: steps 1 to 16


class Reads(object):
    """Everything the plan read, and the Failure that ended it (or None)."""

    def __init__(self, args):
        self.args = dict(args)
        self.failure = None
        self.decl = None  # Declaration
        self.values = {}  # the defaults' values the steps pass
        self.gh = None  # tools-check command=gh (a tools_check.Check)
        self.gcloud = None
        self.go = None  # tools-check command=go, when step 8 invoked it
        self.local_ci_first = None  # the first line of the local ci.yml (step 3)
        self.local_ci_exists = False
        self.describe = None  # step 4
        self.describe_checks = None  # "ci" or None: the checks step 4 passed
        self.describe2 = None  # step 16
        self.checkout = None  # step 5
        self.repository_environments = None
        self.repository_database_components = None
        self.pull_request = None  # step 6
        self.go_setup = []  # step 8: (component, result)
        self.environment = None  # step 9
        self.apis = None  # the APIs to enable (step 9)
        self.registry = None  # step 10
        self.identity = None  # step 11
        self.login = None  # step 12
        self.shared = None  # step 12a
        self.shared_project_id = None  # never printed
        self.deploy = None  # step 13
        self.deploy_env = False  # step 13 got env
        self.database = None  # step 13a
        self.instance = None  # step 13a, after a failed read of the instance
        self.secrets = None  # step 14
        self.ci = None  # step 15
        self.deploy_list = None  # the deploy list of step 15
        self.ci_default_branch = None

    # Shortcuts
    @property
    def exists(self):
        return bool(self.describe and _out(self.describe).get("exists") is True)

    @property
    def project_id(self):
        if self.environment is None:
            return None
        return _out(self.environment).get("projectId")


def _out(result):
    o = result.get("outputs") if isinstance(result, dict) else None
    return o if isinstance(o, dict) else {}


def _failed(result):
    return not isinstance(result, dict) or result.get("status") == "failed"


def cause(result):
    """The sentence a called skill gave for its failure, as it gave it."""
    lines = result.get("answer") if isinstance(result, dict) else None
    text = " ".join(l.strip() for l in (lines or []) if isinstance(l, str) and l.strip())
    if text:
        return text
    return "%s ended failed." % (result.get("action") if isinstance(result, dict) else "A skill")


def _how(sentence):
    return sentence[:-1] if sentence.endswith(".") else sentence


class Caller(object):
    """How gather() invokes the skills: call(command, skill, args) for another plugin's
    command, tools(command) for this plugin's tools-check. The command's Caller uses the
    context; a unit test gives its own."""

    def __init__(self, ctx):
        self.ctx = ctx

    def call(self, command, skill, args):
        return self.ctx.call(command, skill, args)

    def tools(self, command):
        return TC.check(command, self.ctx.read)

    def cwd(self):
        return os.getcwd()

    def defaults_path(self):
        return self.ctx.plugin_path("defaults.json")


def _read_text(path):
    """(text, exists). A folder or a file that cannot be read counts as absent for ci.yml,
    as the Read tool cannot read it either."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), True
    except FileNotFoundError:
        return None, False
    except (OSError, UnicodeDecodeError):
        return None, None


def validate_args(args):
    if "projectId" in args and not _PROJECT_ID.match(args["projectId"]):
        return ("projectId is not valid: it must have 6 to 30 characters of a-z, 0-9 and -, "
                "start with a letter and not end with -.")
    if "readCloud" in args and args["readCloud"] != "yes":
        return "readCloud is not valid: it must be yes."
    return None


def read_declaration(r, caller):
    """Step 1. Sets r.decl and r.values, or r.failure."""
    text, exists = _read_text(os.path.join(caller.cwd(), DECLARATION))
    if exists is False:
        r.failure = Failure(NO_DECLARATION, "declaration", NO_DECLARATION_HOW)
        return
    if text is None:
        r.failure = Failure("The declaration .aleogr/project.json could not be read.",
                            "declaration", "make .aleogr/project.json a readable file")
        return
    try:
        data = parse_json(text)
    except ValueError:
        r.failure = Failure("The declaration .aleogr/project.json is not valid JSON.",
                            "declaration", "fix .aleogr/project.json: it is not valid JSON")
        return
    defaults = Defaults(caller.defaults_path())

    def min_version():
        try:
            return defaults.get("stacks.go.database.minVersion", "version")
        except Invalid as e:
            raise _DefaultsProblem(str(e))
    try:
        check_declaration(data, min_version)
    except _DefaultsProblem as e:
        r.failure = Failure("%s." % _capital(str(e)), "defaults", str(e))
        return
    except Invalid as e:
        r.failure = Failure("The declaration .aleogr/project.json is not valid: %s." % e,
                            "declaration", "fix .aleogr/project.json: %s" % e)
        return
    d = Declaration(data)
    r.decl = d
    wanted = []
    if d.components:
        wanted.append(("workflows", "ci.workflowsRepository", "str"))
    if d.environments:
        wanted += [("services", "project.services", "list"),
                   ("keep", "project.registry.keep", "number"),
                   ("workflows", "ci.workflowsRepository", "str"),
                   ("deployWorkflow", "ci.deployWorkflow", "str")]
        if d.components:
            wanted += [("maxInstances", "project.deploy.maxInstances", "scalar"),
                       ("cpu", "project.deploy.cpu", "scalar"),
                       ("memory", "project.deploy.memory", "scalar")]
    if d.database_components:
        wanted += [("modules", "stacks.go.database.modules", "list"),
                   ("minVersion", "stacks.go.database.minVersion", "version"),
                   ("sharedProject", "platform.shared.project", "str"),
                   ("instance", "platform.database.instance", "str")]
    try:
        for key, dotted, kind in wanted:
            r.values[key] = defaults.get(dotted, kind)
    except Invalid as e:
        r.failure = Failure("%s." % _capital(str(e)), "defaults", str(e))
        r.decl = d


class _DefaultsProblem(Exception):
    pass


def _capital(s):
    return s[:1].upper() + s[1:]


def _tool_failure(chk, item):
    tool = chk.tool
    words = TC.STATE_WORDS[tool["state"]]
    return Failure("%s is %s: the fix is %s, then run /aleogr:project-plan again."
                   % (tool["name"], words, tool["fix"]), item, tool["fix"])


def _call_failure(result, item):
    sentence = cause(result)
    return Failure(sentence, item, _how(sentence))


def note_repository_copy(r):
    """Step 5's note of the repository's copy: its environments and its database
    components, from what github_checkout-setup read (its --json `data`)."""
    d = r.decl
    state = _out(r.checkout).get("state")
    if state == "equal":
        r.repository_environments = ["dev"] if d.environments else []
        r.repository_database_components = list(d.database_names)
        return
    if state in ("not-sent", "missing"):
        r.repository_environments, r.repository_database_components = [], []
        return
    data = r.checkout.get("data") if isinstance(r.checkout, dict) else None
    copy = data.get("repositoryCopy") if isinstance(data, dict) else None
    if not isinstance(copy, dict) or not copy.get("json"):
        r.repository_environments, r.repository_database_components = None, None
        return
    value = copy.get("value")
    envs = value.get("environments") if isinstance(value, dict) else None
    r.repository_environments = sorted(envs.keys()) if isinstance(envs, dict) else []
    comps = value.get("components") if isinstance(value, dict) else None
    r.repository_database_components = sorted(
        c["name"] for c in (comps if isinstance(comps, list) else [])
        if isinstance(c, dict) and c.get("database") is True and isinstance(c.get("name"),
                                                                            str))


def gather(args, caller):
    """Steps 1 to 16. Returns a Reads; r.failure is set when a step ended the plan."""
    r = Reads(args)
    # Step 1
    read_declaration(r, caller)
    if r.failure:
        return r
    problem = validate_args(args)
    if problem:
        r.failure = Failure(problem, "arguments", _how(problem))
        return r
    d = r.decl

    # Step 2
    r.gh = caller.tools("gh")
    if not r.gh.ok:
        r.failure = _tool_failure(r.gh, "gh")
        return r
    if d.environments:
        r.gcloud = caller.tools("gcloud")
        if not r.gcloud.ok:
            r.failure = _tool_failure(r.gcloud, "gcloud")
            return r

    # Step 3
    if d.components:
        text, exists = _read_text(os.path.join(caller.cwd(), LOCAL_CI))
        r.local_ci_exists = bool(exists) and text is not None
        if r.local_ci_exists:
            r.local_ci_first = text.splitlines()[0] if text.splitlines() else ""

    # Step 4
    r.describe_checks = "ci" if r.local_ci_exists else None
    a = {"owner": d.owner, "name": d.repo_name}
    if r.describe_checks:
        a["checks"] = "ci"
    r.describe = caller.call(GH, "github_repo-describe", a)
    if _failed(r.describe):
        r.failure = _call_failure(r.describe, "repository")
        return r
    if not r.exists:
        r.repository_environments, r.repository_database_components = [], []
        return r

    # Step 5
    a = {"owner": d.owner, "name": d.repo_name, "mode": "plan"}
    if d.components:
        a["head"] = "check"
    r.checkout = caller.call(GH, "github_checkout-setup", a)
    if _failed(r.checkout):
        r.failure = _call_failure(r.checkout, "declaration")
        return r
    note_repository_copy(r)

    # Step 6
    paths = d.tooling_paths() if d.components else [DECLARATION]
    r.pull_request = caller.call(GH, "github_pull-request-open",
                                 {"owner": d.owner, "name": d.repo_name,
                                  "paths": ",".join(paths), "mode": "plan"})
    if _failed(r.pull_request):
        r.failure = _call_failure(r.pull_request, "declaration")
        return r

    # Step 7
    action = declaration_row(r)[2]
    if not d.components:
        if d.environments and counts_in_repository(r):
            if not read_environment(r, caller):
                return r
        return r
    if action not in ("propose", NONE):
        return r

    # Step 8
    for c in d.components:
        a = {"component": c["name"], "path": c["path"], "version": c["version"],
             "module": d.module(c), "mode": "plan"}
        if d.environments:
            a["dockerfile"] = "yes"
        if c.get("database") is True:
            a["database"] = "yes"
            a["modules"] = ",".join(r.values["modules"])
            a["minVersion"] = r.values["minVersion"]
        result = caller.call(GO, "go_setup", a)
        if _failed(result):
            r.failure = _call_failure(result, c["name"])
            return r
        r.go_setup.append((c, result))
    if modules_to_add(r):
        r.go = caller.tools("go")

    if d.environments and counts_in_repository(r):
        if not read_environment(r, caller):
            return r

    # Step 15
    if not read_ci(r, caller):
        return r
    # Step 16
    expected = ci_expected(r)
    if action == NONE and (r.describe_checks == "ci") != expected:
        a = {"owner": d.owner, "name": d.repo_name}
        if expected:
            a["checks"] = "ci"
        r.describe2 = caller.call(GH, "github_repo-describe", a)
        if _failed(r.describe2):
            r.failure = _call_failure(r.describe2, "repository")
            return r
    return r


def modules_to_add(r):
    """The database components whose go_setup gave modules would-add."""
    return [c["name"] for c, res in r.go_setup
            if c.get("database") is True and _out(res).get("modules") == "would-add"]


def read_environment(r, caller):
    """Steps 9 to 14. False when one of them ended the plan (r.failure is set)."""
    d = r.decl
    # Step 9
    if "projectId" in r.args:
        a = {"projectId": r.args["projectId"]}
    else:
        a = {"project": d.name, "environment": "dev"}
    r.environment = caller.call(CLOUD, "gcp_environment-describe", a)
    if _failed(r.environment):
        r.failure = _call_failure(r.environment, "environment dev")
        return False
    env = _out(r.environment)
    if env.get("exists") is not True or env.get("billingLinked") is not True:
        return True
    wanted = list(r.values["services"])
    if d.database_components:
        wanted.append("sqladmin.googleapis.com")
    enabled = env.get("enabledServices") if isinstance(env.get("enabledServices"), list) else []
    r.apis = [s for s in wanted if s not in enabled]
    if r.apis:
        return True
    project_id = env.get("projectId")

    # Step 10
    r.registry = caller.call(REGISTRY, "gcp-artifact-registry_registry-describe",
                             {"projectId": project_id, "project": d.name, "region": d.region})
    if _failed(r.registry):
        r.failure = _call_failure(r.registry, "registry")
        return False

    # Step 11
    describe = _out(r.describe)
    r.identity = caller.call(CLOUD, "gcp_ci-identity-setup", {
        "projectId": project_id, "project": d.name,
        "repository": d.full,
        "repositoryId": _scalar_text(describe.get("id")),
        "ownerId": _scalar_text(describe.get("ownerId")),
        "branch": describe.get("defaultBranch"),
        "workflow": "%s/.github/workflows/%s" % (r.values["workflows"],
                                                 r.values["deployWorkflow"]),
        "mode": "plan"})
    if _failed(r.identity) and _out(r.identity).get("account") is None:
        r.failure = _call_failure(r.identity, "ci identity")
        return False
    if not d.components:
        return True

    # Step 12
    r.login = caller.call(CLOUD, "gcp_login-describe", {"projectId": project_id})
    login = _out(r.login)
    prepared = (not _failed(r.login)) and login.get("prepared") is True
    if not prepared:
        if (login.get("readable") is False and "the IAP API is off" in cause(r.login)
                and "iap.googleapis.com" in enabled):
            r.failure = Failure(LOGIN_JUST_ENABLED, "services", LOGIN_JUST_ENABLED_HOW)
            return False
        # Step 13 is not run: go straight to step 14.
        return read_secrets(r, caller)

    # Step 12a
    if d.database_components and not too_long_users(r):
        rows_so_far = [environment_row(r), apis_row(r), registry_row(r), identity_row(r)]
        if all(row[2] == NONE for row in rows_so_far):
            r.shared = caller.call(CLOUD, "gcp_environment-describe",
                                   {"project": r.values["sharedProject"], "platform": "shared"})
            if _failed(r.shared):
                sentence = (SHARED_AMBIGUOUS if cause(r.shared).startswith(
                    "More than one GCP project") else SHARED_UNREADABLE)
                r.failure = Failure(sentence, "database", _how(sentence))
                return False
            shared = _out(r.shared)
            services = shared.get("enabledServices")
            if (shared.get("exists") is True and isinstance(services, list)
                    and "sqladmin.googleapis.com" in services):
                r.shared_project_id = shared.get("projectId")

    # Step 13
    a = {"projectId": project_id, "project": d.name, "region": d.region,
         "components": ",".join(d.names),
         "maxInstances": _scalar_text(r.values["maxInstances"]),
         "cpu": _scalar_text(r.values["cpu"]), "memory": _scalar_text(r.values["memory"]),
         "ciAccount": _out(r.identity).get("account"), "environment": "dev"}
    if r.shared_project_id:
        a["env"] = database_settings(d.name, d.database_names, r.shared_project_id,
                                     d.region, r.values["instance"], project_id)
        r.deploy_env = True
    r.deploy = caller.call(CLOUD, "gcp_deploy-describe", a)
    if _failed(r.deploy):
        r.failure = _call_failure(r.deploy, "services")
        return False

    # Step 13a
    missing = _out(r.deploy).get("missing") or []
    if (r.shared_project_id and not any(n in missing for n in d.database_names)
            and services_row(r)[2] == NONE):
        accounts = ",".join(d.account(n, project_id) for n in d.database_names)
        r.database = caller.call(DB, "gcp-cloud-sql_database-describe", {
            "sharedProjectId": r.shared_project_id, "instance": r.values["instance"],
            "project": d.name, "environment": "dev", "accounts": accounts})
        if _failed(r.database):
            if _out(r.database).get("instanceState") is None:
                r.instance = caller.call(DB, "gcp-cloud-sql_instance-describe", {
                    "projectId": r.shared_project_id, "instance": r.values["instance"]})
                if _out(r.instance).get("exists") is False and not _failed(r.instance):
                    return read_secrets(r, caller)
            r.failure = _call_failure(r.database, "database")
            return False

    # Step 14
    return read_secrets(r, caller)


def read_secrets(r, caller):
    """Step 14. False when it ended the plan."""
    d = r.decl
    variables = _out(r.identity).get("ciVariables")
    image = _out(r.registry).get("imagePath")
    if identity_row(r)[2] != NONE or not isinstance(variables, dict) or not image:
        return True
    value = ("GCP_PROJECT_ID=%s,GCP_WIF_PROVIDER=%s,GCP_CI_ACCOUNT=%s,GCP_IMAGE_PATH=%s"
             % (variables.get("GCP_PROJECT_ID"), variables.get("GCP_WIF_PROVIDER"),
                variables.get("GCP_CI_ACCOUNT"), image))
    r.secrets = caller.call(GH, "github_variables-set", {
        "owner": d.owner, "name": d.repo_name, "kind": "secrets", "variables": value,
        "mode": "plan"})
    if _failed(r.secrets):
        r.failure = _call_failure(r.secrets, "ci secrets")
        return False
    return True


def deploy_list(r):
    """The components that get a deploy job (step 15), sorted."""
    d = r.decl
    if not d.environments:
        return []
    if r.deploy is not None:
        missing = _out(r.deploy).get("missing") or []
        return [n for n in d.names if n not in missing]
    first = r.local_ci_first or ""
    if first.startswith("# aleogr-ci 2 "):
        for word in first.split():
            if word.startswith("deploy=dev:"):
                listed = word[len("deploy=dev:"):].split("+")
                return sorted(n for n in set(listed) if n in d.names)
    return []


def read_ci(r, caller):
    """Step 15. False when it ended the plan."""
    d = r.decl
    r.deploy_list = deploy_list(r)
    r.ci_default_branch = _out(r.describe).get("defaultBranch")
    a = {"owner": d.owner, "name": d.repo_name, "components": d.components_arg(),
         "workflows": r.values["workflows"], "defaultBranch": r.ci_default_branch,
         "mode": "plan"}
    if r.deploy_list:
        a.update({"deploy": "dev", "deployComponents": ",".join(r.deploy_list),
                  "project": d.name, "region": d.region})
    r.ci = caller.call(GH, "github_ci-setup", a)
    if _failed(r.ci):
        r.failure = _call_failure(r.ci, "ci")
        return False
    return True


def ci_expected(r):
    """The protection is expected to require the check ci: step 15 ran and found ci.yml
    on the default branch."""
    return r.ci is not None and not _failed(r.ci) and _out(r.ci).get("inRepository") is True


# ---------------------------------------------------------------------------
# Deciding: the rows


def _names(names):
    return ", ".join(sorted(names))


def counts_in_repository(r):
    """The declaration counts as in the repository (see the SKILL)."""
    row = declaration_row(r)
    if row[2] == NONE:
        return True
    return (r.args.get("readCloud") == "yes" and row[1] == "changed here"
            and _out(r.checkout).get("state") == "equal")


def _protection(r):
    source = r.describe2 if r.describe2 is not None else r.describe
    p = _out(source).get("protection")
    return p if isinstance(p, dict) else {}


def declaration_row(r):
    co = _out(r.checkout)
    pr = _out(r.pull_request)
    state = co.get("state")
    open_pr = pr.get("openPullRequest")
    folder = pr.get("folder")
    changed = pr.get("changed") or []
    protected = _out(r.describe).get("protection", {}) or {}
    protected = protected.get("state") == "protected"
    generated = any(p != DECLARATION for p in changed)
    if open_pr:
        return ("declaration", "proposed in pull request #%s" % open_pr.get("number"),
                "merge it")
    if state == "equal" and not generated:
        return ("declaration", "in the repository", NONE)
    if state == "not-sent" and not protected:
        return ("declaration", "not sent yet", "send")
    if state == "behind":
        return ("declaration", "this folder is behind", "update")
    if state == "needs-attention" or (
            (state in ("differs", "missing") or (state == "not-sent" and protected))
            and folder != "ready"):
        return ("declaration", "this folder needs attention", "fix the folder")
    if state == "differs" or (state == "equal" and generated):
        return ("declaration", "changed here", "propose")
    return ("declaration", "not in the repository", "propose")


def settings_row(r):
    d = r.decl
    o = _out(r.describe)
    names = []
    if o.get("description") != d.description:
        names.append("description")
    got = o.get("topics") if isinstance(o.get("topics"), list) else []
    if set(got) != set(d.declared_topics):
        names.append("topics")
    got = o.get("settings") if isinstance(o.get("settings"), dict) else {}
    for k in SETTINGS_KEYS:
        if got.get(k) is not d.settings[k]:
            names.append(k)
    if names:
        return ("settings", "differs: %s" % ", ".join(names), "update")
    return ("settings", "as declared", NONE)


def visibility_row(r):
    if _out(r.describe).get("visibility") == r.decl.visibility:
        return ("visibility", "as declared", NONE)
    return ("visibility", "differs", "update")


def protection_row(r):
    p = _protection(r)
    state = p.get("state")
    if state == "protected":
        if p.get("matches") is True:
            return ("protection", "protected, requires ci" if ci_expected(r) else "protected",
                    NONE)
        return ("protection", "differs", "update")
    if state == "unavailable":
        return ("protection", "not available on this plan", NONE)
    return ("protection", "unprotected", "create")


def components_row(r):
    by = {}
    for c, res in r.go_setup:
        by.setdefault(res.get("status"), []).append(c["name"])
    if by.get("pending"):
        return ("components", "needs attention: %s" % _names(by["pending"]), "fix the folder")
    if r.go is not None and not r.go.ok:
        return ("components", NEEDS_GO, "fix by hand")
    if by.get("would-create"):
        return ("components", "to generate: %s" % _names(by["would-create"]), "generate")
    return ("components", "as declared", NONE)


def ci_row(r):
    local = _out(r.ci).get("local")
    if local == "as-declared":
        return ("ci", "as declared", NONE)
    if local == "missing":
        return ("ci", "missing", "generate")
    return ("ci", "differs", "generate")


def environment_row(r):
    env = _out(r.environment)
    if env.get("exists") is not True:
        return ("environment dev", "missing", "create")
    if env.get("billingLinked") is not True:
        return ("environment dev", "billing not linked", "repair")
    return ("environment dev", "exists", NONE)


def apis_row(r):
    if r.apis:
        return ("apis", "to enable: %d" % len(r.apis), "enable")
    return ("apis", "enabled", NONE)


def registry_row(r):
    o = _out(r.registry)
    cleanup = o.get("cleanup") if isinstance(o.get("cleanup"), dict) else {}
    if o.get("exists") is not True:
        if o.get("otherRegions"):
            return ("registry", "in another region", "fix by hand")
        return ("registry", "missing", "create")
    if o.get("format") != "DOCKER":
        return ("registry", "not a Docker repository", "fix by hand")
    keep = r.values.get("keep")
    if (cleanup.get("keep") != keep or isinstance(cleanup.get("keep"), bool)
            or cleanup.get("deletesTheRest") is not True or cleanup.get("dryRun") is True
            or cleanup.get("rules") != 2):
        return ("registry", "cleanup differs", "configure")
    return ("registry", "as declared", NONE)


def identity_row(r):
    if _failed(r.identity):
        return ("ci identity", "needs attention", "fix by hand")
    o = _out(r.identity)
    status = r.identity.get("status")
    registry = registry_row(r)[1]
    push = _out(r.registry).get("push") or []
    can_push = ("serviceAccount:%s" % o.get("account")) in push
    if status == "would-create":
        return ("ci identity", "missing", "create")
    if status == "would-update":
        return ("ci identity", "differs", "update")
    if registry in ("as declared", "cleanup differs"):
        if can_push:
            return ("ci identity", "as declared", NONE)
        return ("ci identity", "cannot push", "grant")
    if registry == "missing":
        return ("ci identity", "cannot push", "grant")
    return ("ci identity", "as declared", NONE)


def login_prepared(r):
    return (r.login is not None and not _failed(r.login)
            and _out(r.login).get("prepared") is True)


def service_lists(r):
    """(missing, differing, waiting) of step 13 for the row services: a component whose
    only difference is env is as declared (and waiting when it runs the placeholder)."""
    o = _out(r.deploy)
    by = {}
    for s in o.get("services") or []:
        if isinstance(s, dict):
            by[s.get("component")] = s
    missing = list(o.get("missing") or [])
    differing, waiting = [], list(o.get("waiting") or [])
    for n in o.get("differing") or []:
        s = by.get(n, {})
        if s.get("differences") == ["env"]:
            if s.get("placeholder") is True:
                waiting.append(n)
        else:
            differing.append(n)
    return missing, differing, waiting


def services_row(r):
    if not login_prepared(r):
        return ("services", "waits for the login", "prepare the login")
    missing, differing, waiting = service_lists(r)
    if missing:
        return ("services", "missing: %s" % _names(missing), "create")
    if differing:
        return ("services", "differs: %s" % _names(differing), "update")
    if waiting:
        return ("services", "waiting for the first deploy: %s" % _names(waiting), NONE)
    return ("services", "as declared", NONE)


def too_long_users(r):
    """[(component, length)] of the database components whose user has more than 63
    characters, with projectId of step 9."""
    pid = r.project_id
    if not pid:
        return []
    out = []
    for n in r.decl.database_names:
        n_len = len(r.decl.user(n, pid))
        if n_len > POSTGRES_NAME_LIMIT:
            out.append((n, n_len))
    return out


def shared_platform_missing(r):
    """The shared project was not found or has no Cloud SQL Admin API (step 12a), or the
    shared instance does not exist (step 13a)."""
    if r.shared is not None and not r.shared_project_id:
        return True
    return r.instance is not None and _out(r.instance).get("exists") is False


def database_words(r):
    o = _out(r.database)
    words = []
    if r.database is not None:
        if o.get("databaseExists") is False:
            words.append("database")
        users = [u for u in (o.get("users") or []) if isinstance(u, dict)]
        if any(u.get("user") is False for u in users):
            words.append("user")
        if any(u.get("client") is False or u.get("instanceUser") is False for u in users):
            words.append("roles")
    services = {s.get("component"): s for s in (_out(r.deploy).get("services") or [])
                if isinstance(s, dict)}
    if any("env" in (services.get(n, {}).get("differences") or [])
           for n in r.decl.database_names):
        words.append("settings")
    return words


def database_row(r, earlier):
    """`earlier`: the rows environment dev, apis, registry, ci identity and services."""
    missing = _out(r.deploy).get("missing") or []
    if (any(row[2] != NONE for row in earlier)
            or any(n in missing for n in r.decl.database_names)):
        return ("database", FOLLOWS_SERVICES, NONE)
    if too_long_users(r):
        return ("database", TOO_LONG, "fix by hand")
    if shared_platform_missing(r) or r.shared is None:
        return ("database", SHARED_PLATFORM, NONE)
    words = database_words(r)
    if any(w in words for w in ("database", "user", "roles")):
        return ("database", "missing: %s" % ", ".join(words), "create")
    if words == ["settings"]:
        return ("database", "differs: settings", "update")
    return ("database", "as declared", NONE)


def secrets_row(r):
    if r.secrets is not None:
        if r.secrets.get("status") == "unchanged":
            return ("ci secrets", "as declared", NONE)
        return ("ci secrets", "missing: %s" % ", ".join(_out(r.secrets).get("set") or []),
                "set")
    if identity_row(r)[2] != NONE:
        return ("ci secrets", "follows the ci identity", NONE)
    return ("ci secrets", "follows the registry", NONE)


def _environment_items(d):
    items = ["environment dev", "apis", "registry", "ci identity"]
    if d.components:
        items.append("services")
        if d.database_components:
            items.append("database")
        items.append("ci secrets")
    return items


def rows(r):
    """The items, in order: [(item, state, action)]. [] on failed."""
    if r.failure:
        return []
    d = r.decl
    out = [("repository", "exists", NONE) if r.exists else ("repository", "missing", "create")]
    if not r.exists:
        out += [("settings", FOLLOWS_CREATION, "update"),
                ("visibility", FOLLOWS_CREATION, NONE),
                ("declaration", FOLLOWS_CREATION, "send")]
        if d.components:
            out += [("components", FOLLOWS_CREATION, NONE), ("ci", FOLLOWS_CREATION, NONE)]
        out.append(("protection", FOLLOWS_CREATION, "create"))
        if d.environments:
            out += [(i, FOLLOWS_CREATION, NONE) for i in _environment_items(d)]
        return out

    decl = declaration_row(r)
    changing = decl[2] in ("merge it", "update", "fix the folder", "propose")
    if changing:
        out += [("settings", NOT_CHECKED_MERGE, NONE), ("visibility", NOT_CHECKED_MERGE, NONE)]
    else:
        out += [settings_row(r), visibility_row(r)]
    out.append(decl)
    if d.components:
        if decl[2] in ("merge it", "update", "fix the folder"):
            out += [("components", NOT_CHECKED_MERGE, NONE), ("ci", NOT_CHECKED_MERGE, NONE)]
        elif decl[2] == "send":
            out += [("components", NOT_CHECKED_SENT, NONE), ("ci", NOT_CHECKED_SENT, NONE)]
        else:
            out += [components_row(r), ci_row(r)]
    out.append(("protection", NOT_CHECKED_MERGE, NONE) if changing else protection_row(r))
    if not d.environments:
        return out

    items = _environment_items(d)
    if not counts_in_repository(r):
        return out + [(i, NOT_CHECKED_MERGE, NONE) for i in items]
    env = environment_row(r)
    if env[2] != NONE:
        return out + [env] + [(i, FOLLOWS_ENVIRONMENT, NONE) for i in items[1:]]
    apis = apis_row(r)
    if apis[2] != NONE:
        return out + [env, apis] + [(i, FOLLOWS_APIS, NONE) for i in items[2:]]
    env_rows = [env, apis, registry_row(r), identity_row(r)]
    if d.components:
        services = services_row(r)
        env_rows.append(services)
        if d.database_components:
            env_rows.append(database_row(r, list(env_rows)))
        env_rows.append(secrets_row(r))
    return out + env_rows


# ---------------------------------------------------------------------------
# Deciding: status, outputs, pending


def _row(items, name):
    for row in items:
        if row[0] == name:
            return row
    return None


def status(r, items):
    if r.failure:
        return "failed"
    actions = [a for _, _, a in items]
    database = _row(items, "database")
    shared = database is not None and database[1] == SHARED_PLATFORM
    if all(a == NONE for a in actions):
        return "pending" if shared else "unchanged"
    if _row(items, "repository")[2] == "create":
        return "would-create"
    if any(a in WRITE_ACTIONS for a in actions):
        return "would-update"
    return "pending"


def exposes(r, items):
    if r.failure:
        return False
    if r.decl.visibility != "public":
        return False
    if not r.exists:
        return True
    visibility = _row(items, "visibility")
    return visibility is not None and visibility[1] == "differs"


def instance_state(r):
    if r.database is None or _failed(r.database):
        return None
    return _out(r.database).get("instanceState")


def database_output(r, items):
    d = r.decl
    if r.failure or d is None or not d.database_components:
        return None
    state = instance_state(r)
    row = _row(items, "database")
    components = _row(items, "components")
    start = bool(state == "stopped" and row is not None and row[2] == "create"
                 and not (components is not None and components[1] == NEEDS_GO))
    return {"name": d.database, "instanceState": state, "start": start,
            "components": list(d.database_names)}


def ci_variables(r):
    if r.failure:
        return None
    variables = _out(r.identity).get("ciVariables")
    image = _out(r.registry).get("imagePath")
    if not isinstance(variables, dict) or not image:
        return None
    return {"GCP_PROJECT_ID": variables.get("GCP_PROJECT_ID"),
            "GCP_WIF_PROVIDER": variables.get("GCP_WIF_PROVIDER"),
            "GCP_CI_ACCOUNT": variables.get("GCP_CI_ACCOUNT"),
            "GCP_IMAGE_PATH": image}


def urls(r):
    if r.failure or r.deploy is None:
        return None
    by = {s.get("component"): s for s in (_out(r.deploy).get("services") or [])
          if isinstance(s, dict)}
    out = {}
    for n in r.decl.names:
        s = by.get(n)
        if s and s.get("exists") is True and s.get("url"):
            out[n] = s["url"]
    return out


def outputs(r, items):
    d = r.decl
    failed = r.failure is not None
    environment = None
    if d is not None and d.environments and not failed:
        pid = None
        if r.environment is not None and _out(r.environment).get("exists") is True:
            pid = _out(r.environment).get("projectId")
        environment = {"name": "dev", "projectId": pid}
    ci_ran = r.ci is not None and not _failed(r.ci)
    return {
        "project": d.name if d else None,
        "repository": d.full if d else None,
        "visibility": d.visibility if d else None,
        "exposes": exposes(r, items),
        "items": [{"item": i, "state": s, "action": a} for i, s, a in items],
        "generate": any(a == "generate" for _, _, a in items),
        "checks": "ci" if ci_expected(r) else "none",
        "changed": list(_out(r.pull_request).get("changed") or []) if (
            r.pull_request is not None and not _failed(r.pull_request)) else [],
        "environment": environment,
        "repositoryEnvironments": r.repository_environments,
        "repositoryDatabaseComponents": r.repository_database_components,
        "ciVariables": ci_variables(r),
        "urls": urls(r),
        "ciDeployComponents": sorted(r.deploy_list or []) if ci_ran else None,
        "defaultBranch": r.ci_default_branch if ci_ran else None,
        "database": database_output(r, items),
    }


def identity_how(r):
    """The ci identity's sentence, as a `how`: the cause and what the owner does."""
    parts = []
    for line in r.identity.get("answer") or []:
        line = line.strip()
        for tail in (", then run this again.", "."):
            if line.endswith(tail):
                line = line[:-len(tail)]
                break
        if line:
            parts.append(line)
    return "%s, then run /aleogr:project-plan again" % "; ".join(parts)


def registry_how(r, state):
    o = _out(r.registry)
    if state == "in another region":
        return OTHER_REGION_HOW % (r.decl.name, ", ".join(o.get("otherRegions") or []),
                                   r.decl.region)
    return NOT_DOCKER_HOW % (r.decl.name, r.decl.region, o.get("format"))


def _attention_item(result):
    for p in result.get("pending") or []:
        if isinstance(p, dict) and p.get("item") == "this folder needs attention":
            return p
    pending = result.get("pending") or []
    return pending[0] if pending else None


def pending(r, items):
    if r.failure:
        return [pending_item(r.failure.item, r.failure.how)]
    out = []

    def add(item):
        if item is not None and item not in out:
            out.append(item)
    decl = _row(items, "declaration")
    if decl[2] == "merge it":
        pr = _out(r.pull_request).get("openPullRequest") or {}
        add(pending_item("pull request #%s is open" % pr.get("number"),
                         "merge %s, then run /aleogr:project-apply confirm=yes" % pr.get("url")))
    if decl[2] == "fix the folder":
        if _out(r.checkout).get("state") == "needs-attention":
            add(_attention_item(r.checkout))
        else:
            add(_attention_item(r.pull_request))
    components = _row(items, "components")
    if components is not None and components[2] == "fix the folder":
        for _, res in r.go_setup:
            if res.get("status") == "pending":
                for p in res.get("pending") or []:
                    add(p)
    for c, res in r.go_setup:
        if c.get("database") is True and _out(res).get("route") == "manual":
            for p in res.get("pending") or []:
                if isinstance(p, dict) and p.get("item") == "route":
                    add(p)
    if components is not None and components[1] == NEEDS_GO:
        add(pending_item("go", GO_HOW))
    registry = _row(items, "registry")
    if registry is not None and registry[2] == "fix by hand":
        add(pending_item("registry", registry_how(r, registry[1])))
    identity = _row(items, "ci identity")
    if identity is not None and identity[2] == "fix by hand":
        add(pending_item("ci identity", identity_how(r)))
    services = _row(items, "services")
    if services is not None and services[2] == "prepare the login":
        add(pending_item("login", LOGIN_HOW))
    database = _row(items, "database")
    if database is not None and database[1] == TOO_LONG:
        for n, length in too_long_users(r):
            add(pending_item("database", TOO_LONG_HOW % (n, length)))
    if database is not None and database[1] == SHARED_PLATFORM:
        add(pending_item("database", SHARED_HOW % ", ".join(r.decl.database_names)))
    return out


def resources(r):
    if r.decl is not None and r.exists:
        return [{"type": "repository", "id": r.decl.full, "name": r.decl.repo_name}]
    return []


class Plan(object):
    """What the plan decided: the Reads it came from, the rows, the status, the outputs,
    the pending items and the resources. project-apply takes this object."""

    def __init__(self, reads, items, status, outputs, pending, resources):
        self.reads = reads
        self.items = items
        self.status = status
        self.outputs = outputs
        self.pending = pending
        self.resources = resources

    @property
    def failure(self):
        return self.reads.failure


def decide(r):
    items = rows(r)
    return Plan(r, items, status(r, items), outputs(r, items), pending(r, items),
                resources(r))


def plan(args, ctx, caller=None):
    """The whole plan, read and decided, not printed."""
    return decide(gather(args, caller or Caller(ctx)))


# ---------------------------------------------------------------------------
# Printing


def _lines_under(p):
    r = p.reads
    d = r.decl
    items = p.items
    row = (lambda name: _row(items, name))
    out = []
    visibility = row("visibility")
    if visibility[2] == "update":
        out.append("visibility: needs confirmVisibility=%s" % d.visibility)
    if p.outputs["exposes"]:
        out.append(EXPOSES_LINE)
    if row("protection")[1] == "not available on this plan":
        out.append(UNAVAILABLE_PUBLIC_LINE if (visibility[1] == "differs"
                                              and d.visibility == "public")
                   else UNAVAILABLE_LINE)
    decl = row("declaration")
    if decl[2] in ("merge it", "fix the folder"):
        how = [x for x in p.pending if x["item"].startswith("pull request #")
               or x["item"] == "this folder needs attention"]
        if how:
            out.append("%s: %s; project-apply stops until it is done."
                       % (_capital(how[0]["item"]), how[0]["how"]))
    components = row("components")
    if components is not None and components[2] == "fix the folder":
        for _, res in r.go_setup:
            if res.get("status") == "pending":
                for x in res.get("pending") or []:
                    out.append("%s: %s; project-apply stops until it is done."
                               % (x["item"], x["how"]))
    ci = row("ci")
    if (components is not None and components[2] == "generate") or (
            ci is not None and ci[2] == "generate"):
        out.append(GENERATE_LINE)
    if ci is not None and ci[2] == "generate" and d.environments:
        listed = r.deploy_list or []
        if listed:
            out.append("ci.yml is generated with the deploy jobs of dev for %s."
                       % ", ".join(listed))
        else:
            out.append("ci.yml is generated without deploy jobs.")
        later = [n for n in d.names if n not in listed]
        if later:
            out.append("The deploy job of %s comes once its service exists." % ", ".join(later))
    for name in ("registry", "ci identity"):
        x = row(name)
        if x is not None and x[2] == "fix by hand":
            how = [i for i in p.pending if i["item"] == name]
            if how:
                out.append("%s. The owner does this by hand: project-apply does not."
                           % _capital(how[0]["how"]))
    services = row("services")
    if services is not None and services[2] == "prepare the login":
        out.append(LOGIN_LINE)
    if services is not None and services[1].startswith("waiting for the first deploy: "):
        out.append(WAITING_LINE % services[1][len("waiting for the first deploy: "):])
    for c, res in r.go_setup:
        if c.get("database") is True and _out(res).get("route") == "manual":
            out.append(ROUTE_LINE % c["path"])
    database = row("database")
    state = instance_state(r)
    if database is not None:
        if database[1] == "as declared" and state in ("stopped", "starting", "creating"):
            out.append(NOT_READ_LINE % state)
        elif database[1] == "as declared" and state == "unknown":
            out.append(NOT_READ_UNKNOWN_LINE)
        if database[2] == "create":
            if state == "stopped" and components[1] != NEEDS_GO:
                out.append(START_LINE)
            elif state == "starting":
                out.append(STARTING_LINE)
            elif state == "creating":
                out.append(CREATING_LINE)
            elif state == "unknown":
                out.append(UNKNOWN_LINE)
        if database[1].startswith("follows "):
            out.append(BEFORE_START_LINE)
        if database[1] == "differs: settings":
            out.append(SETTINGS_ONLY_LINE)
    if components is not None and components[1] == NEEDS_GO:
        out.append(GO_LINE % ", ".join(modules_to_add(r)))
    if database is not None and database[1] == SHARED_PLATFORM:
        out.append(SHARED_PLATFORM_LINE % ", ".join(d.database_names))
    if database is not None and database[1] == TOO_LONG:
        for n, length in too_long_users(r):
            out.append(TOO_LONG_LINE % (n, length))
    secrets = row("ci secrets")
    if secrets is not None and secrets[2] == "set":
        out.append(SECRETS_LINE)
    return out


def _last_line(p):
    items = p.items
    database = _row(items, "database")
    acting = [row for row in items if row[2] != NONE]
    if not acting:
        if database is not None and database[1] == SHARED_PLATFORM:
            return NOTHING_FOR_DATABASE
        return NOTHING_TO_DO
    owners = [row for row in acting if row[2] in OWNER_ACTIONS]
    made = len(acting) - len(owners)
    n = len(acting)
    head = "%d item%s %s an action other than none" % (n, "" if n == 1 else "s",
                                                     "has" if n == 1 else "have")
    if not owners:
        return "%s: project-apply makes %s." % (head, "it" if n == 1 else "them")
    owned = ", ".join(row[0] for row in owners)
    if not made:
        return "%s: %s the owner's to do (%s), not project-apply's." % (
            head, "it is" if n == 1 else "they are", owned)
    return ("%s: project-apply makes %d of them, and %d %s the owner's to do (%s)."
            % (head, made, len(owners), "is" if len(owners) == 1 else "are", owned))


def answer_lines(p):
    if p.failure:
        return [p.failure.sentence]
    table = [(i, s, a) for i, s, a in p.items]
    lines = aleogr_common.render_table(["Item", "State", "Action"], table)
    under = _lines_under(p)
    if under:
        lines += [""] + under
    lines += ["", _last_line(p)]
    return lines


def run(args, ctx):
    p = plan(args, ctx)
    return ctx.result(p.status, p.outputs, resources=p.resources, pending=p.pending,
                      cost=dict(COST), lines=answer_lines(p))
