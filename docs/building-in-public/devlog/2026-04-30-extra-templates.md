# Extra Templates CLI

**Date:** 2026-04-30
**Author:** Diego

## Focus

Implement GitHub issue #33: expose feed-level additive templates through CLI and listing commands without renaming the persisted `custom_templates` schema field.

## Progress

Technical review confirmed the issue is still current. `FeedConfig.custom_templates` exists, and `TemplateSelector` already treats custom templates as additive. The missing pieces are CLI write paths, feed listing visibility, feed-mode merge into pipeline options, and docs/tests.

## Decision

Keep `custom_templates` in YAML for compatibility. Use `--extra-templates` in CLI copy because it describes behavior: feed templates are added to default/category-selected templates.

## Next

Add focused integration tests for add/config/list behavior, update docs, and open a PR closing #33.
