# Composite actions

Composite actions reutilizáveis pelos projetos (uma subpasta por action, com `action.yml`).

Fonte da verdade: [`docs/DESIGN.md` — seções 3 e 4](../../docs/DESIGN.md#3-condições-do-repositório-público).

## Regras locais

- Referência nos projetos: `aleogr/aleogr/.github/actions/<nome>@<sha>` — sempre fixada por **SHA** (Dependabot/Renovate atualizam). Dentro deste repositório: `./.github/actions/<nome>`.
- Versionamento por tags prefixadas: `actions-v1`, `actions-v2`...
- Só ferramentas genéricas; nunca dados, IDs ou segredos (o repositório é público).
- Não serão publicadas no GitHub Marketplace (exigiria repositório próprio).

> Atenção: nunca criar `.github/README.md` — ele substituiria o README do perfil.
