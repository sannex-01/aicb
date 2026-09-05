import { state } from '../state.js';
import { api } from '../api.js';
import { navigate } from '../router.js';
import { showToast, openModal, closeModal, openConfirmModal, openOffcanvas, escapeHtml, formatCurrency, formatDate, skeletonPage, initPasswordToggles, renderSelectCards } from '../utils.js';

export async function loadAgentsPage(container) {
  container.innerHTML = skeletonPage({ stats: 0, rows: 6 });
  try {
    const isAdmin = ['admin', 'super_admin'].includes(state.user?.role);
    const [agents, groups] = await Promise.all([
      api('/agents'),
      api('/access-groups'),
    ]);

    const groupsMap = {};
    (groups || []).forEach(g => { groupsMap[g.id] = g.name; });

    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold">Multi-Agent Studio</h1>
            <p class="text-sm text-muted">Configure distinct agent personas, LLM provider credentials, access scopes & channel credentials</p>
          </div>
          ${isAdmin ? `
          <button class="btn btn-primary btn-sm" id="btn-create-agent">
            <i data-lucide="plus" class="w-4 h-4"></i> Create Agent
          </button>
          ` : ''}
        </div>

        ${agents.length === 0 ? `
          <div class="card p-10 sm:p-14 text-center max-w-2xl mx-auto flex flex-col items-center justify-center border-dashed border-2 border-subtle my-6">
            <div class="w-16 h-16 rounded-2xl bg-brand/10 text-brand flex items-center justify-center mb-4 shadow-sm">
              <i data-lucide="bot" class="w-8 h-8"></i>
            </div>
            <h2 class="text-lg font-bold text-main mb-1.5">No AI Agents Created Yet</h2>
            <p class="text-xs text-muted max-w-md mb-6 leading-relaxed">
              Create and configure your first intelligent assistant persona. Set custom system prompts, choose LLM providers (Gemini, OpenAI, Groq, Anthropic), and connect WhatsApp, Telegram, or embeddable Website Widget channels.
            </p>
            <div class="flex flex-wrap items-center justify-center gap-2 mb-6">
              <span class="badge badge-subtle px-3 py-1 text-xs"><i data-lucide="message-circle" class="w-3.5 h-3.5 mr-1 text-emerald-500"></i> WhatsApp Cloud API</span>
              <span class="badge badge-subtle px-3 py-1 text-xs"><i data-lucide="send" class="w-3.5 h-3.5 mr-1 text-sky-500"></i> Telegram Bot</span>
              <span class="badge badge-subtle px-3 py-1 text-xs"><i data-lucide="globe" class="w-3.5 h-3.5 mr-1 text-amber-500"></i> Website Widget</span>
            </div>
            ${isAdmin ? `
            <button class="btn btn-primary" id="btn-create-agent-empty">
              <i data-lucide="plus" class="w-4 h-4 mr-1"></i> Create Your First Agent
            </button>
            ` : `
            <p class="text-xs text-muted">Ask an administrator to deploy your instance's first AI agent.</p>
            `}
          </div>
        ` : `
          <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            ${agents.map(agent => {
              const hasWa = Boolean(agent.whatsapp_phone_number_id || agent.whatsapp_phone_id || agent.whatsapp_access_token_set);
              const hasTg = Boolean(agent.telegram_bot_token_set || agent.telegram_username || agent.telegram_bot_token);
              const hasWidget = Boolean(agent.widget_enabled);

              const assignedGroupIds = agent.group_ids && agent.group_ids.length ? agent.group_ids : (agent.group_id ? [agent.group_id] : []);
              const groupNames = assignedGroupIds.map(gid => groupsMap[gid]).filter(Boolean);

              return `
              <div class="card flex flex-col justify-between">
                <div>
                  <div class="flex items-start justify-between mb-3">
                    <div>
                      <h3 class="font-bold text-base text-main">${escapeHtml(agent.name)}</h3>
                      <span class="text-xs font-mono text-faint">/${escapeHtml(agent.slug)}</span>
                    </div>
                    <span class="badge ${agent.is_active ? 'badge-emerald' : 'badge-subtle'} text-[12px]">${agent.is_active ? 'Active' : 'Inactive'}</span>
                  </div>

                  <p class="text-xs text-muted line-clamp-2 mb-4">${escapeHtml(agent.description || 'No description provided.')}</p>

                  <div class="space-y-2 text-xs mb-4">
                    <div class="flex justify-between text-muted">
                      <span>Provider / Model:</span>
                      <span class="font-mono text-main">${escapeHtml(agent.llm_provider || 'gemini')} / ${escapeHtml(agent.model_name || 'default')}</span>
                    </div>
                    <div class="flex justify-between text-muted">
                      <span>Access Groups:</span>
                      <span class="text-main">
                        ${groupNames.length ? groupNames.map(gn => `<span class="badge badge-sky mr-1 text-[12px]">${escapeHtml(gn)}</span>`).join('') : '<span class="badge badge-emerald text-[12px]">Global (All Products)</span>'}
                      </span>
                    </div>
                    <div class="flex flex-wrap items-center gap-1.5 pt-2.5 border-t border-subtle">
                      ${hasWa ? '<span class="badge badge-emerald inline-flex items-center gap-1"><i data-lucide="message-circle" class="w-3 h-3"></i> WhatsApp</span>' : ''}
                      ${hasTg ? '<span class="badge badge-sky inline-flex items-center gap-1"><i data-lucide="send" class="w-3 h-3"></i> Telegram</span>' : ''}
                      ${hasWidget ? '<span class="badge badge-amber inline-flex items-center gap-1"><i data-lucide="globe" class="w-3 h-3"></i> Widget</span>' : ''}
                      ${!(hasWa || hasTg || hasWidget) ? '<span class="text-[12px] text-muted italic">No channels active</span>' : ''}
                    </div>
                  </div>
                </div>

                <div class="flex items-center justify-end gap-2 pt-4 border-t border-subtle">
                  <button class="btn btn-secondary btn-sm" onclick="window.testAgentModal(${agent.id}, '${escapeHtml(agent.name)}')">
                    <i data-lucide="play" class="w-3.5 h-3.5"></i> Test Run
                  </button>
                  ${hasWidget ? `
                  <button class="btn btn-secondary btn-sm" onclick="window.showEmbedSnippet('${escapeHtml(agent.id)}', '${escapeHtml(agent.slug || '')}')">
                    <i data-lucide="code" class="w-3.5 h-3.5"></i> Snippet
                  </button>
                  ` : ''}
                  ${isAdmin ? `
                  <button class="btn btn-secondary btn-sm" onclick='window.editAgentModal(${JSON.stringify(agent).replace(/'/g, "&apos;")}, ${JSON.stringify(groups).replace(/'/g, "&apos;")})'>
                    <i data-lucide="edit-2" class="w-3.5 h-3.5"></i> Edit
                  </button>
                  <button class="btn btn-icon btn-secondary btn-sm text-rose hover:bg-rose/10" title="Delete Agent" onclick='window.deleteAgent(${agent.id}, "${escapeHtml(agent.slug)}", "${escapeHtml(agent.name)}")'>
                    <i data-lucide="trash-2" class="w-4 h-4"></i>
                  </button>
                  ` : ''}
                </div>
              </div>
              `;
            }).join('')}
          </div>
        `}
      </div>
    `;

    const createBtn = document.getElementById('btn-create-agent');
    if (createBtn) {
      createBtn.addEventListener('click', () => window.editAgentModal(null, groups));
    }
    const createBtnEmpty = document.getElementById('btn-create-agent-empty');
    if (createBtnEmpty) {
      createBtnEmpty.addEventListener('click', () => window.editAgentModal(null, groups));
    }
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load agents: ${escapeHtml(err.message)}</div>`;
  }
}

