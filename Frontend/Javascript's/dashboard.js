// ─────────────────────────────────────────────────────────────
//  dashboard.js — BudgetBuddy Dashboard
//  Depends on: api.js + Chart.js
//
//  Backend endpoints used:
//    GET /users/me    → { id, name, email, password }
//    GET /analytics   → { total_spent, remaining_budget,
//                         category_breakdown, top_category,
//                         expense_count, percentage_spent }
//    GET /budget/     → { id, monthly_budget, month, year, user_id }
//    GET /expenses    → [ { id, amount, category, subcategory,
//                           note, created_at, user_id }, ... ]
// ─────────────────────────────────────────────────────────────

requireAuth();

// ── Category config: icon + color scheme for all 20 categories ──
const CATEGORY_CONFIG = {
    'Food':          { icon: 'restaurant',          scheme: 'secondary' },
    'Transport':     { icon: 'directions_car',      scheme: 'primary'   },
    'Entertainment': { icon: 'sports_esports',      scheme: 'tertiary'  },
    'Shopping':      { icon: 'shopping_bag',        scheme: 'secondary' },
    'Bills':         { icon: 'receipt_long',         scheme: 'primary'   },
    'Health':        { icon: 'health_and_safety',   scheme: 'tertiary'  },
    'Education':     { icon: 'school',              scheme: 'secondary' },
    'Subscriptions': { icon: 'subscriptions',       scheme: 'primary'   },
    'EMI Loans':     { icon: 'account_balance',     scheme: 'tertiary'  },
    'Rent':          { icon: 'home',                scheme: 'primary'   },
    'Investments':   { icon: 'trending_up',         scheme: 'secondary' },
    'Savings':       { icon: 'savings',             scheme: 'tertiary'  },
    'Travel':        { icon: 'flight',              scheme: 'primary'   },
    'Family':        { icon: 'family_restroom',     scheme: 'secondary' },
    'Personal Care': { icon: 'spa',                 scheme: 'tertiary'  },
    'Gifts':         { icon: 'redeem',              scheme: 'primary'   },
    'Donations':     { icon: 'volunteer_activism',  scheme: 'secondary' },
    'Insurance':     { icon: 'shield',              scheme: 'tertiary'  },
    'Taxes':         { icon: 'request_quote',       scheme: 'primary'   },
    'Other':         { icon: 'more_horiz',          scheme: 'secondary' },
};

// Color scheme classes — matches the original HTML card patterns exactly
const COLOR_SCHEMES = {
    secondary: {
        iconBg:   'bg-secondary-container/30',
        iconText: 'text-on-secondary-container',
        barColor: 'bg-secondary',
    },
    primary: {
        iconBg:   'bg-primary-fixed/30',
        iconText: 'text-primary',
        barColor: 'bg-primary',
    },
    tertiary: {
        iconBg:   'bg-tertiary-fixed/30',
        iconText: 'text-tertiary',
        barColor: 'bg-tertiary',
    },
};

// ── DOM refs — match the IDs in dashboard.html ───────────────
const greetingEl         = document.getElementById('greeting');
const userNameEl         = document.getElementById('user-name');
const coachInsightEl     = document.getElementById('coach-insight-content');
const coachReminderEl    = document.getElementById('coach-reminder-content');
const insightTimeEl      = document.getElementById('insight-time');
const healthTitleEl      = document.getElementById('health-title');
const healthStatusEl     = document.getElementById('health-status');
const remainingBudgetEl  = document.getElementById('remaining-budget');
const totalSpentEl       = document.getElementById('total-spent');
const progressTextEl     = document.getElementById('progress-text');
const daysLeftEl         = document.getElementById('days-left');
const progressBarEl      = document.getElementById('progress-bar');
const totalBalanceEl     = document.getElementById('total-balance');
const categoriesListEl   = document.getElementById('categories-list');
const transactionsListEl = document.getElementById('transactions-list');

// ── Load all data on page open ────────────────────────────────
document.addEventListener('DOMContentLoaded', loadDashboard);

