// ─────────────────────────────────────────────────────────────
//  register.js — BudgetBuddy register page
//  Depends on: api.js (must be loaded first in register.html)
//
//  Backend endpoint:
//    POST /users/
//    Body: { name, email, password, age_group, accept_terms, guardian_consent }
//    age_group is "under_13" | "13_17" | "18_plus". The server refuses
//    under-13s and 13-17s without a parent's OK, so these checks are
//    repeated there; the ones here just give faster feedback.
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
function selectedAgeGroup() {
    const checked = document.querySelector('input[name="age_group"]:checked');
    return checked ? checked.value : null;
}

// Show the parent/guardian checkbox only for 13-17, and the refusal note for under 13.
const guardianRow = document.getElementById('guardian-row');
const under13Note = document.getElementById('under13-note');
document.querySelectorAll('input[name="age_group"]').forEach(radio => {
    radio.addEventListener('change', () => {
        const age = selectedAgeGroup();
        guardianRow.classList.toggle('hidden', age !== '13_17');
        under13Note.classList.toggle('hidden', age !== 'under_13');
        btn.disabled = age === 'under_13';
        clearError();
    });
});

['guardian-consent', 'accept-terms'].forEach(id =>
    document.getElementById(id).addEventListener('change', clearError));

function validate(name, email, password, confirm) {
    if (!name.trim())
        return 'Please enter your full name.';

    if (!email.trim() || !email.includes('@'))
        return 'Please enter a valid email address.';

    if (password.length < 8)
        return 'Password must be at least 8 characters.';

    if (password !== confirm)
        return 'Passwords do not match.';

    const age = selectedAgeGroup();
    if (!age)
        return 'Please tell us your age group.';

    if (age === 'under_13')
        return 'Sorry, you need to be 13 or older to use Budget Buddy.';

    if (age === '13_17' && !document.getElementById('guardian-consent').checked)
        return 'If you\'re under 18, a parent or guardian needs to agree before you sign up.';

    if (!document.getElementById('accept-terms').checked)
        return 'Please agree to the Terms of Service and Privacy Policy.';

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
        const age_group = selectedAgeGroup();
        const res = await apiPost('/users/', {
            name, email, password, age_group,
            accept_terms: document.getElementById('accept-terms').checked,
            guardian_consent: age_group === '13_17' && document.getElementById('guardian-consent').checked,
        });

        if (res && res.verification_required) {
            // Step 2: confirm the email with the code we just sent
            try { sessionStorage.setItem('bb_verify_email', res.email || email.trim().toLowerCase()); } catch (e2) { /* ignore */ }
            window.location.href = 'verify_email.html';
            return;
        }

        // Fallback (no verification needed): log them in straight away
        await apiLogin(email, password);

        // New accounts see the welcome tutorial first
        window.location.href = 'welcome.html';

    } catch (err) {
        // Common backend error: "Email already registered"
        showError(err.message);
    } finally {
        setLoading(false);
    }
});

// ── Password Strength Checker ─────────────────────────────────
const passwordInput = document.getElementById('password');
const pBars = [
    document.getElementById('p-bar-1'),
    document.getElementById('p-bar-2'),
    document.getElementById('p-bar-3'),
    document.getElementById('p-bar-4')
];
const strengthText = document.getElementById('strength-text');

passwordInput && passwordInput.addEventListener('input', () => {
    const val = passwordInput.value;
    let score = 0;
    
    if (!val) {
        pBars.forEach(bar => {
            bar.className = 'strength-bar h-full w-1/4 rounded-full bg-surface-variant';
        });
        strengthText.textContent = 'Security level';
        return;
    }

    // Basic scoring
    if (val.length >= 8) score++;
    if (/[A-Z]/.test(val)) score++;
    if (/[0-9]/.test(val)) score++;
    if (/[^A-Za-z0-9]/.test(val)) score++;

    // Update bars and color schemes
    pBars.forEach((bar, idx) => {
        if (idx < score) {
            if (score <= 1) {
                // Weak: Red
                bar.className = 'strength-bar h-full w-1/4 rounded-full bg-red-500';
            } else if (score <= 3) {
                // Medium: Amber/Orange
                bar.className = 'strength-bar h-full w-1/4 rounded-full bg-amber-500';
            } else {
                // Strong: Emerald/Green
                bar.className = 'strength-bar h-full w-1/4 rounded-full bg-emerald-500';
            }
        } else {
            bar.className = 'strength-bar h-full w-1/4 rounded-full bg-surface-variant';
        }
    });

    const labels = ['Weak', 'Fair', 'Good', 'Strong'];
    strengthText.textContent = labels[score - 1] || 'Weak';
});