// ─────────────────────────────────────────────────────────────
//  add-expense.js — BudgetBuddy Add Expense page
//  Depends on: api.js (must be loaded first in add-expense.html)
// ─────────────────────────────────────────────────────────────

/*
Future Features Roadmap
□ AI text parser integration (pre-submission)
□ Voice parser integration (Web Speech to text before submission)
□ Receipt OCR (Image parsing to text before submission)
□ Payment Method backend support
□ Custom expense dates (allow overriding created_at in backend)
□ Merchant field (separate merchant from note in backend schema)
*/

// Require authentication before anything else
requireAuth();

const CATEGORY_MAP = {};

// ── DOM Elements ───────────────────────────────────────────────
const form = document.getElementById('expenseForm');
const amountInput = document.getElementById('amountInput');
const merchantInput = document.getElementById('merchantInput');
const descHelper = document.getElementById('desc-helper');
const categorySelect = document.getElementById('categorySelect');
const dateInput = document.getElementById('dateInput');
const paymentMethod = document.getElementById('paymentMethod');
const paymentIcon = document.getElementById('payment-icon');

// Overlays
const processingOverlay = document.getElementById('processingOverlay');
const processingText = document.getElementById('processingText');
const successOverlay = document.getElementById('successOverlay');

// Global error box (using BudgetBuddy styling if it exists, otherwise creating one)
let errorBox = document.getElementById('global-error-box');
if (!errorBox) {
    // Create one dynamically if not in HTML yet
    errorBox = document.createElement('div');
    errorBox.id = 'global-error-box';
    errorBox.className = 'fixed top-4 left-1/2 -translate-x-1/2 bg-error text-on-error px-4 py-3 rounded-lg shadow-lg z-[100] hidden font-body-md text-center max-w-sm w-[90%]';
    document.body.appendChild(errorBox);
}

// AI status banner (for confidence messages)
let aiBanner = document.getElementById('ai-status-banner');
if (!aiBanner) {
    aiBanner = document.createElement('div');
    aiBanner.id = 'ai-status-banner';
    aiBanner.className = 'fixed top-4 left-1/2 -translate-x-1/2 px-4 py-3 rounded-lg shadow-lg z-[100] hidden font-body-md text-center max-w-sm w-[90%] transition-all duration-300';
    document.body.appendChild(aiBanner);
}

// ── Manual Edit Tracking ───────────────────────────────────────
// Track which fields the user has manually edited so AI won't overwrite them
const manuallyEdited = new Set();

// ── AI Parsed Data ─────────────────────────────────────────────
// Stores the last Gemini-parsed result so submit can use it as fallback
// when no UI chip matches the AI category (e.g. "Health", "Bills")
let aiParsedData = null;

if (amountInput) amountInput.addEventListener('input', () => manuallyEdited.add('amount'));
if (merchantInput) merchantInput.addEventListener('input', () => manuallyEdited.add('note'));
if (dateInput) dateInput.addEventListener('change', () => manuallyEdited.add('date'));
if (paymentMethod) paymentMethod.addEventListener('change', () => manuallyEdited.add('payment_method'));
if (categorySelect) categorySelect.addEventListener('change', () => manuallyEdited.add('category'));

// ── Initialization ─────────────────────────────────────────────
window.onload = () => {
    if (amountInput) amountInput.focus();
};

// ── UI Interactions ────────────────────────────────────────────

// Payment Icon Updater
function updatePaymentIcon(val) {
    if (!paymentIcon) return;
    if (val === 'cash') paymentIcon.innerText = 'payments';
    else if (val === 'upi') paymentIcon.innerText = 'qr_code_scanner';
    else if (val === 'card') paymentIcon.innerText = 'credit_card';
    else if (val === 'bank transfer') paymentIcon.innerText = 'account_balance';
}

// Ensure global scope for HTML onclick
window.updatePaymentIcon = updatePaymentIcon;



// ── Voice Input — Web Speech API + Gemini AI Parsing ──────────
let voiceState = 'idle'; // idle, listening, processing
let recognition = null;

