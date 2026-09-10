import { state } from '../state.js';
import { api } from '../api.js';
import { navigate } from '../router.js';
import { showToast, escapeHtml, formatCurrency, formatDate, skeletonPage, renderDataTable, openModal, closeModal } from '../utils.js';

const _fulfillmentBadge = (s) => {
  const map = {
    delivered: 'badge-emerald', shipped: 'badge-emerald', dispatched: 'badge-sky',
    delivered_digital: 'badge-emerald', manual: 'badge-amber', pending: 'badge-subtle', failed: 'badge-rose',
  };
  return `<span class="badge ${map[s] || 'badge-subtle'}">${escapeHtml((s || 'pending').replace(/_/g, ' '))}</span>`;
};
const _statusBadge = (s) => `<span class="badge ${s === 'paid' ? 'badge-emerald' : s === 'failed' || s === 'cancelled' ? 'badge-rose' : 'badge-amber'}">${escapeHtml(s || 'pending')}</span>`;

export async function loadOrdersPage(container) {
  container.innerHTML = skeletonPage({ stats: 3, rows: 8 });
  try {
    const orders = await api('/orders');

    const totalRevenue = orders.reduce((acc, o) => o.status === 'paid' ? acc + parseFloat(o.total_amount) : acc, 0);
    const paidCount = orders.filter(o => o.status === 'paid').length;
    
    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold">Orders & Payments Hub</h1>
            <p class="text-sm text-muted">Manage all transactions and payments across channels</p>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div class="stat-card">
            <span class="text-xs font-semibold text-muted flex items-center gap-2">
              <i data-lucide="banknote" class="w-4 h-4 text-emerald"></i> Revenue (Paid)
            </span>
            <span class="text-2xl font-bold font-mono text-emerald">${formatCurrency(totalRevenue, state.user?.business?.currency || 'NGN')}</span>
          </div>
          <div class="stat-card">
            <span class="text-xs font-semibold text-muted flex items-center gap-2">
              <i data-lucide="shopping-cart" class="w-4 h-4 text-brand"></i> Total Orders
            </span>
            <span class="text-2xl font-bold font-mono text-main">${orders.length}</span>
          </div>
          <div class="stat-card">
            <span class="text-xs font-semibold text-muted flex items-center gap-2">
              <i data-lucide="check-circle" class="w-4 h-4 text-brand"></i> Paid Orders
            </span>
            <span class="text-2xl font-bold font-mono text-brand">${paidCount}</span>
          </div>
        </div>

        <div id="orders-table-container"></div>
      </div>
    `;

    renderDataTable('#orders-table-container', {
      data: orders,
      searchPlaceholder: 'Search orders by reference, customer, or channel...',
      defaultSort: { key: 'created_at', dir: 'desc' },
      pageSize: 15,
      onRowClick: (row) => viewOrderDetails(row.id),
      columns: [
        {
          key: 'order_reference',
          label: 'Reference',
          sortable: true,
          render: (val, row) => `
            <div>
              <div class="font-mono text-xs font-semibold text-brand">${escapeHtml(val)}</div>
              <div class="text-[12px] text-muted">${escapeHtml(row.customer_name || row.customer_identifier || '—')}</div>
            </div>`
        },
        {
          key: 'total_amount',
          label: 'Amount',
          sortable: true,
          type: 'number',
          render: (val, row) => `<span class="font-semibold text-main">${formatCurrency(val, row.currency)}</span>`
        },
        {
          key: 'status',
          label: 'Payment',
          sortable: true,
          render: (val) => _statusBadge(val)
        },
        {
          key: 'fulfillment_status',
          label: 'Fulfillment',
          sortable: true,
          render: (val) => _fulfillmentBadge(val)
        },
        {
          key: 'channel',
          label: 'Channel',
          sortable: true,
          render: (val) => `<span class="badge ${val === 'whatsapp' ? 'badge-emerald' : val === 'telegram' ? 'badge-sky' : 'badge-subtle'} text-xs">${escapeHtml(val || 'web')}</span>`
        },
        {
          key: 'created_at',
          label: 'Date',
          sortable: true,
          type: 'date',
          render: (val) => `<span class="text-xs text-muted">${formatDate(val)}</span>`
        },
        {
          key: 'actions',
          label: '',
          align: 'right',
          sortable: false,
          render: (_, row) => `<button class="btn btn-secondary btn-sm" onclick="event.stopPropagation(); window.viewOrderDetails(${row.id})"><i data-lucide="eye" class="w-3.5 h-3.5"></i> Details</button>`
        }
      ]
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load orders: ${escapeHtml(err.message)}</div>`;
  }
}

