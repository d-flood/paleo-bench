# htr-bench

Static SvelteKit site for viewing benchmark output stored in `static/results.json`.

At build/dev startup, `scripts/split-results-for-site.mjs` derives lightweight site artifacts:

- `static/site-data/summary.json`
- `static/site-data/compare-index.json`
- `static/site-data/samples/*.json`

This keeps the initial HTML/data payload small while preserving an interactive compare view.

## Local development

```sh
bun install --frozen-lockfile
bun run dev
```

## Build

```sh
bun run build
```

The build runs `scripts/split-results-for-site.mjs` before `vite build`, generating
`static/site-data/*` from the current `static/results.json`.

## Update benchmark results

Benchmark execution is manual. After running the benchmark locally:

1. Replace `static/results.json` with the new output.
2. Run `bun run gen:site-data` (or run `bun run build`, which generates site data automatically).
3. Commit the updated `static/results.json` and generated `static/site-data/*`.
4. Push to `main` to trigger deployment.

If you edited only ground-truth text and want to recompute comparisons without calling models again:

```sh
uv run python -m paleo_bench --config config.toml --recompute-comparisons
```

This recalculates per-row metrics plus model/group summaries from existing `static/results.json`.
