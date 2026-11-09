# Marketplace `aleogr`

Raiz do marketplace de plugins do Claude Code (o diretório que contém `.claude-plugin/marketplace.json`).

Fonte da verdade: [`docs/DESIGN.md` — seção 2](../docs/DESIGN.md#2-estrutura-de-aleograleogr) (nomes na [seção 1](../docs/DESIGN.md#1-nomes)).

## Como registrar

Como o `marketplace.json` não está na raiz do repositório, `claude plugin marketplace add aleogr/aleogr` **não funciona**. Registre em `extraKnownMarketplaces`:

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

Onde colocar, conforme onde o Claude Code roda:

- **Local (app do Windows):** à mão, uma vez por computador, em `~/.claude/settings.json`; nos projetos, o `sync-plugins` escreve o bloco no `.claude/settings.json` (plugins de família no escopo do projeto).
- **Codespaces:** a Feature `base` faz o registro.
- **Sessões na nuvem do Claude Code:** o script de preparação do ambiente de nuvem `lab` faz o registro (o `.claude/settings.json` do repositório **não** instala plugins nessas sessões).
- **Testar uma branch:** acrescente `"ref": "<branch>"` ao `source`.

## Regras locais

- `source` dos plugins relativos a esta pasta (`./plugins/aleogr`), sem `..`.
- Validação: `claude plugin validate ./marketplace`. Teste local: `claude plugin marketplace add ./marketplace`.
- Toda entrada do `marketplace.json` tem `category` e `displayName`, e seu nome é igual ao `name` do `plugin.json`.
- Não usar `dependencies` para ligar o orquestrador aos plugins de família.
- `defaults.json` (futuro): só escolhas pessoais, sem IDs nem segredos.
