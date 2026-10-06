// ─────────────────────────────────────────────────────────────
//  verify-email.js — BudgetBuddy "verify your email" page
//  Depends on: api.js (must be loaded first in verify_email.html)
//
//  Backend endpoints:
//    POST /auth/verify-email        { email, code } -> { access_token }
//    POST /auth/resend-verification { email }
//  The email comes from sessionStorage ('bb_verify_email'), set by
//  register.js / login.js. If it is missing, the user types it in.
// ─────────────────────────────────────────────────────────────

// Already logged in? Nothing to verify.
if (isLoggedIn()) goToDashboard();

const RESEND_SECONDS = 60;

const form         = document.getElementById('verify-form');
const sentToText   = document.getElementById('sent-to-text');
const sentToEmail  = document.getElementById('sent-to-email');
const emailField   = document.getElementById('email-field');
const emailInput   = document.getElementById('ve-email');
const codeInput    = document.getElementById('ve-code');
const verifyBtn    = document.getElementById('verify-btn');
const resendBtn    = document.getElementById('resend-btn');
const errBox       = document.getElementById('ve-error');
const feedback     = document.getElementById('ve-feedback');
const feedbackText = document.getElementById('ve-feedback-text');

let storedEmail = '';
try { storedEmail = sessionStorage.getItem('bb_verify_email') || ''; } catch (e) { /* storage blocked */ }

let feedbackTimer = null;
let countdownTimer = null;

// ── Helpers ───────────────────────────────────────────────────
function showError(msg) {
    errBox.textContent   = msg;
    errBox.style.display = 'block';
}

function clearError() {
    errBox.textContent   = '';
    errBox.style.display = 'none';
}

function showFeedback(msg) {
    feedbackText.textContent = msg;
    feedback.classList.remove('translate-y-20', 'opacity-0');
    feedback.classList.add('translate-y-0', 'opacity-100');
    clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(() => {
        feedback.classList.remove('translate-y-0', 'opacity-100');
        feedback.classList.add('translate-y-20', 'opacity-0');
    }, 2500);
}

function setLoading(loading) {
    verifyBtn.disabled = loading;
    verifyBtn.querySelector('span').textContent = loading ? 'Verifying…' : 'Verify email';
}

function errorMessage(err) {
    if (err instanceof TypeError) return "Can't reach the server. Please try again.";
    return err && err.message ? err.message : 'Something went wrong. Please try again.';
}

function currentEmail() {
    return (storedEmail || emailInput.value).trim();
}

// ── Resend countdown ──────────────────────────────────────────
function startCountdown() {
    clearInterval(countdownTimer);
    let left = RESEND_SECONDS;
    resendBtn.disabled = true;
    resendBtn.textContent = `Resend in ${left}s`;
    countdownTimer = setInterval(() => {
        left -= 1;
        if (left <= 0) {
            clearInterval(countdownTimer);
            resendBtn.disabled = false;
            resendBtn.textContent = 'Resend code';
        } else {
            resendBtn.textContent = `Resend in ${left}s`;
        }
    }, 1000);
}

// ── Initial state ─────────────────────────────────────────────
if (storedEmail) {
    sentToEmail.textContent = storedEmail;   // textContent only, never innerHTML
    // A code was just sent by sign-up or by the login attempt, so wait before resending.
    startCountdown();
} else {
    sentToText.classList.add('hidden');
    emailField.classList.remove('hidden');
    emailField.classList.add('flex');
}

// Clear error when the user edits a field
[emailInput, codeInput].forEach((el) => el.addEventListener('input', clearError));

// Keep code field digits-only
codeInput.addEventListener('input', () => {
    codeInput.value = codeInput.value.replace(/\D/g, '').slice(0, 6);
});

// ── Verify ────────────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    const email = currentEmail();
    const code = codeInput.value.trim();

    if (!email || !email.includes('@')) {
        showError('Please enter a valid email address.');
        return;
    }
    if (!/^\d{6}$/.test(code)) {
        showError('Please enter the 6-digit code.');
        return;
    }

    setLoading(true);
    try {
        const data = await apiPost('/auth/verify-email', { email, code });
        setToken(data.access_token);
        try { sessionStorage.removeItem('bb_verify_email'); } catch (e2) { /* ignore */ }
        // New accounts see the welcome tutorial first
        window.location.href = 'welcome.html';
    } catch (err) {
        showError(errorMessage(err));
        setLoading(false);
    }
});

// ── Resend ────────────────────────────────────────────────────
resendBtn.addEventListener('click', async () => {
    clearError();
    const email = currentEmail();
    if (!email || !email.includes('@')) {
        showError('Please enter a valid email address.');
        return;
    }

    resendBtn.disabled = true;
    resendBtn.textContent = 'Sending…';
    try {
        await apiPost('/auth/resend-verification', { email });
        showFeedback('New code sent');
    } catch (err) {
        showError(errorMessage(err));
    }
    // Sent or rate limited: either way, make them wait before trying again
    startCountdown();
});
