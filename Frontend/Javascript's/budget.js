// ─────────────────────────────────────────────────────────────
//  budget.js — BudgetBuddy Budget Overview page
//  Depends on: api.js
//
//  Backend endpoints expected:
//    GET /budgets   → [{ id, category, limit }]
//    GET /expenses  → used to compute spent per category
//
//  ⚠️  Verify field names match budget_model.py + expense_model.py
// ─────────────────────────────────────────────────────────────

requireAuth();

const budgetList   = document.getElementById('budget-list');
const totalBudgetEl = document.getElementById('total-budget');
const totalSpentEl  = document.getElementById('total-spent');
const logoutBtn     = document.getElementById('logout-btn');

logoutBtn && logoutBtn.addEventListener('click', logout);

document.addEventListener('DOMContentLoaded', loadBudgetPage);

async function loadBudgetPage() {
    try {
        // Fetch both in parallel — faster than sequential awaits
        const [budgets, expenses] = await Promise.all([
            apiGet('/budgets'),    // ⚠️ verify your route
            apiGet('/expenses'),   // ⚠️ verify your route
        ]);

        renderBudgetOverview(budgets, expenses);
    } catch (err) {
        console.error('Budget page load failed:', err.message);
    }
}

function renderBudgetOverview(budgets, expenses) {
    const now       = new Date();
    const thisMonth = now.getMonth();
    const thisYear  = now.getFullYear();

    // Sum expenses per category for current month
    const spentByCategory = {};
    expenses.forEach(e => {
        const d = new Date(e.date);
        if (d.getMonth() === thisMonth && d.getFullYear() === thisYear) {
            // ⚠️ Adjust field names: e.category, e.amount
            spentByCategory[e.category] = (spentByCategory[e.category] || 0) + e.amount;
        }
    });

    // Totals for the header cards
    const totalLimit = budgets.reduce((s, b) => s + b.limit, 0);
    const totalSpent = Object.values(spentByCategory).reduce((s, v) => s + v, 0);

    if (totalBudgetEl) totalBudgetEl.textContent = `₹${totalLimit.toLocaleString('en-IN')}`;
    if (totalSpentEl)  totalSpentEl.textContent  = `₹${totalSpent.toLocaleString('en-IN')}`;

    // Render a row per budget category
    if (!budgetList) return;

    budgetList.innerHTML = budgets.map(b => {
        // ⚠️ Adjust field names: b.category, b.limit
        const spent     = spentByCategory[b.category] || 0;
        const pct       = Math.min(Math.round((spent / b.limit) * 100), 100);
        const remaining = b.limit - spent;
        const status    = getStatus(pct);

        return `
        <div class="budget-row">
            <div class="budget-row-header">
                <span class="budget-category">${b.category}</span>
                <span class="budget-amounts">
                    <span class="budget-spent">₹${spent.toLocaleString('en-IN')}</span>
                    <span class="budget-limit"> / ₹${b.limit.toLocaleString('en-IN')}</span>
                </span>
            </div>
            <div class="progress-track">
                <div class="progress-fill status-${status}" style="width: ${pct}%"></div>
            </div>
            <div class="budget-row-footer">
                <span class="status-label status-${status}">${status === 'over' ? 'Over budget' : status === 'near' ? 'Near limit' : 'On track'}</span>
                <span class="remaining-text">${remaining > 0 ? `₹${remaining.toLocaleString('en-IN')} remaining` : `₹${Math.abs(remaining).toLocaleString('en-IN')} over`}</span>
            </div>
        </div>`;
    }).join('');
}

// ── Status thresholds ─────────────────────────────────────────
function getStatus(pct) {
    if (pct >= 100) return 'over';
    if (pct >= 80)  return 'near';
    return 'on-track';
}