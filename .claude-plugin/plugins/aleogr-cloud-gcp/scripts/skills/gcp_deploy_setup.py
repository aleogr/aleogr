"""gcp_deploy-setup: each component of a project as a Cloud Run service as declared,
behind the login (IAP), never public, with the CI account allowed to replace its image.

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_deploy_setup.py) and its scenarios. It was built from
skills/gcp_deploy-setup/SKILL.md as that text was before the skill became a shell over
this command (the text is in the repository's history, at the commit before that
change): the same reads, in the same order (step 1 the project number, step 2 the active
account, step 3 four reads per component), the same words of difference, the same
commands in the same order (step 5 the security pass over every existing service first,
step 6 a to g per component), the same poll of the binding on a new account, the same
reads again (step 7), the same status (step 8) and the same result block.

Nothing is ever made public: the only removes are of allUsers and allAuthenticatedUsers,
the only deploy carries --no-allow-unauthenticated --iap, and every write goes through
ctx.write, whose allowlist pins each command's shape. The answer and the block hold no
setting's value; the block holds no e-mail.
"""

import json
import re

import aleogr_common as common  # noqa: E402  (scripts/ is on sys.path)

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "deploy-setup"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply creates and repairs services, through ctx.write only

REQUIRED = ("projectId", "project", "environment", "region", "components", "maxInstances",
            "cpu", "memory", "ciAccount", "placeholderImage")
COST = {"fixed": False, "notes": "minimum 0 instances and billing by request: a service "
                                 "costs only while it answers requests"}
COST_LINE = ("There is no fixed cost: with a minimum of 0 instances and billing by request, "
             "a service costs only while it answers requests.")

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_PROJECT = re.compile(r"^[a-z](?:[a-z0-9-]{0,12}[a-z0-9])?$")
_REGION = re.compile(r"^[a-z]+(?:-[a-z]+)+[0-9]+$")
_COMPONENT = re.compile(r"^[a-z](?:[a-z0-9-]{0,18}[a-z0-9])?$")
_MAX_INSTANCES = re.compile(r"^(?:[1-9]|10)$")
_ACCOUNT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ENV_VALUE = re.compile(r"^[A-Za-z0-9._:@-]{1,200}$")
# The argument placeholderImage: Google's hello sample, an optional tag or digest.
_PLACEHOLDER_ARG = re.compile("^" + common.PLACEHOLDER_IMAGE_RE + "$")
# Whether a service still runs the placeholder: the rule of gcp_deploy-describe.
_PLACEHOLDER = re.compile(r"^us-docker\.pkg\.dev/cloudrun/container/hello"
                          r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]*|@sha256:[0-9a-f]+)?$")

OPEN_MEMBERS = ("allUsers", "allAuthenticatedUsers")
WORDS = ("account", "scaling", "size", "public", "open", "login", "agent", "ci", "labels",
         "env")
SA_USER = "roles/iam.serviceAccountUser"
DEVELOPER = "roles/run.developer"
INVOKER = "roles/run.invoker"
ACCESSOR = "roles/iap.httpsResourceAccessor"
MAX_TRIES = 10  # the poll of 6b: at most 10 tries, so at most 9 waits

# The sentences of the SKILL.md, word for word.
PROJECT_UNREADABLE = ("The GCP project %s could not be read. Check that it exists and that "
                      "the active gcloud account may read it.")
ACCOUNT_UNREADABLE = "The active gcloud account could not be read. Run gcloud auth login."
READ_FAILED = ("The service %s or its access could not be read; nothing was changed. Check "
               "that the Cloud Run and IAP APIs are enabled in %s and that the active gcloud "
               "account may read its services and their access.")
STILL_OPEN_LOGIN = ("The service %s is still open: anyone on the internet who signs in with "
                    "any Google account gets through its login.")
STILL_NO_LOGIN = "The service %s is still without the login."
RUN_AGAIN_NOW = "Run this same skill again as soon as possible."
ACCOUNT_FAILED = "The account %s could not be created."
ACT_AS_FAILED = "The CI account could not be allowed to act as the account %s."
CREATE_FAILED = "The service %s could not be created."
CREATE_FOUND = ("The command that creates the service %s failed, but the service exists; "
                "this run went on to set it up as declared.")
CREATE_UNREADABLE = ("The command that creates the service %s failed and the service could "
                     "not be read: it may exist. Run this same skill again to check and repair "
                     "it.")
REPAIR_FAILED = "The settings of the service %s could not be changed."
AGENT_FAILED = "The login's agent could not be allowed to call the service %s."
CI_FAILED = "The CI account could not be given the deploy role on the service %s."
ACCESS_FAILED = ("The active gcloud account could not be given access to the service %s "
                 "through the login.")
ENV_FAILED = "The environment settings %s of the service %s could not be set."
ACCESS_ITEM = {"item": "access", "reason": "manual",
               "how": "/aleogr:project-access person=<e-mail>"}
HOW = "Run gcp_deploy-setup again with the same arguments and mode=apply."
REASON_READ = "The service could not be read after the change."

