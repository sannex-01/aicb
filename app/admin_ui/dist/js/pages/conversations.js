import { state } from '../state.js';
import { api } from '../api.js';
import { navigate } from '../router.js';
import { showToast, escapeHtml, formatDate, skeletonPage } from '../utils.js';
import { createCustomSelect } from '../components/custom-select.js';

let currentThreadData = null;
let convSidebarOpen = true;
let currentSelectedSessionId = null;
let searchDebounceTimer = null;
let selectedAgentId = '';
let selectedChannel = '';

export async function loadConversationsPage(container) {
  container.innerHTML = skeletonPage({ stats: 0, rows: 8 });
  try {
    const [initialData, agentsList] = await Promise.all([
      api('/conversations?limit=50'),
      api('/agents').catch(() => []),
    ]);

    let sessions = initialData.items || [];
    const agents = agentsList || [];

    function renderSessionList(items) {
      const listContainer = document.getElementById('conv-session-list');
      const badgeCount = document.getElementById('conv-count-badge');
      if (badgeCount) badgeCount.textContent = items.length;

      if (!listContainer) return;

      if (items.length === 0) {
        listContainer.innerHTML = `
          <div class="p-8 text-center text-muted text-xs flex flex-col items-center justify-center gap-2">
            <i data-lucide="message-square-off" class="w-7 h-7 text-subtle"></i>
            <p class="font-medium text-main">No conversations found</p>
            <p class="text-[11px]">Try adjusting your search or filters.</p>
          </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
      }

      listContainer.innerHTML = items.map(s => {
        const isSelected = currentSelectedSessionId === s.id;
        const channelBadgeClass = s.channel === 'whatsapp' 
          ? 'badge-emerald' 
          : s.channel === 'telegram' 
            ? 'badge-sky' 
            : 'badge-subtle';

        const displayName = s.customer?.name || s.customer_identifier;
        const subText = s.customer?.phone_number || s.customer?.email || s.customer_identifier;

        return `
          <div id="session-item-${s.id}" class="p-3.5 cursor-pointer transition-colors border-b border-subtle/50 flex flex-col gap-1.5 ${isSelected ? 'bg-surface-hover' : 'hover:bg-surface-hover'}" onclick="window.loadConversationThread(${s.id})">
            <div class="flex justify-between items-start gap-2">
              <div class="flex items-center gap-2 min-w-0">
                <div class="w-6 h-6 rounded-full bg-brand/10 text-brand flex items-center justify-center text-[11px] font-bold flex-shrink-0">
                  ${escapeHtml((displayName.charAt(0) || 'U').toUpperCase())}
                </div>
                <span class="font-medium text-[14px] text-main truncate max-w-[200px]">
                  ${escapeHtml(displayName)}
                </span>
              </div>
              <span class="text-[12px] text-muted whitespace-nowrap">${formatDate(s.last_active_at)}</span>
            </div>

            <div class="flex items-center justify-between gap-2 pl-8">
              <span class="text-[12px] text-muted truncate max-w-[190px] font-mono">${escapeHtml(subText)}</span>
              <div class="flex items-center gap-1.5 flex-shrink-0">
                ${s.agent?.name ? `
                  <span class="badge badge-subtle text-[10px] py-0.5 px-1.5 truncate max-w-[95px]" title="Agent: ${escapeHtml(s.agent.name)}">
                    ${escapeHtml(s.agent.name)}
                  </span>
                ` : ''}
                <span class="badge ${channelBadgeClass} text-[10px] uppercase py-0.5 px-1.5">
                  ${escapeHtml(s.channel)}
                </span>
              </div>
            </div>
          </div>
        `;
      }).join('');

      if (window.lucide) lucide.createIcons();
    }

    async function applyFiltersAndReload() {
      const searchInput = document.getElementById('conv-search-input');
      const clearBtn = document.getElementById('conv-search-clear');
      const search = searchInput?.value?.trim() || '';

      if (clearBtn) {
        clearBtn.classList.toggle('hidden', !search);
      }

      const params = new URLSearchParams({ limit: '50' });
      if (selectedAgentId) params.set('agent_id', selectedAgentId);
      if (selectedChannel) params.set('channel', selectedChannel);
      if (search) params.set('search', search);

      const listContainer = document.getElementById('conv-session-list');
      if (listContainer) {
        listContainer.innerHTML = `<div class="p-8 text-center text-muted text-[14px]"><i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto text-brand mb-2"></i>Loading conversations...</div>`;
        if (window.lucide) lucide.createIcons();
      }

      try {
        const res = await api(`/conversations?${params.toString()}`);
        sessions = res.items || [];
        renderSessionList(sessions);
      } catch (err) {
        if (listContainer) {
          listContainer.innerHTML = `<div class="p-6 text-center text-rose-500 text-[14px]">Failed to filter conversations: ${escapeHtml(err.message)}</div>`;
        }
      }
    }

    container.innerHTML = `
      <div class="h-full min-h-[calc(100vh-48px)] flex-1 flex overflow-hidden rounded-xl border border-subtle bg-surface shadow-xs text-[14px]">
        
        <!-- Left Pane: Search, Filters & Session List (Widened to 380px) -->
        <div class="w-[380px] flex-shrink-0 border-r border-subtle flex flex-col bg-surface">
          
          <!-- Pane Header & Filter Controls -->
          <div class="p-3.5 border-b border-subtle bg-surface-elevated/40 space-y-3 flex-shrink-0">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <i data-lucide="message-square" class="w-4 h-4 text-brand"></i>
                <span class="font-bold text-[16px] text-main">Sessions</span>
              </div>
              <span class="badge badge-brand text-[10px] font-mono font-bold px-2 py-0.5" id="conv-count-badge">${sessions.length}</span>
            </div>

            <!-- Search Input (Normal Design System Input Size) -->
            <div class="relative flex items-center">
              <i data-lucide="search" class="w-4 h-4 absolute left-3 text-muted pointer-events-none"></i>
              <input type="text" id="conv-search-input" placeholder="Search name, phone, email..." class="form-control pl-9.5 pr-8 py-2 w-full text-[14px]" />
              <button id="conv-search-clear" class="hidden absolute right-2.5 text-muted hover:text-main p-1 cursor-pointer" title="Clear search">
                <i data-lucide="x" class="w-3.5 h-3.5"></i>
              </button>
            </div>

            <!-- Filters Row: Custom Agent Selector & Custom Channel Selector -->
            <div class="grid grid-cols-2 gap-2 pt-0.5">
              <div class="space-y-1">
                <label class="form-label-sm block text-[12px] font-bold text-muted uppercase tracking-wider">Agent</label>
                <div id="conv-agent-select-container"></div>
              </div>
              <div class="space-y-1">
                <label class="form-label-sm block text-[12px] font-bold text-muted uppercase tracking-wider">Channel</label>
                <div id="conv-channel-select-container"></div>
              </div>
            </div>
          </div>
          
          <!-- Scrollable Session List -->
          <div class="overflow-y-auto flex-1 divide-y divide-subtle/40" id="conv-session-list"></div>
        </div>

        <!-- Center Pane: Chat Thread View -->
        <div class="flex-1 flex flex-col bg-app min-w-0" id="thread-container">
          <div class="flex-1 flex items-center justify-center text-muted text-[14px] flex-col gap-3">
            <div class="w-12 h-12 rounded-xl bg-surface border border-subtle flex items-center justify-center text-muted/40 shadow-xs">
              <i data-lucide="message-square" class="w-6 h-6"></i>
            </div>
            <div class="text-center">
              <p class="font-semibold text-main text-[16px]">No Conversation Selected</p>
              <p class="text-[12px] text-muted mt-0.5">Select a customer session from the left to view message transcripts</p>
            </div>
          </div>
        </div>

        <!-- Right Pane: Collapsible Metadata Sidebar (Widened to 380px) -->
        <div id="conv-metadata-sidebar" class="${convSidebarOpen ? 'w-[380px]' : 'w-0 hidden'} flex-shrink-0 border-l border-subtle flex flex-col bg-surface transition-all duration-200 overflow-hidden">
          <div class="p-4 border-b border-subtle flex items-center justify-between bg-surface-elevated/40">
            <div class="flex items-center gap-2">
              <i data-lucide="info" class="w-4 h-4 text-brand"></i>
              <span class="font-bold text-[16px] text-main">Session Details</span>
            </div>
            <button class="p-1 rounded-md text-muted hover:text-main hover:bg-surface transition-colors cursor-pointer" onclick="window.toggleConvSidebar()" title="Close Details">
              <i data-lucide="x" class="w-4 h-4"></i>
            </button>
          </div>
          <div id="conv-metadata-content" class="flex-1 overflow-y-auto p-4 space-y-4 text-[14px]">
            <div class="text-muted text-[14px] text-center py-8">Select a conversation session to view full customer identity, state and metadata.</div>
          </div>
        </div>

      </div>
    `;

    renderSessionList(sessions);

    // Initialize Custom Selects
    const agentOptions = [
      { value: '', label: 'All Agents' },
      ...agents.map(a => ({ value: String(a.id), label: a.name }))
    ];

    createCustomSelect({
      container: '#conv-agent-select-container',
      id: 'conv-agent-custom-select',
      value: selectedAgentId,
      options: agentOptions,
      placeholder: 'All Agents',
      searchable: agents.length > 5,
      onChange: (val) => {
        selectedAgentId = val;
        applyFiltersAndReload();
      }
    });

    const channelOptions = [
      { value: '', label: 'All Channels' },
      { value: 'whatsapp', label: 'WhatsApp', icon: 'message-circle' },
      { value: 'telegram', label: 'Telegram', icon: 'send' },
      { value: 'widget', label: 'Widget', icon: 'globe' },
    ];

    createCustomSelect({
      container: '#conv-channel-select-container',
      id: 'conv-channel-custom-select',
      value: selectedChannel,
      options: channelOptions,
      placeholder: 'All Channels',
      searchable: false,
      onChange: (val) => {
        selectedChannel = val;
        applyFiltersAndReload();
      }
    });

    // Bind Search Events
    const searchInput = document.getElementById('conv-search-input');
    const searchClear = document.getElementById('conv-search-clear');

    if (searchInput) {
      searchInput.addEventListener('input', () => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(applyFiltersAndReload, 300);
      });
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          clearTimeout(searchDebounceTimer);
          applyFiltersAndReload();
        }
      });
    }

    if (searchClear) {
      searchClear.addEventListener('click', () => {
        if (searchInput) {
          searchInput.value = '';
          applyFiltersAndReload();
        }
      });
    }

    // Global toggle for the right metadata sidebar
    window.toggleConvSidebar = () => {
      convSidebarOpen = !convSidebarOpen;
      const sidebar = document.getElementById('conv-metadata-sidebar');
      const toggleBtn = document.getElementById('conv-sidebar-toggle-btn');
      if (sidebar) {
        if (convSidebarOpen) {
          sidebar.classList.remove('w-0', 'hidden');
          sidebar.classList.add('w-[380px]');
        } else {
          sidebar.classList.remove('w-[380px]');
          sidebar.classList.add('w-0', 'hidden');
        }
      }
      if (toggleBtn) {
        toggleBtn.classList.toggle('text-brand', convSidebarOpen);
      }
    };

    // Global loader for conversation thread
    window.loadConversationThread = async (sessionId) => {
      currentSelectedSessionId = sessionId;

      // Update active highlight in session list
      sessions.forEach(s => {
        const el = document.getElementById(`session-item-${s.id}`);
        if (el) {
          if (s.id === sessionId) {
            el.className = 'p-3.5 cursor-pointer transition-colors border-b border-subtle/50 flex flex-col gap-1.5 bg-surface-hover';
          } else {
            el.className = 'p-3.5 cursor-pointer transition-colors border-b border-subtle/50 flex flex-col gap-1.5 hover:bg-surface-hover';
          }
        }
      });

      const tc = document.getElementById('thread-container');
      tc.innerHTML = `<div class="flex-1 flex items-center justify-center text-muted text-[14px]"><i data-lucide="loader-2" class="w-6 h-6 animate-spin text-brand"></i></div>`;
      if (window.lucide) lucide.createIcons();
      
      try {
        const thread = await api(`/conversations/${sessionId}`);
        currentThreadData = thread;

        const displayName = thread.customer?.name || thread.customer_identifier || 'Customer';
        const channelBadgeClass = thread.channel === 'whatsapp' 
          ? 'badge-emerald' 
          : thread.channel === 'telegram' 
            ? 'badge-sky' 
            : 'badge-subtle';
        
        tc.innerHTML = `
          <!-- Thread Header -->
          <div class="h-14 px-5 border-b border-subtle bg-surface flex items-center justify-between flex-shrink-0">
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-8 h-8 rounded-full bg-brand/10 text-brand flex items-center justify-center font-bold text-[12px] flex-shrink-0 shadow-xs">
                ${escapeHtml((displayName.charAt(0) || 'U').toUpperCase())}
              </div>
              <div class="min-w-0">
                <div class="font-bold text-[16px] text-main truncate flex items-center gap-2">
                  ${escapeHtml(displayName)}
                  ${thread.customer?.phone_number ? `<span class="text-[12px] text-muted font-normal font-mono">(${escapeHtml(thread.customer.phone_number)})</span>` : ''}
                </div>
                <div class="text-[12px] text-muted truncate">${escapeHtml(thread.customer_identifier)}</div>
              </div>
            </div>

            <div class="flex items-center gap-2">
              ${thread.agent?.name ? `
                <span class="badge badge-brand text-[10px] flex items-center gap-1 font-medium">
                  <i data-lucide="bot" class="w-3.5 h-3.5"></i>
                  ${escapeHtml(thread.agent.name)}
                </span>
              ` : ''}
              <span class="badge ${channelBadgeClass} text-[10px] uppercase font-bold">
                ${escapeHtml(thread.channel)}
              </span>
              <button id="conv-sidebar-toggle-btn" class="p-1.5 rounded-lg text-muted hover:text-main hover:bg-surface-elevated transition-colors ${convSidebarOpen ? 'text-brand' : ''} cursor-pointer" onclick="window.toggleConvSidebar()" title="Toggle Session Details">
                <i data-lucide="panel-right" class="w-4 h-4"></i>
              </button>
            </div>
          </div>

          <!-- Message History -->
          <div class="flex-1 overflow-y-auto p-5 space-y-4">
            ${thread.messages.map(m => {
              const isUser = m.role === 'user';
              return `
                <div class="flex flex-col ${isUser ? 'items-end' : 'items-start'} group">
                  <div class="flex items-center gap-1.5 mb-1 px-1 text-[12px] text-muted">
                    <span class="font-semibold ${isUser ? 'text-main' : 'text-brand'}">${isUser ? 'Customer' : (thread.agent?.name || 'Assistant')}</span>
                    <span>•</span>
                    <span>${formatDate(m.created_at)}</span>
                  </div>
                  <div class="${isUser ? 'bg-brand text-white shadow-sm' : 'bg-surface border border-subtle text-main shadow-xs'} rounded-2xl px-4 py-2.5 text-[14px] max-w-[80%] whitespace-pre-wrap leading-relaxed">
                    ${escapeHtml(m.content)}
                  </div>
                </div>
              `;
            }).join('')}
            ${thread.messages.length === 0 ? `<div class="text-center text-muted text-[14px] py-12">No messages logged in this session.</div>` : ''}
          </div>
        `;

        // Populate Right Metadata Sidebar
        const metaContainer = document.getElementById('conv-metadata-content');
        if (metaContainer) {
          metaContainer.innerHTML = `
            <!-- Customer Section -->
            <div class="space-y-1.5">
              <span class="text-[12px] font-bold text-muted uppercase tracking-wider">Customer Identity</span>
              <div class="p-3 bg-surface-elevated rounded-xl border border-subtle/50 space-y-2">
                <div class="font-bold text-[16px] text-main">${thread.customer?.name ? escapeHtml(thread.customer.name) : 'Anonymous Customer'}</div>
                <div class="text-[12px] text-muted flex items-center gap-2">
                  <i data-lucide="phone" class="w-3.5 h-3.5 text-faint flex-shrink-0"></i>
                  <span class="font-mono">${escapeHtml(thread.customer?.phone_number || thread.customer_identifier)}</span>
                </div>
                ${thread.customer?.email ? `
                <div class="text-[12px] text-muted flex items-center gap-2">
                  <i data-lucide="mail" class="w-3.5 h-3.5 text-faint flex-shrink-0"></i>
                  <span>${escapeHtml(thread.customer.email)}</span>
                </div>` : ''}
              </div>
            </div>

            <!-- Agent Assigned Section -->
            ${thread.agent ? `
            <div class="space-y-1.5">
              <span class="text-[12px] font-bold text-muted uppercase tracking-wider">Assigned AI Agent</span>
              <div class="p-3 bg-surface-elevated rounded-xl border border-subtle/50 space-y-1.5">
                <div class="flex items-center gap-2">
                  <div class="w-6 h-6 rounded-lg bg-brand/10 text-brand flex items-center justify-center flex-shrink-0">
                    <i data-lucide="bot" class="w-3.5 h-3.5"></i>
                  </div>
                  <div>
                    <div class="font-bold text-[14px] text-main">${escapeHtml(thread.agent.name)}</div>
                    <div class="text-[12px] text-muted font-mono">${escapeHtml(thread.agent.slug)}</div>
                  </div>
                </div>
              </div>
            </div>
            ` : ''}

            <!-- Session Details Section -->
            <div class="space-y-1.5">
              <span class="text-[10px] font-bold text-muted uppercase tracking-wider">Session State</span>
              <div class="p-3 bg-surface-elevated rounded-xl border border-subtle/50 space-y-2 text-[12px]">
                <div class="flex justify-between items-center">
                  <span class="text-muted">Channel</span>
                  <span class="font-semibold text-main uppercase">${escapeHtml(thread.channel || 'N/A')}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-muted">Bot Mode</span>
                  <span class="badge badge-brand text-[10px]">${escapeHtml(thread.bot_mode || 'conversational')}</span>
                </div>
                ${thread.active_flow ? `
                <div class="flex justify-between items-center">
                  <span class="text-muted">Active Flow</span>
                  <span class="font-medium text-main">${escapeHtml(thread.active_flow)}</span>
                </div>` : ''}
                ${thread.current_step ? `
                <div class="flex justify-between items-center">
                  <span class="text-muted">Current Step</span>
                  <span class="font-medium text-main">${escapeHtml(thread.current_step)}</span>
                </div>` : ''}
                <div class="flex justify-between items-center">
                  <span class="text-muted">Total Messages</span>
                  <span class="font-mono font-bold text-main">${thread.messages.length}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-muted">Started</span>
                  <span class="text-muted text-[11px]">${formatDate(thread.created_at)}</span>
                </div>
                <div class="flex justify-between items-center">
                  <span class="text-muted">Last Active</span>
                  <span class="text-muted text-[11px]">${formatDate(thread.last_active_at)}</span>
                </div>
              </div>
            </div>

            <!-- Session Key -->
            <div class="space-y-1">
              <span class="text-[10px] font-bold text-muted uppercase tracking-wider">Session Key</span>
              <div class="p-2 bg-app rounded-lg text-[10px] font-mono text-muted break-all select-all border border-subtle/30">
                ${escapeHtml(thread.session_key || `session_${thread.id}`)}
              </div>
            </div>
          `;
        }

        if (window.lucide) lucide.createIcons();
        
        // Auto scroll chat to bottom
        const scrollArea = tc.querySelector('.flex-1.overflow-y-auto');
        if (scrollArea) scrollArea.scrollTop = scrollArea.scrollHeight;

      } catch (e) {
        tc.innerHTML = `<div class="flex-1 flex items-center justify-center text-rose text-sm">${escapeHtml(e.message)}</div>`;
      }
    };

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    container.innerHTML = `<div class="p-8 text-center text-rose">Failed to load conversations: ${escapeHtml(err.message)}</div>`;
  }
}
