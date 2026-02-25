<script lang="ts">
  import { pct, cost, duration, formatDate, comma, normalizeInverted } from '$lib/utils';
  import CircularGauge from '$lib/components/CircularGauge.svelte';
  import ThemeToggle from '$lib/components/ThemeToggle.svelte';
  import { page } from '$app/state';
  import type { ModelSummary, SiteSummaryData } from '$lib/types';
  import type { PageData } from './$types';
  import TextAa from 'phosphor-svelte/lib/TextAa';
  import CurrencyDollar from 'phosphor-svelte/lib/CurrencyDollar';
  import Clock from 'phosphor-svelte/lib/Clock';
  import type { Component } from 'svelte';

  type ChartSortKey = 'quality' | 'cost' | 'latency';

  type ModelRow = {
    label: string;
    summary: ModelSummary | null;
    quality: number;
    costPerSample: number;
    latencyPerSample: number;
    tokensPerSample: number;
  };

  type GaugeMetric = {
    key: string;
    label: string;
    icon: Component;
    color: string;
    gaugeValue: (row: ModelRow) => number;
    rawValue: (row: ModelRow) => string;
  };

  const { data: pageData }: { data: PageData } = $props();
  // svelte-ignore state_referenced_locally
  const siteSummary: SiteSummaryData = pageData.siteSummary;
  const pageTitle = 'Paleo Bench | HTR Model Leaderboard';
  const pageDescription =
    'Compare handwritten Greek text recognition performance across LLM vision models with ranking, CER/WER quality, latency, and cost metrics.';
  const socialImage = `${page.url.origin}/paleo-bench.png`;
  const configuredModels = siteSummary.benchmark.config.models.map((m) => m.label);

  const modelRows: ModelRow[] = configuredModels.map((label) => {
    const summary = siteSummary.model_summaries[label] ?? null;
    if (!summary || summary.samples_evaluated === 0) {
      return {
        label,
        summary,
        quality: 0,
        costPerSample: 0,
        latencyPerSample: 0,
        tokensPerSample: 0
      };
    }

    const quality = Math.max(0, 1 - summary.cer_mean);
    const costPerSample = summary.total_cost / summary.samples_evaluated;
    const latencyPerSample = summary.total_latency_seconds / summary.samples_evaluated;
    const tokensPerSample = summary.total_tokens / summary.samples_evaluated;

    return {
      label,
      summary,
      quality,
      costPerSample,
      latencyPerSample,
      tokensPerSample
    };
  });

  const rowsWithSummary = modelRows.filter((row) => row.summary);

  let hoveredModel = $state<string | null>(null);
  let selectedModel = $state<string | null>(null);
  let chartSortKey = $state<ChartSortKey>('quality');

  // Lollipop chart config
  const chartRowHeight = 38;
  const chartMargin = { top: 28, right: 110, bottom: 38, left: 210 };
  const chartMinWidth = 860;
  let chartViewportWidth = $state(0);
  let chartWidth = $derived(Math.max(chartViewportWidth, chartMinWidth));
  let chartNeedsHorizontalScroll = $derived(chartViewportWidth + 2 < chartMinWidth);

  let chartSorted = $derived.by(() => {
    const rows = [...rowsWithSummary];
    rows.sort((a, b) => {
      if (chartSortKey === 'quality') return b.quality - a.quality;
      if (chartSortKey === 'cost') return a.costPerSample - b.costPerSample;
      return a.latencyPerSample - b.latencyPerSample;
    });
    return rows;
  });
  const chartHeight =
    rowsWithSummary.length * chartRowHeight + chartMargin.top + chartMargin.bottom;
  let chartInnerWidth = $derived(chartWidth - chartMargin.left - chartMargin.right);

  let costMin = $derived(Math.min(...chartSorted.map((r) => r.costPerSample), 0));
  let costMax = $derived(Math.max(...chartSorted.map((r) => r.costPerSample), 0));
  let latencyMin = $derived(Math.min(...chartSorted.map((r) => r.latencyPerSample), 0));
  let latencyMax = $derived(Math.max(...chartSorted.map((r) => r.latencyPerSample), 0));
  let maxQuality = $derived(Math.max(...chartSorted.map((r) => r.quality), 0.01));
  let minQuality = $derived(Math.min(...chartSorted.map((r) => r.quality), 0));
  let qualityFloor = $derived(Math.max(0, Math.floor(minQuality * 20) / 20 - 0.05));

  function lollipopValue(row: ModelRow): number {
    if (chartSortKey === 'quality') return row.quality;
    if (chartSortKey === 'cost') return normalizeInverted(row.costPerSample, costMin, costMax);
    return normalizeInverted(row.latencyPerSample, latencyMin, latencyMax);
  }

  function barWidth(row: ModelRow): number {
    if (chartSortKey === 'quality') {
      return ((row.quality - qualityFloor) / (maxQuality - qualityFloor)) * chartInnerWidth;
    }
    return lollipopValue(row) * chartInnerWidth;
  }

  function lollipopRawLabel(row: ModelRow): string {
    if (chartSortKey === 'quality') return pct(row.quality);
    if (chartSortKey === 'cost') return cost(row.costPerSample);
    return duration(row.latencyPerSample);
  }

  let xAxisLabel = $derived(
    chartSortKey === 'quality'
      ? 'Quality (1 \u2212 CER)'
      : chartSortKey === 'cost'
        ? 'Cost efficiency (lower cost \u2192 longer bar)'
        : 'Speed (lower latency \u2192 longer bar)'
  );

  // The two gauge metrics NOT selected by the radio button
  const allMetrics: Record<ChartSortKey, GaugeMetric> = {
    quality: {
      key: 'quality',
      label: 'Quality',
      icon: TextAa,
      color: 'var(--accent-primary)',
      gaugeValue: (row: ModelRow) => row.quality,
      rawValue: (row: ModelRow) => pct(row.quality)
    },
    cost: {
      key: 'cost',
      label: 'Cost',
      icon: CurrencyDollar,
      color: 'var(--accent-secondary)',
      gaugeValue: (row: ModelRow) => {
        if (costMax === costMin) return 0.5;
        return Math.min(Math.max((row.costPerSample - costMin) / (costMax - costMin), 0), 1);
      },
      rawValue: (row: ModelRow) => cost(row.costPerSample)
    },
    latency: {
      key: 'latency',
      label: 'Latency',
      icon: Clock,
      color: 'var(--accent-tertiary)',
      gaugeValue: (row: ModelRow) => {
        if (latencyMax === latencyMin) return 0.5;
        return Math.min(
          Math.max((row.latencyPerSample - latencyMin) / (latencyMax - latencyMin), 0),
          1
        );
      },
      rawValue: (row: ModelRow) => duration(row.latencyPerSample)
    }
  };

  let gaugeMetrics = $derived.by(() => {
    const keys: ChartSortKey[] = ['quality', 'cost', 'latency'];
    return keys.filter((k) => k !== chartSortKey).map((k) => allMetrics[k]);
  });

  let activeMetric = $derived(allMetrics[chartSortKey]);

  function rowY(index: number): number {
    return chartMargin.top + index * chartRowHeight + chartRowHeight / 2;
  }

  function toggleSelectedModel(label: string) {
    selectedModel = selectedModel === label ? null : label;
  }

  function onChartRowKeydown(event: KeyboardEvent, label: string) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggleSelectedModel(label);
    }
  }

  let activeDetail = $derived.by(() => {
    const model = selectedModel
      ? modelRows.find((r) => r.label === selectedModel)
      : rowsWithSummary[0];
    if (!model) return undefined;
    const idx = chartSorted.findIndex((r) => r.label === model.label);
    return { model, index: idx };
  });

  const totalCost = rowsWithSummary.reduce((s, r) => s + (r.summary?.total_cost ?? 0), 0);
  const totalSamples = rowsWithSummary.reduce((s, r) => s + (r.summary?.samples_evaluated ?? 0), 0);
