// ─────────────────────────────────────────────────────────────
//  recurring.js — BudgetBuddy Recurring Transactions
//  Depends on: api.js, history.js (for CATEGORY_CONFIG)
// ─────────────────────────────────────────────────────────────

// Wait for DOM
document.addEventListener('DOMContentLoaded', () => {
    initRecurringTabs();
    initRecurringEvents();
    if (document.getElementById('tab-recurring').classList.contains('bg-surface-container-lowest')) {
        loadRecurring();
    }
});

// ── DOM Elements ──────────────────────────────────────────────
const tabExpenses   = document.getElementById('tab-expenses');
const tabRecurring  = document.getElementById('tab-recurring');
const expensesTab   = document.getElementById('expenses-tab');
const recurringTab  = document.getElementById('recurring-tab');

const rtList        = document.getElementById('rt-list');
const rtSkeleton    = document.getElementById('rt-skeleton');
const rtEmpty       = document.getElementById('rt-empty');
const rtError       = document.getElementById('rt-error');
const rtRetryBtn    = document.getElementById('rt-retry-btn');
const rtAddBtn      = document.getElementById('rt-add-btn');

const rtModalBackdrop = document.getElementById('rt-modal-backdrop');
const rtModalClose  = document.getElementById('rt-modal-close');
const rtForm        = document.getElementById('rt-form');
const rtModalTitle  = document.getElementById('rt-modal-title');
const rtSubmitBtn   = document.getElementById('rt-submit-btn');

// Form inputs
const rtiId        = document.getElementById('rt-edit-id');
const rtiTitle     = document.getElementById('rt-title');
const rtiAmount    = document.getElementById('rt-amount');
const rtiFrequency = document.getElementById('rt-frequency');
const rtiCategory  = document.getElementById('rt-category');
const rtiNotes     = document.getElementById('rt-notes');
const rtiStartDate = document.getElementById('rt-start-date');
const rtiEndDate   = document.getElementById('rt-end-date');

// ── Tab Logic ────────────────────────────────────────────────
function initRecurringTabs() {
    tabExpenses.addEventListener('click', () => {
        // Style tabs
        tabExpenses.className = "flex-1 py-2.5 rounded-xl text-label-md font-label-md text-center transition-all bg-surface-container-lowest premium-shadow text-primary font-bold";
        tabRecurring.className = "flex-1 py-2.5 rounded-xl text-label-md font-label-md text-center transition-all text-on-surface-variant hover:text-primary";
        
        // Show/hide sections
        expensesTab.classList.remove('hidden');
        recurringTab.classList.add('hidden');
    });

    tabRecurring.addEventListener('click', () => {
        // Style tabs
        tabRecurring.className = "flex-1 py-2.5 rounded-xl text-label-md font-label-md text-center transition-all bg-surface-container-lowest premium-shadow text-primary font-bold";
        tabExpenses.className = "flex-1 py-2.5 rounded-xl text-label-md font-label-md text-center transition-all text-on-surface-variant hover:text-primary";
        
        // Show/hide sections
        recurringTab.classList.remove('hidden');
        expensesTab.classList.add('hidden');
        
        // Load data if empty
        if (rtList.children.length === 0 && rtEmpty.classList.contains('hidden') && rtError.classList.contains('hidden')) {
             loadRecurring();
        } else {
             loadRecurring(); // Always refresh on tab switch for safety
        }
    });
}

// ── Init Events ──────────────────────────────────────────────
function initRecurringEvents() {
    rtRetryBtn.addEventListener('click', loadRecurring);
    
    rtAddBtn.addEventListener('click', () => {
        openRecurringModal();
    });

    rtModalClose.addEventListener('click', closeRecurringModal);
    rtModalBackdrop.addEventListener('click', (e) => {
        if (e.target === rtModalBackdrop) closeRecurringModal();
    });

    rtForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await saveRecurring();
    });
}

// ── Load Data ────────────────────────────────────────────────
async function loadRecurring() {
    showRtState('loading');
    try {
        const response = await apiGet('/recurring/');
        const data = response.recurring_transactions || [];
        
        if (data.length === 0) {
            showRtState('empty');
        } else {
            renderRecurring(data);
            showRtState('list');
        }
    } catch (err) {
        console.error("Failed to load recurring transactions:", err);
        showRtState('error');
    }
}

function showRtState(state) {
    rtSkeleton.classList.toggle('hidden', state !== 'loading');
    rtEmpty.classList.toggle('hidden', state !== 'empty');
    rtError.classList.toggle('hidden', state !== 'error');
    rtList.classList.toggle('hidden', state !== 'list');
}

