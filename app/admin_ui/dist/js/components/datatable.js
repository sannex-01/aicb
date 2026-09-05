import { escapeHtml, formatDate } from '../utils.js';

/**
 * Reusable DataTable Component with sorting, date-aware ordering, search filtering, and pagination.
 */
export class DataTable {
  /**
   * @param {Object} options
   * @param {HTMLElement|string} options.container - Container element or selector
   * @param {Array<Object>} options.data - Data rows array
   * @param {Array<Object>} options.columns - Column configurations
   *   column: {
   *     key: string,
   *     label: string,
   *     sortable?: boolean, // default true (if not action column)
   *     type?: 'string' | 'number' | 'date' | 'custom',
   *     sortValue?: (row) => any,
   *     render?: (val, row, index) => string,
   *     align?: 'left' | 'center' | 'right',
   *     class?: string,
   *     headerClass?: string,
   *     width?: string
   *   }
   * @param {Object} [options.defaultSort] - { key: string, dir: 'asc' | 'desc' }
   * @param {boolean} [options.searchable] - Show built-in search input (default true)
   * @param {string} [options.searchPlaceholder] - Placeholder for search (default 'Search...')
   * @param {number} [options.pageSize] - Rows per page (default 15, or 0 / null for no pagination)
   * @param {string} [options.emptyMessage] - Message when no records found
   * @param {string} [options.tableClass] - Extra CSS classes for table
   */
  constructor(options) {
    this.container = typeof options.container === 'string' 
      ? document.querySelector(options.container) 
      : options.container;

    if (!this.container) {
      console.error('DataTable: container element not found', options.container);
      return;
    }

    this.originalData = Array.isArray(options.data) ? [...options.data] : [];
    this.filteredData = [...this.originalData];
    this.columns = options.columns || [];
    
    this.defaultSort = options.defaultSort || null;
    this.sortKey = this.defaultSort?.key || null;
    this.sortDir = this.defaultSort?.dir || 'asc';
    
    this.searchable = options.searchable !== false;
    this.searchPlaceholder = options.searchPlaceholder || 'Search records...';
    this.searchQuery = '';
    
    this.pageSize = options.pageSize !== undefined ? options.pageSize : 15;
    this.currentPage = 1;
    this.emptyMessage = options.emptyMessage || 'No records found.';
    this.tableClass = options.tableClass || 'data-table';
    
    this.uid = 'dt_' + Math.random().toString(36).substring(2, 9);

    if (this.sortKey) {
      this.sortData();
    }

    this.render();
  }

  setData(newData) {
    this.originalData = Array.isArray(newData) ? [...newData] : [];
    this.applyFilter();
  }

  applyFilter() {
    if (!this.searchQuery.trim()) {
      this.filteredData = [...this.originalData];
    } else {
      const q = this.searchQuery.toLowerCase().trim();
      this.filteredData = this.originalData.filter(row => {
        return this.columns.some(col => {
          if (col.key === 'actions') return false;
          let val = row[col.key];
          if (typeof col.sortValue === 'function') {
            val = col.sortValue(row);
          }
          if (val === null || val === undefined) return false;
          return String(val).toLowerCase().includes(q);
        });
      });
    }

    if (this.sortKey) {
      this.sortData();
    }

    this.currentPage = 1;
    this.renderBodyAndPagination();
  }

  handleSort(columnKey) {
    const col = this.columns.find(c => c.key === columnKey);
    if (!col || col.sortable === false || col.key === 'actions') return;

    if (this.sortKey === columnKey) {
      if (this.sortDir === 'asc') {
        this.sortDir = 'desc';
      } else {
        // Third click cancels sort
        this.sortKey = null;
        this.sortDir = 'asc';
      }
    } else {
      this.sortKey = columnKey;
      this.sortDir = 'asc';
    }

    if (this.sortKey) {
      this.sortData();
    } else {
      // Revert to original insertion / filter order
      if (!this.searchQuery.trim()) {
        this.filteredData = [...this.originalData];
      } else {
        const q = this.searchQuery.toLowerCase().trim();
        this.filteredData = this.originalData.filter(row => {
          return this.columns.some(c => {
            if (c.key === 'actions') return false;
            let val = row[c.key];
            if (typeof c.sortValue === 'function') {
              val = c.sortValue(row);
            }
            if (val === null || val === undefined) return false;
            return String(val).toLowerCase().includes(q);
          });
        });
      }
    }
    this.render();
  }

