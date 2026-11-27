"""gcp-artifact-registry_repository-create: create a project's Docker image repository in
Artifact Registry when it is missing (mode=apply), or say what a run would create
(mode=plan, the default).

The specification is skills/gcp-artifact-registry_repository-create/SKILL.md: the same
check (the describe skill, invoked), the same create, the same one read back, the same
states and the same result block. The create runs through ctx.write only, and only in
mode=apply; it is checked against this skill's allowlist of writes in both modes before
the plan announces it or the apply runs it.
"""

import json
import re

import aleogr_common as common

FAMILY = "registry"
PROVIDER = "gcp-artifact-registry"
ACTION = "repository-create"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply creates the repository, through ctx.write only

SKILL = "gcp-artifact-registry_repository-create"
PLUGIN = "aleogr-registry-gcp-artifact-registry"
DESCRIBE = "gcp-artifact-registry_registry-describe"

COST = {"fixed": False,
        "notes": "free up to 0.5 GB of storage, then about US$ 0.10 per GB a month"}
COST_LINE = ("An empty repository costs nothing: storage is free up to 0.5 GB, then about "
             "US$ 0.10 per GB a month.")

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_PROJECT = re.compile(r"^[a-z]([a-z0-9-]{0,12}[a-z0-9])?$")
_REGION = re.compile(r"^[a-z]+(-[a-z]+)+[0-9]+$")

CREATE_FAILED = ("The repository could not be created; nothing was changed. Check that the "
                 "Artifact Registry API is enabled in %s and that the active gcloud account "
                 "may create repositories in it.")
APPEARED = "The repository was created by another run between the check and the create."
NOT_CONFIRMED = ("The repository %s exists, but it could not be confirmed as a Docker "
                 "repository in %s.")
# One fixed sentence for a create that this skill's allowlist of writes would refuse
# (a value the validation lets through but the write shape does not).
UNUSABLE = ("The repository cannot be created with these arguments: the create command "
            "is not one this skill may run; nothing was changed.")
DESCRIBE_FAILED = "The repository %s could not be read; nothing was changed."


def validate(args):
    """None, or the one sentence of the first argument missing or wrong."""
    for key in ("projectId", "project", "environment", "region"):
        if not args.get(key):
            return "%s is missing." % key
    if not _PROJECT_ID.match(args["projectId"]):
        return "projectId is not a GCP project id."
    if not _PROJECT.match(args["project"]):
        return ("project must have 1 to 14 lowercase letters, digits and hyphens, starting "
                "with a letter.")
    if args["environment"] not in ("dev", "hom", "prd"):
        return "environment must be dev, hom or prd."
    if not _REGION.match(args["region"]):
        return "region is not a Google Cloud region name (such as us-central1)."
    if "mode" in args and args["mode"] not in ("plan", "apply"):
        return "mode must be plan or apply."
    return None


def labels_of(project, environment):
    return {"aleogr-project": project, "aleogr-environment": environment}


def create_command(project_id, project, environment, region):
    """Step 3, as the SKILL.md writes it (the --labels value is one argument)."""
    return ["gcloud", "artifacts", "repositories", "create", project,
            "--project=%s" % project_id, "--location=%s" % region,
            "--repository-format=docker",
            "--labels=aleogr-project=%s,aleogr-environment=%s" % (project, environment)]


def read_back_command(project_id, project, region):
    """Step 4, as the SKILL.md writes it."""
    return ["gcloud", "artifacts", "repositories", "describe", project,
            "--location=%s" % region, "--project=%s" % project_id,
            "--format=json(name,format,labels)"]


def image_path(project_id, project, region):
    return "%s-docker.pkg.dev/%s/%s" % (region, project_id, project)


def json_object(text):
    """The JSON object in `text`, which may follow lines such as `Encryption: ...`."""
    text = text or ""
    for m in re.finditer(r"(?m)^\{", text):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _read_back(ctx, project_id, project, region):
    """Step 4's read: the JSON object, or None (a non-zero exit or no JSON)."""
    c = ctx.read(read_back_command(project_id, project, region))
    if not c.ok:
        return None
    return json_object(c.out) or json_object(c.text)


def _labels(data):
    labels = data.get("labels") if isinstance(data, dict) else None
    return labels if isinstance(labels, dict) else {}


