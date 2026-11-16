# Lab platform, stage 1: checklist for the first real run

For the owner. Run this in the Claude Code Windows app, where `gcloud` is authenticated. It creates only free resources: one Google Cloud project (with billing linked), its enabled APIs and one budget alert.

Source of truth: [`DESIGN.md`](../DESIGN.md) sections 2.3, 6.7, 6.8 and 18.

## Before you start

- The Google account used by `gcloud` can create projects in the organization.
- That account administers the billing account.
- The billing account's currency is BRL (the budget alert is in BRL).

## 1. Register the marketplace

Open the user settings file (`~/.claude/settings.json`) and add the block below. While the work is unmerged, keep the `"ref"` line; after the merge, remove it.

```json
{
  "extraKnownMarketplaces": {
    "aleogr": {
      "source": {
        "source": "github",
        "repo": "aleogr/aleogr",
        "ref": "claude/fervent-planck-78eaxs",
        "path": "marketplace/.claude-plugin/marketplace.json",
        "sparsePaths": ["marketplace"]
      }
    }
  },
  "enabledPlugins": {
    "aleogr@aleogr": true,
    "aleogr-cloud-gcp@aleogr": true
  }
}
```

If the file already has these keys, merge the entries instead of repeating the keys.

`aleogr-cloud-gcp@aleogr` is enabled at user scope here because the platform has no project repository; for projects, DESIGN.md puts family plugins in project scope.

## 2. Restart and check

Restart Claude Code, then type `/plugin`. Both `aleogr` and `aleogr-cloud-gcp` must be listed and enabled. If not, send back what `/plugin` shows.

## 3. Run the three skills, in this order

1. `/aleogr:tools-check`: expected to say `gcloud` is `ok` and that Claude runs `local`. If it says `not authenticated`, run `gcloud auth login` and repeat.
2. `/aleogr:platform-plan`: changes nothing. Expected on a first run: a table with `shared project` missing (`create`), and `services` and `budget alert` marked `not checked, will be checked after the project exists` (`create`).
3. `/aleogr:platform-apply`: shows the plan and asks **one** confirmation (answer yes). It then creates the shared project under the organization, links billing, enables the APIs, and creates one budget alert of R$ 100 per month with alerts at 50%, 90% and 100%. It ends with a new plan that must say `nothing to do`. Everything here is free. If it stops before the end, send its output and run `/aleogr:platform-apply` again: it resumes from what already exists.

## 4. What to send back

- The final plan output (the table and the `aleogr-result` block of the last `platform-plan` inside `platform-apply`).
- The full text of any error, from any step.

## 5. Not verified against real Google Cloud until this run

- The flags of `gcloud billing budgets`.
- Whether the Budget API must be enabled on the quota project (the skills enable it before creating the budget).
- The syntax of the folder and label filters.
- The marketplace registration through `extraKnownMarketplaces` with `path`.
- Whether a plugin skill folder with an underscore in its name (`gcp_environment-create`) loads on Windows.

Whatever fails becomes a fix in the skills and, when it is provider behaviour, a line in [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md).
