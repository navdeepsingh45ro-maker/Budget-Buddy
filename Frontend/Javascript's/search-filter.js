// ─────────────────────────────────────────────────────────────
//  search-filter.js — BudgetBuddy reusable Search, Filter, Sort
//  Shared component used by Expense History and Budget History.
//  Depends on: Tailwind CSS classes from parent page.
// ─────────────────────────────────────────────────────────────

/**
 * Creates and manages a Search / Filter / Sort toolbar.
 *
 * Usage:
 *   const sf = new SearchFilterToolbar({
 *       containerId: 'sf-toolbar',
 *       onFilterChange: (filters) => { ... },
 *       features: { search: true, category: true, dateRange: true, amountRange: true, sort: true }
 *   });
 */
class SearchFilterToolbar {
    constructor(options) {
        this.container = document.getElementById(options.containerId);
        this.onFilterChange = options.onFilterChange || (() => {});
        this.onExportClick = options.onExportClick || (() => {});
        this.features = Object.assign(
            { search: true, category: true, dateRange: true, amountRange: true, sort: true, export: false },
            options.features || {}
        );
        this.sortOptions = options.sortOptions || [
            { value: 'newest', label: 'Newest First' },
            { value: 'oldest', label: 'Oldest First' },
            { value: 'highest', label: 'Highest Amount' },
            { value: 'lowest', label: 'Lowest Amount' },
        ];
        this.categories = options.categories || [
            'Food','Transport','Entertainment','Shopping','Bills','Health',
            'Education','Subscriptions','EMI Loans','Rent','Investments',
            'Savings','Travel','Family','Personal Care','Gifts','Donations',
            'Insurance','Taxes','Other'
        ];

        this.storageKey = `budgetbuddy_filters_${options.containerId}`;

        // State
        const defaultFilters = { search: '', category: '', start_date: '', end_date: '', min_amount: '', max_amount: '', sort: 'newest' };
        this.filters = this._loadState() || defaultFilters;
        this.filterPanelOpen = false;
        this.debounceTimer = null;

        this._render();
        this._syncInputs();
        this._renderChips();
        this._bindEvents();
        
        // Notify parent of initial loaded state
        if (this._loadState()) {
             setTimeout(() => this.onFilterChange(this.getFilters()), 0);
        }
    }

    // ── Storage ───────────────────────────────────────────────
    _loadState() {
        try {
            const saved = localStorage.getItem(this.storageKey);
            return saved ? JSON.parse(saved) : null;
        } catch (e) {
            return null;
        }
    }

