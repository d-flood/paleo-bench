import devtoolsJson from 'vite-plugin-devtools-json';
import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, type Plugin } from 'vite';

function noCacheResultsJsonInDev(): Plugin {
  return {
    name: 'no-cache-results-json-in-dev',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const requestUrl = (req as { url?: string }).url ?? '';
        if (requestUrl.startsWith('/results.json')) {
          res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate, proxy-revalidate');
          res.setHeader('Pragma', 'no-cache');
          res.setHeader('Expires', '0');
          res.setHeader('Surrogate-Control', 'no-store');
        }
        next();
      });
    }
  };
}

export default defineConfig({
  plugins: [tailwindcss(), sveltekit(), noCacheResultsJsonInDev(), devtoolsJson()]
});
