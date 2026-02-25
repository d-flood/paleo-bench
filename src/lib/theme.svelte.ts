let current = $state<'light' | 'dark'>('light');

export const theme = {
  get current() {
    return current;
  },

  init() {
    current = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
  },

  toggle() {
    current = current === 'dark' ? 'light' : 'dark';
    document.documentElement.classList.toggle('dark', current === 'dark');
    localStorage.setItem('theme', current);
  }
};
