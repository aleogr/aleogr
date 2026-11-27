"""gcp-cloud-sql_instance-switch-setup: the "switch" of the shared instance - a custom
role, a service account, its grants, a GitHub Actions workload identity pool and provider,
and the two Cloud Scheduler jobs that stop the instance at night. mode=plan only reads;
mode=apply creates what is missing, updates or resumes the jobs that differ, and verifies.

The specification is skills/gcp-cloud-sql_instance-switch-setup/SKILL.md: the same reads
in the order of the nine parts (a part whose dependency is missing is missing too, with no
command), the same change commands in the same order, the single retry of a job's creation
after about one minute (two waits of ctx.wait()), the same verification and the same
result block. The jobs' body is the plugin's own file files/stop-body.json, passed by its
real path, never inline. The project number and the e-mails appear only in the commands
shown and in the `GitHub secrets` section, never in the block.
"""

import json
import re

import aleogr_common as common

FAMILY = "db"
PROVIDER = "gcp-cloud-sql"
ACTION = "instance-switch-setup"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply only, through ctx.write

PLUGIN = "aleogr-db-gcp-cloud-sql"
SKILL = "gcp-cloud-sql_instance-switch-setup"
COST = {"fixed": False, "notes": "the switch has no cost of its own; the instance costs about "
                                 "R$ 50 per month while stopped"}

ROLE = "aleogrSharedSqlSwitch"
ACCOUNT_ID = "aleogr-shared-sql-switch"
POOL = "github"
PROVIDER_ID = "aleogr"
JOBS = (("job-weeknight", "aleogr-shared-stop-weeknight", "weeknightStop"),
        ("job-weekend", "aleogr-shared-stop-weekend", "weekendStop"))
PARTS = ("role", "account", "role-grant", "act-as", "pool", "provider", "federation-grant",
         "job-weeknight", "job-weekend")
PERMISSIONS = {"cloudsql.instances.get", "cloudsql.instances.update"}
SCOPE = "https://www.googleapis.com/auth/cloud-platform"
HEADERS = "Content-Type=application/json,X-HTTP-Method-Override=PATCH"
STOP_BODY = {"settings": {"activationPolicy": "NEVER"}}
JOB_FORMAT = ("--format=value(schedule,timeZone,state,httpTarget.uri,"
              "httpTarget.oauthToken.serviceAccountEmail,httpTarget.httpMethod,"
              "httpTarget.headers,httpTarget.body,httpTarget.oauthToken.scope,"
              "lastAttemptTime,status.code)")
RETRY_WAITS = 2  # "about one minute"

ARGS = ("projectId", "instance", "region", "timeZone", "weeknightStop", "weekendStop",
        "repository")

_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_INSTANCE = re.compile(r"^[a-z][a-z0-9-]{0,59}$")
_REGION = re.compile(r"^[a-z0-9-]+$")
_TIME_ZONE = re.compile(r"^[A-Za-z_]+/[A-Za-z_]+$")
_CRON = re.compile(r"^[0-9*,/-]+( [0-9*,/-]+){4}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")

NOT_RUNNABLE = ("These values cannot be passed to the commands of this skill (a region of at "
                "most 63 characters, a time zone of at most 64 characters on each side, cron "
                "fields of at most 40 characters, a repository of at most 100 characters on "
                "each side), so nothing was changed.")
NUMBER_FAILED = "The project number of %s could not be read; nothing was changed."
ACCOUNT_FAILED = "The active gcloud account could not be read; nothing was changed."


def _validate(args):
    for key in ARGS:
        if not args.get(key):
            return "%s is missing." % key
    if not _PROJECT_ID.match(args["projectId"]):
        return ("projectId is not valid: it must have 6 to 30 characters of a-z, 0-9 and -, "
                "start with a letter and not end with -.")
    if not _INSTANCE.match(args["instance"]):
        return ("instance is not valid: it must be lowercase letters, digits and -, "
                "start with a letter, at most 60 characters.")
    if not _REGION.match(args["region"]):
        return "region is not valid: it must be lowercase letters, digits and -."
    if not _TIME_ZONE.match(args["timeZone"]):
        return "timeZone is not valid: it must be Area/City, letters and _ on each side of one /."
    for key in ("weeknightStop", "weekendStop"):
        if not _CRON.match(args[key]):
            return ("%s is not valid: it must be five space-separated fields, each of digits, "
                    "*, ',', - and / only." % key)
    if not _REPOSITORY.match(args["repository"]):
        return ("repository is not valid: it must be <owner>/<repo>, each side of letters, "
                "digits, -, _ and ., with exactly one /.")
    if "mode" in args and args["mode"] not in ("plan", "apply"):
        return "mode must be plan or apply."
    return None