# Sentences the SKILL.md leaves free (one fixed wording each).
STILL_OPEN_CALL = "The service %s is still open: anyone on the internet may call it."
REFUSED_TRIES = "The binding was refused after %s."
REREAD_FAILED = ("The access policy of the service %s could not be read again after its "
                 "login was turned on.")
ME_UNUSABLE = ("The active gcloud account is not one this tooling can give access through "
               "the login; nothing was changed.")
REMOVE_UNUSABLE = ("The access of the service %s holds a role this tooling cannot remove a "
                   "member from; nothing was changed. Remove allUsers and allAuthenticatedUsers "
                   "from it by hand, then run this again.")
NUMBER_UNUSABLE = ("The project number of %s is not one this tooling can use; nothing was "
                   "changed.")
REASON_STOPPED = "This run stopped before this work was done."
REASON_FAILED = "A command of this work failed, and this run stopped there."
REASON_MISSING = "The service is still missing after the change."
REASON_DIFFERS = "The service still differs from the declaration after the change."
_PASS_DONE = {
    "open": "The login of the service %s no longer lets %s in.",
    "public": "The access policy of the service %s no longer lists %s.",
    "login": "The login of the service %s was turned on.",
    "invoker": "The invoker check of the service %s was turned back on.",
}


def _unquote(v):
    if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
        return v[1:-1]
    return v


# ---------------------------------------------------------------------------
# Validation


def _parse_env(env, components):
    """(settings, problems): settings is {component: [(NAME, value), ...]} in env's order."""
    settings = {}
    problems = []
    seen = set()
    for n, entry in enumerate(env.split(";"), 1):
        component, colon, rest = entry.partition(":")
        name, eq, value = rest.partition("=")
        if not colon or not eq:
            problems.append("env entry %d must be <component>:<NAME>=<value>." % n)
            continue
        if not _ENV_NAME.match(name):
            problems.append("env entry %d has a name that is not 1 to 64 characters of A-Z, "
                            "0-9 and _, starting with a letter." % n)
            continue
        if component not in components:
            problems.append("env setting %s names %s, which is not one of components."
                            % (name, component))
            continue
        if not _ENV_VALUE.match(value):
            problems.append("env setting %s:%s must have a value of 1 to 200 characters of "
                            "a-z, A-Z, 0-9, -, _, ., : and @." % (component, name))
            continue
        if (component, name) in seen:
            problems.append("env setting %s:%s is given twice." % (component, name))
            continue
        seen.add((component, name))
        settings.setdefault(component, []).append((name, value))
    return settings, problems


def validate(args):
    """(problems, components, settings): one sentence per argument missing or rule broken,
    in the order of the SKILL.md's list."""
    problems = []
    for key in REQUIRED:
        if not args.get(key):
            problems.append("%s is missing." % key)
    project_id = args.get("projectId") or ""
    project = args.get("project") or ""
    if project_id and not _PROJECT_ID.match(project_id):
        problems.append("projectId is not a GCP project id.")
    project_ok = bool(_PROJECT.match(project))
    if project and not project_ok:
        problems.append("project must have 1 to 14 lowercase letters, digits and hyphens, "
                        "starting with a letter and not ending with a hyphen.")
    environment = args.get("environment")
    if environment and environment not in ("dev", "hom", "prd"):
        problems.append("environment must be dev, hom or prd.")
    region = args.get("region") or ""
    if region and not _REGION.match(region):
        problems.append("region is not a Google Cloud region name (such as us-central1).")
    components = []
    raw = args.get("components") or ""
    if raw:
        names = raw.split(",")
        if any(name == "" for name in names):
            problems.append("components must be names separated by , with no empty name.")
        seen = set()
        twice = []
        for name in names:
            if name == "":
                continue
            if not _COMPONENT.match(name):
                problems.append("component %s must have 1 to 20 lowercase letters, digits and "
                                "hyphens, starting with a letter and not ending with a hyphen."
                                % name)
                continue
            if name in seen:
                if name not in twice:
                    twice.append(name)
                    problems.append("component %s is given twice." % name)
                continue
            seen.add(name)
            components.append(name)
        if project_ok:
            for name in components:
                service = "%s-%s" % (project, name)
                if not 6 <= len(service) <= 30:
                    problems.append("%s has %d characters: a service's name, which is also "
                                    "its account's, must have 6 to 30." % (service, len(service)))
    if args.get("maxInstances") and not _MAX_INSTANCES.match(args["maxInstances"]):
        problems.append("maxInstances must be a whole number from 1 to 10.")
    if args.get("cpu") and args["cpu"] not in ("1", "2"):
        problems.append("cpu must be 1 or 2.")
    if args.get("memory") and args["memory"] not in ("512Mi", "1Gi", "2Gi"):
        problems.append("memory must be 512Mi, 1Gi or 2Gi.")
    ci = args.get("ciAccount") or ""
    if ci and project_id:
        local, at, domain = ci.partition("@")
        if not (at and _ACCOUNT_ID.match(local)
                and domain == "%s.iam.gserviceaccount.com" % project_id):
            problems.append("ciAccount must be a service account of the project %s "
                            "(<id>@%s.iam.gserviceaccount.com)." % (project_id, project_id))
    image = args.get("placeholderImage") or ""
    if image and not _PLACEHOLDER_ARG.match(image):
        problems.append("placeholderImage must be Google's hello sample, "
                        "us-docker.pkg.dev/cloudrun/container/hello, with an optional :tag or "
                        "@sha256 digest.")
    mode = args.get("mode")
    if mode is not None and mode not in ("plan", "apply"):
        problems.append("mode must be plan or apply.")
    settings = {}
    if args.get("env") is not None:
        settings, env_problems = _parse_env(_unquote(args["env"]), components)
        problems.extend(env_problems)
    return problems, components, settings


