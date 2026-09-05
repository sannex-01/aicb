// State Management
export const state = {
  user: null,
  business: null,
  apiKeyInfo: null,
  appVersion: '0.2.1',
  appName: 'AICB Assistant',
  support: null,
  route: window.location.pathname || '/_/admin/overview',
  theme: localStorage.getItem('aicb_theme') || 'light',
  sidebarCollapsed: localStorage.getItem('aicb_sidebar_collapsed') === 'true',
};

// Apply Theme
export function applyTheme(theme) {
  state.theme = theme;
  localStorage.setItem('aicb_theme', theme);
  document.documentElement.className = theme;
}

// Initial theme application
applyTheme(state.theme);
