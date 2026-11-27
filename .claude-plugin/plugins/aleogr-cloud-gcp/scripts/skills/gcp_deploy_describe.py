"""gcp_deploy-describe: whether each component runs as a Cloud Run service as declared.
Read-only; a service that does not exist is not a failure.

The specification is skills/gcp_deploy-describe/SKILL.md: the same reads, in the same
order, the same words of difference, the same sentences and the same result block. The
answer and the block hold no member of a policy and no setting's value.
"""

import json
import re

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "deploy-describe"
RESULT_MODE = "plan"  # the skill has no mode: its block always says plan

REQUIRED = ("projectId", "project", "region", "components", "maxInstances", "cpu", "memory",
            "ciAccount")

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_PROJECT = re.compile(r"^[a-z](?:[a-z0-9-]{0,12}[a-z0-9])?$")
_REGION = re.compile(r"^[a-z]+(?:-[a-z]+)+[0-9]+$")
_COMPONENT = re.compile(r"^[a-z](?:[a-z0-9-]{0,18}[a-z0-9])?$")
_MAX_INSTANCES = re.compile(r"^(?:[1-9]|10)$")
_ACCOUNT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ENV_VALUE = re.compile(r"^[A-Za-z0-9._:@-]{1,200}$")
_PLACEHOLDER = re.compile(r"^us-docker\.pkg\.dev/cloudrun/container/hello"
                          r"(?::[A-Za-z0-9_][A-Za-z0-9_.-]*|@sha256:[0-9a-f]+)?$")

OPEN_MEMBERS = ("allUsers", "allAuthenticatedUsers")
WORDS = ("account", "scaling", "size", "public", "open", "login", "agent", "ci", "labels",
         "env")

PROJECT_UNREADABLE = ("The GCP project %s could not be read. Check that it exists and that "
                      "the active gcloud account may read it.")
SERVICE_UNREADABLE = ("The service %s could not be read. Check that the Cloud Run API is "
                      "enabled in %s and that the active gcloud account may read its services.")
ACCESS_UNREADABLE = ("The access of the service %s could not be read. Check that the IAP API "
                     "is enabled in %s and that the active gcloud account may read the access "
                     "of its services and accounts.")
OPEN_SENTENCE = ("Anyone on the internet who signs in with any Google account gets through "
                 "its login.")


def _failed_outputs():
    return {"services": [], "missing": [], "differing": [], "waiting": []}


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


def _validate(args):
    """(problems, components, settings): the sentences of every rule broken, one per line."""
    problems = []
    for key in REQUIRED:
        if not args.get(key):
            problems.append("%s is missing." % key)
    project_id = args.get("projectId") or ""
    project = args.get("project") or ""
    environment = args.get("environment")
    if environment is not None and environment not in ("dev", "hom", "prd"):
        problems.append("environment must be dev, hom or prd.")
    if project_id and not _PROJECT_ID.match(project_id):
        problems.append("projectId is not a GCP project id.")
    project_ok = bool(_PROJECT.match(project))
    if project and not project_ok:
        problems.append("project must have 1 to 14 lowercase letters, digits and hyphens, "
                        "starting with a letter and not ending with a hyphen.")
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


def _bindings(policy):
    b = policy.get("bindings") if isinstance(policy, dict) else None
    return [x for x in b if isinstance(x, dict)] if isinstance(b, list) else []


def _members(binding):
    m = binding.get("members")
    return [x for x in m if isinstance(x, str)] if isinstance(m, list) else []


def _has_open_member(policy):
    return any(m in OPEN_MEMBERS for b in _bindings(policy) for m in _members(b))


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


