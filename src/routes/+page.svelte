<script lang="ts">
  import { resolve } from '$app/paths';
  import { onMount } from 'svelte';
  import CaretDownIcon from 'phosphor-svelte/lib/CaretDownIcon';
  import CaretUpIcon from 'phosphor-svelte/lib/CaretUpIcon';
  import MagnifyingGlassIcon from 'phosphor-svelte/lib/MagnifyingGlassIcon';
  import Mark from '#lib/components/Mark.svelte';
  import Meta from '#lib/components/Meta.svelte';
  import {
    PROVIDERS,
    buildRows,
    fmt0,
    fmt1,
    fmtCost,
    fmtTime,
    pct,
    rank,
    scriptHash,
    store,
    who,
    type Row
  } from '#lib/bench.js';

  let { data } = $props();

  const KEY = 'paleo-bench:results';
  const st = $state({ q: '', prov: 'all', zero: false, sort: 'mark', dir: -1 });
  let restored = $state(false);

  onMount(() => {
    Object.assign(st, store.get(KEY) ?? {});
    restored = true;
  });

  $effect(() => {
    if (restored) store.set(KEY, $state.snapshot(st));
  });

  const total = $derived(data.summary.samples.length);
  const papers = (microfilm: boolean) =>
    data.summary.samples.flatMap((s, p) => (s.microfilm === microfilm ? [p + 1] : []));

  const ranges = (ns: number[]) =>
    ns
      .reduce<number[][]>((acc, n) => {
        const last = acc.at(-1);
        if (last && n === last[last.length - 1] + 1) last.push(n);
        else acc.push([n]);
        return acc;
      }, [])
      .map((r) => (r.length > 1 ? `${r[0]}–${r[r.length - 1]}` : `${r[0]}`))
      .join(', ');
  const colourPapers = $derived(ranges(papers(false)));
  const microfilmPapers = $derived(ranges(papers(true)));
  const rows = $derived(buildRows(data.summary));
  const ranking = $derived(rank(rows, st.zero));
  const v = (r: Row) => (st.zero ? r.zero : r.std);
  const href = (r: Row) => resolve('transcriptions') + scriptHash(r, 0);
  const costPerImage = (r: Row) =>
    r.m.cost > 0 && r.attempted > 0 ? r.m.cost / r.attempted : null;

  const COLS = [
    { k: 'pos', name: 'Position', cls: 'pos' },
    { k: 'cand', name: 'Model', cls: 'tl', dir: 1 },
    { k: 'mark', name: 'Score', cls: 'mark', dir: -1 },
    { k: 'cer', name: 'Character error', cls: 'c-cer', dir: 1 },
    { k: 'wer', name: 'Word error', cls: 'c-wer', dir: 1 },
    { k: 'col', name: 'Colour images', cls: 'c-col grp', dir: -1 },
    { k: 'mic', name: 'Microfilm', cls: 'c-mic', dir: -1 },
    { k: 'sat', name: 'Folios run', cls: 'c-sat', dir: -1 },
    { k: 'cost', name: 'Cost', cls: '', dir: 1 },
    { k: 'time', name: 'Time', cls: 'c-time', dir: 1 }
  ];

  const sub = (k: string) =>
    ({
      mark: st.zero ? 'failed folios count 0' : 'mean of folios run',
      col: colourPapers && `folios ${colourPapers}`,
      mic: microfilmPapers && `folios ${microfilmPapers}`,
      cost: 'per image',
      time: 'all folios'
    })[k] ?? '';

  function val(r: Row, k: string): number | string | null {
    switch (k) {
      case 'cand':
        return r.m.label;
      case 'cer':
        return v(r).cer;
      case 'wer':
        return v(r).wer;
      case 'col':
        return v(r).colour;
      case 'mic':
        return v(r).micro;
      case 'sat':
        return r.sat;
      case 'cost':
        return costPerImage(r);
      case 'time':
        return r.m.latency;
      default:
        return v(r).mark;
    }
  }

  const shown = $derived.by(() => {
    const q = st.q.trim().toLowerCase();
    const posOf = (r: Row) => ranking.pos.get(r.i) ?? 999;
    return rows
      .filter(
        (r) =>
          (!q || r.m.label.toLowerCase().includes(q)) &&
          (st.prov === 'all' || r.m.provider === st.prov)
      )
      .sort((a, b) => {
        const x = val(a, st.sort);
        const y = val(b, st.sort);
        if (x == null && y == null) return posOf(a) - posOf(b);
        if (x == null) return 1;
        if (y == null) return -1;
        const d = typeof x === 'string' ? x.localeCompare(String(y)) : x - (y as number);
        return d * st.dir || posOf(a) - posOf(b);
      });
  });

  function sortBy(k: string, dir: number) {
    st.dir = st.sort === k ? -st.dir : dir;
    st.sort = k;
  }