class Names(object):
    def __init__(self, args, number, active, body_file):
        p = args["projectId"]
        self.project = p
        self.instance = args["instance"]
        self.region = args["region"]
        self.time_zone = args["timeZone"]
        self.repository = args["repository"]
        self.crons = {"job-weeknight": args["weeknightStop"], "job-weekend": args["weekendStop"]}
        self.number = number
        self.active = active
        self.account = "%s@%s.iam.gserviceaccount.com" % (ACCOUNT_ID, p)
        self.uri = "https://sqladmin.googleapis.com/v1/projects/%s/instances/%s" % (
            p, self.instance)
        self.condition = ("assertion.repository=='%s' && assertion.ref=='refs/heads/main'"
                          % self.repository)
        self.principal = ("principalSet://iam.googleapis.com/projects/%s/locations/global/"
                          "workloadIdentityPools/github/attribute.repository/%s"
                          % (number, self.repository))
        self.body_file = body_file


# The reads of step 2, as the SKILL.md writes them.

def read_commands(n):
    p = "--project=%s" % n.project
    return {
        "role": ["gcloud", "iam", "roles", "describe", ROLE, p,
                 "--format=value(includedPermissions)"],
        "account": ["gcloud", "iam", "service-accounts", "describe", n.account, p,
                    "--format=value(email)"],
        "role-grant": ["gcloud", "projects", "get-iam-policy", n.project,
                       "--flatten=bindings[].members",
                       "--filter=bindings.role:roles/%s" % ROLE,
                       "--format=value(bindings.members)"],
        "account-policy": ["gcloud", "iam", "service-accounts", "get-iam-policy", n.account, p,
                           "--format=json"],
        "pool": ["gcloud", "iam", "workload-identity-pools", "describe", POOL, p,
                 "--location=global", "--format=value(state)"],
        "provider": ["gcloud", "iam", "workload-identity-pools", "providers", "describe",
                     PROVIDER_ID, p, "--location=global", "--workload-identity-pool=%s" % POOL,
                     "--format=value(attributeCondition)"],
    }


def job_describe_command(n, job):
    return ["gcloud", "scheduler", "jobs", "describe", job, "--project=%s" % n.project,
            "--location=%s" % n.region, JOB_FORMAT]


# The change commands of step 4, as the SKILL.md writes them.

def role_create(n):
    return ["gcloud", "iam", "roles", "create", ROLE, "--project=%s" % n.project,
            "--title=aleogr shared SQL switch",
            "--permissions=cloudsql.instances.get,cloudsql.instances.update", "--stage=GA",
            "--quiet"]


def account_create(n):
    return ["gcloud", "iam", "service-accounts", "create", ACCOUNT_ID, "--project=%s" % n.project,
            "--display-name=aleogr shared SQL switch", "--quiet"]


def role_grant(n):
    return ["gcloud", "projects", "add-iam-policy-binding", n.project,
            "--member=serviceAccount:%s" % n.account,
            "--role=projects/%s/roles/%s" % (n.project, ROLE), "--condition=None", "--quiet"]


def act_as_grant(n):
    return ["gcloud", "iam", "service-accounts", "add-iam-policy-binding", n.account,
            "--project=%s" % n.project, "--member=user:%s" % n.active,
            "--role=roles/iam.serviceAccountUser", "--quiet"]


def pool_create(n):
    return ["gcloud", "iam", "workload-identity-pools", "create", POOL,
            "--project=%s" % n.project, "--location=global", "--display-name=GitHub", "--quiet"]


def provider_create(n):
    return ["gcloud", "iam", "workload-identity-pools", "providers", "create-oidc", PROVIDER_ID,
            "--project=%s" % n.project, "--location=global",
            "--workload-identity-pool=%s" % POOL,
            "--issuer-uri=https://token.actions.githubusercontent.com",
            "--attribute-mapping=google.subject=assertion.sub,"
            "attribute.repository=assertion.repository,attribute.ref=assertion.ref",
            "--attribute-condition=%s" % n.condition, "--quiet"]


