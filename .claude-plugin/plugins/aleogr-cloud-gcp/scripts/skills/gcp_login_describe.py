"""gcp_login-describe: whether the login of the organization is prepared (its IAP setting
names an OAuth client). Read-only.

The specification is skills/gcp_login-describe/SKILL.md: the same reads, in the same
order, the same states, the same sentences and the same result block. No organization
id, client id or hash of a secret is ever printed.
"""

import json
import re

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "login-describe"
RESULT_MODE = "plan"  # the skill has no mode: its block always says plan

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")

INVALID_PROJECT = "projectId is not a valid GCP project id."
NO_ORGANIZATION = ("No organization was found. Check that the active gcloud account is "
                   "signed in and belongs to an organization.")
SEVERAL_ORGANIZATIONS = "%d organizations were found and none was picked."
API_OFF = ("The login of the organization could not be read: the IAP API is off in the "
           "project the read is counted against; /aleogr:platform-plan shows what preparing "
           "it would make and what it costs.")
NOT_YET = ("The login of the organization could not be read yet; /aleogr:platform-plan "
           "shows what preparing it would make and what it costs.")
READ_FAILED = ("The organization's login setting could not be read. Check that the active "
               "gcloud account is signed in and may read the organization's IAP settings.")
# The SKILL leaves these two to the answer; fixed here.
PREPARED = "The login of the organization is prepared."
NOT_PREPARED = ("The login of the organization is not prepared; /aleogr:platform-plan shows "
                "what preparing it would make and what it costs.")


def _outputs(prepared, readable, organization):
    return {"prepared": prepared, "readable": readable, "organization": organization}


def _client_id(data):
    """accessSettings.oauthSettings.clientId when it is a non-empty string, else None."""
    if not isinstance(data, dict):
        return None
    access = data.get("accessSettings")
    oauth = access.get("oauthSettings") if isinstance(access, dict) else None
    cid = oauth.get("clientId") if isinstance(oauth, dict) else None
    return cid if isinstance(cid, str) and cid != "" else None


def run(args, ctx):
    project_id = args.get("projectId")
    if project_id is not None and not _PROJECT_ID.match(project_id):
        return ctx.failed(INVALID_PROJECT, _outputs(None, None, False))

    # Step 1: the organization.
    c = ctx.read(["gcloud", "organizations", "list", "--format=value(name)"])
    names = [line.strip() for line in c.out.splitlines() if line.strip()] if c.ok else []
    if not names:
        return ctx.failed(NO_ORGANIZATION, _outputs(None, None, False))
    if len(names) > 1:
        return ctx.failed(SEVERAL_ORGANIZATIONS % len(names), _outputs(None, None, False))
    organization_id = names[0].rsplit("/", 1)[-1]

    # Step 2: the organization's IAP setting.
    argv = ["gcloud", "iap", "settings", "get", "--organization=%s" % organization_id]
    if project_id is not None:
        argv.append("--billing-project=%s" % project_id)
    argv.append("--format=json")
    c = ctx.read(argv)
    if not c.ok:
        text = c.text
        if "SERVICE_DISABLED" in text:
            return ctx.result("unchanged", _outputs(False, False, True), lines=[API_OFF])
        if "PERMISSION_DENIED" in text:
            return ctx.result("unchanged", _outputs(False, False, True), lines=[NOT_YET])
        if "NOT_FOUND" in text:
            return ctx.result("unchanged", _outputs(False, True, True), lines=[NOT_PREPARED])
        return ctx.failed(READ_FAILED, _outputs(None, None, True))
    data = {}
    if c.out.strip():
        try:
            data = json.loads(c.out)
        except ValueError:
            return ctx.failed(READ_FAILED, _outputs(None, None, True))
    if _client_id(data):
        return ctx.result("unchanged", _outputs(True, True, True), lines=[PREPARED])
    return ctx.result("unchanged", _outputs(False, True, True), lines=[NOT_PREPARED])
