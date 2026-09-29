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
        if (actionType === 'budget_history' && !window.location.pathname.includes('budget_history.html')) {
            window.location.href = 'budget_history.html';
        } else if (actionType === 'ai_insight' && !window.location.pathname.includes('dashboard.html')) {
            window.location.href = 'dashboard.html';
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
                    <h2 class="font-headline-sm font-bold text-on-background">Notifications</h2>
                </div>
                <button id="nc-mark-read-btn" class="text-label-md font-bold text-primary hover:text-primary-fixed transition-colors hidden">Mark all read</button>
            </div>

            <!-- Content Area -->
            <div id="nc-list" class="flex-1 overflow-y-auto p-4 space-y-6">
                <!-- Injected via JS -->
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
            if (notif.action_type === 'budget_history') {
                window.location.href = 'budget_history.html';
            } else if (notif.action_type === 'ai_insight') {
                window.location.href = 'dashboard.html';
            }
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
            <h3 class="text-label-md font-bold text-on-surface-variant uppercase tracking-wider pl-1 pt-2">${groupName}</h3>
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
                <span class="material-symbols-outlined text-[20px]">${n.icon || 'notifications'}</span>
            </div>
            
            <!-- Content -->
            <div class="flex-1 min-w-0 pr-6">
                <div class="flex items-start justify-between gap-2 mb-1">
                    <p class="text-label-lg font-bold text-on-surface truncate">${n.title}</p>
                    <span class="text-[11px] text-outline flex-shrink-0 whitespace-nowrap mt-0.5">${timeAgo}</span>
                </div>
                <p class="text-body-sm text-on-surface-variant line-clamp-2">${n.message}</p>
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
        if (n.action_type === 'budget_history') {
            window.location.href = 'budget_history.html';
            // In a real SPA we would scroll to the specific month via payload, 
            // but for now redirecting to the right page is sufficient.
        } else if (n.action_type === 'ai_insight') {
            window.location.href = 'dashboard.html';
        }
    }, 200);
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