def federation_grant(n):
    return ["gcloud", "iam", "service-accounts", "add-iam-policy-binding", n.account,
            "--project=%s" % n.project, "--member=%s" % n.principal,
            "--role=roles/iam.workloadIdentityUser", "--quiet"]


def job_create(n, part, job):
    return ["gcloud", "scheduler", "jobs", "create", "http", job, "--project=%s" % n.project,
            "--location=%s" % n.region, "--schedule=%s" % n.crons[part],
            "--time-zone=%s" % n.time_zone, "--uri=%s" % n.uri, "--http-method=POST",
            "--headers=%s" % HEADERS, "--message-body-from-file=%s" % n.body_file,
            "--oauth-service-account-email=%s" % n.account, "--oauth-token-scope=%s" % SCOPE,
            "--max-retry-attempts=5", "--min-backoff=5m", "--max-backoff=15m",
            "--max-doublings=2", "--attempt-deadline=60s", "--quiet"]


def job_update(n, part, job):
    return ["gcloud", "scheduler", "jobs", "update", "http", job, "--project=%s" % n.project,
            "--location=%s" % n.region, "--schedule=%s" % n.crons[part],
            "--time-zone=%s" % n.time_zone, "--uri=%s" % n.uri, "--http-method=POST",
            "--update-headers=%s" % HEADERS, "--message-body-from-file=%s" % n.body_file,
            "--oauth-service-account-email=%s" % n.account, "--oauth-token-scope=%s" % SCOPE,
            "--quiet"]


def job_resume(n, job):
    return ["gcloud", "scheduler", "jobs", "resume", job, "--project=%s" % n.project,
            "--location=%s" % n.region, "--quiet"]


CREATES = {"role": role_create, "account": account_create, "role-grant": role_grant,
           "act-as": act_as_grant, "pool": pool_create, "provider": provider_create,
           "federation-grant": federation_grant}


def _missing_text(c):
    return "NOT_FOUND" in c.text or "404" in c.text


def _job_fields(text):
    line = (text or "").strip("\r\n").split("\n")[0]
    fields = line.split("\t")
    return fields + [""] * (11 - len(fields))


def _headers(text):
    return set(h.strip() for h in (text or "").split(";") if h.strip())


class Check(object):
    """What step 2 (or 5) read: each part's state ('equal', 'missing', 'different'),
    for a job also whether it needs an update and a resume, and the last runs that
    failed. `failure` names the part whose read failed (not a NOT_FOUND)."""

    def __init__(self):
        self.state = {}
        self.update = set()
        self.resume = set()
        self.last_failed = []
        self.failure = None

    def exists(self, part):
        return self.state.get(part) in ("equal", "different")

    def left(self):
        return [p for p in PARTS if self.state.get(p) != "equal"]

    def manual(self):
        return [p for p in ("role", "pool", "provider") if self.state.get(p) == "different"]


