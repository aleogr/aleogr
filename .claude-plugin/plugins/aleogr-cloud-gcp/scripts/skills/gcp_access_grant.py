"""gcp_access-grant: lets one person in, through the login (IAP), to the Cloud Run
service of each component, or lists who each service lets in (list=yes).

The specification is skills/gcp_access-grant/SKILL.md: the same reads, in the same order
(step 1 every service, step 2 each login policy), the same grant (step 4, through
ctx.write only, the member always user:<person>, on the service's login policy only), the
same read back (step 5), the same status (step 6) and the same result block. Nothing is
ever removed, and the block holds no e-mail.
"""

import json
import re

import aleogr_common as common  # noqa: E402  (scripts/ is on sys.path)

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "access-grant"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply with person grants, through ctx.write only

REQUIRED = ("projectId", "project", "region", "components")
COST = {"fixed": False, "notes": "letting a person through the login has no cost"}
COST_LINE = "There is no cost: letting a person through the login costs nothing."
ACCESSOR = "roles/iap.httpsResourceAccessor"
OPEN_MEMBERS = ("allUsers", "allAuthenticatedUsers")

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_PROJECT = re.compile(r"^[a-z](?:[a-z0-9-]{0,12}[a-z0-9])?$")
_REGION = re.compile(r"^[a-z]+(?:-[a-z]+)+[0-9]+$")
_COMPONENT = re.compile(r"^[a-z](?:[a-z0-9-]{0,18}[a-z0-9])?$")
_LOCAL = re.compile(r"^[A-Za-z0-9._+-]{1,64}$")
_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_TLD = re.compile(r"^[A-Za-z]{1,63}$")

# The sentences of the SKILL.md, word for word.
PERSON_RULE = ("person must be the e-mail address of one person (such as name@example.com): "
               "not a group, a domain, a service account or everyone.")
SERVICE_MISSING = ("The service of the component %s (%s) does not exist in %s: create it "
                   "first with gcp_deploy-setup.")
READ_FAILED = ("The service %s or its access could not be read; nothing was changed. Check "
               "that the Cloud Run and IAP APIs are enabled in %s and that the active gcloud "
               "account may read its services and their access.")
GRANT_FAILED = ("The person could not be let in to the service %s through the login. Check "
                "that the active gcloud account may change who gets in to the project's "
                "services.")
GROUP_SENTENCE = ("The address must be a person's Google account: a group's address is not "
                  "supported and would let nobody in.")
OPEN_SENTENCE = ("Anyone on the internet who signs in with any Google account gets through "
                 "the login of the service %s.")

# Sentences the SKILL.md leaves free (one fixed wording each).
UNUSABLE = ("These arguments give a command this tooling does not allow; nothing was changed. "
            "Check the arguments, then run this again.")
REASON_REFUSED = "The grant was refused."
REASON_STOPPED = "This run stopped before this grant."
REASON_UNREAD = "The access could not be read back after the grant."
REASON_NOT_SEEN = "The grant was not found when the access was read back."


def _outputs():
    return {"granted": [], "already": [], "people": None, "open": []}


# ---------------------------------------------------------------------------
# Validation


def person_ok(value):
    """One person's e-mail address, as the SKILL.md's rules say."""
    if value in OPEN_MEMBERS or value.count("@") != 1:
        return False
    if any(ch in value for ch in " :,\"'`"):
        return False
    local, domain = value.split("@")
    if not _LOCAL.match(local):
        return False
    parts = domain.split(".")
    if len(parts) < 2 or not all(_LABEL.match(p) for p in parts) or not _TLD.match(parts[-1]):
        return False
    return not domain.lower().endswith("gserviceaccount.com")