def _differences(svc, policy, account_policy, login_policy, names, args, settings):
    """(words, env_missing, env_other): the words that differ, in the table's order, and
    the names of the settings missing or holding another value."""
    meta = _get(svc, "metadata", "annotations") or {}
    tmeta = _get(svc, "spec", "template", "metadata", "annotations") or {}
    if not isinstance(meta, dict):
        meta = {}
    if not isinstance(tmeta, dict):
        tmeta = {}
    container = _get(svc, "spec", "template", "spec", "containers", 0) or {}
    limits = _get(container, "resources", "limits") or {}
    if not isinstance(limits, dict):
        limits = {}
    ci_member = "serviceAccount:%s" % args["ciAccount"]
    words = set()

    if (_get(svc, "spec", "template", "spec", "serviceAccountName") != names["account"]
            or account_policy is None):
        words.add("account")
    if (meta.get("run.googleapis.com/maxScale") != args["maxInstances"]
            or not _zero_or_absent(meta.get("run.googleapis.com/minScale"))
            or meta.get("run.googleapis.com/scalingMode") == "manual"
            or not _zero_or_absent(tmeta.get("autoscaling.knative.dev/minScale"))):
        words.add("scaling")
    throttling = tmeta.get("run.googleapis.com/cpu-throttling")
    if (_cpu(limits.get("cpu")) != float(args["cpu"])
            or _memory_mi(limits.get("memory")) != _memory_mi(args["memory"])
            or not (throttling is None or str(throttling).strip().lower() == "true")):
        words.add("size")
    disabled = meta.get("run.googleapis.com/invoker-iam-disabled")
    if _has_open_member(policy) or (disabled is not None
                                    and str(disabled).strip().lower() == "true"):
        words.add("public")
    if _has_open_member(login_policy):
        words.add("open")
    if meta.get("run.googleapis.com/iap-enabled") != "true":
        words.add("login")
    if not _granted(policy, "roles/run.invoker", names["agent"]):
        words.add("agent")
    if (not _granted(policy, "roles/run.developer", ci_member) or account_policy is None
            or not _granted(account_policy, "roles/iam.serviceAccountUser", ci_member)):
        words.add("ci")
    labels = _get(svc, "metadata", "labels") or {}
    if not isinstance(labels, dict):
        labels = {}
    environment = args.get("environment")
    if (labels.get("aleogr-project") != args["project"]
            or labels.get("aleogr-component") != names["component"]
            or (labels.get("aleogr-environment") != environment if environment
                else labels.get("aleogr-environment") not in ("dev", "hom", "prd"))):
        words.add("labels")
    env_missing, env_other = [], []
    items = container.get("env") if isinstance(container, dict) else None
    items = [x for x in items if isinstance(x, dict)] if isinstance(items, list) else []
    for name, value in settings.get(names["component"], []):
        held = [x for x in items if x.get("name") == name]
        if not held:
            env_missing.append(name)
        elif not any(x.get("value") == value for x in held):
            env_other.append(name)
    if env_missing or env_other:
        words.add("env")
    return [w for w in WORDS if w in words], env_missing, env_other


