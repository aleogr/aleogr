"""project-access: let one person in, through the login of the organization, to the Cloud
Run services of the project's components in each declared environment (person=<e-mail>),
or say how many people each service lets in (list=yes).

The specification is skills/project-access/SKILL.md: the same rules of "Validate first",
in its order and with its sentences word for word; the same invocations, in the same
order (step 2 gcp_environment-describe, step 3 gcp_access-grant, for each environment);
the same answer and the same result block.

This module runs no provider command and writes nothing: its only reads are the
declaration (a file of the current folder) and gcp_environment-describe, called with
`--read-only`; the grant is gcp_access-grant's, called through ctx.call with exactly the
arguments of step 3 and `mode=apply`. The person's address is an argument: it is passed
to gcp_access-grant and named in the answer's lines of item 2, never in the result block
and never in a file.

Held across steps (part 3a's lesson): the declaration's values (read once at step 1;
this skill and the skills it invokes change no file), the person (an argument), and, for
each environment, its projectId (read at step 2; a grant never changes a GCP project's
id) and the result of its gcp_access-grant (the outcome the answer reports; that skill
reads its own policies back after its grants). No policy read before a grant is kept by
this module: it reads none. The skill waits for nothing, so a run is one command.
"""

import importlib.util
import os
import re
import sys

import aleogr_common as common

FAMILY = "orchestrator"
PROVIDER = "aleogr"
ACTION = "project-access"
DEFAULT_MODE = "apply"  # no mode argument: the skill acts (with list=yes, the callee reads)
RESULT_MODE = "apply"  # "mode is always apply"
WRITES = False  # the orchestrator writes nothing itself
CALLS_OTHERS = True  # what a run made is the called skills': an abort never says "nothing"

CLOUD = "aleogr-cloud-gcp"
DESCRIBE = "gcp_environment-describe"
GRANT = "gcp_access-grant"


def _plan_module():
    """This plugin's project-plan module, loaded by its file path (as project_apply does):
    the declaration's readers are its own."""
    name = "aleogr_plugin_project_plan"
    if name not in sys.modules:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project_plan.py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


PP = _plan_module()

COST = {"fixed": False, "notes": "letting a person through the login has no cost"}

# ---------------------------------------------------------------------------
# Prescribed sentences, word for word

PERSON_MISSING = "person is missing (or give list=yes)."
BOTH_GIVEN = "Give either person or list=yes, not both."
NOT_AN_ARGUMENT = ("%s is not an argument of project-access: give person=<e-mail> or "
                   "list=yes.")
PERSON_RULE = ("person must be the e-mail address of one person (such as name@example.com): "
               "not a group, a domain, a service account or everyone.")
LIST_RULE = "list must be yes."
NO_DECLARATION = PP.NO_DECLARATION
NO_ENVIRONMENT = ("The declaration has no environment: there is no service to let anyone in "
                  "to.")
NO_COMPONENT = "The declaration has no component: there is no service to let anyone in to."
NOT_READ = ("The GCP project of %s could not be read; nothing was changed. Run "
            "/aleogr:project-plan to see why.")
NOT_CREATED = ("The GCP project of %s does not exist yet: run /aleogr:project-apply "
               "confirm=yes first.")
SERVICE_MISSING = ("The service of %s does not exist yet in %s: run /aleogr:project-apply "
                   "confirm=yes first, then this skill again.")
ADDRESSES = "The addresses are in the answer of /aleogr:project-plan."
GROUP_SENTENCE = ("The address must be a person's Google account: a group's address is not "
                  "supported and would let nobody in.")
UNDO_COMMAND = ('gcloud iap web remove-iam-policy-binding --resource-type=cloud-run '
                '--service=%s --region=%s --project=%s --member="user:<e-mail>" '
                '--role="roles/iap.httpsResourceAccessor" --condition=None')
SERVICE_HOW = ("run /aleogr:project-apply confirm=yes first, then /aleogr:project-access "
               "again")

# ---------------------------------------------------------------------------
# Sentences the SKILL.md leaves to this skill's own words (fixed here)

NOT_JSON = "The declaration .aleogr/project.json is not valid JSON."  # as project-plan's
NOT_JSON_HOW = "fix .aleogr/project.json: it is not valid JSON"
UNREADABLE = "The declaration .aleogr/project.json could not be read."  # as project-plan's
UNREADABLE_HOW = "make .aleogr/project.json a readable file"
NOT_VALID = ("The declaration .aleogr/project.json is not valid: run /aleogr:project-plan to "
             "see why.")
NOT_VALID_HOW = "run /aleogr:project-plan to see why"
NO_ENVIRONMENT_HOW = ("declare the environment with /aleogr:project-declare environment=dev, "
                      "then run /aleogr:project-apply confirm=yes")
