<script lang="ts">
  import { family, familyColor, fmt1, fmtCost, fmtTime, who, type Row } from '#lib/bench.js';

  interface Props {
    rows: Row[];
    kind: 'cost' | 'time';
    total: number;
    fam: string;
    line: boolean;
    pin: number | null;
    hov: number | null;
    onpick: (i: number) => void;
  }

  let { rows, kind, total, fam, line, pin, hov = $bindable(), onpick }: Props = $props();

  let width = $state(600);
  const W = $derived(Math.max(300, Math.round(width)));
  const H = $derived(Math.round(Math.min(520, Math.max(300, W * 0.45))));
  const M = { l: 44, r: 18, t: 30, b: 52 };
  const PW = $derived(W - M.l - M.r);
  const PH = $derived(H - M.t - M.b);
  const AXES = {
    cost: {
      ticks: [
        [0.001, '$0.001'],
        [0.01, '$0.01'],
        [0.1, '$0.10'],
        [1, '$1.00'],
        [10, '$10']
      ],
      title: 'Total cost, log scale',
      low: '← cheaper',
      high: 'pricier →',
      get: (r: Row) => (r.m.cost > 0 ? r.m.cost : null)
    },
    time: {
      ticks: [
        [10, '10 s'],
        [60, '1 min'],
        [180, '3 min'],
        [600, '10 min'],
        [1800, '30 min'],
        [3600, '1 h'],
        [7200, '2 h']
      ],
      title: 'Total time, log scale',
      low: '← faster',
      high: 'slower →',
      get: (r: Row) => (r.m.latency > 0 ? r.m.latency : null)
    }
  } as const;

  const ax = $derived(AXES[kind]);
  const range = $derived.by(() => {
    const vals = rows.flatMap((r) => (r.std.mark == null ? [] : (ax.get(r) ?? [])));
    return { lo: Math.min(...vals) / 1.5, hi: Math.max(...vals) * 1.5 };
  });
  const ticks = $derived(ax.ticks.filter(([v]) => v >= range.lo && v <= range.hi));
  const Y = $derived((v: number) => M.t + ((100 - v) / 100) * PH);
  const X = $derived(
    (v: number) =>
      M.l +
      ((Math.log10(v) - Math.log10(range.lo)) / (Math.log10(range.hi) - Math.log10(range.lo))) * PW
  );

  interface Point {
    r: Row;
    x: number;
    y: number;
    front: boolean;
  }

  const dim = (r: Row) => fam !== 'all' && family(r.m) !== fam;

  const pts = $derived.by(() => {
    const list: Point[] = rows
      .filter((r) => r.std.mark != null && ax.get(r) != null)
      .map((r) => ({ r, x: X(ax.get(r)!), y: Y(r.std.mark!), front: false }))
      .sort((a, b) => ax.get(a.r)! - ax.get(b.r)! || b.r.std.mark! - a.r.std.mark!);
    let best = -1;
    for (const p of list) {
      p.front = p.r.std.mark! > best;
      if (p.front) best = p.r.std.mark!;
    }
    return list;
  });
  const front = $derived(pts.filter((p) => p.front));
  const at = $derived(new Map(pts.map((p) => [p.r.i, p])));
  const drawn = $derived(
    [...pts].sort(
      (a, b) =>
        Number(!dim(a.r)) - Number(!dim(b.r)) || Number(line && a.front) - Number(line && b.front)
    )
  );
  const step = $derived.by(() => {
    if (!front.length) return '';
    let d = `M${front[0].x},${front[0].y}`;
    for (const p of front.slice(1)) d += ` H${p.x} V${p.y}`;
    return d + ` H${W - M.r}`;
  });

  interface Box {
    x: number;
    y: number;
    w: number;
    h: number;
  }

  const shortName = (l: string) =>
    l.replace(' 1017', '').replace('Nemotron 3.5 Super VL', 'Nemotron 3.5');

  const labels = $derived.by(() => {
    const placed: Box[] = [{ x: M.l - 8, y: M.t - 26, w: 150, h: 16 }];
    if (line)
      front.forEach((a, k) => {
        const nx = k + 1 < front.length ? front[k + 1].x : W - M.r;
        placed.push({ x: a.x, y: a.y - 2, w: nx - a.x, h: 4 });
        if (k + 1 < front.length) {
          const b = front[k + 1];
          placed.push({ x: b.x - 2, y: b.y, w: 4, h: a.y - b.y });
        }
      });
    const dots = pts.map((p) => ({ p, x: p.x - 5, y: p.y - 5, w: 10, h: 10 }));
    const hit = (a: Box, b: Box) =>
      a.x < b.x + b.w + 2 && a.x + a.w + 2 > b.x && a.y < b.y + b.h + 1 && a.y + a.h + 1 > b.y;
    const inside = (b: Box) =>
      b.x >= 2 && b.x + b.w <= W - 2 && b.y >= M.t - 6 && b.y + b.h <= M.t + PH + 2;
    const tries: [number, number, 'start' | 'end' | 'middle'][] = [
      [8, 4, 'start'],
      [-8, 4, 'end'],
      [7, -9, 'start'],
      [-7, -9, 'end'],
      [7, 17, 'start'],
      [-7, 17, 'end'],
      [0, -12, 'middle'],
      [0, 21, 'middle'],
      [7, -21, 'start'],
      [-7, -21, 'end'],
      [7, 29, 'start'],
      [-7, 29, 'end']
    ];
    const pinned = pin == null ? null : at.get(pin);
    const wanted = [...front].sort((a, b) => b.r.std.mark! - a.r.std.mark!);
    if (pinned && !pinned.front) wanted.unshift(pinned);
    const out: { i: number; text: string; x: number; y: number; anchor: string }[] = [];
    for (const p of wanted) {
      const text = shortName(p.r.m.label);
      const w = text.length * 5.9 + 2;
      const box = (dx: number, dy: number, a: string): Box => {
        const x = p.x + dx;
        return {
          x: a === 'start' ? x : a === 'end' ? x - w : x - w / 2,
          y: p.y + dy - 11,
          w,
          h: 14
        };
      };
      let chosen: [number, number, string] | null = null;
      for (const strict of [true, false]) {
        for (const [dx, dy, a] of tries) {
          const b = box(dx, dy, a);
          if (!inside(b) || placed.some((q) => hit(b, q))) continue;
          if (strict && dots.some((q) => q.p !== p && hit(b, q))) continue;
          placed.push(b);
          chosen = [dx, dy, a];
          break;
        }
        if (chosen) break;
      }
      if (chosen)
        out.push({ i: p.r.i, text, x: p.x + chosen[0], y: p.y + chosen[1], anchor: chosen[2] });
    }
    return out;
  });

  const amount = (r: Row) => (kind === 'cost' ? fmtCost(r.m.cost) : fmtTime(r.m.latency, true));
  const tipPoint = $derived(hov == null ? null : (at.get(hov) ?? null));
