"""gcp_ci-identity-setup: the keyless identity of one repository's CI in one GCP project.
Step 1 converts mode=plan only; mode=apply is still the SKILL.md's prose (exit 64 here).

The specification is skills/gcp_ci-identity-setup/SKILL.md: the same reads, in the same
order, the same parts and states, and the same result block. The reads (read_number,
read_parts) and the checks after them (part_failures) are written for both modes, so
that apply can be added beside plan() without changing them.
"""

import json
import re

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "ci-identity-setup"
UNCONVERTED_MODES = ("apply",)
DEFAULT_MODE = "plan"

REQUIRED = ("projectId", "project", "repository", "repositoryId", "ownerId", "branch",
            "workflow")
COST = {"fixed": False, "notes": "service accounts and workload identity federation are free"}
ISSUER = "https://token.actions.githubusercontent.com"
MAPPING = (
    ("google.subject", "assertion.sub"),
    ("attribute.repository", "assertion.repository"),
    ("attribute.ref", "assertion.ref"),
    ("attribute.repository_id", "assertion.repository_id"),
    ("attribute.repository_owner_id", "assertion.repository_owner_id"),
    ("attribute.job_workflow_ref", "assertion.job_workflow_ref"),
)
MAPPING_TEXT = ",".join("%s=%s" % kv for kv in MAPPING)
MISSING_WORDS = ("NOT_FOUND", "was not found", "does not exist")

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_PROJECT = re.compile(r"^[a-z][a-z0-9-]{1,12}[a-z0-9]$")
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
_NUMERIC_ID = re.compile(r"^[1-9][0-9]{0,19}$")
_BRANCH = re.compile(r"^[A-Za-z0-9._/-]{1,255}$")
_WORKFLOW_FILE = re.compile(r"^[a-z0-9_-]{1,60}\.yml$")

PROJECT_UNREADABLE = ("The GCP project %s could not be read: it must exist, created by "
                      "gcp_environment-create, and the active gcloud account must be able to "
                      "read it.")


# ---------------------------------------------------------------------------
# Validation


def _repository_ok(value):
    parts = value.split("/")
    return (len(parts) == 2 and bool(_OWNER.match(parts[0])) and bool(_NAME.match(parts[1]))
            and parts[1] not in (".", ".."))


def _branch_ok(value):
    return (bool(_BRANCH.match(value)) and not value.startswith("/")
            and not value.endswith("/") and ".." not in value)


def _workflow_ok(value):
    parts = value.split("/")
    return (len(parts) == 5 and _repository_ok("%s/%s" % (parts[0], parts[1]))
            and parts[2] == ".github" and parts[3] == "workflows"
            and bool(_WORKFLOW_FILE.match(parts[4])))


def validate(args):
    """None, or the one sentence of the first argument missing or rule broken."""
    for key in REQUIRED:
        if not args.get(key):
            return "%s is missing." % key
    if not _PROJECT_ID.match(args["projectId"]):
        return ("projectId is not a valid GCP project id: it must have 6 to 30 characters of "
                "a-z, 0-9 and -, start with a letter and not end with -.")
    if not _PROJECT.match(args["project"]):
        return ("project must have 3 to 14 characters of a-z, 0-9 and -, start with a letter "
                "and not end with -.")
    if not _repository_ok(args["repository"]):
        return ("repository must be <owner>/<name>: an owner of 1 to 39 characters of A-Z, "
                "a-z, 0-9 and -, not starting or ending with -, and a name of 1 to 100 "
                "characters of A-Z, a-z, 0-9, ., _ and -, other than . and ..")
    for key in ("repositoryId", "ownerId"):
        if not _NUMERIC_ID.match(args[key]):
            return "%s must be 1 to 20 digits, not starting with 0." % key
    if not _branch_ok(args["branch"]):
        return ("branch must have 1 to 255 characters of A-Z, a-z, 0-9, ., _, - and /, not "
                "start or end with / and not contain ..")
    if not _workflow_ok(args["workflow"]):
        return ("workflow must be <owner>/<name>/.github/workflows/<file>.yml, with <file> of "
                "1 to 60 characters of a-z, 0-9, - and _, and nothing after it.")
    mode = args.get("mode")
    if mode is not None and mode not in ("plan", "apply"):
        return "mode must be plan or apply."
    return None


# ---------------------------------------------------------------------------
# Names