NO_COMPONENT_HOW = ("declare a component with /aleogr:project-declare component=<name>, then "
                    "run /aleogr:project-apply confirm=yes")
NOT_READ_HOW = "run /aleogr:project-plan to see why"
NOT_CREATED_HOW = "run /aleogr:project-apply confirm=yes first"
PERSON_MISSING_HOW = "give person=<e-mail> or list=yes"
BOTH_GIVEN_HOW = "give either person or list=yes, not both"
NOT_AN_ARGUMENT_HOW = "give person=<e-mail> or list=yes"
PERSON_RULE_HOW = ("give person=<e-mail>, the address of one person: not a group, a domain, a "
                   "service account or everyone")
LIST_RULE_HOW = "list must be yes"
GRANT_ENDED = "gcp_access-grant ended failed in %s."
ALREADY = "%s already had access to the service %s in %s."
GRANTED = "%s was let in to the service %s in %s by this run."
NOT_GRANTED = "%s could not be let in to the service %s in %s."
OPENS = "%s opens each service's address and signs in with that Google account."
OPEN_WARNING = ("Anyone on the internet who signs in with any Google account gets through the "
                "login of the service %s in %s.")
OPEN_REMOVE = "To close it, the owner runs:"
OPEN_ALSO = "/aleogr:project-apply confirm=yes also closes it."
UNDO_LEAD = "To undo a grant, the owner runs by hand:"

ARGUMENTS = ("person", "list")

# The rule on person, word for word the one of gcp_access-grant (its "Validate first").
_LOCAL = re.compile(r"^[A-Za-z0-9._+-]{1,64}$")
_LABEL = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_TLD = re.compile(r"^[A-Za-z]{1,63}$")
_OPEN_MEMBERS = ("allUsers", "allAuthenticatedUsers")

# The sentences of gcp_access-grant this skill reads (its answer is input only).
_CALLEE_MISSING = re.compile(r"^The service of the component (\S+) \(\S+\) does not exist in "
                             r"\S+: create it first with gcp_deploy-setup\.$")
_CALLEE_COUNT = re.compile(r"^The service (\S+) lets in [0-9]+ (?:person|people)\.$")
_CALLEE_COUNT_END = ("To remove a person from the service ", "This run changed nothing.")
_CALLEE_NOT_A_CAUSE = ("Anyone on the internet who signs in", "gcloud ",
                       "There is no cost: letting a person through the login costs nothing.",
                       GROUP_SENTENCE)


def person_ok(value):
    """One person's e-mail address, by the rules of "Validate first"."""
    if value in _OPEN_MEMBERS or value.count("@") != 1:
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


def validate_args(args):
    """None, or (the one sentence of the first rule broken, its `how`), in the order of
    "Validate first"."""
    person, listing = args.get("person"), args.get("list")
    if person is None and listing is None:
        return PERSON_MISSING, PERSON_MISSING_HOW
    if person is not None and listing is not None:
        return BOTH_GIVEN, BOTH_GIVEN_HOW
    for k in args:
        if k not in ARGUMENTS:
            return NOT_AN_ARGUMENT % k, NOT_AN_ARGUMENT_HOW
    if person is not None and not person_ok(person):
        return PERSON_RULE, PERSON_RULE_HOW
    if listing is not None and listing != "yes":
        return LIST_RULE, LIST_RULE_HOW
    return None


# ---------------------------------------------------------------------------
# Step 1: the declaration (only the keys this skill reads)


class Stop(Exception):
    """A step that ends the run `failed`: its sentence and its pending item."""

    def __init__(self, sentence, item, how, project=None):
        Exception.__init__(self, sentence)
        self.sentence = sentence
        self.item = item
        self.how = how
        self.project = project


