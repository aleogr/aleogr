# Workflows

Pasta plana (exigência do GitHub), organizada por prefixo.

Fonte da verdade: [`docs/DESIGN.md` — seções 3, 4 e 15](../../docs/DESIGN.md#4-cicd) (nomes na [seção 1](../../docs/DESIGN.md#workflows)).

## Regras locais

- **Reutilizáveis** (`ci-`, `deploy-`, `release-`): somente `on: workflow_call`, para não rodarem a cada commit aqui. Chamados pelos workflows finos (`ci.yml`/`cd.yml`) dos projetos, fixados por SHA.
- **Do próprio repositório**: prefixo `self-` (ex.: `self-validate-marketplace.yml`, `self-lint.yml`, `self-test-features.yml`, `self-publish-features.yml`, `self-cleanup-tests.yml`).
- Versionamento por tags prefixadas: `workflows-v1`, `workflows-v2`...
- Secrets recebidos explicitamente pelo nome; **nunca** `secrets: inherit`.
- Logs de workflows públicos são públicos: **nenhum workflow imprime variáveis ou segredos**.

> Atenção: nunca criar `.github/README.md` — ele substituiria o README do perfil.