def names(args, number=None):
    """The skill's names; those that need the project number are None without it."""
    project_id = args["projectId"]
    n = {
        "account": "%s-ci@%s.iam.gserviceaccount.com" % (args["project"], project_id),
        "condition": ("assertion.repository=='%s' && assertion.repository_id=='%s' && "
                      "assertion.repository_owner_id=='%s' && "
                      "assertion.ref=='refs/heads/%s' && "
                      "assertion.job_workflow_ref.startsWith('%s@')"
                      % (args["repository"], args["repositoryId"], args["ownerId"],
                         args["branch"], args["workflow"])),
        "provider": None,
        "member": None,
    }
    if number:
        n["provider"] = ("projects/%s/locations/global/workloadIdentityPools/github/providers/"
                         "github" % number)
        n["member"] = ("principalSet://iam.googleapis.com/projects/%s/locations/global/"
                       "workloadIdentityPools/github/attribute.repository/%s"
                       % (number, args["repository"]))
    return n


# ---------------------------------------------------------------------------
# Reads (both modes)


def _cause(c):
    """One sentence's cause of a failed gcloud read, with no raw error text."""
    t = c.text.lower()
    if c.code == 127 or "command not found" in t:
        return "gcloud is not installed"
    if ("auth login" in t or "credentials" in t or "reauthentication" in t
            or "not currently have an active account" in t):
        return "gcloud is not authenticated"
    if "service_disabled" in t or "has not been used" in t or "is disabled" in t:
        return "the IAM API is not enabled in the project"
    if "403" in t or "permission" in t or "not authorized" in t or "forbidden" in t:
        return "the active gcloud account is not allowed to read it"
    return "gcloud failed"


def _is_missing(c):
    return not c.ok and any(w in c.text for w in MISSING_WORDS)


def _json_object(text):
    """The JSON object of a read; {} for an empty output; None when it is not JSON."""
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def read_number(ctx, args):
    """Step 1: the project number, or None when the project could not be read."""
    c = ctx.read(["gcloud", "projects", "describe", args["projectId"],
                  "--format=value(projectNumber)"])
    number = c.out.strip() if c.ok else ""
    return number if number.isdigit() else None


class Parts(object):
    """What the reads of step 2 found. A part that was not read is None."""

    def __init__(self):
        self.account = None  # True or False
        self.pool = None  # the pool's JSON object, False when missing
        self.providers = None  # the ids of the pool's providers (list)
        self.provider = None  # the provider's JSON object, False when missing
        self.policy = None  # the account's policy, False when not read (no account)
        self.failure = None  # the sentence of a failed read

    @property
    def pool_exists(self):
        return isinstance(self.pool, dict)

    @property
    def provider_exists(self):
        return isinstance(self.provider, dict)


def read_parts(ctx, args, n):
    """Step 2: the five reads, each alone and in order; stops at the first failed read."""
    project_id = args["projectId"]
    parts = Parts()

    def read(argv, what, as_json):
        c = ctx.read(argv)
        if c.ok:
            if not as_json:
                return c.out
            data = _json_object(c.out)
            if data is None:
                parts.failure = "The %s could not be read: gcloud gave no JSON." % what
            return data
        if _is_missing(c):
            return False
        parts.failure = "The %s could not be read: %s." % (what, _cause(c))
        return None

    out = read(["gcloud", "iam", "service-accounts", "describe", n["account"],
                "--project=%s" % project_id, "--format=value(email)"],
               "service account %s" % n["account"], False)
    if parts.failure:
        return parts
    parts.account = out is not False

    out = read(["gcloud", "iam", "workload-identity-pools", "describe", "github",
                "--project=%s" % project_id, "--location=global", "--format=json"],
               "workload identity pool github", True)
    if parts.failure:
        return parts
    parts.pool = out

    if parts.pool_exists:
        out = read(["gcloud", "iam", "workload-identity-pools", "providers", "list",
                    "--workload-identity-pool=github", "--project=%s" % project_id,
                    "--location=global", "--format=value(name)"],
                   "list of the providers of the pool github", False)
        if parts.failure:
            return parts
        lines = [] if out is False else [x.strip() for x in out.splitlines() if x.strip()]
        parts.providers = [x.rsplit("/", 1)[-1] for x in lines]

        out = read(["gcloud", "iam", "workload-identity-pools", "providers", "describe",
                    "github", "--project=%s" % project_id, "--location=global",
                    "--workload-identity-pool=github", "--format=json"],
                   "workload identity provider github", True)
        if parts.failure:
            return parts
        parts.provider = out
    else:
        parts.provider = False

    if parts.account:
        out = read(["gcloud", "iam", "service-accounts", "get-iam-policy", n["account"],
                    "--project=%s" % project_id, "--format=json"],
                   "access policy of the service account %s" % n["account"], True)
        if parts.failure:
            return parts
        parts.policy = out if isinstance(out, dict) else False
    else:
        parts.policy = False
    return parts