def read_declaration(cwd="."):
    """Step 1: (project, region, components, environments), or Stop. The file is read
    and parsed by project-plan's own readers; none of the plan's other rules apply."""
    text, exists = PP._read_text(os.path.join(cwd, PP.DECLARATION))
    if exists is False:
        raise Stop(NO_DECLARATION, "declaration", PP.NO_DECLARATION_HOW)
    if text is None:
        raise Stop(UNREADABLE, "declaration", UNREADABLE_HOW)
    try:
        data = PP.parse_json(text)
    except ValueError:
        raise Stop(NOT_JSON, "declaration", NOT_JSON_HOW)
    if not isinstance(data, dict):
        raise Stop(NOT_VALID, "declaration", NOT_VALID_HOW)
    name = data.get("name")
    # outputs.project is the declaration's name once it was read.
    project = name if isinstance(name, str) and name else None
    envs = data.get("environments")
    if envs is None or envs == {} or envs == []:
        raise Stop(NO_ENVIRONMENT, "declaration", NO_ENVIRONMENT_HOW, project)
    comps = data.get("components")
    if comps is None or comps == []:
        raise Stop(NO_COMPONENT, "declaration", NO_COMPONENT_HOW, project)
    cloud = data.get("cloud")
    region = cloud.get("region") if isinstance(cloud, dict) else None
    if (not isinstance(envs, dict) or not isinstance(comps, list)
            or not all(isinstance(c, dict) and isinstance(c.get("name"), str) and c["name"]
                       for c in comps)
            or project is None or not isinstance(region, str) or not region):
        raise Stop(NOT_VALID, "declaration", NOT_VALID_HOW, project)
    components = sorted(c["name"] for c in comps)
    return name, region, components, sorted(envs)


# ---------------------------------------------------------------------------
# The invocations


class Calls(object):
    """How the steps invoke the two skills (a unit test gives its own)."""

    def __init__(self, ctx):
        self.ctx = ctx

    def describe(self, args):
        """Step 2, a read: called with --read-only."""
        r = common.call_plugin(CLOUD, DESCRIBE, args, read_only=True, caller=self.ctx.plugin)
        if isinstance(r, dict) and r.get("callError") == "version":
            raise common.PluginVersion(r)
        return r

    def grant(self, args):
        """Step 3: the grant (or, with list=yes, the read) is gcp_access-grant's."""
        return self.ctx.call(CLOUD, GRANT, args)


def _out(result):
    o = result.get("outputs") if isinstance(result, dict) else None
    return o if isinstance(o, dict) else {}


def _status(result):
    return result.get("status") if isinstance(result, dict) else None


def _answer(result):
    lines = result.get("answer") if isinstance(result, dict) else None
    return [l.strip() for l in (lines or []) if isinstance(l, str) and l.strip()]


def _pending(result):
    p = result.get("pending") if isinstance(result, dict) else None
    return [x for x in (p or []) if isinstance(x, dict)]


def _names(v):
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def grant_args(project_id, project, region, components, person):
    """The arguments of step 3, in its order; list=yes in place of person=<person>."""
    a = {"projectId": project_id, "project": project, "region": region,
         "components": ",".join(components)}
    if person is None:
        a["list"] = "yes"
    else:
        a["person"] = person
    a["mode"] = "apply"
    return a


class Environment(object):
    """One environment's gcp_access-grant: what the answer and the block need."""

    def __init__(self, name, project_id, result):
        self.name = name
        self.project_id = project_id
        self.result = result
        o = _out(result)
        self.status = _status(result) or "failed"
        self.granted = _names(o.get("granted"))
        self.already = _names(o.get("already"))
        self.people = o.get("people") if isinstance(o.get("people"), dict) else None
        self.open = _names(o.get("open"))
        self.pending = _pending(result)
        self.missing = []  # components whose service does not exist
        for line in _answer(result):
            m = _CALLEE_MISSING.match(line)
            if m:
                self.missing.append(m.group(1))

    def output(self):
        return {"name": self.name, "status": self.status, "granted": self.granted,
                "already": self.already, "people": self.people, "open": self.open}

    def causes(self, person):
        """The sentences of a failed gcp_access-grant other than a missing service: its
        own, without its lines about open services, its cost, the person, or the group
        sentence (they are this skill's items 2 and 4, which a failure replaces)."""
        out = []
        for line in _answer(self.result):
            if _CALLEE_MISSING.match(line) or line.startswith(_CALLEE_NOT_A_CAUSE):
                continue
            if person is not None and person in line:
                continue
            out.append(line)
        return out or [GRANT_ENDED % self.name]


# ---------------------------------------------------------------------------
# The run


def outputs(project, envs):
    return {"project": project, "environments": [e.output() for e in envs]}


def stop_result(ctx, stop, envs):
    return ctx.result("failed", outputs(stop.project, envs),
                      pending=[{"item": stop.item, "reason": "manual", "how": stop.how}],
                      cost=dict(COST), lines=[stop.sentence])


def status(envs):
    if envs and all(e.status == "failed" for e in envs):
        return "failed"
    if any(e.status == "updated" for e in envs):
        return "updated"
    return "unchanged"


