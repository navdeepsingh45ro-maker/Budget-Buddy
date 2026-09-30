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
function logout() {
    clearToken();
    goToLogin();
}
