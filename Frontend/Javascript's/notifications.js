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
        // Exact match: other icons like 'notifications_active' must not be mistaken for the bell.
        navBtn = buttons.find(b => b.textContent.trim() === 'notifications' && b.classList.contains('material-symbols-outlined'));
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
    
    // 6. Push (silent setup only: never asks for permission) + deep links from pushes
    initPushNotifications();
    checkSyncParams();
}

// ── Push notifications (real Web Push, opt-in from a user tap) ──────

const PUSH_CARD_DISMISSED_KEY = 'bb_push_card_dismissed';

async function initPushNotifications() {
    if (!('serviceWorker' in navigator)) return;

    try {
        // Registering is silent: it never shows a permission prompt.
        await navigator.serviceWorker.register('service-worker.js');
    } catch (err) {
        console.error('Service Worker registration failed:', err);
    }

    // Remove the stale worker that used to live under /Javascript's/
    try {
        const regs = await navigator.serviceWorker.getRegistrations();
        for (const reg of regs) {
            let scope = reg.scope || '';
            try { scope = decodeURIComponent(scope); } catch (e) { /* keep raw */ }
            if (scope.endsWith("/Javascript's/")) {
                await reg.unregister();
            }
        }
    } catch (err) {
        console.error('Old service worker cleanup failed:', err);
    }

    // Warm the push state (e.g. so the card can render without delay)
    try { await getPushState(); } catch (e) { /* ignore */ }
}

function isIOSDevice() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) ||
        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
}

function isInstalledApp() {
    return (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) ||
        navigator.standalone === true;
}

// Resolves with the active service worker registration, or rejects after a timeout
// (navigator.serviceWorker.ready never settles if no worker is registered).
function getSwRegistration(timeoutMs = 4000) {
    return Promise.race([
        navigator.serviceWorker.ready,
        new Promise((_, reject) => setTimeout(() => reject(new Error('Service worker not ready')), timeoutMs))
    ]);
}

// Returns: 'unsupported' | 'ios-needs-install' | 'denied' | 'on' | 'off'
async function getPushState() {
    // iOS Safari only exposes push to installed Home Screen apps, so in a plain
    // Safari tab PushManager is missing. Check this before the support test.
    if (isIOSDevice() && !isInstalledApp()) return 'ios-needs-install';

    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
        return 'unsupported';
    }
    if (Notification.permission === 'denied') return 'denied';

    if (Notification.permission === 'granted') {
        try {
            const reg = await getSwRegistration();
            const sub = await reg.pushManager.getSubscription();
            if (sub) return 'on';
        } catch (e) { /* fall through to 'off' */ }
    }
    return 'off';
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
}

// Must be called from a click/tap handler. Returns the new push state.
async function enablePush() {
    const state = await getPushState();
    if (state === 'unsupported') throw new Error("Notifications aren't supported in this browser.");
    if (state === 'ios-needs-install') throw new Error('On iPhone, add Budget Buddy to your Home Screen first.');
    if (state === 'denied') return 'denied';

    // Keep this first so the permission prompt stays tied to the user's tap.
    const permission = await Notification.requestPermission();
    if (permission === 'denied') return 'denied';
    if (permission !== 'granted') {
        throw new Error("Notifications weren't turned on. Please try again and choose Allow.");
    }

    let reg;
    try {
        reg = await getSwRegistration();
    } catch (e) {
        throw new Error('Notifications are still getting ready. Please reload the page and try again.');
    }

    let publicKey;
    try {
        const data = await apiGet('/push/public-key');
        publicKey = data && data.public_key;
    } catch (e) {
        throw new Error("Notifications aren't available right now. Please try again later.");
    }
    if (!publicKey) throw new Error("Notifications aren't available right now. Please try again later.");

    let sub;
    try {
        sub = await reg.pushManager.getSubscription();
        if (!sub) {
            sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey)
            });
        }
    } catch (e) {
        console.error('Push subscribe failed:', e);
        throw new Error("Couldn't turn on notifications on this device. Please try again.");
    }

    try {
        await apiPost('/push/subscribe', sub.toJSON());
    } catch (e) {
        // Don't leave a browser subscription the server doesn't know about.
        try { await sub.unsubscribe(); } catch (e2) { /* ignore */ }
        throw new Error(e && e.message ? e.message : "Couldn't save your notification settings. Please try again.");
    }

    return 'on';
}

async function disablePush() {
    let reg;
    try { reg = await getSwRegistration(); } catch (e) { return; }
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return;
    try {
        await apiPost('/push/unsubscribe', { endpoint: sub.endpoint });
    } catch (e) { /* the browser-side unsubscribe below still matters most */ }
    await sub.unsubscribe();
}

