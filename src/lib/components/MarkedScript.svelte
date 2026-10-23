<script lang="ts">
  import {
    align,
    charDiff,
    foreignChars,
    lineCosts,
    parseGroundTruth,
    type CharPart,
    type Unit
  } from '#lib/align.js';
  import { paperName, type Cell, type Folio, type Sample } from '#lib/bench.js';

  interface Props {
    label: string;
    sample: Sample;
    cell: Cell;
    folio: Folio | null;
  }

  let { label, sample, cell, folio }: Props = $props();

  type Piece = { kind: 'word'; w: string } | { kind: 'unit'; u: Unit };

  const marked = $derived.by(() => {
    if (!folio || cell.kind !== 'ok') return null;
    const gt = parseGroundTruth(folio.gt);
    const units = align(gt, folio.texts[label] ?? '');
    const costs = lineCosts(units);
    const pieces = new Map<number, Piece[]>();
    const push = (line: number, piece: Piece) => {
      if (!pieces.has(line)) pieces.set(line, []);
      pieces.get(line)!.push(piece);
    };
    const isText = (k: number) => gt.lines[gt.tokens[k].line].kind === 'text';
    let wrong = 0;
    let added = 0;
    for (const u of units) {
      if (u.type === 'eq') {
        for (let k = u.from; k < u.to; k++)
          push(gt.tokens[k].line, { kind: 'word', w: u.pred[k - u.from] });
        continue;
      }
      push(u.line, { kind: 'unit', u });
      for (let k = u.from; k < u.to; k++) if (isText(k)) wrong++;
      added += u.type === 'ins' ? u.pred.length : Math.max(0, u.pred.length - u.lemma.length);
    }
    const lines = gt.lines
      .filter((l) => l.kind !== 'blank')
      .map((l) => {
        const list = pieces.get(l.index) ?? [];
        const cost = costs.get(l.index) ?? 0;
        const margin = !list.length ? '' : cost ? `−${cost}` : l.kind === 'column' ? '' : '✓';
        return { line: l, pieces: list, cost, margin };
      });
    const words = gt.tokens.filter((_, k) => isText(k)).length;
    return { lines, wrong, added, words };
  });

  const lemmaText = (w: string[]) =>
    w.length > 14
      ? `${w.slice(0, 6).join(' ')} … ${w.slice(-3).join(' ')} (${w.length} words)`
      : w.join(' ');
  const long = (u: Unit) => u.lemma.length > 6 || u.pred.length > 12;
</script>

