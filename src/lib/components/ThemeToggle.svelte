<script lang="ts">
	import { theme } from '$lib/theme.svelte';
</script>

<button
	onclick={() => theme.toggle()}
	class="group relative flex h-8 w-[60px] items-center rounded-full border border-stone-300 bg-stone-200 p-0.5 transition-colors dark:border-white/10 dark:bg-white/10"
	aria-label="Toggle theme"
>
	<!-- Thumb -->
	<span
		class="flex h-6 w-6 items-center justify-center rounded-full bg-white shadow-sm transition-transform duration-200 dark:translate-x-7 dark:bg-stone-800"
	>
		{#if theme.current === 'dark'}
			<!-- Moon -->
			<svg class="h-3.5 w-3.5 text-amber-300" fill="currentColor" viewBox="0 0 20 20">
				<path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
			</svg>
		{:else}
			<!-- Sun -->
			<svg class="h-3.5 w-3.5 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
				<path
					fill-rule="evenodd"
					d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
					clip-rule="evenodd"
				/>
			</svg>
		{/if}
	</span>
</button>