def check(ctx, n):
    """The reads of step 2, in the order of the parts."""
    k = Check()
    cmds = read_commands(n)

    def read(key):
        c = ctx.read(cmds[key])
        if c.ok:
            return c
        if _missing_text(c):
            return None
        k.failure = key
        return False

    c = read("role")
    if c is False:
        return k
    if c is None:
        k.state["role"] = "missing"
    else:
        perms = set(x for x in re.split(r"[;,\s]+", c.out.strip()) if x)
        k.state["role"] = "equal" if perms == PERMISSIONS else "different"

    c = read("account")
    if c is False:
        return k
    k.state["account"] = "missing" if c is None else "equal"

    if k.exists("role") and k.exists("account"):
        c = read("role-grant")
        if c is False:
            return k
        members = set(x.strip() for x in (c.out if c else "").splitlines())
        k.state["role-grant"] = ("equal" if c and "serviceAccount:%s" % n.account in members
                                 else "missing")
    else:
        k.state["role-grant"] = "missing"

    policy = None
    if k.exists("account"):
        c = read("account-policy")
        if c is False:
            return k
        if c is not None:
            try:
                policy = json.loads(c.out)
            except ValueError:
                k.failure = "account-policy"
                return k
        if not isinstance(policy, dict):
            policy = {}
        k.state["act-as"] = ("equal" if _bound(policy, "roles/iam.serviceAccountUser",
                                               "user:%s" % n.active) else "missing")
    else:
        k.state["act-as"] = "missing"

    c = read("pool")
    if c is False:
        return k
    if c is None:
        k.state["pool"] = "missing"
    else:
        k.state["pool"] = "equal" if c.out.strip() == "ACTIVE" else "different"

    if k.exists("pool"):
        c = read("provider")
        if c is False:
            return k
        if c is None:
            k.state["provider"] = "missing"
        else:
            k.state["provider"] = "equal" if c.out.strip() == n.condition else "different"
    else:
        k.state["provider"] = "missing"

    if k.exists("account") and k.exists("pool"):
        k.state["federation-grant"] = ("equal" if _bound(policy or {},
                                                         "roles/iam.workloadIdentityUser",
                                                         n.principal) else "missing")
    else:
        k.state["federation-grant"] = "missing"

    for part, job, _cron in JOBS:
        if not k.exists("account"):
            k.state[part] = "missing"
            continue
        c = ctx.read(job_describe_command(n, job))
        if not c.ok:
            if _missing_text(c):
                k.state[part] = "missing"
                continue
            k.failure = part
            return k
        f = _job_fields(c.out)
        headers = _headers(f[6])
        settings_equal = (
            f[0] == n.crons[part] and f[1] == n.time_zone and f[3] == n.uri
            and f[4] == n.account and f[5] == "POST"
            and "X-HTTP-Method-Override=PATCH" in headers
            and "Content-Type=application/json" in headers
            and common.json_from_base64(f[7]) == STOP_BODY and f[8] == SCOPE)
        if not settings_equal:
            k.update.add(part)
        if f[2] != "ENABLED":
            k.resume.add(part)
        k.state[part] = "equal" if settings_equal and f[2] == "ENABLED" else "different"
        code = f[10].strip()
        if code not in ("", "0"):
            k.last_failed.append(part)
    return k


def _bound(policy, role, member):
    bindings = policy.get("bindings") if isinstance(policy, dict) else None
    for b in bindings if isinstance(bindings, list) else []:
        if isinstance(b, dict) and b.get("role") == role:
            for m in b.get("members") or []:
                if isinstance(m, str) and m.lower() == member.lower():
                    return True
    return False


def planned(n, k):
    """The change commands the apply would run for this check, in order (a job's
    creation counted once)."""
    out = []
    for part in PARTS:
        if part in CREATES:
            if k.state.get(part) == "missing":
                out.append((part, "create", CREATES[part](n)))
            continue
        job = dict((p, j) for p, j, _c in JOBS)[part]
        if k.state.get(part) == "missing":
            out.append((part, "create", job_create(n, part, job)))
        elif k.state.get(part) == "different":
            if part in k.update:
                out.append((part, "update", job_update(n, part, job)))
            if part in k.resume:
                out.append((part, "resume", job_resume(n, job)))
    return out


def invocation(args, mode="apply"):
    parts = ["/%s:%s" % (PLUGIN, SKILL)]
    for key in ARGS:
        v = args[key]
        parts.append('%s="%s"' % (key, v) if " " in v else "%s=%s" % (key, v))
    parts.append("mode=%s" % mode)
    return " ".join(parts)


def manual_how(part, n):
    if part == "role":
        return ("The role %s of %s exists with other permissions: set its permissions by hand "
                "to exactly cloudsql.instances.get and cloudsql.instances.update (IAM, Roles), "
                "then run this skill again." % (ROLE, n.project))
    if part == "pool":
        return ("The workload identity pool %s of %s exists but is not ACTIVE: restore or fix "
                "it by hand (IAM, Workload Identity Federation), then run this skill again."
                % (POOL, n.project))
    return ("The provider %s of the pool %s exists with another attribute condition: set it by "
            "hand to %s (IAM, Workload Identity Federation), then run this skill again."
            % (PROVIDER_ID, POOL, n.condition))


