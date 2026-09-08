import { state } from '../state.js';
import { api } from '../api.js';
import { showToast, openModal, closeModal, openConfirmModal, escapeHtml, formatDate, skeletonPage, renderImageUploadField, initImageUploadControl, initAllCustomSelects, initPasswordToggles, renderPasswordStrengthMarkup, bindPasswordValidator } from '../utils.js';

// Business Profile, Change Password, and Platform API Key only — messaging
// channels, payment gateways, email delivery, storage, store connections
// and order alerts all moved to pages/integrations.js (see "Integrations"
// in the CONFIGURATION nav section).

export async function loadSettingsPage(container) {
  if (!['admin', 'super_admin'].includes(state.user?.role)) {
    container.innerHTML = `
      <div class="card text-center p-12 space-y-4 max-w-lg mx-auto mt-12">
        <div class="w-12 h-12 rounded-full bg-rose/10 text-rose flex items-center justify-center mx-auto">
          <i data-lucide="shield-alert" class="w-6 h-6"></i>
        </div>
        <div>
          <h3 class="font-bold text-lg text-main">Administrator Access Required</h3>
          <p class="text-xs text-muted mt-1">Business settings and platform API keys can only be managed by team administrators.</p>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="navigate('/_/admin/overview')">Back to Overview</button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = skeletonPage({ stats: 0, rows: 4 });
  try {
    const [biz, keyInfo, paymentInfo] = await Promise.all([
      api('/settings/profile'),
      api('/settings/api-key'),
      api('/settings/payments').catch(() => ({ provider: null, configured: false, config: {}, available_currencies: [] })),
    ]);
    state.business = biz;
    state.apiKeyInfo = keyInfo;
    state.paymentInfo = paymentInfo;

    const tabs = [
      { id: 'profile', label: 'Business Profile', icon: 'store' },
      { id: 'password', label: 'Change Password', icon: 'key' },
      { id: 'api-key', label: 'Platform API Key', icon: 'shield' },
    ];
    const activeTab = state.settingsTab && tabs.some(t => t.id === state.settingsTab) ? state.settingsTab : 'profile';

    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 class="text-2xl font-bold">Settings</h1>
            <p class="text-sm text-muted">Manage your business identity, account password & platform API key</p>
          </div>
          <button class="btn btn-secondary flex items-center gap-2" onclick="window.toggleTheme()" title="Switch Theme">
            <i data-lucide="${state.theme === 'dark' ? 'sun' : 'moon'}" class="w-4 h-4 text-brand"></i>
            <span>${state.theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
          </button>
        </div>

        <div class="flex flex-col md:flex-row gap-6 items-start">
          <!-- Left Tabs (Settings Sidebar 14px font size) -->
          <nav class="w-full md:w-60 flex-shrink-0 flex flex-row md:flex-col gap-1 p-1.5 bg-surface rounded-xl border border-subtle">
            ${tabs.map(t => `
              <button class="settings-tab flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg text-[14px] font-medium text-left transition-colors ${activeTab === t.id ? 'bg-brand/10 text-brand font-semibold' : 'text-muted hover:bg-surface-hover hover:text-main'}" data-tab="${t.id}">
                <i data-lucide="${t.icon}" class="w-4 h-4 flex-shrink-0"></i>
                <span>${t.label}</span>
              </button>
            `).join('')}
          </nav>

          <!-- Right Content -->
          <div class="flex-1 min-w-0 w-full" id="settings-tab-content"></div>
        </div>
      </div>
    `;

    function renderProfileTab() {
      const el = document.getElementById('settings-tab-content');
      el.innerHTML = `
        <div class="card space-y-6">
          <div>
            <h3 class="font-bold text-base text-main">Business Profile</h3>
            <p class="text-xs text-muted mt-0.5">Customize your brand identity, store currency, and contact info</p>
          </div>

          <form id="business-settings-form" class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div class="form-group col-span-2 sm:col-span-1">
                <label class="form-label">Store / Business Name</label>
                <input type="text" id="biz-name" class="form-control" required value="${escapeHtml(biz.name || '')}" placeholder="Acme Store" />
              </div>
              <div class="form-group col-span-2 sm:col-span-1">
                <label class="form-label flex items-center justify-between">
                  <span>Default Currency</span>
                  ${state.paymentInfo?.configured ? '<span class="text-[12px] text-emerald-600 font-mono">Synced from Payment Gateway</span>' : ''}
                </label>
                <select id="biz-curr" class="form-control">
                  ${(() => {
                    const availableCurrencies = state.paymentInfo?.available_currencies && state.paymentInfo.available_currencies.length
                      ? state.paymentInfo.available_currencies
                      : [
                          { code: 'NGN', symbol: '₦', name: 'Nigerian Naira', label: 'NGN (₦) - Nigerian Naira' },
                          { code: 'USD', symbol: '$', name: 'US Dollar', label: 'USD ($) - US Dollar' },
                          { code: 'GHS', symbol: 'GH₵', name: 'Ghanaian Cedi', label: 'GHS (GH₵) - Ghanaian Cedi' },
                          { code: 'KES', symbol: 'KSh', name: 'Kenyan Shilling', label: 'KES (KSh) - Kenyan Shilling' },
                          { code: 'ZAR', symbol: 'R', name: 'South African Rand', label: 'ZAR (R) - South African Rand' },
                          { code: 'EUR', symbol: '€', name: 'Euro', label: 'EUR (€) - Euro' },
                          { code: 'GBP', symbol: '£', name: 'British Pound', label: 'GBP (£) - British Pound' },
                        ];
                    const hasCurrent = availableCurrencies.some(c => c.code === biz.currency);
                    const list = hasCurrent
                      ? availableCurrencies
                      : [{ code: biz.currency, symbol: biz.currency, name: biz.currency, label: biz.currency }, ...availableCurrencies];
                    return list.map(c => `
                      <option value="${escapeHtml(c.code)}" ${biz.currency === c.code ? 'selected' : ''}>
                        ${escapeHtml(c.label || `${c.code} (${c.symbol}) - ${c.name}`)}
                      </option>
                    `).join('');
                  })()}
                </select>
              </div>

              <div class="col-span-2">
                ${renderImageUploadField({
                  id: 'biz-logo',
                  label: 'Brand Logo Image',
                  value: biz.logo_url || '',
                  storageConfigured: Boolean(state.storageInfo?.configured),
                  placeholder: 'https://...',
                })}
              </div>

              <div class="form-group col-span-2 sm:col-span-1">
                <label class="form-label">Contact Email</label>
                <input type="email" id="biz-email" class="form-control" value="${escapeHtml(biz.contact_email || '')}" placeholder="support@acme.com" />
              </div>
              <div class="form-group col-span-2 sm:col-span-1">
                <label class="form-label">Contact Phone / WhatsApp</label>
                <input type="tel" id="biz-phone" class="form-control" value="${escapeHtml(biz.contact_phone || '')}" placeholder="+234..." />
              </div>
              <div class="form-group col-span-2">
                <label class="form-label">Physical / Headquarters Address</label>
                <input type="text" id="biz-address" class="form-control" value="${escapeHtml(biz.address || '')}" placeholder="123 Commercial Ave, Lagos" />
              </div>
            </div>
            <div class="flex justify-end pt-4 border-t border-subtle">
              <button type="submit" class="btn btn-primary">Save Business Settings</button>
            </div>
          </form>
        </div>
      `;

      initImageUploadControl('biz-logo');

      document.getElementById('business-settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
          name: document.getElementById('biz-name').value,
          currency: document.getElementById('biz-curr').value,
          contact_email: document.getElementById('biz-email').value || null,
          contact_phone: document.getElementById('biz-phone').value || null,
          address: document.getElementById('biz-address').value || null,
          logo_url: document.getElementById('biz-logo').value || null,
        };
        try {
          await api('/settings/profile', { method: 'PUT', body: JSON.stringify(payload) });
          showToast('Business settings saved successfully', 'success');
          state.business = payload;
          if (window.updateSidebarBrand) window.updateSidebarBrand();
        } catch (err) {
          showToast(err.message || 'Failed to save business settings', 'error');
        }
      });
      initAllCustomSelects(el);
      if (window.lucide) lucide.createIcons();
    }

    function renderApiKeyTab() {
      const el = document.getElementById('settings-tab-content');
      const keyInfo = state.apiKeyInfo || {};
      el.innerHTML = `
        <div class="card space-y-6">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-bold text-base text-main">Platform API Security</h3>
              <p class="text-xs text-muted mt-0.5">Authenticate incoming webhooks, external integrations and head-office automation</p>
            </div>
            <span class="badge ${keyInfo.has_api_key ? 'badge-emerald' : 'badge-subtle'}">
              ${keyInfo.has_api_key ? 'Key Active' : 'No Key Generated'}
            </span>
          </div>

          <div class="space-y-4">
            <div class="form-group">
              <label class="form-label">Live API Secret Key</label>
              <div class="flex items-center gap-2">
                <input
                  type="text"
                  id="display-api-key"
                  class="form-control font-mono text-xs bg-surface-elevated/50"
                  readonly
                  value="${keyInfo.masked_key || 'No active key. Click rotate to generate one.'}"
                />
                <button class="btn btn-secondary btn-sm" id="btn-copy-api-key" ${!keyInfo.has_api_key ? 'disabled' : ''}>
                  <i data-lucide="copy" class="w-4 h-4"></i> Copy
                </button>
              </div>
            </div>

            <div class="grid grid-cols-2 gap-4 text-xs text-muted">
              <div>Created: <span class="text-main font-medium">${formatDate(keyInfo.api_key_created_at)}</span></div>
              <div>Last Rotated: <span class="text-main font-medium">${formatDate(keyInfo.last_rotated_at)}</span></div>
            </div>

            <div class="pt-4 flex justify-end border-t border-subtle">
              <button class="btn btn-danger btn-sm" id="btn-rotate-key">
                <i data-lucide="refresh-cw" class="w-4 h-4"></i> Rotate API Key
              </button>
            </div>
          </div>
        </div>
      `;
      bindRotateKeyButton();
      if (window.lucide) lucide.createIcons();
    }

    function renderPasswordTab() {
      const el = document.getElementById('settings-tab-content');
      el.innerHTML = `
        <div class="card space-y-6">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-bold text-base text-main">Change Password</h3>
              <p class="text-xs text-muted mt-0.5">Update your administrative account login password</p>
            </div>
            <span class="badge badge-subtle">
              <i data-lucide="shield" class="w-3.5 h-3.5 mr-1 text-brand"></i> Secure Account
            </span>
          </div>

          <form id="change-password-form" class="space-y-4 max-w-lg">
            <div class="form-group">
              <label class="form-label">Current Password</label>
              <div class="relative">
                <i data-lucide="lock" class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted pointer-events-none"></i>
                <input type="password" id="change-current-password" class="form-control pl-9 pr-10" required placeholder="Enter current password" />
                <button type="button" class="password-toggle-btn absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-main focus:outline-none" data-target="change-current-password" aria-label="Toggle password visibility">
                  <i data-lucide="eye" class="w-4 h-4"></i>
                </button>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">New Password</label>
              <div class="relative">
                <i data-lucide="key" class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted pointer-events-none"></i>
                <input type="password" id="change-new-password" class="form-control pl-9 pr-10" required placeholder="Min 8 characters (mixed case, numbers)" />
                <button type="button" class="password-toggle-btn absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-main focus:outline-none" data-target="change-new-password" aria-label="Toggle password visibility">
                  <i data-lucide="eye" class="w-4 h-4"></i>
                </button>
              </div>
            </div>

            ${renderPasswordStrengthMarkup('change')}

            <div class="form-group">
              <label class="form-label">Confirm New Password</label>
              <div class="relative">
                <i data-lucide="shield-check" class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted pointer-events-none"></i>
                <input type="password" id="change-confirm-password" class="form-control pl-9 pr-10" required placeholder="Repeat new password" />
                <button type="button" class="password-toggle-btn absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-main focus:outline-none" data-target="change-confirm-password" aria-label="Toggle password visibility">
                  <i data-lucide="eye" class="w-4 h-4"></i>
                </button>
              </div>
            </div>

            <div class="flex justify-end pt-4 border-t border-subtle">
              <button type="submit" class="btn btn-primary opacity-50 cursor-not-allowed" id="btn-save-password" disabled>
                Update Password
              </button>
            </div>
          </form>
        </div>
      `;

      initPasswordToggles(el);
      bindPasswordValidator({
        passwordInputId: 'change-new-password',
        confirmInputId: 'change-confirm-password',
        submitBtnId: 'btn-save-password',
        idPrefix: 'change',
      });

      if (window.lucide) lucide.createIcons();

      document.getElementById('change-password-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const current_password = document.getElementById('change-current-password').value;
        const new_password = document.getElementById('change-new-password').value;
        const confirm_password = document.getElementById('change-confirm-password').value;

        if (new_password !== confirm_password) {
          showToast('New passwords do not match.', 'error');
          return;
        }

        const btn = document.getElementById('btn-save-password');
        const orig = btn.innerHTML;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 mr-1 animate-spin"></i> Updating...`;
        btn.disabled = true;
        if (window.lucide) lucide.createIcons();

        try {
          await api('/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({ current_password, new_password }),
          });
          showToast('Password updated successfully', 'success');
          renderPasswordTab();
        } catch (err) {
          showToast(err.message || 'Failed to update password', 'error');
          btn.innerHTML = orig;
          btn.disabled = false;
          if (window.lucide) lucide.createIcons();
        }
      });
    }

    function switchTab(tabId) {
      state.settingsTab = tabId;
      document.querySelectorAll('.settings-tab').forEach((btn) => {
        const isActive = btn.dataset.tab === tabId;
        btn.classList.toggle('bg-brand/10', isActive);
        btn.classList.toggle('text-brand', isActive);
        btn.classList.toggle('font-semibold', isActive);
        btn.classList.toggle('text-muted', !isActive);
      });
      if (tabId === 'profile') renderProfileTab();
      else if (tabId === 'password') renderPasswordTab();
      else renderApiKeyTab();
    }

    document.querySelectorAll('.settings-tab').forEach((btn) => {
      btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });
    switchTab(activeTab);

    function bindRotateKeyButton() {
      document.getElementById('btn-rotate-key').addEventListener('click', () => {
        openConfirmModal({
          title: 'Confirm API Key Rotation',
          message: 'Rotating your API key will immediately invalidate the current key. Any external system or webhook using the previous key will cease functioning until updated.',
          confirmText: 'Yes, Rotate Key',
          confirmType: 'danger',
          onConfirm: async () => {
            const res = await api('/settings/api-key/rotate', { method: 'POST' });
            openModal(`
              <div class="modal-dialog">
                <div class="modal-header">
                  <h3 class="font-bold text-lg flex items-center gap-2 text-emerald">
                    <i data-lucide="check-circle-2" class="w-5 h-5"></i>
                    New Platform API Key Generated
                  </h3>
                </div>
                <div class="modal-body space-y-4">
                  <p class="text-sm text-muted">
                    Please copy and store your new API key now. It will not be shown again.
                  </p>
                  <div class="code-preview">
                    <span id="rotated-api-key">${escapeHtml(res.raw_api_key)}</span>
                    <button class="btn btn-sm btn-secondary" onclick="navigator.clipboard.writeText('${res.raw_api_key}'); showToast('API Key copied!', 'success');">Copy</button>
                  </div>
                </div>
                <div class="modal-footer">
                  <button class="btn btn-primary" onclick="closeModal(); loadSettingsPage(document.getElementById('page-content'));">Done</button>
                </div>
              </div>
            `);
          }
        });
      });
    }

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load settings: ${escapeHtml(err.message)}</div>`;
  }
}
