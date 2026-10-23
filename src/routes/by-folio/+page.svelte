<script lang="ts">
  import { resolve } from '$app/paths';
  import { onMount } from 'svelte';
  import CaretDownIcon from 'phosphor-svelte/lib/CaretDownIcon';
  import Meta from '#lib/components/Meta.svelte';

  import {
    buildRows,
    fmt0,
    median,
    paperName,
    pct,
    scriptHash,
    store,
    type Row
  } from '#lib/bench.js';

  let { data } = $props();
  const KEY = 'paleo-bench:by-folio';
  const S = $derived(data.summary.samples);
  const rows = $derived(buildRows(data.summary));

  let sort = $state<'mean' | number>('mean');
  let selected = $state<string | null>(null);

  onMount(() => {
    const saved = store.get<'mean' | number>(KEY);
    if (saved === 'mean' || (typeof saved === 'number' && saved < S.length)) sort = saved;
    selected = store.get<{ slug: string }>('paleo-bench:transcriptions')?.slug ?? null;
  });

  function sortBy(next: 'mean' | number) {
    sort = next;
    store.set(KEY, next);
  }

  const groups = $derived(
    S.reduce<{ microfilm: boolean; n: number }[]>((acc, s) => {
      const last = acc.at(-1);
      if (last && last.microfilm === s.microfilm) last.n++;
      else acc.push({ microfilm: s.microfilm, n: 1 });
      return acc;
    }, [])
  );

  const ordered = $derived.by(() => {
    const val = (r: Row) => {
      if (sort === 'mean') return r.std.mark;
      const c = r.cells[sort];
      return c.kind === 'ok' ? c.v : null;
    };
    return [...rows].sort((a, b) => {
      const x = val(a);
      const y = val(b);
      if (x == null && y != null) return 1;
      if (y == null && x != null) return -1;

      return (
        (y ?? 0) - (x ?? 0) ||
        (b.std.mark ?? -1) - (a.std.mark ?? -1) ||
        a.m.label.localeCompare(b.m.label)
      );
    });
  });

  const medians = $derived(
    S.map((_, p) => median(rows.flatMap((r) => (r.cells[p].kind === 'ok' ? [r.cells[p].v] : []))))
  );
  const medianMean = $derived(
    median(rows.flatMap((r) => (r.std.mark == null ? [] : [r.std.mark])))
  );
  const places = $derived(
    S.map((_, p) => {
      const cer = (r: Row) => (r.cells[p].kind === 'ok' ? r.res[p]!.cer! : null);
      const all = rows.flatMap((r) => cer(r) ?? []);
      return new Map(
        rows.flatMap((r) => {
          const c = cer(r);
          const place = c == null ? 4 : 1 + all.filter((x) => x < c).length;
          return place <= 2 ? [[r.i, place] as const] : [];
        })
      );
    })
  );
  const SUFFIX = ['', 'st', 'nd'];
  const ordinal = (n: number) => `${n}${SUFFIX[n]}`;
  const link = (r: Row, p: number) => resolve('transcriptions') + scriptHash(r, p);
</script>

<Meta
  title="By folio, Paleo Bench"
  description="Scores for {rows.length} model configurations on each of {S.length} Byzantine Greek manuscript folios, from colour images and microfilm."
/>

<section class="lead">
  <h1>By folio</h1>
  <ul class="points">
    <li>Scores out of 100, one per folio</li>
    <li>Circled: under 50; failed: timeout, token limit or request error</li>
    <li>Highlighted: 1st and 2nd on each folio by character error</li>
    <li>Median: middle score among models that ran the folio</li>
    <li>Select a score to open its transcription, a heading to sort</li>
  </ul>
</section>