# ---------------------------------------------------------------------------
# Reading


def _json_object(text):
    """The JSON object of a read; {} for an empty output; None when it is not JSON."""
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _get(obj, *path):
    for key in path:
        if isinstance(key, int):
            if not isinstance(obj, list) or len(obj) <= key:
                return None
            obj = obj[key]
        else:
            if not isinstance(obj, dict):
                return None
            obj = obj.get(key)
    return obj


def _dict(v):
    return v if isinstance(v, dict) else {}


def _bindings(policy):
    b = policy.get("bindings") if isinstance(policy, dict) else None
    return [x for x in b if isinstance(x, dict)] if isinstance(b, list) else []


def _members(binding):
    m = binding.get("members")
    return [x for x in m if isinstance(x, str)] if isinstance(m, list) else []


def _open_members(policy):
    """(member, role) for each allUsers or allAuthenticatedUsers of each binding."""
    return [(m, b.get("role")) for b in _bindings(policy) for m in _members(b)
            if m in OPEN_MEMBERS]


def _granted(policy, role, member):
    """A binding of `role` without a condition lists `member`."""
    return any(b.get("role") == role and not b.get("condition") and member in _members(b)
               for b in _bindings(policy))


def _cpu(v):
    if v is None:
        return None
    s = str(v).strip()
    try:
        if s.endswith("m"):
            return float(s[:-1]) / 1000
        return float(s)
    except ValueError:
        return None


def _memory_mi(v):
    if not isinstance(v, str):
        return None
    m = re.match(r"^([0-9]+)(Mi|Gi)$", v.strip())
    if not m:
        return None
    return int(m.group(1)) * (1024 if m.group(2) == "Gi" else 1)


def _zero_or_absent(v):
    return v is None or str(v).strip() == "0"


def _true(v):
    return v is not None and str(v).strip().lower() == "true"


def _missing_text(c):
    return "Cannot find service" in c.text or "NOT_FOUND" in c.text or \
        "could not be found" in c.text


class Component(object):
    """One component: its names, what the last read found, and what this run did."""

    def __init__(self, name, args, settings):
        self.name = name
        self.service = "%s-%s" % (args["project"], name)
        self.account = "%s@%s.iam.gserviceaccount.com" % (self.service, args["projectId"])
        self.settings = settings.get(name, [])
        self.svc = None  # the service's JSON object; None: it does not exist
        self.policy = None  # the service's policy (read only when the service exists)
        self.account_policy = None  # None: the account does not exist
        self.login_policy = None  # the login policy (read only when the service exists)
        self.start = None  # the analysis of step 3
        # What this run did.
        self.touched = False  # a command of 5 or 6 ran on it
        self.changed = False  # a command of 5 or 6 exited 0 on it
        self.created_account = False
        self.created_service = False  # by 6c, or found after a failed 6c
        self.exists_now = False  # created by 6c with exit 0 (not read since)
        self.done = False  # its work of 6 ran to its end
        self.f_tried = False
        self.env_set = None
        self.verify_failed = False
        self.still_open_login = False
        self.still_open_call = False
        self.still_no_login = False
        self.reread_failed = False
        self.failed_here = False  # a command of 5 or 6 failed on it


def read_component(ctx, c, args):
    """The four reads of step 3, each alone; True when they hold, False on a failure.
    The component's state changes only when every read held."""
    pid, region = args["projectId"], args["region"]
    r = ctx.read(["gcloud", "run", "services", "describe", c.service, "--project=%s" % pid,
                  "--region=%s" % region, "--format=json"])
    if r.ok:
        svc = _json_object(r.out)
        if svc is None:
            return False
    elif _missing_text(r):
        svc = None
    else:
        return False
    policy = None
    if svc is not None:
        policy = read_policy(ctx, c, args)
        if policy is None:
            return False
    r = ctx.read(["gcloud", "iam", "service-accounts", "get-iam-policy", c.account,
                  "--project=%s" % pid, "--format=json"])
    if r.ok:
        account_policy = _json_object(r.out)
        if account_policy is None:
            return False
    elif "NOT_FOUND" in r.text or "does not exist" in r.text:
        account_policy = None
    else:
        return False
    login_policy = None
    if svc is not None:
        r = ctx.read(["gcloud", "iap", "web", "get-iam-policy", "--resource-type=cloud-run",
                      "--service=%s" % c.service, "--region=%s" % region,
                      "--project=%s" % pid, "--format=json"])
        login_policy = _json_object(r.out) if r.ok else None
        if login_policy is None:
            return False
    c.svc, c.policy, c.account_policy, c.login_policy = svc, policy, account_policy, login_policy
    c.exists_now = False
    return True


