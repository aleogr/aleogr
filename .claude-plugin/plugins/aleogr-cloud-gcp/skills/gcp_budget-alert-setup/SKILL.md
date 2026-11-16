---
description: Google Cloud (GCP) budget alert setup. Use to create one budget alert, with threshold rules, on the whole billing account, unless a budget with the same display name already exists. Plan by default.
---

# gcp_budget-alert-setup

Creates one budget alert on the owner's billing account (the whole account, not one project). A budget whose display name already equals `displayName` is left alone. A budget only alerts; it does not cap spending, and it has no fixed cost.

The budget commands need the Budget API (`billingbudgets.googleapis.com`) enabled on the quota project. A project created seconds ago may still refuse them: that is what the single retry in step 2 is for.

## Arguments

Free text after the skill name, as `key=value` pairs. All five are required (if one is missing, ask for it instead).

| Argument | Meaning |
|---|---|
| `displayName=<name>` | The budget's display name; it identifies the budget. Letters, digits, `.`, `_`, `-` only. |
| `amount=<number>` | The budget amount, for example `100`. |
| `currency=<code>` | The currency code, for example `BRL`. |
| `thresholds=<list>` | Comma-separated fractions of the amount, for example `0.5,0.9,1.0`. |
| `quotaProject=<project id>` | The GCP project id that is billed for the Budget API calls. |
| `mode=plan\|apply` | `plan` (default) reports what would change and changes nothing; `apply` executes. |

## Validate first

Before running any command, check the arguments. Any failure ends the skill with the result block, `status` `failed`, one sentence saying which rule failed, and no `gcloud` call.

- `displayName` starts with a letter or digit, contains only letters, digits, `.`, `_` and `-` (no space, quote or other character), and has at most 60 characters.
- `amount` is a number greater than 0.
- `currency` is three uppercase letters.
- `thresholds` is a comma-separated list of numbers, each greater than 0 and at most 1.
- `quotaProject` looks like a GCP project id: 6 to 30 characters of `a-z`, `0-9` and `-`, starting with a letter and not ending with `-`.
- `mode` is `plan` or `apply`.

## Steps

Show each command before running it. Run only the commands below, in this order. On Windows, when `gcloud` fails to start, use `gcloud.cmd` in its place. The billing account id appears in the commands shown and in `pending[].how`; it never appears in the result block's `outputs` nor in the prose of the final answer.

1. Discover the billing account:

   ```
   gcloud billing accounts list --filter="open=true" --format="value(name)"
   ```

   `gcloud` returns `billingAccounts/<id>`; the flags below take the bare id, the part after the slash. A non-zero exit, or empty output, stops with `failed` and one sentence of cause, without raw error text. More than one line stops with `failed`: say how many were found and ask which to use, without printing any identifier. Never pick one.

2. List the existing budgets:

   ```
   gcloud billing budgets list --billing-account=<id> --billing-project=<quotaProject> --format="value(displayName)"
   ```

   In `apply` mode only, if this first list exits non-zero (the Budget API can take a moment after being enabled), wait about one minute and run it once more. A non-zero exit (in `apply`, the second one) stops with `failed` and one sentence of cause, without raw error text; it never means "no budget". Only a successful call with no match means none.
   - A line equal to `displayName`: run nothing else and end with `unchanged`. Do not compare or change the existing budget's amount or thresholds; say so in the answer.
   - `plan` mode, no match: run nothing else and end with `would-create`.

3. `apply` mode, no match: create the budget, with one `--threshold-rule` per threshold:

   ```
   gcloud billing budgets create --billing-account=<id> --display-name=<displayName> --budget-amount=<amount><currency> --threshold-rule=percent=<t1> --threshold-rule=percent=<t2> --billing-project=<quotaProject>
   ```

   A non-zero exit stops with `failed` and one sentence of cause, without raw error text (nothing was created).

4. Verify by running the step 2 command again. The display name must be in the output. A non-zero exit, or no match, ends with `pending`: say that the budget could not be confirmed, and set `pending[].how` to the step 2 command, written out with the real bare billing account id and quota project so it can be run as is.

Then answer in a few lines: the display name, amount, currency and thresholds, whether the budget was created or already existed, and the result block.

## Result block

End with exactly one fenced block tagged `aleogr-result`:

```aleogr-result
{
  "aleogr-result": 1,
  "family": "cloud",
  "provider": "gcp",
  "action": "budget-alert-setup",
  "mode": "apply",
  "status": "created",
  "resources": [
    { "type": "budget", "id": "<displayName>", "name": "<displayName>", "labels": {} }
  ],
  "outputs": {
    "displayName": "<displayName>",
    "amount": 100,
    "currency": "BRL",
    "thresholds": [0.5, 0.9, 1.0]
  },
  "cost": { "fixed": false, "notes": "a budget alert is free" },
  "pending": []
}
```

- `mode` echoes the mode used. `status` is one of `would-create` (plan), `created`, `unchanged`, `pending` (created, not confirmed by step 4), `failed`.
- `outputs` never holds the billing account id. For `unchanged`, `amount` and `thresholds` echo the arguments, not the existing budget's values.
- `failed`: `resources` is empty and `outputs` is `{ "displayName": null, "amount": null, "currency": null, "thresholds": [] }`.
- `would-create`: `resources` is empty.
- `pending`: `resources` and `outputs` are set as usual.
