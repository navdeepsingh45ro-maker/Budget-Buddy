document.addEventListener('DOMContentLoaded', async () => {
    requireAuth();

    try {
        const user = await apiGet('/users/me');
        if (user && user.name) {
            document.getElementById('profile-greeting').textContent = `Hi, ${user.name}!`;
        } else {
            document.getElementById('profile-greeting').textContent = `Hi there!`;
        }
    } catch (err) {
        console.error("Failed to load user:", err);
        document.getElementById('profile-greeting').textContent = `Hi there!`;
    }

    try {
        const aiData = await apiGet('/ai/insight');
        if (aiData) {
            document.getElementById('insight1-title').textContent = aiData.insight || "No insight available";
            document.getElementById('insight1-detail').textContent = aiData.status === 'ready' ? "Based on your recent activity" : "Generating new insights...";
            document.getElementById('insight1-badge').textContent = aiData.status === 'ready' ? "NEW" : "WAIT";
            
            document.getElementById('insight2-title').textContent = aiData.reminder || "No reminders currently.";
            document.getElementById('insight2-detail').textContent = "Actionable Tip";
        }
    } catch (err) {
        console.error("Failed to load insights:", err);
        document.getElementById('insight1-title').textContent = "Unable to load insights";
        document.getElementById('insight1-detail').textContent = "";
        document.getElementById('insight1-badge').textContent = "ERR";
        
        document.getElementById('insight2-title').textContent = "Unable to load reminders";
        document.getElementById('insight2-detail').textContent = "";
    }

    // ── Chat Logic ────────────────────────────────────────────────
    const chatInput = document.getElementById('chat-input');
    const chatSubmit = document.getElementById('chat-submit');
    const responseCard = document.getElementById('chat-response-card');
    const responseText = document.getElementById('chat-response-text');

    async function handleChatSubmit() {
        const msg = chatInput.value.trim();
        if (!msg) return;

        chatInput.value = '';
        responseCard.classList.remove('hidden');
        responseText.innerHTML = '<span class="animate-pulse">Thinking...</span>';

        try {
            const data = await apiPost('/ai/chat', { message: msg });
            responseText.textContent = data.reply;
        } catch (err) {
            responseText.textContent = "Sorry, I couldn't process that right now.";
            console.error(err);
        }
    }

    chatSubmit.addEventListener('click', handleChatSubmit);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleChatSubmit();
    });
});

function handleLogout() {
    logout();
}