async function viewOrderDetails(orderId) {
  try {
    const data = await api(`/orders/${orderId}`);
    const o = data.order;
    const cust = data.customer;
    const ful = data.fulfillment || {};
    const cur = o.currency || state.user?.business?.currency || 'NGN';
    const row = (k, v) => v ? `<div class="flex justify-between gap-4"><span class="text-muted">${k}</span><span class="text-main text-right">${v}</span></div>` : '';

    const groupRows = Object.entries(ful.groups || {}).map(([type, g]) => `
      <div class="flex justify-between gap-4">
        <span class="text-muted capitalize">${escapeHtml(type)}</span>
        <span class="text-main text-right text-[12px]">${escapeHtml(g.status || '')}${g.detail ? ` — ${escapeHtml(g.detail)}` : ''}</span>
      </div>`).join('');

    openModal(`
      <div class="modal-dialog max-w-2xl">
        <div class="modal-header">
          <div>
            <h3 class="font-bold text-lg text-main font-mono">${escapeHtml(o.order_reference)}</h3>
            <div class="text-xs text-muted">${formatDate(o.created_at)} · ${escapeHtml(o.channel || 'web')}</div>
          </div>
          <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
        </div>
        <div class="modal-body space-y-6 max-h-[72vh]">

          <div class="grid grid-cols-2 gap-4">
            <div class="stat-card p-3">
              <span class="text-xs font-semibold text-muted">Total</span>
              <span class="text-xl font-bold font-mono text-main">${formatCurrency(o.total_amount, cur)}</span>
            </div>
            <div class="stat-card p-3 flex flex-col gap-1">
              <span class="text-xs font-semibold text-muted">Status</span>
              <span>${_statusBadge(o.status)} ${_fulfillmentBadge(ful.status)}</span>
            </div>
          </div>

          <div>
            <h4 class="text-xs font-bold text-muted mb-3">Items</h4>
            <div class="card p-0 overflow-hidden border border-subtle">
              <table class="data-table text-xs">
                <thead><tr><th>Item</th><th class="text-center">Qty</th><th class="text-right">Price</th><th class="text-right">Total</th></tr></thead>
                <tbody class="divide-y divide-subtle">
                  ${(data.line_items || []).map(it => `
                    <tr>
                      <td>${escapeHtml(it.title)}${it.fulfillment_type ? `<span class="badge badge-subtle ml-1 text-[11px] capitalize">${escapeHtml(it.fulfillment_type)}</span>` : ''}</td>
                      <td class="text-center">${it.quantity}</td>
                      <td class="text-right font-mono">${formatCurrency(it.price, cur)}</td>
                      <td class="text-right font-mono font-semibold">${formatCurrency(it.line_total, cur)}</td>
                    </tr>`).join('') || '<tr><td colspan="4" class="text-muted text-center py-3">No line items recorded.</td></tr>'}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h4 class="text-xs font-bold text-muted mb-3">Customer</h4>
            <div class="text-xs space-y-1.5">
              ${row('Name', escapeHtml(o.customer_name || cust?.name || '—'))}
              ${row('Phone', escapeHtml(o.customer_phone || cust?.phone_number || ''))}
              ${row('Email', escapeHtml(o.customer_email || cust?.email || ''))}
              ${row('Identifier', `<span class="font-mono">${escapeHtml(o.customer_identifier || '')}</span>`)}
              ${row('Shipping address', escapeHtml(o.shipping_address || ''))}
              ${cust ? `<div class="pt-1"><button class="btn btn-secondary btn-sm" onclick="window.viewCustomerDetails(${cust.id})"><i data-lucide="user" class="w-3.5 h-3.5"></i> Open customer</button></div>` : ''}
            </div>
          </div>

          <div>
            <h4 class="text-xs font-bold text-muted mb-3">Fulfillment</h4>
            <div class="text-xs space-y-1.5">
              ${row('Status', _fulfillmentBadge(ful.status))}
              ${row('Courier', escapeHtml(ful.courier_name || ''))}
              ${ful.tracking_url ? row('Tracking', `<a href="${ful.tracking_url}" target="_blank" class="text-brand hover:underline">Track shipment</a>`) : ''}
              ${groupRows}
            </div>
          </div>

          <div>
            <h4 class="text-xs font-bold text-muted mb-3">Payment</h4>
            <div class="text-xs space-y-1.5">
              ${row('Gateway', escapeHtml(o.payment_gateway || '—'))}
              ${row('Reference', `<span class="font-mono">${escapeHtml(o.payment_reference || '—')}</span>`)}
              ${o.checkout_url ? row('Checkout link', `<a href="${o.checkout_url}" target="_blank" class="text-brand hover:underline">Open</a>`) : ''}
            </div>
            ${(data.payments || []).length ? `
              <div class="card p-0 overflow-hidden border border-subtle mt-2">
                <table class="data-table text-xs">
                  <thead><tr><th>Gateway</th><th>Reference</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
                  <tbody class="divide-y divide-subtle">
                    ${data.payments.map(p => `
                      <tr>
                        <td>${escapeHtml(p.gateway)}</td>
                        <td class="font-mono text-[11px]">${escapeHtml(p.gateway_reference)}</td>
                        <td class="font-mono">${formatCurrency(p.amount, p.currency || cur)}</td>
                        <td>${_statusBadge(p.status)}</td>
                        <td class="text-muted">${formatDate(p.created_at)}</td>
                      </tr>`).join('')}
                  </tbody>
                </table>
              </div>` : ''}
          </div>

          ${(data.siblings || []).length ? `
            <div>
              <h4 class="text-xs font-bold text-muted mb-3">Split-checkout siblings</h4>
              <div class="space-y-1.5 text-xs">
                ${data.siblings.map(s => `
                  <div class="flex justify-between gap-4 cursor-pointer hover:bg-surface-hover rounded px-1 py-0.5" onclick="window.viewOrderDetails(${s.id})">
                    <span class="font-mono text-brand">${escapeHtml(s.order_reference)}</span>
                    <span>${formatCurrency(s.total_amount, s.currency || cur)} · ${_statusBadge(s.status)}</span>
                  </div>`).join('')}
              </div>
            </div>` : ''}
        </div>
        <div class="modal-footer">
          <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
        </div>
      </div>
    `);
    if (window.lucide) lucide.createIcons();
  } catch (e) {
    showToast(e.message || 'Failed to load order details', 'error');
  }
}

window.viewOrderDetails = viewOrderDetails;
