<script lang="ts">
	import {
		pct,
		cost,
		duration,
		formatDate,
		comma,
		stripDiacritics,
		simpleDiff
	} from '$lib/utils';
	import CircularGauge from '$lib/components/CircularGauge.svelte';
	import { buildManifest } from '$lib/iiif';
	import { base } from '$app/paths';
	import { TriiiceratopsViewer, ViewerState } from 'triiiceratops';
	import { theme } from '$lib/theme.svelte';
	import ThemeToggle from '$lib/components/ThemeToggle.svelte';
	import type { BenchmarkResult, BenchmarkData } from '$lib/types';
	import type { PageData } from './$types';

	type GroupedSample = {
		key: string;
		group: string;
		label: string;
		image: string;
		ground_truth_file: string;
		ground_truth_text: string;
		resultsByModel: Record<string, BenchmarkResult>;
		availableModels: string[];
	};
	type MobilePanel = 'ground-truth' | 'model-output';

	const { data: pageData }: { data: PageData } = $props();
	// svelte-ignore state_referenced_locally
	const benchmarkData: BenchmarkData = pageData.benchmarkData;
	const pageTitle = 'Paleo Bench | Compare Model Outputs';
	const pageDescription =
		'Inspect side-by-side transcription output quality for each handwritten sample with synchronized diffs, CER/WER metrics, latency, and cost.';
	const socialImage = `${base}/paleo-bench-compare.png`;
	const configuredModelOrder = benchmarkData.benchmark.config.models.map((m) => m.label);
	const qualityRankedModelOrder = [...configuredModelOrder].sort((a, b) => {
		const aSummary = benchmarkData.model_summaries[a];
		const bSummary = benchmarkData.model_summaries[b];
		const aQuality = aSummary && aSummary.samples_evaluated > 0 ? 1 - aSummary.cer_mean : Number.NEGATIVE_INFINITY;
		const bQuality = bSummary && bSummary.samples_evaluated > 0 ? 1 - bSummary.cer_mean : Number.NEGATIVE_INFINITY;
		return bQuality - aQuality;
	});

	function groupResultsBySample(results: BenchmarkResult[]): GroupedSample[] {
		const grouped = new Map<string, GroupedSample>();

		for (const result of results) {
			const key = `${result.group}::${result.label}::${result.image}`;
			const existing = grouped.get(key);
			if (existing) {
				existing.resultsByModel[result.model] = result;
				continue;
			}

			grouped.set(key, {
				key,
				group: result.group,
				label: result.label,
				image: result.image,
				ground_truth_file: result.ground_truth_file,
				ground_truth_text: result.ground_truth_text,
				resultsByModel: { [result.model]: result },
				availableModels: []
			});
		}

		for (const sample of grouped.values()) {
			const present = new Set(Object.keys(sample.resultsByModel));
			sample.availableModels = [
				...qualityRankedModelOrder.filter((model) => present.has(model)),
				...Object.keys(sample.resultsByModel).filter(
					(model) => !qualityRankedModelOrder.includes(model)
				)
			];
		}

		return Array.from(grouped.values());
	}

	const samples = groupResultsBySample(benchmarkData.results);

	let viewerThemeConfig = $derived(
		theme.current === 'dark'
			? {
					primary: '#6bb8d6',
					secondary: '#d4956b',
					accent: '#7cb88a',
					base100: '#242429',
					base200: '#1a1a1f',
					base300: '#2e2e33',
					baseContent: '#f3efe8',
					neutral: '#2e2e33',
					neutralContent: '#f3efe8',
					colorScheme: 'dark'
				}
			: {
					primary: '#3b6b8a',
					secondary: '#a0522d',
					accent: '#4a7c59',
					base100: '#ffffff',
					base200: '#f5f3ef',
					base300: '#e0ddd6',
					baseContent: '#2c2a26',
					neutral: '#eae7e0',
					neutralContent: '#2c2a26',
					colorScheme: 'light'
				}
	) as any;

	const manifest = buildManifest(
		samples.map((s) => ({ label: s.label, infoJsonUrl: s.image })),
		benchmarkData.benchmark.name
	);
	const manifestBlob = new Blob([JSON.stringify(manifest)], { type: 'application/json' });
	const manifestUrl = URL.createObjectURL(manifestBlob);

	let viewerState = $state<ViewerState>();
	let activeCanvasIndex = $state(0);
	let selectedModel = $state('');
	let sidebarOpen = $state(false);
	let mobileActivePanel = $state<MobilePanel>('ground-truth');
	let isMobile = $state(false);

	// Draggable resizer state
	let viewerHeight = $state(0);
	let dragging = $state(false);
	const minViewerHeight = 120;
	const defaultViewerHeightRatio = 0.4;
	const mobileDefaultViewerHeightRatio = 0.35;
	const maxViewerHeightRatio = 0.7;
	const mobileBreakpoint = 1024;

	function updateViewportMode() {
		if (typeof window === 'undefined') return;
		isMobile = window.innerWidth < mobileBreakpoint;
		if (!isMobile) {
			sidebarOpen = false;
			mobileActivePanel = 'ground-truth';
		}
	}

	$effect(() => {
		if (typeof window === 'undefined') return;
		updateViewportMode();
		const onResize = () => updateViewportMode();
		window.addEventListener('resize', onResize);
		return () => {
			window.removeEventListener('resize', onResize);
		};
	});

	$effect(() => {
		if (typeof window !== 'undefined' && viewerHeight === 0) {
			viewerHeight = window.innerHeight * (isMobile ? mobileDefaultViewerHeightRatio : defaultViewerHeightRatio);
		}
	});

	function clampViewerHeight(nextHeight: number): number {
		const maxHeight = typeof window !== 'undefined' ? window.innerHeight * maxViewerHeightRatio : nextHeight;
		return Math.min(maxHeight, Math.max(minViewerHeight, nextHeight));
	}

	function setViewerHeightRatio(ratio: number) {
		if (typeof window === 'undefined') return;
		viewerHeight = clampViewerHeight(window.innerHeight * ratio);
	}

	function onResizeStart(e: PointerEvent) {
		if (isMobile) return;
		dragging = true;
		const startY = e.clientY;
		const startHeight = viewerHeight;
		const pointerTarget = e.currentTarget as HTMLElement | null;
		pointerTarget?.setPointerCapture(e.pointerId);

		function onMove(e: PointerEvent) {
			viewerHeight = clampViewerHeight(startHeight + (e.clientY - startY));
		}
		function onUp() {
			dragging = false;
			window.removeEventListener('pointermove', onMove);
			window.removeEventListener('pointerup', onUp);
			window.removeEventListener('pointercancel', onUp);
			pointerTarget?.releasePointerCapture(e.pointerId);
		}
		window.addEventListener('pointermove', onMove);
		window.addEventListener('pointerup', onUp);
		window.addEventListener('pointercancel', onUp);
	}

	function onResizeKeyDown(e: KeyboardEvent) {
		if (isMobile) return;
		const step = 24;
		if (e.key === 'ArrowUp') {
			e.preventDefault();
			viewerHeight = clampViewerHeight(viewerHeight - step);
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			viewerHeight = clampViewerHeight(viewerHeight + step);
		} else if (e.key === 'Home') {
			e.preventDefault();
			viewerHeight = minViewerHeight;
		} else if (e.key === 'End' && typeof window !== 'undefined') {
			e.preventDefault();
			viewerHeight = window.innerHeight * maxViewerHeightRatio;
		}
	}

	// Synchronized scrolling
	let gtPanel: HTMLElement | undefined = $state();
	let modelPanel: HTMLElement | undefined = $state();

	function syncScroll(node: HTMLElement, partner: () => HTMLElement | undefined) {
		let syncing = false;
		function onScroll() {
			const other = partner();
			if (syncing || !other) return;
			syncing = true;
			other.scrollTop = node.scrollTop;
			requestAnimationFrame(() => {
				syncing = false;
			});
		}
		node.addEventListener('scroll', onScroll, { passive: true });
		return {
			destroy() {
				node.removeEventListener('scroll', onScroll);
			}
		};
	}

	$effect(() => {
		if (viewerState) {
			const canvasId = viewerState.canvasId;
			if (canvasId) {
				const idx = samples.findIndex((_, i) => `urn:paleo-bench:canvas:${i}` === canvasId);
				if (idx >= 0) activeCanvasIndex = idx;
			}
		}
	});

	let activeSample = $derived(samples[activeCanvasIndex] ?? samples[0]);
	let activeResult = $derived(
		activeSample ? activeSample.resultsByModel[selectedModel] : undefined
	);
	let normalizedGroundTruth = $derived(
		activeSample ? stripDiacritics(activeSample.ground_truth_text) : ''
	);
	let normalizedModelOutput = $derived(
		activeResult ? stripDiacritics(activeResult.model_output) : ''
	);
	let diffResult = $derived(simpleDiff(normalizedGroundTruth, normalizedModelOutput));
	let groundTruthDiff = $derived(diffResult.ref);
	let modelOutputDiff = $derived(diffResult.hyp);

	$effect(() => {
		if (activeSample && !activeSample.availableModels.includes(selectedModel)) {
			selectedModel = activeSample.availableModels[0] ?? '';
		}
	});

	function selectSample(i: number) {
		activeCanvasIndex = i;
		if (viewerState) {
			viewerState.setCanvas(`urn:paleo-bench:canvas:${i}`);
		}
	}

	function shiftSample(step: number) {
		const next = (activeCanvasIndex + step + samples.length) % samples.length;
		selectSample(next);
	}

	function referenceCharCount(): number {
		if (activeResult?.metrics) return activeResult.metrics.char_count_reference;
		if (!activeSample) return 0;
		return stripDiacritics(activeSample.ground_truth_text).length;
	}

	function modelCharCount(): number {
		if (!activeResult) return 0;
		return stripDiacritics(activeResult.model_output).length;
	}
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
	class="h-dvh min-h-dvh overflow-hidden text-stone-900 dark:text-white"
	style="background: var(--bg-page); font-family: 'Outfit', sans-serif;"
