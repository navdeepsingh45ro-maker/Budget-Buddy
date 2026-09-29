// ─────────────────────────────────────────────────────────────
//  history.js — BudgetBuddy Expense History
//  Depends on: api.js, search-filter.js
//  Uses: GET /expenses/query (ExpenseQueryService)
// ─────────────────────────────────────────────────────────────

requireAuth();

// Category configuration to keep icons consistent with dashboard
const CATEGORY_CONFIG = {
    'Food':          { icon: 'restaurant' },
    'Transport':     { icon: 'directions_car' },
    'Entertainment': { icon: 'sports_esports' },
    'Shopping':      { icon: 'shopping_bag' },
    'Bills':         { icon: 'receipt_long' },
    'Health':        { icon: 'health_and_safety' },
    'Education':     { icon: 'school' },
    'Subscriptions': { icon: 'subscriptions' },
    'EMI Loans':     { icon: 'account_balance' },
    'Rent':          { icon: 'home' },
    'Investments':   { icon: 'trending_up' },
    'Savings':       { icon: 'savings' },
    'Travel':        { icon: 'flight' },
    'Family':        { icon: 'family_restroom' },
    'Personal Care': { icon: 'spa' },
    'Gifts':         { icon: 'redeem' },
    'Donations':     { icon: 'volunteer_activism' },
    'Insurance':     { icon: 'shield' },
    'Taxes':         { icon: 'request_quote' },
    'Other':         { icon: 'more_horiz' },
};

// ── DOM ──────────────────────────────────────────────────────
const historyContainer = document.getElementById('history-container');
const historySkeleton  = document.getElementById('history-skeleton');
const historyEmpty     = document.getElementById('history-empty');
const historyError     = document.getElementById('history-error');
const paginationEl     = document.getElementById('history-pagination');
const prevPageBtn      = document.getElementById('prev-page-btn');
const nextPageBtn      = document.getElementById('next-page-btn');
const pageIndicator    = document.getElementById('page-indicator');
const retryBtn         = document.getElementById('history-retry-btn');

// ── State ────────────────────────────────────────────────────
let currentPage = 1;
let currentTotalExpenses = 0;
let currentExpenses = [];
let currentFiltersState = {};
const PAGE_LIMIT = 20;

// ── Init toolbar ─────────────────────────────────────────────
const toolbar = new SearchFilterToolbar({
    containerId: 'sf-toolbar',
    features: { search: true, category: true, dateRange: true, amountRange: true, sort: true, export: true },
    onFilterChange: (filters) => {
        currentPage = 1;
        currentFiltersState = filters;
        loadHistory(filters);
    },
    onExportClick: (filters) => {
        openExportModal(filters);
    }
});

// ── Event Listeners ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => loadHistory(toolbar.getFilters()));

if (retryBtn) retryBtn.addEventListener('click', () => loadHistory(toolbar.getFilters()));
if (prevPageBtn) prevPageBtn.addEventListener('click', () => { currentPage--; loadHistory(toolbar.getFilters()); });
if (nextPageBtn) nextPageBtn.addEventListener('click', () => { currentPage++; loadHistory(toolbar.getFilters()); });

// ── Load via Query Engine ────────────────────────────────────
async function loadHistory(filters) {
    showState('loading');

    try {
        // Build query string from filters
        const params = new URLSearchParams();
        if (filters.search)     params.append('search', filters.search);
        if (filters.category)   params.append('category', filters.category);
        if (filters.start_date) params.append('start_date', filters.start_date);
        if (filters.end_date)   params.append('end_date', filters.end_date);
        if (filters.min_amount) params.append('min_amount', filters.min_amount);
        if (filters.max_amount) params.append('max_amount', filters.max_amount);
        if (filters.sort)       params.append('sort', filters.sort);
        params.append('page', currentPage);
        params.append('limit', PAGE_LIMIT);

        const result = await apiGet(`/expenses/query?${params.toString()}`);

        if (!result.expenses || result.expenses.length === 0) {
            currentTotalExpenses = 0;
            showState('empty');
            return;
        }

        currentTotalExpenses = result.total;
        currentExpenses = result.expenses;
        renderExpenses(result.expenses);
        renderPagination(result);
        showState('list');

    } catch (err) {
        console.error('Failed to load history:', err.message);
        showState('error');
    }
}

// ── UI State Machine ─────────────────────────────────────────
function showState(state) {
    historySkeleton.classList.toggle('hidden', state !== 'loading');
    historyEmpty.classList.toggle('hidden', state !== 'empty');
    historyError.classList.toggle('hidden', state !== 'error');
    historyContainer.classList.toggle('hidden', state !== 'list');
    paginationEl.classList.toggle('hidden', state !== 'list');
}