function editAgentModal(agent, groups) {
  const isEdit = Boolean(agent);
  const selectedGroupIds = new Set(agent?.group_ids || (agent?.group_id ? [agent.group_id] : []));
  const agentKeyConfigured = Boolean(agent?.api_key_override || agent?.api_key_configured || agent?.api_key_masked);

  openOffcanvas({
    title: isEdit ? 'Edit Agent' : 'Create New AI Agent',
    formId: 'agent-form',
    mode: isEdit ? 'tabs' : 'wizard',
    submitLabel: isEdit ? 'Save Changes' : 'Create Agent',
    extraFooterLeft: isEdit ? `<button type="button" class="btn btn-danger btn-sm" onclick="window.deleteAgent(${agent.id}, '${escapeHtml(agent.slug)}', '${escapeHtml(agent.name)}')">Delete Agent</button>` : '',
    steps: [
      {
        label: 'Identity',
        render: () => `
          <div class="space-y-4">
            <div class="form-group">
              <label class="form-label">Agent Name</label>
              <input type="text" id="ag-name" class="form-control" required value="${escapeHtml(agent?.name || '')}" placeholder="Sales Assistant" />
            </div>
            
            ${!isEdit ? `
              <div class="form-group">
                <label class="form-label flex items-center justify-between">
                  <span>Slug Identifier</span>
                  <span class="text-[12px] text-muted normal-case font-normal">Auto-created from name</span>
                </label>
                <input type="text" id="ag-slug" class="form-control bg-surface-elevated text-muted font-mono text-xs cursor-not-allowed" readonly placeholder="sales-assistant" />
              </div>
            ` : `
              <div class="p-3 rounded-lg bg-surface-elevated border border-subtle flex items-center justify-between text-xs">
                <span class="text-muted">Slug Identifier</span>
                <span class="font-mono font-semibold text-main">${escapeHtml(agent.slug)}</span>
              </div>
            `}

            <div class="form-group">
              <label class="form-label">Description</label>
              <input type="text" id="ag-desc" class="form-control" value="${escapeHtml(agent?.description || '')}" placeholder="Specialized sales & product recommendation agent" />
            </div>
          </div>
        `,
      },
      {
        label: 'Access',
        render: () => `
          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <label class="form-label font-semibold text-main m-0">Access Groups</label>
              <span class="text-[12px] text-muted">Multiple Select</span>
            </div>
            <p class="text-[12px] text-muted">Select the Access Groups this agent belongs to. The agent will have access to products assigned to these groups, and can inherit their configured LLM keys. If left empty, the agent has global access to all products.</p>
            
            <div class="max-h-56 overflow-y-auto pr-1">
              ${renderSelectCards({
                name: 'ag-groups',
                type: 'checkbox',
                items: (groups || []).map(g => ({
                  id: g.id,
                  title: g.name,
                  description: g.description,
                  metaHtml: g.has_api_key 
                    ? `<div class="text-[12px] text-emerald font-mono flex items-center gap-1"><i data-lucide="key" class="w-3 h-3"></i> Key Set (${escapeHtml(g.llm_provider || 'default')})</div>` 
                    : '',
                })),
                selectedValues: selectedGroupIds,
                gridClass: 'select-card-grid grid grid-cols-1 sm:grid-cols-2 gap-2.5',
                emptyMessage: 'No access groups created yet. All products are globally accessible by default.',
              })}
            </div>
          </div>
        `,
      },
      {
        label: 'Model',
        render: () => `
          <div class="space-y-3">
            <div class="grid grid-cols-2 gap-3">
              <div class="form-group">
                <label class="form-label">LLM Provider</label>
                <select id="ag-provider" class="form-control">
                  <option value="gemini" ${agent?.llm_provider === 'gemini' ? 'selected' : ''}>Google Gemini</option>
                  <option value="openai" ${agent?.llm_provider === 'openai' ? 'selected' : ''}>OpenAI</option>
                  <option value="anthropic" ${agent?.llm_provider === 'anthropic' ? 'selected' : ''}>Anthropic Claude</option>
                  <option value="groq" ${agent?.llm_provider === 'groq' ? 'selected' : ''}>Groq</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Model Name</label>
                <input type="text" id="ag-model" class="form-control" value="${escapeHtml(agent?.model_name || 'gemini-2.5-flash')}" placeholder="e.g. gemini-2.5-flash, gpt-4o-mini" />
              </div>
            </div>

            <div class="p-3 rounded-xl border border-subtle bg-app/40 space-y-2">
              <label class="form-label flex items-center justify-between m-0">
                <span class="font-semibold text-main">Agent API Key Override (Optional)</span>
                ${agentKeyConfigured ? `<span class="badge badge-emerald text-[12px] font-mono">Configured: ${escapeHtml(agent.api_key_masked || '••••••••')}</span>` : ''}
              </label>
              <div class="relative flex items-center">
                <input type="password" id="ag-api-key" class="form-control pr-10 font-mono text-xs" placeholder="${agentKeyConfigured ? 'Leave blank to keep configured key' : 'Provider API Key (sk-..., AIzaSy...)'}" autocomplete="new-password" />
                <button type="button" class="password-toggle-btn absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-main focus:outline-none p-1" data-target="ag-api-key" title="Toggle key visibility">
                  <i data-lucide="eye" class="w-4 h-4"></i>
                </button>
              </div>
              <p class="text-[12px] text-muted m-0">If left empty, this agent will automatically inherit the provider key configured on its assigned Access Group, or fall back to system settings.</p>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="form-group">
                <label class="form-label">Temperature: <span id="ag-temp-val">${agent?.temperature ?? 0.7}</span></label>
                <input type="range" id="ag-temp" min="0" max="1" step="0.05" value="${agent?.temperature ?? 0.7}" class="w-full" oninput="document.getElementById('ag-temp-val').innerText = this.value" />
              </div>
              <div class="form-group">
                <label class="form-label">Max Tokens</label>
                <input type="number" id="ag-max-tokens" class="form-control" value="${agent?.max_tokens || 1000}" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Custom System Prompt Persona</label>
              <textarea id="ag-prompt" class="form-control font-mono text-xs" rows="3" placeholder="You are an expert sales consultant for our store...">${escapeHtml(agent?.system_prompt || '')}</textarea>
            </div>
          </div>
        `,
      },
      {
        label: 'Channels',
        render: () => {
          const waConfigured = Boolean(agent?.whatsapp_token_masked || agent?.whatsapp_access_token_set);
          const tgConfigured = Boolean(agent?.telegram_bot_token_masked || agent?.telegram_bot_token_set);

          return `
          <div class="space-y-4">
            <div class="p-3.5 rounded-xl border border-subtle bg-app/40 space-y-3">
              <div class="flex items-center gap-2 text-xs font-semibold text-emerald">
                <i data-lucide="message-circle" class="w-3.5 h-3.5"></i> WhatsApp
              </div>
              <div class="form-group">
                <label class="form-label">WhatsApp Phone ID</label>
                <input type="text" id="ag-wa-phone" class="form-control" value="${escapeHtml(agent?.whatsapp_phone_number_id || agent?.whatsapp_phone_id || '')}" placeholder="Meta Phone Number ID" />
              </div>
              <div class="form-group">
                <label class="form-label flex items-center justify-between">
                  <span>WhatsApp Token</span>
                  ${waConfigured ? `<span class="badge badge-emerald text-[12px] font-mono">Configured: ${escapeHtml(agent.whatsapp_token_masked || '••••••••')}</span>` : ''}
                </label>
                <div class="relative flex items-center">
                  <input type="password" id="ag-wa-token" class="form-control pr-10 font-mono text-xs" placeholder="${waConfigured ? 'Leave blank to keep configured' : 'Meta Access Token'}" autocomplete="new-password" />
                  <button type="button" class="password-toggle-btn absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-main focus:outline-none p-1" data-target="ag-wa-token" title="Toggle token visibility">
                    <i data-lucide="eye" class="w-4 h-4"></i>
                  </button>
                </div>
              </div>
            </div>

            <div class="p-3.5 rounded-xl border border-subtle bg-app/40 space-y-3">
              <div class="flex items-center gap-2 text-xs font-semibold text-sky">
                <i data-lucide="send" class="w-3.5 h-3.5"></i> Telegram Bot API
              </div>
              <div class="form-group">
                <label class="form-label flex items-center justify-between">
                  <span>Telegram Bot Token</span>
                  ${tgConfigured ? `<span class="badge badge-sky text-[12px] font-mono">Configured: ${escapeHtml(agent.telegram_bot_token_masked || '••••••••')}</span>` : ''}
                </label>
                <div class="relative flex items-center">
                  <input type="password" id="ag-tg-token" class="form-control pr-10 font-mono text-xs" placeholder="${tgConfigured ? 'Leave blank to keep configured' : 'Telegram Bot Token from @BotFather'}" autocomplete="new-password" />
                  <button type="button" class="password-toggle-btn absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-main focus:outline-none p-1" data-target="ag-tg-token" title="Toggle token visibility">
                    <i data-lucide="eye" class="w-4 h-4"></i>
                  </button>
                </div>
                <p class="text-[12px] text-muted mt-1">Webhook is configured automatically with your active secret token.</p>
              </div>
            </div>

            <div class="p-3.5 rounded-xl border border-subtle bg-app/50 flex items-center justify-between transition-colors hover:border-brand/40">
              <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center border border-amber-500/20">
                  <i data-lucide="globe" class="w-4 h-4"></i>
                </div>
                <div>
                  <div class="font-medium text-xs text-main">Website Chat Widget</div>
                  <div class="text-[12px] text-muted">Allow customers & visitors to chat with this agent via embedded web widget</div>
                </div>
              </div>
              <label class="relative inline-flex items-center cursor-pointer m-0">
                <input type="checkbox" id="ag-widget-enabled" class="sr-only peer" ${agent?.widget_enabled !== false ? 'checked' : ''}>
                <div class="w-10 h-5 bg-subtle peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald"></div>
              </label>
            </div>
          </div>
          `;
        },
      },
    ],
  });

  const formEl = document.getElementById('agent-form');
  if (formEl) {
    initPasswordToggles(formEl);
  }

  const nameInput = document.getElementById('ag-name');
  const slugInput = document.getElementById('ag-slug');
  if (nameInput && slugInput && !isEdit) {
    nameInput.addEventListener('input', () => {
      const raw = nameInput.value.toLowerCase().trim()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
      slugInput.value = raw;
    });
  }

  formEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const groupCheckboxes = document.querySelectorAll('input[name="ag-groups"]:checked');
    const groupIds = Array.from(groupCheckboxes).map(el => parseInt(el.value, 10));

    const apiKeyInput = document.getElementById('ag-api-key').value.trim();
    const waPhone = document.getElementById('ag-wa-phone').value.trim();
    const waToken = document.getElementById('ag-wa-token').value.trim();
    const tgToken = document.getElementById('ag-tg-token').value.trim();

    const payload = {
      name: document.getElementById('ag-name').value.trim(),
      description: document.getElementById('ag-desc')?.value.trim() || null,
      llm_provider: document.getElementById('ag-provider').value,
      model_name: document.getElementById('ag-model').value.trim(),
      temperature: parseFloat(document.getElementById('ag-temp').value),
      max_tokens: parseInt(document.getElementById('ag-max-tokens').value, 10),
      system_prompt: document.getElementById('ag-prompt').value.trim(),
      group_ids: groupIds,
      whatsapp_phone_number_id: waPhone || null,
      widget_enabled: document.getElementById('ag-widget-enabled').checked,
      is_active: true,
    };

    if (!isEdit) {
      const slugVal = document.getElementById('ag-slug')?.value.trim();
      if (slugVal) {
        payload.slug = slugVal;
      }
    }

    if (apiKeyInput) {
      payload.api_key_override = apiKeyInput;
    }
    if (waToken) {
      payload.whatsapp_access_token = waToken;
    }
    if (tgToken) {
      payload.telegram_bot_token = tgToken;
    }

    try {
      if (isEdit) {
        await api(`/agents/${agent.id}`, { method: 'PUT', body: JSON.stringify(payload) });
        showToast('Agent updated successfully', 'success');
      } else {
        await api('/agents', { method: 'POST', body: JSON.stringify(payload) });
        showToast('Agent created successfully', 'success');
      }
      closeModal();
      loadAgentsPage(document.getElementById('page-content'));
    } catch (err) {
      showToast(err.message || 'Failed to save agent', 'error');
    }
  });
}

