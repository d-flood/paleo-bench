<script lang="ts">
  import { page } from '$app/state';

  let { title, description }: { title: string; description: string } = $props();
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:url" content={page.url.href} />
</svelte:head>