RESOURCE_OF = {
    "role": {"type": "role", "id": ROLE, "name": ROLE, "labels": {}},
    "account": {"type": "service-account", "id": ACCOUNT_ID, "name": ACCOUNT_ID, "labels": {}},
    "pool": {"type": "workload-identity-pool", "id": POOL, "name": POOL, "labels": {}},
    "provider": {"type": "workload-identity-provider", "id": "%s/%s" % (POOL, PROVIDER_ID),
                 "name": PROVIDER_ID, "labels": {}},
    "job-weeknight": {"type": "scheduler-job", "id": JOBS[0][1], "name": JOBS[0][1],
                      "labels": {}},
    "job-weekend": {"type": "scheduler-job", "id": JOBS[1][1], "name": JOBS[1][1],
                    "labels": {}},
}


def resources(exists):
    return [dict(RESOURCE_OF[p]) for p in ("role", "account", "pool", "provider",
                                           "job-weeknight", "job-weekend") if p in exists]


def state_table(states):
    shown = {"equal": "present", "missing": "missing", "different": "different"}
    return common.render_table(["Part", "State"],
                               [[p, shown.get(states.get(p), "missing")] for p in PARTS])


def secrets_section(n):
    return ["", "GitHub secrets", "",
            "GCP_SHARED_PROJECT_ID: %s" % n.project,
            "GCP_SHARED_WIF_PROVIDER: projects/%s/locations/global/workloadIdentityPools/github/"
            "providers/aleogr" % n.number,
            "GCP_SHARED_SWITCH_ACCOUNT: %s" % n.account,
            "",
            "Paste them in the repository on GitHub: Settings, Secrets and variables, Actions, "
            "New repository secret."]


def last_run_lines(last_failed):
    jobs = dict((p, j) for p, j, _c in JOBS)
    return ["The last run of the job %s failed: the instance may have been left running."
            % jobs[p] for p in last_failed]


def run(args, ctx):
    mode = args.get("mode") or DEFAULT_MODE
    empty = {"ready": False, "missing": [], "lastRunFailed": []}
    problem = _validate(args)
    if problem:
        return ctx.failed(problem, dict(empty), cost=dict(COST),
                          mode=mode if mode in ("plan", "apply") else DEFAULT_MODE)
    project = args["projectId"]

    # Step 1: the project number and the active account.
    c = ctx.read(["gcloud", "projects", "describe", project, "--format=value(projectNumber)"])
    number = c.out.strip() if c.ok else ""
    if not number:
        return ctx.failed(NUMBER_FAILED % project, dict(empty), cost=dict(COST))
    c = ctx.read(["gcloud", "config", "get-value", "account"])
    active = c.out.strip() if c.ok else ""
    if not active:
        return ctx.failed(ACCOUNT_FAILED, dict(empty), cost=dict(COST))
    n = Names(args, number, active, ctx.plugin_path("files", "stop-body.json"))

    # Step 2: the parts.
    k = check(ctx, n)
    if k.failure:
        return ctx.failed("The part %s could not be read, so the switch was not checked; "
                          "nothing was changed." % _part_name(k.failure), dict(empty),
                          cost=dict(COST))

    # Every change the apply would run, checked against the allowlist in both modes.
    todo = planned(n, k)
    if any(common.write_refusal(SKILL, argv, root=ctx.root) for _p, _v, argv in todo):
        return ctx.failed(NOT_RUNNABLE, dict(empty), cost=dict(COST))

    if mode == "plan":
        return plan(ctx, args, n, k)
    return apply(ctx, args, n, k, todo)


def _part_name(key):
    return "act-as" if key == "account-policy" else key


def _outputs(k, left=None):
    left = k.left() if left is None else left
    return {"ready": not left, "missing": left, "lastRunFailed": list(k.last_failed)}


def _pending_items(args, n, left, manual):
    how = invocation(args)
    return [{"item": p, "reason": "manual", "how": manual_how(p, n) if p in manual else how}
            for p in left]


def plan(ctx, args, n, k):
    left = k.left()
    manual = k.manual()
    exists = [p for p in PARTS if k.exists(p)]
    if manual:
        status = "pending"
    elif any(k.state.get(p) == "missing" for p in PARTS):
        status = "would-create"
    elif left:
        status = "would-update"
    else:
        status = "unchanged"
    lines = state_table(k.state) + [""]
    lines.extend(manual_how(p, n) for p in manual)
    lines.extend(last_run_lines(k.last_failed))
    if left:
        lines.append("Not ready: missing or different: %s." % ", ".join(left))
    lines.append("This plan changed nothing.")
    if not left:
        lines.extend(secrets_section(n))
    pending = _pending_items(args, n, left, manual) if status == "pending" else []
    return ctx.result(status, _outputs(k), resources=resources(exists), cost=dict(COST),
                      pending=pending, lines=lines)