# ---------------------------------------------------------------------------
# What the reads mean


def _disabled(obj):
    v = obj.get("disabled")
    return v is True or (isinstance(v, str) and v.strip().lower() == "true")


def provider_differences(parts, n):
    """The provider's parts that are not exactly the declared ones (condition, issuer,
    mapping), or None when the provider does not exist."""
    if not parts.provider_exists:
        return None
    p = parts.provider
    words = []
    condition = p.get("attributeCondition")
    if not isinstance(condition, str) or condition.strip() != n["condition"]:
        words.append("condition")
    oidc = p.get("oidc") if isinstance(p.get("oidc"), dict) else {}
    if oidc.get("issuerUri") != ISSUER:
        words.append("issuer")
    if p.get("attributeMapping") != dict(MAPPING):
        words.append("mapping")
    return words


def condition_state(parts, n):
    words = provider_differences(parts, n)
    if words is None:
        return "missing" if parts.provider is False else None
    return "differs" if words else "as-declared"


def _workload_members(parts):
    """The members of roles/iam.workloadIdentityUser on the account (policy read)."""
    members = []
    bindings = parts.policy.get("bindings") if isinstance(parts.policy, dict) else None
    for b in bindings if isinstance(bindings, list) else []:
        if isinstance(b, dict) and b.get("role") == "roles/iam.workloadIdentityUser":
            for m in b.get("members") if isinstance(b.get("members"), list) else []:
                if isinstance(m, str) and m not in members:
                    members.append(m)
    return members


def binding_exists(parts, n):
    return isinstance(parts.policy, dict) and n["member"] in _workload_members(parts)


def other_members(parts, n):
    if not isinstance(parts.policy, dict):
        return None
    return len([m for m in _workload_members(parts) if m != n["member"]])


def part_failures(parts, args):
    """The cases that end the skill with failed after the reads, one sentence each:
    a deleted pool or provider, a disabled one, another provider in the pool."""
    project_id = args["projectId"]
    out = []
    pool_deleted = parts.pool_exists and parts.pool.get("state") != "ACTIVE"
    if pool_deleted:
        # The pool is restored first; its provider's own state is said after that.
        out.append("The workload identity pool github was deleted and stays reserved for 30 "
                   "days: restore it by hand with gcloud iam workload-identity-pools undelete "
                   "github --project=%s --location=global, then run this again." % project_id)
    if (not pool_deleted and parts.provider_exists
            and parts.provider.get("state") != "ACTIVE"):
        out.append("The workload identity provider github was deleted and stays reserved for "
                   "30 days: restore it by hand with gcloud iam workload-identity-pools "
                   "providers undelete github --project=%s --location=global "
                   "--workload-identity-pool=github, then run this again." % project_id)
    if parts.pool_exists and _disabled(parts.pool):
        out.append("The workload identity pool github is disabled and accepts no token: "
                   "enable it by hand in the Google Cloud console (IAM, Workload Identity "
                   "Federation), then run this again.")
    if not pool_deleted and parts.provider_exists and _disabled(parts.provider):
        out.append("The workload identity provider github is disabled and accepts no token: "
                   "enable it by hand in the Google Cloud console (IAM, Workload Identity "
                   "Federation), then run this again.")
    others = [p for p in (parts.providers or []) if p != "github"]
    if others:
        out.append("The pool github has %s %s, which would let in tokens that do not pass "
                   "the condition: remove %s by hand, then run this again."
                   % ("another provider" if len(others) == 1 else "other providers",
                      ", ".join(others), "it" if len(others) == 1 else "them"))
    return out


