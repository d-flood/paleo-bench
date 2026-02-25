<script lang="ts">
  import { pct } from '$lib/utils';

  let {
    value,
    label,
    color,
    size = 72
  }: { value: number; label: string; color: string; size?: number } = $props();

  const radius = 36;
  const fullAngle = Math.PI * 1.5;
  const fullLength = radius * fullAngle;
  const startAngle = -Math.PI * 0.75;

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
</script>

<svg
  viewBox="0 0 100 100"
  width={size}
  height={size}
  class="gauge-svg"
  style="--gauge-color: {color};"
>
  <path d={arc} fill="none" stroke="var(--gauge-track)" stroke-width="5" stroke-linecap="round" />
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
</svg>

<style>
  .gauge-value {
    transition: stroke-dashoffset 0.5s ease-out;
  }
</style>
