# Feed Count Support

**Date:** 2026-04-30
**Author:** Diego

## Focus

Implement GitHub issue #57: `inkwell fetch <feed-name> --count N` for processing the N latest episodes from a saved feed.

## Progress

Started from the OBRA-3 technical review. The docs already mention `--count`, but the current CLI only supports `--latest` and `--episode` selectors for feeds.

## Observations

The existing feed parser already has range/list/position selection with a max episode limit. `--count` should use that same limit but stay explicit in the CLI so validation and help text are clear.

## Next

Add parser/CLI support, focused tests, and docs updates. Land as a PR closing #57.

## Links

- Issue: #57