</script>

<Meta
  title="Paleo Bench"
  description="Compare how well {rows.length} model configurations transcribe Byzantine Greek manuscripts against a human committee transcription."
/>

<section class="lead">
  <h1>Results</h1>
</section>

<div class="controls" role="group" aria-label="Filter the models">
  <label class="vh" for="q">Find a model</label>
  <span class="search">
    <MagnifyingGlassIcon aria-hidden="true" />
    <input
      class="inp q"
      type="search"
      id="q"
      placeholder="Find a model"
      autocomplete="off"
      bind:value={st.q}
    />
  </span>
  <label class="vh" for="prov">Provider</label>
  <select class="sel" id="prov" bind:value={st.prov}>
    <option value="all">All providers</option>
    {#each PROVIDERS as p (p)}<option>{p}</option>{/each}
  </select>
  <label class="check"
    ><input type="checkbox" bind:checked={st.zero} /> Count failed folios as 0</label
  >
</div>

<div class="sheet">
  <div class="tbl-x">
    <table class="board">
      <thead>
        <tr>
          {#each COLS as c (c.k)}
            <th
              scope="col"
              class={c.cls}
              aria-sort={c.k !== 'pos' && st.sort === c.k
                ? st.dir > 0
                  ? 'ascending'
                  : 'descending'
                : undefined}
            >
              {#if c.k === 'pos'}
                {c.name}
              {:else}
                <button type="button" class="sortb" onclick={() => sortBy(c.k, c.dir ?? -1)}>
                  {c.name}{#if st.sort === c.k}{' '}{#if st.dir > 0}<CaretUpIcon
                        class="ico"
                        aria-hidden="true"
                      />{:else}<CaretDownIcon
                        class="ico"
                        aria-hidden="true"
                      />{/if}{/if}{#if sub(c.k)}<span>{sub(c.k)}</span>{/if}
                </button>
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each shown as r (r.i)}
          {@const x = v(r)}
          {@const cost = costPerImage(r)}
          <tr>
            <td class="pos">{ranking.label(r.i)}</td>
            <td class="cand tl">
              <a class="row-link" href={href(r)}>{r.m.label}</a>
              <span class="who">{who(r.m)}</span>
              <span class="mob">
                {x.mark == null
                  ? `No folios run, ${r.absent} failed`
                  : `Character error ${pct(x.cer)}, colour ${fmt0(x.colour)}, microfilm ${fmt0(x.micro)}, ${r.sat} of ${total} run, ${fmtTime(r.m.latency)}`}
              </span>
            </td>
            <td class="mark">
              {#if x.mark == null}
                <span class="ab">failed</span>
              {:else}
                <span class="mv">{fmt1(x.mark)}</span>
                <span class="mbar" aria-hidden="true" style:width="{x.mark}%"></span>
              {/if}
            </td>
            <td class="c-cer">{pct(x.cer)}</td>
            <td class="c-wer">{pct(x.wer)}</td>
            <td class="c-col grp"><Mark value={x.colour} /></td>
            <td class="c-mic"><Mark value={x.micro} /></td>
            <td class="c-sat sat">
              {#if r.sat === total}{total}{:else}{r.sat} of {total}{#if r.absent}<small
                    >{r.absent} failed</small
                  >{/if}{/if}
            </td>
            <td
              >{#if cost != null}{fmtCost(cost)}{:else}<span class="mk na" title="No cost recorded"
                  >–</span
                >{/if}</td
            >
            <td class="c-time">{fmtTime(r.m.latency)}</td>
          </tr>
        {:else}
          <tr>
            <td colspan={COLS.length} class="tl">
              <p class="empty">No match. Clear the search or change a filter.</p>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</div>
<p class="count">
  {shown.length} of {rows.length} models
</p>

<style>
  .search {
    position: relative;
    display: flex;
    align-items: center;
  }

  .search :global(svg) {
    position: absolute;
    left: 0.55rem;
    color: var(--pencil);
    pointer-events: none;
  }

  .q {
    width: 15rem;
    padding-left: 1.9rem;
  }

  .tbl-x {
    overflow-x: auto;
  }

  .board {
    width: 100%;
    border-collapse: collapse;
    font-variant-numeric: tabular-nums;
  }

  .board th {
    font-weight: 500;
    font-size: 0.84rem;
    color: var(--pencil);
    text-align: right;
    padding: 0.7rem 0.7rem 0.45rem;
    border-bottom: 1.5px solid var(--ink);
    vertical-align: bottom;
    white-space: nowrap;
  }

  .board td {
    padding: 0.5rem 0.7rem;
    border-bottom: 1px solid var(--rule);
    text-align: right;
    vertical-align: middle;
    white-space: nowrap;
  }

  .board tbody tr {
    position: relative;
  }

  .board tbody tr:hover td,
  .board tbody tr:focus-within td {
    background: var(--tint);
  }

  .tl {
    text-align: left !important;
  }

  .pos {
    width: 3.4rem;
    padding-right: 0.9rem !important;
    border-right: 1.5px solid var(--margin);
  }

  td.pos {
    font-family: var(--f-script);
    font-size: 1.1rem;
    color: var(--pencil);
  }

  .cand {
    white-space: normal !important;
    min-width: 12rem;
  }

  .row-link {
    font-weight: 500;
    font-size: 1.02rem;
    text-decoration: none;
  }

  .row-link::after {
    content: '';
    position: absolute;
    inset: 0;
  }

  .row-link:hover {
    text-decoration: underline;
    text-underline-offset: 3px;
  }

  .who {
    display: block;
    font-size: 0.82rem;
    color: var(--pencil);
  }

  .mob {
    display: none;
  }

  .mark {
    min-width: 7rem;
  }

  .mv {
    font-family: var(--f-script);
    font-weight: 500;
    font-size: 1.5rem;
    line-height: 1;
  }

  .mbar {
    position: absolute;
    left: 0;
    bottom: 0;
    height: 3px;
    background: var(--bar);
    pointer-events: none;
  }

  .sat small {
    display: block;
    font-size: 0.76rem;
    color: var(--pencil);
  }

  .grp {
    border-left: 1px solid var(--rule);
  }

  .sortb {
    background: none;
    border: 0;
    padding: 0;
    cursor: pointer;
    color: inherit;
    font: inherit;
    text-align: inherit;
  }

  th[aria-sort] .sortb {
    color: var(--ink);
  }

  th[aria-sort] .sortb :global(.ico) {
    color: var(--bar);
  }

  .sortb span {
    display: block;
    font-size: 0.74rem;
    color: var(--faint);
  }

  .count {
    color: var(--pencil);
    font-size: 0.9rem;
    margin: 10px 2px 0;
  }

  @media (max-width: 760px) {
    .c-cer,
    .c-wer,
    .c-col,
    .c-mic,
    .c-sat,
    .c-time {
      display: none;
    }

    .mob {
      display: block;
      font-size: 0.8rem;
      color: var(--pencil);
      margin-top: 2px;
    }

    .board th,
    .board td {
      padding-left: 0.45rem;
      padding-right: 0.45rem;
    }

    .pos {
      width: 2.6rem;
      padding-right: 0.6rem !important;
    }

    .cand {
      min-width: 0;
    }

    .mark {
      min-width: 4.2rem;
    }

    .mv {
      font-size: 1.3rem;
    }

    .search,
    .q {
      width: 100%;
    }
  }
</style>
