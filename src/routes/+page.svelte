<script lang="ts">
	import { pct, cost, duration, formatDate, comma } from '$lib/utils';
	import CircularGauge from '$lib/components/CircularGauge.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';
	import { base } from '$app/paths';
	import type { BenchmarkData, ModelSummary } from '$lib/types';
	import type { PageData } from './$types';

	type SortKey =
		| 'rank'
		| 'quality'
		| 'similarity'
		| 'cer'
		| 'wer'
		| 'cost'
		| 'latency'
		| 'tokens';
	type ChartSortKey = 'quality' | 'cost' | 'latency';

	type ModelRow = {
		label: string;
		summary: ModelSummary | null;
		quality: number;
		similarity: number;
		costPerSample: number;
		latencyPerSample: number;
		tokensPerSample: number;
		rank: number;
	};

	const { data: pageData }: { data: PageData } = $props();
	// svelte-ignore state_referenced_locally
	const benchmarkData: BenchmarkData = pageData.benchmarkData;
	const pageTitle = 'Paleo Bench | HTR Model Leaderboard';
	const pageDescription =
		'Compare handwritten Greek text recognition performance across LLM vision models with ranking, CER/WER quality, latency, and cost metrics.';
	const socialImage = `${base}/paleo-bench.png`;
	const configuredModels = benchmarkData.benchmark.config.models.map((m) => m.label);

	const modelRows: ModelRow[] = configuredModels.map((label) => {
		const summary = benchmarkData.model_summaries[label] ?? null;
		if (!summary || summary.samples_evaluated === 0) {
			return {
				label,
				summary,
				quality: 0,
				similarity: 0,
				costPerSample: 0,
				latencyPerSample: 0,
				tokensPerSample: 0,
				rank: 999
			};
		}

		const quality = Math.max(0, 1 - summary.cer_mean);
		const similarity = Math.max(0, summary.normalized_levenshtein_similarity_mean);
		const costPerSample = summary.total_cost / summary.samples_evaluated;
		const latencyPerSample = summary.total_latency_seconds / summary.samples_evaluated;
		const tokensPerSample = summary.total_tokens / summary.samples_evaluated;

		return {
			label,
			summary,
			quality,
			similarity,
			costPerSample,
			latencyPerSample,
			tokensPerSample,
			rank: 0
		};
	});

	const rowsWithSummary = modelRows.filter((row) => row.summary);

	const rankedByQuality = [...modelRows].sort((a, b) => b.quality - a.quality);
	rankedByQuality.forEach((row, i) => (row.rank = row.summary ? i + 1 : 999));
	const topModel = rankedByQuality[0];

	let sortKey = $state<SortKey>('rank');
	let sortAsc = $state(true);
	let hoveredModel = $state<string | null>(null);
	let selectedModel = $state<string | null>(null);
	let searchQuery = $state('');
	let chartSortKey = $state<ChartSortKey>('quality');

	function toggleSort(key: SortKey) {
		if (sortKey === key) {
			sortAsc = !sortAsc;
		} else {
			sortKey = key;
			sortAsc = key === 'rank' || key === 'quality' || key === 'similarity';
		}
	}

	function getSortValue(row: ModelRow, key: SortKey): number {
		switch (key) {
			case 'rank':
				return row.rank;
			case 'quality':
				return row.quality;
			case 'similarity':
				return row.similarity;
			case 'cer':
				return row.summary?.cer_mean ?? 999;
			case 'wer':
				return row.summary?.wer_mean ?? 999;
			case 'cost':
				return row.costPerSample;
			case 'latency':
				return row.latencyPerSample;
			case 'tokens':
				return row.tokensPerSample;
		}
	}

	let sortedRows = $derived.by(() => {
		let rows = [...modelRows];
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			rows = rows.filter((r) => r.label.toLowerCase().includes(q));
		}
		rows.sort((a, b) => {
			const va = getSortValue(a, sortKey);
			const vb = getSortValue(b, sortKey);
			const ascending = sortKey === 'cer' || sortKey === 'wer' || sortKey === 'cost' || sortKey === 'latency' || sortKey === 'tokens';
			const dir = sortAsc ? 1 : -1;
			if (ascending) return (va - vb) * dir;
			return (vb - va) * dir;
		});
		return rows;
	});

	// Lollipop chart config
	const chartRowHeight = 38;
	const chartMargin = { top: 28, right: 150, bottom: 38, left: 210 };
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
	const chartHeight = rowsWithSummary.length * chartRowHeight + chartMargin.top + chartMargin.bottom;
	let chartInnerWidth = $derived(chartWidth - chartMargin.left - chartMargin.right);

	let maxQuality = $derived(Math.max(...chartSorted.map((r) => r.quality), 0.01));
	let minQuality = $derived(Math.min(...chartSorted.map((r) => r.quality), 0));
	let qualityFloor = $derived(Math.max(0, Math.floor(minQuality * 20) / 20 - 0.05));

	function barWidth(row: ModelRow): number {
		return ((row.quality - qualityFloor) / (maxQuality - qualityFloor)) * chartInnerWidth;
	}

	function latencyColor(row: ModelRow): string {
		const latencies = chartSorted.map((r) => r.latencyPerSample).sort((a, b) => a - b);
		const t1 = latencies[Math.floor(latencies.length / 3)] ?? 0;
		const t2 = latencies[Math.floor((latencies.length * 2) / 3)] ?? 0;
		if (row.latencyPerSample <= t1) return 'var(--accent-tertiary)';
		if (row.latencyPerSample <= t2) return 'var(--accent-secondary)';
		return '#b6493f';
	}

	const minDotR = 4;
	const maxDotR = 10;
	let costMin = $derived(Math.min(...chartSorted.map((r) => r.costPerSample), 0));
	let costMax = $derived(Math.max(...chartSorted.map((r) => r.costPerSample), 0));

	function costRadius(row: ModelRow): number {
		if (costMax === costMin) return (minDotR + maxDotR) / 2;
		const t = (row.costPerSample - costMin) / (costMax - costMin);
		return minDotR + t * (maxDotR - minDotR);
	}

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


	function sortArrow(key: SortKey): string {
		if (sortKey !== key) return '';
		return sortAsc ? ' \u2191' : ' \u2193';
	}

	let activeDetail = $derived(
		selectedModel ? modelRows.find((r) => r.label === selectedModel) : topModel
	);

	const totalCost = rowsWithSummary.reduce((s, r) => s + (r.summary?.total_cost ?? 0), 0);
	const totalSamples = rowsWithSummary.reduce(
		(s, r) => s + (r.summary?.samples_evaluated ?? 0),
		0
	);
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
						class="mt-2 text-4xl leading-tight font-semibold text-stone-800 dark:text-white/90 md:text-5xl"
						style="font-family: 'Fraunces', serif;"
					>
						HTR Model Leaderboard
					</h1>
					<p class="mt-3 max-w-2xl text-sm text-stone-700 dark:text-white/50 md:text-base">
						Greek minuscule handwritten text recognition benchmarks across {comma(configuredModels.length)}
						model configurations. Models ranked by transcription accuracy, with latency indicated by color and cost by dot size.
					</p>
				</div>
				<div class="flex flex-col items-start gap-3 md:items-end">
					<ThemeToggle />
					<span class="font-mono text-xs text-stone-600 dark:text-white/70"
						>{formatDate(benchmarkData.benchmark.timestamp)}</span
					>
					<a
						href={`${base}/compare`}
						class="group flex items-center gap-2 rounded-full border border-[var(--border-card)] px-5 py-2.5 text-sm font-medium text-stone-600 transition-all hover:border-[var(--accent-primary)] hover:text-stone-900 dark:text-white/80 dark:hover:text-white"
					>
						Open comparison viewer
						<span
							class="inline-block transition-transform group-hover:translate-x-0.5"
							>&rarr;</span
						>
					</a>
				</div>
			</div>
		</header>

		<!-- Run stats -->
		<div class="mb-8 grid grid-cols-2 gap-3 md:grid-cols-3">
			{#each [{ label: 'Models', value: comma(configuredModels.length), color: 'var(--accent-primary)' }, { label: 'Samples', value: comma(totalSamples / configuredModels.length), color: 'var(--accent-tertiary)' }, { label: 'Total Cost', value: cost(totalCost), color: 'var(--accent-secondary)' }] as stat}
				<div
					class="rounded-xl border border-[var(--border-card)] bg-[var(--bg-surface)] p-4"
				>
					<p
						class="mb-1 font-mono text-[10px] tracking-wider uppercase"
						style="color: {stat.color};"
					>
						{stat.label}
					</p>
					<p class="font-mono text-xl font-medium text-stone-800 dark:text-white/90">{stat.value}</p>
				</div>
			{/each}
		</div>

		<!-- Chart + detail panel -->
		<section class="mb-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_18.5rem]">
			<div
				class="min-w-0 rounded-2xl border border-[var(--border-card)] bg-[var(--bg-surface)] p-5 md:p-6"
			>
				<div class="mb-4 flex flex-col items-start justify-between gap-3 md:flex-row md:items-center">
					<h2 class="text-lg font-semibold text-stone-800 dark:text-white/90 md:text-xl">Model Ranking</h2>
					<div class="flex flex-wrap items-center gap-2.5">
						<div
							class="inline-flex rounded-full border border-[var(--border-card)] bg-[var(--bg-surface)] p-1"
							role="radiogroup"
							aria-label="Sort ranking chart by"
						>
							{#each [{ key: 'quality', label: 'Quality' }, { key: 'cost', label: 'Cost' }, { key: 'latency', label: 'Latency' }] as option}
								<button
									type="button"
									role="radio"
									aria-checked={chartSortKey === option.key}
									onclick={() => (chartSortKey = option.key as ChartSortKey)}
									class="rounded-full px-3 py-1 text-[10px] font-mono tracking-wide uppercase transition-colors"
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

				<div class="space-y-2 md:hidden">
					{#each chartSorted as row}
						<button
							type="button"
							onclick={() => toggleSelectedModel(row.label)}
							class="w-full rounded-lg border border-[var(--border-card)] p-3 text-left"
							style:background={selectedModel === row.label
								? 'color-mix(in srgb, var(--accent-primary) 8%, var(--bg-surface))'
								: 'var(--bg-surface)'}
						>
							<div class="flex items-start justify-between gap-3">
								<div class="min-w-0">
									<p class="truncate text-sm font-medium text-stone-700 dark:text-white/85">{row.label}</p>
									<p class="font-mono text-[10px] text-stone-600 dark:text-white/70">
										#{row.rank} · Quality {pct(row.quality)}
									</p>
								</div>
								<span
									class="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full"
									style="background: {latencyColor(row)};"
								></span>
							</div>
							<p class="mt-2 font-mono text-[10px] text-stone-600 dark:text-white/70">
								{cost(row.costPerSample)} · {duration(row.latencyPerSample)}
							</p>
						</button>
					{/each}
				</div>

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
						aria-label={`Horizontal lollipop chart of model quality sorted by ${chartSortKey}`}
					>
						<defs>
							{#each chartSorted as row, i}
								<linearGradient id="bar-grad-{i}" x1="0" y1="0" x2="1" y2="0">
									<stop offset="0%" stop-color="var(--svg-bar-start)" stop-opacity="1" />
									<stop offset="100%" stop-color={latencyColor(row)} stop-opacity="0.35" />
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
							{@const tickVal = qualityFloor + (i / 5) * (maxQuality - qualityFloor)}
							{@const x = chartMargin.left + (i / 5) * chartInnerWidth}
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
								{pct(tickVal, 0)}
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
							{@const color = latencyColor(row)}
							{@const isHovered = hoveredModel === row.label}
							{@const isSelected = selectedModel === row.label}
							{@const isDimmed =
								(hoveredModel && !isHovered) || (selectedModel && !isSelected && !hoveredModel)}
							{@const isTop = i === 0}
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

								<!-- Model label -->
								<text
									x={chartMargin.left - 14}
									y={y + 5}
									text-anchor="end"
									font-size="13"
									font-family="Outfit"
									fill={isDimmed ? 'var(--svg-text-dim)' : isHovered || isSelected ? 'var(--svg-text)' : 'var(--svg-text-muted)'}
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

								<!-- Dot at end — radius encodes cost, color encodes latency -->
								<circle
									cx={chartMargin.left + bw}
									cy={y}
									r={isDimmed ? costRadius(row) * 0.7 : costRadius(row)}
									fill={color}
									fill-opacity={isDimmed ? 0.3 : 0.9}
									stroke={isTop ? 'var(--accent-primary)' : 'var(--svg-dot-stroke)'}
									stroke-width={isTop ? 1.5 : 1}
									style="transition: all 0.2s ease;"
								/>

								<!-- Quality value below dot, right-aligned to dot center -->
								<text
									x={chartMargin.left + bw}
									y={y + 16}
									text-anchor="end"
									font-size="11"
									font-family="Space Mono"
									fill={isDimmed ? 'var(--svg-text-dim)' : 'var(--svg-text-muted)'}
									style="transition: fill 0.2s ease;"
								>
									{pct(row.quality)}
								</text>

								<!-- Cost and latency annotation on far right -->
								<text
									x={chartWidth - 12}
									y={y + 5}
									text-anchor="end"
									font-size="12"
									font-family="Space Mono"
									fill={isDimmed ? 'var(--svg-text-dim)' : 'var(--svg-text-ghost)'}
									style="transition: fill 0.2s ease;"
								>
									{cost(row.costPerSample)} · {duration(row.latencyPerSample)}
								</text>
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
							Quality (1 − CER)
						</text>
					</svg>
				</div>

				<!-- Chart legend -->
				<div class="mt-4 flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-[var(--border-card)] pt-4">
					<div class="flex items-center gap-3">
						<p class="font-mono text-[9px] tracking-wider text-stone-600 uppercase dark:text-white/70">Dot Color = Latency</p>
						<div class="flex items-center gap-2.5">
							{#each [{ color: 'var(--accent-tertiary)', label: 'Low' }, { color: 'var(--accent-secondary)', label: 'Mid' }, { color: '#b6493f', label: 'High' }] as tier}
								<div class="flex items-center gap-1">
									<span
										class="inline-block h-2.5 w-2.5 rounded-full"
										style="background: {tier.color};"
									></span>
									<span class="font-mono text-[8px] text-stone-600 dark:text-white/70">{tier.label}</span>
								</div>
							{/each}
						</div>
					</div>
					<p class="font-mono text-[9px] tracking-wider text-stone-600 uppercase dark:text-white/70">Dot Size = Cost</p>
					<p class="text-[10px] text-stone-600 dark:text-white/70">
						{chartSortKey === 'quality'
							? 'Sorted by quality (1 - CER) descending'
							: chartSortKey === 'cost'
								? 'Sorted by cost per sample ascending'
								: 'Sorted by latency per sample ascending'}
					</p>
				</div>
			</div>

			<!-- Detail panel -->
			<div
				class="min-w-0 space-y-4 rounded-2xl border border-[var(--border-card)] bg-[var(--bg-surface)] p-5 md:p-6"
			>
				{#if activeDetail?.summary}
					<div class="flex items-center justify-between">
						<p class="font-mono text-[10px] tracking-wider text-stone-600 uppercase dark:text-white/70">
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
								>{activeDetail.rank}</span
							>
							<div>
								<h3 class="text-lg font-semibold text-stone-800 dark:text-white/90">{activeDetail.label}</h3>
								<p class="text-xs text-stone-700 dark:text-white/70">
									Quality: {pct(activeDetail.quality, 1)}
								</p>
							</div>
						</div>
					</div>

					<div class="flex justify-center gap-4">
						{#each [{ label: 'Quality', value: activeDetail.quality, color: 'var(--accent-primary)' }, { label: 'Similarity', value: activeDetail.similarity, color: 'var(--accent-tertiary)' }] as gauge}
							<div class="text-center">
								<CircularGauge value={gauge.value} label={gauge.label} color={gauge.color} />
							</div>
						{/each}
					</div>

					<div class="grid grid-cols-2 gap-3">
						{#each [{ label: 'CER Mean', value: pct(activeDetail.summary.cer_mean), color: 'var(--accent-primary)' }, { label: 'WER Mean', value: pct(activeDetail.summary.wer_mean), color: 'var(--accent-secondary)' }, { label: 'Cost / sample', value: cost(activeDetail.costPerSample), color: 'var(--accent-secondary)' }, { label: 'Latency / sample', value: duration(activeDetail.latencyPerSample), color: 'var(--accent-primary)' }] as card}
							<div
								class="rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] p-3"
							>
								<p
									class="mb-0.5 font-mono text-[9px] tracking-wider uppercase"
									style="color: {card.color};"
								>
									{card.label}
								</p>
								<p class="font-mono text-sm font-medium text-stone-700 dark:text-white/85">{card.value}</p>
							</div>
						{/each}
					</div>

					<div class="space-y-2 rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] p-3">
						<p class="font-mono text-[9px] tracking-wider text-stone-600 uppercase dark:text-white/70">Metric glossary</p>
						<dl class="space-y-1.5 text-[10px] leading-relaxed">
							<div class="flex gap-2">
								<dt class="shrink-0 font-mono font-medium" style="color: var(--accent-primary);">CER</dt>
								<dd class="text-stone-700 dark:text-white/70">Character Error Rate — fraction of characters the model got wrong vs. the ground truth. Lower is better.</dd>
							</div>
							<div class="flex gap-2">
								<dt class="shrink-0 font-mono font-medium" style="color: var(--accent-secondary);">WER</dt>
								<dd class="text-stone-700 dark:text-white/70">Word Error Rate — fraction of words with at least one error. Lower is better.</dd>
							</div>
							<div class="flex gap-2">
								<dt class="shrink-0 font-mono font-medium" style="color: var(--accent-primary);">Quality</dt>
								<dd class="text-stone-700 dark:text-white/70">1 minus CER — how accurate the transcription is overall. Higher is better.</dd>
							</div>
							<div class="flex gap-2">
								<dt class="shrink-0 font-mono font-medium" style="color: var(--accent-tertiary);">Similarity</dt>
								<dd class="text-stone-700 dark:text-white/70">Normalized Levenshtein similarity — how closely the output matches the reference text, from 0 to 1. Higher is better.</dd>
							</div>
						</dl>
					</div>
				{:else}
					<div class="flex h-full items-center justify-center text-sm text-stone-600 dark:text-white/70">
						No model data available.
					</div>
				{/if}
			</div>
		</section>

		<footer class="mt-8 flex flex-col items-center gap-2 border-t border-[var(--border-card)] pt-6 text-center md:flex-row md:justify-between md:text-left">
			<p class="font-mono text-[10px] text-stone-600 dark:text-white/70">
				{benchmarkData.benchmark.name}
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
			<p class="max-w-full text-balance font-mono text-[10px] text-stone-600 dark:text-white/70">
				{benchmarkData.benchmark.config.groups.map((g) => g.name).join(' · ')}
			</p>
		</footer>
	</main>
</div>
