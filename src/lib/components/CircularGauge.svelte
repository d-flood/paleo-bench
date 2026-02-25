<script lang="ts">
  import { pct } from '$lib/utils';
  import type { Component } from 'svelte';

  let {
    value,
    label,
    color,
    size = 72,
    icon,
    ariaLabel,
    rawValue
  }: {
    value: number;
    label: string;
    color: string;
    size?: number;
    icon?: Component;
    ariaLabel?: string;
    rawValue?: string;
  } = $props();

  const radius = 36;
  const fullAngle = Math.PI * 1.5;
  const fullLength = radius * fullAngle;
  const startAngle = -Math.PI * 0.75;

  let showTooltip = $state(false);

  function arcPath(): string {
    const endAngle = startAngle + fullAngle;
    const x1 = 50 + radius * Math.cos(startAngle);
    const y1 = 50 + radius * Math.sin(startAngle);
    const x2 = 50 + radius * Math.cos(endAngle);
    const y2 = 50 + radius * Math.sin(endAngle);
    return `M ${x1} ${y1} A ${radius} ${radius} 0 1 1 ${x2} ${y2}`;
  }

  function dashOffset(v: number): number {
    const clamped = Math.min(Math.max(v, 0), 1);
    return fullLength * (1 - clamped);
  }

  const arc = arcPath();
  let isSmall = $derived(size <= 36);
  let computedAriaLabel = $derived(ariaLabel ?? `${label}: ${pct(value)}`);

  function handleClick(e: MouseEvent) {
    if (rawValue) {
      e.stopPropagation();
      showTooltip = !showTooltip;
    }
  }

  function handleOutsideClick() {
    showTooltip = false;
  }
</script>

<svelte:window onclick={showTooltip ? handleOutsideClick : undefined} />

<span class="gauge-wrapper" style="position: relative; display: inline-block;">
  <button
    type="button"
    class="gauge-clickable"
    onclick={handleClick}
    style="cursor: {rawValue ? 'pointer' : 'default'}; display: inline-block; background: none; border: none; padding: 0; margin: 0; line-height: 0;"
    aria-label={rawValue ? `${label}: ${rawValue}` : computedAriaLabel}
  >
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      class="gauge-svg"
      style="--gauge-color: {color};"
      role="img"
      aria-label={computedAriaLabel}
    >
      <path
        d={arc}
        fill="none"
        stroke="var(--gauge-track)"
        stroke-width="5"
        stroke-linecap="round"
      />
      <path
        d={arc}
        fill="none"
        stroke={color}
        stroke-width="5"
        stroke-linecap="round"
        stroke-dasharray={fullLength}
        stroke-dashoffset={dashOffset(value)}
        class="gauge-value"
      />

      {#if icon}
        <foreignObject x="10" y="10" width="80" height="80">
          <div
            class="gauge-icon"
            style="display:flex;align-items:center;justify-content:center;width:100%;height:100%;color:{color};"
          >
            {@render iconSlot()}
          </div>
        </foreignObject>
      {/if}

      {#if !isSmall && !icon}
        <text
          x="50"
          y="46"
          text-anchor="middle"
          fill="var(--svg-text)"
          font-size="13"
          font-family="Space Mono"
          font-weight="700"
        >
          {pct(value, 0)}
        </text>
        <text
          x="50"
          y="60"
          text-anchor="middle"
          fill="var(--svg-text-ghost)"
          font-size="7"
          font-family="Space Mono"
        >
          {label.toUpperCase()}
        </text>
      {/if}
    </svg>
  </button>

  {#if showTooltip && rawValue}
    <span class="gauge-tooltip">
      {label}: {rawValue}
    </span>
  {/if}
</span>

{#snippet iconSlot()}
  {#if icon}
    {@const Icon = icon}
    <Icon size={isSmall ? 38 : 32} weight="bold" />
  {/if}
{/snippet}

<style>
  .gauge-value {
    transition: stroke-dashoffset 0.5s ease-out;
  }

  .gauge-tooltip {
    position: absolute;
    bottom: calc(100% + 4px);
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-surface);
    border: 1px solid var(--border-card);
    border-radius: 6px;
    padding: 3px 8px;
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    color: var(--svg-text);
    white-space: nowrap;
    z-index: 10;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
    pointer-events: none;
  }
</style>
