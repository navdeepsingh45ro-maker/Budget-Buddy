// ─────────────────────────────────────────────────────────────
//  notifications.js — BudgetBuddy Notification Center
//  Depends on: api.js, Tailwind CSS utilities
// ─────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', initNotifications);

let drawerEl = null;
let backdropEl = null;
let listEl = null;
let badgeEl = null;
let unreadCount = 0;

function initNotifications() {
    // 1. Find the notification button (bell icon)
    let navBtn = document.getElementById('nav-notification-btn') || document.getElementById('notifications');
    if (!navBtn) {
        // Fallback robust search
        const buttons = Array.from(document.querySelectorAll('button, span'));
        navBtn = buttons.find(b => b.textContent.includes('notifications') && b.classList.contains('material-symbols-outlined'));
    }

    if (!navBtn) return; // No notification button on this page

    // If it's just a span (like in dashboard), get its parent button if possible
    if (navBtn.tagName === 'SPAN' && navBtn.parentElement.tagName === 'BUTTON') {
        navBtn = navBtn.parentElement;
    }

    // 2. Inject Badge into Button
    navBtn.classList.add('relative');
    const existingBadge = navBtn.querySelector('.bg-error');
    if (!existingBadge) {
        badgeEl = document.createElement('span');
        badgeEl.className = 'absolute top-1 right-1 w-2.5 h-2.5 bg-error rounded-full border-2 border-background hidden transition-all duration-300 scale-0';
        navBtn.appendChild(badgeEl);
    } else {
        badgeEl = existingBadge;
        badgeEl.classList.add('transition-all', 'duration-300', 'scale-0');
    }

    // 3. Inject Drawer HTML
    injectDrawerHTML();

    // 4. Attach Event Listeners
    navBtn.addEventListener('click', openDrawer);
    document.getElementById('nc-close-btn').addEventListener('click', closeDrawer);
    backdropEl.addEventListener('click', closeDrawer);
    document.getElementById('nc-mark-read-btn').addEventListener('click', markAllRead);
    document.getElementById('nc-settings-btn').addEventListener('click', openSettings);
    document.getElementById('nc-back-btn').addEventListener('click', closeSettings);

    // 5. Initial fetch & polling
    pollUnreadCount();
    setInterval(pollUnreadCount, 60000); // every 60s
    
    // 6. Local Push Integration
    initPushNotifications();
    checkSyncParams();
}

async function initPushNotifications() {
    if (!('serviceWorker' in navigator) || !('Notification' in window)) return;
    
    try {
        await navigator.serviceWorker.register('../Javascript\'s/service-worker.js');
        
        // Request permission only if not denied
        if (Notification.permission === 'default') {
            await Notification.requestPermission();
        }
    } catch (err) {
        console.error('Service Worker registration failed:', err);
    }
}

async function checkSyncParams() {
    // 5. Synchronization - deep linking from service worker
    const params = new URLSearchParams(window.location.search);
    const syncId = params.get('sync_notif');
    const actionType = params.get('action_type');
    
    if (syncId) {
        // Clean URL to prevent repeated marking on refresh
        const cleanUrl = window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);
        
        // Mark as read in DB
        try {
            await apiPatch(`/notifications/${syncId}/read`);
        } catch (e) {
            console.error('Failed to sync notification read state', e);
        }
        
        // Navigate
        const target = getNotificationTarget(actionType, null);
        if (target && !window.location.pathname.includes(target)) {
            window.location.href = target;
        }
    }
}

