# Dev Container Features

Features distributed to projects, published at `ghcr.io/aleogr/aleogr/<id>`.

Source of truth: [`docs/DESIGN.md` — section 5](../../docs/DESIGN.md#5-dev-containers-and-codespaces) (names in [section 1](../../docs/DESIGN.md#dev-container-features)).

## Local rules

- Named after the **technology, without prefix** (`go`, `java`, `python`, `android`); the Feature common to all projects is `base`.
- Dev containers CLI layout: source in `src/<id>/`, tests in `test/<id>/`; the subfolder has the same name as the `id`.
- `base`: registers the `aleogr` marketplace in the container's Claude Code and brings what is common to all projects. Keep it consistent with the setup script of the `lab` cloud environment (section 14).
- Per-technology Features are only a **preferences layer** over the official one: they don't reinstall the language, they declare `"installsAfter": ["ghcr.io/devcontainers/features/<technology>"]` and **never** use `dependsOn` on the official one.
- A technology's folder only exists if there is something to add to the official one.
- Each Feature has its own semver version in `devcontainer-feature.json`. Published by `self-publish-features.yml`; mark the package as public on GHCR on first publication.
- The `.gitkeep` files in `src/` and `test/` are removed when the first Feature/test exists.
