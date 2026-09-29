// ─────────────────────────────────────────────────────────────
//  budget_history.js — BudgetBuddy Budget History + Detail + Charts
//  Depends on: api.js, Chart.js
// ─────────────────────────────────────────────────────────────

requireAuth();

// ── Status color mapping (driven by backend status.color) ────
const STATUS_COLORS = {
    green:  { bg: 'bg-[#dcfce7]', text: 'text-[#166534]', bar: 'bg-[#22c55e]' },
    blue:   { bg: 'bg-[#dbeafe]', text: 'text-[#1e40af]', bar: 'bg-[#3b82f6]' },
    orange: { bg: 'bg-[#ffedd5]', text: 'text-[#9a3412]', bar: 'bg-[#f97316]' },
    red:    { bg: 'bg-[#fef2f2]', text: 'text-[#991b1b]', bar: 'bg-[#ef4444]' },
};

// ── Chart Theme Colors ────
const CHART_COLORS = {
    primary: '#66547b', // text-primary
    primaryLight: '#d3beeb', // inverse-primary
    secondary: '#b2ae71', // tertiary-container
    error: '#ba1a1a',
    surfaceVariant: '#e6e1e5',
    outline: '#7b757e',
    gridLines: 'rgba(230, 225, 229, 0.5)',
    categoryPalette: [
        '#66547b', '#8b7a9f', '#b2ae71', '#d4beeb', 
        '#69577e', '#4a3a5e', '#cec98a', '#93000a'
    ]
};

// ── State ────────────────────────────────────────────────────
let currentlyExpandedCard = null; // only one card open at a time

// Chart instances
let spendingTrendChartInst = null;
let budgetVsSpentChartInst = null;
let categoryPieChartInst = null;

// ── DOM refs ─────────────────────────────────────────────────
const skeletonLoader   = document.getElementById('skeleton-loader');
const emptyState       = document.getElementById('empty-state');
const errorState       = document.getElementById('error-state');
const historyList      = document.getElementById('history-list');
const retryBtn         = document.getElementById('retry-btn');
const trendsContainer  = document.getElementById('trends-container');
const trendsEmptyState = document.getElementById('trends-empty-state');
const trendsCharts     = document.getElementById('trends-charts');

// Set Chart.js global defaults
Chart.defaults.font.family = 'Inter, sans-serif';
Chart.defaults.color = CHART_COLORS.outline;

// ── Budget History Search/Filter Toolbar ─────────────────────
let allBudgetHistory = [];

const bhToolbar = new SearchFilterToolbar({
    containerId: 'sf-toolbar',
    features: { search: true, category: false, dateRange: false, amountRange: false, sort: true },
    sortOptions: [
        { value: 'newest', label: 'Newest First' },
        { value: 'oldest', label: 'Oldest First' },
        { value: 'highest', label: 'Highest Spent' },
        { value: 'lowest', label: 'Lowest Spent' },
    ],
    onFilterChange: (filters) => {
        applyBudgetHistoryFilters(filters);
    }
});

function applyBudgetHistoryFilters(filters) {
    if (!allBudgetHistory.length) return;
    
    let filtered = [...allBudgetHistory];
    
    // Search
    if (filters.search) {
        const term = filters.search.toLowerCase();
        filtered = filtered.filter(item => 
            item.month_label.toLowerCase().includes(term) ||
            String(item.year).includes(term) ||
            (item.status && item.status.label && item.status.label.toLowerCase().includes(term))
        );
    }
    
    // Sort
    if (filters.sort === 'newest') {
        filtered.sort((a, b) => (b.year * 100 + b.month) - (a.year * 100 + a.month));
    } else if (filters.sort === 'oldest') {
        filtered.sort((a, b) => (a.year * 100 + a.month) - (b.year * 100 + b.month));
    } else if (filters.sort === 'highest') {
        filtered.sort((a, b) => b.spent - a.spent);
    } else if (filters.sort === 'lowest') {
        filtered.sort((a, b) => a.spent - b.spent);
    }
    
    if (filtered.length === 0) {
        historyList.classList.add('hidden');
        emptyState.classList.remove('hidden');
    } else {
        emptyState.classList.add('hidden');
        renderTimeline(filtered);
    }
}

// ── Load on DOMContentLoaded ─────────────────────────────────
document.addEventListener('DOMContentLoaded', loadBudgetHistory);

if (retryBtn) {
    retryBtn.addEventListener('click', () => {
        errorState.classList.add('hidden');
        skeletonLoader.classList.remove('hidden');
        loadBudgetHistory();
    });
}

