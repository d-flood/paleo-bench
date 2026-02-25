<script lang="ts">
  import CircularGauge from '$lib/components/CircularGauge.svelte';
  import type { CompareResultSummary } from '$lib/types';
  import type { Component } from 'svelte';

  type GaugeValues = {
    quality: number;
    cost: number;
    latency: number;
  };

  type Props = {
    availableModels: string[];
    resultsByModel: Record<string, CompareResultSummary>;
    selectedModel: string;
    onSelect: (model: string) => void;
    gaugesForResult: (result: CompareResultSummary | undefined) => GaugeValues;
    gaugeIcons: {
      quality: Component;
      cost: Component;
      latency: Component;
    };
    gaugeSize?: number;
    modelTextClass?: string;
  };

  const {
    availableModels,
    resultsByModel,
    selectedModel,
    onSelect,
    gaugesForResult,
    gaugeIcons,
    gaugeSize = 24,
    modelTextClass = 'font-mono text-[10px]'
  }: Props = $props();
</script>

{#each availableModels as model}
  {@const result = resultsByModel[model]}
  {@const gauges = gaugesForResult(result)}
  {@const isActive = selectedModel === model}
  <button
    type="button"
    onclick={() => onSelect(model)}
    class="flex w-full cursor-pointer items-center gap-2 border-l-2 px-3 py-2 text-left transition-colors hover:bg-stone-50 dark:hover:bg-[#2c2c31]"
    style:border-left-color={isActive ? 'var(--accent-secondary)' : 'transparent'}
    style:background={isActive
      ? 'color-mix(in srgb, var(--accent-secondary) 10%, transparent)'
      : 'transparent'}
  >
    <span
      class={`min-w-0 flex-1 truncate ${modelTextClass} ${isActive ? 'text-stone-800 dark:text-white/90' : 'text-stone-700 dark:text-white/60'}`}
    >
      {model}
    </span>
    <CircularGauge
      value={gauges.quality}
      label=""
      color="var(--accent-primary)"
      size={gaugeSize}
      icon={gaugeIcons.quality}
    />
    <CircularGauge
      value={gauges.cost}
      label=""
      color="var(--accent-secondary)"
      size={gaugeSize}
      icon={gaugeIcons.cost}
    />
    <CircularGauge
      value={gauges.latency}
      label=""
      color="var(--accent-tertiary)"
      size={gaugeSize}
      icon={gaugeIcons.latency}
    />
  </button>
{/each}