// ── Render Expenses ──────────────────────────────────────────
function renderExpenses(expenses) {
    historyContainer.innerHTML = '';

    expenses.forEach(expense => {
        const config = CATEGORY_CONFIG[expense.category] || CATEGORY_CONFIG['Other'];

        const item = document.createElement('div');
        item.className = 'flex items-center justify-between p-4 hover:bg-surface-container-low transition-colors duration-150 group';
        item.id = `expense-${expense.id}`;

        item.innerHTML = `
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-surface-container flex items-center justify-center rounded-full">
                    <span class="material-symbols-outlined text-primary text-[20px]">${config.icon}</span>
                </div>
                <div>
                    <p class="text-body-md font-bold text-on-background">${expense.note || expense.category}</p>
                    <p class="text-[12px] text-outline">${formatDate(expense.expense_date || expense.created_at)} · ${expense.category}</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <p class="text-body-md font-bold text-error mr-2">-${formatCurrency(expense.amount)}</p>
                <button onclick="openEditExpenseModal(${expense.id})" class="text-outline hover:text-primary hover:bg-primary-container/20 p-2 rounded-full transition-all duration-150 md:opacity-0 group-hover:opacity-100 focus:opacity-100 flex items-center justify-center" aria-label="Edit expense">
                    <span class="material-symbols-outlined text-[20px]">edit</span>
                </button>
                <button onclick="deleteExpense(${expense.id})" class="text-outline hover:text-error hover:bg-error-container/20 p-2 rounded-full transition-all duration-150 md:opacity-0 group-hover:opacity-100 focus:opacity-100 flex items-center justify-center" aria-label="Delete expense">
                    <span class="material-symbols-outlined text-[20px]">delete</span>
                </button>
            </div>
        `;

        historyContainer.appendChild(item);
    });
}

// ── Render Pagination ────────────────────────────────────────
function renderPagination(result) {
    currentPage = result.page;
    pageIndicator.textContent = `Page ${result.page} of ${result.total_pages}`;
    prevPageBtn.disabled = result.page <= 1;
    nextPageBtn.disabled = result.page >= result.total_pages;
}

// ── Delete ───────────────────────────────────────────────────
async function deleteExpense(expenseId) {
    if (!confirm('Are you sure you want to delete this expense?')) return;

    try {
        await apiDelete(`/expense/${expenseId}`);

        const item = document.getElementById(`expense-${expenseId}`);
        if (item) {
            item.style.transform = 'scale(0.95)';
            item.style.opacity = '0';
            item.style.transition = 'all 0.3s ease';
            setTimeout(() => loadHistory(toolbar.getFilters()), 300);
        } else {
            loadHistory(toolbar.getFilters());
        }
    } catch (err) {
        alert('Failed to delete expense: ' + err.message);
    }
}

// ── Edit ─────────────────────────────────────────────────────
function openEditExpenseModal(id) {
    const expense = currentExpenses.find(e => e.id === id);
    if (!expense) return;

    document.getElementById('edit-expense-id').value = expense.id;
    document.getElementById('edit-amount').value = expense.amount;
    document.getElementById('edit-note').value = expense.note || expense.category;
    document.getElementById('edit-category').value = expense.category;
    document.getElementById('edit-payment').value = expense.payment_method || 'Card';
    document.getElementById('edit-date').value = expense.expense_date || (expense.created_at ? expense.created_at.split('T')[0] : '');

    const backdrop = document.getElementById('edit-expense-modal-backdrop');
    backdrop.classList.remove('hidden');
    setTimeout(() => {
        document.getElementById('edit-expense-modal').classList.remove('translate-y-full');
    }, 10);
}

function closeEditExpenseModal() {
    document.getElementById('edit-expense-modal').classList.add('translate-y-full');
    setTimeout(() => {
        document.getElementById('edit-expense-modal-backdrop').classList.add('hidden');
    }, 300);
}

document.getElementById('edit-modal-close')?.addEventListener('click', closeEditExpenseModal);
document.getElementById('edit-expense-modal-backdrop')?.addEventListener('click', (e) => {
    if (e.target === document.getElementById('edit-expense-modal-backdrop')) closeEditExpenseModal();
});

document.getElementById('edit-expense-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const id = document.getElementById('edit-expense-id').value;
    const payload = {
        amount: parseFloat(document.getElementById('edit-amount').value),
        category: document.getElementById('edit-category').value,
        note: document.getElementById('edit-note').value,
        payment_method: document.getElementById('edit-payment').value,
        expense_date: document.getElementById('edit-date').value
    };

    const btn = document.getElementById('edit-submit-btn');
    const oldText = btn.textContent;
    btn.textContent = 'Saving...';
    btn.disabled = true;

    try {
        await apiPut(`/expense/${id}`, payload);
        closeEditExpenseModal();
        loadHistory(toolbar.getFilters());
    } catch (err) {
        alert('Failed to update expense: ' + err.message);
    } finally {
        btn.textContent = oldText;
        btn.disabled = false;
    }
});

// ── Utilities ────────────────────────────────────────────────
function formatCurrency(amount) {
    return `₹${Number(amount).toLocaleString('en-IN')}`;
}