def validate(args):
    """(problems, components): one sentence per argument missing or rule broken."""
    problems = []
    for key in REQUIRED:
        if not args.get(key):
            problems.append("%s is missing." % key)
    person, listing = args.get("person"), args.get("list")
    if person is None and listing is None:
        problems.append("person is missing (or give list=yes).")
    elif person is not None and listing is not None:
        problems.append("Give either person or list=yes, not both.")
    project = args.get("project") or ""
    if args.get("projectId") and not _PROJECT_ID.match(args["projectId"]):
        problems.append("projectId is not a GCP project id.")
    project_ok = bool(_PROJECT.match(project))
    if project and not project_ok:
        problems.append("project must have 1 to 14 lowercase letters, digits and hyphens, "
                        "starting with a letter and not ending with a hyphen.")
    if args.get("region") and not _REGION.match(args["region"]):
        problems.append("region is not a Google Cloud region name (such as us-central1).")
    components = []
    raw = args.get("components") or ""
    if raw:
        names = raw.split(",")
        if any(name == "" for name in names):
            problems.append("components must be names separated by , with no empty name.")
        seen, twice = set(), []
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
                    problems.append("%s has %d characters: a service's name must have 6 to 30."
                                    % (service, len(service)))
    if person is not None and not person_ok(person):
        problems.append(PERSON_RULE)
    if listing is not None and listing != "yes":
        problems.append("list must be yes.")
    mode = args.get("mode")
    if mode is not None and mode not in ("plan", "apply"):
        problems.append("mode must be plan or apply.")
    return problems, components


# ---------------------------------------------------------------------------
# Reading


def _json_object(text):
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _bindings(policy):
    b = policy.get("bindings") if isinstance(policy, dict) else None
    return [x for x in b if isinstance(x, dict)] if isinstance(b, list) else []


def _members(binding):
    m = binding.get("members")
    return [x for x in m if isinstance(x, str)] if isinstance(m, list) else []


def read_login_policy(ctx, service, args):
    """The command of step 2, alone: the policy, or None."""
    c = ctx.read(["gcloud", "iap", "web", "get-iam-policy", "--resource-type=cloud-run",
                  "--service=%s" % service, "--region=%s" % args["region"],
                  "--project=%s" % args["projectId"], "--format=json"])
    return _json_object(c.out) if c.ok else None


class Access(object):
    """What a login policy says, as "Names" defines it."""

    def __init__(self, policy, member=None):
        lets_in = [b for b in _bindings(policy) if b.get("role") == ACCESSOR
                   and not b.get("condition")]
        conditional = [b for b in _bindings(policy) if b.get("role") == ACCESSOR
                       and b.get("condition")]
        self.members = []
        for b in lets_in:
            for m in _members(b):
                if m not in self.members:
                    self.members.append(m)
        self.people = len(self.members)
        self.conditional_members = []  # (member, title)
        for b in conditional:
            cond = b.get("condition")
            title = cond.get("title") if isinstance(cond, dict) else None
            for m in _members(b):
                self.conditional_members.append((m, title if isinstance(title, str) else ""))
        self.removes = []  # (member, role) of allUsers and allAuthenticatedUsers
        for b in _bindings(policy):
            for m in _members(b):
                if m in OPEN_MEMBERS:
                    self.removes.append((m, b.get("role")))
        self.open = bool(self.removes)
        self.has = False
        self.conditional = False
        if member is not None:
            low = member.lower()
            self.has = any(m.lower() == low for b in lets_in for m in _members(b))
            self.conditional = not self.has and any(
                m.lower() == low for b in conditional for m in _members(b))


def open_remove_command(service, args, member, role):
    """The remove command of "Names" (the owner runs it; this skill never does)."""
    return ("gcloud iap web remove-iam-policy-binding --resource-type=cloud-run --service=%s "
            "--region=%s --project=%s --member=%s --role=%s --all"
            % (service, args["region"], args["projectId"], member, role))


def person_remove_command(service, args):
    return ('gcloud iap web remove-iam-policy-binding --resource-type=cloud-run --service=%s '
            '--region=%s --project=%s --member="user:<e-mail>" '
            '--role="roles/iap.httpsResourceAccessor" --condition=None'
            % (service, args["region"], args["projectId"]))


