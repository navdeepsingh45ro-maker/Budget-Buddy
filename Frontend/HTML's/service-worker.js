// ─────────────────────────────────────────────────────────────
//  service-worker.js — Budget Buddy push notifications
//  Lives next to the HTML pages so its scope covers all of them.
//  All URLs are built from the registration scope, so it works on
//  localhost and on any deployed host/sub-folder.
// ─────────────────────────────────────────────────────────────

const ICON  = new URL('../Assets/icons/icon-192.png', self.registration.scope).href;
const BADGE = new URL('../Assets/icons/badge-72.png', self.registration.scope).href;

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));

self.addEventListener('push', event => {
    let payload = {};
    try {
        payload = event.data ? event.data.json() : {};
    } catch (e) {
        payload = { title: 'Budget Buddy', body: event.data ? event.data.text() : '' };
    }

    // Every push must show a notification (browsers revoke silent pushes).
    const title = payload.title || 'Budget Buddy';
    const options = {
        body: payload.body || '',
        icon: ICON,
        badge: BADGE,
        tag: payload.tag || undefined,          // same tag replaces instead of stacking
        renotify: Boolean(payload.tag),
        requireInteraction: payload.priority === 'critical',
        data: {
            notification_id: payload.notification_id || null,
            action_type: payload.action_type || null,
            action_payload: payload.action_payload || null,
        },
    };
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    const data = event.notification.data || {};

    // The page (which has the login token) marks it read and routes to the
    // right screen via ?sync_notif / action_type / action_payload.
    const url = new URL('dashboard.html', self.registration.scope);
    if (data.notification_id) url.searchParams.set('sync_notif', data.notification_id);
    if (data.action_type) url.searchParams.set('action_type', data.action_type);
    if (data.action_payload) url.searchParams.set('action_payload', JSON.stringify(data.action_payload));

    event.waitUntil((async () => {
        const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
        for (const client of windows) {
            if (client.url.startsWith(self.registration.scope) && 'focus' in client) {
                await client.focus();
                if ('navigate' in client) return client.navigate(url.href);
                return;
            }
        }
        return self.clients.openWindow(url.href);
    })());
});
