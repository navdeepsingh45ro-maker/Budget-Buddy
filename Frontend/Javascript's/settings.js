// ─────────────────────────────────────────────────────────────
//  settings.js — BudgetBuddy Settings page
//  Depends on: api.js, notifications.js (mountNotificationSettings)
// ─────────────────────────────────────────────────────────────

requireAuth();

(function () {
    if (!isLoggedIn()) return; // requireAuth() is already redirecting

    const $ = (id) => document.getElementById(id);

    // ── Small helpers ───────────────────────────────────────────

    // Server messages are shown with textContent only.
    function errMsg(err, fallback) {
        const m = err && err.message;
        if (!m || typeof m !== 'string' || m.indexOf('[object') !== -1) return fallback;
        return m;
    }

    function showLine(el, text) {
        el.textContent = text || '';
        el.classList.toggle('hidden', !text);
    }

    // Disables a button and swaps its label while a request runs.
    // Returns a function that restores it.
    function setBusy(btn, busyText) {
        const original = btn.textContent;
        btn.disabled = true;
        btn.textContent = busyText;
        return function done() {
            btn.disabled = false;
            btn.textContent = original;
        };
    }

    function setSwitch(sw, on) {
        sw.setAttribute('aria-checked', on ? 'true' : 'false');
        sw.classList.toggle('bg-primary', on);
        sw.classList.toggle('bg-outline-variant', !on);
        if (sw.firstElementChild) sw.firstElementChild.classList.toggle('translate-x-5', on);
    }

    // ── Show / hide password (eye buttons) ──────────────────────

    function resetEyes(scope) {
        scope.querySelectorAll('[data-eye-for]').forEach((btn) => {
            const input = $(btn.dataset.eyeFor);
            if (input) input.type = 'password';
            btn.firstElementChild.textContent = 'visibility';
        });
    }

    document.querySelectorAll('[data-eye-for]').forEach((btn) => {
        btn.addEventListener('click', () => {
            const input = $(btn.dataset.eyeFor);
            if (!input) return;
            const show = input.type === 'password';
            input.type = show ? 'text' : 'password';
            btn.firstElementChild.textContent = show ? 'visibility_off' : 'visibility';
        });
    });

    // ── 1. Account: name ────────────────────────────────────────

    const nameEl = $('account-name');
    const emailEl = $('account-email');
    const nameEditBtn = $('name-edit-btn');
    const nameForm = $('name-form');
    const nameInput = $('name-input');
    const nameError = $('name-error');
    const nameSaveBtn = $('name-save-btn');
    const nameCancelBtn = $('name-cancel-btn');
    let currentName = '';

    async function loadUser() {
        try {
            const user = await apiGet('/users/me');
            if (!user) return;
            currentName = user.name || '';
            nameEl.textContent = currentName || '—';
            emailEl.textContent = user.email || '—';
            nameEditBtn.disabled = false;
        } catch (err) {
            nameEl.textContent = "Couldn't load";
            emailEl.textContent = "Couldn't load";
        }
    }

    function openNameEdit() {
        nameInput.value = currentName;
        showLine(nameError, '');
        nameForm.classList.remove('hidden');
        nameEditBtn.classList.add('hidden');
        nameInput.focus();
    }

    function closeNameEdit() {
        nameForm.classList.add('hidden');
        nameEditBtn.classList.remove('hidden');
        showLine(nameError, '');
    }

    nameEditBtn.addEventListener('click', openNameEdit);
    nameCancelBtn.addEventListener('click', closeNameEdit);

    nameForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = nameInput.value.trim();
        if (!name) {
            showLine(nameError, 'Please enter your name');
            return;
        }
        showLine(nameError, '');
        const done = setBusy(nameSaveBtn, 'Saving…');
        nameCancelBtn.disabled = true;
        try {
            const user = await apiPut('/users/me', { name });
            if (user) {
                currentName = user.name || name;
                nameEl.textContent = currentName;
            }
            closeNameEdit();
        } catch (err) {
            showLine(nameError, errMsg(err, "Couldn't save your name. Please try again."));
        } finally {
            done();
            nameCancelBtn.disabled = false;
        }
    });

    // ── 1. Account: change password ─────────────────────────────

    const pwToggleBtn = $('pw-toggle-btn');
    const pwToggleIcon = $('pw-toggle-icon');
    const pwForm = $('pw-form');
    const pwCurrent = $('pw-current');
    const pwNew = $('pw-new');
    const pwConfirm = $('pw-confirm');
    const pwError = $('pw-error');
    const pwSuccess = $('pw-success');
    const pwSaveBtn = $('pw-save-btn');
    const pwCancelBtn = $('pw-cancel-btn');

    function setPwOpen(open) {
        pwForm.classList.toggle('hidden', !open);
        pwToggleBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        pwToggleIcon.textContent = open ? 'expand_less' : 'expand_more';
        if (open) {
            pwCurrent.focus();
        } else {
            pwForm.reset();
            resetEyes(pwForm);
            showLine(pwError, '');
            showLine(pwSuccess, '');
        }
    }

    pwToggleBtn.addEventListener('click', () => setPwOpen(pwForm.classList.contains('hidden')));
    pwCancelBtn.addEventListener('click', () => setPwOpen(false));

    pwForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        showLine(pwError, '');
        showLine(pwSuccess, '');

        const current = pwCurrent.value;
        const next = pwNew.value;
        const confirm = pwConfirm.value;

        if (!current) { showLine(pwError, 'Enter your current password'); return; }
        if (next.length < 8) { showLine(pwError, 'New password must be at least 8 characters'); return; }
        if (next !== confirm) { showLine(pwError, "New passwords don't match"); return; }

        const done = setBusy(pwSaveBtn, 'Updating…');
        pwCancelBtn.disabled = true;
        try {
            // Changing the password signs out every other device; keep this one logged in.
            const res = await apiPost('/users/me/password', { current_password: current, new_password: next });
            if (res && res.access_token) setToken(res.access_token);
            pwForm.reset();
            resetEyes(pwForm);
            showLine(pwSuccess, 'Password changed');
        } catch (err) {
            showLine(pwError, errMsg(err, "Couldn't change your password. Please try again."));
        } finally {
            done();
            pwCancelBtn.disabled = false;
        }
    });

    // ── 2. Notifications (shared UI from notifications.js) ──────

    const notifMount = $('notification-settings-mount');
    if (typeof mountNotificationSettings === 'function') {
        mountNotificationSettings(notifMount);
    }

    // ── 3. Budget: carry-over switch ────────────────────────────

    const carrySwitch = $('carry-switch');
    const budgetError = $('budget-settings-error');

    async function loadSettings() {
        try {
            const s = await apiGet('/users/me/settings');
            if (!s) return;
            setSwitch(carrySwitch, !!s.carry_over_budget);
            carrySwitch.disabled = false;
        } catch (err) {
            showLine(budgetError, "Couldn't load your budget settings. Please reload the page.");
        }
    }

    carrySwitch.addEventListener('click', async () => {
        const previous = carrySwitch.getAttribute('aria-checked') === 'true';
        const next = !previous;
        showLine(budgetError, '');
        setSwitch(carrySwitch, next); // optimistic
        carrySwitch.disabled = true;
        try {
            await apiPut('/users/me/settings', { carry_over_budget: next });
        } catch (err) {
            setSwitch(carrySwitch, previous); // revert
            showLine(budgetError, errMsg(err, "Couldn't save that change. Please try again."));
        } finally {
            carrySwitch.disabled = false;
        }
    });

    // ── 4. Your data: export ────────────────────────────────────
    // Same request/filename logic as history.js, with no filters (= everything).

    const exportBtns = Array.from(document.querySelectorAll('.export-btn'));
    const exportError = $('export-error');
    const exportStatus = $('export-status');

    async function exportAll(format, btn) {
        showLine(exportError, '');
        showLine(exportStatus, 'Preparing your file…');
        exportBtns.forEach((b) => { b.disabled = true; });
        const label = btn.lastElementChild;
        const originalLabel = label.textContent;
        label.textContent = '…';

        try {
            const response = await fetch(`${API_BASE}/export/${format}`, {
                headers: { 'Authorization': `Bearer ${getToken()}` }
            });

            if (response.status === 401) {
                clearToken();
                goToLogin();
                return;
            }
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(typeof errData.detail === 'string' ? errData.detail : 'Failed to export data');
            }

            let filename = `Expenses.${format === 'excel' ? 'xlsx' : format}`;
            const disposition = response.headers.get('Content-Disposition');
            if (disposition && disposition.indexOf('filename=') !== -1) {
                const matches = /filename="([^"]+)"/.exec(disposition);
                if (matches != null && matches[1]) filename = matches[1];
            }

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = downloadUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => {
                window.URL.revokeObjectURL(downloadUrl);
                a.remove();
            }, 1000);

            showLine(exportStatus, `Downloaded ${filename}`);
        } catch (err) {
            showLine(exportStatus, '');
            showLine(exportError, errMsg(err, "Couldn't export your data. Please try again."));
        } finally {
            label.textContent = originalLabel;
            exportBtns.forEach((b) => { b.disabled = false; });
        }
    }

    exportBtns.forEach((btn) => {
        btn.addEventListener('click', () => exportAll(btn.dataset.format, btn));
    });

    // ── 4. Your data: delete account ────────────────────────────

    const deleteOpenBtn = $('delete-open-btn');
    const deleteModal = $('delete-modal');
    const deleteModalContent = $('delete-modal-content');
    const deleteModalClose = $('delete-modal-close');
    const deleteForm = $('delete-form');
    const deletePassword = $('delete-password');
    const deleteError = $('delete-error');
    const deleteConfirmBtn = $('delete-confirm-btn');
    const deleteConfirmText = $('delete-confirm-text');
    const deleteCancelBtn = $('delete-cancel-btn');
    let deleting = false;

    function openDeleteModal() {
        deleteForm.reset();
        resetEyes(deleteForm);
        showLine(deleteError, '');
        deleteConfirmBtn.disabled = true;
        deleteModal.classList.remove('opacity-0', 'pointer-events-none');
        deleteModalContent.classList.remove('scale-95');
        deleteModalContent.classList.add('scale-100');
        setTimeout(() => deletePassword.focus(), 50);
    }

    function closeDeleteModal() {
        if (deleting) return;
        deleteModal.classList.add('opacity-0', 'pointer-events-none');
        deleteModalContent.classList.remove('scale-100');
        deleteModalContent.classList.add('scale-95');
    }

    deleteOpenBtn.addEventListener('click', openDeleteModal);
    deleteModalClose.addEventListener('click', closeDeleteModal);
    deleteCancelBtn.addEventListener('click', closeDeleteModal);
    deleteModal.addEventListener('click', (e) => {
        if (e.target === deleteModal) closeDeleteModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeDeleteModal();
    });

    deletePassword.addEventListener('input', () => {
        deleteConfirmBtn.disabled = deleting || deletePassword.value.length === 0;
    });

    // Best effort: drop this device's push subscription (the server rows are
    // already gone, so there is nothing to tell the server). Bounded to ~2s.
    async function dropLocalPushSubscription() {
        try {
            await Promise.race([
                (async () => {
                    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
                    const reg = await navigator.serviceWorker.getRegistration();
                    const sub = reg && reg.pushManager ? await reg.pushManager.getSubscription() : null;
                    if (sub) await sub.unsubscribe();
                })(),
                new Promise((resolve) => setTimeout(resolve, 2000))
            ]);
        } catch (e) { /* never block the redirect */ }
    }

    deleteForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const password = deletePassword.value;
        if (!password || deleting) return;

        showLine(deleteError, '');
        deleting = true;
        deleteConfirmBtn.disabled = true;
        deleteCancelBtn.disabled = true;
        deleteModalClose.disabled = true;
        deleteConfirmText.textContent = 'Deleting…';

        try {
            await apiPost('/users/me/delete', { password });
        } catch (err) {
            deleting = false;
            deleteCancelBtn.disabled = false;
            deleteModalClose.disabled = false;
            deleteConfirmText.textContent = 'Delete my account';
            deleteConfirmBtn.disabled = deletePassword.value.length === 0;
            showLine(deleteError, errMsg(err, "Couldn't delete your account. Please try again."));
            return;
        }

        // Account is gone: leave this device clean and go to login.
        await dropLocalPushSubscription();
        clearToken();
        window.location.href = 'login.html';
    });

    // ── 5. Help & about ─────────────────────────────────────────

    const replayTourBtn = $('replay-tour-btn');
    const tourError = $('tour-error');
    const logoutBtn = $('logout-btn');

    replayTourBtn.addEventListener('click', async () => {
        showLine(tourError, '');
        replayTourBtn.disabled = true;
        replayTourBtn.querySelector('p').textContent = 'Opening…';
        try {
            await apiPut('/users/me/settings', { onboarding_completed: false });
            window.location.href = 'welcome.html';
        } catch (err) {
            replayTourBtn.disabled = false;
            replayTourBtn.querySelector('p').textContent = 'Replay the welcome tour';
            showLine(tourError, errMsg(err, "Couldn't start the tour. Please try again."));
        }
    });

    logoutBtn.addEventListener('click', async () => {
        logoutBtn.disabled = true;
        await logout();
    });

    // ── Go ──────────────────────────────────────────────────────
    loadUser();
    loadSettings();
})();