def read_policy(ctx, c, args):
    """The second read of step 3 alone: the service's policy, or None."""
    r = ctx.read(["gcloud", "run", "services", "get-iam-policy", c.service,
                  "--project=%s" % args["projectId"], "--region=%s" % args["region"],
                  "--format=json"])
    return _json_object(r.out) if r.ok else None


def describe_service(ctx, c, args):
    """The first read of step 3 alone: (state, svc), state "exists", "missing" or
    "failed"."""
    r = ctx.read(["gcloud", "run", "services", "describe", c.service,
                  "--project=%s" % args["projectId"], "--region=%s" % args["region"],
                  "--format=json"])
    if r.ok:
        svc = _json_object(r.out)
        return ("failed", None) if svc is None else ("exists", svc)
    return ("missing", None) if _missing_text(r) else ("failed", None)


# ---------------------------------------------------------------------------
# What a read means ("As declared")


class Analysis(object):
    pass


def analyze(c, args, info):
    """The words that differ, in the table's order, and the other fields of a service
    that exists (None for one that does not)."""
    if c.svc is None:
        return None
    svc = c.svc
    a = Analysis()
    meta = _dict(_get(svc, "metadata", "annotations"))
    tmeta = _dict(_get(svc, "spec", "template", "metadata", "annotations"))
    container = _dict(_get(svc, "spec", "template", "spec", "containers", 0))
    limits = _dict(_get(container, "resources", "limits"))
    ci_member = "serviceAccount:%s" % args["ciAccount"]
    words = set()

    a.account_name_differs = (_get(svc, "spec", "template", "spec", "serviceAccountName")
                              != c.account)
    if a.account_name_differs or c.account_policy is None:
        words.add("account")
    a.manual = meta.get("run.googleapis.com/scalingMode") == "manual"
    a.template_min = not _zero_or_absent(tmeta.get("autoscaling.knative.dev/minScale"))
    if (meta.get("run.googleapis.com/maxScale") != args["maxInstances"]
            or not _zero_or_absent(meta.get("run.googleapis.com/minScale"))
            or a.manual or a.template_min):
        words.add("scaling")
    throttling = tmeta.get("run.googleapis.com/cpu-throttling")
    a.cpu_differs = _cpu(limits.get("cpu")) != float(args["cpu"])
    a.memory_differs = _memory_mi(limits.get("memory")) != _memory_mi(args["memory"])
    a.throttling_differs = not (throttling is None or _true(throttling))
    if a.cpu_differs or a.memory_differs or a.throttling_differs:
        words.add("size")
    a.invoker_disabled = _true(meta.get("run.googleapis.com/invoker-iam-disabled"))
    a.public_members = _open_members(c.policy)
    if a.public_members or a.invoker_disabled:
        words.add("public")
    a.open_members = _open_members(c.login_policy)
    if a.open_members:
        words.add("open")
    a.login_off = meta.get("run.googleapis.com/iap-enabled") != "true"
    if a.login_off:
        words.add("login")
    a.agent_missing = not _granted(c.policy, INVOKER, info["agent"])
    if a.agent_missing:
        words.add("agent")
    a.ci_service_missing = not _granted(c.policy, DEVELOPER, ci_member)
    if (a.ci_service_missing or c.account_policy is None
            or not _granted(c.account_policy, SA_USER, ci_member)):
        words.add("ci")
    labels = _dict(_get(svc, "metadata", "labels"))
    if (labels.get("aleogr-project") != args["project"]
            or labels.get("aleogr-environment") != args["environment"]
            or labels.get("aleogr-component") != c.name):
        words.add("labels")
    items = container.get("env")
    items = [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []
    a.env_to_set = []
    for name, value in c.settings:
        held = [x for x in items if x.get("name") == name]
        if not held or not any(x.get("value") == value for x in held):
            a.env_to_set.append((name, value))
    if a.env_to_set:
        words.add("env")
    a.words = [w for w in WORDS if w in words]
    image = _get(container, "image")
    a.placeholder = isinstance(image, str) and bool(_PLACEHOLDER.match(image))
    url = _get(svc, "status", "url")
    a.url = url if isinstance(url, str) and url else None
    me = info["me"].lower()
    a.access = any(b.get("role") == ACCESSOR and any(m.lower() == me for m in _members(b))
                   for b in _bindings(c.login_policy))
    held = {}
    for key in ("aleogr-project", "aleogr-environment", "aleogr-component"):
        if key in labels:
            held[key] = labels[key]
    a.labels = held
    return a


def has_work(c, a):
    """A component's work, as step 3 defines it."""
    if c.account_policy is None or a is None:
        return True
    return bool(a.words) or not a.access


# ---------------------------------------------------------------------------
# The commands (each exactly as the SKILL.md writes it; a double-quoted value is one
# argument without its quotes)


def _tail(args):
    return ["--region=%s" % args["region"], "--project=%s" % args["projectId"], "--quiet"]


def iap_remove_command(c, args, member, role):
    return ["gcloud", "iap", "web", "remove-iam-policy-binding", "--resource-type=cloud-run",
            "--service=%s" % c.service, "--region=%s" % args["region"],
            "--project=%s" % args["projectId"], "--member=%s" % member, "--role=%s" % role,
            "--all", "--quiet"]


def run_remove_command(c, args, member, role):
    return ["gcloud", "run", "services", "remove-iam-policy-binding", c.service,
            "--member=%s" % member, "--role=%s" % role, "--region=%s" % args["region"],
            "--project=%s" % args["projectId"], "--all", "--quiet"]


def login_command(c, args):
    return ["gcloud", "run", "services", "update", c.service, "--iap"] + _tail(args)


def invoker_command(c, args):
    return ["gcloud", "run", "services", "update", c.service, "--invoker-iam-check"] + \
        _tail(args)


def account_command(c, args):
    return ["gcloud", "iam", "service-accounts", "create", c.service,
            "--project=%s" % args["projectId"],
            "--display-name=%s %s" % (args["project"], c.name), "--quiet"]


def act_as_command(c, args):
    return ["gcloud", "iam", "service-accounts", "add-iam-policy-binding", c.account,
            "--member=serviceAccount:%s" % args["ciAccount"], "--role=%s" % SA_USER,
            "--project=%s" % args["projectId"], "--condition=None", "--quiet"]


def labels_text(c, args):
    return "aleogr-project=%s,aleogr-environment=%s,aleogr-component=%s" % (
        args["project"], args["environment"], c.name)


def deploy_command(c, args):
    return ["gcloud", "run", "deploy", c.service, "--image=%s" % args["placeholderImage"],
            "--no-allow-unauthenticated", "--iap", "--service-account=%s" % c.account,
            "--min=0", "--max=%s" % args["maxInstances"], "--cpu=%s" % args["cpu"],
            "--memory=%s" % args["memory"], "--cpu-throttling",
            "--labels=%s" % labels_text(c, args)] + _tail(args)


def repair_flags(c, a, args):
    """The flags of 6d1: only those of what differs, in the SKILL.md's order."""
    flags = []
    if a.account_name_differs:
        flags.append("--service-account=%s" % c.account)
    if "scaling" in a.words:
        flags += ["--min=0", "--max=%s" % args["maxInstances"]]
        if a.manual:
            flags.append("--scaling=auto")
        if a.template_min:
            flags.append("--min-instances=default")
    if a.cpu_differs:
        flags.append("--cpu=%s" % args["cpu"])
    if a.memory_differs:
        flags.append("--memory=%s" % args["memory"])
    if a.throttling_differs:
        flags.append("--cpu-throttling")
    if "labels" in a.words:
        flags.append("--update-labels=%s" % labels_text(c, args))
    return flags


def repair_command(c, args, flags):
    return ["gcloud", "run", "services", "update", c.service] + flags + _tail(args)


def agent_command(c, args, info):
    return ["gcloud", "run", "services", "add-iam-policy-binding", c.service,
            "--member=%s" % info["agent"], "--role=%s" % INVOKER,
            "--region=%s" % args["region"], "--project=%s" % args["projectId"],
            "--condition=None", "--quiet"]


def ci_command(c, args):
    return ["gcloud", "run", "services", "add-iam-policy-binding", c.service,
            "--member=serviceAccount:%s" % args["ciAccount"], "--role=%s" % DEVELOPER,
            "--region=%s" % args["region"], "--project=%s" % args["projectId"],
            "--condition=None", "--quiet"]


def access_command(c, args, info):
    return ["gcloud", "iap", "web", "add-iam-policy-binding", "--resource-type=cloud-run",
            "--service=%s" % c.service, "--region=%s" % args["region"],
            "--project=%s" % args["projectId"], "--member=%s" % info["me"],
            "--role=%s" % ACCESSOR, "--condition=None", "--quiet"]


def env_command(c, args, settings):
    text = "^##^" + "##".join("%s=%s" % (n, v) for n, v in settings)
    return ["gcloud", "run", "services", "update", c.service,
            "--update-env-vars=%s" % text] + _tail(args)


# ---------------------------------------------------------------------------
# The check before any write, in both modes: a value read from Google Cloud (the active
# account, a role of a binding, the project number) that no write of this skill would
# take ends the run before anything is changed, so a plan never announces a write the
# apply would refuse.


def unusable(ctx, comps, analyses, args, info):
    skill = ctx.skill
    if common.write_refusal(skill, agent_command(comps[0], args, info), root=ctx.root):
        return NUMBER_UNUSABLE % args["projectId"]
    if any(has_work(c, analyses[c.name]) for c in comps) and \
            common.write_refusal(skill, access_command(comps[0], args, info), root=ctx.root):
        return ME_UNUSABLE
    for c in comps:
        a = analyses[c.name]
        if a is None:
            continue
        for member, role in a.open_members:
            if common.write_refusal(skill, iap_remove_command(c, args, member, str(role)),
                                    root=ctx.root):
                return REMOVE_UNUSABLE % c.service
        for member, role in a.public_members:
            if common.write_refusal(skill, run_remove_command(c, args, member, str(role)),
                                    root=ctx.root):
                return REMOVE_UNUSABLE % c.service
    return None


# ---------------------------------------------------------------------------
# The result


def _empty_outputs(args):
    o = {"services": [], "missing": [], "differing": [], "waiting": [], "urls": {},
         "created": [], "updated": []}
    if args.get("env") is not None:
        o["envSet"] = {}
    return o


def service_item(c, a):
    if a is None:
        return {"component": c.name, "exists": False, "asDeclared": False, "differences": [],
                "placeholder": False, "url": None}
    return {"component": c.name, "exists": True, "asDeclared": not a.words,
            "differences": a.words, "placeholder": a.placeholder, "url": a.url}


def build_outputs(comps, analyses, args, created=(), updated=(), env_set=None):
    o = _empty_outputs(args)
    resources = []
    for c in comps:
        a = analyses[c.name]
        o["services"].append(service_item(c, a))
        if a is None:
            o["missing"].append(c.name)
            continue
        if a.words:
            o["differing"].append(c.name)
        elif a.placeholder:
            o["waiting"].append(c.name)
        if a.url:
            o["urls"][c.name] = a.url
        resources.append({"type": "run-service",
                          "id": "%s/%s/%s" % (args["projectId"], args["region"], c.service),
                          "name": c.service, "labels": a.labels})
    o["created"] = list(created)
    o["updated"] = list(updated)
    if "envSet" in o and env_set:
        o["envSet"] = env_set
    return o, resources


# ---------------------------------------------------------------------------
# Step 4: the plan


def plan(ctx, comps, analyses, args):
    lines = []
    status = "unchanged"
    if any(analyses[c.name] is None for c in comps):
        lines.append(COST_LINE)
    for c in comps:
        a = analyses[c.name]
        if c.account_policy is None:
            lines.append("The account %s does not exist: it would be created." % c.account)
            status = "would-create"
        else:
            lines.append("The account %s exists." % c.account)
        if a is None:
            status = "would-create"
            lines.append("The service %s does not exist: it would be created behind the login, "
                         "with the placeholder image." % c.service)
            to_set = [n for n, _ in c.settings]
            access = False
        else:
            where = " (%s)" % a.url if a.url else ""
            if a.words:
                lines.append("The service %s%s differs: %s." % (c.service, where,
                                                                ", ".join(a.words)))
                if "open" in a.words:
                    lines.append("Anyone on the internet who signs in with any Google account "
                                 "gets through its login.")
            else:
                lines.append("The service %s%s is as declared." % (c.service, where))
            to_set = [n for n, _ in a.env_to_set]
            access = a.access
        if to_set:
            lines.append("Its settings %s would be set." % ", ".join(to_set))
        if access:
            lines.append("The active gcloud account already gets in to it through the login.")
        else:
            lines.append("The active gcloud account would be given access to it through the "
                         "login.")
        if a is not None and a.placeholder:
            lines.append("It still runs the placeholder image: the first deploy of CI replaces "
                         "it.")
        if status == "unchanged" and has_work(c, a):
            status = "would-update"
    lines.append("This plan changed nothing.")
    outputs, resources = build_outputs(comps, analyses, args)
    return ctx.result(status, outputs, resources=resources, cost=dict(COST), lines=lines)


# ---------------------------------------------------------------------------
# Steps 5 to 8: the apply


ABORT_LINE = ("Services or service accounts may have been created by this run; running this "
              "skill again with the same arguments goes on from them.")


class Run(object):
    def __init__(self, ctx, args, info):
        self.ctx = ctx
        self.args = args
        self.info = info
        self.events = []  # the sentences of failures and found services, in order
        self.pass_done = []  # what the security pass changed
        self.pass_failed = False
        self.stopped = False
        self.any_command = False
        self.any_change = False
        self.any_created = False
        self.access_refused = False
        self.deployed = False

    def write(self, c, argv):
        """One write on component c: True when it exited 0."""
        c.touched = True
        first = not self.any_command
        self.any_command = True
        r = self.ctx.write(argv)
        if first:
            # From the first write on, a run aborted by its time limit or an unexpected
            # error says what it may have left behind.
            self.ctx.on_abort([ABORT_LINE])
        if r.ok:
            c.changed = True
            self.any_change = True
        return r

    def stop(self, c, sentence):
        self.events.append(sentence)
        self.stopped = True
        c.failed_here = True


def security_pass(run, c, a, with_open):
    """Step 5 for one service; True when one of its commands failed. A failure does not
    skip any other command of the pass."""
    args = run.args
    failed = False
    if with_open:
        for member, role in a.open_members:
            if run.write(c, iap_remove_command(c, args, member, role)).ok:
                run.pass_done.append(_PASS_DONE["open"] % (c.service, member))
            else:
                c.still_open_login = True
                failed = True
    for member, role in a.public_members:
        if run.write(c, run_remove_command(c, args, member, role)).ok:
            run.pass_done.append(_PASS_DONE["public"] % (c.service, member))
        else:
            c.still_open_call = True
            failed = True
    if a.login_off:
        if run.write(c, login_command(c, args)).ok:
            run.pass_done.append(_PASS_DONE["login"] % c.service)
            # Turning the login on binds the login's agent itself: read the policy again.
            policy = read_policy(run.ctx, c, args)
            if policy is None:
                c.reread_failed = True
            else:
                c.policy = policy
        else:
            c.still_no_login = True
            failed = True
    if a.invoker_disabled:
        if run.write(c, invoker_command(c, args)).ok:
            run.pass_done.append(_PASS_DONE["invoker"] % c.service)
        else:
            c.still_open_call = True
            failed = True
    if failed:
        c.failed_here = True
    return failed


def poll_act_as(run, c):
    """6b: (ok, tries, budget spent). Polled only on an account this run created."""
    argv = act_as_command(c, run.args)
    count = 0
    while True:
        count += 1
        r = run.write(c, argv)
        if r.ok:
            return True, count, False
        if not c.created_account or not ("does not exist" in r.text or "NOT_FOUND" in r.text):
            return False, count, False
        if count >= MAX_TRIES:
            return False, count, False
        if not run.ctx.wait():
            # A wait that cannot be run ends the poll as the tenth refusal does.
            return False, count, True


def _tries(count):
    return "%d %s" % (count, "try" if count == 1 else "tries")


def component_work(run, c, args, info):
    """Step 6, a to g, for one component."""
    ctx = run.ctx
    ci_member = "serviceAccount:%s" % args["ciAccount"]

    # a. The account.
    if c.account_policy is None:
        r = run.write(c, account_command(c, args))
        if r.ok:
            c.created_account = True
            run.any_created = True
        elif "already exists" not in r.text:
            run.stop(c, ACCOUNT_FAILED % c.account)
            return
        c.account_policy = {}

    # b. The CI binding on the account.
    if not _granted(c.account_policy, SA_USER, ci_member):
        ok, count, budget = poll_act_as(run, c)
        if not ok:
            run.stop(c, ACT_AS_FAILED % c.account)
            run.events.append(REFUSED_TRIES % _tries(count))
            if budget:
                run.events.append(common.WAIT_BUDGET_SENTENCE)
            return
        c.account_policy = {"bindings": [{"role": SA_USER, "members": [ci_member]}]}

    # c. The service.
    new = False  # created by the deploy with exit 0
    if c.svc is None:
        run.deployed = True
        r = run.write(c, deploy_command(c, args))
        if r.ok:
            new = True
            c.created_service = True
            c.exists_now = True
            run.any_created = True
        else:
            state, svc = describe_service(ctx, c, args)
            if state == "missing":
                run.stop(c, CREATE_FAILED % c.service)
                return
            policy = read_policy(ctx, c, args) if state == "exists" else None
            if policy is None:
                run.stop(c, CREATE_UNREADABLE % c.service)
                return
            c.svc, c.policy, c.login_policy = svc, policy, {}
            c.created_service = True
            run.any_created = True
            run.events.append(CREATE_FOUND % c.service)
            if security_pass(run, c, analyze(c, args, info), with_open=False):
                run.pass_failed = True
                run.stopped = True
                c.failed_here = True
                return
            if c.reread_failed:
                run.stop(c, REREAD_FAILED % c.service)
                return

    # d. The rest of a service that exists and differs.
    if not new:
        a = analyze(c, args, info)
        flags = repair_flags(c, a, args)
        if flags:
            if not run.write(c, repair_command(c, args, flags)).ok:
                run.stop(c, REPAIR_FAILED % c.service)
                return
        if a.agent_missing:
            if not run.write(c, agent_command(c, args, info)).ok:
                run.stop(c, AGENT_FAILED % c.service)
                return
        ci_missing = a.ci_service_missing
        access = a.access
        env_to_set = a.env_to_set
    else:
        ci_missing, access, env_to_set = True, False, list(c.settings)
    if c.created_service:
        access = False
        env_to_set = list(c.settings)

    # e. The CI binding on the service.
    if ci_missing:
        if not run.write(c, ci_command(c, args)).ok:
            run.stop(c, CI_FAILED % c.service)
            return

    # f. The access of the active account; a refusal does not stop the run. "Go on with
    # the next component" was written when f was the last part of step 6; g, added after
    # it, runs "after every other command of a to f" on conditions that do not include the
    # access, and a refused grant is not one of the stops of step 6: every other piece of
    # work stands, so the component's settings are still set (g) before the next one.
    if not access:
        c.f_tried = True
        if not run.write(c, access_command(c, args, info)).ok:
            run.events.append(ACCESS_FAILED % c.service)
            run.access_refused = True

    # g. The settings, last, alone.
    if env_to_set:
        if not run.write(c, env_command(c, args, env_to_set)).ok:
            run.stop(c, ENV_FAILED % (", ".join(n for n, _ in env_to_set), c.service))
            return
        c.env_set = [n for n, _ in env_to_set]
    c.done = True


def apply(ctx, comps, analyses, args, info):
    run = Run(ctx, args, info)

    # Step 5: the security pass, over every service that exists, before anything else.
    for c in comps:
        a = analyses[c.name]
        if a is not None and security_pass(run, c, a, with_open=True):
            run.pass_failed = True
    if not run.pass_failed:
        for c in comps:
            if c.reread_failed:
                run.stop(c, REREAD_FAILED % c.service)
                break

    # Step 6: each component's other work.
    if not run.pass_failed and not run.stopped:
        for c in comps:
            component_work(run, c, args, info)
            if run.stopped:
                break

    # Step 7: the reads again, for each component on which a command ran.
    final = dict(analyses)
    for c in comps:
        if not c.touched:
            continue
        if read_component(ctx, c, args):
            final[c.name] = analyze(c, args, info)
        else:
            c.verify_failed = True
            if c.exists_now:
                final[c.name] = None
    pending = []
    interrupted = run.stopped or run.pass_failed
    for c in comps:
        a = final[c.name]
        if c.verify_failed:
            pending.append({"item": "%s: read" % c.name, "reason": REASON_READ, "how": HOW})
            continue
        if a is None:
            what = "service"
        elif a.words:
            what = ", ".join(a.words)
        elif not a.access and not c.f_tried:
            what = "access"
        else:
            continue
        if interrupted and c.failed_here:
            reason = REASON_FAILED
        elif interrupted and not c.done:
            reason = REASON_STOPPED
        else:
            reason = REASON_MISSING if what == "service" else REASON_DIFFERS
        pending.append({"item": "%s: %s" % (c.name, what), "reason": reason, "how": HOW})
    if run.access_refused:
        pending.append(dict(ACCESS_ITEM))

    # Step 8: the status.
    if run.pass_failed or (run.stopped and not run.any_change):
        status = "failed"
    elif run.any_created:
        status = "created"
    elif run.any_change:
        status = "updated"
    else:
        status = "unchanged"

    created = [c.name for c in comps if c.created_service]
    updated = [c.name for c in comps if c.changed and not c.created_service]
    env_set = {c.name: c.env_set for c in comps if c.env_set}
    outputs, resources = build_outputs(comps, final, args, created, updated, env_set)

    lines = []
    if run.deployed:
        lines.append(COST_LINE)
    lines.extend(run.events)
    if run.pass_failed:
        for c in comps:
            if c.still_open_login:
                lines.append(STILL_OPEN_LOGIN % c.service)
            elif c.still_open_call:
                lines.append(STILL_OPEN_CALL % c.service)
        for c in comps:
            if c.still_no_login:
                lines.append(STILL_NO_LOGIN % c.service)
        lines.append(RUN_AGAIN_NOW)
        lines.extend(run.pass_done)
    for c in comps:
        lines.extend(component_lines(c, analyses[c.name], final[c.name]))
    if not run.any_command:
        lines.append("This run changed nothing.")
    return ctx.result(status, outputs, resources=resources, pending=pending, cost=dict(COST),
                      lines=lines)


def component_lines(c, start, a):
    out = []
    if c.created_service:
        out.append("The service %s was created." % c.service)
    elif c.changed and start is not None and start.words:
        out.append("The service %s was repaired: %s." % (c.service, ", ".join(start.words)))
    if a is None:
        if not c.created_service:
            out.append("The service %s does not exist." % c.service)
    elif a.words:
        out.append("The service %s still differs: %s." % (c.service, ", ".join(a.words)))
    elif not c.created_service and not (c.changed and start is not None and start.words):
        out.append("The service %s is as declared." % c.service)
    if c.env_set:
        out.append("Its settings %s were set." % ", ".join(c.env_set))
    if a is not None and a.url:
        out.append("Its address is %s." % a.url)
    if a is not None and a.placeholder:
        out.append("It still runs the placeholder image: the first deploy of CI replaces it.")
    return out


# ---------------------------------------------------------------------------
# The command


def run(args, ctx):
    problems, components, settings = validate(args)
    mode = args.get("mode") or DEFAULT_MODE
    if problems:
        return ctx.failed(problems, _empty_outputs(args), cost=dict(COST),
                          mode=mode if mode in ("plan", "apply") else DEFAULT_MODE)
    project_id = args["projectId"]

    # Step 1: the project number.
    c = ctx.read(["gcloud", "projects", "describe", project_id,
                  "--format=value(projectNumber)"])
    number = c.out.strip() if c.ok else ""
    if not number.isdigit():
        return ctx.failed(PROJECT_UNREADABLE % project_id, _empty_outputs(args),
                          cost=dict(COST))

    # Step 2: the active account.
    c = ctx.read(["gcloud", "config", "get-value", "account"])
    account = c.out.strip() if c.ok else ""
    if not account:
        return ctx.failed(ACCOUNT_UNREADABLE, _empty_outputs(args), cost=dict(COST))
    me = ("serviceAccount:%s" if account.endswith(".gserviceaccount.com") else "user:%s") \
        % account
    info = {"agent": "serviceAccount:service-%s@gcp-sa-iap.iam.gserviceaccount.com" % number,
            "me": me}

    # Step 3: each component, in the order of components.
    comps = [Component(name, args, settings) for name in components]
    analyses = {}
    for i, comp in enumerate(comps):
        if not read_component(ctx, comp, args):
            outputs, resources = build_outputs(comps[:i], analyses, args)
            return ctx.failed(READ_FAILED % (comp.service, project_id), outputs,
                              resources=resources, cost=dict(COST))
        analyses[comp.name] = analyze(comp, args, info)

    refused = unusable(ctx, comps, analyses, args, info)
    if refused:
        outputs, resources = build_outputs(comps, analyses, args)
        return ctx.failed(refused, outputs, resources=resources, cost=dict(COST))

    if mode == "plan":
        return plan(ctx, comps, analyses, args)
    return apply(ctx, comps, analyses, args, info)
