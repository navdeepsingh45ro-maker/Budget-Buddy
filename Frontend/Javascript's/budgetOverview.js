// ─────────────────────────────────────────────────────────────
//  budgetOverview.js — BudgetBuddy Budget Overview page
//  Depends on: api.js (loaded before this file)
//
//  Backend endpoints used:
//    GET /analytics  → { total_spent, remaining_budget,
//                        category_breakdown, top_category,
//                        expense_count, percentage_spent }
//    GET /budget/    → { id, monthly_budget, month, year, user_id }
//
//  This file renders:
//    1. Hero section — remaining budget subtitle + progress bar
//    2. Category cards — one per category from category_breakdown
//    3. Micro-interactions on the rendered cards
// ─────────────────────────────────────────────────────────────

requireAuth();

// ── Category config: icon for all 20 categories ──────────────
// Uses the same categories from expense_schema.py
const CATEGORY_CONFIG = {
    'Food':          { icon: 'restaurant'         },
    'Transport':     { icon: 'directions_car'     },
    'Entertainment': { icon: 'movie'              },
    'Shopping':      { icon: 'shopping_bag'       },
    'Bills':         { icon: 'receipt_long'       },
    'Health':        { icon: 'health_and_safety'  },
    'Education':     { icon: 'school'             },
    'Subscriptions': { icon: 'subscriptions'      },
    'EMI Loans':     { icon: 'account_balance'    },
    'Rent':          { icon: 'home'               },
    'Investments':   { icon: 'trending_up'        },
    'Savings':       { icon: 'savings'            },
    'Travel':        { icon: 'flight'             },
    'Family':        { icon: 'family_restroom'    },
    'Personal Care': { icon: 'spa'               },
    'Gifts':         { icon: 'redeem'             },
    'Donations':     { icon: 'volunteer_activism' },
    'Insurance':     { icon: 'shield'             },
    'Taxes':         { icon: 'request_quote'      },
    'Other':         { icon: 'more_horiz'         },
};

// ── DOM refs ─────────────────────────────────────────────────
const heroSubtitleEl  = document.getElementById('hero-subtitle');
const heroProgressEl  = document.getElementById('hero-progress-bar');
const categoriesListEl = document.getElementById('categories-list');

// ── Modal DOM refs ───────────────────────────────────────────
const updateBudgetBtn = document.getElementById('update-budget-btn');
const budgetModal = document.getElementById('budget-modal');
const budgetModalContent = document.getElementById('budget-modal-content');
const closeBudgetModalBtn = document.getElementById('close-budget-modal');
const budgetForm = document.getElementById('budget-form');
const budgetInput = document.getElementById('budget-input');
const budgetModalTitle = document.getElementById('budget-modal-title');
const budgetModalDesc = document.getElementById('budget-modal-desc');
const budgetSubmitText = document.getElementById('budget-submit-text');
let hasExistingBudget = false;

// ── Load data on page ready ──────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadBudgetOverview();
    setupModalEvents();
});

async function loadBudgetOverview() {
    try {
        const [analytics, budget] = await Promise.all([
            apiGet('/analytics').catch(e => { console.warn('analytics:', e.message); return null; }),
            apiGet('/budget/').catch(e => { console.warn('budget:', e.message); return null; }),
        ]);

        hasExistingBudget = !!budget;
        const monthlyBudget = budget ? budget.monthly_budget : 0;

        if (!hasExistingBudget) {
            showBudgetModal(true); // Automatically ask for budget if none exists
        }

        if (analytics) {
            renderHero(analytics, monthlyBudget);
            renderCategoryCards(analytics.category_breakdown, monthlyBudget);
        } else {
            // No analytics — user has no expenses or no budget set
            if (heroSubtitleEl) heroSubtitleEl.textContent = 'Set a budget and add expenses to see your pulse!';
            if (categoriesListEl) {
                categoriesListEl.innerHTML = `
                    <div class="bg-surface rounded-xl p-md soft-shadow border border-primary/5 text-center">
                        <p class="font-body-md text-on-surface-variant">No spending data yet. Add expenses to see your categories here.</p>
                    </div>
                `;
            }
        }

    } catch (err) {
        console.error('Budget overview load failed:', err.message);
    }
}

// ── Hero section ─────────────────────────────────────────────
function renderHero(analytics, monthlyBudget) {
    const { remaining_budget, percentage_spent } = analytics;

    // Subtitle text
    if (heroSubtitleEl) {
        if (remaining_budget > 0) {
            heroSubtitleEl.textContent = `You're doing great! ${formatCurrency(remaining_budget)} left to spend.`;
        } else {
            heroSubtitleEl.textContent = `Budget exceeded by ${formatCurrency(Math.abs(remaining_budget))}. Time to slow down!`;
        }
    }

    // Progress bar
    if (heroProgressEl) {
        const pct = Math.min(percentage_spent, 100);
        heroProgressEl.style.width = `${pct}%`;

        // Change color when nearing/over limit
        if (percentage_spent >= 90) {
            heroProgressEl.classList.remove('bg-primary');
            heroProgressEl.classList.add('bg-error');
        } else if (percentage_spent >= 75) {
            heroProgressEl.classList.remove('bg-primary');
            heroProgressEl.classList.add('bg-tertiary');
        }
    }
}