function formatDate(dateStr) {
    const date   = new Date(dateStr);
    const now    = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
        return `Today, ${date.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })}`;
    } else if (diffDays === 1) {
        return 'Yesterday';
    } else {
        return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
    }
}

// ── Export Modal Logic ───────────────────────────────────────
const exportModalBackdrop = document.getElementById('export-modal-backdrop');
const exportModalClose = document.getElementById('export-modal-close');
const exportFormatBtns = document.querySelectorAll('.export-format-btn');
const exportDownloadBtn = document.getElementById('export-download-btn');
const exportCountEl = document.getElementById('export-count');
const exportFiltersSummaryEl = document.getElementById('export-filters-summary');
const exportDownloadIcon = document.getElementById('export-download-icon');
const exportDownloadText = document.getElementById('export-download-text');
let selectedFormat = null;

function openExportModal(filters) {
    if (currentTotalExpenses === 0) {
        alert('No expenses available to export.');
        return;
    }

    // Set counts and summaries
    exportCountEl.textContent = currentTotalExpenses;
    
    // Build summary string
    const activeFilters = [];
    if (filters.search) activeFilters.push(`"${filters.search}"`);
    if (filters.category) activeFilters.push(filters.category);
    if (filters.start_date || filters.end_date) activeFilters.push('Date range');
    if (filters.min_amount || filters.max_amount) activeFilters.push('Amount limit');
    
    exportFiltersSummaryEl.textContent = activeFilters.length > 0 ? activeFilters.join(', ') : 'None';
    
    // Reset selection
    selectedFormat = null;
    exportFormatBtns.forEach(btn => btn.classList.remove('ring-2', 'ring-primary', 'border-primary', 'bg-surface-container-low'));
    exportDownloadBtn.disabled = true;
    exportDownloadIcon.textContent = 'download';
    exportDownloadText.textContent = 'Download';

    // Show modal
    exportModalBackdrop.classList.remove('hidden');
    // small delay to allow display:block to apply before transition
    setTimeout(() => {
        document.getElementById('export-modal').classList.remove('translate-y-full');
    }, 10);
}

function closeExportModal() {
    document.getElementById('export-modal').classList.add('translate-y-full');
    setTimeout(() => {
        exportModalBackdrop.classList.add('hidden');
    }, 300);
}

if (exportModalClose) {
    exportModalClose.addEventListener('click', closeExportModal);
}
if (exportModalBackdrop) {
    exportModalBackdrop.addEventListener('click', (e) => {
        if (e.target === exportModalBackdrop) closeExportModal();
    });
}

// Format selection
exportFormatBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
        // Remove active state from all
        exportFormatBtns.forEach(b => b.classList.remove('ring-2', 'ring-primary', 'border-primary', 'bg-surface-container-low'));
        // Add to clicked
        btn.classList.add('ring-2', 'ring-primary', 'border-primary', 'bg-surface-container-low');
        
        selectedFormat = btn.dataset.format;
        exportDownloadBtn.disabled = false;
    });
});

// Trigger Download
exportDownloadBtn.addEventListener('click', async () => {
    if (!selectedFormat) return;
    
    exportDownloadBtn.disabled = true;
    exportDownloadIcon.textContent = 'hourglass_empty';
    exportDownloadText.textContent = 'Generating...';
    
    try {
        const params = new URLSearchParams();
        if (currentFiltersState.search)     params.append('search', currentFiltersState.search);
        if (currentFiltersState.category)   params.append('category', currentFiltersState.category);
        if (currentFiltersState.start_date) params.append('start_date', currentFiltersState.start_date);
        if (currentFiltersState.end_date)   params.append('end_date', currentFiltersState.end_date);
        if (currentFiltersState.min_amount) params.append('min_amount', currentFiltersState.min_amount);
        if (currentFiltersState.max_amount) params.append('max_amount', currentFiltersState.max_amount);
        if (currentFiltersState.sort)       params.append('sort', currentFiltersState.sort);

        const token = getToken();
        const response = await fetch(`${API_BASE}/export/${selectedFormat}?${params.toString()}`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to export data');
        }

        // Get filename from Content-Disposition if available
        let filename = `Expenses.${selectedFormat === 'excel' ? 'xlsx' : selectedFormat}`;
        const disposition = response.headers.get('Content-Disposition');
        if (disposition && disposition.indexOf('filename=') !== -1) {
            const matches = /filename="([^"]+)"/.exec(disposition);
            if (matches != null && matches[1]) {
                filename = matches[1];
            }
        }

        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        
        window.URL.revokeObjectURL(downloadUrl);
        a.remove();
        
        alert('Export downloaded successfully!');
        closeExportModal();

    } catch (err) {
        alert('Export failed: ' + err.message);
        exportDownloadBtn.disabled = false;
        exportDownloadIcon.textContent = 'download';
        exportDownloadText.textContent = 'Download';
    }
});
