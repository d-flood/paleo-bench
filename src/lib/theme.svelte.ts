export type ThemePref = 'system' | 'light' | 'dark';

const DARK_QUERY = '(prefers-color-scheme: dark)';

let pref = $state<ThemePref>('system');
let current = $state<'light' | 'dark'>('light');

function apply() {
  current = pref === 'system' ? (matchMedia(DARK_QUERY).matches ? 'dark' : 'light') : pref;
  document.documentElement.classList.toggle('dark', current === 'dark');
}

export const theme = {
  get current() {
    return current;
  },

  get pref() {
    return pref;
  },

  init() {
    const stored = localStorage.getItem('theme');
    pref = stored === 'light' || stored === 'dark' ? stored : 'system';
    apply();
    matchMedia(DARK_QUERY).addEventListener('change', () => {
      if (pref === 'system') apply();
    });
  },

  set(next: ThemePref) {
    pref = next;
    if (next === 'system') localStorage.removeItem('theme');
    else localStorage.setItem('theme', next);
    apply();
  }
};
