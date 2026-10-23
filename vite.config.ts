import adapter from '@sveltejs/adapter-static';
import devtoolsJson from 'vite-plugin-devtools-json';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

const base = (process.env.BASE_PATH ?? '') as '' | `/${string}`;
const selectionRoutes = ['/transcriptions', '/graphs'].map((route) => `${base}${route}`);

export default defineConfig({
  plugins: [
    sveltekit({
      adapter: adapter(),
      paths: { base },
      prerender: {
        handleMissingId: ({ path, message }) => {
          if (!selectionRoutes.includes(path)) throw new Error(message);
        }
      }
    }),
    devtoolsJson()
  ],
  server: {
    host: true,
    allowedHosts: ['df-laptop-lx']
  }
});
