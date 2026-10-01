// ─────────────────────────────────────────────────────────────
//  api.js — BudgetBuddy shared API utility
//  Every other JS file imports from this. Never write raw
//  fetch() calls outside this file.
// ─────────────────────────────────────────────────────────────

// Backend URL: local API when the page is served from this machine, otherwise
// the deployed API. Set PRODUCTION_API_BASE once the backend is hosted.
const PRODUCTION_API_BASE = 'https://YOUR-BACKEND-URL.onrender.com';
const IS_LOCAL = ['localhost', '127.0.0.1', ''].includes(window.location.hostname);
const API_BASE = window.BB_API_BASE || (IS_LOCAL ? 'http://127.0.0.1:8000' : PRODUCTION_API_BASE);

// ── HTML escaping ─────────────────────────────────────────────
// Wrap every user-supplied value (notes, titles, names) in escapeHtml()
// before putting it inside an innerHTML template string.
function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// ── Date and percentage formatting ───────────────────────────
function parseApiDate(value) {
    if (typeof value !== 'string') return new Date(value);
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
        const [, year, month, day] = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        return new Date(Number(year), Number(month) - 1, Number(day));
    }
    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
    return new Date(hasTimezone ? value : `${value}Z`);
}

function formatExpenseDate(value, { withYear = false } = {}) {
    const dateOnly = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
    const date = parseApiDate(value);
    if (Number.isNaN(date.getTime())) return '';

    const now = new Date();
    const calendarDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const dayDiff = Math.round((calendarDay(now) - calendarDay(date)) / 86400000);
    if (dayDiff === 0) {
        if (!dateOnly) {
            return `Today, ${date.toLocaleTimeString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })}`;
        }
        return 'Today';
    }
    if (dayDiff === 1) return 'Yesterday';

    return date.toLocaleDateString('en-IN', {
        day: 'numeric', month: 'short', ...(withYear ? { year: 'numeric' } : {}),
    });
}

function formatPercent(value) {
    const percentage = Number(value);
    if (percentage > 0 && percentage < 1) return 'under 1%';
    if (percentage >= 1 && percentage < 10) return `${percentage.toFixed(1)}%`;
    return `${Math.round(percentage)}%`;
}

// ── Token helpers ─────────────────────────────────────────────
function getToken()        { return localStorage.getItem('bb_token'); }
function setToken(token)   { localStorage.setItem('bb_token', token); }
function clearToken()      { localStorage.removeItem('bb_token'); }
function isLoggedIn()      { return !!getToken(); }

// ── Redirect helpers ──────────────────────────────────────────
function goToLogin()       { window.location.href = 'login.html'; }
function goToDashboard()   { window.location.href = 'dashboard.html'; }

// Guard: call this at the top of any protected page
// e.g. dashboard.js → requireAuth();
function requireAuth() {
    if (!isLoggedIn()) goToLogin();
}

// ── Core request function ─────────────────────────────────────
// All GET / POST / PUT / DELETE calls go through here.
// Automatically attaches the JWT and handles 401s globally.
async function apiRequest(endpoint, options = {}) {
    const token = getToken();

    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...options.headers,
    };

    const res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
    });

    // Token expired or invalid → kick back to login
    if (res.status === 401) {
        clearToken();
        goToLogin();
        return;
    }

    const data = await res.json();

    if (!res.ok) {
        // data.detail is FastAPI's default error key
        throw new Error(data.detail || 'Something went wrong');
    }

    return data;
}

// ── Shorthand methods ─────────────────────────────────────────
// Use these in every feature file instead of raw apiRequest()

async function apiGet(endpoint) {
    return apiRequest(endpoint, { method: 'GET' });
}

async function apiPost(endpoint, body) {
    return apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify(body),
    });
}

async function apiPut(endpoint, body) {
    return apiRequest(endpoint, {
        method: 'PUT',
        body: JSON.stringify(body),
    });
}

async function apiPatch(endpoint, body = {}) {
    return apiRequest(endpoint, {
        method: 'PATCH',
        body: JSON.stringify(body),
    });
}

async function apiDelete(endpoint) {
    return apiRequest(endpoint, { method: 'DELETE' });
}

// File uploads (multipart). The browser sets the Content-Type boundary itself.
async function apiUpload(endpoint, formData) {
    const token = getToken();
    const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body: formData,
    });

    if (res.status === 401) {
        clearToken();
        goToLogin();
        return;
    }

    const data = await res.json();
    if (!res.ok) {
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Something went wrong');
    }
    return data;
}

// ── Special case: login uses JSON (matches your FastAPI LoginSchema) ──
async function apiLogin(email, password) {
    const res = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json',},
        body: JSON.stringify({
            email,
            password
        }),
    });
    
    const data = await res.json();

    if (!res.ok) {
        throw new Error(data.detail || 'Invalid email or password');
    }
     setToken(data.access_token);
     return data;
}

// ── Logout ────────────────────────────────────────────────────
// Turns off push on this device first (while the token is still valid), so the
// next person to log in here doesn't receive the previous user's notifications.
// Bounded to ~2s and every failure is swallowed so logout can never hang or fail.
async function logout() {
    try {
        await Promise.race([
            (async () => {
                if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
                const reg = await navigator.serviceWorker.getRegistration();
                const sub = reg && reg.pushManager ? await reg.pushManager.getSubscription() : null;
                if (!sub) return;
                try { await apiPost('/push/unsubscribe', { endpoint: sub.endpoint }); } catch (e) { /* ignore */ }
                try { await sub.unsubscribe(); } catch (e) { /* ignore */ }
            })(),
            new Promise(resolve => setTimeout(resolve, 2000))
        ]);
    } catch (e) { /* never block logout */ }
    clearToken();
    goToLogin();
}