function injectDrawerHTML() {
    const container = document.createElement('div');
    container.innerHTML = `
        <!-- Backdrop -->
        <div id="nc-backdrop" class="fixed inset-0 bg-scrim/40 backdrop-blur-sm z-[90] hidden opacity-0 transition-opacity duration-300"></div>
        
        <!-- Drawer -->
        <div id="nc-drawer" class="fixed top-0 right-0 h-full w-full sm:w-[400px] bg-surface-container-lowest z-[100] transform translate-x-full transition-transform duration-300 ease-[cubic-bezier(0.2,0,0,1)] flex flex-col premium-shadow rounded-l-2xl sm:rounded-none">
            
            <!-- Header -->
            <div class="px-6 py-4 flex items-center justify-between border-b border-surface-variant/30 bg-surface-container-lowest/80 backdrop-blur-md">
                <div class="flex items-center gap-3">
                    <button id="nc-close-btn" class="material-symbols-outlined p-2 -ml-2 text-on-surface-variant hover:bg-surface-container rounded-full transition-all active:scale-95">close</button>
                    <button id="nc-back-btn" aria-label="Back to notifications" class="material-symbols-outlined p-2 -ml-2 text-on-surface-variant hover:bg-surface-container rounded-full transition-all active:scale-95 hidden">arrow_back</button>
                    <h2 id="nc-title" class="font-headline-sm font-bold text-on-background">Notifications</h2>
                </div>
                <div class="flex items-center gap-2">
                    <button id="nc-mark-read-btn" class="text-label-md font-bold text-primary hover:text-primary-fixed transition-colors hidden">Mark all read</button>
                    <button id="nc-settings-btn" aria-label="Notification settings" class="material-symbols-outlined p-2 -mr-2 text-on-surface-variant hover:bg-surface-container rounded-full transition-all active:scale-95">settings</button>
                </div>
            </div>

            <!-- Content Area -->
            <div id="nc-list" class="flex-1 overflow-y-auto p-4 space-y-6">
                <!-- Injected via JS -->
            </div>

            <!-- Settings Area -->
            <div id="nc-settings" class="flex-1 overflow-y-auto p-4 space-y-3 hidden">
                <p id="nc-settings-error" role="alert" class="hidden text-body-sm text-error bg-error-container/30 rounded-xl px-3 py-2"></p>
                <div id="nc-settings-rows" class="space-y-2"></div>
            </div>
        </div>
    `;
    document.body.appendChild(container);

    drawerEl = document.getElementById('nc-drawer');
    backdropEl = document.getElementById('nc-backdrop');
    listEl = document.getElementById('nc-list');
}

// ── Polling & Badge ─────────────────────────────────────────────────

async function pollUnreadCount() {
    if (!isLoggedIn()) return;
    try {
        const data = await apiGet('/notifications/unread-count');
        
        if (data.unread_count > unreadCount && unreadCount !== 0) {
            // Unread count increased while app is open -> fetch and show local push
            fetchAndShowLocalPushes();
        } else if (data.unread_count > 0 && unreadCount === 0) {
            // First load or transition from 0 -> fetch silently just to log shown state
            fetchAndShowLocalPushes(true);
        }
        
        updateBadge(data.unread_count);
    } catch (err) {
        console.error('Failed to poll notifications', err);
    }
}

async function fetchAndShowLocalPushes(silentInit = false) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    
    try {
        const data = await apiGet('/notifications?limit=10'); 
        const notifs = data.notifications || [];
        
        let shownIds = [];
        try {
            shownIds = JSON.parse(localStorage.getItem('bb_shown_pushes') || '[]');
        } catch (e) { shownIds = []; }
        
        notifs.forEach(n => {
            if (!n.is_read && !shownIds.includes(n.id)) {
                if (!silentInit) {
                    showLocalNotification(n);
                }
                shownIds.push(n.id);
            }
        });
        
        if (shownIds.length > 100) shownIds = shownIds.slice(-100);
        localStorage.setItem('bb_shown_pushes', JSON.stringify(shownIds));
        
    } catch (err) {
        console.error('Failed to fetch for local pushes', err);
    }
}

function showLocalNotification(notif) {
    const requireInteraction = notif.priority === 'critical';
    const silent = notif.priority === 'info';
    
    // Attempt to pass to service worker if active (for better background click handling)
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        // We let the SW handle it if we want, but since we are in the active page,
        // we can just show it directly. We'll use the SW registration to show it 
        // to ensure mobile compatibility.
        navigator.serviceWorker.ready.then(reg => {
            reg.showNotification(notif.title, {
                body: notif.message,
                icon: 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png', // Generic fallback
                requireInteraction: requireInteraction,
                silent: silent,
                data: {
                    notification_id: notif.id,
                    action_type: notif.action_type
                }
            });
        });
    } else {
        // Fallback for desktop browsers without SW active
        const n = new Notification(notif.title, {
            body: notif.message,
            requireInteraction: requireInteraction,
            silent: silent
        });
        
        n.onclick = function(e) {
            e.preventDefault();
            n.close();
            window.focus();
            apiPatch(`/notifications/${notif.id}/read`).catch(console.error);
            navigateForNotification(notif.action_type, notif.action_payload);
        };
    }
}