// Check browser support once
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

window.toggleMicState = function(btn) {
    const feedback = document.getElementById('voiceFeedback');
    const text = document.getElementById('voice-state-text');
    const waves = document.getElementById('voice-waves');

    if (!SpeechRecognition) {
        showError("Your browser doesn't support voice input. Try Chrome or Edge.");
        return;
    }

    if (voiceState === 'idle') {
        // ── Start Listening ─────────────────────────────────
        voiceState = 'listening';
        btn.classList.add('text-error', 'bg-error-container');
        btn.innerText = 'mic';
        
        feedback.classList.remove('opacity-0', 'pointer-events-none');
        waves.style.display = 'flex';
        text.innerText = 'Listening...';

        recognition = new SpeechRecognition();
        recognition.lang = 'en-IN';        // Indian English for ₹ context
        recognition.interimResults = false; // Only final results
        recognition.maxAlternatives = 1;
        recognition.continuous = false;

        recognition.onresult = async (event) => {
            const transcript = event.results[0][0].transcript;
            
            // ── Switch to Processing state ──────────────────
            voiceState = 'processing';
            waves.style.display = 'none';
            text.innerText = 'Processing with AI...';
            btn.classList.remove('text-error', 'bg-error-container');
            btn.classList.add('text-primary', 'bg-primary-container');
            btn.innerText = 'graphic_eq';

            // Put transcript in the description field immediately
            if (merchantInput) {
                merchantInput.value = transcript;
                if (descHelper) descHelper.style.opacity = '0';
            }

            try {
                // ── Call Gemini via backend ──────────────────
                // Clear manual edits before AI populate (fresh voice input = fresh state)
                manuallyEdited.clear();
                const parsed = await apiPost('/ai/parse-expense', { text: transcript });
                populateFormFromAI(parsed);
                text.innerText = 'Done ✓';
            } catch (err) {
                console.error('AI parse failed:', err);
                text.innerText = 'AI failed — fill manually';
                // Transcript is already in the description field, user can continue manually
            }

            // Auto-hide feedback after a brief delay
            setTimeout(() => {
                resetMicState(btn, feedback);
            }, 1500);
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            let msg = 'Voice input failed. Please try again.';
            if (event.error === 'no-speech') msg = 'No speech detected. Tap the mic and speak.';
            if (event.error === 'not-allowed') msg = 'Microphone access denied. Please allow mic permissions.';
            if (event.error === 'network') msg = 'Network error. Check your connection.';
            showError(msg);
            resetMicState(btn, feedback);
        };

        recognition.onend = () => {
            // If still in listening state (no result/error triggered), reset
            if (voiceState === 'listening') {
                resetMicState(btn, feedback);
            }
        };

        recognition.start();

    } else {
        // ── Stop / Cancel ───────────────────────────────────
        if (recognition) {
            recognition.abort();
            recognition = null;
        }
        resetMicState(btn, feedback);
    }
};

function resetMicState(btn, feedback) {
    voiceState = 'idle';
    recognition = null;
    btn.classList.remove('text-error', 'bg-error-container', 'text-primary', 'bg-primary-container');
    btn.innerText = 'mic';
    feedback.classList.add('opacity-0', 'pointer-events-none');
}

/**
 * Auto-populate form fields from Gemini's parsed JSON.
 * Does NOT submit — user must press "Log Expense".
 * Respects manually-edited fields — never overwrites them.
 */
