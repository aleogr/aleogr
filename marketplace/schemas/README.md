# Schemas

JSON Schema da declaração de projeto (`.aleogr/project.json`) e declarações de exemplo.

Fonte da verdade: [`docs/DESIGN.md` — seção 11](../../docs/DESIGN.md#11-modelo-do-projeto) (testes na [seção 15](../../docs/DESIGN.md#15-testes)).

## Regras locais

- `project.schema.json` é versionado; o `project.json` tem o campo `version` e `$schema` para autocomplete:
  `https://raw.githubusercontent.com/aleogr/aleogr/main/marketplace/schemas/project.schema.json`.
- Famílias exclusivas = objeto; combináveis = lista; exatamente um cloud `primary`; payments `mode` com default `"test"`; campo `environments`; campo opcional `notes`.
- Nomes de projeto **não** podem começar com `test-` (prefixo reservado aos testes).
- Plugins de família podem publicar sub-schemas para suas opções.
- `examples/`: só declarações JSON com **valores fictícios** — são as entradas dos testes; validadas contra o schema em cada PR (`self-validate-marketplace.yml`). Nunca projetos com código.