function deleteAgent(agentId, agentSlug = '', agentName = '') {
  openConfirmModal({
    title: 'Delete AI Agent',
    message: `Are you sure you want to permanently delete "${agentName || 'this agent'}"? All conversation logs, widget configurations, and settings for this agent will be removed.`,
    confirmText: 'Delete Agent',
    confirmType: 'danger',
    confirmInput: agentSlug,
    inputLabel: `To confirm deletion, please type the agent slug <span class="font-mono px-1.5 py-0.5 rounded bg-app border border-subtle text-rose font-bold">${escapeHtml(agentSlug)}</span> below:`,
    inputPlaceholder: `Type ${agentSlug}`,
    onConfirm: async () => {
      await api(`/agents/${agentId}`, { method: 'DELETE' });
      showToast('Agent deleted successfully', 'success');
      loadAgentsPage(document.getElementById('page-content'));
    }
  });
}

function testAgentModal(agentId, agentName) {
  openModal(`
    <div class="modal-dialog max-w-2xl w-full flex flex-col h-[560px] max-h-[85vh] p-0 overflow-hidden">
      <!-- Modal Header -->
      <div class="modal-header flex items-center justify-between border-b border-subtle px-5 py-3.5 bg-surface flex-shrink-0">
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="w-8 h-8 rounded-lg bg-brand/10 text-brand flex items-center justify-center flex-shrink-0">
            <i data-lucide="bot" class="w-4 h-4"></i>
          </div>
          <div class="min-w-0">
            <h3 class="font-bold text-sm text-main truncate">${escapeHtml(agentName)}</h3>
            <span class="text-[12px] text-muted block truncate">Interactive Sandbox Test</span>
          </div>
        </div>
        <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>

      <!-- Chat Transcript (Scrollable) -->
      <div id="test-chat-transcript" class="flex-1 overflow-y-auto p-4 space-y-3 bg-app/40">
        <div class="flex flex-col items-start">
          <span class="text-[12px] text-muted mb-1 px-1 font-medium">${escapeHtml(agentName)}</span>
          <div class="bg-surface border border-subtle text-main rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-xs max-w-[85%] whitespace-pre-wrap leading-relaxed shadow-sm">
            👋 Hello! I am <strong>${escapeHtml(agentName)}</strong>. Send me a message to test how I respond.
          </div>
        </div>
      </div>

      <!-- Input Footer -->
      <div class="border-t border-subtle p-3.5 bg-surface flex-shrink-0">
        <form id="test-chat-form" class="flex items-center gap-2 m-0">
          <input type="text" id="test-msg-input" class="form-control text-xs flex-1" placeholder="Type a test query..." autocomplete="off" />
          <button type="submit" class="btn btn-primary btn-sm flex items-center gap-1.5 flex-shrink-0" id="btn-send-test">
            <span>Send</span>
            <i data-lucide="send" class="w-3.5 h-3.5"></i>
          </button>
        </form>
      </div>
    </div>
  `);

  if (window.lucide) lucide.createIcons();

  const form = document.getElementById('test-chat-form');
  const input = document.getElementById('test-msg-input');
  const sendBtn = document.getElementById('btn-send-test');
  const transcript = document.getElementById('test-chat-transcript');

  if (input) input.focus();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = input.value.trim();
    if (!msg) return;

    // Render User Bubble
    transcript.innerHTML += `
      <div class="flex flex-col items-end">
        <span class="text-[12px] text-muted mb-1 px-1 font-medium">You</span>
        <div class="bg-brand text-brand-contrast rounded-2xl rounded-tr-sm px-3.5 py-2.5 text-xs max-w-[85%] whitespace-pre-wrap leading-relaxed shadow-sm">
          ${escapeHtml(msg)}
        </div>
      </div>
    `;
    input.value = '';
    transcript.scrollTop = transcript.scrollHeight;

    // Show Typing Indicator
    const typingId = `typing-${Date.now()}`;
    transcript.innerHTML += `
      <div id="${typingId}" class="flex flex-col items-start">
        <span class="text-[12px] text-muted mb-1 px-1 font-medium">${escapeHtml(agentName)}</span>
        <div class="bg-surface border border-subtle text-muted rounded-2xl rounded-tl-sm px-3.5 py-2 text-xs flex items-center gap-1.5 shadow-sm">
          <span class="inline-block w-1.5 h-1.5 rounded-full bg-brand animate-pulse"></span>
          <span class="inline-block w-1.5 h-1.5 rounded-full bg-brand animate-pulse [animation-delay:0.2s]"></span>
          <span class="inline-block w-1.5 h-1.5 rounded-full bg-brand animate-pulse [animation-delay:0.4s]"></span>
          <span class="text-[12px] ml-1">Thinking...</span>
        </div>
      </div>
    `;
    transcript.scrollTop = transcript.scrollHeight;

    input.disabled = true;
    sendBtn.disabled = true;

    try {
      const res = await api(`/agents/${agentId}/test-run`, {
        method: 'POST',
        body: JSON.stringify({ message: msg }),
      });

      const typingEl = document.getElementById(typingId);
      if (typingEl) typingEl.remove();

      transcript.innerHTML += `
        <div class="flex flex-col items-start">
          <span class="text-[12px] text-muted mb-1 px-1 font-medium">${escapeHtml(agentName)}</span>
          <div class="bg-surface border border-subtle text-main rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-xs max-w-[85%] whitespace-pre-wrap leading-relaxed shadow-sm">
            ${escapeHtml(res.reply)}
          </div>
        </div>
      `;
      transcript.scrollTop = transcript.scrollHeight;
    } catch (err) {
      const typingEl = document.getElementById(typingId);
      if (typingEl) typingEl.remove();

      transcript.innerHTML += `
        <div class="flex flex-col items-start">
          <span class="text-[12px] text-rose mb-1 px-1 font-medium">Error</span>
          <div class="bg-rose/10 border border-rose/20 text-rose rounded-2xl rounded-tl-sm px-3.5 py-2.5 text-xs max-w-[85%]">
            Failed to get response: ${escapeHtml(err.message || 'Unknown error')}
          </div>
        </div>
      `;
      transcript.scrollTop = transcript.scrollHeight;
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
    }
  });
}

