<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.png';
	import { theme } from '$lib/theme.svelte';
	import { onMount } from 'svelte';

	let { children } = $props();

	onMount(() => {
		theme.init();
	});
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
{@render children()}
