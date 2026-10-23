<script lang="ts">
  import { resolve } from '$app/paths';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import Scatter from '#lib/components/Scatter.svelte';
  import {
    FAMILIES,
    buildRows,
    family,
    familyColor,
    fmt0,
    fmt1,
    fmtCost,
    fmtTime,
    median,
    rank,
    scriptHash,
    store,
    who,
    type Row
  } from '#lib/bench.js';

  let { data } = $props();

  const KEY = 'paleo-bench:graphs';
  const total = $derived(data.summary.samples.length);
  const rows = $derived(buildRows(data.summary));
  const ranking = $derived(rank(rows, false));
  const bySlug = $derived(new Map(rows.map((r) => [r.m.slug, r])));

  let fam = $state('all');
  let line = $state(false);
  let hov = $state<number | null>(null);
  let pin = $state<number | null>(null);
  const pinned = $derived(rows[pin ?? ranking.order[0].i]);

  function choose(i: number) {
    pin = i;
    store.set(KEY, rows[i].m.slug);
    goto(`#${rows[i].m.slug}`, { shallow: true, replace: true });
  }

  function fromHash() {
    const r = bySlug.get(location.hash.slice(1));
    if (r) pin = r.i;
  }

  onMount(() => {
    const saved = bySlug.get(store.get<string>(KEY) ?? '');
    if (saved) pin = saved.i;
    fromHash();
  });

  const times = (a: number, b: number) => {
    const x = a / b;
    return `${x >= 10 ? Math.round(x) : x.toFixed(1).replace(/\.0$/, '')}×`;
  };

  const answers = $derived.by(() => {
    const ok = rows.filter((r) => r.std.mark != null);
    const top = ranking.order[0];
    const list: { r: Row | null; pre: string; post: string }[] = [
      {
        r: top,
        pre: 'Best score:',
        post: `, ${fmt1(top.std.mark)}, ${fmtCost(top.m.cost)}, ${fmtTime(top.m.latency)}`
      }
    ];
    const near = ok.filter((r) => r !== top && r.std.mark! >= top.std.mark! - 1);
    const cheap = near
      .filter((r) => r.m.cost > 0 && r.m.cost < top.m.cost)
      .sort((a, b) => a.m.cost - b.m.cost)[0];
    if (cheap)
      list.push({
        r: cheap,
        pre: 'Within a point of the best:',
        post: `, ${fmt1(cheap.std.mark)} for ${fmtCost(cheap.m.cost)}, ${times(top.m.cost, cheap.m.cost)} cheaper${
          cheap.m.latency < top.m.latency
            ? ` and ${times(top.m.latency, cheap.m.latency)} faster`
            : ''
        }`
      });
    for (const f of FAMILIES.filter((f) => f !== 'OpenRouter')) {
      const best = ranking.order.find((r) => r.std.mark != null && family(r.m) === f);
      if (best && best !== top)
        list.push({
          r: best,
          pre: `Best ${f === 'Open weight' ? 'open weight model' : `from ${f}`}:`,
          post: `, ${fmt1(best.std.mark)}, ${fmtCost(best.m.cost)}`
        });
    }
    const byLabel = new Map(ok.map((r) => [r.m.label, r]));
    const pairs = ok.flatMap((h) => {
      const l = byLabel.get(h.m.label.replace(/ \(high\)$/, ' (low)'));
      return l && l !== h && h.m.cost > 0 && l.m.cost > 0 ? [[h, l]] : [];
    });
    if (pairs.length) {
      const gains = pairs.filter(([h, l]) => h.std.mark! > l.std.mark!).length;
      list.push({
        r: null,
        pre: `High thinking beats low in ${gains} of ${pairs.length} models, at a median ${fmt1(
          median(pairs.map(([h, l]) => h.m.cost / l.m.cost))
        )}× the cost`,
        post: ''
      });
    }
    const film = [...ok]
      .filter((r) => r.std.micro != null)
      .sort((a, b) => b.std.micro! - a.std.micro!)[0];
    if (film) list.push({ r: film, pre: 'Best on microfilm:', post: `, ${fmt0(film.std.micro)}` });
    return list;
  });

  const notPlotted = $derived(
    rows.flatMap((r) =>
      r.std.mark == null
        ? [`${r.m.label} (no folios run)`]
        : r.m.cost > 0
          ? []
          : [`${r.m.label} (no cost recorded; time graph only)`]
    )
  );
</script>

<svelte:head><title>Graphs, Paleo Bench</title></svelte:head>

<svelte:window onhashchange={fromHash} />