// ── Category cards — matches the original HTML design exactly ─
function renderCategoryCards(categoryBreakdown, monthlyBudget) {
    if (!categoriesListEl || !categoryBreakdown) return;

    categoriesListEl.innerHTML = '';

    const entries = Object.entries(categoryBreakdown);

    if (entries.length === 0) {
        categoriesListEl.innerHTML = `
            <div class="bg-surface rounded-xl p-md soft-shadow border border-primary/5 text-center">
                <p class="font-body-md text-on-surface-variant">No spending data yet. Add expenses to see your categories here.</p>
            </div>
        `;
        return;
    }

    // Sort by amount spent, highest first
    entries.sort((a, b) => b[1] - a[1]);

    // Calculate per-category budget share (equal distribution)
    const categoryCount = entries.length;
    const perCategoryBudget = monthlyBudget > 0
        ? monthlyBudget / categoryCount
        : 0;

    entries.forEach(([category, spent]) => {
        const config = CATEGORY_CONFIG[category] || CATEGORY_CONFIG['Other'];
        const limit  = perCategoryBudget;
        const pct    = limit > 0 ? Math.min(Math.round((spent / limit) * 100), 100) : 0;
        const remaining = limit - spent;

        // Status determination
        const status = getStatus(pct);

        // Build the card HTML — exact same structure as the original design
        const card = document.createElement('div');
        card.className = 'bg-surface rounded-xl p-md soft-shadow border border-primary/5 hover:scale-[1.01] transition-transform duration-200';

        card.innerHTML = `
            <div class="flex justify-between items-start mb-sm">
                <div class="flex items-center gap-sm">
                    <div class="w-12 h-12 rounded-lg bg-primary-container/10 flex items-center justify-center">
                        <span class="material-symbols-outlined text-primary">${escapeHtml(config.icon)}</span>
                    </div>
                    <div>
                        <h3 class="font-headline-sm text-headline-sm text-on-surface">${escapeHtml(category)}</h3>
                        ${renderStatusBadge(status)}
                    </div>
                </div>
                <div class="text-right">
                    <p class="font-headline-sm text-headline-sm text-on-surface">${formatCurrency(spent)}</p>
                    <p class="font-body-sm text-on-surface-variant">Limit: ${formatCurrency(limit)}</p>
                </div>
            </div>
            <div class="space-y-2">
                <div class="w-full h-1.5 bg-secondary-container/40 rounded-full overflow-hidden">
                    <div class="h-full ${getBarColorClass(status)} rounded-full transition-all duration-500" style="width: ${pct}%;"></div>
                </div>
                <div class="flex justify-between text-body-sm">
                    <span class="${getMessageColorClass(status)} font-medium">${escapeHtml(getStatusMessage(category, remaining, status))}</span>
                    ${remaining > 0 ? `<span class="text-on-surface-variant">${formatCurrency(remaining)} left</span>` : ''}
                </div>
            </div>
        `;

        categoriesListEl.appendChild(card);
    });

    // Re-apply micro-interactions on the newly rendered cards
    applyMicroInteractions();
}

// ── Status helpers ────────────────────────────────────────────
function getStatus(pct) {
    if (pct >= 100) return 'over';
    if (pct >= 80)  return 'watching';
    return 'on-track';
}

function renderStatusBadge(status) {
    if (status === 'over') {
        return `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-error-container/40 text-error">
                    <span class="material-symbols-outlined text-xs">warning</span>Over Budget
                </span>`;
    }
    if (status === 'watching') {
        return `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-error-container/40 text-error">
                    <span class="material-symbols-outlined text-xs">visibility</span>Watching
                </span>`;
    }
    return `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-tertiary-container/20 text-tertiary">
                <span class="material-symbols-outlined text-xs">check_circle</span>On Track
            </span>`;
}

function getBarColorClass(status) {
    if (status === 'over')     return 'bg-error';
    if (status === 'watching') return 'bg-error/70';
    return 'bg-primary';
}

function getMessageColorClass(status) {
    if (status === 'over' || status === 'watching') return 'text-error';
    return 'text-tertiary';
}

function getStatusMessage(category, remaining, status) {
    if (status === 'over') {
        return `Over by ${formatCurrency(Math.abs(remaining))}!`;
    }
    if (status === 'watching') {
        return `Almost there! ${formatCurrency(remaining)} left`;
    }
    // Friendly on-track messages
    const messages = [
        `Great job in ${category}!`,
        `Keep it up!`,
        `You're doing great!`,
        `Nice work!`,
    ];
    // Pick a deterministic message based on category name length
    return messages[category.length % messages.length];
}

