<script lang="ts">
  import './layout.css';
  import favicon from '#lib/assets/favicon.png';
  import { asset, resolve } from '$app/paths';
  import { page } from '$app/state';
  import { theme, type ThemePref } from '#lib/theme.svelte.js';
  import { onMount } from 'svelte';
  import DownloadSimpleIcon from 'phosphor-svelte/lib/DownloadSimpleIcon';
  import GithubLogoIcon from 'phosphor-svelte/lib/GithubLogoIcon';
  import MonitorIcon from 'phosphor-svelte/lib/MonitorIcon';
  import MoonIcon from 'phosphor-svelte/lib/MoonIcon';
  import SunIcon from 'phosphor-svelte/lib/SunIcon';

  let { data, children } = $props();

  const pages = [
    { href: resolve('/'), name: 'Results' },
    { href: resolve('graphs'), name: 'Graphs' },
    { href: resolve('by-folio'), name: 'By folio' },
    { href: resolve('transcriptions'), name: 'Image & transcription' }
  ];

  const summary = $derived(data.summary);
  const runDate = $derived(
    new Date(summary.timestamp).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      timeZone: 'UTC'
    })
  );

  const current = (href: string) =>
    page.url.pathname.replace(/\/$/, '') === href.replace(/\/$/, '');
  const wide = $derived(current(resolve('transcriptions')));

  const CARD_ALT =
    'Paleo Bench: a Greek manuscript transcription marked in red pen, with a circled score';

  const THEMES: { pref: ThemePref; name: string; icon: typeof SunIcon }[] = [
    { pref: 'system', name: 'System', icon: MonitorIcon },
    { pref: 'light', name: 'Light', icon: SunIcon },
    { pref: 'dark', name: 'Dark', icon: MoonIcon }
  ];

  onMount(() => theme.init());
</script>

<svelte:head>
  <link rel="icon" href={favicon} />
  <meta name="author" content="David A. Flood" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Paleo Bench" />
  <meta property="og:image" content={new URL(asset('og.png'), page.url.href).href} />
  <meta property="og:image:type" content="image/png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content={CARD_ALT} />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:image:alt" content={CARD_ALT} />
</svelte:head>

<div class="wrap" class:wide>
  <header class="mast">
    <div class="brand">
      <a class="name" href={resolve('/')}>Paleo Bench</a>
      <p class="desc">
        {summary.models.length} model configurations, {summary.samples.length}
        {summary.groups.join(' and ')} folios
      </p>
      <p class="run">Run {runDate}</p>
    </div>
    <div class="tools">
      <nav class="nav" aria-label="Pages">
        {#each pages as p (p.href)}
          <a href={p.href} aria-current={current(p.href) ? 'page' : undefined}>{p.name}</a>
        {/each}
      </nav>
      <div class="themes" role="group" aria-label="Theme">
        {#each THEMES as t (t.pref)}
          <button
            type="button"
            aria-pressed={theme.pref === t.pref}
            aria-label={t.name}
            title={t.name}
            onclick={() => theme.set(t.pref)}><t.icon size="1.05rem" aria-hidden="true" /></button
          >
        {/each}
      </div>
    </div>
  </header>

  <main>
    {@render children()}
  </main>

  <footer class="pagefoot">
    <ul class="points">
      <li>Score: 100 minus character error rate, rounded down, minimum 0</li>
      <li>Scoring ignores accents, punctuation and capitals</li>
      <li>Every sigma form counts as σ; ϑ, ϐ and similar variants as their usual letters</li>
      <li>ϛ, ȣ and ϗ count as στ, ου and και</li>
      <li>Latin or Cyrillic look-alikes inside Greek words count as Greek</li>
      <li>Means skip failed folios</li>
      <li>Ground truth keeps rubrics on GA L60 and GA L587 but omits a faded one on GA L2010</li>
    </ul>
    <ul class="points">
      <li>Time: summed request time, timeouts included</li>
      <li>Cost: US dollars; OpenRouter figures estimate from listed token prices</li>
    </ul>
    <ul class="points">
      <li>Images: Center for the Study of New Testament Manuscripts (CSNTM)</li>
      <li>
        Data: <a href={asset('results.json')} download
          ><DownloadSimpleIcon class="ico" aria-hidden="true" />results.json</a
        >
      </li>
      <li>By <a href="https://davidaflood.com">David A. Flood</a></li>
      <li>
        Code: <a href="https://github.com/d-flood/paleo-bench"
          ><GithubLogoIcon class="ico" aria-hidden="true" />d-flood/paleo-bench</a
        >
      </li>
    </ul>
  </footer>
</div>

<style>
  .wrap {
    max-width: 1400px;
    margin: 0 auto;
    padding-left: max(16px, env(safe-area-inset-left, 0px));
    padding-right: max(16px, env(safe-area-inset-right, 0px));
    padding-block: 18px 40px;
  }

  .wrap.wide {
    max-width: 1720px;
  }

  .mast {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: flex-end;
    gap: 10px 32px;
    padding-bottom: 12px;
    margin-bottom: 26px;
    border-bottom: 1px solid var(--edge);
  }

  .brand {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 2px 16px;
    min-width: 0;
  }

  .name {
    font-family: var(--f-script);
    font-weight: 700;
    font-size: 1.75rem;
    line-height: 1.1;
    text-decoration: none;
  }

  .desc,
  .run {
    margin: 0;
    color: var(--pencil);
    font-size: 0.98rem;
  }

  .run {
    color: var(--faint);
  }

  .tools {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px 28px;
  }

  .nav {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 22px;
  }

  .nav a {
    text-decoration: none;
    color: var(--pencil);
    font-weight: 500;
    font-size: 1.04rem;
    padding: 4px 0;
  }

  .nav a:hover {
    color: var(--ink);
  }

  .nav a[aria-current='page'] {
    color: var(--ink);
    text-decoration: underline 2px var(--pen);
    text-underline-offset: 7px;
  }

  .pagefoot :global(.ico) {
    margin-right: 0.2em;
  }

  .pagefoot {
    content-visibility: auto;
    contain-intrinsic-size: auto 12rem;
    margin-top: 34px;
    padding-top: 14px;
    border-top: 1px solid var(--edge);
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
    gap: 8px 28px;
    color: var(--pencil);
    font-size: 0.86rem;
  }

  .themes {
    display: flex;
    border: 1px solid var(--edge);
    border-radius: 3px;
    overflow: hidden;
    background: var(--paper);
  }

  .themes button {
    display: grid;
    place-items: center;
    padding: 0.3rem 0.5rem;
    border: 0;
    border-left: 1px solid var(--edge);
    background: none;
    font-size: 0.86rem;
    color: var(--pencil);
    cursor: pointer;
  }

  .themes button:first-child {
    border-left: 0;
  }

  .themes button[aria-pressed='true'] {
    background: var(--ink);
    color: var(--paper);
  }

  @media (max-width: 760px) {
    .mast {
      margin-bottom: 18px;
    }
  }
</style>
