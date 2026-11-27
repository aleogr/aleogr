"""gcp-artifact-registry_cleanup-configure: set the cleanup policy of a project's image
repository (keep the <keep> most recent versions of each image, delete the rest, dry-run
off) when it differs (mode=apply), or say what differs (mode=plan, the default).

The specification is skills/gcp-artifact-registry_cleanup-configure/SKILL.md: the same
read, the same comparison, the same one set, the same read back, the same states and the
same result block. The policy file is the plugin's own files/cleanup-policy.json for
keep=5; for any other keep it is that file's content with the count replaced, written
for this run in a private folder of this process in the system's temporary folder
(ctx.write_temp_file, common.temp_file_path; the folder is made by the plan too, empty,
to name the path, and removed when the process ends), only in mode=apply, right before
the set. The set runs through ctx.write only; it is checked against this skill's
allowlist of writes in both modes before the plan announces it or the apply writes the
file.
"""

import json
import re

import aleogr_common as common

FAMILY = "registry"
PROVIDER = "gcp-artifact-registry"
ACTION = "cleanup-configure"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply sets the policy, through ctx.write only

SKILL = "gcp-artifact-registry_cleanup-configure"
PLUGIN = "aleogr-registry-gcp-artifact-registry"

COST = {"fixed": False, "notes": "no cost of its own; it caps the storage the repository keeps"}

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_PROJECT = re.compile(r"^[a-z]([a-z0-9-]{0,12}[a-z0-9])?$")
_REGION = re.compile(r"^[a-z]+(-[a-z]+)+[0-9]+$")
_KEEP = re.compile(r"^[1-9][0-9]?$")

SHIPPED_KEEP = 5
SHIPPED_COUNT = '"keepCount": 5'

MISSING = ("The repository %s does not exist in %s: create it first with "
           "gcp-artifact-registry_repository-create.")
READ_FAILED = ("The repository could not be read; nothing was changed. Check that the GCP "
               "project %s exists, that the Artifact Registry API is enabled in it, and that "
               "the active gcloud account is signed in and may read its repositories.")
SET_FAILED = ("The cleanup policy could not be set; nothing was changed. Check that the "
              "active gcloud account may change the repository.")
# Fixed sentences the SKILL.md leaves free.
UNUSABLE = ("The cleanup policy cannot be set with these arguments: the command is not one "
            "this skill may run; nothing was changed.")
FILE_FAILED = "The policy file %s could not be written; nothing was changed."
POLICY_UNREADABLE = "The policy file %s of this plugin could not be read; nothing was changed."


def validate(args):
    """None, or the one sentence of the first argument missing or wrong."""
    for key in ("projectId", "project", "region", "keep"):
        if not args.get(key):
            return "%s is missing." % key
    if not _PROJECT_ID.match(args["projectId"]):
        return "projectId is not a GCP project id."
    if not _PROJECT.match(args["project"]):
        return ("project must have 1 to 14 lowercase letters, digits and hyphens, starting "
                "with a letter.")
    if not _REGION.match(args["region"]):
        return "region is not a Google Cloud region name (such as us-central1)."
    if not _KEEP.match(args["keep"]) or not 1 <= int(args["keep"]) <= 50:
        return "keep must be a whole number from 1 to 50."
    if "mode" in args and args["mode"] not in ("plan", "apply"):
        return "mode must be plan or apply."
    return None


def temp_name(keep):
    return "aleogr-cleanup-policy-keep-%d.json" % keep


def policy_path(ctx, keep):
    """<policy file>: the plugin's own file for keep=5, else the temporary file's path,
    in this process's private folder of the system's temporary folder (made now; None
    when it cannot be made)."""
    if keep == SHIPPED_KEEP:
        return ctx.plugin_path("files", "cleanup-policy.json")
    return common.temp_file_path(temp_name(keep))


def policy_text(shipped, keep):
    """The content of <policy file>: the shipped content, with the number 5 replaced by
    <keep> and nothing else changed."""
    if keep == SHIPPED_KEEP:
        return shipped
    return shipped.replace(SHIPPED_COUNT, '"keepCount": %d' % keep, 1)


