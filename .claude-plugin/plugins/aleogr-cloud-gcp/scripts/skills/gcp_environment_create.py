"""gcp_environment-create: create the GCP project of a project and environment (or the
shared platform project), link its billing account and verify it (mode=apply), or say
what a run would make (mode=plan, the default).

The specification is skills/gcp_environment-create/SKILL.md: the same check (the
describe skill, invoked), the same discovery reads in the same order (organization,
parent, the search by parent, billing account), the same create, link and
verification, the same states and the same result block.

Creating a project cannot be undone (its id is permanent): the create and the link run
only with mode=apply, only through ctx.write, and only after both commands passed the
allowlist of writes of this skill (checked in both modes, so a plan never announces a
write the apply refuses). No organization, folder or billing identifier is printed in
the answer or in the block, except inside `pending[].how`.
"""

import json
import re

import aleogr_common as common

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "environment-create"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply creates the project and links its billing, through ctx.write

SKILL = "gcp_environment-create"
PLUGIN = "aleogr-cloud-gcp"
DESCRIBE = "gcp_environment-describe"
COST = {"fixed": False, "notes": "project creation is free"}

_PROJECT = re.compile(r"^[a-z](?:[a-z0-9-]{0,12}[a-z0-9])?$")
_ENVIRONMENTS = ("dev", "hom", "prd")
PLACEHOLDER = "xxxx"

# Sentences. The SKILL.md fixes some word for word; the others are fixed here.
CREATE_FAILED = "The project could not be created; nothing was created."
PARENT_FOUND = "The first search had not seen project %s yet; the search by parent found it."
CREATED_BUT = "The create reported an error, but the project %s exists."
UNUSABLE = ("An identifier read from Google Cloud does not have the form this tooling allows "
            "in a command; nothing was changed.")


def _cause(c):
    """One sentence's cause of a failed gcloud command, with no raw error text."""
    t = c.text.lower()
    if c.code == 127 or "command not found" in t:
        return "gcloud is not installed"
    if ("auth login" in t or "credentials" in t or "reauthentication" in t
            or "not currently have an active account" in t):
        return "gcloud is not authenticated"
    if "service_disabled" in t or "has not been used" in t or "is disabled" in t:
        return "a Google Cloud API it needs is not enabled"
    if "403" in t or "permission" in t or "not authorized" in t or "forbidden" in t:
        return "the active gcloud account is not allowed to do it"
    return "gcloud failed"


def validate(args):
    """None, or the one sentence of the first rule broken ("Validate first")."""
    mode = args.get("mode", "plan")
    if mode not in ("plan", "apply"):
        return "mode must be plan or apply."
    platform = args.get("platform")
    if platform is not None and platform != "shared":
        return "platform must be absent or shared."
    root = args.get("root")
    if root is not None and root != "tst":
        return "root must be absent or tst."
    project = args.get("project") or ""
    environment = args.get("environment")
    if platform == "shared":
        if project != "shared":
            return "platform=shared needs project=shared."
        if environment is not None:
            return "platform=shared takes no environment."
        if root is not None:
            return "root is not allowed with platform=shared."
        return None
    for key in ("project", "environment"):
        if not args.get(key):
            return "%s is missing." % key
    if environment not in _ENVIRONMENTS:
        return "environment must be dev, hom or prd."
    if project in ("test", "shared"):
        return "project must not be test or shared."
    if not _PROJECT.match(project):
        return ("project must have 1 to 14 characters of a-z, 0-9 and -, start with a "
                "letter and not end with -.")
    return None


def outputs(project_id=None):
    return {"projectId": project_id}


def labels_of(args):
    if args.get("platform") == "shared":
        return {"aleogr-project": "shared", "aleogr-platform": "shared"}
    return {"aleogr-project": args["project"], "aleogr-environment": args["environment"]}


def resource(args, project_id):
    return {"type": "project", "id": project_id, "name": args["project"],
            "labels": labels_of(args)}


def project_id_for(args, suffix):
    if args.get("platform") == "shared":
        return "aleogr-shared-%s" % suffix
    return "aleogr-%s-%s-%s" % (args["environment"], args["project"], suffix)


def _lines(c):
    return [line.strip() for line in c.out.splitlines() if line.strip()]