async function loadDashboard() {
    try {
        // Set time-based greeting immediately
        setGreeting();
        setDaysLeft();

        // Fetch all data in parallel — catch individually so one
        // failure doesn't block the rest
        const [user, analytics, budget, expenses, aiInsight] = await Promise.all([
            apiGet('/users/me').catch(e => { console.warn('users/me:', e.message); return null; }),
            apiGet('/analytics').catch(e => { console.warn('analytics:', e.message); return null; }),
            apiGet('/budget/').catch(e => { console.warn('budget:', e.message); return null; }),
            apiGet('/expenses').catch(e => { console.warn('expenses:', e.message); return []; }),
            apiGet('/ai/insight').catch(e => { console.warn('ai insight:', e.message); return null; }),
        ]);

        // ── User name ────────────────────────────────────────
        if (user && user.name) {
            userNameEl.textContent = user.name;
        } else {
            userNameEl.textContent = 'Buddy';
        }

        // ── Budget / Analytics ───────────────────────────────
        const monthlyBudget = budget ? budget.monthly_budget : 0;

        if (analytics) {
            renderHealthCard(analytics, monthlyBudget);
            renderCategories(analytics.category_breakdown, monthlyBudget);
        } else {
            // No analytics yet (no expenses / no budget set)
            if (healthTitleEl)  healthTitleEl.textContent  = 'Set a Budget!';
            if (healthStatusEl) healthStatusEl.textContent = 'New';
        }
        
        renderInsight(aiInsight);

        if (totalBalanceEl) {
            totalBalanceEl.textContent = formatCurrency(monthlyBudget);
        }

        // ── Transactions ─────────────────────────────────────
        renderTransactions(expenses);

    } catch (err) {
        console.error('Dashboard load failed:', err.message);
    }
}

// ── Greeting (time-of-day) ────────────────────────────────────
function setGreeting() {
    const hour = new Date().getHours();
    let text = 'Good evening,';
    if (hour < 12)      text = 'Good morning,';
    else if (hour < 17) text = 'Good afternoon,';
    if (greetingEl) greetingEl.textContent = text;
}

// ── Days remaining in month ───────────────────────────────────
function setDaysLeft() {
    const now     = new Date();
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
    const remaining = lastDay - now.getDate();
    if (daysLeftEl) daysLeftEl.textContent = `${remaining} days left`;
}

// ── Health card ───────────────────────────────────────────────
function renderHealthCard(analytics, monthlyBudget) {
    const { total_spent, remaining_budget, percentage_spent } = analytics;

    if (totalSpentEl)       totalSpentEl.textContent       = formatCurrency(total_spent);
    if (remainingBudgetEl)  remainingBudgetEl.textContent   = formatCurrency(remaining_budget);
    if (progressBarEl)      progressBarEl.style.width       = `${Math.min(percentage_spent, 100)}%`;
    if (progressTextEl)     progressTextEl.textContent      = `${percentage_spent}% of budget used`;

    // Health status label
    const { title, badge, styleClass } = computeHealthStatus(percentage_spent);
    if (healthTitleEl)  healthTitleEl.textContent  = title;
    if (healthStatusEl) {
        healthStatusEl.textContent = badge;
        healthStatusEl.className = `px-3 py-1 rounded-full text-[12px] font-bold backdrop-blur-md ${styleClass}`;
    }
}

function computeHealthStatus(pct) {
    if (pct < 50)  return { title: "You're on Track!",  badge: 'Excellent', styleClass: 'bg-white/20 text-on-primary' };
    if (pct < 75)  return { title: 'Watch Spending',    badge: 'Good',      styleClass: 'bg-white/20 text-on-primary' };
    if (pct < 90)  return { title: 'Getting Tight',     badge: 'Caution',   styleClass: 'bg-error-container text-on-error-container' };
    return              { title: 'Over Budget!',        badge: 'Critical',  styleClass: 'bg-error text-on-error shadow-[0_0_15px_rgba(186,26,26,0.5)]' };
}

