# `aleogr` marketplace

Root of the Claude Code plugin marketplace (the directory containing `.claude-plugin/marketplace.json`).

Source of truth: [`docs/DESIGN.md` — section 2](../docs/DESIGN.md#2-structure-of-aleograleogr) (names in [section 1](../docs/DESIGN.md#1-names)).

## How to register

Since `marketplace.json` is not at the repository root, `claude plugin marketplace add aleogr/aleogr` **does not work**. Register it in `extraKnownMarketplaces`:

```json
{
  "extraKnownMarketplaces": {
    "aleogr": {
      "source": {
        "source": "github",
        "repo": "aleogr/aleogr",
        "path": "marketplace/.claude-plugin/marketplace.json",
        "sparsePaths": ["marketplace"]
      }
    }
  },
  "enabledPlugins": {
    "aleogr@aleogr": true
  }
}
```

Where to put it, depending on where Claude Code runs:

- **Local (Windows app):** by hand, once per computer, in `~/.claude/settings.json`; in projects, `sync-plugins` writes the block to `.claude/settings.json` (family plugins in project scope).
- **Codespaces:** the `base` Feature registers it.
- **Claude Code cloud sessions:** the setup script of the `lab` cloud environment registers it (the repository's `.claude/settings.json` does **not** install plugins in those sessions).
- **Testing a branch:** add `"ref": "<branch>"` to `source`.

## Local rules

- Plugin `source` paths are relative to this folder (`./plugins/aleogr`), without `..`.
- Validation: `claude plugin validate ./marketplace`. Local test: `claude plugin marketplace add ./marketplace`.
- Every `marketplace.json` entry has `category` and `displayName`, and its name equals the `plugin.json` `name`.
- Do not use `dependencies` to link the orchestrator to the family plugins.
- `defaults.json` (future): personal choices only, no IDs or secrets.
