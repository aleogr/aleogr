"""gcp-artifact-registry_access-grant: let one service account of the project's own GCP
project push to the project's image repository, by granting it
roles/artifactregistry.writer on that one repository (mode=apply), or say whether a run
would (mode=plan, the default).

The specification is skills/gcp-artifact-registry_access-grant/SKILL.md: the same read of
the repository's policy, the same grant (polled while the new account is not visible
yet: at most 10 tries, 9 waits of `sleep 30` through ctx.wait), the same read back, the
same states and the same result block. The grant runs through ctx.write only; it is
checked against this skill's allowlist of writes in both modes before the plan announces
it or the apply runs it. Never on the GCP project, never another role, never a removal.
"""

import json
import re

import aleogr_common as common

FAMILY = "registry"
PROVIDER = "gcp-artifact-registry"
ACTION = "access-grant"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply adds the binding, through ctx.write only

SKILL = "gcp-artifact-registry_access-grant"
PLUGIN = "aleogr-registry-gcp-artifact-registry"
WRITER = "roles/artifactregistry.writer"
TRIES = 10  # the first one included, so at most 9 waits

COST = {"fixed": False, "notes": "no cost"}

_PROJECT_ID_RE = r"[a-z][a-z0-9-]{4,28}[a-z0-9]"
_PROJECT_ID = re.compile("^" + _PROJECT_ID_RE + "$")
_PROJECT = re.compile(r"^[a-z]([a-z0-9-]{0,12}[a-z0-9])?$")
_REGION = re.compile(r"^[a-z]+(-[a-z]+)+[0-9]+$")
_IDENTITY = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]@(" + _PROJECT_ID_RE
                       + r")\.iam\.gserviceaccount\.com$")

MISSING = ("The repository %s does not exist in %s: create it first with "
           "gcp-artifact-registry_repository-create.")
READ_FAILED = ("The repository's access could not be read; nothing was changed. Check that "
               "the GCP project %s exists, that the Artifact Registry API is enabled in it, "
               "and that the active gcloud account is signed in and may read its "
               "repositories.")
GRANT_FAILED = ("The push access could not be granted; nothing was changed. Check that the "
                "account %s exists and that the active gcloud account may change the "
                "repository's access.")
# One fixed sentence for a grant that this skill's allowlist of writes would refuse.
UNUSABLE = ("The push access cannot be granted with these arguments: the command is not one "
            "this skill may run; nothing was changed.")


def validate(args):
    """None, or the one sentence of the first argument missing or wrong."""
    for key in ("projectId", "project", "region", "identity", "role"):
        if not args.get(key):
            return "%s is missing." % key
    if not _PROJECT_ID.match(args["projectId"]):
        return "projectId is not a GCP project id."
    if not _PROJECT.match(args["project"]):
        return ("project must have 1 to 14 lowercase letters, digits and hyphens, starting "
                "with a letter.")
    if not _REGION.match(args["region"]):
        return "region is not a Google Cloud region name (such as us-central1)."
    m = _IDENTITY.match(args["identity"])
    if not m:
        return ("identity must be a service account e-mail "
                "(<id>@<project id>.iam.gserviceaccount.com).")
    if m.group(1) != args["projectId"]:
        return "identity must be a service account of the project %s." % args["projectId"]
    if args["role"] == "pull":
        return ("role=pull is not needed: Cloud Run's own agent pulls from a repository of "
                "its own project, so only push is granted.")
    if args["role"] != "push":
        return "role must be push."
    if "mode" in args and args["mode"] not in ("plan", "apply"):
        return "mode must be plan or apply."
    return None


def policy_command(project_id, project, region):
    """Steps 1 and 4, as the SKILL.md writes them."""
    return ["gcloud", "artifacts", "repositories", "get-iam-policy", project,
            "--location=%s" % region, "--project=%s" % project_id, "--format=json"]


def grant_command(project_id, project, region, member):
    """Step 3, as the SKILL.md writes it."""
    return ["gcloud", "artifacts", "repositories", "add-iam-policy-binding", project,
            "--location=%s" % region, "--project=%s" % project_id, "--member=%s" % member,
            "--role=%s" % WRITER, "--condition=None", "--quiet"]