<div class="sheet book-sheet">
  <div class="tbl-wrap">
    <table class="book">
      <thead>
        <tr class="h1">
          <th rowspan="2" scope="col" class="cand-h">Model</th>
          {#each groups as g, k (k)}
            <th scope="colgroup" colspan={g.n} class="grp"
              >{g.microfilm ? 'Microfilm' : 'Colour images'}</th
            >
          {/each}
          <th
            rowspan="2"
            scope="col"
            class="mean-h"
            aria-sort={sort === 'mean' ? 'descending' : 'none'}
          >
            <button type="button" class="sort" onclick={() => sortBy('mean')}
              >Mean{#if sort === 'mean'}{' '}<CaretDownIcon
                  class="ico"
                  aria-hidden="true"
                />{/if}</button
            >
          </th>
        </tr>
        <tr class="h2">
          {#each S as s, p (s.id)}
            <th scope="col" aria-sort={sort === p ? 'descending' : 'none'}>
              <button
                type="button"
                class="sort"
                title="Sort by {paperName(s)}"
                onclick={() => sortBy(p)}
              >
                {s.ms}{#if sort === p}{' '}<CaretDownIcon
                    class="ico"
                    aria-hidden="true"
                  />{/if}<span>{s.folio}</span>
              </button>
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each ordered as r (r.i)}
          <tr class:sel={r.m.slug === selected}>
            <td class="cand"><a href={link(r, 0)}>{r.m.label}</a></td>
            {#each r.cells as c, p (p)}
              <td class="m">
                {#if c.kind === 'none'}
                  <span class="mk na" title="{r.m.label} did not run on {paperName(S[p])}">–</span>
                {:else if c.kind === 'abs'}
                  <a
                    class="mk ab"
                    href={link(r, p)}
                    title="Failed: {c.why}"
                    aria-label="{r.m.label}, {paperName(S[p])}: failed, {c.why}">failed</a
                  >
                {:else}
                  {@const place = places[p].get(r.i)}
                  <a
                    class="mk"
                    class:lo={c.v < 50}
                    data-place={place}
                    href={link(r, p)}
                    title={place
                      ? `${ordinal(place)}, character error ${pct(r.res[p]!.cer)}`
                      : undefined}
                    aria-label="{r.m.label}, {paperName(S[p])}: {c.v}{place
                      ? `, ${ordinal(place)}`
                      : ''}"
                    >{c.v}{#if place}<span class="pl" aria-hidden="true"
                        >{place}<span class="sfx">{SUFFIX[place]}</span></span
                      >{/if}</a
                  >
                {/if}
              </td>
            {/each}
            <td class="mean">
              {#if r.std.mark == null}
                <span class="ab">failed</span>
              {:else}
                {Math.round(r.std.mark)}{#if r.sat < S.length}<small
                    >{r.sat} of {S.length} run</small
                  >{/if}
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row">Median</th>
          {#each medians as v, p (p)}<td>{fmt0(v)}</td>{/each}
          <td class="mean">{fmt0(medianMean)}</td>
        </tr>
      </tfoot>
    </table>
  </div>
</div>

<style>
  .book-sheet {
    overflow: hidden;
  }

  .tbl-wrap {
    overflow: auto;
    max-height: calc(100vh - 120px);
    min-height: 360px;
  }

  .book {
    border-collapse: separate;
    border-spacing: 0;
    width: 100%;
    font-variant-numeric: tabular-nums;
  }

  th,
  td {
    padding: 0;
    background: var(--paper);
    border-bottom: 1px solid var(--rule);
  }

  thead th {
    position: sticky;
    top: 0;
    z-index: 2;
    font-weight: 500;
    font-size: 0.82rem;
    color: var(--pencil);
    text-align: center;
    vertical-align: bottom;
  }

  .h1 th {
    height: 1.8rem;
    padding: 0 0.3rem;
    border-bottom: 0;
  }

  .h1 th.grp {
    border-bottom: 1px solid var(--edge);
  }

  .h2 th {
    top: 1.8rem;
    width: 7.5%;
    border-bottom: 1.5px solid var(--ink);
  }

  .cand-h {
    left: 0;
    z-index: 3;
    text-align: left;
    padding: 0 0.6rem 0.45rem 0.7rem;
    border-bottom: 1.5px solid var(--ink) !important;
  }

  .mean-h {
    width: 7.5%;
    border-bottom: 1.5px solid var(--ink) !important;
  }

  .cand-h,
  td.cand,
  tfoot th {
    border-right: 1.5px solid var(--margin);
  }

  .mean-h,
  td.mean {
    border-left: 1.5px solid var(--margin);
  }

  td.cand,
  tfoot th {
    position: sticky;
    left: 0;
    z-index: 1;
  }

  tbody tr:hover td,
  tr.sel td {
    background: var(--tint);
  }

  .sort {
    display: block;
    width: 100%;
    padding: 0.35rem 0.3rem 0.4rem;
    line-height: 1.1;
    background: none;
    border: 0;
    cursor: pointer;
    color: inherit;
  }

  .sort span {
    display: block;
    font-size: 0.72rem;
    color: var(--faint);
  }

  th[aria-sort='descending'] .sort {
    color: var(--ink);
  }

  td.cand a {
    display: block;
    padding: 0.42rem 0.6rem 0.42rem 0.7rem;
    font-weight: 500;
    font-size: 0.92rem;
    line-height: 1.2;
    white-space: nowrap;
    text-decoration: none;
  }

  td.cand a:hover {
    text-decoration: underline;
  }

  td.m {
    text-align: center;
  }

  a.mk {
    margin: 0.16rem 0.03rem;
    font-weight: 500;
    font-size: 0.95rem;
  }

  a.mk:hover {
    box-shadow: 0 0 0 1.5px var(--ink);
  }

  a.mk[data-place] {
    position: relative;
    border-radius: 2px;
    background: var(--gold);
  }

  a.mk[data-place='2'] {
    background: var(--silver);
  }

  .pl {
    position: absolute;
    left: 100%;
    top: 50%;
    transform: translateY(-50%);
    margin-left: 0.25rem;
    font-size: 0.62rem;
    font-weight: 700;
    line-height: 1;
    color: var(--pencil);
  }

  td.mean {
    text-align: right;
    padding: 0.3rem 0.7rem 0.3rem 0.5rem;
    font-weight: 700;
    white-space: nowrap;
  }

  td.mean small {
    display: block;
    font-weight: 400;
    font-size: 0.72rem;
    color: var(--pencil);
    line-height: 1.1;
  }

  tfoot th,
  tfoot td {
    position: sticky;
    bottom: 0;
    z-index: 2;
    background: var(--tint);
    border-top: 1.5px solid var(--ink);
    border-bottom: 0;
    font-weight: 500;
  }

  tfoot th {
    z-index: 3;
    text-align: left;
    padding: 0.45rem 0.7rem;
    font-size: 0.92rem;
  }

  tfoot td {
    text-align: center;
    padding: 0.45rem 0.2rem;
    color: var(--pencil);
  }

  @media (max-width: 760px) {
    a.mk[data-place] {
      grid-auto-flow: column;
    }

    .pl {
      position: static;
      align-self: start;
      transform: none;
      margin: 0.1rem 0 0 1px;
      font-size: 0.55rem;
    }

    .sfx {
      display: none;
    }
  }
</style>
