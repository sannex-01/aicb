import { state } from '../state.js';
import { api } from '../api.js';
import { navigate } from '../router.js';
import { showToast, openModal, closeModal, openConfirmModal, escapeHtml, formatCurrency, formatDate, skeletonPage, renderDataTable, initPasswordToggles } from '../utils.js';

export async function loadGroupsPage(container) {
  container.innerHTML = skeletonPage({ stats: 0, rows: 4 });
  try {
    const isAdmin = ['admin', 'super_admin'].includes(state.user?.role);
    const groups = await api('/access-groups');

    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold">Agent Access Groups</h1>
            <p class="text-sm text-muted">Organize agents into access groups with shared product permissions and optional LLM provider API credentials</p>
          </div>
          ${isAdmin ? `
          <button class="btn btn-primary btn-sm" id="btn-create-group">
            <i data-lucide="plus" class="w-4 h-4"></i> New Access Group
          </button>
          ` : ''}
        </div>

        <div id="groups-table-container"></div>
      </div>
    `;

    const columns = [
      {
        key: 'name',
        label: 'Group Name',
        sortable: true,
        render: (val) => `<span class="font-bold text-main">${escapeHtml(val)}</span>`
      },
      {
        key: 'description',
        label: 'Description',
        sortable: true,
        render: (val) => `<span class="text-muted text-xs">${escapeHtml(val || '—')}</span>`
      },
      {
        key: 'llm_provider',
        label: 'LLM Key & Provider',
        sortable: true,
        render: (val, row) => {
          if (!val && !row.has_api_key) {
            return '<span class="text-faint text-xs">Default / System</span>';
          }
          return `
            <div class="flex items-center gap-1.5">
              <span class="badge badge-sky text-[10px] uppercase font-semibold">${escapeHtml(val || 'Custom')}</span>
              ${row.has_api_key ? '<span class="badge badge-emerald text-[10px] font-mono">Key Set</span>' : '<span class="badge badge-subtle text-[10px]">No Key</span>'}
            </div>
          `;
        }
      },
      {
        key: 'agents_count',
        label: 'Assigned Agents',
        sortable: true,
        type: 'number',
        render: (val) => `<span class="badge badge-subtle font-mono">${val} ${val === 1 ? 'agent' : 'agents'}</span>`
      }
    ];

    if (isAdmin) {
      columns.push({
        key: 'actions',
        label: 'Actions',
        align: 'right',
        sortable: false,
        render: (_, row) => `
          <div class="flex items-center justify-end gap-2">
            <button class="btn btn-secondary btn-sm" onclick='window.editGroupModal(${JSON.stringify(row).replace(/'/g, "&apos;")})'>
              <i data-lucide="edit-2" class="w-3.5 h-3.5"></i> Edit
            </button>
            <button class="btn btn-icon btn-secondary btn-sm text-rose hover:bg-rose/10" title="Delete Group" onclick='window.deleteGroup(${row.id}, "${escapeHtml(row.name)}")'>
              <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
          </div>
        `
      });
    }

    renderDataTable('#groups-table-container', {
      data: groups,
      searchPlaceholder: 'Search access groups by name or description...',
      defaultSort: { key: 'name', dir: 'asc' },
      pageSize: 15,
      columns
    });

    const createBtn = document.getElementById('btn-create-group');
    if (createBtn) {
      createBtn.addEventListener('click', () => window.editGroupModal(null));
    }
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load groups: ${escapeHtml(err.message)}</div>`;
  }
}

