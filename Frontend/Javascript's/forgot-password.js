// ─────────────────────────────────────────────────────────────
//  forgot-password.js — BudgetBuddy forgot/reset password page
//  Depends on: api.js (must be loaded first in forgot_password.html)
// ─────────────────────────────────────────────────────────────

const stageEmail   = document.getElementById('stage-email');
const stageReset   = document.getElementById('stage-reset');
const stageSuccess = document.getElementById('stage-success');

const emailInput   = document.getElementById('fp-email');
const codeInput    = document.getElementById('fp-code');
const newPassInput = document.getElementById('fp-new-password');
const confirmInput = document.getElementById('fp-confirm-password');

const sendBtn   = document.getElementById('send-code-btn');
const resetBtn  = document.getElementById('reset-btn');
const resendBtn = document.getElementById('resend-btn');
const changeEmailLink = document.getElementById('change-email-link');
const sentToEmail = document.getElementById('sent-to-email');

const errBox1 = document.getElementById('fp-error-1');
const errBox2 = document.getElementById('fp-error-2');
const feedback = document.getElementById('fp-feedback');
const feedbackText = document.getElementById('fp-feedback-text');

let currentEmail = '';
let feedbackTimer = null;

// ── Helpers ───────────────────────────────────────────────────
function activeErrBox() {
    return stageReset.classList.contains('hidden') ? errBox1 : errBox2;
}

function showError(msg) {
    const box = activeErrBox();
    box.textContent = msg;
    box.style.display = 'block';
}

function clearError() {
    [errBox1, errBox2].forEach((box) => {
        box.textContent = '';
        box.style.display = 'none';
    });
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

function setLoading(btn, loading, loadingLabel, idleLabel) {
    btn.disabled = loading;
    const label = btn.querySelector('span');
    if (label) label.textContent = loading ? loadingLabel : idleLabel;
}

function errorMessage(err) {
    if (err instanceof TypeError) return "Can't reach the server. Please try again.";
    return err && err.message ? err.message : 'Something went wrong. Please try again.';
}

function showStage(stage) {
    [stageEmail, stageReset, stageSuccess].forEach((el) => {
        el.classList.add('hidden');
        el.classList.remove('flex');
    });
    stage.classList.remove('hidden');
    if (stage !== stageEmail) stage.classList.add('flex');
    clearError();
}

// ── Show/hide password toggles ────────────────────────────────
document.querySelectorAll('button[data-toggle-for]').forEach((toggle) => {
    toggle.addEventListener('click', () => {
        const input = document.getElementById(toggle.dataset.toggleFor);
        const icon = toggle.querySelector('.material-symbols-outlined');
        if (input.type === 'password') {
            input.type = 'text';
            icon.textContent = 'visibility_off';
        } else {
            input.type = 'password';
            icon.textContent = 'visibility';
        }
    });
});

// Clear error when the user edits a field
[emailInput, codeInput, newPassInput, confirmInput].forEach((el) => {
    el.addEventListener('input', clearError);
});

// Keep code field digits-only
codeInput.addEventListener('input', () => {
    codeInput.value = codeInput.value.replace(/\D/g, '').slice(0, 6);
});

// ── Stage 1: request code ─────────────────────────────────────
stageEmail.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    const email = emailInput.value.trim();
    if (!email || !email.includes('@')) {
        showError('Please enter a valid email address.');
        return;
    }

    setLoading(sendBtn, true, 'Sending…', 'Send code');
    try {
        await apiPost('/auth/forgot-password', { email });
        currentEmail = email;
        sentToEmail.textContent = email;
        codeInput.value = '';
        newPassInput.value = '';
        confirmInput.value = '';
        showStage(stageReset);
        codeInput.focus();
    } catch (err) {
        showError(errorMessage(err));
    } finally {
        setLoading(sendBtn, false, 'Sending…', 'Send code');
    }
});

// ── Stage 2: reset password ───────────────────────────────────
stageReset.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    const code = codeInput.value.trim();
    const newPassword = newPassInput.value;
    const confirm = confirmInput.value;

    if (!/^\d{6}$/.test(code)) {
        showError('Please enter the 6-digit code.');
        return;
    }
    if (newPassword.length < 8) {
        showError('Password must be at least 8 characters.');
        return;
    }
    if (newPassword !== confirm) {
        showError('Passwords do not match.');
        return;
    }

    setLoading(resetBtn, true, 'Resetting…', 'Reset password');
    try {
        await apiPost('/auth/reset-password', {
            email: currentEmail,
            code,
            new_password: newPassword,
        });
        showStage(stageSuccess);
        setTimeout(() => { window.location.href = 'login.html'; }, 2500);
    } catch (err) {
        showError(errorMessage(err));
    } finally {
        setLoading(resetBtn, false, 'Resetting…', 'Reset password');
    }
});

resendBtn.addEventListener('click', async () => {
    clearError();
    resendBtn.disabled = true;
    resendBtn.textContent = 'Sending…';
    try {
        await apiPost('/auth/forgot-password', { email: currentEmail });
        showFeedback('New code sent');
    } catch (err) {
        showError(errorMessage(err));
    } finally {
        resendBtn.disabled = false;
        resendBtn.textContent = 'Resend code';
    }
});

changeEmailLink.addEventListener('click', (e) => {
    e.preventDefault();
    showStage(stageEmail);
    emailInput.focus();
});
