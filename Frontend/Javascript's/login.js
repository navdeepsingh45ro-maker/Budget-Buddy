// ─────────────────────────────────────────────────────────────
//  login.js — BudgetBuddy login page
//  Depends on: api.js (must be loaded first in login.html)
// ─────────────────────────────────────────────────────────────

// If already logged in, skip the login page entirely
if (isLoggedIn()) goToDashboard();

const form   = document.getElementById('LoginForm');
const btn    = document.getElementById('login-btn');
const errBox = document.getElementById('login-error');

// ── Helpers ───────────────────────────────────────────────────
function showError(msg) {
    errBox.textContent   = msg;
    errBox.style.display = 'block';
}

function clearError() {
    errBox.textContent   = '';
    errBox.style.display = 'none';
}

function setLoading(loading) {
    btn.disabled    = loading;
    btn.textContent = loading ? 'Logging in…' : 'Login';
}

// ── Form submit ───────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    // Basic client-side guard
    if (!username || !password) {
        showError('Please enter your username and password.');
        return;
    }

    setLoading(true);

    try {
        await apiLogin(username, password);
        // apiLogin already stored the token — go straight to dashboard
        goToDashboard();
    } catch (err) {
        // Show the error from the backend (generic "Invalid username or password")
        showError(err.message);
    } finally {
        setLoading(false);
    }
});