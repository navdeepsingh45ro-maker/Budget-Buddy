// ─────────────────────────────────────────────────────────────
//  api.js — BudgetBuddy shared API utility
//  Every other JS file imports from this. Never write raw
//  fetch() calls outside this file.
// ─────────────────────────────────────────────────────────────

const API_BASE = 'http://localhost:8000';  // change to your Render URL on deploy

// ── Token helpers ─────────────────────────────────────────────
function getToken()        { return localStorage.getItem('bb_token'); }
function setToken(token)   { localStorage.setItem('bb_token', token); }
function clearToken()      { localStorage.removeItem('bb_token'); }
function isLoggedIn()      { return !!getToken(); }

// ── Redirect helpers ──────────────────────────────────────────
function goToLogin()       { window.location.href = '/login.html'; }
function goToDashboard()   { window.location.href = '/dashboard.html'; }

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

async function apiDelete(endpoint) {
    return apiRequest(endpoint, { method: 'DELETE' });
}

// ── Special case: login uses form encoding, not JSON ──────────
// FastAPI's OAuth2PasswordRequestForm expects application/x-www-form-urlencoded.
// This is the ONE place we don't use JSON.
async function apiLogin(username, password) {
    const body = new URLSearchParams({ username, password });

    const res = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
    });

    const data = await res.json();

    if (!res.ok) {
        throw new Error(data.detail || 'Invalid username or password');
    }

    // Store the token and return
    setToken(data.access_token);
    return data;
}

// ── Logout ────────────────────────────────────────────────────
function logout() {
    clearToken();
    goToLogin();
}