def run(args, ctx):
    problems, components, settings = _validate(args)
    if problems:
        return ctx.failed(problems, _failed_outputs())
    project_id = args["projectId"]
    project = args["project"]
    region = args["region"]

    # Step 1: the project number.
    c = ctx.read(["gcloud", "projects", "describe", project_id,
                  "--format=value(projectNumber)"])
    number = c.out.strip() if c.ok else ""
    if not number.isdigit():
        return ctx.failed(PROJECT_UNREADABLE % project_id, _failed_outputs())
    agent = "serviceAccount:service-%s@gcp-sa-iap.iam.gserviceaccount.com" % number

    # Step 2: each service, in the order of components.
    described = {}
    for name in components:
        service = "%s-%s" % (project, name)
        c = ctx.read(["gcloud", "run", "services", "describe", service,
                      "--project=%s" % project_id, "--region=%s" % region, "--format=json"])
        if not c.ok:
            if ("Cannot find service" in c.text or "NOT_FOUND" in c.text
                    or "could not be found" in c.text):
                described[name] = None
                continue
            return ctx.failed(SERVICE_UNREADABLE % (service, project_id), _failed_outputs())
        data = _json_object(c.out)
        if data is None:
            return ctx.failed(SERVICE_UNREADABLE % (service, project_id), _failed_outputs())
        described[name] = data

    # Step 3: for each service that exists, its policy, its account's, its login's.
    policies = {}
    for name in components:
        if described[name] is None:
            continue
        service = "%s-%s" % (project, name)
        account = "%s@%s.iam.gserviceaccount.com" % (service, project_id)
        c = ctx.read(["gcloud", "run", "services", "get-iam-policy", service,
                      "--project=%s" % project_id, "--region=%s" % region, "--format=json"])
        policy = _json_object(c.out) if c.ok else None
        if policy is None:
            return ctx.failed(ACCESS_UNREADABLE % (service, project_id), _failed_outputs())
        c = ctx.read(["gcloud", "iam", "service-accounts", "get-iam-policy", account,
                      "--project=%s" % project_id, "--format=json"])
        if c.ok:
            account_policy = _json_object(c.out)
            if account_policy is None:
                return ctx.failed(ACCESS_UNREADABLE % (service, project_id), _failed_outputs())
        elif "NOT_FOUND" in c.text or "does not exist" in c.text:
            account_policy = None  # the account does not exist
        else:
            return ctx.failed(ACCESS_UNREADABLE % (service, project_id), _failed_outputs())
        c = ctx.read(["gcloud", "iap", "web", "get-iam-policy", "--resource-type=cloud-run",
                      "--service=%s" % service, "--region=%s" % region,
                      "--project=%s" % project_id, "--format=json"])
        login_policy = _json_object(c.out) if c.ok else None
        if login_policy is None:
            return ctx.failed(ACCESS_UNREADABLE % (service, project_id), _failed_outputs())
        policies[name] = (policy, account_policy, login_policy, account)

    services, resources, lines = [], [], []
    missing, differing, waiting = [], [], []
    for name in components:
        service = "%s-%s" % (project, name)
        svc = described[name]
        if svc is None:
            services.append({"component": name, "exists": False, "asDeclared": False,
                             "differences": [], "placeholder": False, "url": None})
            missing.append(name)
            lines.append("The service %s does not exist." % service)
            continue
        policy, account_policy, login_policy, account = policies[name]
        names = {"component": name, "account": account, "agent": agent}
        words, env_missing, env_other = _differences(svc, policy, account_policy,
                                                     login_policy, names, args, settings)
        image = _get(svc, "spec", "template", "spec", "containers", 0, "image")
        placeholder = isinstance(image, str) and bool(_PLACEHOLDER.match(image))
        url = _get(svc, "status", "url")
        url = url if isinstance(url, str) and url else None
        services.append({"component": name, "exists": True, "asDeclared": not words,
                         "differences": words, "placeholder": placeholder, "url": url})
        labels = _get(svc, "metadata", "labels") or {}
        held = {}
        if isinstance(labels, dict):
            for key in ("aleogr-project", "aleogr-environment", "aleogr-component"):
                if key in labels:
                    held[key] = labels[key]
        resources.append({"type": "run-service", "id": "%s/%s/%s" % (project_id, region, service),
                          "name": service, "labels": held})
        where = " (%s)" % url if url else ""
        if words:
            differing.append(name)
            lines.append("The service %s%s differs: %s." % (service, where, ", ".join(words)))
            if "open" in words:
                lines.append(OPEN_SENTENCE)
            for setting in env_missing:
                lines.append("Its setting %s is missing." % setting)
            for setting in env_other:
                lines.append("Its setting %s holds another value." % setting)
        else:
            lines.append("The service %s%s is as declared." % (service, where))
            if placeholder:
                waiting.append(name)
        if placeholder:
            lines.append("It still runs the placeholder image.")
        else:
            lines.append("It runs an image CI deployed.")

    outputs = {"services": services, "missing": missing, "differing": differing,
               "waiting": waiting}
    return ctx.result("unchanged", outputs, resources=resources, lines=lines)