function updateBadge(count) {
    unreadCount = count;
    if (count > 0) {
        badgeEl.classList.remove('hidden');
        // Small delay to allow display:block to apply before scaling up
        setTimeout(() => {
            badgeEl.classList.remove('scale-0');
            badgeEl.classList.add('scale-100');
        }, 10);
    } else {
        badgeEl.classList.remove('scale-100');
        badgeEl.classList.add('scale-0');
        setTimeout(() => badgeEl.classList.add('hidden'), 300);
    }
    
    const markReadBtn = document.getElementById('nc-mark-read-btn');
    if (markReadBtn) {
        if (count > 0) markReadBtn.classList.remove('hidden');
        else markReadBtn.classList.add('hidden');
    }
}

// ── Drawer Interactions ─────────────────────────────────────────────

function openDrawer() {
    backdropEl.classList.remove('hidden');
    // trigger reflow
    void backdropEl.offsetWidth;
    backdropEl.classList.remove('opacity-0');
    backdropEl.classList.add('opacity-100');
    
    drawerEl.classList.remove('translate-x-full');
    drawerEl.classList.add('translate-x-0');

    showListView();
    fetchNotifications();
}

function closeDrawer() {
    backdropEl.classList.remove('opacity-100');
    backdropEl.classList.add('opacity-0');
    
    drawerEl.classList.remove('translate-x-0');
    drawerEl.classList.add('translate-x-full');
    
    setTimeout(() => {
        backdropEl.classList.add('hidden');
    }, 300);
}

// ── Fetching & Rendering ────────────────────────────────────────────

async function fetchNotifications() {
    listEl.innerHTML = buildSkeleton();
    
    try {
        const data = await apiGet('/notifications');
        const notifs = data.notifications || [];
        
        if (notifs.length === 0) {
            listEl.innerHTML = buildEmptyState();
            return;
        }

        renderGroupedNotifications(notifs);

    } catch (err) {
        console.error(err);
        listEl.innerHTML = buildErrorState();
    }
}

function renderGroupedNotifications(notifs) {
    listEl.innerHTML = '';
    
    const groups = {
        'Today': [],
        'Yesterday': [],
        'Last 7 Days': [],
        'Earlier': []
    };

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const last7Days = new Date(today);
    last7Days.setDate(last7Days.getDate() - 7);

    notifs.forEach(n => {
        const d = new Date(n.created_at + 'Z'); // parse UTC
        if (d >= today) groups['Today'].push(n);
        else if (d >= yesterday) groups['Yesterday'].push(n);
        else if (d >= last7Days) groups['Last 7 Days'].push(n);
        else groups['Earlier'].push(n);
    });

    Object.entries(groups).forEach(([groupName, items]) => {
        if (items.length === 0) return;

        const section = document.createElement('div');
        section.className = 'space-y-3';
        
        section.innerHTML = `
            <h3 class="text-label-md font-bold text-on-surface-variant uppercase tracking-wider pl-1 pt-2">${escapeHtml(groupName)}</h3>
            <div class="space-y-2 group-list"></div>
        `;
        
        const groupList = section.querySelector('.group-list');
        
        items.forEach(n => {
            groupList.appendChild(createNotificationCard(n));
        });

        listEl.appendChild(section);
    });
}