def _bare(name):
    """`organizations/<id>`, `folders/<id>`, `billingAccounts/<id>`: the part after the
    slash."""
    return name.rsplit("/", 1)[-1]


# The commands, as the SKILL.md writes them.

def organizations_command():
    return ["gcloud", "organizations", "list", "--format=value(name)"]


def folders_command(scope_flag, scope_id, display_name):
    return ["gcloud", "resource-manager", "folders", "list", "%s=%s" % (scope_flag, scope_id),
            "--filter=displayName=%s" % display_name, "--format=value(name)"]


def parent_search_command(args, parent_type, parent_id):
    if parent_type == "organization":
        flt = ("parent.type=organization AND parent.id=%s AND labels.aleogr-project=shared "
               "AND labels.aleogr-platform=shared" % parent_id)
    else:
        flt = ("parent.type=folder AND parent.id=%s AND labels.aleogr-project=%s AND "
               "labels.aleogr-environment=%s" % (parent_id, args["project"],
                                                 args["environment"]))
    return ["gcloud", "projects", "list", "--filter=%s" % flt, "--format=value(projectId)"]


def billing_accounts_command():
    return ["gcloud", "billing", "accounts", "list", "--filter=open=true",
            "--format=value(name)"]


def billing_describe_command(project_id):
    return ["gcloud", "billing", "projects", "describe", project_id,
            "--format=value(billingEnabled)"]


def lifecycle_command(project_id):
    return ["gcloud", "projects", "describe", project_id, "--format=value(lifecycleState)"]


def create_command(args, project_id, parent_id):
    if args.get("platform") == "shared":
        return ["gcloud", "projects", "create", project_id, "--organization=%s" % parent_id,
                "--name=shared", "--labels=aleogr-project=shared,aleogr-platform=shared"]
    return ["gcloud", "projects", "create", project_id, "--folder=%s" % parent_id,
            "--name=%s %s" % (args["environment"], args["project"]),
            "--labels=aleogr-project=%s,aleogr-environment=%s" % (args["project"],
                                                                  args["environment"])]


def link_command(project_id, billing_id):
    return ["gcloud", "billing", "projects", "link", project_id,
            "--billing-account=%s" % billing_id]


def shown(argv):
    """A command as the owner runs it (`pending[].how`): the SKILL.md's quotes kept
    around a --format value."""
    out = []
    for a in argv:
        if a.startswith("--format=") and "(" in a:
            a = '--format="%s"' % a[len("--format="):]
        out.append(a)
    return " ".join(out)


class Stop(Exception):
    """A step ended the run with this Result."""

    def __init__(self, result):
        Exception.__init__(self)
        self.result = result


def run(args, ctx):
    problem = validate(args)
    if problem:
        return ctx.failed(problem, outputs(), cost=dict(COST))
    try:
        return _run(args, ctx)
    except Stop as stop:
        return stop.result


