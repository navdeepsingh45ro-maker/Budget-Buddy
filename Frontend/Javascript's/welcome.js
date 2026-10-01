// ─────────────────────────────────────────────────────────────
//  welcome.js — BudgetBuddy new-user welcome tutorial
//  Depends on: api.js, notifications.js (loaded first in welcome.html)
//
//  Steps: 1 carousel · 2 budget · 3 first expense · 4 notifications · 5 done
//  The account is only marked as onboarded when the user taps the button
//  on the Done step (PUT /users/me/settings { onboarding_completed: true }).
// ─────────────────────────────────────────────────────────────
(function () {
    'use strict';

    requireAuth();
    if (!isLoggedIn()) return; // requireAuth() is redirecting to login

    const TOTAL_STEPS = 4;     // steps counted in the progress label (Done is not counted)
    const DONE_STEP = 5;

    const $ = (id) => document.getElementById(id);

    // ── State ─────────────────────────────────────────────────
    let currentStep = 1;
    let slideIndex = 0;
    const slideCount = 3;
    const summary = { budget: null, expense: false, push: false };
    let swReadyPromise = Promise.resolve();

    // ── Generic helpers ───────────────────────────────────────
    function showError(el, msg) { el.textContent = msg; el.classList.remove('hidden'); }
    function clearError(el) { el.textContent = ''; el.classList.add('hidden'); }

    function setLoading(btn, labelEl, loading, loadingText, idleText) {
        btn.disabled = loading;
        labelEl.textContent = loading ? loadingText : idleText;
    }

    function localDateString() {
        const d = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    }

    // ── Step navigation ───────────────────────────────────────
    function goToStep(step) {
        currentStep = step;
        document.querySelectorAll('[data-step]').forEach((section) => {
            const active = Number(section.dataset.step) === step;
            section.classList.toggle('hidden', !active);
            if (active) {
                section.classList.remove('step-enter');
                void section.offsetWidth; // restart the entrance animation
                section.classList.add('step-enter');
            }
        });

        const onDone = step === DONE_STEP;
        $('progress-label').textContent = onDone ? 'All done' : `Step ${step} of ${TOTAL_STEPS}`;
        $('skip-btn').classList.toggle('hidden', onDone);
        window.scrollTo(0, 0);

        if (step === 4) initPushStep();
        if (step === DONE_STEP) renderSummary();
    }

    function nextStep() { goToStep(Math.min(currentStep + 1, DONE_STEP)); }

    // ── Step 1: carousel ──────────────────────────────────────
    function renderCarousel() {
        $('carousel-track').style.transform = `translateX(-${slideIndex * 100}%)`;
        document.querySelectorAll('#carousel-dots .dot').forEach((dot, i) => {
            dot.classList.toggle('bg-primary', i === slideIndex);
            dot.classList.toggle('bg-outline-variant', i !== slideIndex);
            dot.classList.toggle('w-5', i === slideIndex);
            dot.classList.toggle('w-2', i !== slideIndex);
        });
        $('carousel-next-label').textContent = slideIndex === slideCount - 1 ? "Let's set you up" : 'Next';
    }

    function setSlide(i) {
        slideIndex = Math.max(0, Math.min(slideCount - 1, i));
        renderCarousel();
    }

    function initCarousel() {
        $('carousel-next-btn').addEventListener('click', () => {
            if (slideIndex < slideCount - 1) setSlide(slideIndex + 1);
            else goToStep(2);
        });
        document.querySelectorAll('#carousel-dots .dot').forEach((dot, i) => {
            dot.addEventListener('click', () => setSlide(i));
        });

        // Swipe (touch)
        const viewport = $('carousel-viewport');
        let startX = 0, startY = 0, tracking = false;
        viewport.addEventListener('touchstart', (e) => {
            if (e.touches.length !== 1) return;
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            tracking = true;
        }, { passive: true });
        viewport.addEventListener('touchend', (e) => {
            if (!tracking) return;
            tracking = false;
            const t = e.changedTouches[0];
            const dx = t.clientX - startX;
            const dy = t.clientY - startY;
            if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) {
                setSlide(slideIndex + (dx < 0 ? 1 : -1));
            }
        }, { passive: true });
        viewport.addEventListener('touchcancel', () => { tracking = false; }, { passive: true });

        $('skip-setup-btn').addEventListener('click', () => goToStep(DONE_STEP));
        renderCarousel();
    }

    async function greetUser() {
        try {
            const user = await apiGet('/users/me');
            const first = user && user.name ? String(user.name).trim().split(/\s+/)[0] : '';
            if (first) $('slide-1-title').textContent = `Hi ${first}, I'm Buddy!`;
        } catch (e) { /* keep the generic greeting */ }
    }

    // ── Step 2: monthly budget ────────────────────────────────
    function syncChips() {
        const value = Number($('budget-input').value);
        document.querySelectorAll('#budget-chips .chip').forEach((chip) => {
            const selected = Number(chip.dataset.amount) === value;
            chip.classList.toggle('border-primary', selected);
            chip.classList.toggle('text-primary', selected);
            chip.classList.toggle('bg-primary-fixed', selected);
            chip.classList.toggle('border-outline-variant', !selected);
            chip.classList.toggle('text-on-surface-variant', !selected);
            chip.classList.toggle('bg-surface-container-lowest', !selected);
        });
    }

    function initBudget() {
        const input = $('budget-input');
        document.querySelectorAll('#budget-chips .chip').forEach((chip) => {
            chip.addEventListener('click', () => {
                input.value = chip.dataset.amount;
                clearError($('budget-error'));
                syncChips();
            });
        });
        input.addEventListener('input', syncChips);

        $('budget-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const errEl = $('budget-error');
            clearError(errEl);

            const amount = Number(input.value);
            if (!input.value || !Number.isFinite(amount) || amount <= 0) {
                showError(errEl, 'Please enter a budget greater than 0.');
                return;
            }

            const btn = $('budget-btn'), label = $('budget-btn-label');
            setLoading(btn, label, true, 'Saving…', 'Continue');
            try {
                const body = { monthly_budget: amount };
                try {
                    await apiPost('/budget/', body);
                } catch (err) {
                    // A budget for this month already exists: update it instead.
                    if (err && /already exists/i.test(err.message || '')) {
                        await apiPut('/budget/', body);
                    } else {
                        throw err;
                    }
                }
                summary.budget = amount;
                nextStep();
            } catch (err) {
                showError(errEl, err.message || 'Could not save your budget. Please try again.');
            } finally {
                setLoading(btn, label, false, 'Saving…', 'Continue');
            }
        });
    }

    // ── Step 3: first expense ─────────────────────────────────
    function initExpense() {
        $('expense-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const errEl = $('expense-error');
            clearError(errEl);

            const amountRaw = $('expense-amount').value;
            const amount = Number(amountRaw);
            const note = $('expense-note').value.trim();
            const category = $('expense-category').value;

            if (!amountRaw || !Number.isFinite(amount) || amount <= 0) {
                showError(errEl, 'Please enter an amount greater than 0.');
                return;
            }
            if (!category) {
                showError(errEl, 'Please choose a category.');
                return;
            }

            const btn = $('expense-btn'), label = $('expense-btn-label');
            setLoading(btn, label, true, 'Saving…', 'Save expense');
            try {
                await apiPost('/expense/', {
                    amount,
                    category,
                    note,
                    expense_date: localDateString(),
                });
                summary.expense = true;
                nextStep();
            } catch (err) {
                showError(errEl, err.message || 'Could not save your expense. Please try again.');
            } finally {
                setLoading(btn, label, false, 'Saving…', 'Save expense');
            }
        });
    }

    // ── Step 4: notifications ─────────────────────────────────
    function showPushMessage(text) {
        const el = $('push-message');
        el.textContent = text;
        el.classList.remove('hidden');
    }

    function setPushButtonVisible(visible) {
        const btn = $('push-btn');
        btn.classList.toggle('hidden', !visible);
        btn.classList.toggle('flex', visible);
    }

    const PUSH_TEXT = {
        on: 'Notifications are already on for this device.',
        iosInstall: 'On iPhone: tap Share → Add to Home Screen, then open Budget Buddy from your Home Screen and turn on notifications in Settings.',
        unsupported: "This browser doesn't support notifications. You'll still see everything in the bell inside the app.",
        denied: "Notifications are blocked in your browser settings — you can turn them on later in Settings.",
    };

    async function initPushStep() {
        clearError($('push-error'));
        $('push-message').classList.add('hidden');
        setPushButtonVisible(false);

        let state = 'unsupported';
        try {
            await swReadyPromise;
            state = await getPushState();
        } catch (e) { /* fall back to unsupported */ }

        if (currentStep !== 4) return;

        if (state === 'off') {
            setPushButtonVisible(true);
        } else if (state === 'on') {
            summary.push = true;
            showPushMessage(PUSH_TEXT.on);
        } else if (state === 'ios-needs-install') {
            showPushMessage(PUSH_TEXT.iosInstall);
        } else if (state === 'denied') {
            showPushMessage(PUSH_TEXT.denied);
        } else {
            showPushMessage(PUSH_TEXT.unsupported);
        }
    }

    function initPush() {
        $('push-btn').addEventListener('click', async () => {
            const btn = $('push-btn'), label = $('push-btn-label');
            clearError($('push-error'));
            setLoading(btn, label, true, 'Turning on…', 'Turn on notifications');
            try {
                const result = await enablePush(); // must run from this click
                if (result === 'on') {
                    summary.push = true;
                    setPushButtonVisible(false);
                    showPushMessage('Notifications are on!');
                } else if (result === 'denied') {
                    setPushButtonVisible(false);
                    showPushMessage(PUSH_TEXT.denied);
                } else {
                    showError($('push-error'), "Notifications weren't turned on. Please try again.");
                }
            } catch (err) {
                showError($('push-error'), err.message || "Couldn't turn on notifications. Please try again.");
            } finally {
                setLoading(btn, label, false, 'Turning on…', 'Turn on notifications');
            }
        });
        $('push-continue-btn').addEventListener('click', nextStep);
    }

    // ── Step 5: done ──────────────────────────────────────────
    function setSummaryRow(key, done, doneText, skippedText) {
        $(`summary-${key}`).textContent = done ? doneText : skippedText;
        const icon = $(`summary-${key}-icon`);
        icon.textContent = done ? 'check_circle' : 'radio_button_unchecked';
        icon.classList.toggle('text-primary', done);
        icon.classList.toggle('text-outline', !done);
    }

    function renderSummary() {
        const budgetText = summary.budget
            ? `Monthly budget set to ₹${summary.budget.toLocaleString('en-IN')}`
            : '';
        setSummaryRow('budget', summary.budget !== null, budgetText, 'Budget skipped — set it anytime in Budget');
        setSummaryRow('expense', summary.expense, 'First expense added', 'First expense skipped');
        setSummaryRow('push', summary.push, 'Notifications are on', 'Notifications skipped — turn them on in Settings');
    }

    function initDone() {
        $('done-btn').addEventListener('click', async () => {
            const btn = $('done-btn'), label = $('done-btn-label');
            setLoading(btn, label, true, 'Opening dashboard…', 'Go to my dashboard');
            try {
                await apiPut('/users/me/settings', { onboarding_completed: true });
            } catch (e) { /* never block the user on this */ }
            goToDashboard();
        });
    }

    // ── Init ──────────────────────────────────────────────────
    function registerServiceWorker() {
        // initPushNotifications() in notifications.js only runs when a bell exists,
        // so register the worker here (silent: never shows a permission prompt).
        if (!('serviceWorker' in navigator)) return;
        swReadyPromise = navigator.serviceWorker.register('service-worker.js')
            .catch((err) => { console.error('Service Worker registration failed:', err); });
    }

    $('skip-btn').addEventListener('click', nextStep);
    initCarousel();
    initBudget();
    initExpense();
    initPush();
    initDone();
    registerServiceWorker();
    greetUser();
    goToStep(1);
})();