function createNotificationCard(n) {
    const isUnread = !n.is_read;
    const card = document.createElement('div');
    card.className = `group relative p-4 rounded-2xl border transition-all cursor-pointer ${
        isUnread 
        ? 'bg-surface-container-low border-primary/20 hover:bg-surface-container hover:border-primary/40 premium-shadow' 
        : 'bg-surface-container-lowest border-surface-variant/30 hover:bg-surface-container-low opacity-80'
    }`;
    card.id = `notif-${n.id}`;

    // Color mapping based on priority
    const colors = {
        info: 'text-primary bg-primary-fixed/30',
        success: 'text-[#16a34a] bg-[#dcfce7]',
        warning: 'text-[#ea580c] bg-[#ffedd5]',
        critical: 'text-[#dc2626] bg-[#fee2e2]'
    };
    
    const iconColorClass = colors[n.priority] || colors.info;
    const timeAgo = formatTimeAgo(new Date(n.created_at + 'Z'));

    card.innerHTML = `
        <div class="flex gap-3 relative z-10">
            <!-- Icon -->
            <div class="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${iconColorClass} mt-1">
                <span class="material-symbols-outlined text-[20px]">${escapeHtml(n.icon || 'notifications')}</span>
            </div>
            
            <!-- Content -->
            <div class="flex-1 min-w-0 pr-6">
                <div class="flex items-start justify-between gap-2 mb-1">
                    <p class="text-label-lg font-bold text-on-surface truncate">${escapeHtml(n.title)}</p>
                    <span class="text-[11px] text-outline flex-shrink-0 whitespace-nowrap mt-0.5">${escapeHtml(timeAgo)}</span>
                </div>
                <p class="text-body-sm text-on-surface-variant line-clamp-2">${escapeHtml(n.message)}</p>
            </div>
        </div>

        <!-- Unread Indicator -->
        ${isUnread ? '<div class="absolute top-4 right-4 w-2 h-2 bg-primary rounded-full indicator-dot"></div>' : ''}
        
        <!-- Delete Button (Shown on hover) -->
        <button class="delete-btn absolute top-3 right-3 p-1.5 text-outline hover:text-error hover:bg-error-container/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity z-20">
            <span class="material-symbols-outlined text-[16px]">delete</span>
        </button>
    `;

    // Handle Click (Mark Read + Navigate)
    card.addEventListener('click', (e) => {
        if (e.target.closest('.delete-btn')) return; // handled separately
        handleNotificationClick(n, card);
    });

    // Handle Delete
    const delBtn = card.querySelector('.delete-btn');
    delBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        card.style.opacity = '0';
        card.style.transform = 'scale(0.95)';
        setTimeout(() => card.remove(), 300);
        
        try {
            await apiDelete(`/notifications/${n.id}`);
            if (isUnread && unreadCount > 0) updateBadge(unreadCount - 1);
        } catch (err) {
            console.error('Failed to delete notification', err);
        }
    });

    return card;
}

// ── Actions ─────────────────────────────────────────────────────────

async function handleNotificationClick(n, cardEl) {
    // 1. Mark visually read
    if (!n.is_read) {
        n.is_read = true;
        cardEl.classList.remove('bg-surface-container-low', 'border-primary/20', 'premium-shadow');
        cardEl.classList.add('bg-surface-container-lowest', 'border-surface-variant/30', 'opacity-80');
        const dot = cardEl.querySelector('.indicator-dot');
        if (dot) dot.classList.add('hidden');
        
        // 2. Decrement badge
        if (unreadCount > 0) updateBadge(unreadCount - 1);

        // 3. API call
        apiPatch(`/notifications/${n.id}/read`).catch(console.error);
    }

    // 4. Navigate
    closeDrawer();
    
    // Quick timeout to allow drawer close animation to start
    setTimeout(() => {
        navigateForNotification(n.action_type, n.action_payload);
    }, 200);
}

// Single source of truth for notification tap destinations.
// monthly_report opens the Budget page with ?report=YYYY-M, which opens that month's report.
function getNotificationTarget(actionType, payload) {
    switch (actionType) {
        case 'monthly_report':
            if (payload && payload.month && payload.year) {
                return `budget_overview.html?report=${payload.year}-${payload.month}`;
            }
            return 'budget_overview.html';
        case 'budget_history':
            return 'budget_history.html';
        case 'ai_insight':
            return 'dashboard.html';
        case 'add_expense':
            return 'add_expense.html';
        case 'recurring':
        case 'history':
            return 'history.html';
        case 'set_budget':
            return 'budget_overview.html';
        default:
            return null;
    }
}

function navigateForNotification(actionType, payload) {
    const target = getNotificationTarget(actionType, payload);
    if (target) window.location.href = target;
}