>
	<div class="flex min-h-0 h-full flex-col">
		<!-- Nav bar -->
		<nav
			class="flex shrink-0 flex-wrap items-center gap-2 border-b border-[var(--border-card)] px-3 py-3 sm:px-4 lg:px-6"
			style="background: var(--bg-surface);"
		>
			<div class="flex min-w-0 items-center gap-2 sm:gap-4">
				<!-- Mobile sidebar toggle -->
				<button
					onclick={() => (sidebarOpen = !sidebarOpen)}
					class="cursor-pointer rounded-lg border border-[var(--border-card)] p-2 text-stone-600 transition-colors hover:bg-stone-100 dark:text-white/70 lg:hidden"
					aria-label="Toggle sidebar"
				>
					<svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
					</svg>
				</button>
				<h1 class="hidden text-sm font-semibold tracking-[0.2em] text-stone-600 sm:block dark:text-white/70">COMPARISON VIEW</h1>
				<a
					href={base || '/'}
					class="group flex items-center gap-1 rounded-full border border-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:brightness-95 hover:shadow-md"
					style="background: var(--accent-primary); box-shadow: 0 10px 28px -20px var(--accent-primary);"
					>Back to dashboard</a
				>
			</div>
			<div class="ml-auto flex items-center gap-2 sm:gap-4">
				<a
					href="https://github.com/d-flood/paleo-bench"
					target="_blank"
					rel="noreferrer"
					class="hidden text-xs transition-colors hover:opacity-80 sm:block"
					style="color: var(--accent-primary);"
				>
					View on GitHub
				</a>
				<span class="hidden font-mono text-xs text-stone-600 md:block dark:text-white/70"
					>{formatDate(benchmarkData.benchmark.timestamp)}</span
				>
				<ThemeToggle />
			</div>
		</nav>

		<div class="flex min-h-0 flex-1">
			<!-- Mobile backdrop -->
			{#if sidebarOpen}
				<button
					class="fixed inset-0 z-20 cursor-pointer bg-black/50 lg:hidden"
					onclick={() => (sidebarOpen = false)}
					aria-label="Close sidebar"
				></button>
			{/if}

			<!-- Sidebar -->
			<aside
				class="fixed inset-y-0 left-0 z-30 flex w-[min(20rem,92vw)] shrink-0 transform flex-col gap-3 overflow-y-auto border-r border-[var(--border-card)] p-4 transition-transform duration-200 lg:relative lg:z-auto lg:w-80 lg:translate-x-0"
				style="background: var(--bg-surface);"
				class:translate-x-0={sidebarOpen}
				class:-translate-x-full={!sidebarOpen}
			>
				<!-- Sample Navigator -->
				<p class="font-mono text-[10px] tracking-wider text-stone-600 uppercase dark:text-white/70">
					Sample Navigator
				</p>
				<select
					class="compare-select rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-stone-700 outline-none focus:border-[var(--accent-primary)] dark:text-white/85"
					value={activeCanvasIndex}
					onchange={(e) => {
						selectSample(Number((e.currentTarget as HTMLSelectElement).value));
						sidebarOpen = false;
					}}
				>
					{#each samples as sample, idx}
						<option value={idx}>{sample.group} - {sample.label}</option>
					{/each}
				</select>
				{#if activeSample}
					<p
						class="rounded-md border border-[var(--border-card)] bg-[var(--bg-surface)] px-2.5 py-2 text-xs leading-relaxed text-stone-600 break-words dark:text-white/75"
					>
						<span class="font-mono text-[10px] tracking-wide text-stone-600 uppercase dark:text-white/70">Selected:</span>
						{activeSample.group} - {activeSample.label}
					</p>
				{/if}

				<div class="flex gap-2">
					<button
						onclick={() => shiftSample(-1)}
						class="cursor-pointer flex-1 rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs tracking-wide uppercase transition-colors hover:bg-stone-100 dark:hover:bg-[#2c2c31]"
					>
						Prev
					</button>
					<button
						onclick={() => shiftSample(1)}
						class="cursor-pointer flex-1 rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs tracking-wide uppercase transition-colors hover:bg-stone-100 dark:hover:bg-[#2c2c31]"
					>
						Next
					</button>
				</div>

				<!-- Model Selector -->
				<p class="mt-1 font-mono text-[10px] tracking-wider text-stone-600 uppercase dark:text-white/70">
					Model ({activeSample?.availableModels.length ?? 0})
				</p>
				{#if activeSample}
					<div
						class="max-h-48 overflow-y-auto rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)]"
					>
						{#each activeSample.availableModels as model}
							{@const result = activeSample.resultsByModel[model]}
							{@const isActive = selectedModel === model}
								<button
									type="button"
									onclick={() => (selectedModel = model)}
									class="cursor-pointer flex w-full items-center gap-2 border-l-2 px-3 py-2 text-left text-xs transition-colors hover:bg-stone-50 dark:hover:bg-[#2c2c31]"
									style:border-left-color={isActive ? 'var(--accent-secondary)' : 'transparent'}
									style:background={isActive
										? 'color-mix(in srgb, var(--accent-secondary) 10%, transparent)'
									: 'transparent'}
							>
								<span
									class="min-w-0 flex-1 truncate {isActive ? 'text-stone-800 dark:text-white/90' : 'text-stone-700 dark:text-white/60'}"
								>
									{model}
								</span>
								{#if result?.metrics}
									<span class="shrink-0 font-mono text-[10px] text-stone-600 dark:text-white/70">
										{pct(result.metrics.cer, 1)}
									</span>
								{/if}
							</button>
						{/each}
					</div>
				{/if}

				<!-- Metric Cards -->
				{#if activeResult?.metrics}
					<p class="mt-1 font-mono text-[10px] tracking-wider text-stone-600 uppercase dark:text-white/70">
						Metrics
					</p>
					<div class="grid grid-cols-2 gap-2">
						{#each [{ label: 'Latency', value: duration(activeResult.response_metadata.latency_seconds), color: 'var(--accent-primary)' }, { label: 'Cost', value: cost(activeResult.response_metadata.cost), color: 'var(--accent-secondary)' }, { label: 'Tokens', value: comma(activeResult.response_metadata.input_tokens + activeResult.response_metadata.output_tokens), color: 'var(--accent-primary)' }, { label: 'Lev. Dist', value: comma(activeResult.metrics.levenshtein_distance), color: 'var(--accent-secondary)' }] as card}
							<div
								class="rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] p-2.5"
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

					<!-- Gauges -->
					<div class="flex justify-center gap-3 py-1">
						{#each [{ label: 'CER', value: activeResult.metrics.cer, color: 'var(--accent-primary)' }, { label: 'WER', value: activeResult.metrics.wer, color: 'var(--accent-secondary)' }, { label: 'SIM', value: activeResult.metrics.normalized_levenshtein_similarity, color: 'var(--accent-tertiary)' }] as gauge}
							<div class="text-center">
								<CircularGauge value={gauge.value} label={gauge.label} color={gauge.color} size={64} />
							</div>
						{/each}
					</div>
				{/if}

				<!-- Diff Legend -->
				<div
					class="rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] p-3"
				>
					<p class="mb-2 font-mono text-[9px] tracking-wider text-stone-600 uppercase dark:text-white/70">
						Diff Legend
					</p>
					<div class="space-y-1.5 text-[10px]">
						<div class="flex items-center gap-2">
							<span
								class="inline-block h-3 w-6 rounded"
								style="background: var(--diff-replace-bg);"
							></span>
							<span class="text-stone-700 dark:text-white/50">Replace — text changed between GT & model</span>
						</div>
						<div class="flex items-center gap-2">
							<span
								class="inline-block h-3 w-6 rounded"
								style="background: var(--diff-delete-bg);"
							></span>
							<span class="text-stone-700 dark:text-white/50">Delete — text in GT omitted by model</span>
						</div>
						<div class="flex items-center gap-2">
							<span
								class="inline-block h-3 w-6 rounded"
								style="background: var(--diff-insert-bg);"
							></span>
							<span class="text-stone-700 dark:text-white/50">Insert — text added by model not in GT</span>
						</div>
					</div>
				</div>

				<!-- Info box -->
				<div
					class="mt-auto rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] p-3"
				>
					<p class="text-[10px] leading-relaxed text-stone-700 dark:text-white/70">
						Desktop: drag the divider to resize and scroll both transcription panels together.
						Mobile: use the size presets and switch between Ground Truth and Model Output tabs.
					</p>
				</div>
			</aside>

			<!-- Main content area -->
			<main class="flex min-h-0 flex-1 flex-col overflow-hidden">
				{#if viewerHeight > 0}
					<!-- IIIF Viewer -->
					<div class="shrink-0" style="height: {viewerHeight}px;">
						<TriiiceratopsViewer
							manifestId={manifestUrl}
							bind:viewerState
							themeConfig={viewerThemeConfig}
							config={{
								toolbarOpen: false,
								showCanvasNav: true,
								showToggle: false,
							}}
						/>
					</div>

					{#if isMobile}
						<div
							class="flex shrink-0 items-center justify-end gap-1.5 border-b border-[var(--border-card)] px-3 py-1.5"
						>
							{#each [{ label: 'Compact', ratio: 0.28 }, { label: 'Balanced', ratio: mobileDefaultViewerHeightRatio }, { label: 'Large', ratio: 0.5 }] as size}
								<button
									type="button"
									onclick={() => setViewerHeightRatio(size.ratio)}
									class="rounded-full border border-[var(--border-card)] px-2.5 py-1 text-[10px] font-mono tracking-wide uppercase text-stone-800 dark:text-white/70"
								>
									{size.label}
								</button>
							{/each}
						</div>
					{/if}

					<!-- Draggable resizer -->
					<button
						type="button"
						aria-label="Resize viewer and transcription panels"
						class="group relative hidden h-1.5 shrink-0 cursor-row-resize items-center justify-center border-y border-[var(--border-card)] transition-colors hover:bg-stone-100 lg:flex"
						style:background={dragging
							? 'color-mix(in srgb, var(--accent-primary) 14%, transparent)'
							: undefined}
						onpointerdown={onResizeStart}
						onkeydown={onResizeKeyDown}
					>
						<div
							class="h-0.5 w-10 rounded-full bg-stone-300 transition-colors group-hover:bg-stone-400 dark:bg-white/20 dark:group-hover:bg-white/35"
							style:background={dragging ? 'var(--accent-primary)' : undefined}
						></div>
					</button>

					<!-- Transcription panels -->
					{#if activeSample}
						{#if isMobile}
							<div
								class="flex shrink-0 items-center gap-1 border-b border-[var(--border-card)] bg-[var(--bg-surface)] px-3 py-2"
							>
								<button
									type="button"
									onclick={() => (mobileActivePanel = 'ground-truth')}
									class="rounded-full px-3 py-1 text-[10px] font-mono tracking-wide uppercase transition-colors"
									class:bg-[var(--accent-primary)]={mobileActivePanel === 'ground-truth'}
									class:text-white={mobileActivePanel === 'ground-truth'}
									class:text-stone-700={mobileActivePanel !== 'ground-truth'}
								>
									Ground Truth
								</button>
								<button
									type="button"
									onclick={() => (mobileActivePanel = 'model-output')}
									class="rounded-full px-3 py-1 text-[10px] font-mono tracking-wide uppercase transition-colors"
									class:bg-[var(--accent-secondary)]={mobileActivePanel === 'model-output'}
									class:text-white={mobileActivePanel === 'model-output'}
									class:text-stone-700={mobileActivePanel !== 'model-output'}
								>
									Model Output
								</button>
							</div>
						{/if}
						<div class="flex min-h-0 flex-1 overflow-hidden">
							<!-- Ground Truth panel -->
							{#if !isMobile || mobileActivePanel === 'ground-truth'}
								<div
									class="flex min-h-0 flex-1 flex-col border-b border-[var(--border-card)] lg:border-r lg:border-b-0"
									style="background: color-mix(in srgb, var(--accent-primary) 6%, var(--bg-surface));"
								>
									<div
										class="flex shrink-0 items-center gap-2 border-b border-[var(--border-card)] px-4 py-2"
									>
										<span
											class="h-2 w-2 rounded-full"
											style="background: var(--accent-primary);"
										></span>
										<h3 class="text-xs tracking-wider uppercase" style="color: var(--accent-primary);">
											Ground Truth
										</h3>
										<span class="ml-auto font-mono text-[10px] text-stone-600 dark:text-white/70"
											>{comma(referenceCharCount())} chars</span
										>
									</div>
									<div
										bind:this={gtPanel}
										use:syncScroll={() => modelPanel}
										class="flex-1 overflow-y-auto p-4 font-[Space_Mono] text-xs leading-relaxed whitespace-pre-wrap text-stone-600 dark:text-white/70"
									>
										{#each groundTruthDiff as segment}
											<span
												class:diff-replace={segment.type === 'replace'}
												class:diff-delete={segment.type === 'delete'}>{segment.text}</span
											>
										{/each}
									</div>
								</div>
							{/if}

							<!-- Model Output panel -->
							{#if !isMobile || mobileActivePanel === 'model-output'}
								<div
									class="flex min-h-0 flex-1 flex-col"
									style="background: color-mix(in srgb, var(--accent-secondary) 6%, var(--bg-surface));"
								>
									<div
										class="flex shrink-0 items-center gap-2 border-b border-[var(--border-card)] px-4 py-2"
									>
										<span
											class="h-2 w-2 rounded-full"
											style="background: var(--accent-secondary);"
										></span>
										<h3 class="text-xs tracking-wider uppercase" style="color: var(--accent-secondary);">
											Model Output
										</h3>
										<span class="ml-auto truncate font-mono text-[10px] text-stone-600 dark:text-white/70"
											>{selectedModel}</span
										>
									</div>
									{#if activeResult?.error}
										<div class="p-4">
											<div
												class="rounded-lg border border-amber-400/30 p-3 text-xs text-amber-700 dark:text-amber-200"
												style="background: rgba(245,158,11,0.08);"
											>
												{activeResult.error}
											</div>
										</div>
									{:else if activeResult}
										<div
											bind:this={modelPanel}
											use:syncScroll={() => gtPanel}
											class="flex-1 overflow-y-auto p-4 font-[Space_Mono] text-xs leading-relaxed whitespace-pre-wrap text-stone-600 dark:text-white/70"
										>
											{#each modelOutputDiff as segment}
												<span
													class:diff-replace={segment.type === 'replace'}
													class:diff-insert={segment.type === 'insert'}>{segment.text}</span
												>
											{/each}
										</div>
									{:else}
										<div class="flex flex-1 items-center justify-center text-sm text-stone-600 dark:text-white/70">
											No result found for this model/sample.
										</div>
									{/if}
									</div>
							{/if}
						</div>
					{/if}
				{/if}
			</main>
		</div>
	</div>
</div>

<style>
	:global(.compare-select) {
		color-scheme: light dark;
	}

	:global(.compare-select option) {
		background: var(--bg-page);
		color: var(--svg-text-muted);
	}

	.diff-replace {
		background: var(--diff-replace-bg);
		color: var(--diff-replace-text);
		border-radius: 3px;
	}

	.diff-insert {
		background: var(--diff-insert-bg);
		color: var(--diff-insert-text);
		border-radius: 3px;
	}

	.diff-delete {
		background: var(--diff-delete-bg);
		color: var(--diff-delete-text);
		border-radius: 3px;
	}
</style>
