// ==== Orai Command Center — owner unlock / security / adminFetch module ====
// Auto-split from the former monolithic app.js (M6 Phase 4c, SRP).
// Loaded as an ordered classic <script>; shares one global scope with sibling
// modules (core.js, voice.js, admin.js, cockpit.js, panels.js, app.js).

function isCommandCenterUnlocked() {
    if (!COCKPIT_ADMIN_LOCK_ENABLED) return true;
    return !adminAuthRequired || adminSessionUnlocked;
}

function setHeardLine(text) {
    const gate = document.getElementById('neena-heard-line');
    const cockpit = document.getElementById('cockpit-heard-line');
    if (gate) gate.textContent = text;
    if (cockpit) cockpit.textContent = text;
}

/** Gate-visible chrome only (English). One status line — keep formal/clean. */
function setGateChrome(opts) {
    const o = opts || {};
    if (o.heard != null) {
        const heard = document.getElementById('neena-heard-line');
        if (heard) heard.textContent = o.heard;
    }
    if (o.reply != null) {
        const reply = document.getElementById('cc-gate-reply');
        if (reply) reply.textContent = o.reply;
    }
    if (o.state != null) {
        const state = document.getElementById('cc-gate-state-label');
        if (state) state.textContent = o.state;
    }
}

function syncPhraseGateUI(unlocked, required) {
    const body = document.body;
    const gate = document.getElementById('cc-phrase-gate');
    if (!body) return;
    document.documentElement.classList.remove('cc-session-pending');
    if (!required) {
        body.classList.remove('cc-locked');
        body.classList.add('cc-unlocked');
        try { sessionStorage.setItem('cc_unlocked_hint', '1'); } catch (e) { /* ignore */ }
        document.documentElement.classList.add('cc-unlock-hint');
        if (gate) gate.setAttribute('aria-hidden', 'true');
        return;
    }
    if (unlocked) {
        body.classList.remove('cc-locked');
        body.classList.add('cc-unlocked');
        try { sessionStorage.setItem('cc_unlocked_hint', '1'); } catch (e) { /* ignore */ }
        document.documentElement.classList.add('cc-unlock-hint');
        if (gate) gate.setAttribute('aria-hidden', 'true');
    } else {
        body.classList.add('cc-locked');
        body.classList.remove('cc-unlocked');
        try { sessionStorage.removeItem('cc_unlocked_hint'); } catch (e) { /* ignore */ }
        document.documentElement.classList.remove('cc-unlock-hint');
        if (gate) gate.setAttribute('aria-hidden', 'false');
    }
    if (!unlocked) {
        setGateChrome({
            state: 'Locked',
            heard: 'Tap the mic, or type below.',
            reply: '',
        });
        syncGateGuideMode('idle');
    }
}

async function ensureBrowserVoicesReady(timeoutMs) {
    if (!('speechSynthesis' in window)) return false;
    const deadline = Date.now() + (timeoutMs || 1500);
    let voices = window.speechSynthesis.getVoices();
    if (voices && voices.length) return true;
    return new Promise((resolve) => {
        const finish = (ok) => {
            try { window.speechSynthesis.onvoiceschanged = null; } catch (_) { /* ignore */ }
            resolve(!!ok);
        };
        window.speechSynthesis.onvoiceschanged = () => {
            voices = window.speechSynthesis.getVoices();
            if (voices && voices.length) finish(true);
        };
        const tick = () => {
            voices = window.speechSynthesis.getVoices();
            if (voices && voices.length) {
                finish(true);
                return;
            }
            if (Date.now() >= deadline) {
                finish(false);
                return;
            }
            setTimeout(tick, 100);
        };
        tick();
    });
}

async function speakOwnerMessage(text, options) {
    return speakWithBrowserFallback(text, Object.assign({ fastFail: true }, options || {}));
}

function notifyAdminLocked() {
    if (!COCKPIT_ADMIN_LOCK_ENABLED) return;
    setGateChrome({
        heard: 'Tap the mic, or type below.',
        reply: '',
        state: 'Locked',
    });
    appendCockpitTask('Command Center locked — tap mic to unlock', 'error');
    speakOwnerMessage('Sir, Command Center locked hai. Pehle owner unlock phrase boliye.', {
        priority: 'error',
        forceProvider: 'browser',
    });
    updateLockedCockpitUI();
}

function handleAdminUnauthorized(response) {
    if (!COCKPIT_ADMIN_LOCK_ENABLED) return false;
    if (response && response.status === 401) {
        adminSessionUnlocked = false;
        notifyAdminLocked();
        return true;
    }
    return false;
}

async function adminFetch(url, options) {
    const opts = Object.assign({ credentials: 'include' }, options || {});
    const response = await fetch(url, opts);
    handleAdminUnauthorized(response);
    return response;
}

