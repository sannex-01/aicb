import { state, applyTheme } from './state.js';
import { api } from './api.js';
import { navigate } from './router.js';
import { showToast, escapeHtml } from './utils.js';

// Import Pages
import { renderLoginView } from './pages/login.js';
import { renderForgotPasswordView } from './pages/forgot-password.js';
import { renderResetPasswordView } from './pages/reset-password.js';
import { renderSetupView } from './pages/setup.js';
import { loadOverviewPage } from './pages/overview.js';
import { loadAgentsPage } from './pages/agents.js';
import { loadCustomersPage } from './pages/customers.js';
import { loadSettingsPage } from './pages/settings.js';
import { loadGroupsPage } from './pages/groups.js';
import { loadKnowledgePage } from './pages/knowledge.js';
import { loadCatalogPage } from './pages/catalog.js';
import { loadUsersPage } from './pages/users.js';
import { loadOrdersPage } from './pages/orders.js';
import { loadConversationsPage } from './pages/conversations.js';

export function updateAppTitle(bizName) {
  const name = bizName || state.business?.name || state.user?.business?.name;
  document.title = name ? `${name} — Management Portal` : 'AICB Admin — Multi-Agent Studio';
}

window.updateAppTitle = updateAppTitle;

export async function initApp() {
  const urlParams = new URLSearchParams(window.location.search);
  const ssoToken = urlParams.get('token');
  if (state.route === '/_/admin/sso' && ssoToken) {
    try {
      const res = await fetch('/api/v1/auth/sso', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: ssoToken })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'SSO failed');
      
      localStorage.setItem('aicb_admin_token', data.access_token);
      showToast('Logged in via AgentOS', 'success');
      navigate('/_/admin/overview');
      return;
    } catch (err) {
      showToast('SSO Login Failed: ' + err.message, 'error');
      navigate('/_/admin/login');
      return;
    }
  }

  try {
    const sys = await api('/system/version');
    if (sys?.version) {
      state.appVersion = sys.version;
      state.appName = sys.name || 'AICB Assistant';
      state.support = sys.support || null;
    }
  } catch (e) {}

  try {
    const status = await api('/setup/status');
    if (status.business?.name) {
      updateAppTitle(status.business.name);
      state.business = status.business;
    }
    if (!status.initialized) {
      if (state.route !== '/_/admin/setup') {
        navigate('/_/admin/setup');
        return;
      }
    }
  } catch (e) {
    console.error("Setup check error:", e);
  }

  const storedToken = localStorage.getItem('aicb_admin_token');
  if (storedToken) {
    try {
      const authData = await api('/auth/me');
      state.user = authData;
      state.business = authData.business;
      if (authData.business?.name) updateAppTitle(authData.business.name);
    } catch {
      localStorage.removeItem('aicb_admin_token');
      state.user = null;
      state.business = null;
    }
  }

  const publicRoutes = ['/_/admin/setup', '/_/admin/login', '/_/admin/forgot-password', '/_/admin/reset-password'];
  if (!state.user && !publicRoutes.includes(state.route)) {
    navigate('/_/admin/login');
    return;
  }

  renderApp();
}

export function renderApp() {
  const app = document.getElementById('app');
  const path = state.route.replace(/\/$/, '') || '/_/admin/overview';

  if (path === '/_/admin/setup') {
    renderSetupView(app);
  } else if (path === '/_/admin/login') {
    renderLoginView(app);
  } else if (path === '/_/admin/forgot-password') {
    renderForgotPasswordView(app);
  } else if (path === '/_/admin/reset-password') {
    renderResetPasswordView(app);
  } else {
    renderAdminShell(app, path);
  }

  if (window.lucide) lucide.createIcons();
}