def describe_command(project_id, project, region):
    """Steps 1 and 4, as the SKILL.md writes them."""
    return ["gcloud", "artifacts", "repositories", "describe", project,
            "--location=%s" % region, "--project=%s" % project_id, "--format=json"]


def set_command(project_id, project, region, path):
    """Step 3, as the SKILL.md writes it (the --policy value is one argument)."""
    return ["gcloud", "artifacts", "repositories", "set-cleanup-policies", project,
            "--location=%s" % region, "--project=%s" % project_id, "--policy=%s" % path,
            "--no-dry-run"]


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


def _number(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v == int(v) else v
    try:
        return int(str(v).strip())
    except ValueError:
        return None


def _upper(v):
    return v.upper() if isinstance(v, str) else v


def _dry_run(data):
    v = data.get("cleanupPolicyDryRun")
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return v is True


def _is_keep_entry(p):
    """action KEEP with mostRecentVersions without packageNamePrefixes (the `keep`
    output's entry)."""
    mrv = p.get("mostRecentVersions")
    return (_upper(p.get("action")) == "KEEP" and isinstance(mrv, dict)
            and "packageNamePrefixes" not in mrv)


def _keep_matches(p, keep):
    return (_is_keep_entry(p) and _number(p["mostRecentVersions"].get("keepCount")) == keep
            and "condition" not in p)


def _delete_matches(p):
    cond = p.get("condition")
    return (_upper(p.get("action")) == "DELETE" and isinstance(cond, dict)
            and list(cond.keys()) == ["tagState"] and _upper(cond["tagState"]) == "ANY"
            and "mostRecentVersions" not in p)


class Policy(object):
    """What "Comparing the policy" reads from a describe's JSON."""

    def __init__(self, data, keep):
        policies = data.get("cleanupPolicies")
        self.present = isinstance(policies, dict)
        values = [p for p in (policies.values() if self.present else ())]
        entries = [p for p in values if isinstance(p, dict)]
        keeps = [p for p in entries if _is_keep_entry(p)]
        self.keep = (_number(keeps[0]["mostRecentVersions"].get("keepCount"))
                     if len(keeps) == 1 else None)
        self.dry_run = _dry_run(data)
        self.rules = len(values)
        self.has_keep = any(_keep_matches(p, keep) for p in entries)
        self.has_delete = any(_delete_matches(p) for p in entries)
        self.keep_rules = len(keeps)
        self.as_declared = (self.present and len(values) == 2 and len(entries) == 2
                            and ((_keep_matches(entries[0], keep) and _delete_matches(entries[1]))
                                 or (_keep_matches(entries[1], keep)
                                     and _delete_matches(entries[0])))
                            and not self.dry_run)

    def outputs(self):
        return {"keep": self.keep, "dryRun": self.dry_run}

    def found(self):
        """The policy as found, as the end of a sentence."""
        if not self.present or self.rules == 0:
            return "no cleanup policy"
        if self.keep is None:
            keep = "no single rule says how many versions it keeps"
        else:
            keep = "keeps the %d most recent versions of each image" % self.keep
        rest = "deletes the rest" if self.has_delete else "does not delete the rest"
        return "%s, %s, dry-run %s, %d rule%s" % (
            keep, rest, "on" if self.dry_run else "off", self.rules,
            "" if self.rules == 1 else "s")

    def differences(self, keep):
        """What differs, one sentence each."""
        if not self.present or self.rules == 0:
            return ["No rule is set."]
        out = []
        if not self.has_keep:
            if self.keep is not None and self.keep != keep:
                out.append("It keeps %d versions, not %d." % (self.keep, keep))
            else:
                out.append("The rule that keeps the %d most recent versions is missing." % keep)
        if not self.has_delete:
            out.append("The rule that deletes the rest is missing.")
        if self.rules > 2:
            out.append("It has %d rules, not 2: a rule too many." % self.rules)
        if self.dry_run:
            out.append("Dry-run is on, so it deletes nothing.")
        if not out:
            out.append("Its rules are not the two declared ones.")
        return out


def content_lines(path, text):
    return ["The policy file %s:" % path, "```json"] + text.rstrip("\n").split("\n") + ["```"]


def _read(ctx, project_id, project, region):
    """(Completed, JSON object or None)."""
    c = ctx.read(describe_command(project_id, project, region))
    data = (json_object(c.out) or json_object(c.text)) if c.ok else None
    return c, data


def run(args, ctx):
    mode = args.get("mode") or DEFAULT_MODE
    shown_mode = mode if mode in ("plan", "apply") else DEFAULT_MODE

    def failed(sentence):
        return ctx.result("failed", {"keep": None, "dryRun": None}, cost=dict(COST),
                          lines=[sentence], mode=shown_mode)

    problem = validate(args)
    if problem:
        return failed(problem)
    project_id = args["projectId"]
    project = args["project"]
    region = args["region"]
    keep = int(args["keep"])
    resources = [{"type": "cleanup-policy", "id": "%s/%s/%s" % (project_id, region, project),
                  "name": project}]

    def result(status, outputs, pending=(), lines=()):
        return ctx.result(status, outputs, resources=resources, pending=pending,
                          cost=dict(COST), lines=lines, mode=shown_mode)

    # Step 1: the repository and its policy.
    c, data = _read(ctx, project_id, project, region)
    if not c.ok:
        if "NOT_FOUND:" in c.text and "Requested entity was not found" in c.text:
            return failed(MISSING % (project, region))
        return failed(READ_FAILED % project_id)
    if data is None:
        return failed(READ_FAILED % project_id)
    policy = Policy(data, keep)
    head = ["The repository %s in %s." % (project, region),
            "Policy found: %s." % policy.found()]

    # Step 2.
    if policy.as_declared:
        return result("unchanged", policy.outputs(),
                      lines=head + ["It is as declared (keep %d, delete the rest, dry-run "
                                    "off); nothing was changed." % keep])

    path = policy_path(ctx, keep)
    if path is None:
        # The private temporary folder could not be made: no file can be written.
        return failed(FILE_FAILED % temp_name(keep))
    argv = set_command(project_id, project, region, path)
    if common.write_refusal(SKILL, argv, root=ctx.root):
        return failed(UNUSABLE)
    shipped_path = ctx.plugin_path("files", "cleanup-policy.json")
    try:
        with open(shipped_path, encoding="utf-8") as f:
            shipped = f.read()
    except (OSError, UnicodeDecodeError):
        return failed(POLICY_UNREADABLE % shipped_path)
    if shipped.count(SHIPPED_COUNT) != 1:
        return failed(POLICY_UNREADABLE % shipped_path)
    text = policy_text(shipped, keep)
    would = ("keep the %d most recent versions of each image and delete the rest, with "
             "dry-run off" % keep)
    head += policy.differences(keep)

    if mode != "apply":
        return result("would-update", policy.outputs(),
                      lines=head + ["A run with mode=apply would set both rules: %s." % would]
                      + content_lines(path, text))

    # Step 3: the file (only for a keep other than 5), right before the set.
    if keep != SHIPPED_KEEP:
        if ctx.write_temp_file(temp_name(keep), text) is None:
            return failed(FILE_FAILED % path)
    c = ctx.write(argv)
    if not c.ok:
        return failed(SET_FAILED)

    # Step 4: read it back; it was set, whatever this read shows.
    lines = head + ["Both rules were set: %s." % would] + content_lines(path, text)
    _, data = _read(ctx, project_id, project, region)
    after = Policy(data, keep) if data is not None else None
    outputs = (after or policy).outputs()
    if after is None:
        lines.append("The policy could not be read back to confirm it.")
    else:
        lines.append("Policy read back: %s." % after.found())
        if not after.as_declared:
            lines.append("The policy read back is not the declared one.")
    pending = []
    if after is None or not after.as_declared:
        pending.append({
            "item": "cleanup policy of %s read back" % project, "reason": "manual",
            "how": "/%s:%s projectId=%s project=%s region=%s keep=%d mode=plan"
                   % (PLUGIN, SKILL, project_id, project, region, keep)})
    return result("updated", outputs, pending=pending, lines=lines)
