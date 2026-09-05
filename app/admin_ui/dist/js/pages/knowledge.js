import { state } from '../state.js';
import { api } from '../api.js';
import { navigate } from '../router.js';
import { showToast, openModal, closeModal, openConfirmModal, escapeHtml, formatCurrency, formatDate, skeletonPage, renderDataTable } from '../utils.js';

export async function loadKnowledgePage(container) {
  container.innerHTML = skeletonPage({ stats: 0, rows: 6 });
  try {
    const isAdmin = ['admin', 'super_admin'].includes(state.user?.role);
    const data = await api('/admin/knowledge');
    const items = data.items || [];

    container.innerHTML = `
      <div class="space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h1 class="text-2xl font-bold">Knowledge Base (RAG)</h1>
            <p class="text-sm text-muted">Official business information used by AI agents for grounded responses with tag scoping</p>
          </div>
          ${isAdmin ? `
          <button class="btn btn-primary btn-sm" id="btn-create-doc">
            <i data-lucide="plus" class="w-4 h-4"></i> Add Document
          </button>
          ` : ''}
        </div>

        <div id="knowledge-table-container"></div>
      </div>
    `;

    const columns = [
      {
        key: 'title',
        label: 'Title',
        sortable: true,
        render: (val) => `<span class="font-bold text-main">${escapeHtml(val)}</span>`
      },
      {
        key: 'category',
        label: 'Category',
        sortable: true,
        render: (val) => `<span class="badge badge-subtle">${escapeHtml(val || 'General')}</span>`
      },
      {
        key: 'content',
        label: 'Content Snippet',
        sortable: false,
        render: (val) => `<span class="text-xs text-muted line-clamp-2 max-w-md">${escapeHtml(val || '')}</span>`
      },
      {
        key: 'access_tags',
        label: 'Access Scope',
        sortable: false,
        render: (val) => {
          const tags = Array.isArray(val) ? val : [];
          return tags.length 
            ? tags.map(t => `<span class="badge badge-sky mr-1 text-[12px]">${escapeHtml(t)}</span>`).join('') 
            : '<span class="badge badge-subtle text-[12px]">Public (All Agents)</span>';
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
            <button class="btn btn-secondary btn-sm" onclick='window.editKnowledgeModal(${JSON.stringify(row).replace(/'/g, "&apos;")})'>
              <i data-lucide="edit-2" class="w-3.5 h-3.5"></i> Edit
            </button>
            <button class="btn btn-icon btn-secondary btn-sm text-rose hover:bg-rose/10" title="Delete Document" onclick='window.deleteKnowledgeDoc(${row.id}, "${escapeHtml(row.title)}")'>
              <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
          </div>
        `
      });
    }

    renderDataTable('#knowledge-table-container', {
      data: items,
      searchPlaceholder: 'Search knowledge docs by title, category, or content...',
      defaultSort: { key: 'title', dir: 'asc' },
      pageSize: 15,
      columns
    });

    const createBtn = document.getElementById('btn-create-doc');
    if (createBtn) {
      createBtn.addEventListener('click', () => window.editKnowledgeModal(null));
    }
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load knowledge base: ${escapeHtml(err.message)}</div>`;
  }
}

function editKnowledgeModal(doc) {
  const isEdit = Boolean(doc);
  openModal(`
    <div class="modal-dialog">
      <div class="modal-header">
        <h3 class="font-bold text-lg text-main">${isEdit ? 'Edit Knowledge Document' : 'Add Knowledge Document'}</h3>
        <button class="btn btn-icon btn-secondary btn-sm" onclick="closeModal()"><i data-lucide="x" class="w-4 h-4"></i></button>
      </div>
      <form id="knowledge-form">
        <div class="modal-body space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div class="form-group col-span-2 sm:col-span-1">
              <label class="form-label">Document Title</label>
              <input type="text" id="doc-title" class="form-control" required value="${escapeHtml(doc?.title || '')}" placeholder="Return & Refund Policy" />
            </div>
            <div class="form-group col-span-2 sm:col-span-1">
              <label class="form-label">Category</label>
              <input type="text" id="doc-cat" class="form-control" value="${escapeHtml(doc?.category || '')}" placeholder="Policies, FAQ, Shipping" />
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Document Content (Markdown supported)</label>
            <textarea id="doc-content" class="form-control font-mono text-xs" rows="6" required placeholder="Customers may return undamaged items within 14 days...">${escapeHtml(doc?.content || '')}</textarea>
          </div>
          <div class="form-group">
            <label class="form-label">Access Tags (comma-separated, empty = public to all agents)</label>
            <input type="text" id="doc-tags" class="form-control" value="${escapeHtml((doc?.access_tags || []).join(', '))}" placeholder="support, billing, enterprise" />
          </div>
        </div>
        <div class="modal-footer">
          ${isEdit ? `<button type="button" class="btn btn-danger btn-sm mr-auto" onclick="window.deleteKnowledgeDoc(${doc.id}, '${escapeHtml(doc.title)}')">Delete</button>` : ''}
          <button type="button" class="btn btn-secondary btn-sm" onclick="closeModal()">Cancel</button>
          <button type="submit" class="btn btn-primary btn-sm">${isEdit ? 'Save Document' : 'Add Document'}</button>
        </div>
      </form>
    </div>
  `);

  document.getElementById('knowledge-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const rawTags = document.getElementById('doc-tags').value;
    const tags = rawTags.split(',').map(t => t.trim()).filter(Boolean);

    const payload = {
      title: document.getElementById('doc-title').value,
      category: document.getElementById('doc-cat').value || null,
      content: document.getElementById('doc-content').value,
      access_tags: tags,
    };

    try {
      if (isEdit) {
        await api(`/admin/knowledge/${doc.id}`, { method: 'PUT', body: JSON.stringify(payload) });
        showToast('Document updated', 'success');
      } else {
        await api('/admin/knowledge', { method: 'POST', body: JSON.stringify(payload) });
        showToast('Document created', 'success');
      }
      closeModal();
      loadKnowledgePage(document.getElementById('page-content'));
    } catch {}
  });
}

function deleteKnowledgeDoc(docId, docTitle = '') {
  openConfirmModal({
    title: 'Delete Knowledge Document',
    message: `Are you sure you want to delete "${docTitle || 'this document'}"? Agents will no longer retrieve information from this source.`,
    confirmText: 'Delete Document',
    confirmType: 'danger',
    onConfirm: async () => {
      await api(`/admin/knowledge/${docId}`, { method: 'DELETE' });
      showToast('Knowledge doc deleted', 'success');
      loadKnowledgePage(document.getElementById('page-content'));
    }
  });
}

window.editKnowledgeModal = editKnowledgeModal;
window.deleteKnowledgeDoc = deleteKnowledgeDoc;