def run(args, ctx):
    mode = args.get("mode") or DEFAULT_MODE
    shown_mode = mode if mode in ("plan", "apply") else DEFAULT_MODE

    def result(status, path=None, resources=(), pending=(), lines=()):
        return ctx.result(status, {"imagePath": path}, resources=resources, pending=pending,
                          cost=dict(COST), lines=lines, mode=shown_mode)

    def failed(sentence):
        return result("failed", lines=[sentence])

    problem = validate(args)
    if problem:
        return failed(problem)
    project_id = args["projectId"]
    project = args["project"]
    environment = args["environment"]
    region = args["region"]
    path = image_path(project_id, project, region)
    rid = "%s/%s/%s" % (project_id, region, project)

    def resource(labels):
        return [{"type": "repository", "id": rid, "name": project, "labels": labels}]

    # Step 1: the check, by the describe skill (its block is input only).
    found = ctx.call(PLUGIN, DESCRIBE,
                     {"projectId": project_id, "project": project, "region": region})
    out = found.get("outputs") if isinstance(found.get("outputs"), dict) else {}
    if found.get("status") == "failed" or out.get("exists") not in (True, False):
        answer = found.get("answer") or []
        cause = answer[0] if answer and isinstance(answer[0], str) else (
            DESCRIBE_FAILED % project)
        return failed(cause)
    if out.get("exists") is True:
        if out.get("format") == "DOCKER":
            labels = out.get("labels") if isinstance(out.get("labels"), dict) else {}
            shown_path = out.get("imagePath") or path
            return result("unchanged", shown_path, resource(labels),
                          lines=["The repository %s already exists in %s, as a Docker "
                                 "repository; nothing was changed." % (project, region),
                                 "Image path: %s." % shown_path])
        how = ("fix by hand: the repository %s in %s is not a Docker repository; delete it, "
               "then run this skill again" % (project, region))
        return result("pending",
                      pending=[{"item": "repository %s" % project, "reason": "manual",
                                "how": how}],
                      lines=["The repository %s in %s is not a Docker repository, and a "
                             "repository's format cannot be changed: nothing was changed; "
                             "fix it by hand." % (project, region)])
    others = out.get("otherRegions") if isinstance(out.get("otherRegions"), list) else []
    if others:
        where = ", ".join(str(o) for o in others)
        how = ("fix by hand: the repository %s exists in %s, not in %s, and a repository has "
               "one region; delete it there (moving the images it holds first, if they are "
               "needed), or declare the region %s" % (project, where, region, where))
        return result("pending",
                      pending=[{"item": "repository %s in %s" % (project, where),
                                "reason": "manual", "how": how}],
                      lines=["The repository %s exists in %s, not in %s, and a repository "
                             "has one region: nothing was changed; fix it by hand."
                             % (project, where, region)])

    argv = create_command(project_id, project, environment, region)
    if common.write_refusal(SKILL, argv, root=ctx.root):
        return failed(UNUSABLE)
    labels = labels_of(project, environment)
    what = ("the repository %s, format Docker, in %s, with the labels aleogr-project=%s and "
            "aleogr-environment=%s" % (project, region, project, environment))

    # Step 2: the plan ends here.
    if mode != "apply":
        return result("would-create", path,
                      lines=["The repository %s does not exist in %s." % (project, region),
                             COST_LINE,
                             "A run with mode=apply would create %s." % what,
                             "Image path: %s." % path])

    # Step 3: create it (no --async: the command waits until it exists).
    c = ctx.write(argv)
    if not c.ok:
        if "ALREADY_EXISTS" not in c.text:
            return failed(CREATE_FAILED % project_id)
        data = _read_back(ctx, project_id, project, region)
        name = data.get("name") if isinstance(data, dict) else None
        if (isinstance(data, dict) and data.get("format") == "DOCKER"
                and isinstance(name, str) and ("locations/%s/" % region) in name + "/"):
            return result("unchanged", path, resource(_labels(data)),
                          lines=[APPEARED,
                                 "The repository %s is in %s, as a Docker repository."
                                 % (project, region),
                                 "Image path: %s." % path])
        return failed(NOT_CONFIRMED % (project, region))

    # Step 4: read it back; it was created, whatever this read shows.
    lines = [COST_LINE, "Created %s." % what]
    data = _read_back(ctx, project_id, project, region)
    pending = []
    if not (isinstance(data, dict) and data.get("format") == "DOCKER"
            and all(_labels(data).get(k) == v for k, v in labels.items())):
        pending.append({
            "item": "repository %s read back" % project, "reason": "manual",
            "how": "/%s:%s projectId=%s project=%s region=%s"
                   % (PLUGIN, DESCRIBE, project_id, project, region)})
        lines.append("Its format and labels could not be confirmed by reading it back.")
    lines.append("Image path: %s." % path)
    return result("created", path, resource(labels), pending=pending, lines=lines)