// ============================================================================
// 6. ACCESS GROUPS PAGE
// ============================================================================

window.showEmbedSnippet = function(agentId, agentSlug) {
  const host = window.location.origin;
  const botId = agentSlug || agentId || 'default';
  const snippet = `<script src="${host}/widget.js" data-bot-id="${botId}" async></script>`;

  openModal(`
    <div class="modal-dialog max-w-xl w-full">
      <div class="modal-header">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-lg bg-brand/10 text-brand flex items-center justify-center">
            <i data-lucide="code" class="w-4 h-4"></i>
          </div>
          <div>
            <h3 class="font-bold text-base text-main">Embed Website Widget</h3>
            <p class="text-xs text-muted">Single script tag for your website or online store</p>
          </div>
        </div>
        <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>
      <div class="modal-body space-y-3">
        <p class="text-xs text-muted leading-relaxed">Copy and paste this script tag into the <code>&lt;head&gt;</code> or right before the closing <code>&lt;/body&gt;</code> tag of any web page:</p>
        <div class="relative">
          <textarea class="form-control font-mono text-xs w-full h-24 p-3 bg-surface-elevated/80 resize-none select-all" readonly id="embed-snippet-text">${escapeHtml(snippet)}</textarea>
          <button class="absolute top-2 right-2 btn btn-secondary btn-sm flex items-center gap-1" onclick="navigator.clipboard.writeText(document.getElementById('embed-snippet-text').value); showToast('Widget script tag copied!', 'success')">
            <i data-lucide="copy" class="w-3.5 h-3.5"></i> Copy
          </button>
        </div>
        <div class="p-2.5 rounded-lg border border-subtle bg-surface text-[12px] text-muted flex items-center gap-2">
          <i data-lucide="info" class="w-4 h-4 text-brand flex-shrink-0"></i>
          <span>Auto-loads the chat bubble and connects directly to this AI agent.</span>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary w-full" onclick="closeModal()">Done</button>
      </div>
    </div>
  `);
  if (window.lucide) lucide.createIcons();
};

window.editAgentModal = editAgentModal;
window.deleteAgent = deleteAgent;
window.testAgentModal = testAgentModal;