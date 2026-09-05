import { state } from './state.js';
import { renderApp } from './main.js';

// Router
export function navigate(path) {
  window.history.pushState({}, '', path);
  state.route = path;
  renderApp();
}

window.navigate = navigate;

// Intercept popstate for browser back/forward buttons
window.addEventListener('popstate', () => {
  state.route = window.location.pathname;
  renderApp();
});
