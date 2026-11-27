"""gcp_login-setup: prepare the login of the organization as far as a command can: grant
the active gcloud account roles/iap.settingsAdmin on the organization, enable the IAP
API in the shared project (mode=apply), and print the list of what is left to the owner;
or say what a run would do (mode=plan, the default).

The specification is skills/gcp_login-setup/SKILL.md: the same reads in the same order,
the same grant and enable, the same read after the change (polled with the shared wait
helper, at most 10 reads after the grant, 9 waits), the same sentences word for word,
the same list and the same result block.

The client's secret never passes through this module: it prints the owner's command of
item 3 as text and never runs it, never runs `gcloud iap settings set`, never reads,
builds or prints a client id or a secret. The setting's read is used only for whether
it names a client. No organization id and no e-mail is printed in the answer or the
block (they appear only in the `+ ` lines of the commands run).
"""

import json
import re

import aleogr_common as common

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "login-setup"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply grants the role and enables the API, through ctx.write

SKILL = "gcp_login-setup"
ROLE = "roles/iap.settingsAdmin"
COST = {"fixed": False, "notes": "the role and the API are free"}
MAX_READS_AFTER_GRANT = 10

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")

# The sentences the SKILL.md writes word for word.
PROJECT_MISSING = "projectId is missing."
PROJECT_INVALID = "projectId is not a valid GCP project id."
MODE_INVALID = "mode must be plan or apply."
NO_ORGANIZATION = ("No organization was found. Check that the active gcloud account is "
                   "signed in and belongs to an organization.")
SEVERAL_ORGANIZATIONS = "%d organizations were found and none was picked."
NO_ACCOUNT = "The active gcloud account could not be read. Run gcloud auth login."
POLICY_FAILED = ("The organization's access could not be read. Check that the active gcloud "
                 "account may read the organization's access.")
APIS_FAILED = ("The APIs of the GCP project %s could not be read. Check that the project "
               "exists and that the active gcloud account may read it.")
READ_API_OFF = "The organization's login setting could not be read: the IAP API is not on in %s."
READ_FAILED = ("The organization's login setting could not be read. Check that the active "
               "gcloud account is signed in and may read the organization's IAP settings.")
GRANT_FAILED = ("The role that changes the organization's login could not be granted; nothing "
                "was changed. The active gcloud account must be an administrator of the "
                "organization.")
ENABLE_FAILED_ALONE = "The IAP API could not be enabled in %s; nothing was changed."
ENABLE_FAILED_AFTER_GRANT = "The IAP API could not be enabled in %s."
AFTER_API_OFF = ("The organization's login setting could not be read: the IAP API is not on "
                 "in %s yet.")
AFTER_STILL_REFUSED = ("The role was granted, but the organization's login setting could not "
                       "be read yet.")
AFTER_NO_WAIT = ("The role was granted, but the wait for it to reach the read could not be "
                 "run; the organization's login setting could not be read yet.")
AFTER_FAILED = "The organization's login setting could not be read after the change."

# Fixed here (the SKILL.md leaves their wording to the answer).
UNUSABLE = ("The active gcloud account cannot be named in the grant this tooling allows (a "
            "user's e-mail address or a service account); nothing was changed.")
PREPARED = "The login of the organization is prepared."
PREPARED_NOTHING = "The login of the organization is already prepared; nothing was changed."
NOT_PREPARED = "The login of the organization is not prepared."
NOT_KNOWN = ("The login of the organization is not known yet: its setting cannot be read "
             "before the active account has the role and the IAP API is on.")
LIST_INTRO = "What is left to the owner:"

# The list of what is left, as the SKILL.md writes it ({p}: the shared project's id).
LIST = [
    "1. Consent screen: open https://console.cloud.google.com/auth/branding?project={p} and "
    "create it with app name aleogr, your own e-mail as the support and contact e-mail, and "
    "audience External. Add no logo and publish nothing.",
    "2. Client: open https://console.cloud.google.com/auth/clients?project={p} and create a "
    "client of type Web application named iap. When the console shows the client id and the "
    "client secret, copy both: the secret is shown only once. Keep them private; the next "
    "step asks for them. Then add to the client the authorized redirect URI "
    "https://iap.googleapis.com/v1/oauth/clientIds/<client id>:handleRedirect, with the "
    "client id in place of <client id>.",
    "3. Paste this command in a bash terminal (Cloud Shell). It asks for the client id and, "
    "without showing it, the client secret, sets the login on the organization, and removes "
    "its temporary file however it ends:",
    "( read -r -p \"Client id: \" CID; read -r -s -p \"Client secret: \" CSEC; echo; "
    "O=$(gcloud organizations list --format=\"value(name)\" | sed 's#.*/##'); F=$(mktemp); "
    "trap 'rm -f \"$F\"' EXIT; printf 'accessSettings:\\n  oauthSettings:\\n    clientId: "
    "%s\\n    clientSecret: %s\\n' \"$CID\" \"$CSEC\" > \"$F\"; gcloud iap settings set \"$F\" "
    "--organization=\"$O\" --billing-project={p} )",
    "4. Run /aleogr:platform-plan; its row login then reads prepared.",
]
COMMAND_LINE = 3  # the index of the owner's command in LIST