def _run(args, ctx):
    apply = args.get("mode") == "apply"
    shared = args.get("platform") == "shared"

    def failed(sentence, lines_before=()):
        raise Stop(ctx.result("failed", outputs(), cost=dict(COST),
                              lines=list(lines_before) + [sentence]))

    # Step 1: the check, by the describe skill (its block is input only).
    if shared:
        found = ctx.call(PLUGIN, DESCRIBE, {"project": "shared", "platform": "shared"})
    else:
        found = ctx.call(PLUGIN, DESCRIBE, {"project": args["project"],
                                            "environment": args["environment"]})
    out = found.get("outputs") if isinstance(found.get("outputs"), dict) else {}
    if found.get("status") == "failed" or out.get("exists") not in (True, False):
        answer = found.get("answer") or []
        cause = answer[0] if answer and isinstance(answer[0], str) else (
            "The GCP project could not be looked up.")
        failed(cause)
    if out.get("exists") is True:
        if not isinstance(out.get("projectId"), str) or not out["projectId"]:
            failed("The GCP project could not be looked up.")
        project_id = out["projectId"]
        if out.get("billingLinked") is True:
            return unchanged(args, ctx, project_id, parent_type_of(out.get("parent")))
        # A project left without billing: step 4 only, then the repair.
        billing_id = billing_account(ctx, failed)
        return repair(args, ctx, apply, project_id, billing_id,
                      parent_type_of(out.get("parent")), [])

    # Step 2: the organization.
    organization_id = one_of(ctx, organizations_command(), "organization", "organizations",
                             "The organization could not be read", failed)

    # Step 3: the parent. This skill never creates folders.
    if shared:
        parent_type, parent_id = "organization", organization_id
        parent_words = "under the organization"
    elif args.get("root") == "tst":
        tst_id = one_of(ctx, folders_command("--organization", organization_id, "tst"),
                        "folder tst", "folders tst",
                        "The folder tst could not be read", failed,
                        empty="The folder tst must be created first under the organization; "
                              "nothing was created.")
        parent_id = one_of(ctx, folders_command("--folder", tst_id, args["environment"]),
                           "folder %s inside tst" % args["environment"],
                           "folders %s inside tst" % args["environment"],
                           "The folder %s inside tst could not be read" % args["environment"],
                           failed,
                           empty="The folder %s inside tst must be created first; nothing "
                                 "was created." % args["environment"])
        parent_type = "folder"
        parent_words = "in the folder %s inside tst" % args["environment"]
    else:
        parent_id = one_of(ctx, folders_command("--organization", organization_id,
                                                args["environment"]),
                           "folder %s" % args["environment"],
                           "folders %s" % args["environment"],
                           "The folder %s could not be read" % args["environment"], failed,
                           empty="The folder %s must be created first under the "
                                 "organization; nothing was created." % args["environment"])
        parent_type = "folder"
        parent_words = "in the folder %s" % args["environment"]

    # The search by parent, alone, before step 4.
    c = ctx.read(parent_search_command(args, parent_type, parent_id))
    if not c.ok:
        failed("The projects of the parent could not be searched: %s; nothing was created."
               % _cause(c))
    seen = _lines(c)
    if len(seen) > 1:
        failed("%d projects with these labels were found in the parent and none was "
               "picked; nothing was created." % len(seen))
    if len(seen) == 1:
        project_id = seen[0]
        first = [PARENT_FOUND % project_id]
        c = ctx.read(billing_describe_command(project_id))
        if not c.ok:
            failed("The billing of the project %s could not be read: %s."
                   % (project_id, _cause(c)), first)
        if c.out.strip() == "True":
            return unchanged(args, ctx, project_id, parent_type, first)
        billing_id = billing_account(ctx, failed, first)
        return repair(args, ctx, apply, project_id, billing_id, parent_type, first)

    # Step 4: the billing account.
    billing_id = billing_account(ctx, failed)

    # Both writes are checked before any is made, in both modes.
    planned = project_id_for(args, PLACEHOLDER)
    for argv in (create_command(args, planned, parent_id), link_command(planned, billing_id)):
        if common.write_refusal(SKILL, argv, root=ctx.root):
            failed(UNUSABLE)

    # Step 5: plan ends here.
    if not apply:
        return ctx.result("would-create", outputs(), resources=[resource(args, planned)],
                          cost=dict(COST), lines=[
                              "mode=apply would create the GCP project %s %s (parent type "
                              "%s) and link it to the open billing account."
                              % (planned, parent_words, parent_type)])

    # Step 6: create the project.
    project_id = project_id_for(args, common.random_name_part(4))
    lines = []
    c = ctx.write(create_command(args, project_id, parent_id))
    if not c.ok:
        c = ctx.read(lifecycle_command(project_id))
        if not c.ok:
            failed(CREATE_FAILED)
        if lifecycle_state(c) != "ACTIVE":
            return pending(args, ctx, project_id, [
                "The project %s exists, but it is not active." % project_id],
                lifecycle_command(project_id))
        lines.append(CREATED_BUT % project_id)

    # Steps 7 and 8.
    return link_and_verify(args, ctx, project_id, billing_id, parent_type, lines, "created")


def lifecycle_state(c):
    """The state a `--format=value(lifecycleState)` read printed. A JSON object of the
    project (what a fixture that answers both describes of a project gives) is read for
    its `lifecycleState` too."""
    text = c.out.strip()
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except ValueError:
            return text
        state = data.get("lifecycleState") if isinstance(data, dict) else None
        return state if isinstance(state, str) else ""
    return text