// ── Categories — built from analytics.category_breakdown ──────
function renderCategories(categoryBreakdown, monthlyBudget) {
    if (!categoriesListEl || !categoryBreakdown) return;

    categoriesListEl.innerHTML = '';

    // Sort categories by amount spent, highest first
    const entries = Object.entries(categoryBreakdown)
        .sort((a, b) => b[1] - a[1]);

    entries.forEach(([category, amount]) => {
        const config = CATEGORY_CONFIG[category] || CATEGORY_CONFIG['Other'];
        const scheme = COLOR_SCHEMES[config.scheme];
        const pct    = monthlyBudget > 0
            ? Math.min(Math.round((amount / monthlyBudget) * 100), 100)
            : 0;

        const card = document.createElement('div');
        card.className = 'bg-surface-container-lowest p-4 rounded-2xl border border-surface-variant/30 premium-shadow flex items-center gap-4';

        card.innerHTML = `
            <div class="w-12 h-12 rounded-xl ${scheme.iconBg} flex items-center justify-center ${scheme.iconText}">
                <span class="material-symbols-outlined">${config.icon}</span>
            </div>
            <div class="flex-1">
                <div class="flex justify-between mb-1.5">
                    <span class="text-body-md font-bold text-on-surface">${category}</span>
                    <span class="text-body-md font-bold text-on-surface">${formatCurrency(amount)}</span>
                </div>
                <div class="h-1.5 bg-surface-container-high rounded-full overflow-hidden">
                    <div class="h-full ${scheme.barColor} rounded-full" style="width: ${pct}%"></div>
                </div>
            </div>
        `;

        categoriesListEl.appendChild(card);
    });
}

// ── Recent transactions — last 5 expenses ─────────────────────
function renderTransactions(expenses) {
    if (!transactionsListEl) return;

    transactionsListEl.innerHTML = '';

    if (!expenses || expenses.length === 0) {
        transactionsListEl.innerHTML = `
            <div class="p-6 text-center">
                <p class="text-body-sm text-outline">No transactions yet. Add your first expense!</p>
            </div>
        `;
        return;
    }

    // Sort by expense_date (fallback to created_at) descending, take latest 5
    const recent = [...expenses]
        .sort((a, b) => new Date(b.expense_date || b.created_at) - new Date(a.expense_date || a.created_at))
        .slice(0, 5);

    recent.forEach(expense => {
        const config = CATEGORY_CONFIG[expense.category] || CATEGORY_CONFIG['Other'];

        const item = document.createElement('div');
        item.className = 'flex items-center justify-between p-4';

        item.innerHTML = `
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-surface-container flex items-center justify-center rounded-full">
                    <span class="material-symbols-outlined text-primary text-[20px]">${config.icon}</span>
                </div>
                <div>
                    <p class="text-body-md font-bold text-on-background">${expense.note || expense.category}</p>
                    <p class="text-[12px] text-outline">${formatDate(expense.expense_date || expense.created_at)}</p>
                </div>
            </div>
            <p class="text-body-md font-bold text-error">-${formatCurrency(expense.amount)}</p>
        `;

        transactionsListEl.appendChild(item);
    });
}

// ── Coach Insight ─────────────────────────────────────────────
function renderInsight(aiInsight) {
    if (!coachInsightEl) return;
    
    // Remove loading animation
    coachInsightEl.classList.remove('animate-pulse');

    if (!aiInsight) {
        coachInsightEl.textContent = 'Buddy is unavailable right now.';
        if (coachReminderEl) {
            coachReminderEl.textContent = 'Your financial insights will return shortly.';
        }
        return;
    }

    // Set Insight
    coachInsightEl.textContent = aiInsight.insight;
    
    // Set Reminder
    if (coachReminderEl) {
        coachReminderEl.textContent = aiInsight.reminder;
    }
    
    // Set Last Updated Time
    if (insightTimeEl && aiInsight.last_updated) {
        const updatedTime = new Date(aiInsight.last_updated);
        const now = new Date();
        const diffMs = now - updatedTime;
        const diffMins = Math.floor(diffMs / 60000);
        
        if (diffMins < 60) {
            insightTimeEl.textContent = diffMins <= 1 ? '(Just now)' : `(${diffMins}m ago)`;
        } else {
            const diffHours = Math.floor(diffMins / 60);
            insightTimeEl.textContent = diffHours === 1 ? '(1h ago)' : `(${diffHours}h ago)`;
        }
    }
}

// ── Utilities ─────────────────────────────────────────────────
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
        return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
    }
}