async function loadBudgetHistory() {
    try {
        const history = await apiGet('/budget/history');

        // Hide skeleton
        skeletonLoader.classList.add('hidden');

        if (!history || history.length === 0) {
            emptyState.classList.remove('hidden');
            return;
        }

        allBudgetHistory = history;
        renderTrends(history);
        renderTimeline(history);

    } catch (err) {
        console.error('Budget history failed:', err.message);
        skeletonLoader.classList.add('hidden');
        errorState.classList.remove('hidden');
    }
}

// ── Render: Trends Charts ────────────────────────────────────
function renderTrends(history) {
    trendsContainer.classList.remove('hidden');

    if (history.length < 2) {
        trendsCharts.classList.add('hidden');
        trendsEmptyState.classList.remove('hidden');
        return;
    }

    trendsCharts.classList.remove('hidden');
    trendsEmptyState.classList.add('hidden');

    // Sort chronologically (oldest to newest) for trends
    const chronoHistory = [...history].sort((a, b) => {
        if (a.year !== b.year) return a.year - b.year;
        return a.month - b.month;
    });

    const labels = chronoHistory.map(item => {
        const shortMonth = item.month_label.split(' ')[0].substring(0, 3);
        return `${shortMonth} '${String(item.year).substring(2)}`;
    });
    
    const spentData = chronoHistory.map(item => item.spent);
    const budgetData = chronoHistory.map(item => item.budget);

    // 1. Line Chart: Monthly Spending Trend
    if (spendingTrendChartInst) spendingTrendChartInst.destroy();
    const ctxTrend = document.getElementById('spending-trend-chart').getContext('2d');
    
    // Gradient for line chart
    const gradient = ctxTrend.createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(102, 84, 123, 0.2)'); // primary with opacity
    gradient.addColorStop(1, 'rgba(102, 84, 123, 0)');

    spendingTrendChartInst = new Chart(ctxTrend, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Total Spent',
                data: spentData,
                borderColor: CHART_COLORS.primary,
                backgroundColor: gradient,
                borderWidth: 2,
                pointBackgroundColor: '#ffffff',
                pointBorderColor: CHART_COLORS.primary,
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: {
                callbacks: { label: (ctx) => formatCurrency(ctx.raw) }
            }},
            scales: {
                x: { grid: { display: false } },
                y: { 
                    grid: { color: CHART_COLORS.gridLines, borderDash: [5, 5] },
                    ticks: { callback: (value) => '₹' + (value >= 1000 ? (value/1000) + 'k' : value) },
                    beginAtZero: true
                }
            }
        }
    });

    // 2. Bar Chart: Budget vs Spending
    if (budgetVsSpentChartInst) budgetVsSpentChartInst.destroy();
    const ctxBar = document.getElementById('budget-vs-spent-chart').getContext('2d');
    budgetVsSpentChartInst = new Chart(ctxBar, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Budget',
                    data: budgetData,
                    backgroundColor: CHART_COLORS.primaryLight,
                    borderRadius: 4
                },
                {
                    label: 'Spent',
                    data: spentData,
                    backgroundColor: CHART_COLORS.primary,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { 
                legend: { position: 'top', labels: { usePointStyle: true, boxWidth: 8, padding: 10 } },
                tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.raw)}` } }
            },
            scales: {
                x: { grid: { display: false } },
                y: { 
                    grid: { color: CHART_COLORS.gridLines, borderDash: [5, 5] },
                    ticks: { callback: (value) => '₹' + (value >= 1000 ? (value/1000) + 'k' : value) },
                    beginAtZero: true
                }
            }
        }
    });
}

// ── Render: Timeline ─────────────────────────────────────────
function renderTimeline(history) {
    historyList.innerHTML = '';
    historyList.classList.remove('hidden');

    const yearGroups = {};
    history.forEach(item => {
        if (!yearGroups[item.year]) yearGroups[item.year] = [];
        yearGroups[item.year].push(item);
    });

    const sortedYears = Object.keys(yearGroups).sort((a, b) => b - a);

    sortedYears.forEach(year => {
        const yearHeader = document.createElement('div');
        yearHeader.className = 'flex items-center gap-3 mb-3';
        yearHeader.innerHTML = `
            <h3 class="text-headline-sm font-bold text-on-background">${year}</h3>
            <div class="flex-1 h-px bg-outline-variant/50"></div>
        `;
        historyList.appendChild(yearHeader);

        const cardsContainer = document.createElement('div');
        cardsContainer.className = 'space-y-3 mb-6';

        yearGroups[year]
            .sort((a, b) => b.month - a.month)
            .forEach(item => cardsContainer.appendChild(createMonthCard(item)));

        historyList.appendChild(cardsContainer);
    });
}

// ── Build a single month card ────────────────────────────────
function createMonthCard(item) {
    const colors = STATUS_COLORS[item.status.color] || STATUS_COLORS.blue;
    const monthName = item.month_label.split(' ')[0];

    const wrapper = document.createElement('div');
    wrapper.id = `month-${item.year}-${item.month}`;

    const card = document.createElement('div');
    card.className = 'bg-surface-container-lowest rounded-2xl border border-surface-variant/30 premium-shadow p-4 cursor-pointer hover:border-primary/30 active:scale-[0.98] transition-all';

    card.innerHTML = `
        <div class="flex justify-between items-start mb-3">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-primary-fixed/30 flex items-center justify-center">
                    <span class="material-symbols-outlined text-primary text-[20px]">calendar_month</span>
                </div>
                <div>
                    <p class="text-body-md font-bold text-on-background">${monthName}</p>
                    <p class="text-[12px] text-outline">Budget: ${formatCurrency(item.budget)}</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <span class="px-2.5 py-1 rounded-full text-[11px] font-bold ${colors.bg} ${colors.text}">${item.status.label}</span>
                <span class="material-symbols-outlined text-outline-variant text-[18px] transition-transform duration-300 chevron-icon">expand_more</span>
            </div>
        </div>

        <div class="h-2 bg-surface-container-high rounded-full overflow-hidden mb-3">
            <div class="h-full ${colors.bar} rounded-full transition-all duration-700 ease-out" style="width: ${item.budget_progress}%"></div>
        </div>

        <div class="flex justify-between text-[12px]">
            <div>
                <span class="text-outline">Spent</span>
                <p class="font-bold text-on-surface">${formatCurrency(item.spent)}</p>
            </div>
            <div class="text-center">
                <span class="text-outline">Saved</span>
                <p class="font-bold text-on-surface" style="color: ${item.saved > 0 ? '#16a34a' : '#dc2626'}">${formatCurrency(item.saved)}</p>
            </div>
            <div class="text-right">
                <span class="text-outline">Used</span>
                <p class="font-bold text-on-surface">${item.percentage_spent}%</p>
            </div>
        </div>
    `;

    const detailPanel = document.createElement('div');
    detailPanel.className = 'detail-panel hidden';
    detailPanel.id = `detail-${item.year}-${item.month}`;

    wrapper.appendChild(card);
    wrapper.appendChild(detailPanel);

    card.addEventListener('click', () => toggleDetail(item.year, item.month, card, detailPanel));

    return wrapper;
}

// ── Toggle detail panel ──────────────────────────────────────
async function toggleDetail(year, month, cardEl, panelEl) {
    const chevron = cardEl.querySelector('.chevron-icon');
    const isOpen = !panelEl.classList.contains('hidden');

    if (isOpen) {
        panelEl.classList.add('hidden');
        chevron.style.transform = 'rotate(0deg)';
        cardEl.classList.remove('border-primary/40');
        currentlyExpandedCard = null;
        return;
    }

    if (currentlyExpandedCard && currentlyExpandedCard !== panelEl) {
        currentlyExpandedCard.classList.add('hidden');
        const prevCard = currentlyExpandedCard.previousElementSibling;
        if (prevCard) {
            const prevChevron = prevCard.querySelector('.chevron-icon');
            if (prevChevron) prevChevron.style.transform = 'rotate(0deg)';
            prevCard.classList.remove('border-primary/40');
        }
    }

    currentlyExpandedCard = panelEl;
    chevron.style.transform = 'rotate(180deg)';
    cardEl.classList.add('border-primary/40');

    panelEl.innerHTML = buildDetailSkeleton();
    panelEl.classList.remove('hidden');

    try {
        const report = await apiGet(`/budget/history/${year}/${month}`);
        panelEl.innerHTML = buildDetailView(report);
        renderCategoryPieChart(report, year, month);
    } catch (err) {
        console.error(`Monthly report failed for ${year}/${month}:`, err.message);
        panelEl.innerHTML = buildDetailError();
    }
}

function buildDetailSkeleton() {
    return `
        <div class="bg-surface-container-low rounded-b-2xl border border-t-0 border-surface-variant/30 p-4 space-y-4 mt-[-8px]">
            <div class="grid grid-cols-2 gap-3">
                <div class="skeleton h-16 rounded-xl"></div>
                <div class="skeleton h-16 rounded-xl"></div>
                <div class="skeleton h-16 rounded-xl"></div>
                <div class="skeleton h-16 rounded-xl"></div>
            </div>
            <div class="skeleton h-4 w-32 mt-2"></div>
            <div class="space-y-2">
                <div class="skeleton h-10 rounded-lg"></div>
                <div class="skeleton h-10 rounded-lg"></div>
                <div class="skeleton h-10 rounded-lg"></div>
            </div>
        </div>
    `;
}

function buildDetailError() {
    return `
        <div class="bg-error-container/30 rounded-b-2xl border border-t-0 border-surface-variant/30 p-6 mt-[-8px] text-center">
            <span class="material-symbols-outlined text-on-error-container text-[24px] mb-2">error_outline</span>
            <p class="text-body-sm font-bold text-on-error-container">Unable to load this monthly report.</p>
        </div>
    `;
}

// ── Detail: full report view ─────────────────────────────────
function buildDetailView(report) {
    const colors = STATUS_COLORS[report.status.color] || STATUS_COLORS.blue;
    const hasCategoryData = report.category_breakdown && Object.keys(report.category_breakdown).length > 0;

    let categoryRows = '';
    if (hasCategoryData) {
        const sorted = Object.entries(report.category_breakdown).sort((a, b) => b[1] - a[1]);
        const totalSpent = report.total_spent || 1;

        categoryRows = sorted.map(([cat, amount], idx) => {
            const pct = Math.round((amount / totalSpent) * 100);
            const dotColor = CHART_COLORS.categoryPalette[idx % CHART_COLORS.categoryPalette.length];
            return `
                <div class="flex items-center justify-between py-2.5">
                    <div class="flex items-center gap-3 flex-1 min-w-0">
                        <div class="w-2.5 h-2.5 rounded-full" style="background-color: ${dotColor}"></div>
                        <span class="text-body-sm font-semibold text-on-surface truncate">${cat}</span>
                    </div>
                    <div class="flex items-center gap-3">
                        <span class="text-body-sm font-bold text-on-surface">${formatCurrency(amount)}</span>
                        <span class="text-[12px] text-outline w-10 text-right">${pct}%</span>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        categoryRows = '<p class="text-body-sm text-outline py-2">No category data available.</p>';
    }

    let largestExpenseHtml = '';
    if (report.largest_expense) {
        const le = report.largest_expense;
        largestExpenseHtml = `
            <div class="flex items-center gap-3 bg-surface-container rounded-xl p-3">
                <div class="w-9 h-9 rounded-lg bg-error-container/50 flex items-center justify-center">
                    <span class="material-symbols-outlined text-on-error-container text-[18px]">trending_up</span>
                </div>
                <div class="flex-1">
                    <p class="text-[12px] text-outline">Largest Expense</p>
                    <p class="text-body-sm font-bold text-on-surface">${formatCurrency(le.amount)} · ${le.category}</p>
                </div>
                <span class="text-[11px] text-outline">${le.date}</span>
            </div>
        `;
    }

    let aiReportHtml = '';
    if (report.ai_report && report.ai_report.status === 'not_generated') {
        aiReportHtml = `
            <div class="flex items-center gap-3 bg-primary-fixed/20 rounded-xl p-3">
                <div class="w-9 h-9 rounded-lg bg-primary-fixed/40 flex items-center justify-center">
                    <span class="material-symbols-outlined text-primary text-[18px]" style="font-variation-settings: 'FILL' 1;">auto_awesome</span>
                </div>
                <div>
                    <p class="text-body-sm font-semibold text-primary">Monthly AI Report</p>
                    <p class="text-[12px] text-outline">Coming Soon</p>
                </div>
            </div>
        `;
    } else if (report.ai_report && report.ai_report.status === 'ready' && report.ai_report.data) {
        aiReportHtml = `
            <div class="bg-primary-fixed/20 rounded-xl p-3 space-y-1">
                <div class="flex items-center gap-2 mb-1">
                    <span class="material-symbols-outlined text-primary text-[18px]" style="font-variation-settings: 'FILL' 1;">auto_awesome</span>
                    <p class="text-body-sm font-semibold text-primary">Monthly AI Report</p>
                </div>
                <p class="text-body-sm text-on-surface">${report.ai_report.data.insight || ''}</p>
                <p class="text-[12px] text-primary font-medium">${report.ai_report.data.recommendation || ''}</p>
            </div>
        `;
    }

    return `
        <div class="bg-surface-container-low rounded-b-2xl border border-t-0 border-surface-variant/30 p-4 space-y-4 mt-[-8px]">
            <div class="grid grid-cols-2 gap-3">
                <div class="bg-surface-container-lowest rounded-xl p-3 border border-surface-variant/20">
                    <p class="text-[11px] text-outline uppercase tracking-wider mb-1">Monthly Budget</p>
                    <p class="text-body-md font-bold text-on-surface">${formatCurrency(report.monthly_budget)}</p>
                </div>
                <div class="bg-surface-container-lowest rounded-xl p-3 border border-surface-variant/20">
                    <p class="text-[11px] text-outline uppercase tracking-wider mb-1">Total Spent</p>
                    <p class="text-body-md font-bold text-on-surface">${formatCurrency(report.total_spent)}</p>
                </div>
                <div class="bg-surface-container-lowest rounded-xl p-3 border border-surface-variant/20">
                    <p class="text-[11px] text-outline uppercase tracking-wider mb-1">Saved</p>
                    <p class="text-body-md font-bold" style="color: ${report.saved > 0 ? '#16a34a' : '#dc2626'}">${formatCurrency(report.saved)}</p>
                </div>
                <div class="bg-surface-container-lowest rounded-xl p-3 border border-surface-variant/20">
                    <p class="text-[11px] text-outline uppercase tracking-wider mb-1">Budget Used</p>
                    <p class="text-body-md font-bold text-on-surface">${report.percentage_spent}%</p>
                </div>
            </div>

            <div class="grid grid-cols-3 gap-2 text-center">
                <div class="bg-surface-container-lowest rounded-xl p-2.5 border border-surface-variant/20">
                    <p class="text-[10px] text-outline uppercase">Expenses</p>
                    <p class="text-body-sm font-bold text-on-surface">${report.expense_count}</p>
                </div>
                <div class="bg-surface-container-lowest rounded-xl p-2.5 border border-surface-variant/20">
                    <p class="text-[10px] text-outline uppercase">Top Category</p>
                    <p class="text-body-sm font-bold text-on-surface truncate">${report.top_category || '—'}</p>
                </div>
                <div class="bg-surface-container-lowest rounded-xl p-2.5 border border-surface-variant/20">
                    <p class="text-[10px] text-outline uppercase">Avg/Day</p>
                    <p class="text-body-sm font-bold text-on-surface">${formatCurrency(report.average_daily_spending)}</p>
                </div>
            </div>

            ${largestExpenseHtml}

            <!-- Category Breakdown with Chart -->
            <div>
                <p class="text-label-md font-bold text-on-surface-variant mb-2">Category Breakdown</p>
                <div class="bg-surface-container-lowest rounded-xl border border-surface-variant/20 p-3 mb-2 flex justify-center ${!hasCategoryData ? 'hidden' : ''}">
                    <div class="w-48 h-48 relative">
                        <canvas id="pie-chart-${report.year}-${report.month}"></canvas>
                    </div>
                </div>
                <div class="bg-surface-container-lowest rounded-xl border border-surface-variant/20 px-3 divide-y divide-surface-container">
                    ${categoryRows}
                </div>
            </div>

            ${aiReportHtml}
        </div>
    `;
}

// ── Detail: Pie Chart Rendering ──────────────────────────────
function renderCategoryPieChart(report, year, month) {
    if (!report.category_breakdown || Object.keys(report.category_breakdown).length === 0) return;
    
    const canvasId = `pie-chart-${year}-${month}`;
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    if (categoryPieChartInst) {
        categoryPieChartInst.destroy();
    }

    const sorted = Object.entries(report.category_breakdown).sort((a, b) => b[1] - a[1]);
    const labels = sorted.map(i => i[0]);
    const data = sorted.map(i => i[1]);
    
    // Cycle through palette for colors
    const bgColors = labels.map((_, i) => CHART_COLORS.categoryPalette[i % CHART_COLORS.categoryPalette.length]);

    categoryPieChartInst = new Chart(ctx.getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: bgColors,
                borderWidth: 2,
                borderColor: '#ffffff',
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${formatCurrency(ctx.raw)}` } }
            }
        }
    });
}

// ── Utilities ────────────────────────────────────────────────
function formatCurrency(amount) {
    return `₹${Number(amount).toLocaleString('en-IN')}`;
}