def parent_type_of(parent):
    if isinstance(parent, str) and "/" in parent:
        kind = parent.split("/", 1)[0]
        return {"organizations": "organization", "folders": "folder"}.get(kind, kind)
    return "unknown"


def one_of(ctx, argv, one, many, read_failed, failed, empty=None):
    """Steps 2 and 3: exactly one line, its bare id; otherwise the run stops failed."""
    c = ctx.read(argv)
    if not c.ok:
        failed("%s: %s; nothing was created." % (read_failed, _cause(c)))
    found = _lines(c)
    if not found:
        failed(empty or ("No %s was found; nothing was created." % one))
    if len(found) > 1:
        failed("%d %s were found: say which %s to use. None was picked, and nothing was "
               "created." % (len(found), many, one))
    return _bare(found[0])


def billing_account(ctx, failed, lines_before=()):
    """Step 4: the bare id of the one open billing account."""
    c = ctx.read(billing_accounts_command())
    if not c.ok:
        failed("The billing accounts could not be read: %s; nothing was created."
               % _cause(c), lines_before)
    found = _lines(c)
    if not found:
        failed("No open billing account was found; nothing was created.", lines_before)
    if len(found) > 1:
        failed("%d open billing accounts were found: say which billing account to use. None "
               "was picked, and nothing was created." % len(found), lines_before)
    return _bare(found[0])


def unchanged(args, ctx, project_id, parent_type, lines_before=()):
    return ctx.result("unchanged", outputs(project_id), resources=[resource(args, project_id)],
                      cost=dict(COST), lines=list(lines_before) + [
                          "The GCP project %s already exists (parent type %s) and billing is "
                          "linked; nothing was changed." % (project_id, parent_type)])


def repair(args, ctx, apply, project_id, billing_id, parent_type, lines_before):
    """A project that exists without billing: would-update (plan), or step 7 (apply)."""
    if common.write_refusal(SKILL, link_command(project_id, billing_id), root=ctx.root):
        return ctx.result("failed", outputs(), cost=dict(COST),
                          lines=list(lines_before) + [UNUSABLE])
    if not apply:
        return ctx.result("would-update", outputs(project_id),
                          resources=[resource(args, project_id)], cost=dict(COST),
                          lines=list(lines_before) + [
                              "The GCP project %s exists (parent type %s), but billing is not "
                              "linked; mode=apply would link it to the open billing account."
                              % (project_id, parent_type)])
    return link_and_verify(args, ctx, project_id, billing_id, parent_type,
                           list(lines_before), "updated")


def pending(args, ctx, project_id, lines, how_argv=None, how=None, item="project"):
    return ctx.result("pending", outputs(project_id), resources=[resource(args, project_id)],
                      cost=dict(COST), lines=lines,
                      pending=[{"item": item, "reason": "manual",
                                "how": how if how is not None else shown(how_argv)}])


def link_and_verify(args, ctx, project_id, billing_id, parent_type, lines, done):
    # Step 7: link billing.
    link = link_command(project_id, billing_id)
    c = ctx.write(link)
    if not c.ok:
        what = ("The project %s was created, but its billing could not be linked."
                if done == "created" else
                "The billing of the project %s could not be linked.") % project_id
        return pending(args, ctx, project_id, lines + [what], how=" ".join(link),
                       item="billing")

    # Step 8: verify.
    c = ctx.read(lifecycle_command(project_id))
    if not c.ok or lifecycle_state(c) != "ACTIVE":
        return pending(args, ctx, project_id, lines + [
            "The project %s could not be verified as active." % project_id],
            lifecycle_command(project_id))
    c = ctx.read(billing_describe_command(project_id))
    if not c.ok or c.out.strip() != "True":
        return pending(args, ctx, project_id, lines + [
            "The billing of the project %s could not be verified as linked." % project_id],
            billing_describe_command(project_id), item="billing")
    if done == "created":
        lines = lines + ["The GCP project %s was created (parent type %s), and billing is "
                         "linked." % (project_id, parent_type)]
    else:
        lines = lines + ["The GCP project %s exists (parent type %s), and its billing is now "
                         "linked." % (project_id, parent_type)]
    return ctx.result(done, outputs(project_id), resources=[resource(args, project_id)],
                      cost=dict(COST), lines=lines)
