<script lang="ts">
  import {
    pct,
    cost,
    duration,
    formatDate,
    comma,
    stripDiacritics,
    simpleDiff,
    normalizeInverted
  } from '$lib/utils';
  import CircularGauge from '$lib/components/CircularGauge.svelte';
  import { buildManifest } from '$lib/iiif';
  import { browser, dev } from '$app/environment';
  import { asset, resolve } from '$app/paths';
  import { TriiiceratopsViewer, ViewerState } from 'triiiceratops';
  import TextAa from 'phosphor-svelte/lib/TextAa';
  import CurrencyDollar from 'phosphor-svelte/lib/CurrencyDollar';
  import Clock from 'phosphor-svelte/lib/Clock';
  import { theme } from '$lib/theme.svelte';
  import ThemeToggle from '$lib/components/ThemeToggle.svelte';
  import type {
    CompareIndexData,
    CompareResultSummary,
    CompareSampleIndex,
    SampleDetailsData
  } from '$lib/types';
  import type { PageData } from './$types';

  type GroupedSample = CompareSampleIndex;
  type DiffToken = {
    type: string;
    text: string;
  };
  type DiffLine = {
    lineNumber: number;
    segments: DiffToken[];
  };
  type MobilePanel = 'ground-truth' | 'model-output';

  const { data: pageData }: { data: PageData } = $props();
  // svelte-ignore state_referenced_locally
  const compareIndex: CompareIndexData = pageData.compareIndex;
  const pageTitle = 'Paleo Bench | Compare Model Outputs';
  const pageDescription =
    'Inspect side-by-side transcription output quality for each handwritten sample with synchronized diffs, CER/WER metrics, latency, and cost.';
  const productionSiteUrl = 'https://d-flood.github.io/paleo-bench/';
  const socialImage = dev
    ? asset('/paleo-bench-compare.png')
    : new URL('paleo-bench-compare.png', productionSiteUrl).toString();
  const samples: GroupedSample[] = compareIndex.samples;

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
    compareIndex.benchmark.name
  );
  const manifestBlob = new Blob([JSON.stringify(manifest)], { type: 'application/json' });
  const manifestUrl = URL.createObjectURL(manifestBlob);

  let viewerState = $state<ViewerState>();
  let activeCanvasIndex = $state(0);
  let selectedModel = $state('');
  let sampleDetailsCache = $state<Record<string, SampleDetailsData>>({});
  let loadingSampleId = $state<string | null>(null);
  let sampleDetailsError = $state<string | null>(null);
  let sidebarOpen = $state(false);
  let mobileActivePanel = $state<MobilePanel>('ground-truth');
  let mobileModelDropdownOpen = $state(false);
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
    if (!browser) return;
    isMobile = window.innerWidth < mobileBreakpoint;
    if (!isMobile) {
      sidebarOpen = false;
      mobileActivePanel = 'ground-truth';
    }
  }

  $effect(() => {
    if (!browser) return;
    updateViewportMode();
    const onResize = () => updateViewportMode();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
    };
  });

  $effect(() => {
    if (browser && viewerHeight === 0) {
      viewerHeight =
        window.innerHeight * (isMobile ? mobileDefaultViewerHeightRatio : defaultViewerHeightRatio);
    }
  });

  function clampViewerHeight(nextHeight: number): number {
    const maxHeight = browser ? window.innerHeight * maxViewerHeightRatio : nextHeight;
    return Math.min(maxHeight, Math.max(minViewerHeight, nextHeight));
  }

  function setViewerHeightRatio(ratio: number) {
    if (!browser) return;
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
    } else if (e.key === 'End' && browser) {
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

  async function ensureSampleDetails(sampleId: string) {
    if (sampleDetailsCache[sampleId]) {
      return;
    }

    loadingSampleId = sampleId;
    sampleDetailsError = null;

    try {
      const response = await fetch(asset(`/site-data/samples/${sampleId}.json`));
      if (!response.ok) {
        throw new Error(`Failed to load sample details (${response.status})`);
      }
      const details = (await response.json()) as SampleDetailsData;
      sampleDetailsCache = {
        ...sampleDetailsCache,
        [sampleId]: details
      };
    } catch (error) {
      sampleDetailsError = error instanceof Error ? error.message : 'Failed to load sample details';
    } finally {
      if (loadingSampleId === sampleId) {
        loadingSampleId = null;
      }
    }
  }

  let activeSample = $derived(samples[activeCanvasIndex] ?? samples[0]);
  let activeSampleDetails = $derived(
    activeSample ? sampleDetailsCache[activeSample.sampleId] : undefined
  );
  let sampleDetailsLoading = $derived(
    activeSample ? loadingSampleId === activeSample.sampleId : false
  );
  let activeResultBase = $derived(
    activeSample ? activeSample.resultsByModel[selectedModel] : undefined
  );
  let activeResult = $derived.by(() => {
    if (!activeResultBase) return undefined;
    return {
      ...activeResultBase,
      model_output: activeSampleDetails?.model_outputs[selectedModel] ?? ''
    };
  });
  let normalizedGroundTruth = $derived(
    activeSampleDetails ? stripDiacritics(activeSampleDetails.ground_truth_text) : ''
  );
  let normalizedModelOutput = $derived(
    activeResult?.model_output ? stripDiacritics(activeResult.model_output) : ''
  );
  let diffResult = $derived(simpleDiff(normalizedGroundTruth, normalizedModelOutput));
  let groundTruthDiff = $derived(diffResult.ref);
  let modelOutputDiff = $derived(diffResult.hyp);
  let groundTruthLines = $derived(splitDiffLines(groundTruthDiff));
  let modelOutputLines = $derived(splitDiffLines(modelOutputDiff));

  // Per-sample min/max for cost and latency (used for mobile gauge normalization)
  let sampleCostRange = $derived.by(() => {
    if (!activeSample) return { min: 0, max: 1 };
    let min = Infinity,
      max = -Infinity;
    for (const model of activeSample.availableModels) {
      const r = activeSample.resultsByModel[model];
      if (r?.response_metadata?.cost != null) {
        const v = r.response_metadata.cost;
        if (v < min) min = v;
        if (v > max) max = v;
      }
    }
    if (!isFinite(min)) return { min: 0, max: 1 };
    return { min, max };
  });

  let sampleLatencyRange = $derived.by(() => {
    if (!activeSample) return { min: 0, max: 1 };
    let min = Infinity,
      max = -Infinity;
    for (const model of activeSample.availableModels) {
      const r = activeSample.resultsByModel[model];
      if (r?.response_metadata?.latency_seconds != null) {
        const v = r.response_metadata.latency_seconds;
        if (v < min) min = v;
        if (v > max) max = v;
      }
    }
    if (!isFinite(min)) return { min: 0, max: 1 };
    return { min, max };
  });

  function mobileGauges(result: CompareResultSummary | undefined) {
    if (!result?.metrics) return { quality: 0, cost: 0, latency: 0 };
    return {
      quality: Math.max(0, 1 - result.metrics.cer),
      cost: normalizeInverted(
        result.response_metadata.cost,
        sampleCostRange.min,
        sampleCostRange.max
      ),
      latency: normalizeInverted(
        result.response_metadata.latency_seconds,
        sampleLatencyRange.min,
        sampleLatencyRange.max
      )
    };
  }

  function splitDiffLines(segments: DiffToken[]): DiffLine[] {
    const lines: DiffLine[] = [{ lineNumber: 1, segments: [] }];

    for (const segment of segments) {
      const parts = segment.text.split('\n');
      for (let i = 0; i < parts.length; i += 1) {
        const part = parts[i];
        if (part.length > 0) {
          lines[lines.length - 1].segments.push({
            type: segment.type,
            text: part
          });
        }
        if (i < parts.length - 1) {
          lines.push({
            lineNumber: lines.length + 1,
            segments: []
          });
        }
      }
    }

    return lines;
  }

  const mobileGaugeIcons = {
    quality: TextAa,
    cost: CurrencyDollar,
    latency: Clock
  };

  $effect(() => {
    if (activeSample && !activeSample.availableModels.includes(selectedModel)) {
      selectedModel = activeSample.availableModels[0] ?? '';
    }
  });

  $effect(() => {
    if (!browser || !activeSample) return;
    void ensureSampleDetails(activeSample.sampleId);
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
    if (activeResultBase?.metrics) return activeResultBase.metrics.char_count_reference;
    if (!activeSampleDetails) return 0;
    return stripDiacritics(activeSampleDetails.ground_truth_text).length;
  }

  function modelCharCount(): number {
    if (!activeResult?.model_output) return 0;
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
  <div class="flex h-full min-h-0 flex-col">
    <!-- Nav bar -->
    <nav
      class="flex shrink-0 flex-wrap items-center gap-2 border-b border-[var(--border-card)] px-3 py-3 sm:px-4 lg:px-6"
      style="background: var(--bg-surface);"
    >
      <div class="flex min-w-0 items-center gap-2 sm:gap-4">
        <!-- Mobile sidebar toggle -->
        <button
          onclick={() => (sidebarOpen = !sidebarOpen)}
          class="cursor-pointer rounded-lg border border-[var(--border-card)] p-2 text-stone-600 transition-colors hover:bg-stone-100 lg:hidden dark:text-white/70"
          aria-label="Toggle sidebar"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1
          class="hidden text-sm font-semibold tracking-[0.2em] text-stone-600 sm:block dark:text-white/70"
        >
          COMPARISON VIEW
        </h1>
        <a
          href={resolve('/')}
          class="group flex items-center gap-1 rounded-full border border-[var(--accent-primary)] px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md hover:brightness-95"
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
          >{formatDate(compareIndex.benchmark.timestamp)}</span
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
            class="rounded-md border border-[var(--border-card)] bg-[var(--bg-surface)] px-2.5 py-2 text-xs leading-relaxed break-words text-stone-600 dark:text-white/75"
          >
            <span
              class="font-mono text-[10px] tracking-wide text-stone-600 uppercase dark:text-white/70"
              >Selected:</span
            >
            {activeSample.group} - {activeSample.label}
          </p>
        {/if}

        <div class="flex gap-2">
          <button
            onclick={() => shiftSample(-1)}
            class="flex-1 cursor-pointer rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs tracking-wide uppercase transition-colors hover:bg-stone-100 dark:hover:bg-[#2c2c31]"
          >
            Prev
          </button>
          <button
            onclick={() => shiftSample(1)}
            class="flex-1 cursor-pointer rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] px-3 py-1.5 text-xs tracking-wide uppercase transition-colors hover:bg-stone-100 dark:hover:bg-[#2c2c31]"
          >
            Next
          </button>
        </div>

        <!-- Model Selector -->
        <p
          class="mt-1 font-mono text-[10px] tracking-wider text-stone-600 uppercase dark:text-white/70"
        >
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
                class="flex w-full cursor-pointer items-center gap-2 border-l-2 px-3 py-2 text-left text-xs transition-colors hover:bg-stone-50 dark:hover:bg-[#2c2c31]"
                style:border-left-color={isActive ? 'var(--accent-secondary)' : 'transparent'}
                style:background={isActive
                  ? 'color-mix(in srgb, var(--accent-secondary) 10%, transparent)'
                  : 'transparent'}
              >
                <span
                  class="min-w-0 flex-1 truncate {isActive
                    ? 'text-stone-800 dark:text-white/90'
                    : 'text-stone-700 dark:text-white/60'}"
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
          <p
            class="mt-1 font-mono text-[10px] tracking-wider text-stone-600 uppercase dark:text-white/70"
          >
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
                <p class="font-mono text-sm font-medium text-stone-700 dark:text-white/85">
                  {card.value}
                </p>
              </div>
            {/each}
          </div>

          <!-- Gauges -->
          <div class="flex justify-center gap-3 py-1">
            {#each [{ label: 'CER', value: activeResult.metrics.cer, color: 'var(--accent-primary)' }, { label: 'WER', value: activeResult.metrics.wer, color: 'var(--accent-secondary)' }, { label: 'SIM', value: activeResult.metrics.normalized_levenshtein_similarity, color: 'var(--accent-tertiary)' }] as gauge}
              <div class="text-center">
                <CircularGauge
                  value={gauge.value}
                  label={gauge.label}
                  color={gauge.color}
                  size={64}
                />
              </div>
            {/each}
          </div>
        {/if}

        <!-- Diff Legend -->
        <div class="rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] p-3">
          <p
            class="mb-2 font-mono text-[9px] tracking-wider text-stone-600 uppercase dark:text-white/70"
          >
            Diff Legend
          </p>
          <div class="space-y-1.5 text-[10px]">
            <div class="flex items-center gap-2">
              <span class="inline-block h-3 w-6 rounded" style="background: var(--diff-replace-bg);"
              ></span>
              <span class="text-stone-700 dark:text-white/50"
                >Replace — text changed between GT & model</span
              >
            </div>
            <div class="flex items-center gap-2">
              <span class="inline-block h-3 w-6 rounded" style="background: var(--diff-delete-bg);"
              ></span>
              <span class="text-stone-700 dark:text-white/50"
                >Delete — text in GT omitted by model</span
              >
            </div>
            <div class="flex items-center gap-2">
              <span class="inline-block h-3 w-6 rounded" style="background: var(--diff-insert-bg);"
              ></span>
              <span class="text-stone-700 dark:text-white/50"
                >Insert — text added by model not in GT</span
              >
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
                showToggle: false
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
                  class="rounded-full border border-[var(--border-card)] px-2.5 py-1 font-mono text-[10px] tracking-wide text-stone-800 uppercase dark:text-white/70"
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
                  class="rounded-full px-3 py-1 font-mono text-[10px] tracking-wide text-stone-600 uppercase transition-colors dark:text-white/70"
                  class:bg-[var(--accent-primary)]={mobileActivePanel === 'ground-truth'}
                  class:!text-white={mobileActivePanel === 'ground-truth'}
                >
                  Ground Truth
                </button>
                <button
                  type="button"
                  onclick={() => (mobileActivePanel = 'model-output')}
                  class="rounded-full px-3 py-1 font-mono text-[10px] tracking-wide text-stone-600 uppercase transition-colors dark:text-white/70"
                  class:bg-[var(--accent-secondary)]={mobileActivePanel === 'model-output'}
                  class:!text-white={mobileActivePanel === 'model-output'}
                >
                  Model Output
                </button>
                {#if activeSample}
                  <div class="relative ml-auto max-w-[55%] min-w-0">
                    <!-- Selected model button -->
                    <button
                      type="button"
                      onclick={() => (mobileModelDropdownOpen = !mobileModelDropdownOpen)}
                      class="flex w-full cursor-pointer items-center gap-1.5 rounded-full border border-[var(--border-card)] bg-[var(--bg-surface)] px-2.5 py-1"
                    >
                      <span
                        class="min-w-0 flex-1 truncate font-mono text-[10px] text-stone-700 dark:text-white/85"
                        >{selectedModel}</span
                      >
                      <svg
                        class="h-3 w-3 shrink-0 text-stone-500 transition-transform dark:text-white/50"
                        class:rotate-180={mobileModelDropdownOpen}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M19 9l-7 7-7-7"
                        />
                      </svg>
                    </button>

                    <!-- Dropdown panel -->
                    {#if mobileModelDropdownOpen}
                      <!-- Backdrop -->
                      <button
                        type="button"
                        class="fixed inset-0 z-40 cursor-default"
                        onclick={() => (mobileModelDropdownOpen = false)}
                        aria-label="Close model dropdown"
                      ></button>
                      <div
                        class="absolute top-full right-0 z-50 mt-1 max-h-64 w-72 overflow-y-auto rounded-lg border border-[var(--border-card)] bg-[var(--bg-surface)] shadow-lg"
                      >
                        {#each activeSample.availableModels as model}
                          {@const result = activeSample.resultsByModel[model]}
                          {@const gauges = mobileGauges(result)}
                          {@const isActive = selectedModel === model}
                          <button
                            type="button"
                            onclick={() => {
                              selectedModel = model;
                              mobileModelDropdownOpen = false;
                            }}
                            class="flex w-full cursor-pointer items-center gap-2 border-l-2 px-3 py-2 text-left transition-colors hover:bg-stone-50 dark:hover:bg-[#2c2c31]"
                            style:border-left-color={isActive
                              ? 'var(--accent-secondary)'
                              : 'transparent'}
                            style:background={isActive
                              ? 'color-mix(in srgb, var(--accent-secondary) 10%, transparent)'
                              : 'transparent'}
                          >
                            <span
                              class="min-w-0 flex-1 truncate font-mono text-[10px] {isActive
                                ? 'text-stone-800 dark:text-white/90'
                                : 'text-stone-700 dark:text-white/60'}"
                            >
                              {model}
                            </span>
                            <CircularGauge
                              value={gauges.quality}
                              label=""
                              color="var(--accent-primary)"
                              size={24}
                              icon={mobileGaugeIcons.quality}
                            />
                            <CircularGauge
                              value={gauges.cost}
                              label=""
                              color="var(--accent-secondary)"
                              size={24}
                              icon={mobileGaugeIcons.cost}
                            />
                            <CircularGauge
                              value={gauges.latency}
                              label=""
                              color="var(--accent-tertiary)"
                              size={24}
                              icon={mobileGaugeIcons.latency}
                            />
                          </button>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/if}
              </div>
            {/if}
            <div class="flex min-h-0 flex-1 overflow-hidden">
              <!-- Ground Truth panel -->
              {#if !isMobile || mobileActivePanel === 'ground-truth'}
                <div
                  class="flex min-h-0 min-w-0 flex-1 flex-col border-b border-[var(--border-card)] lg:border-r lg:border-b-0"
                  style="background: color-mix(in srgb, var(--accent-primary) 6%, var(--bg-surface));"
                >
                  <div
                    class="flex min-w-0 shrink-0 items-center gap-2 border-b border-[var(--border-card)] px-4 py-2"
                  >
                    <span class="h-2 w-2 rounded-full" style="background: var(--accent-primary);"
                    ></span>
                    <h3
                      class="text-xs tracking-wider uppercase"
                      style="color: var(--accent-primary);"
                    >
                      Ground Truth
                    </h3>
                    <span
                      class="ml-auto min-w-0 truncate text-right font-mono text-[9px] text-stone-600 sm:text-[10px] dark:text-white/70"
                      >{comma(referenceCharCount())} chars</span
                    >
                  </div>
                  <div
                    bind:this={gtPanel}
                    use:syncScroll={() => modelPanel}
                    class="min-w-0 flex-1 overflow-auto py-4 pr-4 pl-2 font-[Space_Mono] text-xs leading-relaxed text-stone-600 dark:text-white/70"
                  >
                    {#if sampleDetailsLoading}
                      <p class="px-2 text-sm text-stone-600 dark:text-white/70">
                        Loading sample text…
                      </p>
                    {:else if sampleDetailsError}
                      <p class="px-2 text-sm text-amber-700 dark:text-amber-200">
                        {sampleDetailsError}
                      </p>
                    {:else if activeSampleDetails}
                      <div class="w-max min-w-full">
                        {#each groundTruthLines as line}
                          <div class="grid w-max grid-cols-[1.75rem_auto] items-baseline gap-x-2.5">
                            <span
                              class="w-7 shrink-0 text-right font-mono text-[10px] text-stone-400 dark:text-white/35"
                            >
                              {line.lineNumber}
                            </span>
                            <div class="w-max whitespace-pre">
                              {#if line.segments.length === 0}
                                <span>&nbsp;</span>
                              {:else}
                                {#each line.segments as segment}
                                  <span
                                    class:diff-replace={segment.type === 'replace'}
                                    class:diff-delete={segment.type === 'delete'}
                                    >{segment.text}</span
                                  >
                                {/each}
                              {/if}
                            </div>
                          </div>
                        {/each}
                      </div>
                    {/if}
                  </div>
                </div>
              {/if}

              <!-- Model Output panel -->
              {#if !isMobile || mobileActivePanel === 'model-output'}
                <div
                  class="flex min-h-0 min-w-0 flex-1 flex-col"
                  style="background: color-mix(in srgb, var(--accent-secondary) 6%, var(--bg-surface));"
                >
                  <div
                    class="flex min-w-0 shrink-0 items-center gap-2 border-b border-[var(--border-card)] px-4 py-2"
                  >
                    <span class="h-2 w-2 rounded-full" style="background: var(--accent-secondary);"
                    ></span>
                    <h3
                      class="text-xs tracking-wider uppercase"
                      style="color: var(--accent-secondary);"
                    >
                      Model Output
                    </h3>
                    {#if isMobile && mobileActivePanel === 'model-output'}
                      {@const selectedGauges = mobileGauges(
                        activeSample.resultsByModel[selectedModel]
                      )}
                      <div
                        class="ml-auto flex min-w-0 flex-1 items-center justify-end gap-1 overflow-hidden"
                      >
                        <span
                          class="min-w-0 truncate text-right font-mono text-[10px] text-stone-600 dark:text-white/70"
                          >{selectedModel}</span
                        >
                        <div class="flex shrink-0 items-center gap-0.5">
                          <CircularGauge
                            value={selectedGauges.quality}
                            label=""
                            color="var(--accent-primary)"
                            size={24}
                            icon={mobileGaugeIcons.quality}
                          />
                          <CircularGauge
                            value={selectedGauges.cost}
                            label=""
                            color="var(--accent-secondary)"
                            size={24}
                            icon={mobileGaugeIcons.cost}
                          />
                          <CircularGauge
                            value={selectedGauges.latency}
                            label=""
                            color="var(--accent-tertiary)"
                            size={24}
                            icon={mobileGaugeIcons.latency}
                          />
                        </div>
                      </div>
                    {:else}
                      <span
                        class="ml-auto truncate font-mono text-[10px] text-stone-600 dark:text-white/70"
                        >{selectedModel}</span
                      >
                    {/if}
                  </div>
                  {#if sampleDetailsLoading}
                    <div
                      class="flex flex-1 items-center justify-center text-sm text-stone-600 dark:text-white/70"
                    >
                      Loading sample text…
                    </div>
                  {:else if sampleDetailsError}
                    <div class="p-4">
                      <div
                        class="rounded-lg border border-amber-400/30 p-3 text-xs text-amber-700 dark:text-amber-200"
                        style="background: rgba(245,158,11,0.08);"
                      >
                        {sampleDetailsError}
                      </div>
                    </div>
                  {:else if activeResult?.error}
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
                      class="min-w-0 flex-1 overflow-auto py-4 pr-4 pl-2 font-[Space_Mono] text-xs leading-relaxed text-stone-600 dark:text-white/70"
                    >
                      <div class="w-max min-w-full">
                        {#each modelOutputLines as line}
                          <div class="grid w-max grid-cols-[1.75rem_auto] items-baseline gap-x-2.5">
                            <span
                              class="w-7 shrink-0 text-right font-mono text-[10px] text-stone-400 dark:text-white/35"
                            >
                              {line.lineNumber}
                            </span>
                            <div class="w-max whitespace-pre">
                              {#if line.segments.length === 0}
                                <span>&nbsp;</span>
                              {:else}
                                {#each line.segments as segment}
                                  <span
                                    class:diff-replace={segment.type === 'replace'}
                                    class:diff-insert={segment.type === 'insert'}
                                    >{segment.text}</span
                                  >
                                {/each}
                              {/if}
                            </div>
                          </div>
                        {/each}
                      </div>
                    </div>
                  {:else}
                    <div
                      class="flex flex-1 items-center justify-center text-sm text-stone-600 dark:text-white/70"
                    >
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
