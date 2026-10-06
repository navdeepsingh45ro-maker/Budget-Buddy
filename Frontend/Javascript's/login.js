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

    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;

    // Basic client-side guard
    if (!email || !password) {
        showError('Please enter your email and password.');
        return;
    }

    setLoading(true);

    try {
        await apiLogin(email, password);
        
        // Show successful login toast feedback
        const feedback = document.getElementById('login-feedback');
        if (feedback) {
            feedback.classList.remove('translate-y-20', 'opacity-0');
            feedback.classList.add('translate-y-0', 'opacity-100');
        }
        
        setTimeout(() => {
            goToDashboard();
        }, 1200); // Let the user see the premium toast before redirecting
    } catch (err) {
        // 403 = right password but email not verified yet; the server just sent a new code
        if (err.status === 403) {
            try { sessionStorage.setItem('bb_verify_email', email); } catch (e2) { /* ignore */ }
            window.location.href = 'verify_email.html';
            return;
        }
        // Show the error from the backend (generic "Invalid email or password")
        showError(err.message);
    } finally {
        setLoading(false);
    }
});