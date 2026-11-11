# Plugins

One subfolder per plugin. Do not create a plugin's folder before the plugin itself.

Source of truth: [`docs/DESIGN.md` — sections 1, 8, 9, 10 and 12](../../docs/DESIGN.md#1-names).

## Names

- Orchestrator: `aleogr` (skills without provider, e.g. `declare-project`).
- Family plugins: `aleogr-<family>-<provider>` (e.g. `aleogr-repo-github`).
- Family skills: `<provider>-<action>`, given by the **folder name** (e.g. `skills/github-create-repo/`).
- **No `SKILL.md` has `name:` in its frontmatter.** The `description` names the provider.
- Never use built-in command names (`init`, `doctor`, `status`, `review`, `context`, `config`...).

## Family types

- **Exclusive** (one provider per project/domain), **combinable** (several at once); **project**, **component** or **domain** scope. Full map in section 9.
- Each family has a minimum contract of actions, defined in [`docs/CONTRACTS.md`](../../docs/CONTRACTS.md); extra skills follow the same naming convention.
- Every family has a `describe-*` action, and every skill ends with an `aleogr-result` block (CONTRACTS.md section 1).

## Plugin skeleton

```
aleogr-<family>-<provider>/
├── .claude-plugin/plugin.json   ← only the manifest in here
├── skills/<provider>-<action>/SKILL.md
├── agents/                      (optional)
├── hooks/hooks.json             (optional)
├── scripts/                     (optional; reference with ${CLAUDE_PLUGIN_ROOT})
└── .mcp.json                    (optional; official MCP when there is no good CLI)
```