</script>

<svelte:head>
  <title>{pageTitle}</title>
  <meta name="description" content={pageDescription} />

  <meta property="og:title" content={pageTitle} />
  <meta property="og:description" content={pageDescription} />
  <meta property="og:type" content="website" />
  <meta property="og:image" content={socialImage} />

  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={pageTitle} />
  <meta name="twitter:description" content={pageDescription} />
  <meta name="twitter:image" content={socialImage} />
</svelte:head>

<div
  class="min-h-screen text-stone-900 dark:text-white"
  style="background: var(--bg-page); font-family: 'Outfit', sans-serif;"
>
  <main class="mx-auto max-w-[1400px] px-6 py-8 md:px-10 md:py-10">
    <header class="mb-10">
      <div class="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p
            class="text-[11px] font-semibold tracking-[0.3em] uppercase"
            style="color: var(--accent-primary);"
          >
            Paleo Bench
          </p>
          <h1
            class="mt-2 text-4xl leading-tight font-semibold text-stone-800 md:text-5xl dark:text-white/90"
            style="font-family: 'Fraunces', serif;"
          >
            HTR Model Leaderboard
          </h1>
          <p class="mt-3 max-w-2xl text-sm text-stone-700 md:text-base dark:text-white/50">
            Greek minuscule handwritten text recognition benchmarks across {comma(
              configuredModels.length
            )}
            model configurations. Models ranked by transcription accuracy, cost, and latency.
          </p>
        </div>
        <div class="flex flex-col items-start gap-3 md:items-end">
          <ThemeToggle />
          <span class="font-mono text-xs text-stone-600 dark:text-white/70"
            >{formatDate(siteSummary.benchmark.timestamp)}</span
          >
          <a
            href={`${page.url.origin}/compare`}
            class="group flex items-center gap-2 rounded-full border border-[var(--accent-primary)] px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md hover:brightness-95"
            style="background: var(--accent-primary); box-shadow: 0 10px 28px -20px var(--accent-primary);"
          >
            Open comparison viewer
            <span class="inline-block transition-transform group-hover:translate-x-0.5">&rarr;</span
            >
          </a>
        </div>
      </div>
    </header>

    <!-- Run stats -->
    <div class="mb-8 grid grid-cols-2 gap-3 md:grid-cols-3">
      {#each [{ label: 'Models', value: comma(configuredModels.length), color: 'var(--accent-primary)' }, { label: 'Samples', value: comma(totalSamples / configuredModels.length), color: 'var(--accent-tertiary)' }, { label: 'Total Cost', value: cost(totalCost), color: 'var(--accent-secondary)' }] as stat}
        <div class="rounded-xl border border-[var(--border-card)] bg-[var(--bg-surface)] p-4">
          <p
            class="mb-1 font-mono text-[10px] tracking-wider uppercase"
            style="color: {stat.color};"
          >
            {stat.label}
          </p>
          <p class="font-mono text-xl font-medium text-stone-800 dark:text-white/90">
            {stat.value}
          </p>
        </div>
      {/each}
    </div>

    <!-- Chart + detail panel -->
    <section class="mb-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_18.5rem]">
      <div
        class="min-w-0 rounded-2xl border border-[var(--border-card)] bg-[var(--bg-surface)] p-5 md:p-6"
      >
        <div
          class="mb-4 flex flex-col items-start justify-between gap-3 md:flex-row md:items-center"
        >
          <h2 class="text-lg font-semibold text-stone-800 md:text-xl dark:text-white/90">
            Model Ranking
          </h2>
          <div class="flex flex-wrap items-center gap-2.5">
            <div
              class="inline-flex rounded-full border border-[var(--border-card)] bg-[var(--bg-surface)] p-1"
              role="radiogroup"
              aria-label="Select primary metric"
            >
              {#each [{ key: 'quality', label: 'Quality' }, { key: 'cost', label: 'Cost' }, { key: 'latency', label: 'Latency' }] as option}
                <button
                  type="button"
                  role="radio"
                  aria-checked={chartSortKey === option.key}
                  onclick={() => (chartSortKey = option.key as ChartSortKey)}
                  class="cursor-pointer rounded-full px-3 py-1 font-mono text-[10px] tracking-wide uppercase transition-colors"
                  class:bg-stone-800={chartSortKey === option.key}
                  class:text-white={chartSortKey === option.key}
                  class:dark:bg-white={chartSortKey === option.key}
                  class:dark:text-stone-900={chartSortKey === option.key}
                  class:text-stone-800={chartSortKey !== option.key}
                  class:dark:text-white={chartSortKey !== option.key}
                >
                  {option.label}
                </button>
              {/each}
            </div>
            <p class="text-[10px] text-stone-600 dark:text-white/70">Click a row to inspect</p>
          </div>
        </div>

        <!-- Mobile view -->
        <div class="space-y-2 md:hidden">
          {#each chartSorted as row, i}
            {@const isExpanded = selectedModel === row.label}
            <div
              class="overflow-hidden rounded-lg border border-[var(--border-card)]"
              style:background={isExpanded
                ? 'color-mix(in srgb, var(--accent-primary) 8%, var(--bg-surface))'
                : 'var(--bg-surface)'}
            >
              <button
                type="button"
                onclick={() => toggleSelectedModel(row.label)}
                class="w-full p-3 text-left"
              >
                <div class="flex items-center justify-between gap-3">
                  <div class="flex min-w-0 items-center gap-2.5">
                    <span
                      class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold"
                      style="background: color-mix(in srgb, var(--accent-primary) 20%, transparent); color: var(--accent-primary);"
                      >{i + 1}</span
                    >
                    <div class="min-w-0">
                      <p class="truncate text-sm font-medium text-stone-700 dark:text-white/85">
                        {row.label}
                      </p>
                    </div>
                  </div>
                  <div class="flex shrink-0 items-center gap-1.5">
                    {#each [allMetrics.quality, allMetrics.cost, allMetrics.latency] as m}
                      <CircularGauge
                        value={m.gaugeValue(row)}
                        label={m.label}
                        color={m.color}
                        size={28}
                        icon={m.icon}
                        rawValue={m.rawValue(row)}
                      />
                    {/each}
                  </div>
                </div>
              </button>

              {#if isExpanded && row.summary}
                <div class="space-y-3 border-t border-[var(--border-card)] px-3 pt-3 pb-3">
                  <div class="flex justify-center gap-4">
                    {#each [allMetrics.quality, allMetrics.cost, allMetrics.latency] as gm}
                      <div class="text-center">
                        <CircularGauge
                          value={gm.gaugeValue(row)}
                          label={gm.label}
                          color={gm.color}
                          icon={gm.icon}
                          rawValue={gm.rawValue(row)}
                        />
                        <p class="mt-1 font-mono text-[9px] text-stone-600 dark:text-white/70">
                          {gm.rawValue(row)}
                        </p>
                      </div>
                    {/each}
                  </div>

                  <div class="grid grid-cols-2 gap-2">
                    {#each [{ label: 'CER Mean', value: pct(row.summary.cer_mean), color: 'var(--accent-primary)' }, { label: 'WER Mean', value: pct(row.summary.wer_mean), color: 'var(--accent-secondary)' }, { label: 'Cost / sample', value: cost(row.costPerSample), color: 'var(--accent-secondary)' }, { label: 'Latency / sample', value: duration(row.latencyPerSample), color: 'var(--accent-primary)' }] as card}
                      <div
                        class="rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] p-2.5"
                      >
                        <p
                          class="mb-0.5 font-mono text-[9px] tracking-wider uppercase"
                          style="color: {card.color};"
                        >
                          {card.label}
                        </p>
                        <p class="font-mono text-sm font-medium text-stone-700 dark:text-white/85">
                          {card.value}
                        </p>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>

        <!-- Desktop chart -->
        <div
          class="hidden pb-1 md:block"
          class:overflow-x-auto={chartNeedsHorizontalScroll}
          class:overflow-x-hidden={!chartNeedsHorizontalScroll}
          bind:clientWidth={chartViewportWidth}
        >
          <svg
            width={chartWidth}
            height={chartHeight}
            viewBox={`0 0 ${chartWidth} ${chartHeight}`}
            style={`min-width: ${chartMinWidth}px;`}
            role="img"
            aria-label={`Horizontal lollipop chart of model performance sorted by ${chartSortKey}`}
          >
            <defs>
              {#each chartSorted as _, i}
                <linearGradient id="bar-grad-{i}" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stop-color="var(--svg-bar-start)" stop-opacity="1" />
                  <stop offset="100%" stop-color="var(--svg-text-ghost)" stop-opacity="0.35" />
                </linearGradient>
              {/each}
            </defs>

            <rect
              x="0"
              y="0"
              width={chartWidth}
              height={chartHeight}
              rx="14"
              fill="var(--svg-chart-bg)"
            />

            <!-- X-axis ticks -->
            {#each Array.from({ length: 6 }, (_, i) => i) as i}
              {@const tickFrac = i / 5}
              {@const tickVal =
                chartSortKey === 'quality'
                  ? qualityFloor + tickFrac * (maxQuality - qualityFloor)
                  : tickFrac}
              {@const x = chartMargin.left + tickFrac * chartInnerWidth}
              <line
                x1={x}
                x2={x}
                y1={chartMargin.top - 4}
                y2={chartMargin.top + chartSorted.length * chartRowHeight}
                stroke="var(--svg-grid)"
              />
              <text
                {x}
                y={chartHeight - chartMargin.bottom + 20}
                text-anchor="middle"
                font-size="12"
                font-family="Space Mono"
                fill="var(--svg-text-ghost)"
              >
                {chartSortKey === 'quality' ? pct(tickVal, 0) : pct(tickFrac, 0)}
              </text>
            {/each}

            <!-- Reference line at top model score -->
            <line
              x1={chartMargin.left + chartInnerWidth}
              x2={chartMargin.left + chartInnerWidth}
              y1={chartMargin.top - 4}
              y2={chartMargin.top + chartSorted.length * chartRowHeight}
              stroke="var(--svg-ref-line)"
              stroke-width="1"
              stroke-dasharray="4 4"
            />

            <!-- Rows -->
            {#each chartSorted as row, i}
              {@const y = rowY(i)}
              {@const bw = barWidth(row)}
              {@const isHovered = hoveredModel === row.label}
              {@const isSelected = selectedModel === row.label}
              {@const isDimmed =
                (hoveredModel && !isHovered) || (selectedModel && !isSelected && !hoveredModel)}
              <g
                role="button"
                tabindex="0"
                aria-label={`Toggle details for ${row.label}`}
                style="cursor: pointer;"
                onmouseenter={() => (hoveredModel = row.label)}
                onmouseleave={() => (hoveredModel = null)}
                onclick={() => toggleSelectedModel(row.label)}
                onkeydown={(event) => onChartRowKeydown(event, row.label)}
              >
                <!-- Invisible hit target covering full row -->
                <rect
                  x={0}
                  y={y - chartRowHeight / 2}
                  width={chartWidth}
                  height={chartRowHeight}
                  fill={isHovered || isSelected ? 'var(--svg-hit-hover)' : 'transparent'}
                  rx="4"
                />

                <!-- Rank badge -->
                <circle
                  cx={chartMargin.left + 20}
                  cy={y}
                  r={10}
                  fill={isDimmed
                    ? 'var(--svg-text-dim)'
                    : isHovered || isSelected
                      ? 'var(--accent-primary)'
                      : 'color-mix(in srgb, var(--accent-primary) 20%, transparent)'}
                  opacity={isDimmed ? 0.3 : 1}
                  style="transition: fill 0.2s ease;"
                />
                <text
                  x={chartMargin.left + 20}
                  y={y + 4}
                  text-anchor="middle"
                  font-size="9"
                  font-family="Space Mono"
                  font-weight="bold"
                  fill={isDimmed
                    ? 'var(--svg-text-dim)'
                    : isHovered || isSelected
                      ? 'white'
                      : 'var(--accent-primary)'}
                  opacity={isDimmed ? 0.3 : 1}
                  style="transition: fill 0.2s ease;"
                >
                  {i + 1}
                </text>

                <!-- Model label -->
                <text
                  x={chartMargin.left - 14}
                  y={y + 5}
                  text-anchor="end"
                  font-size="13"
                  font-family="Outfit"
                  fill={isDimmed
                    ? 'var(--svg-text-dim)'
                    : isHovered || isSelected
                      ? 'var(--svg-text)'
                      : 'var(--svg-text-muted)'}
                  style="transition: fill 0.2s ease;"
                >
                  {row.label.length > 22 ? row.label.slice(0, 20) + '\u2026' : row.label}
                </text>

                <!-- Bar -->
                <rect
                  x={chartMargin.left}
                  y={y - 3}
                  width={bw}
                  height={6}
                  rx="3"
                  fill="url(#bar-grad-{i})"
                  opacity={isDimmed ? 0.3 : 1}
                  style="transition: opacity 0.2s ease;"
                />

                <!-- Dot at end — uniform size/color -->
                <circle
                  cx={chartMargin.left + bw}
                  cy={y}
                  r={isDimmed ? 3.5 : 5}
                  fill="var(--svg-text-ghost)"
                  fill-opacity={isDimmed ? 0.3 : 0.9}
                  stroke={i === 0 ? 'var(--accent-primary)' : 'var(--svg-dot-stroke)'}
                  stroke-width={i === 0 ? 1.5 : 1}
                  style="transition: all 0.2s ease;"
                />

                <!-- Raw value label below dot -->
                <text
                  x={chartMargin.left + bw}
                  y={y + 16}
                  text-anchor="end"
                  font-size="11"
                  font-family="Space Mono"
                  fill={isDimmed ? 'var(--svg-text-dim)' : 'var(--svg-text-muted)'}
                  style="transition: fill 0.2s ease;"
                >
                  {lollipopRawLabel(row)}
                </text>

                <!-- Two gauge columns on far right -->
                {#each gaugeMetrics as gm, gi}
                  <foreignObject
                    x={chartWidth - chartMargin.right + gi * 52 + 4}
                    y={y - 15}
                    width="48"
                    height="34"
                  >
                    <div
                      style="display:flex;flex-direction:column;align-items:center;gap:0px;line-height:1;"
                    >
                      <CircularGauge
                        value={gm.gaugeValue(row)}
                        label={gm.label}
                        color={gm.color}
                        size={26}
                        icon={gm.icon}
                        rawValue={gm.rawValue(row)}
                      />
                      <span
                        style="font-family:'Space Mono',monospace;font-size:6px;color:var(--svg-text-ghost);white-space:nowrap;margin-top:-1px;"
                      >
                        {gm.rawValue(row)}
                      </span>
                    </div>
                  </foreignObject>
                {/each}
              </g>
            {/each}

            <!-- X-axis label -->
            <text
              x={chartMargin.left + chartInnerWidth / 2}
              y={chartHeight - 6}
              text-anchor="middle"
              font-size="12"
              font-family="Outfit"
              fill="var(--svg-text-ghost)"
            >
              {xAxisLabel}
            </text>
          </svg>
        </div>

        <!-- Chart legend -->
        <div
          class="mt-4 flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-[var(--border-card)] pt-4"
        >
          <div class="flex items-center gap-3">
            <div class="flex items-center gap-1.5">
              <span
                class="inline-block h-1.5 w-6 rounded-full"
                style="background: var(--svg-text-ghost);"
              ></span>
              <span
                class="font-mono text-[9px] tracking-wider text-stone-600 uppercase dark:text-white/70"
              >
                Bar = {activeMetric.label}
              </span>
            </div>
          </div>
          {#each gaugeMetrics as gm}
            <div class="flex items-center gap-1.5">
              <CircularGauge
                value={0.7}
                label={gm.label}
                color={gm.color}
                size={18}
                icon={gm.icon}
              />
              <span
                class="font-mono text-[9px] tracking-wider text-stone-600 uppercase dark:text-white/70"
              >
                {gm.label}
              </span>
            </div>
          {/each}
          <p class="text-[10px] text-stone-600 dark:text-white/70">
            {chartSortKey === 'quality'
              ? 'Sorted by quality (1 \u2212 CER) descending'
              : chartSortKey === 'cost'
                ? 'Sorted by cost per sample ascending'
                : 'Sorted by latency per sample ascending'}
          </p>
        </div>
      </div>

      <!-- Detail panel (desktop only — mobile uses expandable rows) -->
      <div
        class="hidden min-w-0 space-y-4 rounded-2xl border border-[var(--border-card)] bg-[var(--bg-surface)] p-5 md:p-6 xl:block"
      >
        {#if activeDetail?.model?.summary}
          <div class="flex items-center justify-between">
            <p
              class="font-mono text-[10px] tracking-wider text-stone-600 uppercase dark:text-white/70"
            >
              {selectedModel ? 'Selected Model' : 'Top Performer'}
            </p>
            {#if selectedModel}
              <button
                onclick={() => (selectedModel = null)}
                class="text-[10px] text-stone-600 transition-colors hover:text-stone-600 dark:text-white/70 dark:hover:text-white/60"
              >
                Clear
              </button>
            {/if}
          </div>

          <div
            class="rounded-xl border border-[var(--border-card)] p-4"
            style="background: color-mix(in srgb, var(--accent-primary) 6%, transparent);"
          >
            <div class="flex items-center gap-3">
              <span
                class="flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold"
                style="background: color-mix(in srgb, var(--accent-primary) 20%, transparent); color: var(--accent-primary);"
                >{activeDetail.index + 1}</span
              >
              <div>
                <h3 class="text-lg font-semibold text-stone-800 dark:text-white/90">
                  {activeDetail.model.label}
                </h3>
                <p class="text-xs text-stone-700 dark:text-white/70">
                  Quality: {pct(activeDetail.model.quality, 1)}
                </p>
              </div>
            </div>
          </div>

          <div class="flex justify-center gap-4">
            {#each [allMetrics.quality, allMetrics.cost, allMetrics.latency] as gm}
              <div class="text-center">
                <CircularGauge
                  value={gm.gaugeValue(activeDetail.model)}
                  label={gm.label}
                  color={gm.color}
                  icon={gm.icon}
                  rawValue={gm.rawValue(activeDetail.model)}
                />
                <p class="mt-1 font-mono text-[9px] text-stone-600 dark:text-white/70">
                  {gm.rawValue(activeDetail.model)}
                </p>
              </div>
            {/each}
          </div>

          <div class="grid grid-cols-2 gap-3">
            {#each [{ label: 'CER Mean', value: pct(activeDetail.model.summary.cer_mean), color: 'var(--accent-primary)' }, { label: 'WER Mean', value: pct(activeDetail.model.summary.wer_mean), color: 'var(--accent-secondary)' }, { label: 'Cost / sample', value: cost(activeDetail.model.costPerSample), color: 'var(--accent-secondary)' }, { label: 'Latency / sample', value: duration(activeDetail.model.latencyPerSample), color: 'var(--accent-primary)' }] as card}
              <div class="rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] p-3">
                <p
                  class="mb-0.5 font-mono text-[9px] tracking-wider uppercase"
                  style="color: {card.color};"
                >
                  {card.label}
                </p>
                <p class="font-mono text-sm font-medium text-stone-700 dark:text-white/85">
                  {card.value}
                </p>
              </div>
            {/each}
          </div>

          <div
            class="space-y-2 rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] p-3"
          >
            <p
              class="font-mono text-[9px] tracking-wider text-stone-600 uppercase dark:text-white/70"
            >
              Metric glossary
            </p>
            <dl class="space-y-1.5 text-[10px] leading-relaxed">
              <div class="flex gap-2">
                <dt class="shrink-0 font-mono font-medium" style="color: var(--accent-primary);">
                  CER
                </dt>
                <dd class="text-stone-700 dark:text-white/70">
                  Character Error Rate — fraction of characters the model got wrong vs. the ground
                  truth. Lower is better.
                </dd>
              </div>
              <div class="flex gap-2">
                <dt class="shrink-0 font-mono font-medium" style="color: var(--accent-secondary);">
                  WER
                </dt>
                <dd class="text-stone-700 dark:text-white/70">
                  Word Error Rate — fraction of words with at least one error. Lower is better.
                </dd>
              </div>
              <div class="flex gap-2">
                <dt class="shrink-0 font-mono font-medium" style="color: var(--accent-primary);">
                  Quality
                </dt>
                <dd class="text-stone-700 dark:text-white/70">
                  1 minus CER — how accurate the transcription is overall. Higher is better.
                </dd>
              </div>
            </dl>
          </div>
        {:else}
          <div
            class="flex h-full items-center justify-center text-sm text-stone-600 dark:text-white/70"
          >
            No model data available.
          </div>
        {/if}
      </div>
    </section>

    <footer
      class="mt-8 flex flex-col items-center gap-2 border-t border-[var(--border-card)] pt-6 text-center md:flex-row md:justify-between md:text-left"
    >
      <p class="font-mono text-[10px] text-stone-600 dark:text-white/70">
        {siteSummary.benchmark.name}
      </p>
      <a
        href="https://github.com/d-flood/paleo-bench"
        target="_blank"
        rel="noreferrer"
        class="font-mono text-[10px] transition-colors hover:opacity-80"
        style="color: var(--accent-primary);"
      >
        View on GitHub
      </a>
      <p class="max-w-full font-mono text-[10px] text-balance text-stone-600 dark:text-white/70">
        {siteSummary.benchmark.config.groups.map((g) => g.name).join(' · ')}
      </p>
    </footer>
  </main>
</div>
