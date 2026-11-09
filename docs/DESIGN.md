# DESIGN — aleogr/aleogr

> **Fonte da verdade** deste repositório. Toda mudança de decisão é registrada aqui primeiro, e os READMEs das pastas afetadas são atualizados em seguida, no mesmo commit.

## Índice

- [0. Contexto e terminologia](#0-contexto-e-terminologia)
- [1. Nomes](#1-nomes)
- [2. Estrutura de aleogr/aleogr](#2-estrutura-de-aleograleogr)
- [3. Condições do repositório público](#3-condições-do-repositório-público)
- [4. CI/CD](#4-cicd)
- [5. Dev containers e Codespaces](#5-dev-containers-e-codespaces)
- [6. O lab, ambientes de projeto e custo mínimo](#6-o-lab-ambientes-de-projeto-e-custo-mínimo)
- [7. Onde ficam os dados](#7-onde-ficam-os-dados)
- [8. Tipos de família](#8-tipos-de-família)
- [9. Mapa de famílias](#9-mapa-de-famílias-direção-não-lista-de-tarefas)
- [10. Regras de contrato](#10-regras-de-contrato-valem-para-todas-as-famílias)
- [11. Modelo do projeto](#11-modelo-do-projeto)
- [12. Skills do orquestrador `aleogr`](#12-skills-do-orquestrador-aleogr)
- [13. Outros componentes](#13-outros-componentes)
- [14. Onde rodo o Claude Code](#14-onde-rodo-o-claude-code)
- [15. Testes](#15-testes)
- [16. Decisões descartadas](#16-decisões-descartadas)
- [17. Estratégia de implementação](#17-estratégia-de-implementação)
- [18. Pendências](#18-pendências)

---

## 0. Contexto e terminologia

Marketplace pessoal de plugins do Claude Code para automatizar a configuração de projetos novos (repositório, cloud, DNS, stacks, plataformas, serviços, CI/CD e ambiente de desenvolvimento), hoje feita manualmente clicando em painéis.

Tudo fica no repositório de perfil do GitHub, `aleogr/aleogr`, que tem **quatro funções**:

1. Perfil do GitHub (`README.md` da raiz).
2. Marketplace de plugins do Claude Code (`marketplace/`).
3. CI/CD reutilizável: workflows parametrizados e composite actions (`.github/`).
4. Dev Container Features para GitHub Codespaces (`.devcontainer/features/`).

Tudo isso é **FERRAMENTA** do laboratório de desenvolvimento (o "lab", em `lab.aleogr.dev`).

Premissas pessoais:

- Prática de "vibe coding" (não escrevo código), mas quero poder abrir um ambiente de desenvolvimento na web.
- Muitos projetos em desenvolvimento ao mesmo tempo.
- Busca constante do **MENOR CUSTO** possível em desenvolvimento.

Terminologia (são coisas diferentes):

- **Ambiente de projeto**: `lab`, `homolog`, `prod` ([seção 6](#6-o-lab-ambientes-de-projeto-e-custo-mínimo)).
- **Ambiente de nuvem do Claude Code**: a configuração onde rodam as sessões do Claude Code na nuvem ([seção 14](#14-onde-rodo-o-claude-code)).

Regras de trabalho neste repositório:

- Responder sempre em português.
- Sempre que uma decisão mudar, atualizar `docs/DESIGN.md` e os READMEs afetados, e fazer commit.
- NUNCA criar `.github/README.md`; NÃO alterar o `README.md` da raiz (perfil) sem pedido explícito.
- Não criar pastas de plugins nem implementar plugins, skills, actions, workflows ou Features sem instrução explícita.

---

## 1. Nomes

### Marketplace e plugins

- Marketplace: `name` = `aleogr`. Repositório: `aleogr/aleogr`.
- Plugin orquestrador: `aleogr` (ex.: `/aleogr:new-project`). Id de instalação: `aleogr@aleogr`.
- Plugins de família: `aleogr-<família>-<provedor>` (ex.: `aleogr-repo-github`, `aleogr-cloud-gcp`, `aleogr-dns-cloudflare`, `aleogr-stack-go`).

### Skills

- Skills de família: `<provedor>-<ação>`, definido pelo **NOME DA PASTA** da skill (ex.: `skills/github-create-repo/`). Comando completo: `/aleogr-repo-github:github-create-repo`, `/aleogr-cloud-gcp:gcp-create-environment`, `/aleogr-dns-cloudflare:cloudflare-add-record`, `/aleogr-stack-go:go-setup`.
- Produtos de clouds levam o provedor completo: `aws-route53-add-record`, `gcp-cloud-sql-create-database`.
- **NENHUM `SKILL.md` de plugin tem o campo `name:` no frontmatter.** O nome vem da pasta e o Claude Code aplica o prefixo do plugin. Motivo: há um bug recorrente (issue anthropics/claude-code#22063, resolvida em março de 2026 e relatada de novo como regressão em junho) em que o campo `name:` faz a skill perder o prefixo do plugin; a documentação de plugins orienta a não usar `name:`.
- O provedor no nome da skill é uma proteção **ADICIONAL e deliberada**: mesmo que o namespace `plugin:skill` falhe (regressão, ou superfície que mostra skills sem prefixo), não há colisão entre plugins. A redundância no comando (`github` aparece duas vezes) é aceita conscientemente.
- Skills do orquestrador não têm tecnologia e não levam provedor (ex.: `/aleogr:declare-project`).
- Descrições de skills citam o provedor explicitamente (é pela descrição que o Claude escolhe a skill na invocação automática). Exemplo de frontmatter:

```markdown
---
description: Cria um repositório no GitHub usando o gh CLI e configura o remote local. Use ao iniciar um projeto hospedado no GitHub.
---
```

- Nunca usar nomes iguais a comandos embutidos do Claude Code (`init`, `doctor`, `status`, `review`, `context`, `config` etc.).

### marketplace.json

- A entrada no `marketplace.json` e o `name` no `plugin.json` devem ser iguais.
- Toda entrada do `marketplace.json` tem `category` (ex.: `orquestrador`, `repo`, `cloud`, `dns`, `stack`) e `displayName` legível (ex.: "GitHub (repositório)"); `tags` opcionais para busca.

### Workflows

- Workflows reutilizáveis: prefixo por finalidade (`ci-`, `deploy-`, `release-`).
- Workflows que rodam no próprio repositório: prefixo `self-`.

### Dev Container Features

- Features próprias: nomeadas pela **TECNOLOGIA, SEM prefixo**, porque o endereço publicado já funciona como prefixo: `ghcr.io/aleogr/aleogr/<id>` (ex.: `go`, `java`, `python`, `android`).
- A Feature comum a todos os projetos se chama `base`.
- Correspondência direta com os plugins: `aleogr-stack-go` ↔ Feature `go`; `aleogr-platform-android` ↔ Feature `android`.

### Ambientes de nuvem do Claude Code

- Nomeados por **PERFIL DE NECESSIDADE** (ex.: `lab`, `lab-android`), nunca por repositório ou projeto.

### Recursos de projeto e da plataforma no lab

- Recursos de projeto no lab: serviços `<projeto>-<componente>`, banco `<projeto>` (normalizado para o formato aceito pelo banco), registro `<projeto>.lab.aleogr.dev`, label `aleogr-project=<projeto>`.
- Recursos da plataforma do lab: label `aleogr-platform=lab`.

### Testes

- Organização separada no GitHub, com **NOME EM ABERTO** (referida aqui como `<org-de-testes>`).
- Um `<id>` curto e aleatório por teste, usado em **TODOS** os recursos do teste:
  - repositório `test-<id>`;
  - tópico `aleogr-test`;
  - serviços `test-<id>-<componente>`;
  - banco `test_<id>`;
  - registro `test-<id>.lab.aleogr.dev`;
  - label `aleogr-test=<id>`.
- O prefixo `test-` é **RESERVADO**: o schema e o `declare-project` recusam nomes de projetos reais que comecem com `test-`.

---

## 2. Estrutura de aleogr/aleogr

**Premissa: raiz limpa.** Visíveis na raiz só `README.md`, `docs/` e `marketplace/`; o resto fica nas pastas com ponto exigidas por convenção (`.github/`, `.devcontainer/`).

A árvore abaixo é o **ALVO**; marcações "(esqueleto)" indicam o que existe desde a primeira tarefa.

```
aleogr/aleogr/
├── README.md                                  ← perfil do GitHub (não mexer sem pedir)
├── docs/
│   ├── DESIGN.md                              ← fonte da verdade (esqueleto)
│   └── cloud-environments/                    (futuro) versão canônica dos ambientes de nuvem do Claude Code
│       └── lab.md                             ← script de preparação, domínios permitidos, sem IDs nem segredos
├── .devcontainer/
│   ├── devcontainer.json                      ← ambiente do próprio aleogr/aleogr (usa as Features locais)
│   └── features/                              ← Dev Container Features distribuídas aos projetos
│       ├── README.md                          ← nome pela tecnologia, installsAfter, base (esqueleto)
│       ├── src/
│       │   ├── .gitkeep                       (esqueleto; remover quando a primeira Feature existir)
│       │   ├── base/                          ← presente em todo projeto
│       │   │   ├── devcontainer-feature.json
│       │   │   └── install.sh
│       │   ├── go/                            (só se houver preferências a acrescentar à oficial)
│       │   ├── java/                          (idem)
│       │   └── python/                        (idem)
│       └── test/
│           ├── .gitkeep                       (esqueleto; remover quando o primeiro teste existir)
│           ├── base/test.sh
│           └── go/ ...
├── .github/                                   ← NUNCA criar .github/README.md
│   ├── dependabot.yml                         ← atualiza referências de actions do próprio repo
│   ├── actions/                               ← composite actions (subpastas permitidas)
│   │   ├── README.md                          ← como referenciar, actions-v1, SHA (esqueleto)
│   │   ├── detect-changes/action.yml          (futuro)
│   │   ├── setup-go/action.yml                (futuro)
│   │   └── setup-java/action.yml              (futuro)
│   └── workflows/                             ← pasta plana (exigência do GitHub), organizada por prefixo
│       ├── README.md                          ← prefixos, só workflow_call, workflows-v1 (esqueleto)
│       ├── self-validate-marketplace.yml      ← valida marketplace e declarações de exemplo em cada PR
│       ├── self-lint.yml                      ← verificação estática de workflows e scripts em cada PR
│       ├── self-test-features.yml             ← testa as Features (pasta test/) em cada PR
│       ├── self-publish-features.yml          ← publica as Features no GHCR
│       ├── self-cleanup-tests.yml             ← agendado: apaga os recursos de testes antigos
│       ├── ci-go.yml                          (futuro, reutilizável)
│       ├── ci-java.yml                        (futuro, reutilizável)
│       └── deploy-cloud-run.yml               (futuro, reutilizável)
└── marketplace/                               ← raiz do marketplace
    ├── README.md                              ← como registrar o marketplace (esqueleto)
    ├── defaults.json                          ← meus padrões pessoais (só escolhas, sem IDs) (futuro)
    ├── .claude-plugin/
    │   └── marketplace.json
    ├── schemas/
    │   ├── README.md                          ← propósito, versionamento e exemplos do schema (esqueleto)
    │   ├── project.schema.json
    │   └── examples/                          ← declarações de exemplo (só JSON, valores fictícios)
    │       └── go-gcp-cloudflare.json         (futuro)
    └── plugins/
        ├── README.md                          ← nomes, tipos de família, esqueleto de um plugin (esqueleto)
        ├── aleogr/                            ← orquestrador (MVP)
        │   ├── .claude-plugin/plugin.json
        │   ├── skills/
        │   │   ├── check-environment/SKILL.md
        │   │   ├── declare-project/SKILL.md
        │   │   ├── plan-project/SKILL.md
        │   │   └── apply-project/SKILL.md
        │   ├── hooks/hooks.json               ← trava de comandos destrutivos
        │   └── scripts/guard-destructive.sh
        ├── aleogr-repo-github/                (MVP)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/
        │       ├── github-create-repo/SKILL.md        ← contrato
        │       ├── github-configure-repo/SKILL.md     ← contrato
        │       ├── github-protect-branch/SKILL.md     ← contrato
        │       ├── github-set-ci-secret/SKILL.md      ← contrato
        │       ├── github-setup-ci/SKILL.md           ← contrato
        │       └── github-install-claude-app/SKILL.md ← extra (futuro)
        ├── aleogr-cloud-gcp/                  (MVP)
        │   ├── .claude-plugin/plugin.json
        │   └── skills/ gcp-create-environment, gcp-enable-services, gcp-setup-deploy
        └── aleogr-dns-cloudflare/             (MVP)
            ├── .claude-plugin/plugin.json
            ├── .mcp.json                      ← MCP oficial do Cloudflare (https://mcp.cloudflare.com/mcp)
            └── skills/ cloudflare-add-record
```

### 2.1 Regras de documentação

- Um `README.md` curto por pasta onde houver regras locais a explicar, sempre apontando para a seção correspondente de `docs/DESIGN.md` (fonte da verdade).
- Preferir README a `.gitkeep`, que só é usado onde um README seria repetitivo (`.devcontainer/features/src/` e `test/`, onde as ferramentas de dev containers esperam apenas subpastas de Features).
- **NUNCA criar `.github/README.md`**: o GitHub procura o README em `.github/`, depois na raiz e depois em `docs/`, e um README em `.github/` substituiria o do meu perfil. READMEs em `.github/actions/` e `.github/workflows/` não têm esse problema.
- Não criar pasta de plugin antes do próprio plugin.

### 2.2 Regras de estrutura do marketplace

- O `marketplace.json` fica em `marketplace/.claude-plugin/marketplace.json`. A raiz do marketplace é `marketplace/` (o diretório que contém `.claude-plugin/`); os `source` são relativos a ela (`./plugins/aleogr`), sem `..`.
- Cada plugin tem `.claude-plugin/plugin.json` (só o manifesto fica dentro de `.claude-plugin/`); `skills/`, `agents/`, `hooks/`, `scripts/` e `.mcp.json` ficam na raiz do plugin. Scripts são referenciados com `${CLAUDE_PLUGIN_ROOT}`.
- Validação local: `claude plugin validate ./marketplace`. Teste local: `claude plugin marketplace add ./marketplace`.
- **NÃO usar o campo `dependencies`** para ligar o orquestrador aos plugins de família: isso instalaria todas as famílias em todos os projetos. A ativação é decidida pela declaração de cada projeto, via `sync-plugins`.

### 2.3 Registro do marketplace

Como o `marketplace.json` não está na raiz do repositório, o `claude plugin marketplace add aleogr/aleogr` **não funciona**. O registro é feito em `extraKnownMarketplaces`, por quatro caminhos, conforme onde o Claude Code roda:

- **Local (app do Windows):** à mão uma vez por computador em `~/.claude/settings.json`; e pelo `sync-plugins` no `.claude/settings.json` de cada projeto (plugins de família no escopo do projeto).
- **Codespaces:** pela Feature `base`.
- **Sessões na nuvem do Claude Code:** pelo SCRIPT DE PREPARAÇÃO do ambiente de nuvem ([seção 14](#14-onde-rodo-o-claude-code)). **ATENÇÃO:** sessões na nuvem NÃO instalam plugins nem marketplaces declarados no `.claude/settings.json` do repositório (`enabledPlugins`/`extraKnownMarketplaces`).
- **Para testar uma branch:** acrescentar `"ref": "<branch>"` ao `source`.

Bloco de settings:

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

- **Visibilidade (local):** o catálogo do marketplace mostra todos os plugins; entre os instalados, o `aleogr` aparece em todo lugar (escopo de usuário) e os plugins de família aparecem só nos projetos que os ativaram (escopo de projeto).
- **URL do schema nos projetos:** `https://raw.githubusercontent.com/aleogr/aleogr/main/marketplace/schemas/project.schema.json`.

---

## 3. Condições do repositório público

- O repositório de perfil é obrigatoriamente público; marketplace, actions, workflows e Features ficam públicos. Contêm só **FERRAMENTAS genéricas, NUNCA dados** (ver [seção 7](#7-onde-ficam-os-dados)). As declarações de exemplo em `marketplace/schemas/examples/` usam valores fictícios; o `defaults.json` e `docs/cloud-environments/` contêm só escolhas, sem IDs nem segredos.
- **Versões separadas por produto:**
  - tags prefixadas para workflows e actions (`workflows-v1`, `actions-v1`);
  - o marketplace segue a branch padrão e as versões dos `plugin.json`;
  - cada Feature tem a própria versão semver no `devcontainer-feature.json`, publicada no GHCR (independente das tags do Git);
  - nos projetos, os `uses:` são fixados por SHA (Dependabot/Renovate atualizam).
- Workflows reutilizáveis têm apenas `on: workflow_call`, para não rodarem a cada commit no próprio repositório.
- **Proteção à altura do alcance:** `main` protegida (exigir PR, mesmo trabalhando sozinho), 2FA, SHAs fixados nos consumidores.
- Composite actions são referenciadas como `aleogr/aleogr/.github/actions/<nome>@<sha>` (ou `./.github/actions/<nome>` dentro do próprio repo). Publicar uma action no GitHub Marketplace exigiria repositório próprio; não é o objetivo.
- Ser público é deliberado e traz vantagens no plano gratuito do GitHub:
  - proteção de branch disponível;
  - minutos ilimitados de Actions nos runners padrão;
  - workflows e actions utilizáveis por repositórios de outros donos (como a organização de testes);
  - Features e schema legíveis sem autenticação.

---

## 4. CI/CD

- As peças reutilizáveis vivem no `aleogr/aleogr`; cada projeto tem workflows **FINOS** gerados pela skill `<provedor>-setup-ci` do plugin `repo-*` (no GitHub, `github-setup-ci`), que só chamam os reutilizáveis com parâmetros.
- **Um único `.github/workflows/ci.yml` por projeto:**
  - um job `changes` detecta o que mudou (inicialmente `dorny/paths-filter` fixado por SHA; candidato a virar a composite action `aleogr/aleogr/.github/actions/detect-changes`, que recebe a lista de componentes);
  - um job por componente, com `needs: changes` e `if:` na saída correspondente, chamando o reutilizável da sua stack (ex.: `aleogr/aleogr/.github/workflows/ci-go.yml@<sha>` com `working-directory` e `go-version`);
  - dois componentes da mesma stack = dois jobs chamando o mesmo reutilizável.
- **NÃO usar um workflow por componente com `on.push.paths`:** o filtro nativo vale para o workflow inteiro, e um workflow que não disparou deixa o check obrigatório pendente para sempre, travando o PR. Job pulado por `if:` conta como sucesso.
- Secrets são passados explicitamente pelo nome aos reutilizáveis (**não usar `secrets: inherit`**), deixando visível no projeto o que cada um recebe.
- Deploy em `cd.yml` (ou jobs posteriores do mesmo arquivo) com `needs:` no CI do componente e condição para rodar só na `main`. Com ambientes de projeto múltiplos ([seção 6](#6-o-lab-ambientes-de-projeto-e-custo-mínimo)), o `cd.yml` faz deploy no `lab` e promove para os ambientes seguintes.
- **Futuro GitLab:** os workflows reutilizáveis e as composite actions só servem ao GitHub Actions. Um `gitlab-setup-ci` precisaria de templates de pipeline.
  - Opção preferida (menos repositórios): templates no próprio `aleogr/aleogr` (ex.: `.gitlab/ci/`), incluídos nos projetos por URL pública.
  - Alternativa: CI/CD components do catálogo do GitLab (exige projeto hospedado no GitLab).
  - Decidir só quando houver projeto real no GitLab.

---

## 5. Dev containers e Codespaces

- O Codespaces lê o `.devcontainer/devcontainer.json` do repositório aberto; cada projeto tem o seu, **FINO**, gerado pelo orquestrador a partir da declaração. O que é reutilizável são as Dev Container Features (padrão aberto: funcionam no Codespaces, no VS Code local e nas IDEs JetBrains).
- Todo projeto recebe: a Feature oficial do Claude Code (`ghcr.io/anthropics/devcontainer-features/claude-code:1.0`) e a `ghcr.io/aleogr/aleogr/base:1`.
- **`base`:** registra o marketplace `aleogr` (bloco da [seção 2.3](#23-registro-do-marketplace)) nas configurações de usuário do Claude Code dentro do container, para que o orquestrador esteja disponível em qualquer codespace, inclusive vazio, e traz o que é comum a todos os projetos. A Feature `base` (Codespaces) e o script de preparação do ambiente de nuvem `lab` (sessões na nuvem do Claude Code, [seção 14](#14-onde-rodo-o-claude-code)) têm a **MESMA responsabilidade, em dois veículos**; manter os dois coerentes.
- **Features por tecnologia** (`go`, `java`, `python`, `android`...) são uma **CAMADA DE PREFERÊNCIAS** sobre as Features oficiais (ex.: `ghcr.io/devcontainers/features/go`): linters, formatador, servidor de linguagem, depurador, extensões do editor. **NÃO reinstalam a linguagem.** Declaram `"installsAfter": ["ghcr.io/devcontainers/features/<tecnologia>"]` para rodar depois da oficial.
- **NÃO usar `dependsOn` para a oficial:** as opções de uma dependência ficam fixas na definição da Feature, e a versão declarada no project.json não chegaria à linguagem instalada. O `devcontainer.json` gerado lista as DUAS, com a versão na oficial:

```json
"features": {
  "ghcr.io/devcontainers/features/go:1": { "version": "1.23" },
  "ghcr.io/aleogr/aleogr/go:1": {},
  "ghcr.io/anthropics/devcontainer-features/claude-code:1.0": {},
  "ghcr.io/aleogr/aleogr/base:1": {}
}
```

- A pasta de uma tecnologia só existe se houver algo meu a acrescentar. Se a oficial bastar, o `stack-*` contribui só com ela.
- **Autenticação do Claude Code nos codespaces:** `ANTHROPIC_API_KEY` ou `CLAUDE_CODE_OAUTH_TOKEN` (gerado com `claude setup-token`) guardado como secret do Codespaces.
- **Layout:** fontes das Features em `.devcontainer/features/src/<id>/` e testes em `.devcontainer/features/test/<id>/` (layout esperado pela CLI de dev containers). A subpasta tem o mesmo nome do `id`. O `devcontainer.json` do próprio `aleogr/aleogr` referencia as Features locais por caminho relativo (ex.: `./features/src/base`) para testar antes de publicar.
- **Publicação** via `self-publish-features.yml` no GHCR (namespace `aleogr/aleogr`). Pacotes do GHCR nascem privados: marcar cada Feature como pública na primeira publicação.
- O `devcontainer.json` dos projetos é **arquivo compartilhado**: cada stack/plataforma contribui com suas entradas em `features` sem mexer nas outras. Monorepo: um único `devcontainer.json` por padrão; um por componente (`.devcontainer/<componente>/devcontainer.json`) quando alguma plataforma declarar toolchain pesado ou conflitante.
- O que é específico do Codespaces (secrets do Codespaces, prebuilds) são skills extras do `aleogr-repo-github` (ex.: `github-configure-codespaces`).
- iOS/watchOS (macOS) e firmware (dispositivo físico) não compilam no codespace: o devcontainer serve para editar e usar o Claude Code; o build fica no CI (runner macOS) ou no app do Windows. A `platform-*` registra esse limite.
- **NÃO usar o `aleogr/aleogr` como repositório de dotfiles do Codespaces** (exigiria script na raiz ou links das pastas com ponto); a `base` cumpre o objetivo.
- **Custo:** definir limite de gastos e desligamento rápido por inatividade no Codespaces.
- Codespaces complementa o Claude Code na web: acrescenta editor completo, aplicação rodando e prévia de portas.

---

## 6. O lab, ambientes de projeto e custo mínimo

- Sou dono do domínio `aleogr.dev`. O lab (`lab.aleogr.dev`) é **TUDO o que não é produção**: o desenvolvimento e a homologação dos meus projetos e os testes da própria ferramenta.

### 6.1 Endereços dos ambientes de um projeto

- **`lab`** (desenvolvimento): `<projeto>.lab.aleogr.dev`; tenants: `<tenant>.<projeto>.lab.aleogr.dev`, atendidos por curinga `*.<projeto>.lab.aleogr.dev` (o roteamento por tenant é feito pela aplicação, pelo hostname).
- **`homolog`** (opcional): ambiente como **SUFIXO** do projeto, `<projeto>-homolog.lab.aleogr.dev`, com curinga próprio `*.<projeto>-homolog.lab.aleogr.dev`. Nunca `homolog.<projeto>.lab...`, que se confundiria com um tenant e seria capturado pelo curinga do projeto.
- **`prod`** (opcional): domínio próprio do projeto ou, sem domínio próprio, `<projeto>.aleogr.dev` (subdomínio de primeiro nível, coberto pelo certificado gratuito do Cloudflare).
- O orquestrador deriva os nomes a partir do nome do projeto e do ambiente; eu só declaro quais ambientes o projeto tem.

Declaração (substitui um campo `domains` simples):

```json
"environments": {
  "lab":     { "host": "projeto2.lab.aleogr.dev",         "tenants": "wildcard" },
  "homolog": { "host": "projeto2-homolog.lab.aleogr.dev", "tenants": "wildcard" },
  "prod":    null
}
```

### 6.2 HTTPS e certificados

- `.dev` exige HTTPS (o domínio está na lista de pré-carregamento HSTS dos navegadores): não há HTTP nem em desenvolvimento.
- O Universal SSL gratuito do Cloudflare cobre só o domínio raiz e o primeiro nível de subdomínio. `projeto1.lab.aleogr.dev` (segundo nível) e os tenants (terceiro nível), com proxy ativo, **NÃO são cobertos** e dão erro como `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`.
- Saídas: Advanced Certificate Manager (pago) com Total TLS ou certificados avançados; ou registros sem proxy, com o certificado emitido pelo destino.
- A solução usada hoje no meu lab está **PENDENTE** de investigação ([seção 18](#18-pendências)).

### 6.3 Proteção e acesso único

- **Proteção do lab:** Cloudflare Access exigindo login para `*.lab.aleogr.dev` (exige registros com proxy). Skill extra do plugin do Cloudflare, aplicada uma vez para o lab inteiro. Testadores externos entram por e-mail na regra.
- **Acesso único:** hoje acesso todos os projetos do lab por um acesso único, SEM load balancer. A implementação atual está **PENDENTE** de investigação ([seção 18](#18-pendências)). Se for um ponto único de roteamento (ex.: Worker do Cloudflare roteando pelo hostname), adicionar um projeto ao lab passa a ser "adicionar uma rota" nesse ponto, com um único curinga DNS configurado uma vez; o contrato de dns-* no lab será ajustado conforme o resultado.

### 6.4 Plataforma do lab × recursos de projeto

- **Plataforma do lab:** criada UMA vez e compartilhada por todos os projetos em desenvolvimento (ex.: uma única instância do Cloud SQL, o acesso único sob `lab.aleogr.dev`, o curinga DNS, a proteção do Access, o cofre de segredos do lab). Cada provedor de cloud (GCP, AWS, Azure) tem a sua versão da plataforma do lab, com a mesma lógica.
- **Recursos de projeto:** criados DENTRO da plataforma (ex.: banco + usuário na instância compartilhada, serviço no ambiente de cloud do lab, rota no acesso único, segredos com prefixo do projeto).
- O contrato das famílias ganha o modo `shared` ou `dedicated`; no ambiente de projeto `lab` o padrão é `shared`. Ex.: db-* no lab cria banco + usuário na instância única; em produção, instância própria.
- Isolamento dentro dos recursos compartilhados por nome e labels ([seção 1](#1-nomes)); `plan-project` de um projeto enxerga só o que é dele; `remove-*` nunca toca no que é de outro.

### 6.5 Custo mínimo (regra de contrato no ambiente de projeto `lab`)

- Escalar a zero sempre que possível.
- Menor nível/tamanho disponível.
- Nada com custo fixo por projeto (load balancer, IP estático, NAT, instâncias dedicadas).
- Avisar e pedir confirmação antes de criar qualquer coisa com custo fixo.
- Alertas de orçamento configurados na plataforma do lab de cada provedor.

### 6.6 Padrões pessoais

- Em `marketplace/defaults.json` (público, só escolhas, sem IDs), lidos pelo `declare-project` para pré-preencher declarações: domínio do lab (`lab.aleogr.dev`), dono no GitHub, cloud e região preferidos, provedor de DNS, quais serviços a plataforma do lab compartilha.

---

## 7. Onde ficam os dados

- **NÃO haverá repositório privado `aleogr/lab`, nem ferramentas em repositório privado.** Os dados da plataforma do lab são separados em três tipos:

| Tipo | Onde fica | Visível publicamente? |
|---|---|---|
| Segredos (senhas, tokens, chaves) | `secrets-*` do provedor (ex.: GCP Secret Manager) + secrets do GitHub Actions/Codespaces quando workflows ou codespaces precisarem + segredos de rede do ambiente de nuvem do Claude Code ([seção 14](#14-onde-rodo-o-claude-code)) | não |
| Identificadores (ID do projeto de cloud do lab, ID da zona DNS...) | convenção de nomes (preferida) + variáveis do GitHub Actions no `aleogr/aleogr`, lidas com `gh variable get` | não |
| Estado da plataforma do lab | descoberto no próprio cloud via labels e nomes (o cloud é a fonte da verdade); se não bastar, arquivo de estado num bucket privado com versionamento | não |
| Ferramentas | `aleogr/aleogr` | sim, de propósito |

- Secrets do GitHub não podem ser lidos de volta: servem para entregar credenciais a workflows/codespaces, não para guardar informação que o orquestrador consulte.
- Variáveis do Actions não são visíveis publicamente mesmo em repositório público, mas os logs de workflows públicos são: **nenhum workflow pode imprimir variáveis**.
- Variáveis de ambiente dos ambientes de nuvem do Claude Code são legíveis por quem usa o ambiente: **nunca colocar segredos nelas**.
- **Regras da descoberta:**
  - label em tudo que aceita label (`aleogr-platform`, `aleogr-project`, `aleogr-test`);
  - nome por convenção SEMPRE (é o identificador de recursos sem labels, como bancos dentro da instância compartilhada e registros DNS);
  - variáveis só para o que não pode ser deduzido (idealmente só IDs escolhidos uma vez).
- O histórico de mudanças da plataforma vem do log de auditoria dos hooks e dos logs de auditoria dos provedores; as decisões ficam versionadas no Git (`defaults.json`).
- Dados de PROJETO (`project.json`, `state.json`) continuam no repositório de cada projeto. **Questão em aberto:** aplicar o mesmo princípio de descoberta aos projetos, tornando o `state.json` mais leve ou só um cache (ver na prática, com o MVP).

---

## 8. Tipos de família

- **Exclusiva:** um provedor por projeto (ou por domínio).
- **Combinável:** vários ao mesmo tempo.
- **Escopo:** projeto, componente (diretório ou repositório) ou domínio.

---

## 9. Mapa de famílias (direção, NÃO lista de tarefas)

| Família | Representantes | Tipo | Escopo |
|---|---|---|---|
| repo-* | github, gitlab, bitbucket | exclusiva (sem espelhamento) | projeto |
| cloud-* | aws, azure, gcp | combinável, com exatamente um principal | projeto |
| secrets-* | aws-secrets-manager, gcp-secret-manager, azure-key-vault | exclusiva | projeto |
| tracker-* | jira, linear, asana | exclusiva | projeto |
| wiki-* | confluence, notion, gitbook | exclusiva | projeto |
| notify-* | slack, microsoft-teams, discord | combinável | projeto |
| registrar-* | godaddy, namecheap, cloudflare | exclusiva por domínio | domínio |
| dns-* | cloudflare, aws-route53, gcp-cloud-dns | exclusiva por domínio | domínio |
| cdn-* | cloudflare, akamai, aws-cloudfront | exclusiva por domínio | domínio |
| db-* | aws-rds, gcp-cloud-sql, azure-sql | combinável | projeto |
| cache-* | aws-elasticache, gcp-memorystore, redis-cloud | exclusiva | projeto |
| storage-* | aws-s3, gcp-storage, azure-blob | combinável | projeto |
| registry-* | docker-hub, ghcr, aws-ecr | exclusiva | projeto |
| hosting-* | vercel, netlify, cloudflare-pages | combinável | componente |
| search-* | elastic, algolia, aws-opensearch | exclusiva | projeto |
| auth-* | auth0, firebase-auth, aws-cognito | exclusiva | projeto |
| email-* | sendgrid, aws-ses, mailgun | exclusiva | projeto |
| sms-* | twilio, vonage, sinch | exclusiva | projeto |
| push-* | fcm, apns, onesignal | combinável | componente |
| payments-* | stripe, paypal, adyen | combinável | projeto |
| llm-* | anthropic, openai, google-gemini | combinável | projeto |
| flags-* | launchdarkly, unleash, flagsmith | exclusiva | projeto |
| monitoring-* | sentry, datadog, new-relic | combinável | projeto |
| analytics-* | google-analytics, mixpanel, amplitude | combinável | componente |
| stack-* | typescript, python, java (e go etc.) | combinável | componente |
| platform-* (mobile) | android, ios, harmonyos | combinável | componente |
| platform-* (desktop) | windows, macos, linux | combinável | componente |
| platform-* (embarcado) | zephyr, esp-idf, stm32cube | combinável | componente |
| platform-* (wearable) | wearos, watchos, garmin-connect-iq | combinável | componente |
| store-* | google-play, apple-app-store, microsoft-store | combinável | componente |
| publish-* | npm, pypi, maven-central | combinável | componente |

Observações:

- Os representantes são de referência, não um ranking preciso; alternativas independentes (Vault, 1Password, Doppler, Supabase, Neon, Clerk, Flathub etc.) podem fazer mais sentido.
- Web não é plataforma (é stack + hosting).
- CI fica em repo-*; deploy de containers em cloud-*.

---

## 10. Regras de contrato (valem para todas as famílias)

### 10.1 Contratos

Cada família tem um contrato: as mesmas AÇÕES, com o mesmo tipo de resultado, entre provedores; a skill se chama `<provedor>-<ação>`. O orquestrador monta o nome juntando o provedor (da declaração) com a ação (fixa no contrato). Contratos atuais:

- **repo-\***:
  - `<provedor>-create-repo` (URL e remote);
  - `<provedor>-configure-repo` (merge, recursos);
  - `<provedor>-protect-branch` (regras na branch principal);
  - `<provedor>-set-ci-secret` (nível repo ou org/grupo);
  - `<provedor>-setup-ci` (pipeline fino por componente).
  - Ex.: `github-create-repo` ↔ `gitlab-create-repo`.
- **cloud-\***:
  - `<provedor>-create-environment` (devolve o ID do ambiente);
  - `<provedor>-enable-services`;
  - `<provedor>-setup-deploy` (devolve o hostname público).
  - Proposta: "environment" em vez de "project", porque cloud tem conceitos diferentes (projeto no GCP, conta na AWS, subscription/resource group no Azure).
- **dns-\***: `<provedor>-add-record` (recebe nome + destino). No lab, pode virar "adicionar rota no acesso único" ([seção 6.3](#63-proteção-e-acesso-único)).
- **stack-\***: `<tecnologia>-setup` (recebe o diretório do componente).

### 10.2 Modo, nomes e labels

- Toda skill de família aceita o modo `shared` (dentro da plataforma do lab) ou `dedicated` (recursos próprios); no ambiente de projeto `lab`, o padrão é `shared`.
- Toda skill aplica as labels e os nomes por convenção da [seção 1](#1-nomes) em TUDO o que cria.

### 10.3 Extensão dos contratos

- O contrato é o MÍNIMO comum; plugins podem ter skills extras, com a mesma convenção de nome (ex.: `github-install-claude-app`, `github-configure-codespaces`, `cloudflare-protect-lab`).
- Contratos só são extraídos quando existir um segundo provedor real; não inventar no abstrato.
- Quando um recurso depender do plano do provedor e não estiver disponível, a skill avisa e registra como pendência no checklist, em vez de falhar ou fingir que aplicou.

### 10.4 Comportamento de toda skill

- Verifica antes de criar (idempotente).
- Mostra cada comando antes de executar.
- Para e pede confirmação antes de ações irreversíveis ou com custo.
- Segue a regra de CUSTO MÍNIMO no lab ([seção 6.5](#65-custo-mínimo-regra-de-contrato-no-ambiente-de-projeto-lab)).
- Termina com uma verificação (ex.: `gh repo view`, `gcloud ... describe`, consulta DNS).
- O que não puder ser automatizado vira checklist.
- Skills de platform-* começam verificando o ambiente (SO, SDK, dispositivo conectado).

### 10.5 Ferramentas e dependências entre famílias

- CLI primeiro (gh, glab, gcloud, aws, az); MCP quando não houver boa CLI ou o MCP oficial for melhor. O MCP vai no `.mcp.json` do plugin da família.
- cloud-* fornece a base (conta/projeto, identidades, permissões, APIs, deploy); famílias de serviço assumem que a base existe. O orquestrador garante a ordem.
- secrets-* é único por projeto, normalmente no cloud principal; credenciais de outros clouds também ficam lá. No lab, segredos de projeto ficam no cofre da plataforma do lab, com prefixo do projeto.

### 10.6 Divisão "quê/como"

- **stack-\*** fornece versão da linguagem, comandos de build/teste/lint, cache e Features de devcontainer (a oficial e, se existir, a minha camada de preferências).
- **platform-\*** fornece toolchain, runner necessário, Features e limites (o que não roda em codespace).
- **repo-\*** gera o workflow no formato da plataforma (`<provedor>-setup-ci`; no GitHub, workflows finos chamando os reutilizáveis do `aleogr/aleogr`).
- **O orquestrador** monta o `devcontainer.json`.
- CI e devcontainer saem da MESMA declaração: a versão da linguagem declarada vai tanto para o parâmetro do workflow quanto para a Feature oficial do devcontainer, evitando divergência. Mudar no project.json + apply-project atualiza os dois.

### 10.7 Arquivos compartilhados e hooks de stack

- Arquivos compartilhados na raiz dos projetos (.gitignore, .editorconfig, pre-commit, Dependabot/Renovate, devcontainer.json) recebem contribuições:
  - em texto, seções marcadas (`# >>> aleogr-stack-go` ... `# <<< aleogr-stack-go`);
  - em arquivos estruturados, cada contribuinte adiciona/atualiza só as suas entradas;
  - nunca substituição.
- Hooks de stack filtram pela extensão do arquivo e saem em silêncio se não for sua linguagem.

### 10.8 Famílias de cuidado especial (payments, registrar, store)

- Modo de teste por padrão.
- Nada de compra, produção ou envio a loja sem confirmação explícita.
- Chaves de assinatura só via secrets-*.

---

## 11. Modelo do projeto

- **Preferência pessoal:** o MENOR número possível de repositórios. Monorepo sempre que fizer sentido; em projetos multi-repo, preferir o layout federado (não cria repositório extra).
- O projeto é uma lista de componentes (stack, plataforma, deploy/distribuição, local = diretório ou repositório), os ambientes de projeto ([seção 6](#6-o-lab-ambientes-de-projeto-e-custo-mínimo)) e os serviços compartilhados do projeto.
- **Declaração** em `.aleogr/project.json` no repositório do projeto (o que eu QUERO; editado por mim ou pela skill `declare-project`). **Estado** em `.aleogr/state.json` (o que EXISTE; só o orquestrador escreve). Nenhum dos dois guarda segredos, só referências.
- A **plataforma do lab** é gerenciada pelo mesmo orquestrador, com o mesmo formato de declaração (marcada como `"kind": "platform"`), mas sem repositório próprio: escolhas no `defaults.json`, identificadores por convenção e variáveis, estado descoberto no cloud ([seção 7](#7-onde-ficam-os-dados)). Os projetos apontam para ela no ambiente de projeto `lab`.

### 11.1 JSON Schema

- Em `marketplace/schemas/project.schema.json` (versionado; campo `version` no project.json; `$schema` para autocomplete).
- Famílias exclusivas = objeto; combináveis = lista.
- Exatamente um cloud `primary` (contains + minContains/maxContains = 1).
- payments `mode` com default "test".
- Nomes de projeto não podem começar com `test-`.
- Campo `environments` ([seção 6.1](#61-endereços-dos-ambientes-de-um-projeto)).
- Nome do plugin derivado de família + provedor.
- Cada plugin de família pode publicar um sub-schema para suas opções.
- Campo opcional `notes` (JSON não aceita comentários).

### 11.2 Layouts suportados (mesmo formato)

- **monorepo:** um project.json na raiz.
- **manifesto:** repositório PRIVADO só com a declaração completa; componentes apontam para ele; nunca o `aleogr/aleogr`.
- **federado:** cada repositório tem seu fragmento com `"layout": "federated"`; membros encontrados por tópico (ex.: `aleogr-meu-projeto`); criação idempotente; remoção de serviço compartilhado consulta todos os membros antes.
- Antes de tudo, decidir se é UM projeto (compartilha serviços) ou VÁRIOS projetos relacionados (cada um com sua declaração).

### 11.3 Ativação de plugins de família

- **Local (app do Windows):** no ESCOPO DO PROJETO (`.claude/settings.json` versionado, com o bloco `extraKnownMarketplaces` da [seção 2.3](#23-registro-do-marketplace)), conforme a declaração. Em multi-repo, cada repositório ativa só as famílias que lhe dizem respeito.
- **Sessões na nuvem do Claude Code:** o `.claude/settings.json` do repositório NÃO instala plugins nelas. Os plugins chegam pelo script de preparação do ambiente de nuvem ([seção 14](#14-onde-rodo-o-claude-code)). Como os plugins de família chegam lá está **PENDENTE** ([seção 18](#18-pendências)).
- **O que o repositório leva às sessões na nuvem** (sessão com um repositório): `CLAUDE.md`, `.claude/skills/`, `.claude/agents/`, `.claude/commands/`, `.claude/rules/`, hooks e permissões do `.claude/settings.json`, `.mcp.json`.

---

## 12. Skills do orquestrador `aleogr`

- **Núcleo:**
  - `declare-project`: edita project.json por perguntas, pré-preenchendo com o `defaults.json`, sem executar;
  - `plan-project`: compara declaração, estado e realidade; não altera nada;
  - `apply-project`: executa o plano na ordem.
- **Atalhos:** `new-project`, `add-component`, `add-service`.
- **Manutenção:**
  - `check-environment`: CLIs, autenticação, MCPs, dispositivos; identifica se roda localmente, em codespace ou em sessão na nuvem e avisa o que não é possível ali;
  - `sync-plugins`: escreve `extraKnownMarketplaces` e instala/desativa plugins de família no escopo do projeto;
  - `remove-component`, `remove-service`: param antes de apagar, pedindo confirmação.
- **Marketplace** (talvez num plugin separado `aleogr-dev`, decisão em aberto):
  - `create-plugin`: gera o esqueleto já no padrão (nomes, `category` e `displayName` obrigatórios, skills do contrato);
  - `validate-marketplace`.

### 12.1 O que `validate-marketplace` verifica

`validate-marketplace` (e o workflow `self-validate-marketplace.yml`, em cada PR) verifica:

- `claude plugin validate ./marketplace`;
- skills de família no formato `<provedor>-<ação>`;
- NENHUM `name:` no frontmatter dos `SKILL.md` dentro de `marketplace/plugins/`;
- nenhum nome de skill igual a comando embutido;
- entrada do `marketplace.json` igual ao `name` do `plugin.json`;
- `category` e `displayName` presentes;
- skills obrigatórias do contrato presentes em cada plugin de família;
- declarações de `marketplace/schemas/examples/` válidas contra o schema.

### 12.2 Ordem do apply

1. Repositórios.
2. Registro de domínio.
3. Base de cloud (ou verificação da plataforma do lab).
4. Secrets.
5. Infraestrutura (db, cache, storage, registry, search).
6. Serviços (auth, email, sms, payments, llm, flags).
7. Componentes (stack, platform, hosting, push), incluindo o devcontainer.json.
8. DNS, rotas e CDN (recolhe registros das etapas anteriores).
9. Operação (monitoring, analytics, notify).
10. CI/CD (ci.yml e cd.yml finos, secrets).
11. Distribuição (store, publish).
12. `plan-project` final deve dizer "nada a fazer".

---

## 13. Outros componentes

### 13.1 Hooks

Garantias determinísticas; os gerais ficam no `aleogr`, os específicos em cada família.

- **PreToolUse em Bash** bloqueando comandos destrutivos (delete de projeto/repo, visibilidade pública, remoção de DNS, drop de banco, remoção de serviços) fora de um remove-* confirmado. Exceções **ESTREITAS**, só para recursos de teste que constam no estado de um teste:
  - repositórios (organização de testes + nome `test-<id>` + tópico `aleogr-test` + NÃO arquivado);
  - registros DNS `test-<id>` ou `test-<id>-<ambiente>` sob `lab.aleogr.dev`, e os tenants abaixo deles;
  - bancos `test_<id>`;
  - serviços/recursos de cloud `test-<id>-...` com label `aleogr-test=<id>`.
- **PreToolUse em Write/Edit** bloqueando segredos em arquivos versionados.
- **PostToolUse em Write/Edit** validando o project.json contra o schema.
- **PostToolUse de formatação** por stack.
- **SessionStart** injetando resumo da declaração e pendências manuais.
- **PostToolUse em Bash** registrando log de auditoria dos comandos de infraestrutura (também é o histórico da plataforma do lab).
- Hooks do `.claude/settings.json` do repositório rodam também em sessões na nuvem com um único repositório; para rodar algo só na nuvem, checar `CLAUDE_CODE_REMOTE=true`.

### 13.2 Agents

- Executores por família (isolam a saída verbosa das CLIs).
- Auditor independente sem ferramentas de escrita, que verifica o estado final sem ter visto a execução.
- Revisor de plano antes do apply.
- Agents de plugin não podem declarar hooks, mcpServers nem permissionMode.

### 13.3 LSP servers

- Cada stack-* traz o servidor de linguagem (ex.: gopls).

### 13.4 Commands

- Não usar; tudo é skill.

### 13.5 Settings/permissões

- `allow` para comandos só de leitura (gh repo view, gh variable get, gcloud ... describe/list).
- `ask` para o que cria ou altera.
- `deny` para o que nunca deve rodar.

### 13.6 CLAUDE.md dos projetos

- Curto; aponta para `.aleogr/project.json`, diz para não editar `state.json` à mão, guarda convenções.
- CLAUDE.md por diretório com convenções de cada stack.

### 13.7 Futuro

- GitHub Action agendada (semanal) rodando plan-project nos projetos e abrindo issue em caso de divergência.

---

## 14. Onde rodo o Claude Code

- Uso o Claude Code no app para Windows e na web (sessões na nuvem), e quero poder usar GitHub Codespaces.
- Configuração de infraestrutura (criar repositórios, gcloud auth login, OAuth do Cloudflare, gh auth login) é feita no **APP DO WINDOWS**. Evitar guardar na nuvem credenciais com poder de admin.
- iOS/watchOS exigem macOS (build via runner macOS no CI); embarcados e wearables geralmente exigem o dispositivo conectado ao app do Windows.

### 14.1 Sessões na nuvem do Claude Code (web, app, celular, `claude --cloud`)

- Rodam numa máquina Ubuntu nova a cada sessão, com o repositório clonado e ferramentas comuns pré-instaladas (inclusive `gh`, Go, Java 21, Node, Python, Docker, PostgreSQL, Redis).
- O que chega do repositório: ver [seção 11.3](#113-ativação-de-plugins-de-família).
- O que **NÃO** chega: plugins e marketplaces do `.claude/settings.json` do repositório; meu `~/.claude/` pessoal (CLAUDE.md, skills, plugins de usuário); MCPs adicionados no escopo local/usuário; login interativo (SSO).
- **GitHub nas sessões na nuvem:** as operações passam por um proxy que guarda minhas credenciais fora da máquina. O `gh` está instalado, mas:
  - a API só atende os repositórios ANEXADOS à sessão (outros recebem 403);
  - chamadas GraphQL são rejeitadas, o que quebra `gh pr` e `gh issue`, mesmo com `GH_TOKEN` próprio;
  - usar `gh api` (REST) para os repositórios anexados.
  - Por isso, **criar e configurar repositórios novos NÃO é trabalho para sessões na nuvem**.

### 14.2 Ambientes de nuvem do Claude Code

Configuração onde cada sessão na nuvem roda.

- Cada ambiente define:
  - acesso à rede (None, Trusted, Full ou Custom);
  - variáveis de ambiente (legíveis por quem usa o ambiente: **NUNCA segredos**);
  - segredos de rede (chaves anexadas pelo proxy às requisições dos hosts listados, invisíveis à sessão; servem para APIs com token fixo, como a do Cloudflare);
  - script de preparação (roda como root antes do Claude Code iniciar; com cache se terminar em cerca de 5 minutos; cache refeito quando o script muda e expira em cerca de 7 dias).
- São **PESSOAIS** (da minha conta) e **NÃO pertencem a repositórios**; a escolha é por sessão (seletor na web/app; `/remote-env` define o padrão da linha de comando; `remote.defaultEnvironmentId` no `.claude/settings.json` de um projeto fixa o ambiente das sessões iniciadas com `claude --cloud` naquele projeto). Ambientes compartilhados com organização só existem nos planos Team/Enterprise.
- **BOA PRÁTICA:** um ambiente por PERFIL DE NECESSIDADE, nunca por repositório ou projeto (evita scripts idênticos duplicados).

#### Ambiente `lab` (padrão, único no início)

- Rede Custom: lista padrão de gerenciadores de pacotes + domínios que as sessões precisam alcançar (ex.: `*.lab.aleogr.dev`).
- Script de preparação: registra o marketplace `aleogr` e instala o orquestrador (`claude plugin marketplace add` + `claude plugin install`), e escreve meu `~/.claude/CLAUDE.md` pessoal. Mesma responsabilidade da Feature `base` ([seção 5](#5-dev-containers-e-codespaces)); manter coerentes. Testar se a instalação de plugins funciona nessa etapa.
- Segredos de rede para APIs com token fixo; variáveis só com valores não sensíveis.

#### Ambientes adicionais

- SÓ quando surgir um perfil realmente diferente: toolchain pesado (ex.: `lab-android` com o SDK do Android, mantendo o script do `lab` abaixo do limite de cache) ou rede diferente (ex.: um sem rede, para revisar código de terceiros).

#### Versão canônica

- Os ambientes são configurados na interface do claude.ai, não por arquivo. A versão CANÔNICA (script de preparação, domínios permitidos, descrição dos segredos de rede sem valores) fica versionada em `docs/cloud-environments/<ambiente>.md` no `aleogr/aleogr`, sem IDs nem segredos, e é copiada para a interface quando mudar.

---

## 15. Testes

> Esta seção registra a **DIREÇÃO** dos testes. Os detalhes de execução ainda estão em aberto e serão definidos antes da implementação; **não implementar nada desta seção sem confirmação**.

Os testes testam a **FERRAMENTA** (o `aleogr/aleogr`), não os meus produtos: "se eu rodar `/aleogr:new-project` com esta declaração, sai um projeto funcionando?". Não confundir com o ambiente de projeto `homolog`, que testa um produto. Os testes são atividade do lab e usam a **PLATAFORMA DO LAB** (custo zero de infraestrutura extra e realismo: exercitam o mesmo compartilhamento dos projetos reais).

### 15.1 Camada 1 — no próprio repositório (estático, sem criar nada fora), em cada PR

- `self-validate-marketplace.yml`: validação do marketplace e das regras de nome, e das declarações de exemplo contra o schema.
- `self-lint.yml`: verificação estática dos workflows e dos scripts dos hooks.
- `self-test-features.yml`: testes das Features com a CLI de dev containers, usando `.devcontainer/features/test/`.
- A única "pasta de testes" no repositório é `marketplace/schemas/examples/`, com as ENTRADAS dos testes (declarações com valores fictícios), nunca projetos com código.

### 15.2 Camada 2 — desenvolvimento local

- Carregar um plugin direto da pasta com `--plugin-dir`, ou registrar o marketplace local com `claude plugin marketplace add ./marketplace`, e experimentar numa pasta de teste no app do Windows. Nada é publicado.

### 15.3 Camada 3 — ponta a ponta

As SAÍDAS dos testes (os projetos criados) ficam **FORA** do `aleogr/aleogr`, porque só um repositório de verdade reproduz o que se testa: criação e proteção de repositório, segredos, workflows (o GitHub só executa os da raiz; a chamada entre repositórios precisa ser exercitada), Codespaces e `.claude/settings.json` (lidos da raiz). Testes dentro do `aleogr/aleogr` também alterariam a proteção e os segredos do próprio repositório e poluiriam o histórico.

- Organização separada no GitHub (`<org-de-testes>`, nome em aberto), gratuita: os repositórios de teste nunca aparecem na minha conta pessoal, e é possível testar segredos no nível de organização. Endereço: `github.com/<org-de-testes>/test-<id>`.
- Executados a partir do **APP DO WINDOWS** (criação de repositórios não funciona em sessões na nuvem, [seção 14](#14-onde-rodo-o-claude-code)).
- Testar o que está na **BRANCH do PR**, antes do merge:
  - workflows reutilizáveis referenciados por nome de branch (`@<branch>`);
  - marketplace registrado com `"ref": "<branch>"`;
  - Features testadas pela camada 1 (e, se necessário, publicadas com versão de pré-lançamento).
- Cada teste usa um `<id>` em TODOS os recursos ([seção 1](#1-nomes)): repositório `test-<id>`, serviços `test-<id>-<componente>` no ambiente de cloud do lab, banco `test_<id>` na instância compartilhada, `test-<id>.lab.aleogr.dev` (com ambientes de projeto: `test-<id>-<ambiente>.lab.aleogr.dev`; tenants: `<tenant>.test-<id>.lab.aleogr.dev`).
- **O teste:** rodar `/aleogr:new-project` com uma declaração de `marketplace/schemas/examples/`; conferir:
  - CI verde;
  - endereço respondendo (e tenants, se houver);
  - codespace abrindo com as ferramentas certas;
  - uma sessão na nuvem do Claude Code no ambiente `lab` funcionando no repositório criado;
  - `plan-project` final dizendo "nada a fazer".
- **Exemplos de cenários:**
  - backend simples (1 componente, 1 ambiente de projeto);
  - monorepo multi-tenant (2 componentes, curinga, CI rodando só o job do componente alterado);
  - dois ambientes de projeto (lab + homolog, com promoção no cd.yml);
  - app Android (só repositório, CI e devcontainer, sem DNS nem cloud).
- Nem todo teste precisa de repositório novo: skills que só mexem em arquivos de um projeto existente podem usar um repositório de teste FIXO na organização, reaproveitado a cada execução.
- Inicialmente executado manualmente; automatizar depois, se fizer sentido.

### 15.4 Pagamentos

- Sempre em modo de teste.

### 15.5 Limpeza

O workflow agendado `self-cleanup-tests.yml` apaga testes com mais de alguns dias, nesta ordem:

1. Ler o `state.json` do repositório `test-<id>`.
2. Apagar os recursos externos (cloud, conferindo também a label `aleogr-test=<id>`; registros DNS/rotas no padrão; bancos `test_<id>`; codespaces).
3. Apagar o repositório POR ÚLTIMO (o estado está nele).

A trava de comandos destrutivos tem exceção APENAS para esses casos ([seção 13.1](#131-hooks)).

---

## 16. Decisões descartadas

- Repositório dedicado ao marketplace (`aleogr-claude-plugins`): substituído pelo `aleogr/aleogr`.
- Ferramentas em repositório privado (`aleogr/lab` com tudo): perderia, no plano gratuito, proteção de branch, minutos ilimitados de Actions e o uso dos workflows por repositórios de outros donos (como a organização de testes), e complicaria Features, schema e marketplace.
- Repositório privado `aleogr/lab` só para dados da plataforma do lab: substituído por segredos no cofre, identificadores por convenção e variáveis do Actions, e estado descoberto no cloud.
- `marketplace.json` na raiz do repositório (com `metadata.pluginRoot`): preterido em favor de tudo dentro de `marketplace/`, pela organização.
- Pasta `actions/` na raiz: as composite actions ficam em `.github/actions/`.
- Pastas `devcontainers/`, `codespaces/` ou `features/` na raiz: as Features ficam em `.devcontainer/features/`.
- Prefixo `aleogr-` nas Features (ex.: `aleogr-setup`, `aleogr-go`): redundante com o endereço `ghcr.io/aleogr/aleogr/`; usar `base`, `go`, `java`...
- Features por tecnologia que reinstalam a linguagem, ou que usam `dependsOn` na oficial.
- Skills de família só com a ação (`create-repo`): seria mais limpo e confiaria no namespace, mas optei pela proteção adicional do provedor no nome.
- Formato `<ação>-<provedor>` (`create-repo-github`): substituído por `<provedor>-<ação>` (`github-create-repo`), que agrupa as skills por provedor.
- Campo `name:` no frontmatter de `SKILL.md` de plugin.
- `dependencies` ligando o orquestrador aos plugins de família.
- Confiar no `.claude/settings.json` do repositório para levar plugins às sessões na nuvem do Claude Code (elas não instalam esses plugins).
- Um ambiente de nuvem do Claude Code por repositório ou por projeto; segredos em variáveis de ambiente desses ambientes.
- Criar ou configurar repositórios a partir de sessões na nuvem do Claude Code (limites do proxy do GitHub).
- `.gitkeep` onde um README curto pode documentar a pasta; `.github/README.md` (substituiria o README do perfil); pasta de plugin criada antes do plugin.
- Projetos de teste (com código) dentro do `aleogr/aleogr`; repositórios de teste na conta pessoal; projeto de cloud separado só para testes ("sandbox" fixo no GCP); um projeto de cloud novo a cada teste.
- Árvores de DNS separadas para testes (`sandbox.aleogr.dev`, `sandbox.lab.aleogr.dev`): os testes ficam direto no lab com prefixo reservado, pela URL mais curta.
- Testes por caminho (`lab.aleogr.dev/test-<id>`): exigiria roteador, apps sob subcaminho (diferente da realidade), origem compartilhada entre testes (cookies e armazenamento vazando) e não comportaria tenants.
- Homologação como `homolog.<projeto>.lab.aleogr.dev` (conflita com tenants).
- No lab: instâncias dedicadas por projeto, load balancer, IP estático, NAT ou qualquer custo fixo por projeto.
- Usar o `aleogr/aleogr` como repositório de dotfiles do Codespaces.
- Um workflow de CI por componente com filtro `on.push.paths` (trava checks obrigatórios).
- `secrets: inherit` nos workflows reutilizáveis.
- Nome "bootstrap" (genérico, ambíguo com o framework CSS); `init` (comando embutido).
- Skill genérica única tipo "setup-cloud".
- Versionar o mesmo projeto em mais de um host Git (espelhamento).
- O mesmo componente replicado em mais de um cloud.
- Repositório central obrigatório em projetos multi-repo.

---

## 17. Estratégia de implementação

- Construir guiado pelo **PRÓXIMO PROJETO REAL**: só os plugins, workflows, actions e Features que ele exige (provavelmente `aleogr`, `aleogr-repo-github`, `aleogr-cloud-gcp`, `aleogr-dns-cloudflare`, a Feature `base`, o ambiente de nuvem `lab` e os workflows reutilizáveis das stacks do projeto). **Meta:** o projeto sai do zero sem eu abrir nenhum painel.
- Antes do primeiro projeto: entender e declarar a plataforma do lab existente ([seções 6](#6-o-lab-ambientes-de-projeto-e-custo-mínimo) e [7](#7-onde-ficam-os-dados)), a partir da investigação pendente.
- **MVP do orquestrador:** `check-environment`, `declare-project`, `plan-project`, `apply-project`, mais o hook de trava de comandos destrutivos (já com as exceções de teste) e permissões de leitura em `allow`.
- A declaração do próximo projeto real, com valores fictícios, vira o primeiro exemplo em `marketplace/schemas/examples/` e o primeiro teste ponta a ponta, antes de ser aplicada ao projeto de verdade.
- Novas famílias, provedores, actions, workflows, Features e ambientes de nuvem entram quando um projeto real precisar.

---

## 18. Pendências

- [ ] **INVESTIGAR (somente leitura) como o lab funciona hoje:**
  - no Cloudflare: registros DNS de `lab` e `*.lab` (CNAME para `*.cfargotunnel.com` = túnel; para `ghs.googlehosted.com` = mapeamento de domínio do Cloud Run; para `*.run.app` = serviço direto; registro A = VM com proxy reverso; proxy ativo ou não), Workers e rotas em `lab.aleogr.dev`, túneis e Access (Zero Trust), SSL/TLS → Edge Certificates (certificados avançados, Total TLS);
  - no GCP: mapeamentos de domínio do Cloud Run, VMs e a instância compartilhada do Cloud SQL.
  - O resultado define: a solução de certificados, o contrato de dns-* no lab (registro ou rota) e a declaração da plataforma do lab.
- [ ] Criar o ambiente de nuvem `lab` do Claude Code; testar se o script de preparação consegue registrar o marketplace e instalar plugins; definir os domínios permitidos e os segredos de rede (ex.: token da API do Cloudflare); versionar a definição canônica em `docs/cloud-environments/lab.md`.
- [ ] Definir como os plugins de FAMÍLIA chegam às sessões na nuvem. Opções:
  - (a) o script de preparação do `lab` instala todos os plugins do marketplace (sem colisão, graças ao provedor no nome das skills, mas com mais skills no contexto);
  - (b) um hook SessionStart do projeto, só quando `CLAUDE_CODE_REMOTE=true`, instala os plugins da declaração (testar se carregam sem reiniciar a sessão).
- [ ] Decidir o nome da organização de testes no GitHub. Ideias: `aleogr-sandbox`; ou `aleogr-graveyard`, que também receberia meus projetos aposentados (transferidos e SEMPRE arquivados, nunca com prefixo `test-` nem tópico `aleogr-test`). As regras de exceção da trava já cobrem os dois cenários.
- [ ] Definir os detalhes de execução dos testes ([seção 15](#15-testes)) antes de implementá-los.
- [ ] Definir os identificadores da plataforma do lab que não puderem ser deduzidos e gravá-los como variáveis do Actions no `aleogr/aleogr`; configurar alertas de orçamento.
- [ ] Testar o registro via `extraKnownMarketplaces` com `path` (e com `ref` de branch) e a resolução dos caminhos relativos a partir de `marketplace/`.
- [ ] Testar a referência a Feature local em caminho aninhado (`./features/src/base`); se não funcionar, subir as Features um nível.
- [ ] Marcar as Features como públicas no GHCR após a primeira publicação.
- [ ] Configurar limite de gastos e tempo de inatividade do Codespaces; criar o secret do Codespaces para autenticação do Claude Code.
- [ ] Confirmar "create-environment" como nome da ação de cloud-*.
- [ ] Decidir se create-plugin/validate-marketplace ficam no `aleogr` ou em `aleogr-dev`.
- [ ] Avaliar, com o MVP, tornar o `state.json` dos projetos mais leve ou só um cache da descoberta.
- [ ] Configurar a proteção da `main` do `aleogr/aleogr` (exigir PR) e conferir o 2FA.
- [ ] Escolher o próximo projeto real para guiar o MVP.
