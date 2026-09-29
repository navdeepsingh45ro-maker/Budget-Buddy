self.addEventListener('push', function(event) {
    if (!event.data) return;
    
    try {
        const payload = event.data.json();
        
        // Priority Mapping handling for local display
        const requireInteraction = payload.priority === 'high';
        const silent = payload.priority === 'low';
        
        const options = {
            body: payload.body,
            icon: payload.icon || 'https://cdn-icons-png.flaticon.com/512/3135/3135715.png', // Generic icon fallback
            requireInteraction: requireInteraction,
            silent: silent,
            data: payload.data
        };

        event.waitUntil(
            self.registration.showNotification(payload.title, options)
        );
    } catch (err) {
        console.error('Error processing push event', err);
    }
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    const data = event.notification.data;
    
    // We need to open the app and pass the notification ID and action type
    // so the main thread (which has access to localStorage JWT) can mark it read
    // and handle the deep link.
    
    const targetUrl = new URL(self.location.origin);
    targetUrl.pathname = '/Frontend/HTML\'s/dashboard.html'; // Default landing
    targetUrl.searchParams.append('sync_notif', data.notification_id);
    targetUrl.searchParams.append('action_type', data.action_type || '');
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            // If a window is already open, focus it and navigate
            for (let i = 0; i < clientList.length; i++) {
                const client = clientList[i];
                if (client.url && 'focus' in client) {
                    client.focus();
                    client.navigate(targetUrl.href);
                    return;
                }
            }
            // Otherwise open a new window
            if (clients.openWindow) {
                return clients.openWindow(targetUrl.href);
            }
        })
    );
});