function editGroupModal(group) {
  const isEdit = Boolean(group);
  const hasKey = Boolean(group?.has_api_key || group?.api_key_masked);

  openModal(`
    <div class="modal-dialog max-w-lg">
      <div class="modal-header">
        <h3 class="font-bold text-lg text-main">${isEdit ? 'Edit Access Group' : 'New Access Group'}</h3>
        <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>
      <form id="group-form">
        <div class="modal-body space-y-4">
          <div class="form-group">
            <label class="form-label">Group Name</label>
            <input type="text" id="grp-name" class="form-control" required value="${escapeHtml(group?.name || '')}" placeholder="e.g. Sales Department, VIP Support" />
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <input type="text" id="grp-desc" class="form-control" value="${escapeHtml(group?.description || '')}" placeholder="Access group description..." />
          </div>

          <div class="p-3.5 rounded-xl border border-subtle bg-app/40 space-y-3 pt-3">
            <div class="flex items-center gap-2 text-xs font-semibold text-brand uppercase tracking-wider">
              <i data-lucide="cpu" class="w-3.5 h-3.5"></i> Shared LLM Provider & Credentials (Optional)
            </div>
            <p class="text-[11px] text-muted">Agents assigned to this group can inherit this API key for LLM inference.</p>
            
            <div class="grid grid-cols-2 gap-3">
              <div class="form-group">
                <label class="form-label">LLM Provider</label>
                <select id="grp-provider" class="form-control">
                  <option value="" ${!group?.llm_provider ? 'selected' : ''}>None (Use System Default)</option>
                  <option value="gemini" ${group?.llm_provider === 'gemini' ? 'selected' : ''}>Google Gemini</option>
                  <option value="openai" ${group?.llm_provider === 'openai' ? 'selected' : ''}>OpenAI</option>
                  <option value="anthropic" ${group?.llm_provider === 'anthropic' ? 'selected' : ''}>Anthropic Claude</option>
                  <option value="groq" ${group?.llm_provider === 'groq' ? 'selected' : ''}>Groq</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Default Model</label>
                <input type="text" id="grp-model" class="form-control" value="${escapeHtml(group?.model_name || '')}" placeholder="e.g. gpt-4o-mini" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label flex items-center justify-between">
                <span>Provider API Key</span>
                ${hasKey ? `<span class="badge badge-emerald text-[10px] font-mono">Configured: ${escapeHtml(group.api_key_masked || '••••••••')}</span>` : ''}
              </label>
              <div class="relative flex items-center">
                <input type="password" id="grp-api-key" class="form-control pr-10 font-mono text-xs" placeholder="${hasKey ? 'Leave blank to keep configured key' : 'Paste API Key (sk-..., AIzaSy...)'}" autocomplete="new-password" />
                <button type="button" class="password-toggle-btn absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-main focus:outline-none p-1" data-target="grp-api-key" title="Toggle key visibility">
                  <i data-lucide="eye" class="w-4 h-4"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          ${isEdit ? `<button type="button" class="btn btn-danger btn-sm mr-auto" onclick="window.deleteGroup(${group.id}, '${escapeHtml(group.name)}')">Delete</button>` : ''}
          <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm">${isEdit ? 'Save Group' : 'Create Group'}</button>
        </div>
      </form>
    </div>
  `);

  const formEl = document.getElementById('group-form');
  if (formEl) {
    initPasswordToggles(formEl);
  }
  if (window.lucide) lucide.createIcons();

  formEl.addEventListener('submit', async (e) => {
    e.preventDefault();
    const apiKeyInput = document.getElementById('grp-api-key').value.trim();

    const payload = {
      name: document.getElementById('grp-name').value.trim(),
      description: document.getElementById('grp-desc').value.trim() || null,
      llm_provider: document.getElementById('grp-provider').value || null,
      model_name: document.getElementById('grp-model').value.trim() || null,
    };

    if (apiKeyInput) {
      payload.api_key = apiKeyInput;
    }

    try {
      if (isEdit) {
        await api(`/access-groups/${group.id}`, { method: 'PUT', body: JSON.stringify(payload) });
        showToast('Access group updated successfully', 'success');
      } else {
        await api('/access-groups', { method: 'POST', body: JSON.stringify(payload) });
        showToast('Access group created successfully', 'success');
      }
      closeModal();
      loadGroupsPage(document.getElementById('page-content'));
    } catch (err) {
      showToast(err.message || 'Failed to save access group', 'error');
    }
  });
}

function deleteGroup(groupId, groupName = '') {
  openConfirmModal({
    title: 'Delete Access Group',
    message: `Are you sure you want to delete "${groupName || 'this access group'}"? Agents in this group will lose their assigned permission scopes.`,
    confirmText: 'Delete Group',
    confirmType: 'danger',
    onConfirm: async () => {
      await api(`/access-groups/${groupId}`, { method: 'DELETE' });
      showToast('Access group deleted', 'success');
      loadGroupsPage(document.getElementById('page-content'));
    }
  });
}

window.editGroupModal = editGroupModal;
window.deleteGroup = deleteGroup;