import { state } from '../state.js';
import { api } from '../api.js';
import { navigate } from '../router.js';
import { showToast, escapeHtml, formatCurrency, formatDate, skeletonPage, renderDataTable } from '../utils.js';

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
      columns: [
        {
          key: 'order_reference',
          label: 'Reference',
          sortable: true,
          render: (val) => `<span class="font-mono text-xs font-semibold text-main">${escapeHtml(val)}</span>`
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
          label: 'Status',
          sortable: true,
          render: (val) => `<span class="badge ${val === 'paid' ? 'badge-emerald' : val === 'failed' ? 'badge-rose' : 'badge-amber'}">${escapeHtml(val)}</span>`
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
          label: 'Actions',
          align: 'right',
          sortable: false,
          render: (_, row) => row.checkout_url 
            ? `<a href="${row.checkout_url}" target="_blank" class="text-brand hover:underline text-xs inline-flex items-center gap-1 font-medium">View Checkout <i data-lucide="external-link" class="w-3 h-3"></i></a>` 
            : `<span class="text-faint text-xs">—</span>`
        }
      ]
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load orders: ${escapeHtml(err.message)}</div>`;
  }
}
