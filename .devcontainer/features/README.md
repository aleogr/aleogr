# Dev Container Features

Features distribuídas aos projetos, publicadas em `ghcr.io/aleogr/aleogr/<id>`.

Fonte da verdade: [`docs/DESIGN.md` — seção 5](../../docs/DESIGN.md#5-dev-containers-e-codespaces) (nomes na [seção 1](../../docs/DESIGN.md#dev-container-features)).

## Regras locais

- Nome pela **tecnologia, sem prefixo** (`go`, `java`, `python`, `android`); a Feature comum a todos os projetos é `base`.
- Layout da CLI de dev containers: fonte em `src/<id>/`, testes em `test/<id>/`; a subpasta tem o mesmo nome do `id`.
- `base`: registra o marketplace `aleogr` no Claude Code do container e traz o que é comum a todos os projetos. Mantê-la coerente com o script de preparação do ambiente de nuvem `lab` (seção 14).
- Features por tecnologia são só uma **camada de preferências** sobre a oficial: não reinstalam a linguagem, declaram `"installsAfter": ["ghcr.io/devcontainers/features/<tecnologia>"]` e **nunca** usam `dependsOn` na oficial.
- A pasta de uma tecnologia só existe se houver algo a acrescentar à oficial.
- Cada Feature tem a própria versão semver no `devcontainer-feature.json`. Publicação por `self-publish-features.yml`; marcar o pacote como público no GHCR na primeira publicação.
- Os `.gitkeep` de `src/` e `test/` são removidos quando a primeira Feature/teste existir.