  sortData() {
    if (!this.sortKey) return;
    const col = this.columns.find(c => c.key === this.sortKey);
    if (!col) return;

    const isDate = col.type === 'date' || 
                   this.sortKey.endsWith('_at') || 
                   this.sortKey.endsWith('date') || 
                   this.sortKey.endsWith('time');

    const isNumber = col.type === 'number' || 
                     this.sortKey.includes('amount') || 
                     this.sortKey.includes('price') || 
                     this.sortKey.includes('count') || 
                     this.sortKey.includes('total') || 
                     this.sortKey.includes('stock');

    this.filteredData.sort((a, b) => {
      let valA = a[this.sortKey];
      let valB = b[this.sortKey];

      if (typeof col.sortValue === 'function') {
        valA = col.sortValue(a);
        valB = col.sortValue(b);
      }

      // Handle nulls / undefined
      if (valA === null || valA === undefined) return this.sortDir === 'asc' ? 1 : -1;
      if (valB === null || valB === undefined) return this.sortDir === 'asc' ? -1 : 1;

      if (isDate) {
        const timeA = new Date(valA).getTime() || 0;
        const timeB = new Date(valB).getTime() || 0;
        return this.sortDir === 'asc' ? timeA - timeB : timeB - timeA;
      }

      if (isNumber) {
        const numA = typeof valA === 'number' ? valA : (parseFloat(valA) || 0);
        const numB = typeof valB === 'number' ? valB : (parseFloat(valB) || 0);
        return this.sortDir === 'asc' ? numA - numB : numB - numA;
      }

      const strA = String(valA).toLowerCase();
      const strB = String(valB).toLowerCase();
      return this.sortDir === 'asc' ? strA.localeCompare(strB) : strB.localeCompare(strA);
    });
  }

  getPaginatedRows() {
    if (!this.pageSize || this.pageSize <= 0) {
      return this.filteredData;
    }
    const start = (this.currentPage - 1) * this.pageSize;
    return this.filteredData.slice(start, start + this.pageSize);
  }

  getTotalPages() {
    if (!this.pageSize || this.pageSize <= 0) return 1;
    return Math.ceil(this.filteredData.length / this.pageSize) || 1;
  }

  render() {
    this.container.innerHTML = `
      <div class="space-y-3" id="${this.uid}-root">
        ${this.searchable ? `
        <div class="flex items-center justify-between gap-4">
          <div class="relative flex-1 max-w-xs">
            <i data-lucide="search" class="w-4 h-4 text-faint absolute left-3 top-1/2 -translate-y-1/2"></i>
            <input 
              type="text" 
              id="${this.uid}-search-input" 
              class="form-control text-xs pl-9 pr-3 py-2 bg-surface border border-subtle rounded-lg focus:border-brand" 
              placeholder="${escapeHtml(this.searchPlaceholder)}"
              value="${escapeHtml(this.searchQuery)}"
            />
          </div>
          <div class="text-xs text-muted font-medium">
            <span>${this.filteredData.length}</span> ${this.filteredData.length === 1 ? 'record' : 'records'}
          </div>
        </div>
        ` : ''}

        <div class="card p-0 overflow-hidden border border-subtle shadow-sm bg-surface">
          <div class="table-container">
            <table class="${this.tableClass} w-full text-left">
              <thead>
                <tr>
                  ${this.columns.map(col => {
                    const isSortable = col.sortable !== false && col.key !== 'actions';
                    const isSorted = this.sortKey === col.key;
                    const alignClass = col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left';
                    const styleWidth = col.width ? `style="width: ${col.width}"` : '';

                    return `
                      <th 
                        class="px-4 py-3 ${alignClass} ${col.headerClass || ''} ${isSortable ? 'cursor-pointer select-none hover:bg-surface-hover/80 transition-colors group' : ''}" 
                        ${styleWidth}
                        ${isSortable ? `data-sort-key="${escapeHtml(col.key)}"` : ''}
                      >
                        <div class="inline-flex items-center gap-1.5 ${col.align === 'right' ? 'justify-end' : col.align === 'center' ? 'justify-center' : 'justify-start'}">
                          <span class="font-semibold text-[11px] uppercase tracking-wider text-muted group-hover:text-main transition-colors">${escapeHtml(col.label)}</span>
                          ${isSortable ? `
                            <span class="inline-flex items-center">
                              ${isSorted 
                                ? (this.sortDir === 'asc' 
                                  ? '<i data-lucide="arrow-up" class="w-3.5 h-3.5 text-brand"></i>' 
                                  : '<i data-lucide="arrow-down" class="w-3.5 h-3.5 text-brand"></i>')
                                : '<i data-lucide="chevrons-up-down" class="w-3 h-3 text-faint opacity-40 group-hover:opacity-100 transition-opacity"></i>'
                              }
                            </span>
                          ` : ''}
                        </div>
                      </th>
                    `;
                  }).join('')}
                </tr>
              </thead>
              <tbody id="${this.uid}-tbody" class="divide-y divide-subtle/60">
                ${this.renderRowsHtml()}
              </tbody>
            </table>
          </div>

          <div id="${this.uid}-pagination" class="border-t border-subtle px-4 py-3 bg-surface-elevated/40 flex items-center justify-between text-xs text-muted">
            ${this.renderPaginationHtml()}
          </div>
        </div>
      </div>
    `;

    this.attachEventListeners();
    if (window.lucide) lucide.createIcons();
  }