def grant_command(service, args):
    """The command of step 4, exactly as the SKILL.md writes it."""
    return ["gcloud", "iap", "web", "add-iam-policy-binding", "--resource-type=cloud-run",
            "--service=%s" % service, "--region=%s" % args["region"],
            "--project=%s" % args["projectId"], "--member=user:%s" % args["person"],
            "--role=%s" % ACCESSOR, "--condition=None", "--quiet"]


def pending_how(name, args):
    return ("/aleogr-cloud-gcp:gcp_access-grant projectId=%s project=%s region=%s "
            "components=%s person=<e-mail> mode=apply"
            % (args["projectId"], args["project"], args["region"], name))


# ---------------------------------------------------------------------------
# The command


def run(args, ctx):
    problems, components = validate(args)
    mode = args.get("mode") or DEFAULT_MODE
    if problems:
        return ctx.failed(problems, _outputs(), cost=dict(COST),
                          mode=mode if mode in ("plan", "apply") else DEFAULT_MODE)
    project_id, region = args["projectId"], args["region"]
    person = args.get("person")
    services = [(name, "%s-%s" % (args["project"], name)) for name in components]

    # Step 1: every service, each alone; a missing one is named once all are read.
    missing = []
    for name, service in services:
        c = ctx.read(["gcloud", "run", "services", "describe", service,
                      "--project=%s" % project_id, "--region=%s" % region,
                      "--format=value(metadata.name)"])
        if c.ok:
            continue
        if ("Cannot find service" in c.text or "NOT_FOUND" in c.text
                or "could not be found" in c.text):
            missing.append(SERVICE_MISSING % (name, service, region))
            continue
        return ctx.failed(READ_FAILED % (service, project_id), _outputs(), cost=dict(COST))
    if missing:
        return ctx.failed(missing, _outputs(), cost=dict(COST))
    resources = [{"type": "run-service", "id": "%s/%s/%s" % (project_id, region, service),
                  "name": service} for _, service in services]

    # A grant that no write of this skill would take ends the run here, in both modes.
    if person is not None and any(
            common.write_refusal(ctx.skill, grant_command(service, args), root=ctx.root)
            for _, service in services):
        return ctx.failed(UNUSABLE, _outputs(), cost=dict(COST))

    # Step 2: each login policy, each alone.
    member = "user:%s" % person if person is not None else None
    access = {}
    for name, service in services:
        policy = read_login_policy(ctx, service, args)
        if policy is None:
            return ctx.failed(READ_FAILED % (service, project_id), _outputs(), cost=dict(COST))
        access[name] = Access(policy, member)

    # Step 3: one pending item per remove command of an open service.
    pending = []
    open_lines = []
    for name, service in services:
        for m, role in access[name].removes:
            command = open_remove_command(service, args, m, role)
            pending.append({"item": "access", "reason": "manual", "how": command})
        if access[name].open:
            open_lines.append(OPEN_SENTENCE % service)
            open_lines.extend(open_remove_command(service, args, m, role)
                              for m, role in access[name].removes)

    if person is None:
        return listing(ctx, services, access, args, resources, pending, open_lines)

    already = [name for name, _ in services if access[name].has]
    to_grant = [(name, service) for name, service in services if not access[name].has]
    if mode != "apply":
        lines = list(open_lines)
        if to_grant:
            lines.append(COST_LINE)
        for name, service in services:
            a = access[name]
            if a.has:
                lines.append("%s already gets in to the service %s through the login."
                             % (person, service))
            else:
                lines.append("%s would be let in to the service %s through the login."
                             % (person, service))
                if a.conditional:
                    lines.append("A conditional binding already names the person; an "
                                 "unconditional one would be added.")
        lines.append("This plan changed nothing.")
        lines.extend(closing_lines(person))
        outputs = {"granted": [n for n, _ in to_grant], "already": already, "people": None,
                   "open": [n for n, _ in services if access[n].open]}
        return ctx.result("would-update" if to_grant else "unchanged", outputs,
                          resources=resources, pending=pending, cost=dict(COST), lines=lines)

    # Step 4: the grants, in the order of components; no wait, no retry.
    granted = []
    events = []
    stopped_at = None
    for i, (name, service) in enumerate(to_grant):
        if ctx.write(grant_command(service, args)).ok:
            granted.append((name, service))
            continue
        events.append(GRANT_FAILED % service)
        stopped_at = i
        break
    if stopped_at == 0:
        lines = list(open_lines) + [COST_LINE] + events
        lines.extend(answer_lines(services, access, person, [], already))
        outputs = {"granted": [], "already": already, "people": None,
                   "open": [n for n, _ in services if access[n].open]}
        return ctx.failed(lines, outputs, pending=pending, cost=dict(COST),
                          resources=resources)
    if stopped_at is not None:
        pending.append({"item": "%s: access" % to_grant[stopped_at][0],
                        "reason": REASON_REFUSED, "how": pending_how(to_grant[stopped_at][0],
                                                                     args)})
        for name, _ in to_grant[stopped_at + 1:]:
            pending.append({"item": "%s: access" % name, "reason": REASON_STOPPED,
                            "how": pending_how(name, args)})

    # Step 5: read back each service granted.
    before = dict(access)
    for name, service in granted:
        policy = read_login_policy(ctx, service, args)
        if policy is None:
            events.append("The access to the service %s could not be read back, so the grant "
                          "could not be confirmed." % service)
            pending.append({"item": "%s: access" % name, "reason": REASON_UNREAD,
                            "how": pending_how(name, args)})
            continue
        access[name] = Access(policy, member)
        if not access[name].has:
            events.append("The grant on the service %s could not be confirmed when it was read "
                          "back." % service)
            pending.append({"item": "%s: access" % name, "reason": REASON_NOT_SEEN,
                            "how": pending_how(name, args)})

    lines = list(open_lines)
    if to_grant:
        lines.append(COST_LINE)
    lines.extend(events)
    lines.extend(answer_lines(services, before, person, [n for n, _ in granted], already))
    outputs = {"granted": [n for n, _ in granted], "already": already, "people": None,
               "open": [n for n, _ in services if access[n].open]}
    return ctx.result("updated" if granted else "unchanged", outputs, resources=resources,
                      pending=pending, cost=dict(COST), lines=lines)