// ── Render List ──────────────────────────────────────────────
function renderRecurring(items) {
    rtList.innerHTML = '';
    
    // Need CATEGORY_CONFIG from history.js, fallback if not ready
    const getIcon = (cat) => {
        if (typeof CATEGORY_CONFIG !== 'undefined' && CATEGORY_CONFIG[cat]) {
            return CATEGORY_CONFIG[cat].icon;
        }
        return 'receipt_long';
    };

    items.forEach(rt => {
        const itemEl = document.createElement('div');
        itemEl.className = `flex flex-col p-4 bg-surface-container-lowest rounded-2xl border border-surface-variant/30 premium-shadow transition-colors duration-150 ${!rt.is_active ? 'opacity-60 grayscale-[50%]' : ''}`;
        
        // Determine status text/color
        let statusHtml = '';
        if (!rt.is_active) {
            statusHtml = `<span class="px-2 py-0.5 bg-surface-variant text-on-surface-variant rounded-full text-[10px] font-bold uppercase tracking-wider">Paused</span>`;
        } else {
            statusHtml = `<span class="px-2 py-0.5 bg-primary-container/20 text-primary rounded-full text-[10px] font-bold uppercase tracking-wider">Active</span>`;
        }
        
        let endHtml = rt.end_date ? `<br><span class="text-[11px] opacity-70">Until: ${formatRtDate(rt.end_date)}</span>` : '';

        itemEl.innerHTML = `
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-surface-container flex items-center justify-center rounded-full">
                        <span class="material-symbols-outlined text-primary text-[20px]">${getIcon(rt.category)}</span>
                    </div>
                    <div>
                        <div class="flex items-center gap-2">
                            <p class="text-body-md font-bold text-on-background leading-tight">${rt.title}</p>
                            ${statusHtml}
                        </div>
                        <p class="text-[12px] text-outline capitalize">${rt.frequency} · ${rt.category}</p>
                    </div>
                </div>
                <div class="text-right">
                    <p class="text-body-md font-bold text-error">-${formatCurrency(rt.amount)}</p>
                    <p class="text-[11px] text-outline font-medium mt-0.5">Next: <span class="text-on-surface-variant">${formatRtDate(rt.next_run)}</span>${endHtml}</p>
                </div>
            </div>
            
            <div class="flex justify-end gap-2 border-t border-surface-variant/30 pt-3 mt-1">
                <button onclick="toggleRtStatus(${rt.id}, ${rt.is_active})" class="px-3 py-1.5 border border-outline-variant/30 rounded-lg text-[12px] font-semibold text-on-surface-variant hover:bg-surface-container transition-all">
                    ${rt.is_active ? 'Pause' : 'Resume'}
                </button>
                <button onclick='editRt(${JSON.stringify(rt).replace(/'/g, "&#39;")})' class="px-3 py-1.5 border border-outline-variant/30 rounded-lg text-[12px] font-semibold text-on-surface-variant hover:bg-surface-container transition-all">
                    Edit
                </button>
                <button onclick="deleteRt(${rt.id})" class="px-3 py-1.5 border border-error/30 text-error rounded-lg text-[12px] font-semibold hover:bg-error-container/20 transition-all">
                    Delete
                </button>
            </div>
        `;
        rtList.appendChild(itemEl);
    });
}

// ── Modal Actions ────────────────────────────────────────────
function openRecurringModal(rt = null) {
    if (rt) {
        rtModalTitle.textContent = "Edit Recurring Transaction";
        rtSubmitBtn.textContent = "Save Changes";
        rtiId.value = rt.id;
        rtiTitle.value = rt.title;
        rtiAmount.value = rt.amount;
        rtiFrequency.value = rt.frequency;
        rtiCategory.value = rt.category;
        rtiNotes.value = rt.notes || "";
        rtiStartDate.value = rt.start_date;
        rtiEndDate.value = rt.end_date || "";
    } else {
        rtModalTitle.textContent = "New Recurring Transaction";
        rtSubmitBtn.textContent = "Create";
        rtForm.reset();
        rtiId.value = "";
        
        // Set start date to today by default
        const today = new Date().toISOString().split('T')[0];
        rtiStartDate.value = today;
    }
    
    rtModalBackdrop.classList.remove('hidden');
}

function closeRecurringModal() {
    rtModalBackdrop.classList.add('hidden');
    rtForm.reset();
}

window.editRt = function(rt) {
    openRecurringModal(rt);
};

// ── CRUD Actions ─────────────────────────────────────────────
async function saveRecurring() {
    const isEdit = rtiId.value !== "";
    
    const payload = {
        title: rtiTitle.value.trim(),
        amount: parseFloat(rtiAmount.value),
        frequency: rtiFrequency.value,
        category: rtiCategory.value,
        notes: rtiNotes.value.trim() || null,
        start_date: rtiStartDate.value,
        end_date: rtiEndDate.value || null
    };

    const originalText = rtSubmitBtn.textContent;
    rtSubmitBtn.textContent = "Saving...";
    rtSubmitBtn.disabled = true;

    try {
        if (isEdit) {
            await apiPut(`/recurring/${rtiId.value}`, payload);
        } else {
            await apiPost('/recurring/', payload);
        }
        closeRecurringModal();
        loadRecurring();
    } catch (err) {
        alert("Error saving: " + err.message);
    } finally {
        rtSubmitBtn.textContent = originalText;
        rtSubmitBtn.disabled = false;
    }
}

window.deleteRt = async function(id) {
    if (!confirm("Are you sure you want to delete this recurring transaction template? This will not delete previously generated expenses.")) {
        return;
    }
    
    try {
        await apiDelete(`/recurring/${id}`);
        loadRecurring();
    } catch (err) {
        alert("Failed to delete: " + err.message);
    }
};

window.toggleRtStatus = async function(id, currentStatus) {
    try {
        await apiPut(`/recurring/${id}`, { is_active: !currentStatus });
        loadRecurring();
    } catch (err) {
        alert("Failed to update status: " + err.message);
    }
};

// ── Utils ────────────────────────────────────────────────────
function formatRtDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}