async function checkSyncParams() {
    // Deep linking from a tapped push (see service-worker.js)
    const params = new URLSearchParams(window.location.search);
    const syncId = params.get('sync_notif');
    const actionType = params.get('action_type');
    let payload = null;
    const rawPayload = params.get('action_payload');
    if (rawPayload) {
        try { payload = JSON.parse(rawPayload); } catch (e) { payload = null; }
        if (payload === null || typeof payload !== 'object') payload = null;
    }

    if (syncId) {
        // Clean URL (drops sync_notif, action_type, action_payload) to prevent repeated marking on refresh
        const cleanUrl = window.location.pathname;
        window.history.replaceState({}, document.title, cleanUrl);

        // Mark as read in DB
        try {
            await apiPatch(`/notifications/${encodeURIComponent(syncId)}/read`);
        } catch (e) {
            console.error('Failed to sync notification read state', e);
        }

        // Navigate
        const target = getNotificationTarget(actionType, payload);
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
                <p id="nc-settings-error" data-nc="error" role="alert" class="hidden text-body-sm text-error bg-error-container/30 rounded-xl px-3 py-2"></p>
                <div id="nc-push-section" data-nc="push-section" class="space-y-2 pb-3"></div>
                <div id="nc-settings-rows" data-nc="rows" class="space-y-2"></div>
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
        
        updateBadge(data.unread_count);
    } catch (err) {
        console.error('Failed to poll notifications', err);
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
    renderPushCard();
    
    try {
        const data = await apiGet('/notifications');
        const notifs = data.notifications || [];
        
        if (notifs.length === 0) {
            listEl.innerHTML = buildEmptyState();
            renderPushCard();
            return;
        }

        renderGroupedNotifications(notifs);
        renderPushCard();

    } catch (err) {
        console.error(err);
        listEl.innerHTML = buildErrorState();
        renderPushCard();
    }
}

// ── Push opt-in card (top of the list) ──────────────────────────────

function ncEl(tag, className, text) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined) e.textContent = text;
    return e;
}

function isPushCardDismissed() {
    try { return localStorage.getItem(PUSH_CARD_DISMISSED_KEY) === '1'; } catch (e) { return false; }
}

function dismissPushCard() {
    try { localStorage.setItem(PUSH_CARD_DISMISSED_KEY, '1'); } catch (e) { /* ignore */ }
    const card = document.getElementById('nc-push-card');
    if (card) card.remove();
}

