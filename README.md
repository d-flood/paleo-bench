# htr-bench

Static SvelteKit site for viewing benchmark output stored in `static/results.json`.

## Local development

```sh
bun install --frozen-lockfile
bun run dev
```

## Build

```sh
bun run build
```

The build runs `scripts/generate-results-version.mjs` before `vite build`, generating
`static/results.version.json` from the current `static/results.json`.

## Update benchmark results

Benchmark execution is manual. After running the benchmark locally:

1. Replace `static/results.json` with the new output.
2. Commit the updated `static/results.json` (and generated `static/results.version.json` if changed).
3. Push to `main` to trigger deployment.

If you edited only ground-truth text and want to recompute comparisons without calling models again:

```sh
uv run python -m paleo_bench --config config.toml --recompute-comparisons
```

This recalculates per-row metrics plus model/group summaries from existing `static/results.json`.