async function markAllRead() {
    // Optimistic UI update
    const unreadCards = listEl.querySelectorAll('.bg-surface-container-low');
    unreadCards.forEach(cardEl => {
        cardEl.classList.remove('bg-surface-container-low', 'border-primary/20', 'premium-shadow');
        cardEl.classList.add('bg-surface-container-lowest', 'border-surface-variant/30', 'opacity-80');
        const dot = cardEl.querySelector('.indicator-dot');
        if (dot) dot.classList.add('hidden');
    });
    
    updateBadge(0);

    try {
        await apiPatch('/notifications/read-all');
    } catch (err) {
        console.error('Failed to mark all read', err);
    }
}

// ── Settings View ───────────────────────────────────────────────────

const NC_SETTINGS = [
    { key: 'notify_budget',    icon: 'account_balance_wallet', title: 'Budget alerts',  desc: "When you pass 50%, 80% and 100% of your budget, or haven't set one" },
    { key: 'notify_reminders', icon: 'notifications_active',   title: 'Reminders',      desc: 'Evening nudge to log expenses, and bills due tomorrow' },
    { key: 'notify_weekly',    icon: 'date_range',             title: 'Weekly summary', desc: "Every Monday morning: last week's spending" },
    { key: 'notify_monthly',   icon: 'assessment',             title: 'Monthly report', desc: 'On the 1st: how last month went' },
    { key: 'notify_ai',        icon: 'auto_awesome',           title: "Buddy's alerts", desc: "When you're on course to overspend or spending jumps" },
    { key: 'notify_system',    icon: 'info',                   title: 'App updates',    desc: 'Account and system messages' }
];

function showListView() {
    document.getElementById('nc-settings').classList.add('hidden');
    document.getElementById('nc-back-btn').classList.add('hidden');
    document.getElementById('nc-close-btn').classList.remove('hidden');
    document.getElementById('nc-settings-btn').classList.remove('hidden');
    document.getElementById('nc-title').textContent = 'Notifications';
    listEl.classList.remove('hidden');
    updateBadge(unreadCount); // restores "Mark all read" visibility
}

function closeSettings() {
    showListView();
}

async function openSettings() {
    listEl.classList.add('hidden');
    document.getElementById('nc-mark-read-btn').classList.add('hidden');
    document.getElementById('nc-settings-btn').classList.add('hidden');
    document.getElementById('nc-close-btn').classList.add('hidden');
    document.getElementById('nc-back-btn').classList.remove('hidden');
    document.getElementById('nc-title').textContent = 'Notification settings';
    document.getElementById('nc-settings').classList.remove('hidden');
    showSettingsError('');

    const rowsEl = document.getElementById('nc-settings-rows');
    rowsEl.innerHTML = buildSettingsSkeleton();

    try {
        const prefs = await apiGet('/notification-preferences/');
        renderSettingsRows(prefs || {});
    } catch (err) {
        console.error('Failed to load notification preferences', err);
        rowsEl.innerHTML = '';
        showSettingsError("Couldn't load your settings. Please try again.");
    }
}

function showSettingsError(msg) {
    const el = document.getElementById('nc-settings-error');
    el.textContent = msg;
    el.classList.toggle('hidden', !msg);
}

function renderSettingsRows(prefs) {
    const rowsEl = document.getElementById('nc-settings-rows');
    rowsEl.innerHTML = '';
    NC_SETTINGS.forEach(def => {
        const row = document.createElement('div');
        row.className = 'flex items-center gap-3 p-4 rounded-2xl border border-surface-variant/30 bg-surface-container-lowest';

        const iconWrap = document.createElement('div');
        iconWrap.className = 'flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-primary bg-primary-fixed/30';
        const icon = document.createElement('span');
        icon.className = 'material-symbols-outlined text-[20px]';
        icon.textContent = def.icon;
        iconWrap.appendChild(icon);

        const text = document.createElement('div');
        text.className = 'flex-1 min-w-0';
        const title = document.createElement('p');
        title.className = 'text-label-lg font-bold text-on-surface';
        title.textContent = def.title;
        const desc = document.createElement('p');
        desc.className = 'text-body-sm text-on-surface-variant';
        desc.textContent = def.desc;
        text.appendChild(title);
        text.appendChild(desc);

        const sw = document.createElement('button');
        sw.type = 'button';
        sw.setAttribute('role', 'switch');
        sw.setAttribute('aria-label', def.title);
        sw.dataset.key = def.key;
        sw.className = 'relative flex-shrink-0 w-11 h-6 rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary';
        const knob = document.createElement('span');
        knob.className = 'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-surface-container-lowest transition-transform';
        sw.appendChild(knob);
        setSwitchState(sw, !!prefs[def.key]);

        sw.addEventListener('click', () => toggleSetting(sw));

        row.appendChild(iconWrap);
        row.appendChild(text);
        row.appendChild(sw);
        rowsEl.appendChild(row);
    });
}

