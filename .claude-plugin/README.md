# `aleogr` marketplace

The whole Claude Code plugin marketplace lives in this folder: the catalog (`marketplace.json`), the plugins, their tests and the schemas. The marketplace root is the repository root, the directory that contains `.claude-plugin/`.

Source of truth: [`docs/DESIGN.md` — section 2](../docs/DESIGN.md#2-structure-of-aleograleogr) (names in [section 1](../docs/DESIGN.md#1-names)).

## How to register

The catalog is at the standard location, so `claude plugin marketplace add aleogr/aleogr` works. In settings:

```json
{
  "extraKnownMarketplaces": {
    "aleogr": {
      "source": {
        "source": "github",
        "repo": "aleogr/aleogr"
      }
    }
  },
  "enabledPlugins": {
    "aleogr@aleogr": true
  }
}
```

Where to put it, depending on where Claude Code runs:

- **Local (Windows app):** by hand, once per computer, in `~/.claude/settings.json`; in projects, `plugins-sync` writes the block to `.claude/settings.json` (family plugins in project scope).
- **Codespaces:** the `base` Feature registers it.
- **Claude Code cloud sessions:** the setup script of the `lab` cloud environment registers it (the repository's `.claude/settings.json` does **not** install plugins in those sessions).
- **Testing a branch:** add `"ref": "<branch>"` to `source`.

Registering is not installing: each plugin is installed once per computer, from the app's plugin browser or with `claude plugin install <plugin>@aleogr`.

## Local rules

- Plugin `source` paths are relative to the repository root (`./.claude-plugin/plugins/aleogr`), without `..`.
- Validation, from the repository root: `claude plugin validate .`. Local test: `claude plugin marketplace add .`.
- Every `marketplace.json` entry has `category` and `displayName`, and its name equals the `plugin.json` `name`.
- Do not use `dependencies` to link the orchestrator to the family plugins.
- `plugins/aleogr/defaults.json`: personal choices only, no IDs or secrets. It lives inside the orchestrator plugin because an installed plugin cannot read files outside its own folder; skills read it as `${CLAUDE_PLUGIN_ROOT}/defaults.json`. `contracts.json` will live there too.