async function renderPushCard() {
    if (!listEl) return;
    const existing = document.getElementById('nc-push-card');
    if (existing) existing.remove();
    if (isPushCardDismissed()) return;

    let state;
    try { state = await getPushState(); } catch (e) { return; }
    if (state !== 'off' && state !== 'ios-needs-install') return;

    // A newer render may have added a card while we awaited
    const dup = document.getElementById('nc-push-card');
    if (dup) dup.remove();

    const card = ncEl('div', 'p-4 rounded-2xl border border-primary/20 bg-surface-container');
    card.id = 'nc-push-card';
    const row = ncEl('div', 'flex gap-3');

    const iconWrap = ncEl('div', 'flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-primary bg-primary-fixed/30');
    const icon = ncEl('span', 'material-symbols-outlined text-[20px]', state === 'off' ? 'notifications_active' : 'ios_share');
    iconWrap.appendChild(icon);

    const body = ncEl('div', 'flex-1 min-w-0');
    const title = ncEl('p', 'text-label-lg font-bold text-on-surface',
        state === 'off' ? 'Get reminders on this device?' : 'Notifications on iPhone');
    const text = ncEl('p', 'text-body-sm text-on-surface-variant mt-1',
        state === 'off'
            ? 'Bills due, your weekly summary and monthly report \u2014 even when the app is closed.'
            : 'Tap the Share button, then \u201cAdd to Home Screen\u201d. Open Budget Buddy from your Home Screen to turn on notifications.');
    const msg = ncEl('p', 'hidden text-body-sm text-error mt-2');
    msg.setAttribute('role', 'alert');
    const actions = ncEl('div', 'flex items-center gap-3 mt-3');

    if (state === 'off') {
        const turnOn = ncEl('button', 'bg-primary text-on-primary px-4 py-2 rounded-xl text-label-md font-bold hover:opacity-90 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed', 'Turn on');
        turnOn.type = 'button';
        const later = ncEl('button', 'text-label-md font-bold text-on-surface-variant hover:text-on-surface transition-colors', 'Not now');
        later.type = 'button';
        later.addEventListener('click', dismissPushCard);

        turnOn.addEventListener('click', async () => {
            msg.classList.add('hidden');
            turnOn.disabled = true;
            later.disabled = true;
            turnOn.textContent = 'Turning on\u2026';
            try {
                const result = await enablePush();
                if (result === 'on') {
                    body.replaceChildren(ncEl('p', 'text-label-lg font-bold text-on-surface', 'Notifications are on for this device.'));
                    icon.textContent = 'check_circle';
                    setTimeout(() => card.remove(), 2000);
                    return;
                }
                msg.textContent = 'Notifications are blocked in your browser settings. Allow them for this site, then try again.';
                msg.classList.remove('hidden');
            } catch (err) {
                msg.textContent = (err && err.message) || "Couldn't turn on notifications. Please try again.";
                msg.classList.remove('hidden');
            }
            turnOn.disabled = false;
            later.disabled = false;
            turnOn.textContent = 'Turn on';
        });
        actions.appendChild(turnOn);
        actions.appendChild(later);
    } else {
        const gotIt = ncEl('button', 'text-label-md font-bold text-primary hover:text-primary-fixed transition-colors', 'Got it');
        gotIt.type = 'button';
        gotIt.addEventListener('click', dismissPushCard);
        actions.appendChild(gotIt);
    }

    body.appendChild(title);
    body.appendChild(text);
    body.appendChild(msg);
    body.appendChild(actions);
    row.appendChild(iconWrap);
    row.appendChild(body);
    card.appendChild(row);
    listEl.insertBefore(card, listEl.firstChild);
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
        const d = parseApiDate(n.created_at);
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
    const timeAgo = formatTimeAgo(parseApiDate(n.created_at));

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
            // Only plain integers are allowed into the URL (payload can come from the query string)
            if (payload && Number.isInteger(Number(payload.month)) && Number.isInteger(Number(payload.year))
                && Number(payload.month) >= 1 && Number(payload.month) <= 12 && Number(payload.year) >= 2000 && Number(payload.year) <= 2100) {
                return `budget_overview.html?report=${Number(payload.year)}-${Number(payload.month)}`;
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
    loadNotificationSettings(document.getElementById('nc-settings'));
}

// The settings UI (push section + preference toggles) is shared between the
// drawer and the Settings page. Every function below works on a "root" element
// that contains three children marked data-nc="error" | "push-section" | "rows",
// and looks elements up inside that root (never by global id), so several
// instances can live on one page.
function ncQuery(root, name) {
    return root.querySelector('[data-nc="' + name + '"]');
}

async function loadNotificationSettings(root) {
    showSettingsError(root, '');

    renderPushSettings(root);

    const rowsEl = ncQuery(root, 'rows');
    rowsEl.innerHTML = buildSettingsSkeleton();

    try {
        const prefs = await apiGet('/notification-preferences/');
        renderSettingsRows(root, prefs || {});
    } catch (err) {
        console.error('Failed to load notification preferences', err);
        rowsEl.innerHTML = '';
        showSettingsError(root, "Couldn't load your settings. Please try again.");
    }
}

// Public: render the push-device section + the preference toggles into any container.
function mountNotificationSettings(containerEl) {
    if (!containerEl) return Promise.resolve();
    const err = ncEl('p', 'hidden text-body-sm text-error bg-error-container/30 rounded-xl px-3 py-2');
    err.setAttribute('data-nc', 'error');
    err.setAttribute('role', 'alert');
    const push = ncEl('div', 'space-y-2 pb-3');
    push.setAttribute('data-nc', 'push-section');
    const rows = ncEl('div', 'space-y-2');
    rows.setAttribute('data-nc', 'rows');
    containerEl.replaceChildren(err, push, rows);
    return loadNotificationSettings(containerEl);
}
window.mountNotificationSettings = mountNotificationSettings;

function showSettingsError(root, msg) {
    const el = ncQuery(root, 'error');
    if (!el) return;
    el.textContent = msg;
    el.classList.toggle('hidden', !msg);
}

// ── Settings: push notifications on this device ─────────────────────

const PUSH_STATUS_TEXT = {
    'unsupported': 'Not supported in this browser.',
    'ios-needs-install': 'On iPhone, add Budget Buddy to your Home Screen first.',
    'denied': 'Blocked in browser settings.',
    'on': 'On for this device.',
    'off': 'Off for this device.'
};

async function renderPushSettings(root) {
    const section = ncQuery(root, 'push-section');
    if (!section) return;
    section.innerHTML = '';

    const row = ncEl('div', 'flex items-center gap-3 p-4 rounded-2xl border border-surface-variant/30 bg-surface-container-lowest');

    const iconWrap = ncEl('div', 'flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-primary bg-primary-fixed/30');
    iconWrap.appendChild(ncEl('span', 'material-symbols-outlined text-[20px]', 'phonelink_ring'));

    const text = ncEl('div', 'flex-1 min-w-0');
    text.appendChild(ncEl('p', 'text-label-lg font-bold text-on-surface', 'Push notifications on this device'));
    text.appendChild(ncEl('p', 'text-body-sm text-on-surface-variant', 'Get reminders even when the app is closed'));
    const status = ncEl('p', 'text-[11px] text-outline mt-1', 'Checking…');
    status.setAttribute('data-nc', 'push-status');
    status.setAttribute('aria-live', 'polite');
    text.appendChild(status);

    const sw = document.createElement('button');
    sw.type = 'button';
    sw.setAttribute('data-nc', 'push-switch');
    sw.setAttribute('role', 'switch');
    sw.setAttribute('aria-label', 'Push notifications on this device');
    sw.className = 'relative flex-shrink-0 w-11 h-6 rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50';
    sw.appendChild(ncEl('span', 'absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-surface-container-lowest transition-transform'));
    setSwitchState(sw, false);
    sw.disabled = true; // until the state is known

    row.appendChild(iconWrap);
    row.appendChild(text);
    row.appendChild(sw);
    section.appendChild(row);

    const testBtn = ncEl('button', 'hidden text-label-md font-bold text-primary hover:text-primary-fixed transition-colors px-1 disabled:opacity-50', 'Send test notification');
    testBtn.type = 'button';
    testBtn.setAttribute('data-nc', 'push-test-btn');
    section.appendChild(testBtn);

    section.appendChild(ncEl('p', 'text-[11px] text-outline px-1',
        "Your settings below decide what you get. The app's own messages are never sent between 10 PM and 8 AM."));

    sw.addEventListener('click', () => togglePush(root, sw));
    testBtn.addEventListener('click', () => sendTestPush(root, testBtn));

    let state;
    try { state = await getPushState(); } catch (e) { state = 'off'; }
    applyPushSettingsState(root, state);
}

function applyPushSettingsState(root, state) {
    const sw = ncQuery(root, 'push-switch');
    const status = ncQuery(root, 'push-status');
    const testBtn = ncQuery(root, 'push-test-btn');
    if (!sw || !status || !testBtn) return;

    const unavailable = state === 'unsupported' || state === 'ios-needs-install' || state === 'denied';
    setSwitchState(sw, state === 'on');
    sw.disabled = unavailable;
    status.textContent = PUSH_STATUS_TEXT[state] || '';
    testBtn.classList.toggle('hidden', state !== 'on');
}

async function togglePush(root, sw) {
    const previous = sw.getAttribute('aria-checked') === 'true';
    const next = !previous;

    showSettingsError(root, '');
    setSwitchState(sw, next); // optimistic
    sw.disabled = true;

    try {
        if (next) {
            const state = await enablePush();
            applyPushSettingsState(root, state);
        } else {
            await disablePush();
            applyPushSettingsState(root, await getPushState());
        }
    } catch (err) {
        console.error('Failed to change push setting', err);
        setSwitchState(sw, previous); // revert
        sw.disabled = false;
        showSettingsError(root, (err && err.message) || "Couldn't change that. Please try again.");
    }
}

async function sendTestPush(root, btn) {
    const status = ncQuery(root, 'push-status');
    btn.disabled = true;
    if (status) status.textContent = 'Sending…';
    try {
        const res = await apiPost('/push/test', {});
        if (status) status.textContent = (res && res.message) || 'Test notification sent.';
    } catch (err) {
        if (status) status.textContent = (err && err.message) || "Couldn't send a test notification.";
    } finally {
        btn.disabled = false;
    }
}

function renderSettingsRows(root, prefs) {
    const rowsEl = ncQuery(root, 'rows');
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

        sw.addEventListener('click', () => toggleSetting(root, sw));

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

async function toggleSetting(root, sw) {
    const key = sw.dataset.key;
    const previous = sw.getAttribute('aria-checked') === 'true';
    const next = !previous;

    showSettingsError(root, '');
    setSwitchState(sw, next); // optimistic
    sw.disabled = true;

    try {
        await apiPut('/notification-preferences/', { [key]: next });
    } catch (err) {
        console.error('Failed to save notification preference', err);
        setSwitchState(sw, previous); // revert
        showSettingsError(root, "Couldn't save that change. Please try again.");
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