function populateFormFromAI(parsed) {
    // Store AI result for submit fallback
    aiParsedData = parsed;

    // Amount (skip if user manually edited)
    if (parsed.amount && amountInput && !manuallyEdited.has('amount')) {
        amountInput.value = parsed.amount;
    }

    // Description / Note (skip if user manually edited)
    if (parsed.note && merchantInput && !manuallyEdited.has('note')) {
        merchantInput.value = parsed.note;
        if (descHelper) descHelper.style.opacity = '0';
    }

    // Category
    if (parsed.category && !manuallyEdited.has('category') && categorySelect) {
        // Ensure category matches one of the options
        const option = Array.from(categorySelect.options).find(o => o.value === parsed.category);
        if (option) {
            categorySelect.value = parsed.category;
        }
    }

    // Payment Method (skip if user manually changed)
    if (parsed.payment_method && paymentMethod && !manuallyEdited.has('payment_method')) {
        const valMap = { 'Cash': 'cash', 'Card': 'card', 'UPI': 'upi' };
        const selectVal = valMap[parsed.payment_method];
        if (selectVal) {
            paymentMethod.value = selectVal;
            updatePaymentIcon(selectVal);
        }
    }

    // Expense Date (skip if user manually set)
    if (parsed.expense_date && dateInput && !manuallyEdited.has('date')) {
        dateInput.type = 'date';
        dateInput.value = parsed.expense_date;
    }

    // ── Confidence-based feedback ────────────────────────────
    showAIConfidenceBanner(parsed.confidence);
}

/**
 * Show a confidence-based status banner after AI parsing.
 */
function showAIConfidenceBanner(confidence) {
    const conf = typeof confidence === 'number' ? confidence : 0;

    if (conf < 0.60) {
        aiBanner.textContent = '⚠️ Please review the extracted details before saving.';
        aiBanner.className = 'fixed top-4 left-1/2 -translate-x-1/2 px-4 py-3 rounded-lg shadow-lg z-[100] font-body-md text-center max-w-sm w-[90%] transition-all duration-300 bg-error-container text-on-error-container';
    } else {
        aiBanner.textContent = '✨ AI filled your expense.';
        aiBanner.className = 'fixed top-4 left-1/2 -translate-x-1/2 px-4 py-3 rounded-lg shadow-lg z-[100] font-body-md text-center max-w-sm w-[90%] transition-all duration-300 bg-secondary-container text-on-secondary-container';
    }

    aiBanner.classList.remove('hidden');
    // Auto-hide after 4 seconds
    setTimeout(() => {
        aiBanner.classList.add('hidden');
    }, 4000);
}

// ── Helpers ────────────────────────────────────────────────────
function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove('hidden');
    // auto hide after 3 seconds
    setTimeout(() => {
        errorBox.classList.add('hidden');
    }, 3000);
}

function getSelectedCategory() {
    return categorySelect && categorySelect.value ? categorySelect.value : null;
}

function getTodayString() {
    return new Date().toISOString().split('T')[0];
}

// ── Submission Flow ────────────────────────────────────────────

form.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    // 1. Gather raw data
    const rawAmount = amountInput.value;
    const rawNote = merchantInput.value.trim();
    const uiCategory = getSelectedCategory();
    let rawDate = dateInput ? dateInput.value : '';
    let rawPaymentMethod = paymentMethod ? paymentMethod.value : 'card';
    
    // 2. Validate
    const amount = parseFloat(rawAmount);
    if (isNaN(amount) || amount <= 0) {
        showError("Please enter a valid amount greater than zero.");
        return;
    }
    
    if (!rawNote) {
        showError("Please describe your expense.");
        return;
    }
    
    if (!uiCategory) {
        // No chip selected — try AI-parsed category as fallback
        if (aiParsedData && aiParsedData.category) {
            // AI provided a valid category directly
        } else {
            showError("Please select a category.");
            return;
        }
    }

    // 3. Format Data
    let mappedCategory = uiCategory;
    let subcategory = uiCategory;

    // AI-parsed fallback if no UI category
    if (!uiCategory) {
        mappedCategory = aiParsedData.category;
        subcategory = aiParsedData.subcategory || aiParsedData.category;
    } else if (!manuallyEdited.has('category') && aiParsedData && aiParsedData.subcategory) {
        subcategory = aiParsedData.subcategory;
    }
    
    // Format Payment Method (capitalize first letter: "card" -> "Card", "upi" -> "UPI")
    if (rawPaymentMethod === 'upi') {
        rawPaymentMethod = 'UPI';
    } else {
        rawPaymentMethod = rawPaymentMethod.charAt(0).toUpperCase() + rawPaymentMethod.slice(1);
    }
    
    // Default date to today if empty
    if (!rawDate) {
        rawDate = getTodayString();
    }

    // 4. Normalized Payload for unified architecture
    const normalizedExpense = {
        amount: amount,
        category: mappedCategory,
        subcategory: subcategory,
        note: rawNote,
        payment_method: rawPaymentMethod,
        expense_date: rawDate
    };

    // 5. Submit
    await submitExpense(normalizedExpense);
});