def answer_lines(services, access, person, granted, already):
    lines = []
    for name, service in services:
        a = access[name]
        if name in already:
            lines.append("%s already got in to the service %s through the login."
                         % (person, service))
        elif name in granted:
            lines.append("%s was let in to the service %s through the login by this run."
                         % (person, service))
            if a.conditional:
                lines.append("A conditional binding already named the person; an "
                             "unconditional one was added.")
        else:
            lines.append("%s was not let in to the service %s." % (person, service))
    lines.extend(closing_lines(person))
    return lines


def closing_lines(person):
    return ["%s opens each service's address and signs in with that Google account."
            % person, GROUP_SENTENCE]


def listing(ctx, services, access, args, resources, pending, open_lines):
    """list=yes: who each service lets in, in the answer only; numbers in the block."""
    lines = list(open_lines)
    any_user = []
    for name, service in services:
        a = access[name]
        lines.append("The service %s lets in %d %s." % (service, a.people,
                                                        "person" if a.people == 1 else
                                                        "people"))
        users = [m for m in a.members if m.startswith("user:")]
        others = [m for m in a.members if not m.startswith("user:")]
        lines.extend(users)
        if others:
            lines.append("Other members: %s." % ", ".join(others))
        if a.conditional_members:
            lines.append("Members of conditional bindings, not counted: %s." % ", ".join(
                "%s (%s)" % (m, t) if t else m for m, t in a.conditional_members))
        if users:
            any_user.append(service)
    for service in any_user:
        lines.append("To remove a person from the service %s, the owner runs by hand:" % service)
        lines.append(person_remove_command(service, args))
    lines.append("This run changed nothing.")
    outputs = {"granted": [], "already": [],
               "people": {name: access[name].people for name, _ in services},
               "open": [n for n, _ in services if access[n].open]}
    return ctx.result("unchanged", outputs, resources=resources, pending=pending,
                      cost=dict(COST), lines=lines)
