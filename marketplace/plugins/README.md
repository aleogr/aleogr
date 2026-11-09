# Plugins

Uma subpasta por plugin. Não criar a pasta de um plugin antes do próprio plugin.

Fonte da verdade: [`docs/DESIGN.md` — seções 1, 8, 9, 10 e 12](../../docs/DESIGN.md#1-nomes).

## Nomes

- Orquestrador: `aleogr` (skills sem provedor, ex.: `declare-project`).
- Plugins de família: `aleogr-<família>-<provedor>` (ex.: `aleogr-repo-github`).
- Skills de família: `<provedor>-<ação>`, dado pelo **nome da pasta** (ex.: `skills/github-create-repo/`).
- **Nenhum `SKILL.md` tem `name:` no frontmatter.** A `description` cita o provedor.
- Nunca usar nomes de comandos embutidos (`init`, `doctor`, `status`, `review`, `context`, `config`...).

## Tipos de família

- **Exclusiva** (um provedor por projeto/domínio), **combinável** (vários ao mesmo tempo); escopo de **projeto**, **componente** ou **domínio**. Mapa completo na seção 9.
- Cada família tem um contrato mínimo de ações (seção 10); skills extras seguem a mesma convenção de nome.

## Esqueleto de um plugin

```
aleogr-<família>-<provedor>/
├── .claude-plugin/plugin.json   ← só o manifesto aqui dentro
├── skills/<provedor>-<ação>/SKILL.md
├── agents/                      (opcional)
├── hooks/hooks.json             (opcional)
├── scripts/                     (opcional; referenciar com ${CLAUDE_PLUGIN_ROOT})
└── .mcp.json                    (opcional; MCP oficial quando não houver boa CLI)
```