def part_states(parts, n):
    """{part: "as declared" | "missing" | "differs"} in the order of the parts."""
    differs = provider_differences(parts, n)
    return {
        "account": "as declared" if parts.account else "missing",
        "pool": "as declared" if parts.pool_exists else "missing",
        "provider": ("missing" if differs is None else "differs" if differs
                     else "as declared"),
        "binding": "as declared" if binding_exists(parts, n) else "missing",
    }


def resources(parts, project):
    out = []
    if parts.account:
        out.append({"type": "service-account", "id": "%s-ci" % project,
                    "name": "%s-ci" % project, "labels": {}})
    if parts.pool_exists:
        out.append({"type": "workload-identity-pool", "id": "github", "name": "github",
                    "labels": {}})
    if parts.provider_exists:
        out.append({"type": "workload-identity-provider", "id": "github/github",
                    "name": "github", "labels": {}})
    return out


def outputs(parts, n, args, all_declared):
    return {
        "account": n["account"],
        "provider": n["provider"],
        "condition": condition_state(parts, n),
        "otherMembers": other_members(parts, n),
        "ciVariables": ({"GCP_PROJECT_ID": args["projectId"],
                         "GCP_WIF_PROVIDER": n["provider"],
                         "GCP_CI_ACCOUNT": n["account"]} if all_declared else None),
    }


def _null_outputs():
    return {"account": None, "provider": None, "condition": None, "otherMembers": None,
            "ciVariables": None}


# ---------------------------------------------------------------------------
# The answer


_LABELS = {
    "account": "The service account %(account)s",
    "pool": "The workload identity pool github",
    "provider": "The workload identity provider %(provider)s",
    "binding": "The binding that lets the repository's CI act as the account",
}


def state_lines(parts, n, states):
    lines = []
    for part in ("account", "pool", "provider", "binding"):
        label = _LABELS[part] % n
        state = states[part]
        if state == "as declared":
            lines.append("%s exists as declared." % label)
        elif state == "missing":
            lines.append("%s is missing." % label)
        else:
            lines.append("%s differs (%s)." % (label,
                                                ", ".join(provider_differences(parts, n))))
    condition = condition_state(parts, n)
    lines.append({"as-declared": "The condition is as declared.",
                  "missing": "The condition is missing.",
                  "differs": "The condition differs."}[condition])
    return lines


def members_line(count):
    if not count:
        return []
    return ["%d other member%s may also act as the account; this skill does not remove %s."
            % (count, "" if count == 1 else "s", "it" if count == 1 else "them")]


def ci_lines(args, n):
    return ["CI values: GCP_PROJECT_ID=%s, GCP_WIF_PROVIDER=%s, GCP_CI_ACCOUNT=%s."
            % (args["projectId"], n["provider"], n["account"])]


# ---------------------------------------------------------------------------
# The modes


def plan(args, ctx, n, parts):
    """Step 3: report, change nothing."""
    states = part_states(parts, n)
    all_declared = all(s == "as declared" for s in states.values())
    if any(s == "missing" for s in states.values()):
        status = "would-create"
    elif states["provider"] == "differs":
        status = "would-update"
    else:
        status = "unchanged"
    lines = state_lines(parts, n, states)
    lines.append("This plan changed nothing.")
    lines.extend(members_line(other_members(parts, n)))
    if all_declared:
        lines.extend(ci_lines(args, n))
    return ctx.result(status, outputs(parts, n, args, all_declared),
                      resources=resources(parts, args["project"]), cost=dict(COST),
                      lines=lines)


def run(args, ctx):
    mode = args.get("mode") or DEFAULT_MODE
    problem = validate(args)
    if problem:
        return ctx.failed(problem, _null_outputs(), cost=dict(COST),
                          mode=mode if mode in ("plan", "apply") else DEFAULT_MODE)

    number = read_number(ctx, args)
    if number is None:
        return ctx.failed(PROJECT_UNREADABLE % args["projectId"], _null_outputs(),
                          cost=dict(COST))
    n = names(args, number)

    parts = read_parts(ctx, args, n)
    failures = [parts.failure] if parts.failure else part_failures(parts, args)
    if failures:
        return ctx.failed(failures, outputs(parts, n, args, False), cost=dict(COST),
                          resources=resources(parts, args["project"]))

    if mode == "plan":
        return plan(args, ctx, n, parts)
    raise NotImplementedError("mode=%s is not converted" % mode)  # exits 64 before this