  renderRowsHtml() {
    const rows = this.getPaginatedRows();
    if (rows.length === 0) {
      return `
        <tr>
          <td colspan="${this.columns.length}" class="px-4 py-12 text-center text-muted text-xs">
            <div class="flex flex-col items-center justify-center gap-2">
              <i data-lucide="inbox" class="w-7 h-7 text-faint opacity-40"></i>
              <span>${escapeHtml(this.emptyMessage)}</span>
            </div>
          </td>
        </tr>
      `;
    }

    return rows.map((row, rowIndex) => {
      const actualIndex = (this.currentPage - 1) * (this.pageSize || 0) + rowIndex;
      return `
        <tr class="hover:bg-surface-hover/60 transition-colors">
          ${this.columns.map(col => {
            const alignClass = col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left';
            let cellContent = '';

            if (typeof col.render === 'function') {
              cellContent = col.render(row[col.key], row, actualIndex);
            } else {
              const val = row[col.key];
              if (val === null || val === undefined) {
                cellContent = '<span class="text-faint">—</span>';
              } else if (col.type === 'date') {
                cellContent = formatDate(val);
              } else {
                cellContent = escapeHtml(String(val));
              }
            }

            return `
              <td class="px-4 py-3 ${alignClass} ${col.class || ''}">
                ${cellContent}
              </td>
            `;
          }).join('')}
        </tr>
      `;
    }).join('');
  }

  renderPaginationHtml() {
    const total = this.filteredData.length;
    if (total === 0) {
      return `<span>0 entries</span>`;
    }

    const totalPages = this.getTotalPages();
    const start = (this.currentPage - 1) * this.pageSize + 1;
    const end = Math.min(start + this.pageSize - 1, total);

    return `
      <div>
        Showing <span class="font-semibold text-main">${start}</span> to <span class="font-semibold text-main">${end}</span> of <span class="font-semibold text-main">${total}</span> entries
      </div>
      ${totalPages > 1 ? `
      <div class="flex items-center gap-1.5">
        <button 
          type="button" 
          id="${this.uid}-btn-prev" 
          class="btn btn-secondary btn-sm px-2.5 py-1 text-xs ${this.currentPage === 1 ? 'opacity-40 cursor-not-allowed' : ''}"
          ${this.currentPage === 1 ? 'disabled' : ''}
        >
          <i data-lucide="chevron-left" class="w-3.5 h-3.5"></i> Prev
        </button>
        <span class="px-2 py-1 font-medium text-main">
          ${this.currentPage} / ${totalPages}
        </span>
        <button 
          type="button" 
          id="${this.uid}-btn-next" 
          class="btn btn-secondary btn-sm px-2.5 py-1 text-xs ${this.currentPage === totalPages ? 'opacity-40 cursor-not-allowed' : ''}"
          ${this.currentPage === totalPages ? 'disabled' : ''}
        >
          Next <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i>
        </button>
      </div>
      ` : ''}
    `;
  }

  renderBodyAndPagination() {
    const tbody = document.getElementById(`${this.uid}-tbody`);
    const pagination = document.getElementById(`${this.uid}-pagination`);
    if (tbody) tbody.innerHTML = this.renderRowsHtml();
    if (pagination) pagination.innerHTML = this.renderPaginationHtml();
    this.attachPaginationListeners();
    if (window.lucide) lucide.createIcons();
  }

  attachEventListeners() {
    const root = document.getElementById(`${this.uid}-root`);
    if (!root) return;

    // Search input
    const searchInput = document.getElementById(`${this.uid}-search-input`);
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        this.searchQuery = e.target.value;
        this.applyFilter();
      });
    }

    // Column sorting headers
    const sortHeaders = root.querySelectorAll('th[data-sort-key]');
    sortHeaders.forEach(th => {
      th.addEventListener('click', () => {
        const key = th.getAttribute('data-sort-key');
        this.handleSort(key);
      });
    });

    this.attachPaginationListeners();
  }

  attachPaginationListeners() {
    const prevBtn = document.getElementById(`${this.uid}-btn-prev`);
    const nextBtn = document.getElementById(`${this.uid}-btn-next`);

    if (prevBtn && this.currentPage > 1) {
      prevBtn.addEventListener('click', () => {
        this.currentPage--;
        this.renderBodyAndPagination();
      });
    }

    if (nextBtn && this.currentPage < this.getTotalPages()) {
      nextBtn.addEventListener('click', () => {
        this.currentPage++;
        this.renderBodyAndPagination();
      });
    }
  }
}

/**
 * Convenient functional helper to create and mount a DataTable.
 */
export function renderDataTable(container, options) {
  return new DataTable({ container, ...options });
}