/**
 * Unified submission function.
 * Future AI parsers (voice, text, OCR) will construct a normalized object
 * and call this function directly.
 */
async function submitExpense(expenseData) {
    try {
        // Sequenced Loading State
        processingOverlay.classList.remove('hidden');
        setTimeout(() => processingOverlay.classList.remove('opacity-0'), 10);
        
        processingText.innerText = 'Reading...';
        
        await new Promise(r => setTimeout(r, 400));
        processingText.innerText = 'Categorizing...';
        
        await new Promise(r => setTimeout(r, 400));
        processingText.innerText = 'Saving...';
        
        // Ensure payload exactly matches the finalized backend contract
        const payload = {
            amount: expenseData.amount,
            category: expenseData.category,
            subcategory: expenseData.subcategory,
            note: expenseData.note,
            payment_method: expenseData.payment_method,
            expense_date: expenseData.expense_date
        };

        // Network Call
        await apiPost('/expense/', payload);
        
        // Hide processing
        processingOverlay.classList.add('opacity-0');
        setTimeout(() => processingOverlay.classList.add('hidden'), 300);
        
        // Show Success UI
        showSuccessUI(expenseData.amount, expenseData.subcategory);

    } catch (err) {
        // Hide processing
        processingOverlay.classList.add('opacity-0');
        setTimeout(() => processingOverlay.classList.add('hidden'), 300);
        
        // Extract clean error message
        let errorMsg = err.message || "Failed to save expense. Please try again.";
        if (err.detail && typeof err.detail === 'string') {
            errorMsg = err.detail;
        } else if (err.detail && Array.isArray(err.detail)) {
            errorMsg = err.detail[0]?.msg || errorMsg;
        }
        
        showError(errorMsg);
    }
}

function showSuccessUI(amountVal, catName) {
    const icon = document.getElementById('successIconCont');
    const title = document.getElementById('successTitle');
    const amt = document.getElementById('successAmount');
    const cat = document.getElementById('successCategory');
    const msg = document.getElementById('successMsg');
    
    // Populate static visual placeholders dynamically
    amt.innerText = '₹' + parseFloat(amountVal).toFixed(2);
    cat.innerText = catName;
    
    successOverlay.classList.remove('hidden');
    setTimeout(() => {
        successOverlay.classList.remove('opacity-0');
        icon.classList.remove('scale-50');
        icon.classList.add('scale-100');
        title.classList.remove('opacity-0');
        amt.classList.remove('opacity-0');
        cat.classList.remove('opacity-0');
        msg.classList.remove('opacity-0');
    }, 10);
    
    // Reset after animation
    setTimeout(() => {
        successOverlay.classList.add('opacity-0');
        setTimeout(() => {
            successOverlay.classList.add('hidden');
            icon.classList.replace('scale-100', 'scale-50');
            title.classList.add('opacity-0');
            amt.classList.add('opacity-0');
            cat.classList.add('opacity-0');
            msg.classList.add('opacity-0');
            
            // Full Reset
            form.reset();
            manuallyEdited.clear();
            aiParsedData = null;
            if (categorySelect) categorySelect.value = "";
            if (descHelper) descHelper.style.opacity = '1';
            
            // Reset Date & Payment Method
            if (dateInput) {
                dateInput.value = '';
                dateInput.type = 'text';
            }
            if (paymentMethod) {
                paymentMethod.value = 'card';
                updatePaymentIcon('card');
            }
            
            if (amountInput) amountInput.focus();
            
            // Optionally redirect after success
            // setTimeout(() => goToDashboard(), 1500);
        }, 500);
    }, 2500);
}