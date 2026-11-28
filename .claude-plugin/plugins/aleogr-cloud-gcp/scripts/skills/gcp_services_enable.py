"""gcp_services-enable: enable the Google APIs a GCP project needs, only the ones still
missing (mode=apply), or say which a run would enable (mode=plan, the default).

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_services_enable.py) and its scenarios. It was built from
skills/gcp_services-enable/SKILL.md as that text was before the skill became a shell
over this command (the text is in the repository's history, at the commit before that
change): the same check (the describe skill, invoked), the same comparison, one enable
for all the missing services, one verification, the same states and the same result
block. The enable runs only with mode=apply, through ctx.write, after the command passed
the allowlist of writes of this skill (checked in both modes, so a plan never announces
an enable the apply refuses). The SKILL.md prescribes no wait."""

import re

import aleogr_common as common

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "services-enable"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply enables services, through ctx.write

SKILL = "gcp_services-enable"
PLUGIN = "aleogr-cloud-gcp"
DESCRIBE = "gcp_environment-describe"
COST = {"fixed": False, "notes": "enabling APIs is free"}

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_SERVICE = re.compile(r"^[a-z0-9.-]*\.googleapis\.com$")
_ENVIRONMENTS = ("dev", "hom", "prd")

SERVICES_INVALID = ("services is not valid: every entry must end with .googleapis.com and "
                    "have only a-z, 0-9, - and . before it.")
UNUSABLE = ("A service name does not have the form this tooling allows in the enable "
            "command; nothing was enabled.")


def _cause(c):
    """One sentence's cause of a failed gcloud command, with no raw error text."""
    t = c.text.lower()
    if c.code == 127 or "command not found" in t:
        return "gcloud is not installed"
    if ("auth login" in t or "credentials" in t or "reauthentication" in t
            or "not currently have an active account" in t):
        return "gcloud is not authenticated"
    if "billing" in t:
        return "the project's billing does not allow it"
    if "403" in t or "permission" in t or "not authorized" in t or "forbidden" in t:
        return "the active gcloud account is not allowed to enable them"
    return "gcloud failed"


def validate(args):
    """(the services, deduplicated in order, None) or (None, the one sentence)."""
    if args.get("mode", "plan") not in ("plan", "apply"):
        return None, "mode must be plan or apply."
    if not args.get("services"):
        return None, "services is missing."
    project_id = args.get("projectId")
    if project_id is not None:
        if not _PROJECT_ID.match(project_id):
            return None, ("projectId must have 6 to 30 characters of a-z, 0-9 and -, start "
                          "with a letter and not end with -.")
    else:
        platform = args.get("platform")
        environment = args.get("environment")
        project = args.get("project") or ""
        if platform is not None and platform != "shared":
            return None, "platform must be absent or shared."
        if environment and environment not in _ENVIRONMENTS:
            return None, "environment must be dev, hom or prd."
        if platform == "shared":
            if project != "shared" or environment is not None:
                return None, "platform=shared needs project=shared and no environment."
        else:
            if project == "shared":
                return None, "project=shared needs platform=shared."
            for key in ("project", "environment"):
                if not args.get(key):
                    return None, "%s is missing." % key
    services = []
    for entry in args["services"].split(","):
        if not _SERVICE.match(entry):
            return None, SERVICES_INVALID
        if entry not in services:
            services.append(entry)
    return services, None


def outputs(project_id=None, enabled=(), already=()):
    return {"projectId": project_id, "enabled": list(enabled), "alreadyEnabled": list(already)}


def enable_command(missing, project_id):
    """Step 3, as the SKILL.md writes it."""
    return ["gcloud", "services", "enable"] + list(missing) + ["--project=%s" % project_id]


def verify_command(project_id):
    """Step 4, as the SKILL.md writes it."""
    return ["gcloud", "services", "list", "--enabled", "--project=%s" % project_id,
            "--format=value(config.name)"]


def verify_how(project_id):
    return ('gcloud services list --enabled --project=%s --format="value(config.name)"'
            % project_id)


def describe_args(args):
    if args.get("projectId") is not None:
        return {"projectId": args["projectId"]}
    if args.get("platform") == "shared":
        return {"project": "shared", "platform": "shared"}
    return {"project": args["project"], "environment": args["environment"]}


def run(args, ctx):
    services, problem = validate(args)
    if problem:
        return ctx.failed(problem, outputs(), cost=dict(COST))

    def failed(sentence):
        return ctx.result("failed", outputs(), cost=dict(COST), lines=[sentence])

    # Step 1: the project and its enabled services, by the describe skill.
    found = ctx.call(PLUGIN, DESCRIBE, describe_args(args))
    out = found.get("outputs") if isinstance(found.get("outputs"), dict) else {}
    if found.get("status") == "failed" or out.get("exists") not in (True, False):
        answer = found.get("answer") or []
        return failed(answer[0] if answer and isinstance(answer[0], str) else
                      "The GCP project could not be looked up.")
    if out.get("exists") is False:
        return failed("The GCP project does not exist: create the environment first with "
                      "gcp_environment-create; nothing was enabled.")
    project_id = out.get("projectId")
    enabled_now = out.get("enabledServices")
    if not isinstance(project_id, str) or not isinstance(enabled_now, list):
        return failed("The GCP project could not be looked up.")
    labels = out.get("labels") if isinstance(out.get("labels"), dict) else {}
    name = labels.get("aleogr-project") or args.get("project") or project_id
    resources = [{"type": "project", "id": project_id, "name": name, "labels": labels}]

    # Step 2: compare.
    already = [s for s in services if s in enabled_now]
    missing = [s for s in services if s not in enabled_now]
    already_line = ("These were already enabled: %s." % ", ".join(already)) if already else None
    if not missing:
        return ctx.result("unchanged", outputs(project_id, (), already), resources=resources,
                          cost=dict(COST), lines=[
                              "Every requested service is already enabled in the GCP project "
                              "%s: %s." % (project_id, ", ".join(already))])
    if common.write_refusal(SKILL, enable_command(missing, project_id), root=ctx.root):
        return failed(UNUSABLE)
    if args.get("mode") != "apply":
        return ctx.result("would-update", outputs(project_id, missing, already),
                          resources=resources, cost=dict(COST),
                          lines=["mode=apply would enable these services in the GCP project "
                                 "%s: %s." % (project_id, ", ".join(missing))]
                          + ([already_line] if already_line else []))

    # Step 3: one enable for all the missing services.
    c = ctx.write(enable_command(missing, project_id))
    if not c.ok:
        return failed("The services could not be enabled in the GCP project %s: %s; nothing "
                      "was enabled." % (project_id, _cause(c)))

    # Step 4: verify.
    lines = ["These services were enabled in the GCP project %s: %s."
             % (project_id, ", ".join(missing))] + ([already_line] if already_line else [])
    c = ctx.read(verify_command(project_id))
    listed = [line.strip() for line in c.out.splitlines() if line.strip()] if c.ok else []
    unconfirmed = [s for s in services if s not in listed] if c.ok else list(services)
    if unconfirmed:
        return ctx.result("pending", outputs(project_id, missing, already), resources=resources,
                          cost=dict(COST),
                          lines=lines + ["These services could not be confirmed as enabled: "
                                         "%s." % ", ".join(unconfirmed)],
                          pending=[{"item": "services", "reason": "manual",
                                    "how": verify_how(project_id)}])
    return ctx.result("updated", outputs(project_id, missing, already), resources=resources,
                      cost=dict(COST), lines=lines)
