import { state } from '../state.js';
import { api } from '../api.js';
import { showToast, openModal, closeModal, openConfirmModal, escapeHtml, formatCurrency, formatDate, skeletonPage, renderDataTable, renderImageUploadField, initImageUploadControl, renderSelectCards } from '../utils.js';
import { CATALOG_CATEGORIES, subcategoriesFor } from '../catalog-taxonomy.js';

export async function loadCatalogPage(container) {
  container.innerHTML = skeletonPage({ stats: 0, rows: 6 });
  try {
    const isAdmin = ['admin', 'super_admin'].includes(state.user?.role);
    const [data, storageInfo, groups, importProviders] = await Promise.all([
      api('/admin/catalog'),
      api('/settings/storage').catch(() => ({ configured: false })),
      api('/access-groups').catch(() => []),
      isAdmin ? api('/admin/catalog/import/providers').catch(() => ({})) : Promise.resolve({}),
    ]);
    state.storageInfo = storageInfo;
    state.accessGroups = groups || [];
    const items = data.items || [];
    const hasImportSource = Object.values(importProviders || {}).some(p => p?.configured);

    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold">Products & Services Catalog</h1>
            <p class="text-sm text-muted">Manage store items with image previews and scoped access groups</p>
          </div>
          ${isAdmin ? `
          <div class="flex items-center gap-2">
            ${hasImportSource ? `
            <button class="btn btn-secondary btn-sm" id="btn-import-catalog">
              <i data-lucide="download-cloud" class="w-4 h-4"></i> Import Catalog
            </button>
            ` : ''}
            <button class="btn btn-primary btn-sm" id="btn-create-product">
              <i data-lucide="plus" class="w-4 h-4"></i> Add Product
            </button>
          </div>
          ` : ''}
        </div>

        <div id="catalog-table-container"></div>
      </div>
    `;

    if (hasImportSource) {
      document.getElementById('btn-import-catalog').addEventListener('click', () => importCatalogModal(importProviders));
    }

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
        render: (val, row) => `
          <span class="badge badge-subtle">${escapeHtml(val || 'General')}</span>
          ${row.subcategory ? `<span class="badge badge-subtle ml-1">${escapeHtml(row.subcategory)}</span>` : ''}
        `
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

  const businessCurrency = (product?.currency || state.business?.currency || state.user?.business?.currency || 'NGN').toUpperCase();
  let currencySymbol = businessCurrency;
  try {
    currencySymbol = new Intl.NumberFormat('en-US', { style: 'currency', currency: businessCurrency, currencyDisplay: 'narrowSymbol' })
      .formatToParts(0).find(p => p.type === 'currency')?.value || businessCurrency;
  } catch {
    // Intl throws on an unrecognized currency code — fall back to the code itself
  }

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

  // The table row passed in doesn't carry variant data (list_admin_catalog
  // doesn't fetch variants per row) — fetch the full item so the form can
  // pre-populate existing variant rows when editing.
  let existingVariants = [];
  if (isEdit && product.has_variants) {
    try {
      const fresh = await api(`/admin/catalog/${product.id}`);
      existingVariants = fresh.variants || [];
    } catch {
      existingVariants = [];
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
              <div class="relative">
                <span class="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-sm pointer-events-none">${escapeHtml(currencySymbol)}</span>
                <input type="number" id="prod-price" class="form-control pl-8" step="0.01" required value="${product?.price || 0}" />
              </div>
              <p class="text-[12px] text-muted mt-1">Priced in your store's default currency (${escapeHtml(businessCurrency)}) — set under Settings.</p>
            </div>
            <div class="form-group">
              <label class="form-label">Stock Quantity</label>
              <input type="number" id="prod-stock" class="form-control" value="${product?.stock_quantity ?? 100}" />
            </div>
            <div class="form-group">
              <label class="form-label">Category</label>
              <select id="prod-cat" class="form-control">
                <option value="">Select category...</option>
                ${CATALOG_CATEGORIES.map(c => `<option value="${escapeHtml(c)}" ${product?.category === c ? 'selected' : ''}>${escapeHtml(c)}</option>`).join('')}
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Sub-category</label>
              <select id="prod-subcat" class="form-control">
                ${subcategoriesFor(product?.category || CATALOG_CATEGORIES[0]).map(sc => `<option value="${escapeHtml(sc)}" ${product?.subcategory === sc ? 'selected' : ''}>${escapeHtml(sc)}</option>`).join('')}
              </select>
            </div>
          </div>

          <div class="p-3.5 rounded-xl border border-subtle bg-app/40 space-y-2.5">
            <label class="form-label font-semibold text-main m-0">Fulfillment</label>
            <p class="text-[12px] text-muted">How this product is delivered after payment — decides whether customers are asked for a delivery address, and what happens automatically once they pay.</p>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2" id="prod-fulfillment-cards">
              <label class="flex items-start gap-2 p-2.5 rounded-lg border cursor-pointer transition-all ${(product?.fulfillment_type || 'physical') === 'physical' ? 'border-brand bg-brand/5' : 'border-subtle bg-surface hover:bg-surface-hover'}">
                <input type="radio" name="prod-fulfillment-type" value="physical" ${(product?.fulfillment_type || 'physical') === 'physical' ? 'checked' : ''} class="mt-0.5" onchange="window.switchFulfillmentTypeUI('physical')" />
                <div>
                  <div class="font-semibold text-xs text-main">Physical</div>
                  <div class="text-[12px] text-muted">Ships to a delivery address</div>
                </div>
              </label>
              <label class="flex items-start gap-2 p-2.5 rounded-lg border cursor-pointer transition-all ${product?.fulfillment_type === 'digital' ? 'border-brand bg-brand/5' : 'border-subtle bg-surface hover:bg-surface-hover'}">
                <input type="radio" name="prod-fulfillment-type" value="digital" ${product?.fulfillment_type === 'digital' ? 'checked' : ''} class="mt-0.5" onchange="window.switchFulfillmentTypeUI('digital')" />
                <div>
                  <div class="font-semibold text-xs text-main">Digital</div>
                  <div class="text-[12px] text-muted">Instant link, no shipping</div>
                </div>
              </label>
              <label class="flex items-start gap-2 p-2.5 rounded-lg border cursor-pointer transition-all ${product?.fulfillment_type === 'service' ? 'border-brand bg-brand/5' : 'border-subtle bg-surface hover:bg-surface-hover'}">
                <input type="radio" name="prod-fulfillment-type" value="service" ${product?.fulfillment_type === 'service' ? 'checked' : ''} class="mt-0.5" onchange="window.switchFulfillmentTypeUI('service')" />
                <div>
                  <div class="font-semibold text-xs text-main">Service</div>
                  <div class="text-[12px] text-muted">No auto dispatch, just a merchant alert</div>
                </div>
              </label>
            </div>
            <div id="prod-fulfillment-digital-field" class="form-group ${product?.fulfillment_type === 'digital' ? '' : 'hidden'}">
              <label class="form-label">Digital Asset URL</label>
              <input type="text" id="prod-digital-asset-url" class="form-control text-xs" value="${escapeHtml(product?.digital_asset_url || '')}" placeholder="https://... (download link, license key page, etc.)" />
              <p class="text-[12px] text-muted mt-1">Sent to the customer automatically the moment they pay.</p>
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

          <div class="p-3.5 rounded-xl border border-subtle bg-app/40 space-y-2.5">
            <div class="flex items-center justify-between">
              <label class="form-label font-semibold text-main m-0">Variants</label>
              <button type="button" class="btn btn-secondary btn-sm" id="btn-add-variant">
                <i data-lucide="plus" class="w-3.5 h-3.5"></i> Add Variant
              </button>
            </div>
            <p class="text-[12px] text-muted">
              Optional. If a product has variants (size, color, etc.), customers must pick one before
              adding it to their cart. Leave empty to sell this product as a single item, as today.
            </p>
            <div id="variant-rows" class="space-y-2"></div>
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

  // Variant repeatable rows — each row is a small inline form (name, sku,
  // price override, stock). Keeps a hidden data-variant-id so an edited
  // existing row round-trips its id (so the backend updates it in place
  // instead of deleting + recreating), while a freshly-added row has no id
  // and is created new on save.
  const variantRowsEl = document.getElementById('variant-rows');

  function addVariantRow(variant) {
    const row = document.createElement('div');
    row.className = 'flex items-start gap-2 variant-row';
    if (variant?.id) row.dataset.variantId = variant.id;
    row.innerHTML = `
      <input type="text" class="form-control variant-name" placeholder="e.g. Large / Blue" value="${escapeHtml(variant?.name || '')}" style="flex: 2;" />
      <input type="text" class="form-control variant-sku" placeholder="SKU (optional)" value="${escapeHtml(variant?.sku || '')}" style="flex: 1.5;" />
      <input type="number" class="form-control variant-price" placeholder="Price override" step="0.01" value="${variant?.price_override ?? ''}" style="flex: 1;" />
      <input type="number" class="form-control variant-stock" placeholder="Stock" value="${variant?.stock_quantity ?? 100}" style="flex: 1;" />
      <button type="button" class="btn btn-icon btn-secondary btn-sm text-rose hover:bg-rose/10 btn-remove-variant" title="Remove variant">
        <i data-lucide="x" class="w-4 h-4"></i>
      </button>
    `;
    row.querySelector('.btn-remove-variant').addEventListener('click', () => row.remove());
    variantRowsEl.appendChild(row);
    if (window.lucide) lucide.createIcons();
  }

  (existingVariants || []).forEach(addVariantRow);
  document.getElementById('btn-add-variant').addEventListener('click', () => addVariantRow(null));

  document.getElementById('prod-cat').addEventListener('change', (e) => {
    const subcatSelect = document.getElementById('prod-subcat');
    const options = subcategoriesFor(e.target.value);
    subcatSelect.innerHTML = options.map(sc => `<option value="${escapeHtml(sc)}">${escapeHtml(sc)}</option>`).join('');
    // The category select is enhanced into a custom dropdown widget
    // (see initAllCustomSelects, called on every openModal) that only
    // reads the native <select>'s options once at build time — rebuilding
    // the native options above doesn't refresh what the widget itself
    // shows. Push the new option list into the sub-category widget
    // directly (keepValue=false: always reset to the new category's
    // first option, never silently keep an incompatible one from before).
    if (subcatSelect._customSelectInstance) {
      const newOpts = options.map(sc => ({ value: sc, label: sc }));
      subcatSelect._customSelectInstance.setOptions(newOpts, false);
      subcatSelect.value = subcatSelect._customSelectInstance.getValue();
    }
  });

  window.switchFulfillmentTypeUI = (type) => {
    document.getElementById('prod-fulfillment-digital-field')?.classList.toggle('hidden', type !== 'digital');
    document.querySelectorAll('input[name="prod-fulfillment-type"]').forEach(inp => {
      const card = inp.closest('label');
      if (card) {
        card.className = inp.value === type
          ? 'flex items-start gap-2 p-2.5 rounded-lg border cursor-pointer transition-all border-brand bg-brand/5'
          : 'flex items-start gap-2 p-2.5 rounded-lg border cursor-pointer transition-all border-subtle bg-surface hover:bg-surface-hover';
      }
    });
  };

  if (window.lucide) lucide.createIcons();

  document.getElementById('product-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const groupCheckboxes = document.querySelectorAll('input[name="prod-group"]:checked');
    const accessGroupIds = Array.from(groupCheckboxes).map(el => parseInt(el.value, 10));

    // Build the variants payload from whatever rows remain. Rows with a
    // blank name are ignored (treated as an accidentally-added empty row,
    // not an error) rather than rejecting the whole save.
    const variantRows = Array.from(document.querySelectorAll('.variant-row'));
    const variants = variantRows
      .map(row => {
        const name = row.querySelector('.variant-name').value.trim();
        if (!name) return null;
        const priceVal = row.querySelector('.variant-price').value;
        const v = {
          name,
          sku: row.querySelector('.variant-sku').value.trim() || null,
          price_override: priceVal !== '' ? parseFloat(priceVal) : null,
          stock_quantity: parseInt(row.querySelector('.variant-stock').value, 10) || 0,
          in_stock: (parseInt(row.querySelector('.variant-stock').value, 10) || 0) > 0,
        };
        if (row.dataset.variantId) v.id = parseInt(row.dataset.variantId, 10);
        return v;
      })
      .filter(Boolean);

    const fulfillmentType = document.querySelector('input[name="prod-fulfillment-type"]:checked')?.value || 'physical';

    const payload = {
      title: document.getElementById('prod-title').value.trim(),
      description: document.getElementById('prod-desc').value.trim() || null,
      price: parseFloat(document.getElementById('prod-price').value),
      category: document.getElementById('prod-cat').value || null,
      subcategory: document.getElementById('prod-subcat').value || null,
      stock_quantity: parseInt(document.getElementById('prod-stock').value, 10),
      image_url: document.getElementById('prod-img').value.trim() || null,
      access_group_ids: accessGroupIds,
      in_stock: parseInt(document.getElementById('prod-stock').value, 10) > 0,
      // Always included (not conditionally omitted) since the form's rows
      // always reflect the product's true current variant state — whether
      // pre-populated from an existing product or freshly empty for a new
      // one — so there's no "untouched, leave alone" case to preserve here.
      variants,
      fulfillment_type: fulfillmentType,
      digital_asset_url: fulfillmentType === 'digital' ? (document.getElementById('prod-digital-asset-url').value.trim() || null) : null,
      requires_shipping: fulfillmentType === 'physical',
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

const IMPORT_PROVIDER_LABELS = { bumpa: 'Bumpa', paystack: 'Paystack' };

function importCatalogModal(providers) {
  const available = Object.entries(providers || {}).filter(([, p]) => p?.configured);

  openModal(`
    <div class="modal-dialog max-w-md">
      <div class="modal-header">
        <h3 class="font-bold text-lg text-main">Import Catalog</h3>
        <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>
      <div class="modal-body space-y-3">
        <p class="text-sm text-muted">
          Choose a connected source to pull products from. New products are added;
          products already imported from that source are updated with the latest
          price, stock, and image.
        </p>
        <div id="import-provider-list">
          ${renderSelectCards({
            name: 'import-source',
            type: 'radio',
            items: available.map(([key, info]) => ({
              value: key,
              title: IMPORT_PROVIDER_LABELS[key] || key,
              badge: info.preview_count === null ? 'Count unavailable' : `${info.preview_count} product${info.preview_count === 1 ? '' : 's'} found`,
              badgeClass: 'badge-subtle',
            })),
            selectedValues: available.length === 1 ? [available[0][0]] : [],
            gridClass: 'space-y-2',
          })}
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal()">Cancel</button>
        <button type="button" class="btn btn-primary btn-sm" id="btn-confirm-import">
          <i data-lucide="download-cloud" class="w-4 h-4"></i> Confirm Import
        </button>
      </div>
    </div>
  `);
  if (window.lucide) lucide.createIcons();

  document.getElementById('btn-confirm-import').addEventListener('click', async (e) => {
    const selected = document.querySelector('input[name="import-source"]:checked');
    if (!selected) {
      showToast('Please choose a source to import from', 'error');
      return;
    }
    const btn = e.currentTarget;
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> Importing...`;
    if (window.lucide) lucide.createIcons();

    try {
      const result = await api('/admin/catalog/import', {
        method: 'POST',
        body: JSON.stringify({ source: selected.value }),
      });
      closeModal();
      showToast(`Imported ${result.imported} new, updated ${result.updated} existing products`, 'success');
      loadCatalogPage(document.getElementById('page-content'));
    } catch (err) {
      showToast(err.message || 'Import failed', 'error');
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      if (window.lucide) lucide.createIcons();
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