function setSwitchState(sw, on) {
    sw.setAttribute('aria-checked', on ? 'true' : 'false');
    sw.classList.toggle('bg-primary', on);
    sw.classList.toggle('bg-outline-variant', !on);
    const knob = sw.firstElementChild;
    if (knob) {
        knob.classList.toggle('translate-x-5', on);
    }
}

async function toggleSetting(sw) {
    const key = sw.dataset.key;
    const previous = sw.getAttribute('aria-checked') === 'true';
    const next = !previous;

    showSettingsError('');
    setSwitchState(sw, next); // optimistic
    sw.disabled = true;

    try {
        await apiPut('/notification-preferences/', { [key]: next });
    } catch (err) {
        console.error('Failed to save notification preference', err);
        setSwitchState(sw, previous); // revert
        showSettingsError("Couldn't save that change. Please try again.");
    } finally {
        sw.disabled = false;
    }
}

function buildSettingsSkeleton() {
    return Array(NC_SETTINGS.length).fill(0).map(() => `
        <div class="p-4 rounded-2xl border border-surface-variant/30 bg-surface-container-lowest flex gap-3">
            <div class="skeleton w-10 h-10 rounded-full flex-shrink-0"></div>
            <div class="flex-1 space-y-2 mt-1">
                <div class="skeleton h-4 w-1/2"></div>
                <div class="skeleton h-3 w-full"></div>
            </div>
        </div>
    `).join('');
}

// ── States ──────────────────────────────────────────────────────────

function buildSkeleton() {
    return Array(4).fill(0).map(() => `
        <div class="p-4 rounded-2xl border border-surface-variant/30 bg-surface-container-lowest flex gap-3">
            <div class="skeleton w-10 h-10 rounded-full flex-shrink-0"></div>
            <div class="flex-1 space-y-2 mt-1">
                <div class="skeleton h-4 w-3/4"></div>
                <div class="skeleton h-3 w-full"></div>
                <div class="skeleton h-3 w-5/6"></div>
            </div>
        </div>
    `).join('');
}

function buildEmptyState() {
    return `
        <div class="flex flex-col items-center justify-center h-64 text-center px-4">
            <div class="w-16 h-16 bg-surface-container rounded-full flex items-center justify-center mb-4 text-[32px]">🎉</div>
            <h3 class="text-headline-sm font-bold text-on-background mb-2">You're all caught up!</h3>
            <p class="text-body-sm text-on-surface-variant">No new notifications to display right now.</p>
        </div>
    `;
}

function buildErrorState() {
    return `
        <div class="flex flex-col items-center justify-center h-64 text-center px-4">
            <div class="w-16 h-16 bg-error-container/30 rounded-full flex items-center justify-center mb-4">
                <span class="material-symbols-outlined text-[32px] text-on-error-container">cloud_off</span>
            </div>
            <h3 class="text-headline-sm font-bold text-on-background mb-2">Unable to load notifications.</h3>
            <p class="text-body-sm text-on-surface-variant">Please check your connection and try again.</p>
        </div>
    `;
}

// ── Utils ───────────────────────────────────────────────────────────

function formatTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    
    let interval = seconds / 31536000;
    if (interval > 1) return Math.floor(interval) + " yrs ago";
    interval = seconds / 2592000;
    if (interval > 1) return Math.floor(interval) + " mos ago";
    interval = seconds / 86400;
    if (interval >= 2) return Math.floor(interval) + " days ago";
    if (interval >= 1) return "Yesterday";
    interval = seconds / 3600;
    if (interval > 1) return Math.floor(interval) + " hrs ago";
    interval = seconds / 60;
    if (interval > 1) return Math.floor(interval) + " min ago";
    
    return "Just now";
}