    _saveState() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.filters));
        } catch (e) {
            console.warn("Could not save filters to localStorage");
        }
    }

    // ── Public API ────────────────────────────────────────────
    getFilters() { return { ...this.filters }; }

    clearAll() {
        this.filters = { search: '', category: '', start_date: '', end_date: '', min_amount: '', max_amount: '', sort: 'newest' };
        this._saveState();
        this._syncInputs();
        this._renderChips();
        this.onFilterChange(this.getFilters());
    }

    // ── Render ────────────────────────────────────────────────
    _render() {
        if (!this.container) return;

        this.container.innerHTML = `
            <!-- Row 1: Search + Filter + Sort -->
            <div class="flex flex-wrap gap-2 items-center">
                ${this.features.search ? `
                <div class="relative w-full basis-full sm:w-auto sm:basis-auto sm:flex-1">
                    <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">search</span>
                    <input id="sf-search" type="text" placeholder="Search expenses..."
                        class="w-full pl-10 pr-4 py-2.5 bg-surface-container-lowest border border-outline-variant/30 rounded-xl text-body-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all" />
                </div>` : ''}

                ${(this.features.dateRange || this.features.amountRange || this.features.category) ? `
                <button id="sf-filter-btn"
                    class="relative flex items-center gap-1.5 px-3.5 py-2.5 bg-surface-container-lowest border border-outline-variant/30 rounded-xl text-body-sm font-medium text-on-surface-variant hover:bg-surface-container-low active:scale-95 transition-all">
                    <span class="material-symbols-outlined text-[18px]">tune</span>
                    <span class="hidden sm:inline">Filters</span>
                    <span id="sf-filter-badge" class="hidden absolute -top-1.5 -right-1.5 w-5 h-5 bg-primary text-on-primary text-[10px] font-bold rounded-full flex items-center justify-center">0</span>
                </button>` : ''}

                ${this.features.sort ? `
                <div class="relative">
                    <select id="sf-sort"
                        class="appearance-none pl-3 pr-8 py-2.5 bg-surface-container-lowest border border-outline-variant/30 rounded-xl text-body-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all cursor-pointer">
                        ${this.sortOptions.map(o => `<option value="${escapeHtml(o.value)}">${escapeHtml(o.label)}</option>`).join('')}
                    </select>
                    <span class="material-symbols-outlined absolute right-2 top-1/2 -translate-y-1/2 text-outline text-[18px] pointer-events-none">unfold_more</span>
                </div>` : ''}

                ${this.features.export ? `
                <button id="sf-export-btn" title="Export Data" class="relative flex items-center gap-1.5 px-3.5 py-2.5 bg-primary/10 border border-primary/20 rounded-xl text-body-sm font-medium text-primary hover:bg-primary/20 active:scale-95 transition-all">
                    <span class="material-symbols-outlined text-[18px]">download</span>
                    <span class="hidden md:inline">Export</span>
                </button>` : ''}
            </div>

            <!-- Active Filter Chips -->
            <div id="sf-chips" class="flex flex-wrap gap-2 mt-2 empty:mt-0"></div>

            <!-- Expandable Filter Panel -->
            <div id="sf-panel" class="hidden mt-3 bg-surface-container-lowest border border-outline-variant/30 rounded-2xl p-4 space-y-4 transition-all premium-shadow">
                ${this.features.category ? `
                <div>
                    <label class="text-[12px] font-bold text-on-surface-variant uppercase tracking-wider mb-1.5 block">Category</label>
                    <select id="sf-category"
                        class="w-full px-3 py-2.5 bg-surface-container-low border border-outline-variant/20 rounded-xl text-body-sm focus:outline-none focus:ring-2 focus:ring-primary/20">
                        <option value="">All Categories</option>
                        ${this.categories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('')}
                    </select>
                </div>` : ''}

                ${this.features.dateRange ? `
                <div>
                    <label class="text-[12px] font-bold text-on-surface-variant uppercase tracking-wider mb-1.5 block">Date Range</label>
                    <div class="grid grid-cols-2 gap-2">
                        <input id="sf-start-date" type="date" class="px-3 py-2.5 bg-surface-container-low border border-outline-variant/20 rounded-xl text-body-sm focus:outline-none focus:ring-2 focus:ring-primary/20" />
                        <input id="sf-end-date" type="date" class="px-3 py-2.5 bg-surface-container-low border border-outline-variant/20 rounded-xl text-body-sm focus:outline-none focus:ring-2 focus:ring-primary/20" />
                    </div>
                </div>` : ''}

                ${this.features.amountRange ? `
                <div>
                    <label class="text-[12px] font-bold text-on-surface-variant uppercase tracking-wider mb-1.5 block">Amount Range</label>
                    <div class="grid grid-cols-2 gap-2">
                        <input id="sf-min-amount" type="number" placeholder="Min ₹" min="0" class="px-3 py-2.5 bg-surface-container-low border border-outline-variant/20 rounded-xl text-body-sm focus:outline-none focus:ring-2 focus:ring-primary/20" />
                        <input id="sf-max-amount" type="number" placeholder="Max ₹" min="0" class="px-3 py-2.5 bg-surface-container-low border border-outline-variant/20 rounded-xl text-body-sm focus:outline-none focus:ring-2 focus:ring-primary/20" />
                    </div>
                </div>` : ''}

                <div class="flex gap-2 pt-1">
                    <button id="sf-apply-btn" class="flex-1 bg-primary text-on-primary py-2.5 rounded-xl font-label-md text-label-md hover:opacity-90 active:scale-95 transition-all">Apply Filters</button>
                    <button id="sf-clear-btn" class="px-4 py-2.5 border border-outline-variant/30 rounded-xl text-body-sm text-on-surface-variant hover:bg-surface-container-low active:scale-95 transition-all">Clear</button>
                </div>
            </div>
        `;
    }

    // ── Bind ──────────────────────────────────────────────────
    _bindEvents() {
        const searchEl   = document.getElementById('sf-search');
        const filterBtn  = document.getElementById('sf-filter-btn');
        const sortEl     = document.getElementById('sf-sort');
        const applyBtn   = document.getElementById('sf-apply-btn');
        const clearBtn   = document.getElementById('sf-clear-btn');
        const exportBtn  = document.getElementById('sf-export-btn');

        if (exportBtn) {
            exportBtn.addEventListener('click', () => {
                this.onExportClick(this.getFilters());
            });
        }

        if (searchEl) {
            searchEl.addEventListener('input', () => {
                clearTimeout(this.debounceTimer);
                this.debounceTimer = setTimeout(() => {
                    this.filters.search = searchEl.value.trim();
                    this._saveState();
                    this._renderChips();
                    this.onFilterChange(this.getFilters());
                }, 300);
            });
        }

        if (filterBtn) {
            filterBtn.addEventListener('click', () => {
                this.filterPanelOpen = !this.filterPanelOpen;
                const panel = document.getElementById('sf-panel');
                if (panel) panel.classList.toggle('hidden', !this.filterPanelOpen);
            });
        }

        if (sortEl) {
            sortEl.addEventListener('change', () => {
                this.filters.sort = sortEl.value;
                this._saveState();
                this.onFilterChange(this.getFilters());
            });
        }

        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this._readPanelInputs();
                this._saveState();
                this._renderChips();
                this.filterPanelOpen = false;
                document.getElementById('sf-panel').classList.add('hidden');
                this.onFilterChange(this.getFilters());
            });
        }

        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearAll());
        }
    }

    _readPanelInputs() {
        const cat  = document.getElementById('sf-category');
        const sd   = document.getElementById('sf-start-date');
        const ed   = document.getElementById('sf-end-date');
        const minA = document.getElementById('sf-min-amount');
        const maxA = document.getElementById('sf-max-amount');

        if (cat) this.filters.category = cat.value;
        if (sd)  this.filters.start_date = sd.value;
        if (ed)  this.filters.end_date = ed.value;
        if (minA) this.filters.min_amount = minA.value;
        if (maxA) this.filters.max_amount = maxA.value;
    }

    _syncInputs() {
        const searchEl = document.getElementById('sf-search');
        const sortEl   = document.getElementById('sf-sort');
        const catEl    = document.getElementById('sf-category');
        const sdEl     = document.getElementById('sf-start-date');
        const edEl     = document.getElementById('sf-end-date');
        const minEl    = document.getElementById('sf-min-amount');
        const maxEl    = document.getElementById('sf-max-amount');

        if (searchEl) searchEl.value = this.filters.search;
        if (sortEl)   sortEl.value   = this.filters.sort;
        if (catEl)    catEl.value     = this.filters.category;
        if (sdEl)     sdEl.value      = this.filters.start_date;
        if (edEl)     edEl.value      = this.filters.end_date;
        if (minEl)    minEl.value     = this.filters.min_amount;
        if (maxEl)    maxEl.value     = this.filters.max_amount;
    }

    // ── Chips ────────────────────────────────────────────────
    _renderChips() {
        const chipsEl = document.getElementById('sf-chips');
        if (!chipsEl) return;

        const chips = [];
        let activeCount = 0;

        if (this.filters.search) {
            chips.push(this._chipHTML('search', `"${this.filters.search}"`));
            activeCount++;
        }
        if (this.filters.category) {
            chips.push(this._chipHTML('category', this.filters.category));
            activeCount++;
        }
        if (this.filters.start_date || this.filters.end_date) {
            const label = (this.filters.start_date || '...') + ' → ' + (this.filters.end_date || '...');
            chips.push(this._chipHTML('date', label));
            activeCount++;
        }
        if (this.filters.min_amount || this.filters.max_amount) {
            const label = '₹' + (this.filters.min_amount || '0') + ' – ₹' + (this.filters.max_amount || '∞');
            chips.push(this._chipHTML('amount', label));
            activeCount++;
        }

        if (activeCount > 0) {
            chips.push(`<button id="sf-clear-all-chip" class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-[12px] font-bold text-error hover:bg-error-container/20 transition-all cursor-pointer">Clear All</button>`);
        }

        chipsEl.innerHTML = chips.join('');

        // Badge
        const badge = document.getElementById('sf-filter-badge');
        if (badge) {
            if (activeCount > 0) {
                badge.textContent = activeCount;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        }

        // Chip remove listeners
        chipsEl.querySelectorAll('[data-chip-remove]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const key = e.currentTarget.dataset.chipRemove;
                this._removeFilter(key);
            });
        });

        const clearAllChip = document.getElementById('sf-clear-all-chip');
        if (clearAllChip) clearAllChip.addEventListener('click', () => this.clearAll());
    }

    _chipHTML(key, label) {
        return `
            <span class="inline-flex items-center gap-1.5 px-3 py-1.5 bg-primary-fixed/30 text-primary rounded-full text-[12px] font-semibold">
                ${escapeHtml(label)}
                <button data-chip-remove="${escapeHtml(key)}" class="hover:text-error transition-colors">
                    <span class="material-symbols-outlined text-[14px]">close</span>
                </button>
            </span>
        `;
    }

    _removeFilter(key) {
        if (key === 'search') {
            this.filters.search = '';
        } else if (key === 'category') {
            this.filters.category = '';
        } else if (key === 'date') {
            this.filters.start_date = '';
            this.filters.end_date = '';
        } else if (key === 'amount') {
            this.filters.min_amount = '';
            this.filters.max_amount = '';
        }
        this._saveState();
        this._syncInputs();
        this._renderChips();
        this.onFilterChange(this.getFilters());
    }
}
