// ─────────────────────────────────────────────────────────────
//  dashboard.js — BudgetBuddy Dashboard
//  Depends on: api.js + Chart.js
//
//  Backend endpoints expected:
//    GET /expenses          → list of all expenses for this user
//    GET /expenses/summary  → { total_spent, monthly_spent, by_category }
//                             (if you have this route)
//
//  ⚠️  If you don't have a /summary endpoint yet, everything
//  is computed client-side from /expenses below.
//  ⚠️  Verify field names match your expense_model.py
// ─────────────────────────────────────────────────────────────

requireAuth();

// ── DOM refs — match the IDs in your dashboard.html ──────────
const totalBalanceEl   = document.getElementById('total-balance');
const monthlySpendEl   = document.getElementById('monthly-spend');
const budgetRemainingEl = document.getElementById('budget-remaining');
const transactionsList  = document.getElementById('transactions-list');
const chartCanvas       = document.getElementById('spending-chart');
const logoutBtn         = document.getElementById('logout-btn');

// ── Logout ────────────────────────────────────────────────────
logoutBtn && logoutBtn.addEventListener('click', logout);

// ── Load all data on page open ────────────────────────────────
document.addEventListener('DOMContentLoaded', loadDashboard);

async function loadDashboard() {
    try {
        // ⚠️ Change '/expenses' to match your actual route
        const expenses = await apiGet('/expenses');
        renderDashboard(expenses);
    } catch (err) {
        console.error('Dashboard load failed:', err.message);
    }
}

// ── Compute summary from raw expenses list ────────────────────
function renderDashboard(expenses) {
    const now         = new Date();
    const thisMonth   = now.getMonth();
    const thisYear    = now.getFullYear();

    // Filter to current month
    // ⚠️ Adjust 'expense.date' to match your model's date field name
    const monthExpenses = expenses.filter(e => {
        const d = new Date(e.date);
        return d.getMonth() === thisMonth && d.getFullYear() === thisYear;
    });

    // Total spent this month
    const monthlyTotal = monthExpenses.reduce((sum, e) => sum + e.amount, 0);

    // Spending by category
    const byCategory = {};
    monthExpenses.forEach(e => {
        byCategory[e.category] = (byCategory[e.category] || 0) + e.amount;
    });

    // ── Update stat cards ─────────────────────────────────────
    if (monthlySpendEl) {
        monthlySpendEl.textContent = `₹${monthlyTotal.toLocaleString('en-IN')}`;
    }

    // Recent 5 transactions (newest first)
    // ⚠️ Adjust field names (amount, category, date, note) to your model
    const recent = [...expenses]
        .sort((a, b) => new Date(b.date) - new Date(a.date))
        .slice(0, 5);

    renderTransactions(recent);
    renderChart(byCategory);
}

// ── Recent transactions list ──────────────────────────────────
function renderTransactions(transactions) {
    if (!transactionsList) return;

    if (transactions.length === 0) {
        transactionsList.innerHTML = `<p style="color:var(--color-text-secondary); font-size:14px; padding:1rem 0;">No transactions yet. Add your first expense!</p>`;
        return;
    }

    transactionsList.innerHTML = transactions.map(t => `
        <div class="transaction-item">
            <div class="transaction-info">
                <span class="transaction-category">${t.category}</span>
                <span class="transaction-date">${formatDate(t.date)}</span>
                ${t.note ? `<span class="transaction-note">${t.note}</span>` : ''}
            </div>
            <span class="transaction-amount">-₹${t.amount.toLocaleString('en-IN')}</span>
        </div>
    `).join('');
}

// ── Spending by category — donut chart via Chart.js ──────────
let chartInstance = null;

function renderChart(byCategory) {
    if (!chartCanvas) return;

    // BudgetBuddy purple palette for chart segments
    const colors = [
        '#9784ae', '#b8a4d4', '#7e6b94',
        '#ccb3e7', '#6b5a84', '#d8c8f0', '#4a3f59',
    ];

    const labels  = Object.keys(byCategory);
    const data    = Object.values(byCategory);

    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(chartCanvas, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors.slice(0, labels.length),
                borderWidth: 0,
            }],
        },
        options: {
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { font: { family: 'Inter', size: 12 }, padding: 16 },
                },
                tooltip: {
                    callbacks: {
                        label: ctx => ` ₹${ctx.parsed.toLocaleString('en-IN')}`,
                    },
                },
            },
        },
    });
}

// ── Utility ───────────────────────────────────────────────────
function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-IN', {
        day: 'numeric', month: 'short',
    });
}