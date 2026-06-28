// ─────────────────────────────────────────────────────────────
//  add-expense.js — BudgetBuddy Add Expense page
//  Depends on: api.js (must be loaded first in add-expense.html)
//
//  Backend endpoint expected:
//    POST /expenses
//    Headers: Authorization: Bearer <token>
//    Body: { amount, category, date, note }
//    Returns: the created expense object
//
//  ⚠️  Verify field names match your expense_schema.py
// ─────────────────────────────────────────────────────────────

requireAuth(); // redirect to login if no token

const form    = document.getElementById('AddExpenseForm');
const btn     = document.getElementById('add-expense-btn');
const errBox  = document.getElementById('expense-error');
const micBtn  = document.getElementById('mic-btn');  // if you have one

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
    btn.textContent = loading ? 'Logging…' : 'Log Expense';
}

function showSuccess() {
    btn.textContent = '✓ Logged!';
    btn.style.background = '#4a9e6b';
    setTimeout(() => {
        btn.textContent = 'Log Expense';
        btn.style.background = '';
        form.reset();
        // Set today's date again after reset
        document.getElementById('date').value = new Date().toISOString().split('T')[0];
    }, 1500);
}

// ── Set today's date as default ───────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const dateField = document.getElementById('date');
    if (dateField) {
        dateField.value = new Date().toISOString().split('T')[0];
    }
});

// ── Form submit ───────────────────────────────────────────────
form && form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    const amount   = parseFloat(document.getElementById('amount').value);
    const category = document.getElementById('category').value;
    const date     = document.getElementById('date').value;
    const note     = document.getElementById('note')?.value || '';

    if (!amount || amount <= 0) {
        showError('Please enter a valid amount.');
        return;
    }
    if (!category) {
        showError('Please select a category.');
        return;
    }

    setLoading(true);

    try {
        // ⚠️ Adjust field names to match your expense_schema.py exactly
        await apiPost('/expenses', {
            amount,
            category,
            date,
            note,
        });

        showSuccess();

    } catch (err) {
        showError(err.message);
    } finally {
        setLoading(false);
    }
});

// ── Voice input (Web Speech API) ──────────────────────────────
// Parses natural speech like "spent 450 on groceries" and
// fills the form fields automatically — no AI needed.
let recording = false;
let recognition = null;

micBtn && micBtn.addEventListener('click', () => {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRec) {
        showError('Voice input is not supported in this browser. Try Chrome.');
        return;
    }

    if (recording) {
        recognition && recognition.stop();
        return;
    }

    recognition = new SpeechRec();
    recognition.lang = 'en-IN';
    recognition.interimResults = false;

    recognition.onstart = () => {
        recording = true;
        micBtn.style.background = '#ece8f5';
        micBtn.style.borderColor = '#9784ae';
    };

    recognition.onresult = (e) => {
        const transcript = e.results[0][0].transcript.toLowerCase();
        parseVoiceInput(transcript);
    };

    recognition.onend = () => {
        recording = false;
        micBtn.style.background = '';
        micBtn.style.borderColor = '';
    };

    recognition.start();
});

// Parses: "spent 450 on groceries" / "250 rupees food" / "coffee 120"
function parseVoiceInput(text) {
    const amountMatch = text.match(/\d+(\.\d+)?/);
    if (amountMatch) {
        document.getElementById('amount').value = parseFloat(amountMatch[0]);
    }

    // ⚠️ Match these category keywords to your actual category values
    const categoryMap = {
        'food': 'Food & Dining',
        'grocery': 'Food & Dining',
        'groceries': 'Food & Dining',
        'restaurant': 'Food & Dining',
        'coffee': 'Food & Dining',
        'transport': 'Transport',
        'uber': 'Transport',
        'auto': 'Transport',
        'cab': 'Transport',
        'rent': 'Rent & Bills',
        'bill': 'Rent & Bills',
        'electricity': 'Rent & Bills',
        'entertainment': 'Fun & Entertainment',
        'movie': 'Fun & Entertainment',
        'shopping': 'Shopping',
        'clothes': 'Shopping',
    };

    for (const [keyword, category] of Object.entries(categoryMap)) {
        if (text.includes(keyword)) {
            const categorySelect = document.getElementById('category');
            if (categorySelect) categorySelect.value = category;
            break;
        }
    }

    const noteField = document.getElementById('note');
    if (noteField) noteField.value = text.charAt(0).toUpperCase() + text.slice(1);
}