{#snippet word(w: string)}
  {@const flags = foreignChars(w)}
  {#if flags.some(Boolean)}
    {#each [...w] as ch, k (k)}{#if flags[k]}<span class="fx" title="Not a Greek letter">{ch}</span
        >{:else}{ch}{/if}{/each}
  {:else}{w}{/if}
{/snippet}

{#snippet reading(words: string[])}
  {#each words.length > 12 ? words.slice(0, 8) : words as w, k (k)}{#if k}{' '}{/if}{@render word(
      w
    )}{/each}{#if words.length > 12}{' '}<span class="more"
      >…and {words.length - 8} more words not on the page</span
    >{/if}
{/snippet}

{#snippet unit(u: Unit)}
  {#if u.type === 'ins'}
    <span class="add">{@render reading(u.pred)}</span>
  {:else if u.type === 'del' && u.lemma.length > 6}
    <span class="fix">‸ {lemmaText(u.lemma)}</span>
  {:else if u.type === 'del'}
    <span class="cw" style:min-width="{u.lemma.join(' ').length * 0.44}rem"
      ><span class="ann">{u.lemma.join(' ')}</span><span class="car">‸</span></span
    >
  {:else if long(u)}
    <s class="xs">{@render reading(u.pred)}</s> <span class="fix">{lemmaText(u.lemma)}</span>
  {:else}
    {@const diff = charDiff(u.pred.join(' '), u.lemma.join(' '))}
    {#if diff.similarity >= 0.5}
      {@render letters(diff.parts)}
    {:else}
      <span class="cw" style:min-width="{u.lemma.join(' ').length * 0.44}rem"
        ><span class="ann">{u.lemma.join(' ')}</span><s class="xs">{@render reading(u.pred)}</s
        ></span
      >
    {/if}
  {/if}
{/snippet}

{#snippet letters(parts: CharPart[])}
  {#each parts as part, k (k)}{#if part.type === 'eq'}{part.pred}{:else if part.type === 'sub'}<span
        class="cc"><span class="ann">{part.gt}</span><s class="xs">{part.pred}</s></span
      >{:else if part.type === 'extra' && part.pred.trim()}<s class="xs">{part.pred}</s
      >{:else if part.type === 'extra'}<span class="sp" title="Close up">‿</span
      >{:else if part.gt.trim()}<span class="cc"
        ><span class="ann">{part.gt}</span><span class="car">‸</span></span
      >{:else}<span class="sp" title="Space missing">|</span>{/if}{/each}
{/snippet}

<article class="sheet script" aria-live="polite">
  <div class="ruled">
    <div class="hl"><span>Model:</span> <span class="val">{label}</span></div>
    <div class="hl"><span>Folio:</span> <span class="val">{paperName(sample)}</span></div>
    {#if cell.kind === 'ok'}
      <div class="grade" aria-label="Score {cell.v} out of 100">{cell.v}</div>
      {#if marked}
        {#each marked.lines as l (l.line.index)}
          <div class="l" class:col={l.line.kind === 'column'}>
            <span class="mm" title={l.cost ? `${l.cost} characters wrong` : 'no errors'}
              >{l.margin}</span
            >{#each l.pieces as p, k (k)}{#if k}{' '}{/if}{#if p.kind === 'word'}{p.w}{:else}{@render unit(
                  p.u
                )}{/if}{:else}&nbsp;{/each}
          </div>
        {/each}
        <div class="sfoot">
          <p>
            {marked.wrong} of {marked.words} words wrong{marked.added
              ? `, ${marked.added} added`
              : ''}
          </p>
        </div>
      {:else}
        <p class="l col">Scoring the transcription…</p>
      {/if}
    {:else}
      <div class="grade ab" aria-label="Failed">failed</div>
      <div class="sfoot">
        {#if cell.kind === 'abs'}
          <p>Failed: {cell.why}</p>
        {:else}
          <p>Not run</p>
        {/if}
      </div>
    {/if}
  </div>
</article>

<style>
  .grade {
    position: absolute;
    top: 0.85rem;
    right: 1.3rem;
    width: 4.6rem;
    height: 4.6rem;
    display: grid;
    place-items: center;
    border: 2.5px solid var(--pen);
    border-radius: 50%;
    transform: rotate(-8deg);
    font-family: var(--f-script);
    font-size: 2rem;
    font-weight: 500;
    color: var(--pen);
    font-variant-numeric: lining-nums;
  }

  .grade.ab {
    font-style: italic;
    font-size: 1.15rem;
  }

  .cw {
    position: relative;
    display: inline-block;
  }

  .ann {
    position: absolute;
    left: 0;
    top: -0.12rem;
    white-space: nowrap;
    font: italic 500 0.8rem/1 var(--f-script);
    color: var(--pen);
  }

  .cc {
    position: relative;
  }

  .sp {
    color: var(--pen);
    font-weight: 700;
    padding: 0 0.05rem;
  }

  .xs {
    text-decoration: line-through;
    text-decoration-color: var(--pen);
    text-decoration-thickness: 1.5px;
  }

  .car {
    color: var(--pen);
    font-weight: 700;
    padding: 0 0.1rem;
  }

  .add {
    text-decoration: underline wavy var(--pen) 1px;
    text-underline-offset: 5px;
    text-decoration-skip-ink: none;
  }

  .fix,
  .more {
    display: inline-block;
    font-family: var(--f-script);
    font-style: italic;
    font-size: 0.85em;
    color: var(--pen);
    text-decoration: none;
  }

  .fx {
    text-decoration: underline dotted var(--pen) 2px;
    text-underline-offset: 3px;
  }

  @media (max-width: 760px) {
    .grade {
      width: 3.8rem;
      height: 3.8rem;
      font-size: 1.65rem;
      right: 0.8rem;
    }
  }
</style>