function updateThemeUI(theme) {
  const lightBtn = document.getElementById('header-theme-btn-light');
  const darkBtn = document.getElementById('header-theme-btn-dark');
  if (lightBtn && darkBtn) {
    if (theme === 'light') {
      lightBtn.className = 'p-1.5 rounded-md transition-colors bg-surface text-brand font-semibold shadow-xs';
      darkBtn.className = 'p-1.5 rounded-md transition-colors text-muted hover:text-main';
    } else {
      lightBtn.className = 'p-1.5 rounded-md transition-colors text-muted hover:text-main';
      darkBtn.className = 'p-1.5 rounded-md transition-colors bg-surface text-brand font-semibold shadow-xs';
    }
  }
}

function renderAdminShell(container, currentPath) {
  const user = state.user || {};
  const isAdmin = ['admin', 'super_admin'].includes(user.role);

  // Route protection: redirect unauthorized roles away from admin-only pages
  if ((currentPath === '/_/admin/users' || currentPath === '/_/admin/settings') && !isAdmin) {
    showToast('Access restricted to administrators.', 'warning');
    navigate('/_/admin/overview');
    return;
  }

  const allNavItems = [
    { label: 'Overview', path: '/_/admin/overview', icon: 'layout-dashboard' },
    { label: 'Conversations', path: '/_/admin/conversations', icon: 'message-square' },
    { label: 'Orders & Payments', path: '/_/admin/orders', icon: 'shopping-cart' },
    { label: 'AI Agents Studio', path: '/_/admin/agents', icon: 'bot' },
    { label: 'Access Groups', path: '/_/admin/groups', icon: 'shield-check' },
    { label: 'Customers', path: '/_/admin/customers', icon: 'users' },
    { label: 'Products Catalog', path: '/_/admin/catalog', icon: 'shopping-bag' },
    { label: 'Knowledge Base', path: '/_/admin/knowledge', icon: 'book-open' },
    { label: 'Team Accounts', path: '/_/admin/users', icon: 'user-check', adminOnly: true },
    { label: 'Settings', path: '/_/admin/settings', icon: 'settings', adminOnly: true },
  ];

  const navItems = allNavItems.filter(item => !item.adminOnly || isAdmin);

  const business = state.business || state.user?.business || {};
  const businessName = business.name || 'AICB Studio';
  const logoUrl = business.logo_url;
  const initial = (businessName.trim().charAt(0) || 'A').toUpperCase();

  const logoMarkup = logoUrl ? `
    <div class="w-8 h-8 rounded-lg bg-surface-elevated border border-subtle flex items-center justify-center overflow-hidden flex-shrink-0 shadow-sm">
      <img src="${escapeHtml(logoUrl)}" class="w-full h-full object-cover" onerror="this.parentElement.innerHTML='<div class=\\'w-8 h-8 rounded-lg bg-brand flex items-center justify-center text-white font-bold text-sm\\'>${escapeHtml(initial)}</div>';" />
    </div>
  ` : `
    <div class="w-8 h-8 rounded-lg bg-brand flex items-center justify-center text-white font-bold text-sm flex-shrink-0 shadow-sm">
      ${escapeHtml(initial)}
    </div>
  `;

  const roleBadgeClass = isAdmin 
    ? 'badge-emerald' 
    : user.role === 'operator' 
      ? 'badge-sky' 
      : 'badge-subtle';

  container.innerHTML = `
    <div class="flex h-screen bg-app overflow-hidden text-[13px]">
      <!-- Sidebar -->
      <aside class="${state.sidebarCollapsed ? 'w-16' : 'w-60'} bg-sidebar border-r border-subtle flex flex-col flex-shrink-0 z-20 relative transition-all duration-200">

        <!-- Business Identity Card -->
        <div class="p-3.5 border-b border-subtle flex items-center ${state.sidebarCollapsed ? 'justify-center' : 'gap-2.5'}">
          <div id="sidebar-logo-container" class="flex-shrink-0">
            ${logoMarkup}
          </div>
          ${!state.sidebarCollapsed ? `
          <div class="min-w-0 flex-1">
            <p class="font-bold text-xs text-main truncate">AICB Studio</p>
            <div class="flex items-center gap-1 mt-0.5">
              <span class="w-1.5 h-1.5 rounded-full bg-brand flex-shrink-0 animate-pulse"></span>
              <p class="text-[10px] text-muted truncate" id="sidebar-business-name">${escapeHtml(businessName)}</p>
            </div>
          </div>
          ` : ''}
        </div>

        <div class="flex-1 overflow-y-auto py-3 px-2">
          ${!state.sidebarCollapsed ? `<div class="px-2.5 pb-1.5 text-[10px] font-bold text-faint uppercase tracking-wider">Workspace Tools</div>` : ''}
          <nav class="flex flex-col gap-0.5 mt-1">
            ${navItems.map(item => `
              <a href="${item.path}" class="flex items-center ${state.sidebarCollapsed ? 'justify-center' : 'gap-2.5'} px-2.5 py-2 rounded-md text-[13px] font-medium transition-colors group ${currentPath === item.path ? 'bg-brand/10 text-brand font-semibold' : 'text-muted hover:bg-surface-hover hover:text-main'}" onclick="event.preventDefault(); navigate('${item.path}')" title="${item.label}">
                <i data-lucide="${item.icon}" class="w-4 h-4 flex-shrink-0 ${currentPath === item.path ? 'text-brand' : 'text-faint group-hover:text-main transition-colors'}"></i>
                ${!state.sidebarCollapsed ? `<span class="truncate">${item.label}</span>` : ''}
              </a>
            `).join('')}
          </nav>
        </div>

        <div class="p-3 border-t border-subtle flex flex-col gap-2">
          ${!state.sidebarCollapsed ? `
          <!-- Support Open-Source Project Button -->
          <button type="button" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium text-pink-600 dark:text-pink-400 hover:text-pink-700 hover:bg-pink-500/10 border border-pink-500/15 dark:border-pink-500/20 bg-pink-500/5 transition-all group cursor-pointer" onclick="window.openSupportModal()" title="Support & Sponsor Open-Source AICB">
            <div class="flex items-center gap-2 min-w-0">
              <i data-lucide="heart" class="w-3.5 h-3.5 text-pink-500 flex-shrink-0 group-hover:scale-110 transition-transform fill-pink-500/20"></i>
              <span class="truncate text-xs font-semibold">Support AICB</span>
            </div>
            <span class="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-pink-500/10 text-pink-600 dark:text-pink-400 border border-pink-500/20">
              Sponsor
            </span>
          </button>

          <!-- Releases Section & Current App Version -->
          <button type="button" id="sidebar-releases-btn" class="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium text-muted hover:text-main hover:bg-surface-hover border border-subtle/50 dark:border-white/5 bg-surface/50 dark:bg-white/[0.02] transition-all group cursor-pointer" onclick="window.openReleasesModal()" title="View AICB Platform Releases & Changelog">
            <div class="flex items-center gap-2 min-w-0">
              <i data-lucide="rocket" class="w-3.5 h-3.5 text-brand flex-shrink-0 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-transform"></i>
              <span class="truncate text-xs font-medium">Releases</span>
            </div>
            <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-brand/10 text-brand border border-brand/20">
              v${escapeHtml(state.appVersion || '0.2.1')}
            </span>
          </button>
          ` : ''}

          <!-- User Identity Card -->
          <div class="flex items-center ${state.sidebarCollapsed ? 'justify-center flex-col pt-1' : 'gap-2.5 pt-1'}">
            <div class="w-7 h-7 rounded-full bg-brand/10 border border-brand/20 flex items-center justify-center text-brand font-bold text-xs flex-shrink-0">
              ${escapeHtml(user.name?.charAt(0) || 'U')}
            </div>
            ${!state.sidebarCollapsed ? `
            <div class="flex-1 min-w-0">
              <div class="text-xs font-bold truncate text-main leading-none mb-1">${escapeHtml(user.name || 'User')}</div>
              <div class="flex items-center gap-1">
                <span class="badge ${roleBadgeClass} text-[9px] px-1.5 py-0 uppercase font-bold tracking-wider">
                  ${escapeHtml(user.role || 'operator')}
                </span>
              </div>
            </div>
            ` : ''}
            <button class="text-faint hover:text-rose transition-colors p-1 hover:bg-rose/10 rounded-md ${state.sidebarCollapsed ? 'mt-1' : ''}" onclick="window.logout()" title="Logout">
              <i data-lucide="log-out" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      </aside>

      <!-- Main Content -->
      <main class="flex-1 flex flex-col min-w-0 bg-app relative">
        <header class="h-14 flex-shrink-0 bg-surface border-b border-subtle flex items-center justify-between px-6 sticky top-0 z-10">
          <div class="flex items-center gap-3">
            <button class="text-faint hover:text-main transition-colors p-1" onclick="window.toggleSidebar()" title="Toggle Sidebar">
              <i data-lucide="menu" class="w-4.5 h-4.5"></i>
            </button>
            <h2 class="text-[15px] font-semibold tracking-tight text-main">${allNavItems.find(i => i.path === currentPath)?.label || 'Dashboard'}</h2>
          </div>
          <div class="flex items-center gap-3">
            <!-- Header Theme Toggle -->
            <div class="flex items-center bg-app p-0.5 rounded-lg border border-subtle">
              <button type="button" id="header-theme-btn-light" class="p-1.5 rounded-md transition-colors ${state.theme === 'light' ? 'bg-surface text-brand font-semibold shadow-xs' : 'text-muted hover:text-main'}" onclick="window.setTheme('light')" title="Light Mode">
                <i data-lucide="sun" class="w-4 h-4 pointer-events-none"></i>
              </button>
              <button type="button" id="header-theme-btn-dark" class="p-1.5 rounded-md transition-colors ${state.theme === 'dark' ? 'bg-surface text-brand font-semibold shadow-xs' : 'text-muted hover:text-main'}" onclick="window.setTheme('dark')" title="Dark Mode">
                <i data-lucide="moon" class="w-4 h-4 pointer-events-none"></i>
              </button>
            </div>
            <div class="h-4 w-px bg-subtle"></div>
            <span class="badge badge-emerald">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span> LIVE
            </span>
          </div>
        </header>

        <div id="page-content" class="p-6 max-w-[1600px] mx-auto w-full flex-1 overflow-y-auto"></div>
      </main>
    </div>
  `;

  // Attach global shell handlers so inline onclicks work
  window.navigate = navigate;
  window.setTheme = function(t) {
    applyTheme(t);
    updateThemeUI(t);
  };
  window.toggleTheme = function() {
    const next = state.theme === 'light' ? 'dark' : 'light';
    window.setTheme(next);
  };
  window.updateSidebarBrand = function() {
    const b = state.business || state.user?.business || {};
    const bName = b.name || 'AICB Studio';
    const bLogo = b.logo_url;
    const bInit = (bName.trim().charAt(0) || 'A').toUpperCase();

    const logoContainer = document.getElementById('sidebar-logo-container');
    if (logoContainer) {
      logoContainer.innerHTML = bLogo ? `
        <div class="w-8 h-8 rounded-lg bg-surface-elevated border border-subtle flex items-center justify-center overflow-hidden flex-shrink-0 shadow-sm">
          <img src="${escapeHtml(bLogo)}" class="w-full h-full object-cover" onerror="this.parentElement.innerHTML='<div class=\\'w-8 h-8 rounded-lg bg-brand flex items-center justify-center text-white font-bold text-sm\\'>${escapeHtml(bInit)}</div>';" />
        </div>
      ` : `
        <div class="w-8 h-8 rounded-lg bg-brand flex items-center justify-center text-white font-bold text-sm flex-shrink-0 shadow-sm">
          ${escapeHtml(bInit)}
        </div>
      `;
    }
    const nameEl = document.getElementById('sidebar-business-name');
    if (nameEl) nameEl.textContent = bName;
  };
  window.toggleSidebar = function() {
    state.sidebarCollapsed = !state.sidebarCollapsed;
    localStorage.setItem('aicb_sidebar_collapsed', String(state.sidebarCollapsed));
    renderAdminShell(container, currentPath);
  };
  window.logout = async function() {
    try { await api('/auth/logout', { method: 'POST' }); } catch {}
    localStorage.removeItem('aicb_admin_token');
    state.user = null;
    state.business = null;
    navigate('/_/admin/login');
  };

  // Support / Sponsor Modal Handler
  window.openSupportModal = async function() {
    let existingModal = document.getElementById('support-modal');
    if (existingModal) existingModal.remove();

    // Fetch latest support config if not present
    let support = state.support;
    if (!support) {
      try {
        support = await api('/system/support');
        state.support = support;
      } catch (e) {}
    }

    const title = support?.title || 'Support Open-Source AICB';
    const message = support?.message || 'AICB is 100% free and open source. If AICB powers your business or projects, consider supporting ongoing development, documentation, and maintenance.';
    const supportUrl = support?.url || 'https://github.com/sponsors/sannex';

    const modal = document.createElement('div');
    modal.id = 'support-modal';
    modal.className = 'fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in';
    modal.innerHTML = `
      <div class="bg-surface border border-subtle rounded-2xl shadow-2xl max-w-lg w-full flex flex-col overflow-hidden animate-scale-in">
        <div class="p-5 border-b border-subtle flex items-center justify-between bg-surface-elevated">
          <div class="flex items-center gap-2.5">
            <div class="w-10 h-10 rounded-xl bg-pink-500/10 border border-pink-500/20 flex items-center justify-center text-pink-500 flex-shrink-0">
              <i data-lucide="heart" class="w-5 h-5 fill-pink-500/20"></i>
            </div>
            <div>
              <h3 class="font-bold text-base text-main">${escapeHtml(title)}</h3>
              <p class="text-xs text-muted">Community & Open Source Sponsorship</p>
            </div>
          </div>
          <button class="text-muted hover:text-main p-1.5 rounded-lg hover:bg-surface transition-colors cursor-pointer" onclick="document.getElementById('support-modal')?.remove()" title="Close">
            <i data-lucide="x" class="w-5 h-5"></i>
          </button>
        </div>

        <div class="p-6 space-y-4">
          <div class="p-4 rounded-xl border border-subtle bg-surface-elevated flex items-start gap-3">
            <i data-lucide="sparkles" class="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5"></i>
            <p class="text-xs text-main leading-relaxed">${escapeHtml(message)}</p>
          </div>

          <div class="space-y-2 text-xs text-muted">
            <div class="flex items-center gap-2">
              <i data-lucide="check" class="w-4 h-4 text-emerald-500 flex-shrink-0"></i>
              <span>Directly backs open-source feature development</span>
            </div>
            <div class="flex items-center gap-2">
              <i data-lucide="check" class="w-4 h-4 text-emerald-500 flex-shrink-0"></i>
              <span>Keeps AgentOS Documentation & Releases freely accessible</span>
            </div>
            <div class="flex items-center gap-2">
              <i data-lucide="check" class="w-4 h-4 text-emerald-500 flex-shrink-0"></i>
              <span>100% self-hosted freedom with zero artificial tier locks</span>
            </div>
          </div>
        </div>

        <div class="p-4 border-t border-subtle bg-surface-elevated flex items-center justify-between gap-3">
          <button type="button" class="btn btn-secondary text-xs" onclick="document.getElementById('support-modal')?.remove()">
            Maybe Later
          </button>
          <a href="${escapeHtml(supportUrl)}" target="_blank" rel="noopener noreferrer" class="btn btn-primary text-xs flex items-center gap-1.5 bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-700 hover:to-rose-700 text-white font-semibold shadow-sm" onclick="document.getElementById('support-modal')?.remove()">
            <i data-lucide="heart" class="w-3.5 h-3.5 fill-white"></i>
            <span>Sponsor on GitHub</span>
            <i data-lucide="external-link" class="w-3 h-3 opacity-80"></i>
          </a>
        </div>
      </div>
    `;

    document.body.appendChild(modal);
    if (window.lucide) lucide.createIcons();
  };

  // Releases Offcanvas Handlers
  window.openReleasesModal = async function() {
    let existingModal = document.getElementById('releases-offcanvas-backdrop');
    if (existingModal) {
      existingModal.remove();
      return;
    }

    const backdrop = document.createElement('div');
    backdrop.id = 'releases-offcanvas-backdrop';
    backdrop.className = 'fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]';
    backdrop.onclick = (e) => {
      if (e.target === backdrop) backdrop.remove();
    };

    const sidebarWidthClass = state.sidebarCollapsed ? 'left-20' : 'left-[248px]';

    backdrop.innerHTML = `
      <div class="fixed bottom-3 ${sidebarWidthClass} z-50 w-[390px] max-w-[calc(100vw-18rem)] max-h-[74vh] flex flex-col bg-surface border border-subtle dark:border-white/10 rounded-2xl shadow-2xl overflow-hidden animate-scale-in" onclick="event.stopPropagation()">
        <div class="p-4 border-b border-subtle flex items-center justify-between bg-surface-elevated/80">
          <div class="flex items-center gap-2.5 min-w-0">
            <div class="w-8 h-8 rounded-xl bg-brand/10 border border-brand/20 flex items-center justify-center text-brand flex-shrink-0">
              <i data-lucide="rocket" class="w-4 h-4"></i>
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <h3 class="font-bold text-sm text-main truncate">AICB Releases</h3>
                <span class="badge badge-emerald text-[9px] font-mono px-1.5 py-0.2">v${escapeHtml(state.appVersion || '0.2.1')}</span>
              </div>
              <p class="text-[11px] text-muted truncate">Synchronized from AgentOS</p>
            </div>
          </div>
          <button class="text-muted hover:text-main p-1 rounded-lg hover:bg-surface transition-colors cursor-pointer" onclick="document.getElementById('releases-offcanvas-backdrop')?.remove()" title="Close">
            <i data-lucide="x" class="w-4 h-4"></i>
          </button>
        </div>

        <div id="releases-modal-content" class="p-4 overflow-y-auto space-y-3 flex-1">
          <div class="flex items-center justify-center py-8">
            <div class="animate-spin w-5 h-5 border-2 border-brand border-t-transparent rounded-full"></div>
          </div>
        </div>

        <div class="p-3 border-t border-subtle bg-surface-elevated/80 flex items-center justify-between gap-2">
          <button type="button" id="releases-sync-btn" class="btn btn-secondary text-xs flex items-center gap-1.5 py-1.5" onclick="window.syncReleasesFromModal()">
            <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
            <span>Check Updates</span>
          </button>
          <button type="button" class="btn btn-primary text-xs py-1.5 px-3" onclick="document.getElementById('releases-offcanvas-backdrop')?.remove()">
            Close
          </button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    if (window.lucide) lucide.createIcons();

    await window.loadReleasesModalContent();
  };

  window.loadReleasesModalContent = async function() {
    const container = document.getElementById('releases-modal-content');
    if (!container) return;

    try {
      const releases = await api('/system/releases');
      if (!releases || releases.length === 0) {
        container.innerHTML = `
          <div class="text-center py-8 text-muted">
            <i data-lucide="info" class="w-8 h-8 mx-auto text-subtle mb-2"></i>
            <p class="font-medium text-sm text-main">No release notes available</p>
            <p class="text-xs">Click "Check for Updates" to sync release notes from AgentOS.</p>
          </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
      }

      const agentosHost = 'https://agentos.aicb.sannex.ng';
      container.innerHTML = releases.map((rel, idx) => `
        <a href="${escapeHtml(rel.download_url || `${agentosHost}/releases`)}" target="_blank" rel="noopener noreferrer" class="block p-3 rounded-xl border border-subtle dark:border-white/5 bg-surface-elevated/40 hover:bg-surface-elevated hover:border-brand/30 transition-all group">
          <div class="flex items-center justify-between gap-2 mb-1">
            <div class="flex items-center gap-2 min-w-0">
              <span class="badge ${idx === 0 ? 'badge-emerald' : 'badge-subtle'} font-mono font-bold text-xs px-2 py-0.5">
                v${escapeHtml(rel.version)}
              </span>
              <h4 class="font-bold text-xs text-main truncate group-hover:text-brand transition-colors">${escapeHtml(rel.title || 'Update')}</h4>
              ${rel.is_critical ? '<span class="badge badge-rose text-[9px] font-bold uppercase">Critical</span>' : ''}
            </div>
            <i data-lucide="external-link" class="w-3.5 h-3.5 text-muted group-hover:text-brand transition-colors flex-shrink-0"></i>
          </div>
          ${rel.description ? `<p class="text-[11px] text-muted line-clamp-2 leading-relaxed mt-1">${escapeHtml(rel.description)}</p>` : ''}
          <div class="flex items-center justify-between text-[10px] text-faint mt-2 pt-1.5 border-t border-subtle/40">
            <span>${rel.release_date ? escapeHtml(rel.release_date) : 'Official Release'}</span>
            <span class="text-brand flex items-center gap-0.5 font-medium">Read on AgentOS &rarr;</span>
          </div>
        </a>
      `).join('');

      if (window.lucide) lucide.createIcons();
    } catch (e) {
      container.innerHTML = `
        <div class="p-3.5 rounded-xl bg-rose/10 border border-rose/20 text-rose text-xs">
          Failed to load release notes: ${escapeHtml(e.message || 'Network error')}
        </div>
      `;
    }
  };

  window.syncReleasesFromModal = async function() {
    const btn = document.getElementById('releases-sync-btn');
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> Checking...`;
      if (window.lucide) lucide.createIcons();
    }

    try {
      const res = await api('/system/releases/sync', { method: 'POST' });
      showToast('Release notes synchronized successfully.', 'success');
      await window.loadReleasesModalContent();
    } catch (e) {
      showToast('Sync failed: ' + (e.message || 'Could not reach AgentOS'), 'error');
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i> Check for Updates`;
        if (window.lucide) lucide.createIcons();
      }
    }
  };

  const pageContainer = document.getElementById('page-content');
  
  if (currentPath === '/_/admin/overview') loadOverviewPage(pageContainer);
  else if (currentPath === '/_/admin/conversations') loadConversationsPage(pageContainer);
  else if (currentPath === '/_/admin/orders') loadOrdersPage(pageContainer);
  else if (currentPath === '/_/admin/agents') loadAgentsPage(pageContainer);
  else if (currentPath === '/_/admin/groups') loadGroupsPage(pageContainer);
  else if (currentPath === '/_/admin/customers') loadCustomersPage(pageContainer);
  else if (currentPath === '/_/admin/catalog') loadCatalogPage(pageContainer);
  else if (currentPath === '/_/admin/knowledge') loadKnowledgePage(pageContainer);
  else if (currentPath === '/_/admin/users') loadUsersPage(pageContainer);
  else if (currentPath === '/_/admin/settings') loadSettingsPage(pageContainer);

  if (window.lucide) lucide.createIcons();
}

// Start SPA on Load
document.addEventListener('DOMContentLoaded', initApp);