</script>

<div class="chart" bind:clientWidth={width}>
  <svg
    width={W}
    height={H}
    viewBox="0 0 {W} {H}"
    role="group"
    aria-label="Mean score against {kind} for each model"
  >
    {#each [0, 25, 50, 75, 100] as v (v)}
      <line class="gr" x1={M.l} x2={W - M.r} y1={Y(v)} y2={Y(v)} />
      <text class="ax" x={M.l - 8} y={Y(v) + 4} text-anchor="end">{v}</text>
    {/each}
    {#each ticks as [v, t] (v)}
      <line class="gr" x1={X(v)} x2={X(v)} y1={M.t} y2={M.t + PH} />
      <text class="ax" x={X(v)} y={M.t + PH + 18} text-anchor="middle">{t}</text>
    {/each}
    <text class="ax" x={M.l - 8} y={M.t - 14}>Mean score, higher is better</text>
    <text class="ax hint" x={M.l} y={H - 8}>{ax.low}</text>
    <text class="ax" x={M.l + PW / 2} y={H - 8} text-anchor="middle">{ax.title}</text>
    <text class="ax hint" x={W - M.r} y={H - 8} text-anchor="end">{ax.high}</text>
    {#if line}
      <path class="step" d={step} />
    {/if}
    {#each drawn as p (p.r.i)}
      <circle
        class="dot"
        class:fr={line && p.front}
        class:hollow={p.r.absent > 0}
        class:dim={dim(p.r)}
        style:--c={familyColor(family(p.r.m))}
        cx={p.x}
        cy={p.y}
        r={(line && p.front ? 0.8 : 0) + (W > 700 ? 5 : 4.2)}
      />
    {/each}
    {#each labels as l (l.i)}
      <text class="lb" class:dim={dim(at.get(l.i)!.r)} x={l.x} y={l.y} text-anchor={l.anchor}
        >{l.text}</text
      >
    {/each}
    {#each [pin, hov !== pin ? hov : null] as i, k (k)}
      {@const p = i == null ? null : at.get(i)}
      {#if p}
        <circle class="ring" class:hov={k === 1} cx={p.x} cy={p.y} r="9" />
      {/if}
    {/each}
    {#each pts as p (p.r.i)}
      <circle
        class="hit"
        cx={p.x}
        cy={p.y}
        r="12"
        tabindex="0"
        role="button"
        aria-label="{p.r.m.label}, {family(p.r.m)}: mean score {fmt1(p.r.std.mark)}, {amount(
          p.r
        )} for all folios"
        onpointerenter={() => (hov = p.r.i)}
        onpointerleave={() => (hov = null)}
        onfocus={() => (hov = p.r.i)}
        onblur={() => (hov = null)}
        onclick={() => onpick(p.r.i)}
        onkeydown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onpick(p.r.i);
          }
        }}
      />
    {/each}
  </svg>
  {#if tipPoint}
    {@const r = tipPoint.r}
    <div
      class="tip"
      style:left="{Math.min(Math.max(tipPoint.x - 115, 0), W - 230)}px"
      style:top="{Math.max(0, tipPoint.y - 96)}px"
    >
      <b>{r.m.label}</b><br />
      {who(r.m)}{r.m.openWeights ? ', open weight' : ''}<br />
      Mean score {fmt1(r.std.mark)}, {r.sat} of {total} run<br />
      {r.m.cost > 0 ? fmtCost(r.m.cost) : 'No cost recorded'}, {fmtTime(r.m.latency, true)}
    </div>
  {/if}
</div>

<style>
  .chart {
    position: relative;
    margin-top: 8px;
  }

  svg {
    display: block;
    overflow: visible;
  }

  .gr {
    stroke: var(--rule);
    stroke-width: 1;
    fill: none;
  }

  .ax {
    fill: var(--pencil);
    font: 12px var(--f-ui);
  }

  .hint {
    fill: var(--faint);
  }

  .dot {
    fill: var(--c);
    stroke: var(--paper);
    stroke-width: 1.2;
  }

  .dot.hollow {
    fill: var(--paper);
    stroke: var(--c);
    stroke-width: 1.8;
  }

  .dot.fr {
    stroke: var(--ink);
    stroke-width: 1.6;
  }

  .step {
    fill: none;
    stroke: var(--ink);
    stroke-width: 1.5;
  }

  .lb {
    fill: var(--ink);
    font: 12px var(--f-ui);
    paint-order: stroke;
    stroke: var(--paper);
    stroke-width: 3px;
    stroke-linejoin: round;
  }

  .ring {
    fill: none;
    stroke: var(--ink);
    stroke-width: 1.8;
    pointer-events: none;
  }

  .ring.hov {
    stroke-dasharray: 2 2;
  }

  .hit {
    fill: var(--paper);
    fill-opacity: 0;
    cursor: pointer;
  }

  .hit:focus {
    outline: none;
  }

  .hit:focus-visible {
    stroke: var(--ink);
    stroke-width: 2;
  }

  .dim {
    opacity: 0.15;
  }

  .tip {
    width: 230px;
    white-space: normal;
  }
</style>