def apply(ctx, args, n, k, todo):
    exists = set(p for p in PARTS if k.exists(p))
    done = {}  # part -> "created" | "updated"
    ran = []  # the indexes in todo of the commands that succeeded
    created = False
    jobs = dict((p, j) for p, j, _c in JOBS)

    def not_done():
        """The parts left: not equal at the check, and not brought to equal by every
        command of theirs having run."""
        finished = set(p for p in PARTS
                       if any(t[0] == p for t in todo)
                       and all(i in ran for i, t in enumerate(todo) if t[0] == p))
        return [p for p in PARTS if k.state.get(p) != "equal" and p not in finished]

    def stop(sentence, part):
        """A change command failed: no later command, no verification."""
        left = not_done()
        status = "pending" if exists else "failed"
        if status == "failed":
            left = list(PARTS)
        lines = [sentence]
        if done:
            lines.append("This run made: %s." % ", ".join(sorted(done, key=PARTS.index)))
        lines.append("Not ready: missing or different: %s." % ", ".join(left))
        return ctx.result(status, {"ready": False, "missing": left,
                                   "lastRunFailed": list(k.last_failed)},
                          resources=resources(exists), cost=dict(COST),
                          pending=(_pending_items(args, n, left, k.manual())
                                   if status == "pending" else []),
                          lines=lines)

    for index, (part, verb, argv) in enumerate(todo):
        if verb == "create" and part in jobs:
            c = ctx.write(argv)
            if not c.ok:
                for _ in range(RETRY_WAITS):
                    if not ctx.wait():
                        left = not_done()
                        return ctx.result(
                            "pending", {"ready": False, "missing": left,
                                        "lastRunFailed": list(k.last_failed)},
                            resources=resources(exists), cost=dict(COST),
                            pending=[ctx.wait_budget_item()],
                            lines=["The job %s could not be created yet." % jobs[part],
                                   common.WAIT_BUDGET_SENTENCE])
                c = ctx.write(argv)
            if not c.ok:
                return stop("The part %s could not be created, also after one retry; nothing "
                            "later was run." % part, part)
        else:
            c = ctx.write(argv)
            if not c.ok:
                what = {"create": "created", "update": "updated", "resume": "resumed"}[verb]
                return stop("The part %s could not be %s; nothing later was run." % (part, what),
                            part)
        ran.append(index)
        if verb == "create":
            created = True
            exists.add(part)
            done[part] = "created"
        else:
            done.setdefault(part, "updated")

    # Step 5: verify, only when a change ran.
    if todo:
        v = check(ctx, n)
        if v.failure:
            left = not_done()
            return ctx.result("pending", {"ready": False, "missing": left,
                                          "lastRunFailed": list(k.last_failed)},
                              resources=resources(exists), cost=dict(COST),
                              pending=_pending_items(args, n, left, k.manual()),
                              lines=["The part %s could not be read to verify the switch."
                                     % _part_name(v.failure),
                                     "This run made: %s." % ", ".join(
                                         sorted(done, key=PARTS.index))])
        k = v
    left = k.left()
    exists = [p for p in PARTS if k.exists(p)]
    if left:
        status = "pending"
    elif not todo:
        status = "unchanged"
    elif created:
        status = "created"
    else:
        status = "updated"
    lines = state_table(k.state) + [""]
    if done:
        made = [p for p in PARTS if done.get(p) == "created"]
        changed = [p for p in PARTS if done.get(p) == "updated"]
        if made:
            lines.append("This run created: %s." % ", ".join(made))
        if changed:
            lines.append("This run updated: %s." % ", ".join(changed))
    else:
        lines.append("Nothing was changed.")
    lines.extend(manual_how(p, n) for p in k.manual())
    lines.extend(last_run_lines(k.last_failed))
    if left:
        lines.append("Not ready: missing or different: %s." % ", ".join(left))
    else:
        lines.extend(secrets_section(n))
    return ctx.result(status, _outputs(k), resources=resources(exists), cost=dict(COST),
                      pending=_pending_items(args, n, left, k.manual()) if left else [],
                      lines=lines)