async function adminFetchWithTimeout(url, options, timeoutMs) {
    const controller = new AbortController();
    const parentSignal = options && options.signal;
    if (parentSignal) {
        if (parentSignal.aborted) {
            controller.abort();
        } else {
            parentSignal.addEventListener('abort', () => controller.abort(), { once: true });
        }
    }
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs || LIVE_STATE_TIMEOUT_MS);
    try {
        return await adminFetch(url, Object.assign({}, options || {}, { signal: controller.signal }));
    } finally {
        clearTimeout(timeoutId);
    }
}

function updateLockedCockpitUI(sec) {
    const lockState = document.getElementById('cockpit-lock-state');
    const unlockedActions = document.getElementById('cockpit-unlocked-actions');
    const micLabel = document.getElementById('cockpit-mic-label');
    const gateMicLabel = document.getElementById('gate-mic-label');

    const required = adminAuthRequired || !!(sec && sec.auth_required);
    if (!required) {
        adminSessionUnlocked = true;
        if (lockState) lockState.classList.add('hidden');
        if (unlockedActions) unlockedActions.classList.add('hidden');
        setQuickActionsDisabled(false);
        if (micLabel) micLabel.textContent = 'Tap to Talk';
        if (gateMicLabel) gateMicLabel.textContent = 'Tap to say phrase';
        setHeardLine('Tap the mic and speak a command.');
        setNeenaState('online', 'Neena Online');
        syncPhraseGateUI(true, false);
        return;
    }

    const unlocked = adminSessionUnlocked || !!(sec && sec.session_unlocked);
    adminSessionUnlocked = unlocked;

    if (unlocked) {
        voiceRecognitionMode = 'command';
        if (lockState) lockState.classList.add('hidden');
        if (unlockedActions) unlockedActions.classList.remove('hidden');
        manualUnlockPanelOpen = false;
        setQuickActionsDisabled(false);
        if (micLabel) micLabel.textContent = 'Tap to Talk';
        if (gateMicLabel) gateMicLabel.textContent = 'Tap to say phrase';
        setHeardLine('Tap the mic and speak a command.');
        setNeenaState('online', 'Neena Online');
    } else {
        if (lockState) {
            lockState.classList.add('hidden');
            lockState.setAttribute('hidden', '');
            lockState.setAttribute('aria-hidden', 'true');
        }
        if (unlockedActions) unlockedActions.classList.add('hidden');
        setQuickActionsDisabled(true);
        if (micLabel) micLabel.textContent = 'Tap to Unlock';
        if (gateMicLabel) gateMicLabel.textContent = 'Tap to say phrase';
        setHeardLine('Tap the mic, or type below.');
        setNeenaState('error', 'Neena Locked');
    }
    syncPhraseGateUI(unlocked, true);
}

