"""gcp_budget-alert-setup: create one budget alert on the whole billing account, or bring
an existing budget of the same display name to the amount and thresholds asked
(mode=apply); or say what a run would do (mode=plan, the default).

The rules are this module's, pinned by its unit tests
(tests/unit/test_gcp_budget_alert_setup.py) and its scenarios. It was built from
skills/gcp_budget-alert-setup/SKILL.md as that text was before the skill became a shell
over this command (the text is in the repository's history, at the commit before that
change): the same discovery of the billing account, the same list (in apply, retried
once after about one minute: two waits of the shared helper), the same create or update
and the same verification, the same states and the same result block. The create and the
update run only with mode=apply, through ctx.write, after the command passed the
allowlist of writes of this skill (checked in both modes, so a plan never announces a
write the apply refuses).

Neither the billing account id nor the budget id appears in the answer's prose or in
the block, except the billing account inside `pending[].how`, as the SKILL.md says.
"""

import decimal
import json
import re

import aleogr_common as common

FAMILY = "cloud"
PROVIDER = "gcp"
ACTION = "budget-alert-setup"
DEFAULT_MODE = "plan"
WRITES = True  # mode=apply creates or updates the budget, through ctx.write

SKILL = "gcp_budget-alert-setup"
COST = {"fixed": False, "notes": "a budget alert is free"}

