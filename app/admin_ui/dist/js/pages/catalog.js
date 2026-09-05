import { state } from '../state.js';
import { api } from '../api.js';
import { showToast, openModal, closeModal, openConfirmModal, escapeHtml, formatCurrency, formatDate, skeletonPage, renderDataTable, renderImageUploadField, initImageUploadControl, renderSelectCards } from '../utils.js';

export async function loadCatalogPage(container) {
  container.innerHTML = skeletonPage({ stats: 0, rows: 6 });
  try {
    const isAdmin = ['admin', 'super_admin'].includes(state.user?.role);
    const [data, storageInfo, groups] = await Promise.all([
      api('/admin/catalog'),
      api('/settings/storage').catch(() => ({ configured: false })),
      api('/access-groups').catch(() => []),
    ]);
    state.storageInfo = storageInfo;
    state.accessGroups = groups || [];
    const items = data.items || [];

    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold">Products & Services Catalog</h1>
            <p class="text-sm text-muted">Manage store items with image previews and scoped access groups</p>
          </div>
          ${isAdmin ? `
          <button class="btn btn-primary btn-sm" id="btn-create-product">
            <i data-lucide="plus" class="w-4 h-4"></i> Add Product
          </button>
          ` : ''}
        </div>

        <div id="catalog-table-container"></div>
      </div>
    `;

    const columns = [
      {
        key: 'title',
        label: 'Product',
        sortable: true,
        render: (val, row) => `
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-lg bg-surface-elevated border border-subtle flex items-center justify-center text-muted flex-shrink-0 overflow-hidden shadow-inner">
              ${row.image_url ? `
                <img src="${escapeHtml(row.image_url)}" class="w-full h-full object-cover" onerror="this.parentElement.innerHTML='<i data-lucide=\\'package\\' class=\\'w-5 h-5 text-muted\\'></i>';" />
              ` : `
                <i data-lucide="package" class="w-5 h-5 text-muted"></i>
              `}
            </div>
            <div class="min-w-0">
              <div class="font-semibold text-main truncate max-w-xs">${escapeHtml(val)}</div>
              <div class="text-xs text-muted truncate max-w-xs">${escapeHtml(row.description || 'No description')}</div>
            </div>
          </div>
        `
      },
      {
        key: 'category',
        label: 'Category',
        sortable: true,
        render: (val) => `<span class="badge badge-subtle">${escapeHtml(val || 'General')}</span>`
      },
      {
        key: 'price',
        label: 'Price',
        sortable: true,
        type: 'number',
        render: (val, row) => `<span class="font-semibold text-main font-mono">${formatCurrency(val, row.currency)}</span>`
      },
      {
        key: 'stock_quantity',
        label: 'Stock',
        sortable: true,
        type: 'number',
        render: (val, row) => `<span class="badge ${row.in_stock ? 'badge-emerald' : 'badge-rose'}">${row.in_stock ? `${val} in stock` : 'Out of Stock'}</span>`
      },
      {
        key: 'access_scope',
        label: 'Access Scope',
        sortable: false,
        render: (_, row) => {
          const names = Array.isArray(row.access_group_names) ? row.access_group_names : [];
          if (names.length) {
            return names.map(n => `<span class="badge badge-sky mr-1 text-[12px]">${escapeHtml(n)}</span>`).join('');
          }
          const tags = Array.isArray(row.access_tags) ? row.access_tags.filter(t => !t.match(/^\d+$/)) : [];
          if (tags.length) {
            return tags.map(t => `<span class="badge badge-sky mr-1 text-[12px]">${escapeHtml(t)}</span>`).join('');
          }
          return '<span class="badge badge-emerald text-[12px]">Global (All Agents)</span>';
        }
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
            <button class="btn btn-secondary btn-sm" onclick='window.editProductModal(${JSON.stringify(row).replace(/'/g, "&apos;")})'>
              <i data-lucide="edit-2" class="w-3.5 h-3.5"></i> Edit
            </button>
            <button class="btn btn-icon btn-secondary btn-sm text-rose hover:bg-rose/10" title="Delete Product" onclick='window.deleteProduct(${row.id}, "${escapeHtml(row.title)}")'>
              <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
          </div>
        `
      });
    }

    renderDataTable('#catalog-table-container', {
      data: items,
      searchPlaceholder: 'Search catalog by title, category, or access group...',
      defaultSort: { key: 'title', dir: 'asc' },
      pageSize: 15,
      columns
    });

    const createBtn = document.getElementById('btn-create-product');
    if (createBtn) {
      createBtn.addEventListener('click', () => window.editProductModal(null));
    }
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load catalog: ${escapeHtml(err.message)}</div>`;
  }
}

async function editProductModal(product) {
  const isEdit = Boolean(product);
  
  if (!state.storageInfo) {
    try {
      state.storageInfo = await api('/settings/storage');
    } catch {
      state.storageInfo = { configured: false };
    }
  }

  if (!state.accessGroups || !state.accessGroups.length) {
    try {
      state.accessGroups = await api('/access-groups');
    } catch {
      state.accessGroups = [];
    }
  }

  const selectedGroupIds = new Set(product?.access_group_ids || []);

  openModal(`
    <div class="modal-dialog max-w-2xl">
      <div class="modal-header">
        <h3 class="font-bold text-lg text-main">${isEdit ? 'Edit Product' : 'Add Catalog Product'}</h3>
        <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>
      <form id="product-form" class="flex flex-col flex-1 min-h-0 justify-between">
        <div class="modal-body space-y-4">
          <div class="form-group">
            <label class="form-label">Product Title</label>
            <input type="text" id="prod-title" class="form-control" required value="${escapeHtml(product?.title || '')}" placeholder="Wireless Noise-Cancelling Headphones" />
          </div>
          <div class="form-group">
            <label class="form-label">Description</label>
            <textarea id="prod-desc" class="form-control" rows="2" placeholder="Detailed product description...">${escapeHtml(product?.description || '')}</textarea>
          </div>
          
          <!-- Image Upload / URL Component -->
          ${renderImageUploadField({
            id: 'prod-img',
            label: 'Product Image',
            value: product?.image_url || '',
            storageConfigured: Boolean(state.storageInfo?.configured),
            placeholder: 'https://...',
          })}

          <div class="grid grid-cols-2 gap-4">
            <div class="form-group">
              <label class="form-label">Price</label>
              <input type="number" id="prod-price" class="form-control" step="0.01" required value="${product?.price || 0}" />
            </div>
            <div class="form-group">
              <label class="form-label">Category</label>
              <input type="text" id="prod-cat" class="form-control" value="${escapeHtml(product?.category || '')}" placeholder="Electronics" />
            </div>
            <div class="form-group">
              <label class="form-label">Stock Quantity</label>
              <input type="number" id="prod-stock" class="form-control" value="${product?.stock_quantity ?? 100}" />
            </div>
            <div class="form-group">
              <label class="form-label">Currency</label>
              <input type="text" id="prod-currency" class="form-control" value="${escapeHtml(product?.currency || state.user?.business?.currency || 'NGN')}" />
            </div>
          </div>

          <div class="p-3.5 rounded-xl border border-subtle bg-app/40 space-y-2.5">
            <div class="flex items-center justify-between">
              <label class="form-label font-semibold text-main m-0">Access Groups</label>
              <span class="text-[12px] text-muted">Empty = Globally Accessible</span>
            </div>
            <p class="text-[12px] text-muted">Select which Access Groups can sell or view this product. If left unselected, this product is available to all agents across all channels.</p>
            
            <div class="max-h-44 overflow-y-auto pr-1">
              ${renderSelectCards({
                name: 'prod-group',
                type: 'checkbox',
                items: (state.accessGroups || []).map(g => ({
                  id: g.id,
                  title: g.name,
                  description: g.description,
                  metaHtml: g.has_api_key 
                    ? `<div class="text-[12px] text-emerald font-mono flex items-center gap-1"><i data-lucide="key" class="w-3 h-3"></i> Key Set</div>` 
                    : '',
                })),
                selectedValues: selectedGroupIds,
                gridClass: 'select-card-grid grid grid-cols-1 sm:grid-cols-2 gap-2',
                emptyMessage: 'No access groups created yet. All products are globally accessible by default.',
              })}
            </div>
          </div>
        </div>
        <div class="modal-footer">
          ${isEdit ? `<button type="button" class="btn btn-danger btn-sm mr-auto" onclick="window.deleteProduct(${product.id}, '${escapeHtml(product.title)}')">Delete</button>` : ''}
          <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm">${isEdit ? 'Save Product' : 'Create Product'}</button>
        </div>
      </form>
    </div>
  `);

  initImageUploadControl('prod-img');
  if (window.lucide) lucide.createIcons();

  document.getElementById('product-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const groupCheckboxes = document.querySelectorAll('input[name="prod-group"]:checked');
    const accessGroupIds = Array.from(groupCheckboxes).map(el => parseInt(el.value, 10));

    const payload = {
      title: document.getElementById('prod-title').value.trim(),
      description: document.getElementById('prod-desc').value.trim() || null,
      price: parseFloat(document.getElementById('prod-price').value),
      category: document.getElementById('prod-cat').value.trim() || null,
      stock_quantity: parseInt(document.getElementById('prod-stock').value, 10),
      currency: document.getElementById('prod-currency').value.trim() || 'NGN',
      image_url: document.getElementById('prod-img').value.trim() || null,
      access_group_ids: accessGroupIds,
      in_stock: parseInt(document.getElementById('prod-stock').value, 10) > 0,
    };

    try {
      if (isEdit) {
        await api(`/admin/catalog/${product.id}`, { method: 'PUT', body: JSON.stringify(payload) });
        showToast('Product updated successfully', 'success');
      } else {
        await api('/admin/catalog', { method: 'POST', body: JSON.stringify(payload) });
        showToast('Product created successfully', 'success');
      }
      closeModal();
      loadCatalogPage(document.getElementById('page-content'));
    } catch (err) {
      showToast(err.message || 'Failed to save product', 'error');
    }
  });
}

function deleteProduct(productId, productTitle = '') {
  openConfirmModal({
    title: 'Delete Product',
    message: `Are you sure you want to delete "${productTitle || 'this product'}"? It will no longer be offered or referenced by agents.`,
    confirmText: 'Delete Product',
    confirmType: 'danger',
    onConfirm: async () => {
      await api(`/admin/catalog/${productId}`, { method: 'DELETE' });
      showToast('Product deleted', 'success');
      loadCatalogPage(document.getElementById('page-content'));
    }
  });
}

window.editProductModal = editProductModal;
window.deleteProduct = deleteProduct;