// ── Micro-interactions (same behavior as original inline script) ─
function applyMicroInteractions() {
    document.querySelectorAll('#categories-list .soft-shadow').forEach(card => {
        card.addEventListener('mousedown', () => {
            card.style.transform = 'scale(0.98)';
            card.style.boxShadow = 'none';
        });
        card.addEventListener('mouseup', () => {
            card.style.transform = 'scale(1.01)';
            card.style.boxShadow = '0px 4px 20px rgba(151, 132, 174, 0.15)';
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'scale(1)';
            card.style.boxShadow = '0px 4px 20px rgba(151, 132, 174, 0.15)';
        });
    });
}

// ── Utilities ─────────────────────────────────────────────────
function formatCurrency(amount) {
    return `₹${Number(amount).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ── Modal Logic ───────────────────────────────────────────────
function setupModalEvents() {
    if (updateBudgetBtn) updateBudgetBtn.addEventListener('click', () => showBudgetModal(false));
    if (closeBudgetModalBtn) closeBudgetModalBtn.addEventListener('click', hideBudgetModal);
    if (budgetForm) budgetForm.addEventListener('submit', handleBudgetSubmit);
}

function showBudgetModal(isInitialSetup = false) {
    if (!budgetModal || !budgetModalContent) return;
    
    if (isInitialSetup) {
        budgetModalTitle.textContent = 'Set Your First Budget';
        budgetModalDesc.textContent = 'Please tell your budget for this month to help us track your expenses better.';
        budgetSubmitText.textContent = 'Save Budget';
    } else {
        budgetModalTitle.textContent = 'Update Monthly Budget';
        budgetModalDesc.textContent = 'Update your budget for the current month.';
        budgetSubmitText.textContent = 'Update Budget';
    }

    budgetModal.classList.remove('hidden', 'pointer-events-none');
    // Small delay for CSS transition
    setTimeout(() => {
        budgetModal.classList.remove('opacity-0');
        budgetModalContent.classList.remove('scale-95', 'opacity-0');
        budgetModalContent.classList.add('scale-100', 'opacity-100');
    }, 10);
}

function hideBudgetModal() {
    if (!budgetModal || !budgetModalContent) return;
    
    budgetModal.classList.add('opacity-0');
    budgetModalContent.classList.remove('scale-100', 'opacity-100');
    budgetModalContent.classList.add('scale-95', 'opacity-0');
    
    setTimeout(() => {
        budgetModal.classList.add('hidden', 'pointer-events-none');
    }, 300);
}

async function handleBudgetSubmit(e) {
    e.preventDefault();
    const val = parseFloat(budgetInput.value);
    if (isNaN(val) || val <= 0) {
        alert('Please enter a valid amount.');
        return;
    }

    try {
        if (hasExistingBudget) {
            await apiPut('/budget/', { monthly_budget: val });
        } else {
            await apiPost('/budget/', { monthly_budget: val });
        }
        hideBudgetModal();
        hasExistingBudget = true;
        
        // Refresh the page data
        loadBudgetOverview();
    } catch (err) {
        alert(err.message || 'Failed to save budget.');
    }
}

// ── Monthly Report Logic ──────────────────────────────────────────
const generateReportBtn = document.getElementById('generate-report-btn');
const reportModal = document.getElementById('report-modal');
const reportModalContent = document.getElementById('report-modal-content');
const reportModalBody = document.getElementById('report-modal-body');
const closeReportModalBtn = document.getElementById('close-report-modal');

if (generateReportBtn) {
    generateReportBtn.addEventListener('click', async () => {
        const now = new Date();
        const month = now.getMonth() + 1;
        const year = now.getFullYear();
        
        generateReportBtn.innerHTML = '<span class="material-symbols-outlined text-[20px] animate-spin">refresh</span><span class="font-label-md text-label-md">Generating...</span>';
        
        try {
            const data = await apiGet(`/ai/monthly-report?month=${month}&year=${year}`);
            reportModalBody.textContent = data.report;
            
            reportModal.classList.remove('opacity-0', 'pointer-events-none');
            setTimeout(() => {
                reportModalContent.classList.remove('scale-95');
                reportModalContent.classList.add('scale-100');
            }, 10);
        } catch(e) {
            console.error(e);
            alert('Failed to generate report: ' + e.message);
        } finally {
            generateReportBtn.innerHTML = '<span class="material-symbols-outlined text-[20px]">auto_awesome</span><span class="font-label-md text-label-md">Generate AI Monthly Report</span>';
        }
    });
}

function closeReportModal() {
    reportModalContent.classList.remove('scale-100');
    reportModalContent.classList.add('scale-95');
    setTimeout(() => {
        reportModal.classList.add('opacity-0', 'pointer-events-none');
    }, 200);
}

if (closeReportModalBtn) {
    closeReportModalBtn.addEventListener('click', closeReportModal);
}
if (reportModal) {
    reportModal.addEventListener('click', (e) => {
        if (e.target === reportModal) {
            closeReportModal();
        }
    });
}