def run(args, ctx, calls=None, cwd="."):
    # Validate first: no skill invoked and no file read.
    problem = validate_args(args)
    if problem:
        sentence, how = problem
        return ctx.result("failed", outputs(None, []),
                          pending=[{"item": "arguments", "reason": "manual", "how": how}],
                          cost=dict(COST), lines=[sentence])
    person = args.get("person")
    calls = calls or Calls(ctx)

    # Step 1
    try:
        project, region, components, environments = read_declaration(cwd)
    except Stop as stop:
        return stop_result(ctx, stop, [])

    envs = []
    for name in environments:
        # Step 2
        r = calls.describe({"project": project, "environment": name})
        if _status(r) == "failed" or not isinstance(r, dict):
            return stop_result(ctx, Stop(NOT_READ % name, "environment %s" % name,
                                         NOT_READ_HOW, project), envs)
        o = _out(r)
        if o.get("exists") is not True:
            return stop_result(ctx, Stop(NOT_CREATED % name, "environment %s" % name,
                                         NOT_CREATED_HOW, project), envs)
        project_id = o.get("projectId")
        if not isinstance(project_id, str) or not project_id:
            return stop_result(ctx, Stop(NOT_READ % name, "environment %s" % name,
                                         NOT_READ_HOW, project), envs)
        # Step 3
        e = Environment(name, project_id,
                        calls.grant(grant_args(project_id, project, region, components,
                                               person)))
        envs.append(e)
        # What this run made so far, for an aborted run (no e-mail).
        ctx.on_abort(["%s: %s" % (x.name, x.status) for x in envs
                      if x.status == "updated"])

    st = status(envs)
    return ctx.result(st, outputs(project, envs), pending=pending(envs, st),
                      cost=dict(COST), lines=answer_lines(envs, st, project, region,
                                                          components, person))


def pending(envs, st):
    out = []

    def add(x):
        if x not in out:
            out.append(x)
    for e in envs:
        for x in e.pending:
            add(x)
        for c in e.missing:
            add({"item": "%s: service" % c, "reason": "manual", "how": SERVICE_HOW})
    if st == "failed":
        for e in envs:
            if not e.missing:
                add({"item": "environment %s" % e.name, "reason": "manual",
                     "how": _how(e.causes(None)[0])})
    return out


def _how(sentence):
    return sentence[:-1] if sentence.endswith(".") else sentence


def failure_lines(e, person):
    """The sentence of an environment's failure (item 6): a missing service's, for each
    such component, or gcp_access-grant's own."""
    if e.missing:
        return [SERVICE_MISSING % (c, e.name) for c in e.missing]
    return e.causes(person)


def answer_lines(envs, st, project, region, components, person):
    if st == "failed":
        lines = []
        for e in envs:
            lines.extend(failure_lines(e, person))
        return lines
    # 1. One line per environment.
    lines = ["%s: %s" % (e.name, e.status) for e in envs]
    for e in envs:
        if e.status == "failed":
            lines.extend(failure_lines(e, person))
    ok = [e for e in envs if e.status != "failed"]
    if person is not None:
        # 2. Each component, the addresses, and the group sentence.
        for e in ok:
            for c in components:
                service = "%s-%s" % (project, c)
                if c in e.already:
                    lines.append(ALREADY % (person, service, e.name))
                elif c in e.granted:
                    lines.append(GRANTED % (person, service, e.name))
                else:
                    lines.append(NOT_GRANTED % (person, service, e.name))
        lines.append(OPENS % person)
        lines.append(ADDRESSES)
        lines.append(GROUP_SENTENCE)
    else:
        # 3. How many people each service lets in, and who, as gcp_access-grant listed.
        for e in ok:
            lines.extend(listed_lines(e))
    # 4. Open services.
    for e in ok:
        for c in e.open:
            service = "%s-%s" % (project, c)
            lines.append(OPEN_WARNING % (service, e.name))
            commands = [x["how"] for x in e.pending
                        if isinstance(x.get("how"), str)
                        and x["how"].startswith("gcloud iap web remove-iam-policy-binding ")
                        and (" --service=%s " % service) in x["how"]]
            if commands:
                lines.append(OPEN_REMOVE)
                lines.extend(commands)
            lines.append(OPEN_ALSO)
    # 5. The command that undoes a grant.
    if person is not None:
        undo = []
        for e in ok:
            for c in components:
                if c in e.granted or c in e.already:
                    undo.append(UNDO_COMMAND % ("%s-%s" % (project, c), region, e.project_id))
        if undo:
            lines.append(UNDO_LEAD)
            lines.extend(undo)
    return lines


def listed_lines(e):
    """The lines of gcp_access-grant's list: for each service, how many people it lets
    in, then the members it listed, as it listed them."""
    out = []
    inside = False
    for line in _answer(e.result):
        if _CALLEE_COUNT.match(line):
            inside = True
        elif line.startswith(_CALLEE_COUNT_END):
            inside = False
        if inside:
            out.append(line)
    return out