async function fetchAdminSecurityStatus() {
    if (!COCKPIT_ADMIN_LOCK_ENABLED) {
        adminAuthRequired = false;
        adminSessionUnlocked = true;
        syncPhraseGateUI(true, false);
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/neena/security-status`, { cache: 'no-store', credentials: 'include' });
        if (!res.ok) return;
        const data = await res.json();
        const sec = data.security || {};
        adminAuthRequired = !!sec.auth_required;
        adminSessionUnlocked = !!sec.session_unlocked;
        updateLockedCockpitUI(sec);
    } catch (e) {
        /* non-blocking */
    }
}

function setVoiceRecognitionLang(mode) {
    if (!voiceRecognition) return;
    voiceRecognition.lang = mode === 'unlock' ? VOICE_UNLOCK_LANG : VOICE_COMMAND_LANG;
    voiceRecognition.maxAlternatives = mode === 'unlock' ? 3 : 1;
}

async function submitUnlockPhrase(phrase, options) {
    const opts = options || {};
    const quietFail = !!opts.quietFail;
    const trimmed = (phrase || '').trim();
    if (!trimmed) {
        appendCockpitTask('Owner unlock phrase enter kariye', 'error');
        return false;
    }
    try {
        const res = await fetch(`${API_BASE}/admin/unlock`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phrase: trimmed }),
        });
        if (!res.ok) {
            try {
                const secRes = await fetch(`${API_BASE}/neena/security-status`, { cache: 'no-store', credentials: 'include' });
                if (secRes.ok) {
                    const secData = await secRes.json();
                    const sec = secData.security || {};
                    if (sec.session_unlocked) {
                        adminSessionUnlocked = true;
                        voiceRecognitionMode = 'command';
                        updateLockedCockpitUI(sec);
                        runVoiceCommand(trimmed);
                        return true;
                    }
                }
            } catch (e) {
                /* fall through to unlock rejection */
            }
            if (!quietFail) {
                appendCockpitTask('Unlock phrase rejected', 'error');
                setGateChrome({
                    heard: 'Phrase did not match. Try again.',
                    reply: '',
                    state: 'Try again',
                });
                await speakOwnerMessage('Phrase match nahi hua sir, dobara boliye.', {
                    priority: 'error',
                    forceProvider: 'browser',
                });
                setNeenaState('error', 'Neena Locked');
            }
            return false;
        }
        adminSessionUnlocked = true;
        voiceRecognitionMode = 'command';
        manualUnlockPanelOpen = false;
        const input = document.getElementById('cockpit-unlock-phrase-input');
        if (input) input.value = '';
        updateLockedCockpitUI({ auth_required: true, session_unlocked: true });
        appendCockpitTask('Command Center unlocked', 'success');
        setGateChrome({
            heard: 'Unlocked.',
            reply: '',
            state: 'Unlocked',
        });
        await speakOwnerMessage('Welcome sir, Command Center unlock ho gaya. Batayiye kya karna hai.', {
            priority: 'final',
            forceProvider: 'browser',
        });
        return true;
    } catch (e) {
        appendCockpitTask('Unlock request failed', 'error');
        return false;
    }
}

function unlockCommandCenter() {
    const input = document.getElementById('cockpit-unlock-phrase-input');
    submitUnlockPhrase(input && input.value ? input.value : '');
}

async function lockCommandCenter() {
    try {
        await fetch(`${API_BASE}/admin/lock`, { method: 'POST', credentials: 'include' });
    } catch (e) {
        /* best effort */
    }
    adminSessionUnlocked = false;
    manualUnlockPanelOpen = false;
    try { window.speechSynthesis.cancel(); } catch(e){}
    if (voiceRecognition && voiceListening) {
        try { voiceRecognition.stop(); } catch(e){}
    }
    updateLockedCockpitUI({ auth_required: true, session_unlocked: false });
    appendCockpitTask('Command Center locked', 'info');
    setGateChrome({
        reply: 'Command Center locked.',
        heard: 'Tap the mic, or type below.',
        state: 'Locked',
    });
    transitionToState('LOCKED');
}

function toggleManualUnlockPanel(forceOpen) {
    /* Gate shows phrase form always; legacy toggle kept for compatibility. */
    if (forceOpen === true) manualUnlockPanelOpen = true;
    else if (forceOpen === false) manualUnlockPanelOpen = false;
    else manualUnlockPanelOpen = !manualUnlockPanelOpen;
}

async function handleUnlockPhraseHeard(transcriptOrEvent) {
    if (isCommandCenterUnlocked()) {
        voiceRecognitionMode = 'command';
        const single = typeof transcriptOrEvent === 'string'
            ? transcriptOrEvent
            : (transcriptOrEvent.results[0][0].transcript || '').trim();
        runVoiceCommand(single);
        return;
    }
    const transcripts = [];
    if (typeof transcriptOrEvent === 'string') {
        transcripts.push(transcriptOrEvent.trim());
    } else {
        const result = transcriptOrEvent.results[0];
        for (let i = 0; i < result.length; i++) {
            const t = (result[i].transcript || '').trim();
            if (t) transcripts.push(t);
        }
    }
    if (!transcripts.length) return;
    setHeardLine(`Heard: ${transcripts[0]}`);
    appendCockpitTask('Unlock phrase heard — verifying…', 'info');
    for (let i = 0; i < transcripts.length; i++) {
        const ok = await submitUnlockPhrase(transcripts[i], { quietFail: i < transcripts.length - 1 });
        if (ok) return;
    }
}

async function startUnlockListening() {
    if (isCommandCenterUnlocked()) {
        voiceRecognitionMode = 'command';
        toggleVoiceListening();
        return;
    }
    voiceOwnerGestureUnlocked = true;
    voiceRecognitionMode = 'unlock';
    setVoiceRecognitionLang('unlock');
    setGateChrome({
        heard: 'Listening…',
        reply: '',
        state: 'Listening',
    });
    appendCockpitTask('Listening for owner unlock phrase…', 'info');
    await ensureBrowserVoicesReady(2000);
    await speakOwnerMessage('Sir, Command Center locked hai. Pehle owner unlock phrase boliye.', {
        priority: 'error',
        forceProvider: 'browser',
    });
    setNeenaState('listening', 'Listening for unlock phrase…');

    if (!voiceRecognition) {
        initVoiceRecognition();
    }
    if (!voiceRecognition) {
        setGateChrome({ heard: 'Mic unavailable — type below.', reply: '', state: 'Locked' });
        appendCockpitTask('Speech recognition unavailable — type owner phrase', 'info');
        return;
    }
    if (voiceListening) {
        try { voiceRecognition.stop(); } catch (e) {}
        return;
    }
    try {
        voiceRecognition.start();
    } catch (e) {
        setGateChrome({ heard: 'Mic failed — type below.', reply: '', state: 'Locked' });
        appendCockpitTask('Mic start failed — type owner phrase', 'error');
    }
}

function updateCcLiveClock() {
    const el = document.getElementById('cc-live-clock');
    if (!el) return;
    const now = new Date();
    el.dateTime = now.toISOString();
    el.textContent = now.toLocaleString('en-IN', {
        weekday: 'short',
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
    });
}

if (typeof window !== 'undefined') {
    updateCcLiveClock();
    setInterval(updateCcLiveClock, 1000);
}
