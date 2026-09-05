import { state } from '../state.js';
import { api } from '../api.js';
import { navigate } from '../router.js';
import { showToast, openModal, closeModal, openConfirmModal, escapeHtml, formatCurrency, formatDate, skeletonPage, renderDataTable, initPasswordToggles } from '../utils.js';

export async function loadUsersPage(container) {
  if (!['admin', 'super_admin'].includes(state.user?.role)) {
    container.innerHTML = `
      <div class="card text-center p-12 space-y-4 max-w-lg mx-auto mt-12">
        <div class="w-12 h-12 rounded-full bg-rose/10 text-rose flex items-center justify-center mx-auto">
          <i data-lucide="shield-alert" class="w-6 h-6"></i>
        </div>
        <div>
          <h3 class="font-bold text-lg text-main">Administrator Access Required</h3>
          <p class="text-xs text-muted mt-1">Team accounts and member permissions can only be managed by administrators.</p>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="navigate('/_/admin/overview')">Back to Overview</button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  container.innerHTML = skeletonPage({ stats: 0, rows: 4 });
  try {
    const [users, emailStatus] = await Promise.all([
      api('/users'),
      api('/settings/email').catch(() => ({ provider: null, configured: false })),
    ]);

    const isEmailConfigured = Boolean(emailStatus?.configured);

    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold">Team Accounts</h1>
            <p class="text-sm text-muted">Manage administrators, operators, and member roles across this workspace</p>
          </div>
          <button class="btn btn-primary btn-sm" id="btn-create-user">
            <i data-lucide="${isEmailConfigured ? 'mail-plus' : 'plus'}" class="w-4 h-4"></i> ${isEmailConfigured ? 'Invite Team Member' : 'Add Team Member'}
          </button>
        </div>

        <div id="users-table-container"></div>
      </div>
    `;

    renderDataTable('#users-table-container', {
      data: users,
      searchPlaceholder: 'Search team members by name or email...',
      defaultSort: { key: 'created_at', dir: 'desc' },
      pageSize: 15,
      columns: [
        {
          key: 'name',
          label: 'User',
          sortable: true,
          render: (val, row) => `
            <div>
              <div class="font-semibold text-main">${escapeHtml(val || 'Unnamed')} ${row.id === state.user?.id ? '<span class="badge badge-subtle text-[10px] ml-1.5 font-normal">You</span>' : ''}</div>
              <div class="text-xs text-muted font-mono">${escapeHtml(row.email)}</div>
            </div>
          `
        },
        {
          key: 'role',
          label: 'Role',
          sortable: true,
          render: (val) => {
            let badgeCls = 'badge-subtle';
            if (val === 'super_admin') badgeCls = 'badge-purple';
            else if (val === 'admin') badgeCls = 'badge-emerald';
            else if (val === 'operator') badgeCls = 'badge-sky';
            return `<span class="badge ${badgeCls} text-[10px] uppercase">${escapeHtml(val === 'super_admin' ? 'Super Admin' : val)}</span>`;
          }
        },
        {
          key: 'is_active',
          label: 'Status',
          sortable: true,
          render: (val) => `<span class="badge ${val ? 'badge-emerald' : 'badge-rose'} text-[10px] uppercase">${val ? 'Active' : 'Disabled'}</span>`
        },
        {
          key: 'created_at',
          label: 'Created',
          sortable: true,
          type: 'date',
          render: (val) => `<span class="text-xs text-muted">${formatDate(val)}</span>`
        },
        {
          key: 'last_login_at',
          label: 'Last Login',
          sortable: true,
          type: 'date',
          render: (val) => `<span class="text-xs text-muted">${val ? formatDate(val) : 'Never'}</span>`
        },
        {
          key: 'actions',
          label: 'Actions',
          align: 'right',
          sortable: false,
          render: (_, row) => `
            <div class="flex items-center justify-end gap-1.5">
              <button class="btn btn-icon btn-secondary btn-sm" title="Edit Member Role" onclick='window.editUserModal(${JSON.stringify(row).replace(/'/g, "&apos;")})'>
                <i data-lucide="edit-2" class="w-3.5 h-3.5"></i>
              </button>
              ${row.id !== state.user?.id ? `
              <button class="btn btn-icon btn-secondary btn-sm text-rose hover:bg-rose/10" title="Remove User" onclick="window.deleteUserAccount(${row.id}, '${escapeHtml(row.name || row.email)}')">
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
              </button>
              ` : ''}
            </div>
          `
        }
      ]
    });

    document.getElementById('btn-create-user').addEventListener('click', () => {
      openAddUserModal(isEmailConfigured);
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load users: ${escapeHtml(err.message)}</div>`;
  }
}

function openAddUserModal(isEmailConfigured) {
  openModal(`
    <div class="modal-dialog max-w-xl w-full">
      <div class="modal-header">
        <div>
          <h3 class="font-bold text-lg text-main">${isEmailConfigured ? 'Invite Team Member' : 'Add Team Member'}</h3>
          <p class="text-xs text-muted mt-0.5">${isEmailConfigured ? 'An invitation link will be emailed for them to set their password.' : 'Email is not configured. Specify an initial password manually.'}</p>
        </div>
        <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>
      <form id="user-form">
        <div class="modal-body space-y-4">
          <div class="form-group">
            <label class="form-label">Full Name</label>
            <input type="text" id="usr-name" class="form-control" required placeholder="Jane Smith" />
          </div>
          <div class="form-group">
            <label class="form-label">Email Address</label>
            <input type="email" id="usr-email" class="form-control" required placeholder="jane@example.com" />
          </div>

          ${!isEmailConfigured ? `
          <div class="form-group">
            <label class="form-label">Password</label>
            <div class="relative flex items-center">
              <input type="password" id="usr-password" class="form-control pr-10" required minlength="6" placeholder="••••••••••••" autocomplete="new-password" />
              <button type="button" class="password-toggle-btn absolute right-2.5 top-1/2 -translate-y-1/2 text-muted hover:text-main focus:outline-none p-1" data-target="usr-password">
                <i data-lucide="eye" class="w-4 h-4"></i>
              </button>
            </div>
          </div>
          ` : ''}

          <div class="form-group">
            <label class="form-label">Role</label>
            <select id="usr-role" class="form-control">
              <option value="operator">Operator (Manage chat & orders)</option>
              <option value="admin">Administrator (Full settings & team control)</option>
              <option value="viewer">Viewer (Read-only analytics & logs)</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm flex items-center gap-1.5" id="btn-submit-user">
            <i data-lucide="${isEmailConfigured ? 'send' : 'user-plus'}" class="w-4 h-4"></i>
            <span>${isEmailConfigured ? 'Send Invitation' : 'Add Member'}</span>
          </button>
        </div>
      </form>
    </div>
  `);

  const form = document.getElementById('user-form');
  if (form) initPasswordToggles(form);
  if (window.lucide) lucide.createIcons();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById('btn-submit-user');
    if (submitBtn) submitBtn.disabled = true;

    const payload = {
      name: document.getElementById('usr-name').value.trim(),
      email: document.getElementById('usr-email').value.trim(),
      role: document.getElementById('usr-role').value,
    };

    const pwdInput = document.getElementById('usr-password');
    if (pwdInput && pwdInput.value) {
      payload.password = pwdInput.value;
    }

    try {
      const res = await api('/users', { method: 'POST', body: JSON.stringify(payload) });
      if (res.invited) {
        if (res.invite_warning) {
          showToast(res.invite_warning, 'warning');
        } else {
          showToast('Invitation email sent successfully!', 'success');
        }
      } else {
        showToast('Team member added successfully', 'success');
      }
      closeModal();
      loadUsersPage(document.getElementById('page-content'));
    } catch {} finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

function editUserModal(user) {
  const isSelf = user.id === state.user?.id;

  openModal(`
    <div class="modal-dialog max-w-xl w-full">
      <div class="modal-header">
        <div>
          <h3 class="font-bold text-lg text-main">Edit Team Member</h3>
          <p class="text-xs text-muted mt-0.5">Update account role and permissions</p>
        </div>
        <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>
      <form id="edit-user-form">
        <div class="modal-body space-y-4">
          <div class="form-group">
            <label class="form-label">Full Name</label>
            <input type="text" id="edit-usr-name" class="form-control" required value="${escapeHtml(user.name || '')}" placeholder="Full Name" />
          </div>
          <div class="form-group">
            <label class="form-label">Email Address</label>
            <input type="email" id="edit-usr-email" class="form-control" required value="${escapeHtml(user.email || '')}" placeholder="email@example.com" />
          </div>
          <div class="form-group">
            <label class="form-label">Role</label>
            <select id="edit-usr-role" class="form-control" ${isSelf ? 'disabled' : ''}>
              <option value="operator" ${user.role === 'operator' ? 'selected' : ''}>Operator (Manage chat & orders)</option>
              <option value="admin" ${user.role === 'admin' || user.role === 'super_admin' ? 'selected' : ''}>Administrator (Full access & team management)</option>
              <option value="viewer" ${user.role === 'viewer' ? 'selected' : ''}>Viewer (Read-only)</option>
            </select>
            ${isSelf ? '<p class="text-[11px] text-muted mt-1">You cannot modify your own administrator role.</p>' : ''}
          </div>
          <div class="form-group">
            <label class="form-label">Account Status</label>
            <select id="edit-usr-status" class="form-control" ${isSelf ? 'disabled' : ''}>
              <option value="true" ${user.is_active ? 'selected' : ''}>Active</option>
              <option value="false" ${!user.is_active ? 'selected' : ''}>Disabled</option>
            </select>
            ${isSelf ? '<p class="text-[11px] text-muted mt-1">You cannot disable your own active account.</p>' : ''}
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm" id="btn-save-edit-user">Save Changes</button>
        </div>
      </form>
    </div>
  `);

  if (window.lucide) lucide.createIcons();

  document.getElementById('edit-user-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const saveBtn = document.getElementById('btn-save-edit-user');
    if (saveBtn) saveBtn.disabled = true;

    const payload = {
      name: document.getElementById('edit-usr-name').value.trim(),
      email: document.getElementById('edit-usr-email').value.trim(),
    };

    if (!isSelf) {
      payload.role = document.getElementById('edit-usr-role').value;
      payload.is_active = document.getElementById('edit-usr-status').value === 'true';
    }

    try {
      await api(`/users/${user.id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Team member updated successfully', 'success');
      closeModal();
      loadUsersPage(document.getElementById('page-content'));
    } catch {} finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  });
}

function deleteUserAccount(userId, userName = '') {
  openConfirmModal({
    title: 'Remove Team Member',
    message: `Are you sure you want to remove ${userName ? `"${userName}"` : 'this account'}? They will immediately lose access to the admin dashboard.`,
    confirmText: 'Remove User',
    confirmType: 'danger',
    onConfirm: async () => {
      await api(`/users/${userId}`, { method: 'DELETE' });
      showToast('User removed', 'success');
      loadUsersPage(document.getElementById('page-content'));
    }
  });
}

window.openAddUserModal = openAddUserModal;
window.editUserModal = editUserModal;
window.deleteUserAccount = deleteUserAccount;