def json_object(text):
    text = text or ""
    for m in re.finditer(r"(?m)^\{", text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def granted(policy, member):
    """A binding whose role is exactly the writer role, with no condition, lists
    `member`."""
    bindings = policy.get("bindings") if isinstance(policy, dict) else None
    for b in bindings if isinstance(bindings, list) else []:
        if (isinstance(b, dict) and b.get("role") == WRITER and "condition" not in b
                and isinstance(b.get("members"), list) and member in b["members"]):
            return True
    return False


def not_visible_yet(c):
    """The refusal that waiting cures: the account does not exist (yet)."""
    return not c.ok and ("does not exist" in c.text or "NOT_FOUND" in c.text)


def _read(ctx, project_id, project, region):
    c = ctx.read(policy_command(project_id, project, region))
    return c, (json_object(c.out) or json_object(c.text)) if c.ok else None


def run(args, ctx):
    mode = args.get("mode") or DEFAULT_MODE
    shown_mode = mode if mode in ("plan", "apply") else DEFAULT_MODE

    def failed(sentence):
        return ctx.result("failed", {"granted": None}, cost=dict(COST), lines=[sentence],
                          mode=shown_mode)

    problem = validate(args)
    if problem:
        return failed(problem)
    project_id = args["projectId"]
    project = args["project"]
    region = args["region"]
    identity = args["identity"]
    member = "serviceAccount:%s" % identity
    resources = [{"type": "repository-binding", "id": "%s/%s/%s" % (project_id, region, project),
                  "name": project, "member": member, "role": WRITER}]

    def result(status, outputs, listed=True, pending=(), lines=()):
        return ctx.result(status, outputs, resources=resources if listed else [],
                          pending=pending, cost=dict(COST), lines=lines, mode=shown_mode)

    # Step 1: who may push.
    c, policy = _read(ctx, project_id, project, region)
    if not c.ok:
        if "NOT_FOUND:" in c.text and "Requested entity was not found" in c.text:
            return failed(MISSING % (project, region))
        return failed(READ_FAILED % project_id)
    if policy is None:
        return failed(READ_FAILED % project_id)
    where = "the repository %s in %s" % (project, region)

    # Step 2.
    if granted(policy, member):
        return result("unchanged", {"granted": True},
                      lines=["The account %s may already push to %s; nothing was changed."
                             % (identity, where)])
    argv = grant_command(project_id, project, region, member)
    if common.write_refusal(SKILL, argv, root=ctx.root):
        return failed(UNUSABLE)
    before = "The account %s may not push to %s." % (identity, where)
    if mode != "apply":
        return result("would-update", {"granted": False}, listed=False,
                      lines=[before, "A run with mode=apply would grant it the role %s on "
                                     "the repository %s, never on the GCP project."
                             % (WRITER, project)])

    # Step 3: the grant, polled while the new account is not visible yet.
    tries = 0
    while True:
        tries += 1
        c = ctx.write(argv)
        if c.ok:
            break
        if not not_visible_yet(c) or tries >= TRIES:
            return failed(GRANT_FAILED % identity)
        # A wait that cannot be run ends the poll as the tenth refusal does.
        if not ctx.wait():
            return failed(GRANT_FAILED % identity)

    # Step 4: read it back; it was granted, whatever this read shows.
    lines = [before, "It was granted the role %s on the repository %s." % (WRITER, project)]
    c, after = _read(ctx, project_id, project, region)
    now = granted(after, member) if after is not None else False
    pending = []
    if after is None or not now:
        pending.append({
            "item": "push access of %s read back" % identity, "reason": "manual",
            "how": "/%s:%s projectId=%s project=%s region=%s identity=%s role=push mode=plan"
                   % (PLUGIN, SKILL, project_id, project, region, identity)})
        lines.append("Its push access could not be confirmed: %s." % (
            "the repository's access could not be read back" if after is None
            else "the policy read back does not list it as a writer"))
    else:
        lines.append("It may push now.")
    return result("updated", {"granted": now if after is not None else False},
                  pending=pending, lines=lines)