_DISPLAY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,59}$")
_NUMBER = re.compile(r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_PROJECT_ID = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
REQUIRED = ("displayName", "amount", "currency", "thresholds", "quotaProject")

UNUSABLE = ("The amount, a threshold or the billing account does not have the form this "
            "tooling allows in the budget command (write numbers as plain decimals, such "
            "as 100 or 0.5); nothing was changed.")
ARROW = "→"


def _cause(c):
    """One sentence's cause of a failed gcloud command, with no raw error text."""
    t = c.text.lower()
    if c.code == 127 or "command not found" in t:
        return "gcloud is not installed"
    if ("auth login" in t or "credentials" in t or "reauthentication" in t
            or "not currently have an active account" in t):
        return "gcloud is not authenticated"
    if "service_disabled" in t or "has not been used" in t or "is disabled" in t \
            or "not enabled" in t:
        return "the Budget API is not enabled on the quota project"
    if "403" in t or "permission" in t or "not authorized" in t or "forbidden" in t:
        return "the active gcloud account is not allowed to do it"
    return "gcloud failed"


def _number(text):
    """A finite Decimal, or None."""
    if not _NUMBER.match(text):
        return None
    try:
        d = decimal.Decimal(text)
    except decimal.InvalidOperation:
        return None
    return d if d.is_finite() else None


def validate(args):
    """((amount, thresholds), None) or (None, the one sentence). The amount and each
    threshold as Decimal."""
    for key in REQUIRED:
        if not args.get(key):
            return None, "%s is missing." % key
    if not _DISPLAY_NAME.match(args["displayName"]):
        return None, ("displayName must start with a letter or a digit, have only letters, "
                      "digits, ., _ and -, and at most 60 characters.")
    amount = _number(args["amount"])
    if amount is None or amount <= 0:
        return None, "amount must be a number greater than 0."
    if not _CURRENCY.match(args["currency"]):
        return None, "currency must be three uppercase letters."
    thresholds = []
    for entry in args["thresholds"].split(","):
        t = _number(entry)
        if t is None or t <= 0 or t > 1:
            return None, ("thresholds must be a comma-separated list of numbers, each greater "
                          "than 0 and at most 1.")
        thresholds.append(t)
    if not _PROJECT_ID.match(args["quotaProject"]):
        return None, ("quotaProject must have 6 to 30 characters of a-z, 0-9 and -, start "
                      "with a letter and not end with -.")
    if args.get("mode", "plan") not in ("plan", "apply"):
        return None, "mode must be plan or apply."
    return (amount, thresholds), None


def _json_number(text):
    """An argument echoed as a JSON number: an int when it is written as one."""
    d = decimal.Decimal(text)
    if re.match(r"^[+-]?[0-9]+$", text):
        return int(d)
    return float(d)


def outputs(args, compared=None, differs=None):
    out = {"displayName": args["displayName"], "amount": _json_number(args["amount"]),
           "currency": args["currency"],
           "thresholds": [_json_number(t) for t in args["thresholds"].split(",")],
           "compared": compared}
    if differs is not None:
        out["differs"] = differs
    return out


FAILED_OUTPUTS = {"displayName": None, "amount": None, "currency": None, "thresholds": []}


def budget_resource(args):
    return {"type": "budget", "id": args["displayName"], "name": args["displayName"],
            "labels": {}}


# The commands, as the SKILL.md writes them.

def accounts_command():
    return ["gcloud", "billing", "accounts", "list", "--filter=open=true",
            "--format=value(name)"]


def list_command(billing_id, quota_project):
    return ["gcloud", "billing", "budgets", "list", "--billing-account=%s" % billing_id,
            "--billing-project=%s" % quota_project, "--format=value(displayName,name)"]


def list_how(billing_id, quota_project):
    return ('gcloud billing budgets list --billing-account=%s --billing-project=%s '
            '--format="value(displayName,name)"' % (billing_id, quota_project))


def create_command(args, billing_id):
    return (["gcloud", "billing", "budgets", "create", "--billing-account=%s" % billing_id,
             "--display-name=%s" % args["displayName"],
             "--budget-amount=%s%s" % (args["amount"], args["currency"])]
            + ["--threshold-rule=percent=%s" % t for t in args["thresholds"].split(",")]
            + ["--billing-project=%s" % args["quotaProject"]])


def describe_command(budget_id, billing_id, quota_project):
    return ["gcloud", "billing", "budgets", "describe", budget_id,
            "--billing-account=%s" % billing_id, "--billing-project=%s" % quota_project,
            "--format=json"]


def update_command(args, budget_id, billing_id):
    return (["gcloud", "billing", "budgets", "update", budget_id,
             "--billing-account=%s" % billing_id,
             "--budget-amount=%s%s" % (args["amount"], args["currency"]),
             "--clear-threshold-rules"]
            + ["--add-threshold-rule=percent=%s" % t for t in args["thresholds"].split(",")]
            + ["--billing-project=%s" % args["quotaProject"]])


def find_budget(text, display_name):
    """(found, resource name or None) of the first line whose display name (first
    column) equals display_name."""
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if parts[0].strip() == display_name:
            name = parts[1].strip() if len(parts) > 1 else ""
            return True, (name or None)
    return False, None


def read_budget(c):
    """((amount, currency, thresholds), None) or (None, a clause naming what is
    missing), from the output of the describe."""
    if not c.ok:
        return None, "its description could not be read"
    if not c.out.strip():
        return None, "its description was empty"
    try:
        data = json.loads(c.out, parse_float=decimal.Decimal)
    except ValueError:
        return None, "its description was not JSON"
    if not isinstance(data, dict):
        return None, "its description was not JSON"
    amount_obj = data.get("amount")
    spec = amount_obj.get("specifiedAmount") if isinstance(amount_obj, dict) else None
    if not isinstance(spec, dict):
        return None, "its amount was not found"
    units, nanos = spec.get("units"), spec.get("nanos")
    if units is None and nanos is None:
        return None, "its amount was not found"
    try:
        amount = decimal.Decimal(str(units if units is not None else 0))
        if nanos is not None:
            amount += decimal.Decimal(str(nanos)) / decimal.Decimal(10 ** 9)
    except decimal.InvalidOperation:
        return None, "its amount was not found"
    currency = spec.get("currencyCode")
    if not isinstance(currency, str) or not currency:
        return None, "its currency was not found"
    rules = data.get("thresholdRules")
    if not isinstance(rules, list) or not rules:
        return None, "its thresholds were not found"
    thresholds = []
    for rule in rules:
        p = rule.get("thresholdPercent") if isinstance(rule, dict) else None
        if isinstance(p, bool) or not isinstance(p, (int, decimal.Decimal)):
            return None, "its thresholds were not found"
        thresholds.append(decimal.Decimal(p))
    return (amount, currency, thresholds), None


def _plain(d):
    """A Decimal written plainly, without trailing zeros: 100, 0.5, 1."""
    text = format(d, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".") or "0"
    return text


def differences(asked, held):
    """The short strings of what differs (empty: all equal)."""
    amount, currency, thresholds = asked
    h_amount, h_currency, h_thresholds = held
    out = []
    if h_amount != amount:
        out.append("amount %s %s %s" % (_plain(h_amount), ARROW, _plain(amount)))
    if h_currency != currency:
        out.append("currency %s %s %s" % (h_currency, ARROW, currency))
    if set(h_thresholds) != set(thresholds):
        out.append("thresholds %s %s %s" % (", ".join(_plain(t) for t in h_thresholds), ARROW,
                                           ", ".join(_plain(t) for t in thresholds)))
    return out


def run(args, ctx):
    parsed, problem = validate(args)
    if problem:
        return ctx.failed(problem, dict(FAILED_OUTPUTS), cost=dict(COST))
    amount, thresholds = parsed
    asked = (amount, args["currency"], thresholds)
    apply = args.get("mode") == "apply"
    quota = args["quotaProject"]
    summary = ("Budget %s: %s %s, thresholds %s." % (args["displayName"], args["amount"],
                                                   args["currency"],
                                                   ", ".join(args["thresholds"].split(","))))

    def failed(sentence):
        return ctx.result("failed", dict(FAILED_OUTPUTS), cost=dict(COST), lines=[sentence])

    def result(status, out, sentence, resources=True, pending=()):
        return ctx.result(status, out, resources=[budget_resource(args)] if resources else [],
                          pending=pending, cost=dict(COST), lines=[summary, sentence])

    # Step 1: the billing account.
    c = ctx.read(accounts_command())
    if not c.ok:
        return failed("The billing accounts could not be read: %s; nothing was changed."
                      % _cause(c))
    accounts = [line.strip() for line in c.out.splitlines() if line.strip()]
    if not accounts:
        return failed("No open billing account was found; nothing was changed.")
    if len(accounts) > 1:
        return failed("%d open billing accounts were found: say which billing account to "
                      "use. None was picked, and nothing was changed." % len(accounts))
    billing_id = accounts[0].rsplit("/", 1)[-1]

    # Step 2: the existing budgets (in apply, one retry after about one minute).
    c = ctx.read(list_command(billing_id, quota))
    if not c.ok and apply:
        for _ in range(2):
            if not ctx.wait():
                return ctx.result("pending", outputs(args), cost=dict(COST),
                                  lines=[summary, common.WAIT_BUDGET_SENTENCE],
                                  pending=[ctx.wait_budget_item()])
        c = ctx.read(list_command(billing_id, quota))
    if not c.ok:
        return failed("The budgets of the billing account could not be listed: %s; nothing "
                      "was changed." % _cause(c))
    exists, resource_name = find_budget(c.out, args["displayName"])

    if exists:
        return existing(args, ctx, apply, asked, billing_id, resource_name, result, failed)

    if common.write_refusal(SKILL, create_command(args, billing_id), root=ctx.root):
        return failed(UNUSABLE)
    if not apply:
        return result("would-create", outputs(args), "No budget is named %s: mode=apply would "
                      "create it." % args["displayName"], resources=False)

    # Step 3: create it.
    c = ctx.write(create_command(args, billing_id))
    if not c.ok:
        return failed("The budget could not be created: %s; nothing was created." % _cause(c))

    # Step 4: verify, with the list of step 2.
    c = ctx.read(list_command(billing_id, quota))
    if not c.ok or not find_budget(c.out, args["displayName"])[0]:
        return result("pending", outputs(args), "The budget %s was created, but it could not "
                      "be confirmed." % args["displayName"],
                      pending=[{"item": "budget", "reason": "manual",
                                "how": list_how(billing_id, quota)}])
    return result("created", outputs(args), "The budget %s was created." % args["displayName"])


def existing(args, ctx, apply, asked, billing_id, resource_name, result, failed):
    """"Existing budget", steps a to d."""
    name = args["displayName"]
    quota = args["quotaProject"]

    def not_compared(what):
        return result("unchanged", outputs(args, compared=False),
                      "The budget %s exists, but it could not be compared: %s; "
                      "nothing was changed." % (name, what))

    # a. Read it.
    if resource_name is None:
        return not_compared("the list gave no resource name for it")
    budget_id = resource_name.rsplit("/", 1)[-1]
    held, missing = read_budget(ctx.read(describe_command(budget_id, billing_id, quota)))
    if held is None:
        return not_compared(missing)

    # b. Compare.
    differs = differences(asked, held)
    if not differs:
        return result("unchanged", outputs(args, compared=True),
                      "The budget %s already has this amount, currency and these thresholds; "
                      "nothing was changed." % name)

    if common.write_refusal(SKILL, update_command(args, budget_id, billing_id), root=ctx.root):
        return failed(UNUSABLE)

    # c. Different, plan.
    if not apply:
        return result("would-update", outputs(args, compared=True, differs=differs),
                      "The budget %s differs (%s): mode=apply would update it."
                      % (name, "; ".join(differs)))

    # d. Different, apply: update it, then read it again and compare again.
    c = ctx.write(update_command(args, budget_id, billing_id))
    if not c.ok:
        return failed("The budget %s could not be updated: %s; nothing was changed."
                      % (name, _cause(c)))
    held, missing = read_budget(ctx.read(describe_command(budget_id, billing_id, quota)))
    if held is None:
        return result("pending", outputs(args, compared=True),
                      "The budget %s was updated, but it could not be read again to confirm "
                      "it." % name,
                      pending=[{"item": "budget", "reason": "manual",
                                "how": "the budget %s could not be read again after the "
                                       "update (%s): run gcp_budget-alert-setup again with "
                                       "the same arguments" % (name, missing)}])
    still = differences(asked, held)
    if still:
        return result("pending", outputs(args, compared=True),
                      "The budget %s was updated, but it still differs (%s)."
                      % (name, "; ".join(still)),
                      pending=[{"item": "budget", "reason": "manual",
                                "how": "the budget %s still differs (%s): run "
                                       "gcp_budget-alert-setup again with the same arguments"
                                       % (name, "; ".join(still))}])
    return result("updated", outputs(args, compared=True),
                  "The budget %s was updated to this amount, currency and these thresholds."
                  % name)