LOGIN_HOW = ("In the Google Cloud console of {p}, create the consent screen aleogr (External) "
             "and the web application client iap with its redirect address, paste the "
             "printed command in a terminal, then run /aleogr:platform-plan")
NOT_READ_ITEM = {"item": "login", "reason": "The login's setting could not be read.",
                 "how": "Wait a few minutes, then run /aleogr:platform-plan"}


def steps_of(project_id):
    """The lines of the list, `{p}` filled in with the shared project's id only."""
    return [line.replace("{p}", project_id) for line in LIST]


def login_item(project_id):
    return {"item": "login", "reason": "manual", "how": LOGIN_HOW.replace("{p}", project_id)}


def api_item(project_id):
    return {"item": "api", "reason": "The IAP API could not be enabled.",
            "how": "gcloud services enable iap.googleapis.com --project=%s" % project_id}


def list_lines(project_id):
    """The list as the answer prints it: the command of item 3 alone on its line, in a
    fenced block labelled bash."""
    steps = steps_of(project_id)
    return ([LIST_INTRO] + steps[:COMMAND_LINE] + ["```bash", steps[COMMAND_LINE], "```"]
            + steps[COMMAND_LINE + 1:])


def validate(args):
    if not args.get("projectId"):
        return PROJECT_MISSING
    if not _PROJECT_ID.match(args["projectId"]):
        return PROJECT_INVALID
    if args.get("mode", "plan") not in ("plan", "apply"):
        return MODE_INVALID
    return None


def outputs(prepared=None, role_granted=False, api_enabled=False, steps=()):
    return {"prepared": prepared, "roleGranted": role_granted, "apiEnabled": api_enabled,
            "steps": list(steps)}


# The commands, as the SKILL.md writes them.

def organizations_command():
    return ["gcloud", "organizations", "list", "--format=value(name)"]


def account_command():
    return ["gcloud", "config", "get-value", "account"]


def policy_command(organization_id, member):
    return ["gcloud", "organizations", "get-iam-policy", organization_id,
            "--flatten=bindings[].members",
            "--filter=bindings.role=%s AND bindings.members=%s" % (ROLE, member),
            "--format=value(bindings.members)"]


def api_command(project_id):
    return ["gcloud", "services", "list", "--enabled", "--project=%s" % project_id,
            "--filter=config.name=iap.googleapis.com", "--format=value(config.name)"]


def settings_command(organization_id, project_id):
    return ["gcloud", "iap", "settings", "get", "--organization=%s" % organization_id,
            "--billing-project=%s" % project_id, "--format=json"]


def grant_command(organization_id, member):
    return ["gcloud", "organizations", "add-iam-policy-binding", organization_id,
            "--member=%s" % member, "--role=%s" % ROLE, "--condition=None", "--quiet"]


def enable_command(project_id):
    return ["gcloud", "services", "enable", "iap.googleapis.com", "--project=%s" % project_id]


def member_of(account):
    if account.endswith(".gserviceaccount.com"):
        return "serviceAccount:%s" % account
    return "user:%s" % account


def names_client(c):
    """True when a successful read's accessSettings.oauthSettings.clientId is a non-empty
    string. Nothing else of the setting is kept."""
    if not c.out.strip():
        return False
    try:
        data = json.loads(c.out)
    except ValueError:
        return False
    access = data.get("accessSettings") if isinstance(data, dict) else None
    oauth = access.get("oauthSettings") if isinstance(access, dict) else None
    cid = oauth.get("clientId") if isinstance(oauth, dict) else None
    return isinstance(cid, str) and cid != ""


def first_read(c):
    """Step 5: "prepared", "not-prepared" or "refused" (any other non-zero exit)."""
    if c.ok:
        return "prepared" if names_client(c) else "not-prepared"
    if "NOT_FOUND" in c.text:
        return "not-prepared"
    return "refused"