{#snippet pick(r: Row)}<button
    type="button"
    class="answer"
    onclick={() => choose(r.i)}
    onpointerenter={() => (hov = r.i)}
    onpointerleave={() => (hov = null)}>{r.m.label}</button
  >{/snippet}

<section class="lead">
  <h1>Graphs</h1>
  <ul class="points">
    <li>One dot per model, coloured by provider; open weight models share a colour</li>
    <li>Higher: better score; further left: cheaper or faster</li>
    <li>Select a dot to see that model below</li>
  </ul>
</section>

<div class="controls">
  <div class="chips" role="group" aria-label="Highlight a provider">
    <button type="button" class="btn" aria-pressed={fam === 'all'} onclick={() => (fam = 'all')}
      >All</button
    >
    {#each FAMILIES as f (f)}
      <button
        type="button"
        class="btn"
        aria-pressed={fam === f}
        onclick={() => (fam = fam === f ? 'all' : f)}
        ><span class="sw" style:background={familyColor(f)}></span>{f}</button
      >
    {/each}
  </div>
  <label class="check"><input type="checkbox" bind:checked={line} /> Show best-value line</label>
</div>

<section class="sheet panel" aria-labelledby="h-cost">
  <h2 class="sh" id="h-cost">Score against cost</h2>
  <Scatter {rows} kind="cost" {total} {fam} {line} pin={pinned.i} bind:hov onpick={choose} />
</section>
<section class="sheet panel" aria-labelledby="h-time">
  <h2 class="sh" id="h-time">Score against time</h2>
  <Scatter {rows} kind="time" {total} {fam} {line} pin={pinned.i} bind:hov onpick={choose} />
</section>

<ul class="legend">
  <li>
    <svg width="14" height="14" aria-hidden="true"
      ><circle class="hollow" cx="7" cy="7" r="4.4"></circle></svg
    >
    Failed at least one folio
  </li>
  {#if line}
    <li>
      <svg width="22" height="14" aria-hidden="true"><path class="step" d="M1,11 H9 V4 H21" /></svg>
      Best value: no cheaper or faster model scores higher
    </li>
  {/if}
</ul>
{#if notPlotted.length}
  <p class="note">Not plotted: {notPlotted.join('; ')}</p>
{/if}

<div class="below">
  <section class="sheet detail" aria-live="polite">
    <h2 class="sh">{pinned.m.label}</h2>
    <p class="note">
      {who(pinned.m)}{pinned.m.openWeights ? ', open weight' : ''}, position {ranking.label(
        pinned.i
      )}
    </p>
    <dl>
      <dt>Mean score</dt>
      <dd>{fmt1(pinned.std.mark)}</dd>
      <dt>Colour images</dt>
      <dd>{fmt0(pinned.std.colour)}</dd>
      <dt>Microfilm</dt>
      <dd>{fmt0(pinned.std.micro)}</dd>
      <dt>Folios run</dt>
      <dd>{pinned.sat} of {total}{pinned.absent ? `, ${pinned.absent} failed` : ''}</dd>
      <dt>Cost</dt>
      <dd>
        {pinned.m.cost > 0
          ? `${fmtCost(pinned.m.cost)} in total, ${fmtCost(pinned.m.cost / (pinned.attempted || 1))} a folio`
          : 'No cost recorded'}
      </dd>
      <dt>Time</dt>
      <dd>
        {fmtTime(pinned.m.latency, true)} in total, {fmtTime(
          pinned.m.latency / (pinned.attempted || 1),
          true
        )} a folio
      </dd>
    </dl>

    <a class="btn" href={resolve('transcriptions') + scriptHash(pinned, 0)}
      >Open image & transcription</a
    >
  </section>
  <section class="sheet answers" aria-labelledby="h-ans">
    <h2 class="sh" id="h-ans">Quick answers</h2>
    <ul>
      {#each answers as a, k (k)}
        <li>
          {a.pre}{#if a.r}{' '}{@render pick(a.r)}{/if}{a.post}
        </li>
      {/each}
    </ul>
  </section>
</div>

<style>
  .controls {
    justify-content: space-between;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }

  .sw {
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 50%;
  }

  .panel {
    padding: 14px 16px 8px;
    margin-bottom: 18px;
  }

  .below {
    display: grid;
    gap: 18px;
    margin-top: 18px;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 20px;
    margin: -6px 0 0;
    padding: 0;
    list-style: none;
    color: var(--pencil);
    font-size: 0.88rem;
  }

  .legend li {
    display: inline-flex;
    align-items: center;
    gap: 7px;
  }

  .legend .hollow {
    fill: var(--paper);
    stroke: var(--pencil);
    stroke-width: 1.8;
  }

  .legend .step {
    fill: none;
    stroke: var(--ink);
    stroke-width: 1.5;
  }

  .detail,
  .answers {
    padding: 16px 18px;
  }

  dl {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 6px 20px;
    margin: 12px 0 14px;
    font-variant-numeric: tabular-nums;
  }

  dt {
    color: var(--pencil);
  }

  dd {
    margin: 0;
  }

  .answers ul {
    list-style: none;
    margin: 10px 0 0;
    padding: 0;
  }

  .answers li {
    padding: 0.55rem 0;
    border-bottom: 1px solid var(--rule);
  }

  .answers li:last-child {
    border-bottom: 0;
  }

  .answer {
    background: none;
    border: 0;
    padding: 0;
    font-weight: 500;
    text-decoration: underline;
    text-underline-offset: 3px;
    cursor: pointer;
  }

  @media (min-width: 1000px) {
    .below {
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    }
  }
</style>
