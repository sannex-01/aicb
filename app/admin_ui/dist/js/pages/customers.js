import { state } from '../state.js';
import { api } from '../api.js';
import { navigate } from '../router.js';
import { showToast, openModal, closeModal, escapeHtml, formatCurrency, formatDate, skeletonPage, renderDataTable } from '../utils.js';

export async function loadCustomersPage(container) {
  container.innerHTML = skeletonPage({ stats: 4, rows: 6 });
  try {
    const data = await api('/customers');
    const items = data.items || [];

    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold">Customers Directory</h1>
            <p class="text-sm text-muted">Cross-channel customer profiles across WhatsApp, Telegram and Orders</p>
          </div>
        </div>

        <div id="customers-table-container"></div>
      </div>
    `;

    renderDataTable('#customers-table-container', {
      data: items,
      searchPlaceholder: 'Search customers by name, phone, email...',
      defaultSort: { key: 'last_seen_at', dir: 'desc' },
      pageSize: 15,
      columns: [
        {
          key: 'name',
          label: 'Customer',
          sortable: true,
          render: (val, row) => `
            <div>
              <div class="font-semibold text-main">${escapeHtml(val || 'Anonymous')}</div>
              <div class="text-xs text-muted font-mono">${escapeHtml(row.phone_number || row.email || row.wa_id || row.telegram_id || '—')}</div>
            </div>
          `
        },
        {
          key: 'channels',
          label: 'Channels',
          sortable: false,
          render: (val) => {
            const channels = Array.isArray(val) ? val : [];
            return channels.map(ch => `<span class="badge ${ch === 'whatsapp' ? 'badge-emerald' : 'badge-sky'} mr-1 text-[12px] capitalize">${escapeHtml(ch)}</span>`).join('') || '<span class="text-faint text-xs">—</span>';
          }
        },
        {
          key: 'total_orders',
          label: 'Orders',
          sortable: true,
          type: 'number',
          render: (val) => `<span class="badge badge-subtle font-mono">${val}</span>`
        },
        {
          key: 'total_spent',
          label: 'Total Spent',
          sortable: true,
          type: 'number',
          render: (val) => `<span class="font-semibold text-main font-mono">${formatCurrency(val)}</span>`
        },
        {
          key: 'last_seen_at',
          label: 'Last Active',
          sortable: true,
          type: 'date',
          render: (val) => `<span class="text-xs text-muted">${formatDate(val)}</span>`
        },
        {
          key: 'actions',
          label: 'Actions',
          align: 'right',
          sortable: false,
          render: (_, row) => `
            <button class="btn btn-secondary btn-sm" onclick="window.viewCustomerDetails(${row.id})">
              <i data-lucide="user" class="w-3.5 h-3.5"></i> Details
            </button>
          `
        }
      ]
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load customers: ${escapeHtml(err.message)}</div>`;
  }
}

async function viewCustomerDetails(customerId) {
  try {
    const data = await api(`/customers/${customerId}`);
    const c = data.customer;
    const conv = data.conversation_summary || {};
    const identLines = [
      c.phone_number && ['Phone', c.phone_number],
      c.email && ['Email', c.email],
      c.wa_id && ['WhatsApp ID', c.wa_id],
      c.telegram_id && ['Telegram ID', c.telegram_id],
    ].filter(Boolean);

    openModal(`
      <div class="modal-dialog max-w-2xl">
        <div class="modal-header">
          <div>
            <h3 class="font-bold text-lg text-main">${escapeHtml(c.name || 'Customer')}</h3>
            <div class="text-xs text-muted font-mono">${escapeHtml(c.phone_number || c.email || c.wa_id || c.telegram_id || '')}</div>
          </div>
          <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
        </div>
        <div class="modal-body space-y-6 max-h-[70vh]">
          <div class="grid grid-cols-2 gap-4">
            <div class="stat-card p-3">
              <span class="text-xs font-semibold text-muted">Orders</span>
              <span class="text-xl font-bold font-mono text-main">${c.total_orders}</span>
            </div>
            <div class="stat-card p-3">
              <span class="text-xs font-semibold text-muted">Total Spent</span>
              <span class="text-xl font-bold font-mono text-emerald">${formatCurrency(c.total_spent)}</span>
            </div>
          </div>

          <div>
            <h4 class="text-xs font-bold text-muted mb-3">Contact & Identifiers</h4>
            <div class="text-xs space-y-1.5">
              ${identLines.map(([k, v]) => `<div class="flex justify-between gap-4"><span class="text-muted">${k}</span><span class="font-mono text-main truncate">${escapeHtml(v)}</span></div>`).join('') || '<p class="text-muted">No contact details on file.</p>'}
              <div class="flex justify-between gap-4"><span class="text-muted">Channels</span><span>${(c.channels || []).map(ch => `<span class="badge ${ch === 'whatsapp' ? 'badge-emerald' : 'badge-sky'} text-[12px] capitalize ml-1">${escapeHtml(ch)}</span>`).join('') || '—'}</span></div>
              <div class="flex justify-between gap-4"><span class="text-muted">First seen</span><span class="text-main">${formatDate(c.created_at)}</span></div>
              <div class="flex justify-between gap-4"><span class="text-muted">Last active</span><span class="text-main">${formatDate(c.last_seen_at)}</span></div>
            </div>
          </div>

          <div>
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-xs font-bold text-muted">Conversations</h4>
              <button class="btn btn-secondary btn-sm" onclick="window.viewCustomerConversation('${escapeHtml(conv.search_term || c.name || '')}')">
                <i data-lucide="message-square" class="w-3.5 h-3.5"></i> View Conversation
              </button>
            </div>
            <p class="text-xs text-muted">
              ${conv.session_count || 0} session${(conv.session_count || 0) === 1 ? '' : 's'}${conv.last_conversation_at ? ` · last active ${formatDate(conv.last_conversation_at)}` : ''}
            </p>
          </div>

          <div>
            <h4 class="text-xs font-bold text-muted mb-3">Order History</h4>
            ${data.orders.length === 0 ? '<p class="text-xs text-muted">No orders associated with this customer.</p>' : `
              <div class="card p-0 overflow-hidden border border-subtle">
                <table class="data-table text-xs">
                  <thead>
                    <tr><th>Reference</th><th>Amount</th><th>Status</th><th>Date</th></tr>
                  </thead>
                  <tbody class="divide-y divide-subtle">
                    ${data.orders.map(o => `
                      <tr class="cursor-pointer hover:bg-surface-hover" onclick="window.viewOrderDetails(${o.id})">
                        <td class="font-mono text-xs text-brand">${escapeHtml(o.order_reference)}</td>
                        <td class="font-semibold">${formatCurrency(o.total_amount, o.currency)}</td>
                        <td><span class="badge ${o.status === 'paid' ? 'badge-emerald' : o.status === 'failed' || o.status === 'cancelled' ? 'badge-rose' : 'badge-amber'}">${escapeHtml(o.status)}</span></td>
                        <td class="text-muted">${formatDate(o.created_at)}</td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            `}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
        </div>
      </div>
    `);
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    showToast(e.message || 'Failed to load customer details', 'error');
  }
}

function viewCustomerConversation(searchTerm) {
  state.conversationsPrefilter = searchTerm || '';
  closeModal();
  navigate('/_/admin/conversations');
}

window.viewCustomerDetails = viewCustomerDetails;
window.viewCustomerConversation = viewCustomerConversation;