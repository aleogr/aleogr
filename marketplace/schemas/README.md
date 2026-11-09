# Schemas

JSON Schema for the project declaration (`.aleogr/project.json`) and example declarations.

Source of truth: [`docs/DESIGN.md` — section 11](../../docs/DESIGN.md#11-project-model) (tests in [section 15](../../docs/DESIGN.md#15-tests)).

## Local rules

- `project.schema.json` is versioned; `project.json` has a `version` field and `$schema` for autocomplete:
  `https://raw.githubusercontent.com/aleogr/aleogr/main/marketplace/schemas/project.schema.json`.
- Exclusive families = object; combinable = list; exactly one `primary` cloud; payments `mode` defaults to `"test"`; `environments` field; optional `notes` field.
- Project names **cannot** start with `test-` (prefix reserved for tests).
- Family plugins may publish sub-schemas for their options.
- `examples/`: JSON declarations with **fictitious values** only — they are the test inputs; validated against the schema on every PR (`self-validate-marketplace.yml`). Never projects with code.
