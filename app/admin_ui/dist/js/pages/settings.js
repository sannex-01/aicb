import { state } from '../state.js';
import { api } from '../api.js';
import { navigate } from '../router.js';
import { showToast, openModal, closeModal, openConfirmModal, escapeHtml, formatCurrency, formatDate, skeletonPage, renderImageUploadField, initImageUploadControl, uploadMediaFile, initAllCustomSelects, initPasswordToggles, renderPasswordStrengthMarkup, bindPasswordValidator } from '../utils.js';

export async function loadSettingsPage(container) {
  if (!['admin', 'super_admin'].includes(state.user?.role)) {
    container.innerHTML = `
      <div class="card text-center p-12 space-y-4 max-w-lg mx-auto mt-12">
        <div class="w-12 h-12 rounded-full bg-rose/10 text-rose flex items-center justify-center mx-auto">
          <i data-lucide="shield-alert" class="w-6 h-6"></i>
        </div>
        <div>
          <h3 class="font-bold text-lg text-main">Administrator Access Required</h3>
          <p class="text-xs text-muted mt-1">Platform settings, cloud storage, and API keys can only be managed by team administrators.</p>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="navigate('/_/admin/overview')">Back to Overview</button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = skeletonPage({ stats: 0, rows: 4 });
  try {
    const [biz, keyInfo, storageInfo, emailInfo, paymentInfo, channelsInfo] = await Promise.all([
      api('/settings/profile'),
      api('/settings/api-key'),
      api('/settings/storage'),
      api('/settings/email').catch(() => ({ provider: null, configured: false, config: {} })),
      api('/settings/payments').catch(() => ({ provider: null, configured: false, config: {} })),
      api('/settings/channels').catch(() => ({ whatsapp: {}, telegram: {}, widget: {} })),
    ]);
    state.business = biz;
    state.apiKeyInfo = keyInfo;
    state.storageInfo = storageInfo;
    state.emailInfo = emailInfo;
    state.paymentInfo = paymentInfo;
    state.channelsInfo = channelsInfo;

    const tabs = [
      { id: 'profile', label: 'Business Profile', icon: 'store' },
      { id: 'channels', label: 'Messaging Channels', icon: 'message-square' },
      { id: 'payments', label: 'Payment Gateways', icon: 'credit-card' },
      { id: 'email', label: 'Email Delivery', icon: 'mail' },
      { id: 'storage', label: 'Storage & Media', icon: 'hard-drive' },
      { id: 'password', label: 'Change Password', icon: 'key' },
      { id: 'api-key', label: 'Platform API Key', icon: 'shield' },
    ];
    const activeTab = state.settingsTab || 'profile';

    container.innerHTML = `
      <div class="space-y-6">
        <div>
          <h1 class="text-2xl font-bold">Settings & Platform Security</h1>
          <p class="text-sm text-muted">Manage business identity, payment gateways, email delivery (Resend/Brevo) & API keys</p>
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
                  ${state.paymentInfo?.configured ? '<span class="text-[12px] text-emerald-600 font-mono">Synced from Paystack</span>' : ''}
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

    function renderChannelsTab() {
      const el = document.getElementById('settings-tab-content');
      const ch = state.channelsInfo || { whatsapp: {}, telegram: {} };
      const wa = ch.whatsapp || {};
      const tg = ch.telegram || {};
      const domain = ch.domain || window.location.origin;

      el.innerHTML = `
        <div class="card space-y-6">
          <div>
            <h3 class="font-bold text-base text-main">Messaging Channels</h3>
            <p class="text-xs text-muted mt-0.5">Configure global webhook verification tokens, channel secrets, and test live webhooks</p>
          </div>

          <form id="channels-settings-form" class="space-y-6">
            <!-- WhatsApp Cloud API -->
            <div class="p-4 rounded-xl border border-subtle bg-surface-elevated/20 space-y-4">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs font-semibold text-emerald">
                  <i data-lucide="message-circle" class="w-4 h-4"></i> WhatsApp Cloud API
                </div>
                <span class="badge ${wa.app_secret_configured ? 'badge-emerald' : 'badge-subtle'} text-[12px]">
                  ${wa.app_secret_configured ? 'App Secret Configured' : 'Open / Unverified'}
                </span>
              </div>

              <div class="space-y-3">
                <div class="form-group">
                  <label class="form-label flex items-center justify-between">
                    <span>Webhook Callback URL</span>
                    <span class="text-[12px] text-muted normal-case font-normal">Paste in Meta WhatsApp Configuration</span>
                  </label>
                  <div class="code-preview text-xs">
                    <span class="truncate">${escapeHtml(wa.webhook_url || `${domain}/api/v1/webhooks/whatsapp`)}</span>
                    <button type="button" class="btn btn-secondary btn-sm flex-shrink-0" onclick="navigator.clipboard.writeText('${wa.webhook_url || `${domain}/api/v1/webhooks/whatsapp`}'); showToast('WhatsApp Webhook URL copied!', 'success');">Copy</button>
                  </div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div class="form-group">
                    <label class="form-label flex items-center justify-between">
                      <span>Webhook Verify Token</span>
                      <button type="button" id="btn-rotate-wa-token" class="text-[12px] text-brand hover:underline flex items-center gap-1 cursor-pointer" title="Generate fresh random verify token">
                        <i data-lucide="refresh-cw" class="w-3 h-3"></i> Generate New
                      </button>
                    </label>
                    <div class="relative flex items-center">
                      <button type="button" id="btn-rotate-wa-token-icon" class="absolute left-2.5 text-muted hover:text-brand transition-colors p-1" title="Rotate verify token">
                        <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
                      </button>
                      <input type="text" id="wa-verify-token" class="form-control text-xs font-mono pl-9 pr-14" value="${escapeHtml(wa.verify_token || 'aicb_webhook_verification_token_secret')}" placeholder="aicb_webhook_verify_token" />
                      <button type="button" class="btn btn-ghost btn-sm absolute right-1.5 text-xs text-muted hover:text-main px-2 py-0.5" onclick="navigator.clipboard.writeText(document.getElementById('wa-verify-token').value); showToast('Verify token copied!', 'success');">Copy</button>
                    </div>
                  </div>

                  <div class="form-group">
                    <label class="form-label flex items-center justify-between">
                      <span>Meta App Secret (HMAC)</span>
                      ${wa.app_secret_configured ? `<span class="badge badge-emerald text-[12px] font-mono">Configured: ${escapeHtml(wa.app_secret_masked)}</span>` : ''}
                    </label>
                    <div class="relative flex items-center">
                      <input type="password" id="wa-app-secret" class="form-control pr-10 font-mono text-xs" placeholder="${wa.app_secret_configured ? 'Leave blank to keep current secret' : 'Meta App Secret for HMAC-SHA256'}" autocomplete="new-password" />
                      <button type="button" class="password-toggle-btn absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-main focus:outline-none p-1" data-target="wa-app-secret" title="Toggle secret visibility">
                        <i data-lucide="eye" class="w-4 h-4"></i>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Telegram Bot API -->
            <div class="p-4 rounded-xl border border-subtle bg-surface-elevated/20 space-y-4">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs font-semibold text-sky">
                  <i data-lucide="send" class="w-4 h-4"></i> Telegram Bot API
                </div>
                <span class="badge ${tg.webhook_secret_configured ? 'badge-sky' : 'badge-subtle'} text-[12px]">
                  ${tg.webhook_secret_configured ? 'Secret Token Active' : 'Auto-Generated'}
                </span>
              </div>

              <div class="space-y-3">
                <div class="form-group">
                  <label class="form-label flex items-center justify-between">
                    <span>Webhook Callback URL</span>
                    <span class="text-[12px] text-muted normal-case font-normal">Registered automatically via Telegram API</span>
                  </label>
                  <div class="code-preview text-xs">
                    <span class="truncate">${escapeHtml(tg.webhook_url || `${domain}/api/v1/webhooks/telegram`)}</span>
                    <button type="button" class="btn btn-secondary btn-sm flex-shrink-0" onclick="navigator.clipboard.writeText('${tg.webhook_url || `${domain}/api/v1/webhooks/telegram`}'); showToast('Telegram Webhook URL copied!', 'success');">Copy</button>
                  </div>
                </div>

                <div class="form-group">
                  <label class="form-label flex items-center justify-between">
                    <span>Webhook Secret Token (X-Telegram-Bot-Api-Secret-Token)</span>
                    <button type="button" id="btn-rotate-tg-token" class="text-[12px] text-brand hover:underline flex items-center gap-1 cursor-pointer" title="Generate fresh secret token">
                      <i data-lucide="refresh-cw" class="w-3 h-3"></i> Generate New
                    </button>
                  </label>
                  <div class="relative flex items-center">
                    <button type="button" id="btn-rotate-tg-token-icon" class="absolute left-2.5 text-muted hover:text-brand transition-colors p-1" title="Rotate secret token">
                      <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i>
                    </button>
                    <input type="password" id="tg-webhook-secret" class="form-control pr-20 pl-9 font-mono text-xs" value="${escapeHtml(tg.webhook_secret || '')}" placeholder="whsec_••••••••••••" autocomplete="new-password" />
                    <div class="absolute right-2 flex items-center gap-1">
                      <button type="button" class="password-toggle-btn text-muted hover:text-main focus:outline-none p-1" data-target="tg-webhook-secret" title="Toggle secret visibility">
                        <i data-lucide="eye" class="w-4 h-4"></i>
                      </button>
                      <button type="button" class="btn btn-ghost btn-sm text-xs text-muted hover:text-main px-2 py-0.5" onclick="navigator.clipboard.writeText(document.getElementById('tg-webhook-secret').value); showToast('Secret token copied!', 'success');">Copy</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="flex justify-end pt-2 border-t border-subtle">
              <button type="submit" class="btn btn-primary" id="btn-save-channels">Save Messaging Settings</button>
            </div>
          </form>

          <!-- Webhook Setup & Live Test Instructions -->
          <div class="p-5 rounded-2xl border border-subtle bg-surface-elevated/40 space-y-4">
            <div class="flex items-center gap-2">
              <div class="w-8 h-8 rounded-lg bg-brand/10 text-brand flex items-center justify-center flex-shrink-0">
                <i data-lucide="check-circle-2" class="w-4 h-4"></i>
              </div>
              <div>
                <h4 class="font-bold text-sm text-main">Webhook Setup & Live Test Diagnostics</h4>
                <p class="text-xs text-muted">Verify connectivity and confirm webhooks are receiving events</p>
              </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <!-- WhatsApp Guide -->
              <div class="p-4 rounded-xl border border-subtle bg-surface space-y-2.5 text-xs">
                <div class="font-bold text-main flex items-center gap-1.5 text-emerald">
                  <i data-lucide="message-circle" class="w-4 h-4"></i> WhatsApp Setup Instructions
                </div>
                <ol class="list-decimal list-inside space-y-1.5 text-muted leading-relaxed">
                  <li>Open your <span class="font-semibold text-main">Meta Developer App Dashboard</span>.</li>
                  <li>Go to <span class="font-semibold text-main">WhatsApp &rarr; Configuration</span>.</li>
                  <li>In <span class="font-semibold text-main">Webhook</span>, click <span class="font-semibold text-main">Edit</span>.</li>
                  <li>Paste the <span class="font-mono text-[12px] text-main">Webhook Callback URL</span> and <span class="font-mono text-[12px] text-main">Verify Token</span> above.</li>
                  <li>Click <span class="font-semibold text-main">Verify and Save</span>, then subscribe to the <code class="px-1 py-0.5 rounded bg-surface-elevated border border-subtle text-brand font-mono">messages</code> field.</li>
                </ol>
              </div>

              <!-- Telegram Tester -->
              <div class="p-4 rounded-xl border border-subtle bg-surface space-y-3 text-xs">
                <div class="font-bold text-main flex items-center gap-1.5 text-sky">
                  <i data-lucide="send" class="w-4 h-4"></i> Telegram Webhook Live Tester
                </div>
                <p class="text-muted leading-relaxed">
                  Once an agent has a Telegram Bot Token, the webhook is registered automatically. You can also test or register it directly here:
                </p>
                <div class="space-y-2">
                  <div class="flex gap-2">
                    <input type="text" id="tg-test-token" class="form-control text-xs font-mono flex-1" placeholder="123456789:ABCdefGHIjklMNOpqr..." />
                    <button type="button" id="btn-test-tg-webhook" class="btn btn-secondary text-xs flex-shrink-0 flex items-center gap-1.5">
                      <i data-lucide="zap" class="w-3.5 h-3.5 text-amber-500"></i>
                      <span>Test & Set</span>
                    </button>
                  </div>
                  <div id="tg-test-result" class="hidden text-xs p-2.5 rounded-lg"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      `;

      initPasswordToggles(el);
      if (window.lucide) lucide.createIcons();

      // Rotate WhatsApp verify token
      const rotateWa = async () => {
        try {
          const res = await api('/settings/channels/generate-secret', { method: 'POST' });
          if (res?.verify_token) {
            document.getElementById('wa-verify-token').value = res.verify_token;
            showToast('New WhatsApp Verify Token generated. Remember to click Save!', 'success');
          }
        } catch (err) {
          showToast('Failed to generate token: ' + err.message, 'error');
        }
      };
      document.getElementById('btn-rotate-wa-token')?.addEventListener('click', rotateWa);
      document.getElementById('btn-rotate-wa-token-icon')?.addEventListener('click', rotateWa);

      // Rotate Telegram secret token
      const rotateTg = async () => {
        try {
          const res = await api('/settings/channels/generate-secret', { method: 'POST' });
          if (res?.webhook_secret) {
            document.getElementById('tg-webhook-secret').value = res.webhook_secret;
            showToast('New Telegram Secret Token generated. Remember to click Save!', 'success');
          }
        } catch (err) {
          showToast('Failed to generate secret: ' + err.message, 'error');
        }
      };
      document.getElementById('btn-rotate-tg-token')?.addEventListener('click', rotateTg);
      document.getElementById('btn-rotate-tg-token-icon')?.addEventListener('click', rotateTg);

      // Telegram Live Webhook Tester
      document.getElementById('btn-test-tg-webhook')?.addEventListener('click', async () => {
        const tokenInput = document.getElementById('tg-test-token');
        const resultDiv = document.getElementById('tg-test-result');
        const botToken = tokenInput.value.trim();

        if (!botToken) {
          showToast('Please enter a Telegram Bot Token to test.', 'warning');
          return;
        }

        const btn = document.getElementById('btn-test-tg-webhook');
        const orig = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> Testing...`;
        if (window.lucide) lucide.createIcons();

        try {
          const res = await api('/settings/channels/telegram/test-webhook', {
            method: 'POST',
            body: JSON.stringify({ bot_token: botToken }),
          });

          resultDiv.classList.remove('hidden', 'bg-emerald/10', 'text-emerald', 'border-emerald/20', 'bg-rose/10', 'text-rose', 'border-rose/20');
          resultDiv.classList.add('border');

          if (res.ok) {
            resultDiv.classList.add('bg-emerald/10', 'text-emerald', 'border-emerald/20');
            resultDiv.innerHTML = `
              <div class="flex items-center gap-1.5 font-bold mb-0.5">
                <i data-lucide="check" class="w-4 h-4"></i> Webhook Set Successfully!
              </div>
              <p class="text-[12px] text-emerald/90 leading-relaxed">${escapeHtml(res.description || 'Webhook URL registered with Telegram Bot API.')}</p>
            `;
          } else {
            resultDiv.classList.add('bg-rose/10', 'text-rose', 'border-rose/20');
            resultDiv.innerHTML = `
              <div class="flex items-center gap-1.5 font-bold mb-0.5">
                <i data-lucide="alert-circle" class="w-4 h-4"></i> Telegram API Error
              </div>
              <p class="text-[12px] text-rose/90 leading-relaxed">${escapeHtml(res.description || 'Failed to register webhook.')}</p>
            `;
          }
          if (window.lucide) lucide.createIcons();
        } catch (err) {
          resultDiv.classList.remove('hidden');
          resultDiv.className = 'text-xs p-2.5 rounded-lg border bg-rose/10 text-rose border-rose/20';
          resultDiv.innerHTML = `
            <div class="flex items-center gap-1.5 font-bold mb-0.5">
              <i data-lucide="alert-circle" class="w-4 h-4"></i> Test Error
            </div>
            <p class="text-[12px]">${escapeHtml(err.message || 'Connection failed')}</p>
          `;
          if (window.lucide) lucide.createIcons();
        } finally {
          btn.disabled = false;
          btn.innerHTML = orig;
          if (window.lucide) lucide.createIcons();
        }
      });

      document.getElementById('channels-settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('btn-save-channels');
        const orig = btn.innerHTML;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 mr-1 animate-spin"></i> Saving...`;
        btn.disabled = true;
        if (window.lucide) lucide.createIcons();

        const waSecret = document.getElementById('wa-app-secret').value.trim();
        const tgSecret = document.getElementById('tg-webhook-secret').value.trim();

        const payload = {
          whatsapp: {
            verify_token: document.getElementById('wa-verify-token').value.trim(),
          },
          telegram: {},
        };

        if (waSecret) payload.whatsapp.app_secret = waSecret;
        if (tgSecret) payload.telegram.webhook_secret = tgSecret;

        try {
          const res = await api('/settings/channels', {
            method: 'PUT',
            body: JSON.stringify(payload),
          });
          state.channelsInfo = res;
          showToast('Messaging channels updated successfully', 'success');
          renderChannelsTab();
        } catch (err) {
          showToast(err.message || 'Failed to save channel settings', 'error');
          btn.innerHTML = orig;
          btn.disabled = false;
          if (window.lucide) lucide.createIcons();
        }
      });
    }

    function renderStorageTab() {
      const el = document.getElementById('settings-tab-content');
      const st = state.storageInfo || {};
      const currentProvider = st.provider || 'none';
      const conf = st.config || {};

      el.innerHTML = `
        <div class="card space-y-6">
          <div class="flex items-start justify-between">
            <div>
              <h3 class="font-bold text-base text-main flex items-center gap-2">
                <i data-lucide="hard-drive" class="w-5 h-5 text-brand"></i>
                Media & File Storage Settings
              </h3>
              <p class="text-xs text-muted mt-0.5">
                Connect your cloud bucket or image CDN to enable file uploads for product photos, store logos, and agent media.
              </p>
            </div>
            <span class="badge ${st.configured ? 'badge-emerald' : 'badge-amber'}">
              ${st.configured ? `Active (${st.provider})` : 'Not Configured'}
            </span>
          </div>

          <!-- Provider Picker -->
          <div class="space-y-2">
            <label class="form-label">Storage Provider</label>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <label class="flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${currentProvider === 'cloudinary' ? 'border-brand bg-brand/5 shadow-sm' : 'border-subtle bg-surface-elevated/40 hover:bg-surface-hover'}">
                <input type="radio" name="storage-provider" value="cloudinary" ${currentProvider === 'cloudinary' ? 'checked' : ''} class="text-brand focus:ring-brand" onchange="window.switchStorageProviderUI('cloudinary')" />
                <div>
                  <div class="font-semibold text-sm text-main">Cloudinary</div>
                  <div class="text-[12px] text-muted">Image CDN & Optimization</div>
                </div>
              </label>

              <label class="flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${currentProvider === 'cloudflare_r2' ? 'border-brand bg-brand/5 shadow-sm' : 'border-subtle bg-surface-elevated/40 hover:bg-surface-hover'}">
                <input type="radio" name="storage-provider" value="cloudflare_r2" ${currentProvider === 'cloudflare_r2' ? 'checked' : ''} class="text-brand focus:ring-brand" onchange="window.switchStorageProviderUI('cloudflare_r2')" />
                <div>
                  <div class="font-semibold text-sm text-main">Cloudflare R2</div>
                  <div class="text-[12px] text-muted">Zero Egress S3 Bucket</div>
                </div>
              </label>

              <label class="flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${currentProvider === 'none' ? 'border-brand bg-brand/5 shadow-sm' : 'border-subtle bg-surface-elevated/40 hover:bg-surface-hover'}">
                <input type="radio" name="storage-provider" value="none" ${currentProvider === 'none' ? 'checked' : ''} class="text-brand focus:ring-brand" onchange="window.switchStorageProviderUI('none')" />
                <div>
                  <div class="font-semibold text-sm text-main">Disabled</div>
                  <div class="text-[12px] text-muted">URL Links Only</div>
                </div>
              </label>
            </div>
          </div>

          <form id="storage-settings-form" class="space-y-4">
            <!-- Cloudinary Fields -->
            <div id="storage-fields-cloudinary" class="${currentProvider === 'cloudinary' ? '' : 'hidden'} space-y-4 p-4 rounded-xl border border-subtle bg-surface-elevated/30">
              <div class="font-semibold text-xs text-main">Cloudinary Credentials</div>
              <div class="grid grid-cols-2 gap-4">
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Cloud Name</label>
                  <input type="text" id="cld-name" class="form-control" placeholder="e.g. dxyz123" value="${escapeHtml(conf.cloud_name || '')}" />
                </div>
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">API Key</label>
                  <input type="text" id="cld-key" class="form-control" placeholder="123456789012345" value="${escapeHtml(conf.api_key || '')}" />
                </div>
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">API Secret ${conf.api_secret_masked ? '<span class="text-emerald text-[12px]">(Saved)</span>' : ''}</label>
                  <input type="password" id="cld-secret" class="form-control" placeholder="${conf.api_secret_masked ? '••••••••••••••••••••••••••••' : 'Cloudinary API Secret'}" />
                </div>
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Upload Folder</label>
                  <input type="text" id="cld-folder" class="form-control" placeholder="aicb_uploads" value="${escapeHtml(conf.folder || 'aicb_uploads')}" />
                </div>
              </div>
            </div>

            <!-- Cloudflare R2 Fields -->
            <div id="storage-fields-cloudflare_r2" class="${currentProvider === 'cloudflare_r2' ? '' : 'hidden'} space-y-4 p-4 rounded-xl border border-subtle bg-surface-elevated/30">
              <div class="font-semibold text-xs text-main">Cloudflare R2 Bucket Details</div>
              <div class="grid grid-cols-2 gap-4">
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Account ID</label>
                  <input type="text" id="r2-account" class="form-control" placeholder="Cloudflare Account ID hex" value="${escapeHtml(conf.account_id || '')}" />
                </div>
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Bucket Name</label>
                  <input type="text" id="r2-bucket" class="form-control" placeholder="my-aicb-media" value="${escapeHtml(conf.bucket_name || '')}" />
                </div>
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Access Key ID</label>
                  <input type="text" id="r2-key" class="form-control" placeholder="R2 Token Access Key" value="${escapeHtml(conf.access_key_id || '')}" />
                </div>
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Secret Access Key ${conf.secret_access_key_masked ? '<span class="text-emerald text-[12px]">(Saved)</span>' : ''}</label>
                  <input type="password" id="r2-secret" class="form-control" placeholder="${conf.secret_access_key_masked ? '••••••••••••••••••••••••••••' : 'R2 Secret Access Key'}" />
                </div>
                <div class="form-group col-span-2">
                  <label class="form-label">Public Base URL / Custom Domain (Optional)</label>
                  <input type="url" id="r2-public-url" class="form-control" placeholder="https://pub-xxxxxx.r2.dev or https://media.mybrand.com" value="${escapeHtml(conf.public_url || '')}" />
                </div>
              </div>
            </div>

            <div class="flex items-center justify-between pt-4 border-t border-subtle">
              <div id="storage-test-status" class="text-xs text-muted"></div>
              <button type="submit" class="btn btn-primary" id="btn-save-storage">Save Storage Configuration</button>
            </div>
          </form>

          <!-- Upload Sandbox Test -->
          ${st.configured ? `
            <div class="p-4 rounded-xl border border-subtle bg-surface-elevated/20 space-y-3">
              <div class="font-semibold text-xs text-main flex items-center gap-2">
                <i data-lucide="test-tube" class="w-4 h-4 text-brand"></i>
                Test Live Upload
              </div>
              <div class="flex items-center gap-3">
                <label class="btn btn-secondary btn-sm cursor-pointer text-xs">
                  <i data-lucide="upload" class="w-3.5 h-3.5 text-brand"></i> Choose Test File
                  <input type="file" id="sandbox-test-file" class="hidden" accept="image/*" />
                </label>
                <div id="sandbox-test-output" class="text-xs text-muted truncate flex-1"></div>
              </div>
            </div>
          ` : ''}
        </div>
      `;

      window.switchStorageProviderUI = (provider) => {
        const cldEl = document.getElementById('storage-fields-cloudinary');
        const r2El = document.getElementById('storage-fields-cloudflare_r2');
        if (cldEl) cldEl.classList.toggle('hidden', provider !== 'cloudinary');
        if (r2El) r2El.classList.toggle('hidden', provider !== 'cloudflare_r2');

        const cards = document.querySelectorAll('input[name="storage-provider"]');
        cards.forEach(inp => {
          const card = inp.closest('label');
          if (card) {
            if (inp.value === provider) {
              card.className = 'flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-all border-brand bg-brand/5 shadow-sm';
            } else {
              card.className = 'flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-all border-subtle bg-surface-elevated/40 hover:bg-surface-hover';
            }
          }
        });
      };

      // Form submission
      document.getElementById('storage-settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const selected = document.querySelector('input[name="storage-provider"]:checked')?.value || 'none';

        let configPayload = {};
        if (selected === 'cloudinary') {
          configPayload = {
            cloud_name: document.getElementById('cld-name').value.trim(),
            api_key: document.getElementById('cld-key').value.trim(),
            api_secret: document.getElementById('cld-secret').value.trim(),
            folder: document.getElementById('cld-folder').value.trim() || 'aicb_uploads',
          };
        } else if (selected === 'cloudflare_r2') {
          configPayload = {
            account_id: document.getElementById('r2-account').value.trim(),
            bucket_name: document.getElementById('r2-bucket').value.trim(),
            access_key_id: document.getElementById('r2-key').value.trim(),
            secret_access_key: document.getElementById('r2-secret').value.trim(),
            public_url: document.getElementById('r2-public-url').value.trim(),
          };
        }

        try {
          const res = await api('/settings/storage', {
            method: 'PUT',
            body: JSON.stringify({
              provider: selected === 'none' ? null : selected,
              config: configPayload,
            })
          });
          state.storageInfo = res;
          showToast('Storage settings saved successfully', 'success');
          renderStorageTab();
        } catch (err) {
          showToast(err.message || 'Failed to save storage settings', 'error');
        }
      });

      // Test upload sandbox handler
      const sandboxFile = document.getElementById('sandbox-test-file');
      if (sandboxFile) {
        sandboxFile.addEventListener('change', async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          const out = document.getElementById('sandbox-test-output');
          if (out) out.innerHTML = `<span class="text-brand flex items-center gap-1.5"><i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i> Uploading test file...</span>`;
          if (window.lucide) lucide.createIcons();

          try {
            const url = await uploadMediaFile(file);
            if (out) {
              out.innerHTML = `
                <span class="text-emerald font-medium">Uploaded: </span>
                <a href="${url}" target="_blank" class="font-mono text-brand underline truncate max-w-sm">${url}</a>
              `;
            }
            showToast('Test upload succeeded!', 'success');
          } catch (err) {
            if (out) out.innerHTML = `<span class="text-rose">${escapeHtml(err.message || 'Upload failed')}</span>`;
          }
        });
      }

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

    function renderEmailTab() {
      const el = document.getElementById('settings-tab-content');
      const em = state.emailInfo || {};
      const currentProvider = em.provider || 'none';
      const cfg = em.config || {};

      el.innerHTML = `
        <div class="card space-y-6">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-bold text-base text-main">Transactional Email Delivery</h3>
              <p class="text-xs text-muted mt-0.5">Configure an email delivery provider for password resets, order notifications & customer alerts</p>
            </div>
            <span class="badge ${em.configured ? 'badge-emerald' : 'badge-subtle'}">
              ${em.configured ? `<span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1 animate-pulse"></span> Active: ${escapeHtml(em.provider ? (em.provider.charAt(0).toUpperCase() + em.provider.slice(1)) : '')}` : 'Not Configured'}
            </span>
          </div>

          <!-- Provider Select Cards -->
          <div class="space-y-2">
            <label class="form-label text-xs font-semibold text-main">Select Email Provider</label>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3" id="email-provider-cards">
              <label class="flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${currentProvider === 'resend' ? 'border-brand bg-brand/5 shadow-sm' : 'border-subtle bg-surface-elevated/40 hover:bg-surface-hover'}">
                <input type="radio" name="email-provider" value="resend" ${currentProvider === 'resend' ? 'checked' : ''} class="mt-1 text-brand focus:ring-brand" onchange="window.switchEmailProviderUI('resend')" />
                <div>
                  <div class="flex items-center gap-1.5 font-semibold text-sm text-main">
                    Resend
                    <span class="badge badge-brand text-[12px] py-0 px-1">Recommended</span>
                  </div>
                  <div class="text-[12px] text-muted mt-0.5">3,000 free emails/mo • Modern DX</div>
                </div>
              </label>

              <label class="flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${currentProvider === 'brevo' ? 'border-brand bg-brand/5 shadow-sm' : 'border-subtle bg-surface-elevated/40 hover:bg-surface-hover'}">
                <input type="radio" name="email-provider" value="brevo" ${currentProvider === 'brevo' ? 'checked' : ''} class="mt-1 text-brand focus:ring-brand" onchange="window.switchEmailProviderUI('brevo')" />
                <div>
                  <div class="flex items-center gap-1.5 font-semibold text-sm text-main">
                    Brevo
                  </div>
                  <div class="text-[12px] text-muted mt-0.5">300 free emails/day (Sendinblue)</div>
                </div>
              </label>

              <label class="flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${currentProvider === 'none' ? 'border-brand bg-brand/5 shadow-sm' : 'border-subtle bg-surface-elevated/40 hover:bg-surface-hover'}">
                <input type="radio" name="email-provider" value="none" ${currentProvider === 'none' ? 'checked' : ''} class="mt-1 text-brand focus:ring-brand" onchange="window.switchEmailProviderUI('none')" />
                <div>
                  <div class="font-semibold text-sm text-main">Disabled</div>
                  <div class="text-[12px] text-muted mt-0.5">Email sending turned off</div>
                </div>
              </label>
            </div>
          </div>

          <form id="email-settings-form" class="space-y-4">
            <!-- Resend Fields -->
            <div id="email-fields-resend" class="${currentProvider === 'resend' ? '' : 'hidden'} space-y-4 p-4 rounded-xl border border-subtle bg-surface-elevated/30">
              <div class="flex items-center justify-between">
                <div class="font-semibold text-xs text-main">Resend Configuration</div>
                <a href="https://resend.com/api-keys" target="_blank" class="text-[12px] text-brand hover:underline flex items-center gap-1">
                  Get API Key <i data-lucide="external-link" class="w-3 h-3"></i>
                </a>
              </div>
              <div class="form-group">
                <label class="form-label flex items-center justify-between">
                  <span>API Key</span>
                  ${currentProvider === 'resend' && cfg.api_key_configured ? `<span class="badge badge-emerald text-[12px] font-mono lowercase">configured (${cfg.api_key_masked})</span>` : ''}
                </label>
                <input type="password" id="resend-api-key" class="form-control font-mono text-xs" placeholder="${currentProvider === 'resend' && cfg.api_key_configured ? '•••••••••••••••• (Leave blank to keep saved key)' : 're_123456789...'}" />
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Sender Email (From)</label>
                  <input type="email" id="resend-from-email" class="form-control text-xs" value="${escapeHtml(currentProvider === 'resend' ? (cfg.from_email || '') : '')}" placeholder="noreply@yourdomain.com" />
                  <p class="text-[12px] text-muted mt-1">Must be verified under your Resend Domains.</p>
                </div>
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Sender Display Name</label>
                  <input type="text" id="resend-from-name" class="form-control text-xs" value="${escapeHtml(currentProvider === 'resend' ? (cfg.from_name || state.business?.name || '') : (state.business?.name || ''))}" placeholder="Acme Support" />
                </div>
              </div>
            </div>

            <!-- Brevo Fields -->
            <div id="email-fields-brevo" class="${currentProvider === 'brevo' ? '' : 'hidden'} space-y-4 p-4 rounded-xl border border-subtle bg-surface-elevated/30">
              <div class="flex items-center justify-between">
                <div class="font-semibold text-xs text-main">Brevo (Sendinblue) Configuration</div>
                <a href="https://app.brevo.com/settings/keys/api" target="_blank" class="text-[12px] text-brand hover:underline flex items-center gap-1">
                  Get v3 API Key <i data-lucide="external-link" class="w-3 h-3"></i>
                </a>
              </div>
              <div class="form-group">
                <label class="form-label flex items-center justify-between">
                  <span>v3 API Key</span>
                  ${currentProvider === 'brevo' && cfg.api_key_configured ? `<span class="badge badge-emerald text-[12px] font-mono lowercase">configured (${cfg.api_key_masked})</span>` : ''}
                </label>
                <input type="password" id="brevo-api-key" class="form-control font-mono text-xs" placeholder="${currentProvider === 'brevo' && cfg.api_key_configured ? '•••••••••••••••• (Leave blank to keep saved key)' : 'xkeysib-...'}" />
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Sender Email (From)</label>
                  <input type="email" id="brevo-from-email" class="form-control text-xs" value="${escapeHtml(currentProvider === 'brevo' ? (cfg.from_email || '') : '')}" placeholder="support@yourdomain.com" />
                  <p class="text-[12px] text-muted mt-1">Must be an authorized sender in Brevo.</p>
                </div>
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Sender Display Name</label>
                  <input type="text" id="brevo-from-name" class="form-control text-xs" value="${escapeHtml(currentProvider === 'brevo' ? (cfg.from_name || state.business?.name || '') : (state.business?.name || ''))}" placeholder="Acme Support" />
                </div>
              </div>
            </div>

            <!-- Disabled State Info -->
            <div id="email-fields-none" class="${currentProvider === 'none' ? '' : 'hidden'} p-4 rounded-xl border border-dashed border-subtle text-center text-xs text-muted">
              Transactional email delivery is disabled. Password reset requests will require manual administrator intervention.
            </div>

            <div class="flex justify-end pt-4 border-t border-subtle">
              <button type="submit" class="btn btn-primary" id="btn-save-email">Save Email Settings</button>
            </div>
          </form>
        </div>

        <!-- Test Email Card -->
        ${em.configured ? `
          <div class="card space-y-4 mt-6">
            <div>
              <h4 class="font-bold text-sm text-main">Send Verification Email</h4>
              <p class="text-xs text-muted mt-0.5">Send a test email to verify your API credentials and sender domain delivery</p>
            </div>
            <form id="email-test-form" class="flex items-center gap-3">
              <input type="email" id="email-test-to" class="form-control text-xs flex-1" required placeholder="admin@example.com" value="${escapeHtml(state.user?.email || '')}" />
              <button type="submit" class="btn btn-secondary btn-sm flex-shrink-0" id="btn-send-test-email">
                <i data-lucide="send" class="w-3.5 h-3.5 mr-1"></i> Send Test Email
              </button>
            </form>
          </div>
        ` : ''}
      `;

      window.switchEmailProviderUI = (provider) => {
        const resEl = document.getElementById('email-fields-resend');
        const brvEl = document.getElementById('email-fields-brevo');
        const nonEl = document.getElementById('email-fields-none');
        if (resEl) resEl.classList.toggle('hidden', provider !== 'resend');
        if (brvEl) brvEl.classList.toggle('hidden', provider !== 'brevo');
        if (nonEl) nonEl.classList.toggle('hidden', provider !== 'none');

        const cards = document.querySelectorAll('input[name="email-provider"]');
        cards.forEach(inp => {
          const card = inp.closest('label');
          if (card) {
            if (inp.value === provider) {
              card.className = 'flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all border-brand bg-brand/5 shadow-sm';
            } else {
              card.className = 'flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all border-subtle bg-surface-elevated/40 hover:bg-surface-hover';
            }
          }
        });
      };

      document.getElementById('email-settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const selected = document.querySelector('input[name="email-provider"]:checked')?.value || 'none';
        let configPayload = {};
        if (selected === 'resend') {
          configPayload = {
            api_key: document.getElementById('resend-api-key').value.trim() || undefined,
            from_email: document.getElementById('resend-from-email').value.trim(),
            from_name: document.getElementById('resend-from-name').value.trim(),
          };
        } else if (selected === 'brevo') {
          configPayload = {
            api_key: document.getElementById('brevo-api-key').value.trim() || undefined,
            from_email: document.getElementById('brevo-from-email').value.trim(),
            from_name: document.getElementById('brevo-from-name').value.trim(),
          };
        }

        try {
          const res = await api('/settings/email', {
            method: 'PUT',
            body: JSON.stringify({
              provider: selected === 'none' ? null : selected,
              config: configPayload,
            })
          });
          state.emailInfo = res;
          showToast('Email delivery settings saved successfully', 'success');
          renderEmailTab();
        } catch (err) {
          showToast(err.message || 'Failed to save email settings', 'error');
        }
      });

      const testForm = document.getElementById('email-test-form');
      if (testForm) {
        testForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          const btn = document.getElementById('btn-send-test-email');
          const original = btn.innerHTML;
          btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin mr-1"></i> Sending...`;
          btn.disabled = true;
          if (window.lucide) lucide.createIcons();

          try {
            const to = document.getElementById('email-test-to').value.trim();
            const res = await api('/settings/email/test', {
              method: 'POST',
              body: JSON.stringify({ to_email: to }),
            });
            showToast(res.message || 'Test email sent successfully', 'success');
          } catch (err) {
            showToast(err.message || 'Failed to send test email', 'error');
          } finally {
            btn.innerHTML = original;
            btn.disabled = false;
            if (window.lucide) lucide.createIcons();
          }
        });
      }

      initAllCustomSelects(el);
      if (window.lucide) lucide.createIcons();
    }

    function renderPaymentsTab() {
      const el = document.getElementById('settings-tab-content');
      const pm = state.paymentInfo || {};
      const currentProvider = pm.provider || (pm.configured ? 'paystack' : 'none');
      const cfg = pm.config || {};
      const isPaystack = currentProvider === 'paystack';

      el.innerHTML = `
        <div class="card space-y-6">
          <div class="flex items-center justify-between">
            <div>
              <h3 class="font-bold text-base text-main">Payment Gateway</h3>
              <p class="text-xs text-muted mt-0.5">Configure Paystack to generate secure checkout and instant payment links across AI conversations</p>
            </div>
            <span class="badge ${pm.configured ? 'badge-emerald' : 'badge-subtle'}">
              ${pm.configured ? `<span class="w-1.5 h-1.5 rounded-full bg-emerald-500 mr-1 animate-pulse"></span> Active: Paystack` : 'Disabled'}
            </span>
          </div>

          <!-- Provider Selection (Paystack vs Disabled) -->
          <div class="space-y-2">
            <label class="form-label text-xs font-semibold text-main">Gateway Status</label>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3" id="payment-provider-cards">
              <!-- Paystack -->
              <label class="flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${isPaystack ? 'border-brand bg-brand/5 shadow-sm' : 'border-subtle bg-surface-elevated/40 hover:bg-surface-hover'}">
                <input type="radio" name="payment-provider" value="paystack" ${isPaystack ? 'checked' : ''} class="mt-1 text-brand focus:ring-brand" onchange="window.switchPaymentProviderUI('paystack')" />
                <div>
                  <div class="flex items-center gap-1.5 font-semibold text-sm text-main">
                    Paystack
                    <span class="badge badge-brand text-[12px] py-0 px-1">Confirmed</span>
                  </div>
                  <div class="text-[12px] text-muted mt-0.5">Accept Cards, Bank Transfer, USSD, Apple Pay & Mobile Money</div>
                </div>
              </label>

              <!-- Disabled -->
              <label class="flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${!isPaystack ? 'border-brand bg-brand/5 shadow-sm' : 'border-subtle bg-surface-elevated/40 hover:bg-surface-hover'}">
                <input type="radio" name="payment-provider" value="none" ${!isPaystack ? 'checked' : ''} class="mt-1 text-brand focus:ring-brand" onchange="window.switchPaymentProviderUI('none')" />
                <div>
                  <div class="font-semibold text-sm text-main">Disabled</div>
                  <div class="text-[12px] text-muted mt-0.5">Turn off automated checkout links generation</div>
                </div>
              </label>
            </div>
          </div>

          <form id="payments-settings-form" class="space-y-4">
            <!-- Paystack Fields -->
            <div id="payment-fields-paystack" class="${isPaystack ? '' : 'hidden'} space-y-4 p-4 rounded-xl border border-subtle bg-surface-elevated/30">
              <div class="flex items-center justify-between">
                <div class="font-semibold text-xs text-main">Paystack API Credentials</div>
                <a href="https://dashboard.paystack.com/#/settings/developer" target="_blank" class="text-[12px] text-brand hover:underline flex items-center gap-1">
                  Developer Dashboard <i data-lucide="external-link" class="w-3 h-3"></i>
                </a>
              </div>
              <div class="grid grid-cols-2 gap-4">
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label flex items-center justify-between">
                    <span>Secret Key</span>
                    ${cfg.secret_key_configured ? `<span class="badge badge-emerald text-[12px] font-mono lowercase">saved (${cfg.secret_key_masked})</span>` : ''}
                  </label>
                  <input type="password" id="paystack-secret-key" class="form-control font-mono text-xs" placeholder="${cfg.secret_key_configured ? '•••••••••••••••• (Leave blank to keep saved key)' : 'sk_live_...'}" />
                </div>
                <div class="form-group col-span-2 sm:col-span-1">
                  <label class="form-label">Public Key</label>
                  <input type="text" id="paystack-public-key" class="form-control font-mono text-xs" value="${escapeHtml(cfg.public_key || '')}" placeholder="pk_live_..." />
                </div>
              </div>
              <div class="p-3 rounded-lg bg-surface text-xs text-muted flex items-start gap-2 border border-subtle">
                <i data-lucide="info" class="w-4 h-4 text-brand flex-shrink-0 mt-0.5"></i>
                <div>
                  Set your Paystack Webhook URL to: <code class="text-brand font-mono text-[12px] select-all">${window.location.origin}/api/v1/payments/webhook/paystack</code>
                </div>
              </div>
              ${pm.configured && pm.available_currencies && pm.available_currencies.length ? `
                <div class="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20 text-xs text-main">
                  <div class="flex items-center gap-1.5 font-semibold text-emerald-600 dark:text-emerald-400 mb-1.5">
                    <i data-lucide="check-circle" class="w-3.5 h-3.5"></i>
                    <span>Discovered Merchant Currencies</span>
                  </div>
                  <div class="flex flex-wrap gap-1.5">
                    ${pm.available_currencies.map(c => `
                      <span class="badge badge-emerald text-[12px] font-mono">${escapeHtml(c.code)} (${escapeHtml(c.symbol)})</span>
                    `).join('')}
                  </div>
                </div>
              ` : ''}
            </div>

            <!-- Disabled State Info -->
            <div id="payment-fields-none" class="${!isPaystack ? '' : 'hidden'} p-4 rounded-xl border border-dashed border-subtle text-center text-xs text-muted">
              Payment link generation is disabled. Customer orders will be recorded with pending payment status.
            </div>

            <div class="flex justify-end pt-4 border-t border-subtle">
              <button type="submit" class="btn btn-primary" id="btn-save-payments">Save Payment Settings</button>
            </div>
          </form>
        </div>
      `;

      window.switchPaymentProviderUI = (provider) => {
        const isPay = provider === 'paystack';
        const payFields = document.getElementById('payment-fields-paystack');
        const noneFields = document.getElementById('payment-fields-none');
        if (payFields) payFields.classList.toggle('hidden', !isPay);
        if (noneFields) noneFields.classList.toggle('hidden', isPay);

        const cards = document.querySelectorAll('input[name="payment-provider"]');
        cards.forEach(inp => {
          const card = inp.closest('label');
          if (card) {
            if (inp.value === provider) {
              card.className = 'flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all border-brand bg-brand/5 shadow-sm';
            } else {
              card.className = 'flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-all border-subtle bg-surface-elevated/40 hover:bg-surface-hover';
            }
          }
        });
      };

      document.getElementById('payments-settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const selected = document.querySelector('input[name="payment-provider"]:checked')?.value || 'none';
        let configPayload = {};
        if (selected === 'paystack') {
          configPayload = {
            secret_key: document.getElementById('paystack-secret-key').value.trim() || undefined,
            public_key: document.getElementById('paystack-public-key').value.trim(),
          };
        }

        try {
          const res = await api('/settings/payments', {
            method: 'PUT',
            body: JSON.stringify({
              provider: selected === 'none' ? null : selected,
              config: configPayload,
            })
          });
          state.paymentInfo = res;
          showToast('Payment gateway settings saved successfully', 'success');
          renderPaymentsTab();
        } catch (err) {
          showToast(err.message || 'Failed to save payment settings', 'error');
        }
      });

      initAllCustomSelects(el);
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
      else if (tabId === 'channels') renderChannelsTab();
      else if (tabId === 'payments') renderPaymentsTab();
      else if (tabId === 'email') renderEmailTab();
      else if (tabId === 'storage') renderStorageTab();
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