def run(args, ctx):
    problem = validate(args)
    if problem:
        return ctx.failed(problem, outputs(), cost=dict(COST))
    project_id = args["projectId"]
    apply = args.get("mode") == "apply"

    def failed(sentence, prepared=None):
        return ctx.result("failed", outputs(prepared), cost=dict(COST), lines=[sentence])

    # Step 1: the organization.
    c = ctx.read(organizations_command())
    names = [line.strip() for line in c.out.splitlines() if line.strip()] if c.ok else []
    if not names:
        return failed(NO_ORGANIZATION)
    if len(names) > 1:
        return failed(SEVERAL_ORGANIZATIONS % len(names))
    organization_id = names[0].rsplit("/", 1)[-1]

    # Step 2: the active account.
    c = ctx.read(account_command())
    account = c.out.strip() if c.ok else ""
    if not account:
        return failed(NO_ACCOUNT)
    member = member_of(account)

    # Step 3: does the account have the role.
    c = ctx.read(policy_command(organization_id, member))
    if not c.ok:
        return failed(POLICY_FAILED)
    role_present = any(line.strip() == member for line in c.out.splitlines())

    # Step 4: is the IAP API on in the shared project.
    c = ctx.read(api_command(project_id))
    if not c.ok:
        return failed(APIS_FAILED % project_id)
    api_on = any(line.strip() == "iap.googleapis.com" for line in c.out.splitlines())

    # Step 5: the first read of the setting, once.
    c = ctx.read(settings_command(organization_id, project_id))
    state = first_read(c)
    if state == "prepared":
        return ctx.result("unchanged", outputs(True), cost=dict(COST), lines=[PREPARED_NOTHING])
    if state == "refused":
        if role_present and api_on:
            return failed(READ_API_OFF % project_id if "SERVICE_DISABLED" in c.text
                          else READ_FAILED)
        state = "not-known"

    # The grant is checked against the allowlist of writes in both modes, before
    # anything is announced or changed.
    if not role_present and common.write_refusal(SKILL, grant_command(organization_id, member),
                                                 root=ctx.root):
        return failed(UNUSABLE, prepared=False if state == "not-prepared" else None)

    presence = [
        ("The active gcloud account has the role %s on the organization." % ROLE)
        if role_present else
        ("The active gcloud account lacks the role %s on the organization." % ROLE),
        ("The IAP API is on in %s." % project_id) if api_on else
        ("The IAP API is off in %s." % project_id),
    ]

    # Step 6: plan ends here.
    if not apply:
        would = []
        if not role_present:
            would.append("grant the active gcloud account the role %s on the organization"
                         % ROLE)
        if not api_on:
            would.append("enable the IAP API in %s" % project_id)
        if state == "not-known":
            return ctx.result("would-update", outputs(None, not role_present, not api_on),
                              cost=dict(COST), lines=[NOT_KNOWN] + presence + [
                                  "mode=apply would %s, then check the login and give what "
                                  "is left." % " and ".join(would)])
        status = "would-update" if would else "pending"
        lines = [NOT_PREPARED] + presence
        if would:
            lines.append("mode=apply would %s." % " and ".join(would))
        return ctx.result(status, outputs(False, not role_present, not api_on,
                                          steps_of(project_id)),
                          cost=dict(COST), lines=lines + list_lines(project_id),
                          pending=[login_item(project_id)])

    # Step 7: the parts that are missing, in order.
    granted = enabled = False
    done = []
    if not role_present:
        c = ctx.write(grant_command(organization_id, member))
        if not c.ok:
            return failed(GRANT_FAILED, prepared=False if state == "not-prepared" else None)
        granted = True
        done.append("This run granted the active gcloud account the role %s on the "
                    "organization." % ROLE)
    else:
        done.append(presence[0])
    if not api_on:
        c = ctx.write(enable_command(project_id))
        if not c.ok:
            if not granted:
                return failed(ENABLE_FAILED_ALONE % project_id,
                              prepared=False if state == "not-prepared" else None)
            return ctx.result("updated", outputs(False if state == "not-prepared" else None,
                                                 True, False),
                              cost=dict(COST), lines=done + [ENABLE_FAILED_AFTER_GRANT
                                                             % project_id],
                              pending=[api_item(project_id)])
        enabled = True
        done.append("This run enabled the IAP API in %s." % project_id)
    else:
        done.append(presence[1])

    # Step 8: the read after the change, only when the first read did not answer.
    if state == "not-known":
        reads = 0
        while True:
            c = ctx.read(settings_command(organization_id, project_id))
            reads += 1
            if c.ok and names_client(c):
                return ctx.result("updated", outputs(True, granted, enabled), cost=dict(COST),
                                  lines=[PREPARED] + done)
            if c.ok or "NOT_FOUND" in c.text:
                break  # not prepared: step 9
            if "SERVICE_DISABLED" in c.text:
                return not_read(ctx, granted, enabled, done, AFTER_API_OFF % project_id)
            if "PERMISSION_DENIED" in c.text and granted:
                if reads >= MAX_READS_AFTER_GRANT:
                    return not_read(ctx, granted, enabled, done, AFTER_STILL_REFUSED)
                if not ctx.wait():
                    return not_read(ctx, granted, enabled, done, AFTER_NO_WAIT)
                continue
            return not_read(ctx, granted, enabled, done, AFTER_FAILED)

    # Step 9: not prepared: the list.
    status = "updated" if (granted or enabled) else "pending"
    return ctx.result(status, outputs(False, granted, enabled, steps_of(project_id)),
                      cost=dict(COST), lines=[NOT_PREPARED] + done + list_lines(project_id),
                      pending=[login_item(project_id)])


def not_read(ctx, granted, enabled, done, sentence):
    """The ends of step 8 where the login is not known after the change: `updated`, no
    list, the item `login` "not read"."""
    return ctx.result("updated", outputs(None, granted, enabled), cost=dict(COST),
                      lines=done + [sentence], pending=[dict(NOT_READ_ITEM)])
