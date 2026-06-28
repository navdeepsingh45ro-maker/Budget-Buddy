// ─────────────────────────────────────────────────────────────
//  register.js — BudgetBuddy register page
//  Depends on: api.js (must be loaded first in register.html)
//
//  Backend endpoint expected:
//    POST /register
//    Body: { name, email, password }
//    Returns: { id, name, email } or similar
//
//  ⚠️  Verify your actual route path in user_routes.py.
//  Common alternatives: /users  /auth/register  /signup
// ─────────────────────────────────────────────────────────────

// If already logged in, skip registration
if (isLoggedIn()) goToDashboard();

const form    = document.getElementById('RegisterForm');
const btn     = document.getElementById('register-btn');
const errBox  = document.getElementById('register-error');

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
    btn.textContent = loading ? 'Creating account…' : 'Create Account';
}

// ── Client-side validation ────────────────────────────────────
function validate(name, email, password, confirm) {
    if (!name.trim())
        return 'Please enter your full name.';

    if (!email.trim() || !email.includes('@'))
        return 'Please enter a valid email address.';

    if (password.length < 8)
        return 'Password must be at least 8 characters.';

    if (password !== confirm)
        return 'Passwords do not match.';

    return null; // null = valid
}

// ── Form submit ───────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    const name     = document.getElementById('name').value;
    const email    = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const confirm  = document.getElementById('confirm-password').value;

    // Client-side check first — never hits the API if this fails
    const validationError = validate(name, email, password, confirm);
    if (validationError) {
        showError(validationError);
        return;
    }

    setLoading(true);

    try {
        // Step 1: create the account
        // ⚠️ Change '/register' to match your actual route in user_routes.py
        await apiPost('/register', { name, email, password });

        // Step 2: immediately log them in so they land on dashboard
        // This hits POST /login with form encoding (handled by apiLogin)
        // ⚠️ Your login endpoint takes 'username' — check if it's email or username
        await apiLogin(email, password);

        goToDashboard();

    } catch (err) {
        // Common backend error: "Email already registered"
        showError(err.message);
    } finally {
        setLoading(false);
    }
});