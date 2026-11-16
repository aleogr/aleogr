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
        "ref": "claude/fervent-planck-78eaxs"
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

## 2. Restart and install the plugins

Restart Claude Code. Registering the marketplace does not install its plugins: in a session on this computer, open the plugin browser (the **+** button of the message box, then **Plugins**, then browse), go to the **Code** tab, and install `aleogr` and `aleogr-cloud-gcp` for your user. If they are not listed, send back what the screen shows.

Prerequisites on Windows found in the first run: `git` installed (the app uses it to download the marketplace), `gcloud` installed, and PowerShell allowed to run local scripts (`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`), because in PowerShell `gcloud` is a script.

## 3. Run the three skills, in this order

1. `/aleogr:tools-check`: expected to say `gcloud` is `ok` and that Claude runs `local`. If it says `not authenticated`, run `gcloud auth login` and repeat.
2. `/aleogr:platform-plan`: changes nothing. Expected on a first run: a table with `shared project` missing (`create`), and `services` and `budget alert` marked `not checked, will be checked after the project exists` (`create`).
3. `/aleogr:platform-apply`: shows the plan and asks **one** confirmation (answer yes). It then creates the shared project under the organization, links billing, enables the APIs, and creates one budget alert of R$ 100 per month with alerts at 50%, 90% and 100%. It ends with a new plan that must say `nothing to do`. Everything here is free. If it stops before the end, send its output and run `/aleogr:platform-apply` again: it resumes from what already exists.

## 4. What to send back

- The final plan output (the table and the `aleogr-result` block of the last `platform-plan` inside `platform-apply`).
- The full text of any error, from any step.

## 5. Result of the first run (2026-11-16)

The run ended with `nothing to do`: the shared project, its two APIs and the budget alert exist.

- The flags of `gcloud billing budgets` work as written.
- The plugins install in the Windows app from the catalog at the standard location, and skill folders with an underscore load. The marketplace was added in the plugin browser (the **+** button, "add from a repository", `aleogr/aleogr#<branch>`), not through step 1: the app did not register it from the settings file after it had been removed once.
- The project creation failed once, before creating anything: PowerShell split the unquoted `--labels` value at its commas. The skill now quotes it.
- The first budget listing was denied on the project created seconds before; the skill's single retry, a minute later, succeeded.
- A second `platform-plan`, in a new session and without a project id, found the project by its labels and ended with `nothing to do`.
- Still not verified: the folder filter (the shared project is not in a folder).

Whatever failed became a fix in the skills and, when it is provider behaviour, a line in [`PROVIDER-FACTS.md`](../PROVIDER-FACTS.md).
