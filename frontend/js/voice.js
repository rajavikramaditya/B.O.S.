// ==== Orai Command Center — voice engine / TTS / voice state machine module ====
// Auto-split from the former monolithic app.js (M6 Phase 4c, SRP).
// Loaded as an ordered classic <script>; shares one global scope with sibling
// modules (core.js, voice.js, admin.js, cockpit.js, panels.js, app.js).

function getSpeakCheckboxElements() {
    return [
        document.getElementById('enable-voice-synthesis-main'),
        document.getElementById('enable-voice-synthesis'),
    ].filter(Boolean);
}

function isSpeakResponsesEnabled() {
    const boxes = getSpeakCheckboxElements();
    const saved = sessionStorage.getItem(SPEAK_PREF_KEY);
    if (boxes.length) {
        return boxes.some(el => el.checked);
    }
    if (saved === null) return true;
    return saved === '1';
}

function syncSpeakCheckboxes(checked) {
    getSpeakCheckboxElements().forEach(el => {
        el.checked = checked;
    });
    sessionStorage.setItem(SPEAK_PREF_KEY, checked ? '1' : '0');
    updateVoiceStatusBadge();
}

function setVoiceStatusBadge(state, detail) {
    voiceStatusState = state || 'idle';
    updateVoiceStatusBadge();
}

const STATE_CONFIGS = {
    LOCKED: { label: 'Neena Locked', cls: 'error', micLabel: 'Tap to Unlock' },
    IDLE: { label: 'Neena Online', cls: 'online', micLabel: 'Tap to Talk' },
    LISTENING: { label: 'Listening…', cls: 'listening', micLabel: 'Tap to stop' },
    PROCESSING: { label: 'Thinking…', cls: 'thinking', micLabel: 'Cancel' },
    SPEAKING: { label: 'Neena speaking…', cls: 'broadcasting', micLabel: 'Tap to interrupt' },
    WAITING_FOR_FOLLOWUP: { label: 'Aap jawab bol sakte hain…', cls: 'listening', micLabel: 'Tap to stop' },
    ERROR: { label: 'Error', cls: 'error', micLabel: 'Tap to Talk' }
};

// Rule 8: explicit state machine — declare the legal transitions so illegal
// ones are surfaced (logged) instead of silently corrupting voice state. This
// is a diagnostic guard: it warns but does not block, so runtime behavior is
// unchanged while making voice-state bugs visible in the console/trace.
const ALLOWED_TRANSITIONS = {
    LOCKED: ['LOCKED', 'IDLE'],
    IDLE: ['IDLE', 'LOCKED', 'LISTENING', 'PROCESSING', 'SPEAKING', 'ERROR'],
    LISTENING: ['LISTENING', 'IDLE', 'LOCKED', 'PROCESSING', 'SPEAKING', 'ERROR'],
    PROCESSING: ['PROCESSING', 'IDLE', 'LOCKED', 'SPEAKING', 'WAITING_FOR_FOLLOWUP', 'ERROR'],
    SPEAKING: ['SPEAKING', 'IDLE', 'LOCKED', 'LISTENING', 'WAITING_FOR_FOLLOWUP', 'ERROR'],
    WAITING_FOR_FOLLOWUP: ['WAITING_FOR_FOLLOWUP', 'IDLE', 'LOCKED', 'LISTENING', 'PROCESSING', 'SPEAKING', 'ERROR'],
    ERROR: ['ERROR', 'IDLE', 'LOCKED', 'LISTENING'],
};

function transitionToState(newState, customLabel = null) {
    if (!isCommandCenterUnlocked() && newState !== 'LOCKED') {
        newState = 'LOCKED';
    }

    // Diagnostic guard (non-blocking): flag unexpected transitions.
    const legal = ALLOWED_TRANSITIONS[currentState];
    if (legal && !legal.includes(newState)) {
        console.warn(`[VoiceState] Unexpected transition ${currentState} -> ${newState}`);
    }

    if (currentState === 'WAITING_FOR_FOLLOWUP' && newState !== 'WAITING_FOR_FOLLOWUP') {
        if (followUpTimeoutId) {
            clearTimeout(followUpTimeoutId);
            followUpTimeoutId = null;
        }
    }

    currentState = newState;
    const cfg = STATE_CONFIGS[newState] || STATE_CONFIGS.IDLE;
    const label = customLabel || cfg.label;

    let neenaCls = 'online';
    if (cfg.cls === 'error') neenaCls = 'error';
    else if (cfg.cls === 'listening') neenaCls = 'listening';
    else if (cfg.cls === 'thinking') neenaCls = 'thinking';
    else if (cfg.cls === 'broadcasting') neenaCls = 'broadcasting';

    setNeenaState(neenaCls, label);

    const micBtn = document.getElementById('cockpit-mic-btn');
    const micLabel = document.getElementById('cockpit-mic-label');
    const gateMic = document.getElementById('gate-mic-btn');
    if (micLabel) micLabel.textContent = cfg.micLabel;

    if (micBtn) {
        if (newState === 'LISTENING' || newState === 'WAITING_FOR_FOLLOWUP') {
            micBtn.classList.add('listening');
        } else {
            micBtn.classList.remove('listening');
        }
    }
    if (gateMic) {
        if (newState === 'LISTENING' || newState === 'WAITING_FOR_FOLLOWUP') {
            gateMic.classList.add('listening');
        } else {
            gateMic.classList.remove('listening');
        }
    }

    // Mutual exclusion:
    if (newState === 'LISTENING' || newState === 'WAITING_FOR_FOLLOWUP') {
        if (window.speechSynthesis && window.speechSynthesis.speaking) {
            try { window.speechSynthesis.cancel(); } catch (e) {}
            voiceSpeaking = false;
        }
        if (currentCockpitAudio) {
            try { currentCockpitAudio.pause(); } catch (e) {}
        }
    }

    if (newState === 'SPEAKING' || newState === 'PROCESSING') {
        if (voiceRecognition && voiceListening) {
            try { voiceRecognition.stop(); } catch (e) {}
            voiceListening = false;
        }
    }

    updateVoiceStatusBadge();
}

function updateVoiceStatusBadge() {
    const badge = document.getElementById('voice-status-badge');
    if (!badge) return;

    if (!window.speechSynthesis) {
        badge.textContent = 'Voice: unsupported';
        badge.className = 'voice-status-badge voice-status-unavailable';
        return;
    }

    if (!isSpeakResponsesEnabled()) {
        badge.textContent = 'Voice: muted';
        badge.className = 'voice-status-badge voice-status-blocked';
        return;
    }

    if (voiceSpeaking || currentState === 'SPEAKING') {
        badge.textContent = 'Voice: speaking';
        badge.className = 'voice-status-badge voice-status-speaking';
        return;
    }

    badge.textContent = 'Voice: ready';
    badge.className = 'voice-status-badge voice-status-ready';
}

function isFollowUpListenEnabled() {
    const el = document.getElementById('setting-follow-up-listen');
    if (el) return el.checked;
    return true;
}

function shouldTriggerFollowUp(text) {
    if (!isFollowUpListenEnabled()) return false;
    const cleanText = (text || '').trim().toLowerCase();
    if (cleanText.includes('?') || cleanText.includes('कया') || cleanText.includes('क्या')) {
        return true;
    }
    const questionPatterns = [
        'kya main bhej doon',
        'kya main bhej',
        'bheju',
        'karna chahenge',
        'kya karun',
        'bataiye sir',
        'bataiye',
        'karo ya nahi',
        'approve kar doon',
        'confirm karein',
        'sure ho',
        'sure hain',
        'boliye',
        'kya haal'
    ];
    return questionPatterns.some(p => cleanText.includes(p));
}

function checkAndStartFollowUpListening(spokenText) {
    if (shouldTriggerFollowUp(spokenText)) {
        transitionToState('WAITING_FOR_FOLLOWUP');
        try {
            if (voiceRecognition) voiceRecognition.start();
        } catch (e) { /* ignore */ }

        if (followUpTimeoutId) clearTimeout(followUpTimeoutId);
        followUpTimeoutId = setTimeout(() => {
            if (currentState === 'WAITING_FOR_FOLLOWUP') {
                try { if (voiceRecognition) voiceRecognition.stop(); } catch (e) {}
                transitionToState('IDLE');
            }
        }, 10000);
    } else {
        transitionToState('IDLE');
    }
}

function syncVoiceModeSelector(mode) {
    const sel = document.getElementById('voice-provider-select');
    if (sel && sel.value !== mode) sel.value = mode;
    voiceProviderMode = mode || 'auto';
    sessionStorage.setItem(VOICE_MODE_KEY, voiceProviderMode);
}

function setVoiceProviderMode(mode) {
    syncVoiceModeSelector(mode || 'auto');
    appendCockpitTask(`Voice provider: ${voiceProviderMode}`, 'info');
    refreshVoiceEngineStatus();
}

function shouldAutoSwitchToBackend(error) {
    const err = String(error || '').toLowerCase();
    return BROWSER_FAIL_AUTO_BACKEND_ERRORS.some(token => err.includes(token));
}

function noteBrowserFailureForAuto(error) {
    voiceLastBrowserError = error || 'browser speech failed';
    voiceBrowserKnownFailed = true;
    lastBrowserVoiceHealthy = false;
    setVoiceStatusBadge('browser_failed', voiceLastBrowserError);
    if (voiceProviderMode === 'auto' && shouldAutoSwitchToBackend(error)) {
        syncVoiceModeSelector('backend');
        appendCockpitTask(`Browser voice failed: ${voiceLastBrowserError} — switched to Backend`, 'info');
    }
}

function getEffectiveVoiceProvider() {
    if (voiceProviderMode === 'backend') return 'backend';
    if (voiceProviderMode === 'browser') return 'browser';
    return 'browser';
}

function absoluteCockpitAudioUrl(audioUrl) {
    if (!audioUrl) return '';
    if (audioUrl.startsWith('http')) return audioUrl;
    return window.location.origin + audioUrl;
}

function hideManualVoicePlayer() {
    const container = document.getElementById('cockpit-manual-voice-player');
    if (container) {
        container.classList.add('hidden');
        container.innerHTML = '';
    }
}

function showManualVoicePlayer(audioUrl, message) {
    const container = document.getElementById('cockpit-manual-voice-player');
    if (!container || !audioUrl) return null;
    const url = absoluteCockpitAudioUrl(audioUrl);
    currentCockpitAudioUrl = url;
    container.classList.remove('hidden');
    let audio = currentCockpitAudio;
    if (!audio || audio.parentElement !== container) {
        container.innerHTML = '';
        const p = document.createElement('p');
        p.className = 'manual-voice-hint';
        p.textContent = message || 'Backend voice ready — tap Play Voice.';
        container.appendChild(p);
        audio = document.createElement('audio');
        audio.controls = true;
        audio.preload = 'auto';
        audio.volume = 1.0;
        container.appendChild(audio);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-secondary btn-sm btn-play-voice';
        btn.textContent = 'Play Voice';
        btn.onclick = () => {
            voiceOwnerGestureUnlocked = true;
            audio.play().catch(() => {});
        };
        container.appendChild(btn);
        currentCockpitAudio = audio;
    } else {
        const hint = container.querySelector('.manual-voice-hint');
        if (hint && message) hint.textContent = message;
    }
    audio.src = url;
    return audio;
}

function showVoiceFailureTextOnly(detail) {
    const msg = detail || 'Voice unavailable — text replies active.';
    voiceLastBackendError = msg;
    if ('speechSynthesis' in window && voiceOwnerGestureUnlocked) {
        setVoiceStatusBadge('browser_fallback');
        const banner = document.getElementById('voice-fail-banner');
        if (banner) banner.classList.add('hidden');
        return;
    }
    setVoiceStatusBadge('browser_fallback');
    const banner = document.getElementById('voice-fail-banner');
    if (banner) banner.classList.add('hidden');
}

function showVoiceUnavailableWarning(detail) {
    showVoiceFailureTextOnly(detail);
}

function refreshVoiceEngineStatus() {
    if (['testing', 'backend_testing', 'ready_browser', 'ready_backend', 'browser_ready', 'backend_ready', 'browser_failed', 'backend_failed', 'speaking'].includes(voiceStatusState)) {
        return;
    }
    if (voiceProviderMode === 'backend') {
        setVoiceStatusBadge('idle', 'Backend/Edge mode selected');
        return;
    }
    if (!('speechSynthesis' in window)) {
        speechSynthAvailable = false;
        setVoiceStatusBadge('unavailable', 'speechSynthesis not supported — use Backend');
        return;
    }
    speechSynthAvailable = true;
    const voices = window.speechSynthesis.getVoices();
    if (voiceProviderMode === 'browser' && !voiceOwnerGestureUnlocked) {
        setVoiceStatusBadge('blocked', 'Click Test Voice once to unlock browser speech');
    } else if (voiceProviderMode === 'browser' && !voices.length) {
        setVoiceStatusBadge('no_voices', 'Waiting for voices — click Test Voice');
    } else if (voiceSpeaking) {
        setVoiceStatusBadge('speaking');
    } else {
        setVoiceStatusBadge('idle');
    }
}

function speakBrowserAsync(text, options) {
    const opts = Object.assign({ fastProbe: false }, options || {});
    const probeMs = opts.fastProbe ? AUTO_BROWSER_PROBE_MS : BROWSER_SPEECH_FULL_TIMEOUT_MS;
    try { window.speechSynthesis.cancel(); } catch(e){}
    return new Promise(resolve => {
        let settled = false;
        let hadError = false;
        let started = false;
        let probeTimer = null;
        let fullTimer = null;
        const finish = (payload) => {
            if (settled) return;
            settled = true;
            if (probeTimer) clearTimeout(probeTimer);
            if (fullTimer) clearTimeout(fullTimer);
            resolve(payload);
        };
        if (!speechSynthAvailable || !('speechSynthesis' in window)) {
            finish({ started: false, completed: false, error: 'speechSynthesis unavailable', provider: 'browser' });
            return;
        }
        const cleanText = (text || '').replace(/\*.*?\*/g, '').replace(/\[SCRIPT_OUTPUT\][\s\S]*?\[\/SCRIPT_OUTPUT\]/g, '').trim();
        if (!cleanText) {
            finish({ started: false, completed: false, error: 'empty speech text', provider: 'browser' });
            return;
        }
        if (!voiceOwnerGestureUnlocked) {
            finish({ started: false, completed: false, error: 'blocked by browser — user gesture required', provider: 'browser' });
            return;
        }
        const utterance = new SpeechSynthesisUtterance(cleanText);
        const voices = window.speechSynthesis.getVoices();
        if (!voices.length) {
            finish({ started: false, completed: false, error: 'no voices loaded', provider: 'browser' });
            return;
        }
        const selectedVoice = voices.find(v => v.lang.includes('hi') || v.lang.includes('IN') || v.name.toLowerCase().includes('female'))
            || voices.find(v => v.lang.startsWith('en'))
            || voices[0];
        if (selectedVoice) utterance.voice = selectedVoice;
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;
        utterance.onstart = () => {
            started = true;
            voiceSpeaking = true;
            transitionToState('SPEAKING');
            if (probeTimer) {
                clearTimeout(probeTimer);
                probeTimer = null;
            }
            if (!fullTimer) {
                fullTimer = setTimeout(() => {
                    if (!settled) {
                        hadError = true;
                        try { window.speechSynthesis.cancel(); } catch (_) { /* ignore */ }
                        finish({ started: false, completed: false, error: 'speech timeout', provider: 'browser' });
                    }
                }, BROWSER_SPEECH_FULL_TIMEOUT_MS);
            }
        };
        utterance.onend = () => {
            voiceSpeaking = false;
            if (!hadError) {
                lastBrowserVoiceHealthy = true;
                checkAndStartFollowUpListening(cleanText);
                finish({ started: true, completed: true, error: null, provider: 'browser' });
            }
        };
        utterance.onerror = (ev) => {
            voiceSpeaking = false;
            hadError = true;
            const err = (ev && ev.error) ? String(ev.error) : 'speech error';
            voiceLastBrowserError = err;
            if (currentState === 'SPEAKING') {
                transitionToState('IDLE');
            }
            finish({ started: false, completed: false, error: err, provider: 'browser' });
        };
        try {
            window.speechSynthesis.speak(utterance);
            probeTimer = setTimeout(() => {
                if (!started && !settled) {
                    hadError = true;
                    try { window.speechSynthesis.cancel(); } catch (_) { /* ignore */ }
                    finish({ started: false, completed: false, error: 'speech timeout', provider: 'browser' });
                }
            }, probeMs);
            if (!opts.fastProbe) {
                fullTimer = setTimeout(() => {
                    if (!settled) {
                        hadError = true;
                        try { window.speechSynthesis.cancel(); } catch (_) { /* ignore */ }
                        finish({ started: false, completed: false, error: 'speech timeout', provider: 'browser' });
                    }
                }, BROWSER_SPEECH_FULL_TIMEOUT_MS);
            }
        } catch (err) {
            finish({ started: false, completed: false, error: err.message || 'speech exception', provider: 'browser' });
        }
    });
}

function speakTextLocallyAsync(text) {
    return speakBrowserAsync(text, { fastProbe: false });
}

function speakTextLocally(text) {
    speakTextLocallyAsync(text);
}

function playAudioElementAsync(audio, audioUrl) {
    return new Promise(resolve => {
        if (!audio) {
            resolve({ started: false, completed: false, error: 'no audio element', provider: 'backend', needsManual: true, manualUrl: audioUrl });
            return;
        }
        currentCockpitAudio = audio;
        audio.volume = 1.0;
        let settled = false;
        let played = false;
        const finish = (payload) => {
            if (settled) return;
            settled = true;
            resolve(payload);
        };
        audio.onplay = () => {
            played = true;
            voiceOwnerGestureUnlocked = true;
            voiceSpeaking = true;
            setVoiceStatusBadge('speaking');
        };
        audio.onended = () => {
            voiceSpeaking = false;
            finish({ started: true, completed: true, played: true, error: null, provider: 'backend', manualUrl: audioUrl });
        };
        audio.onerror = () => {
            voiceSpeaking = false;
            showVoiceFailureTextOnly('backend audio playback failed');
            showManualVoicePlayer(audioUrl, 'Backend voice audio blocked. Click Play Voice.');
            finish({
                started: false,
                completed: false,
                played: false,
                error: voiceLastBackendError,
                provider: 'backend',
                needsManual: true,
                manualUrl: audioUrl,
            });
        };
        audio.play().then(() => {
            played = true;
        }).catch(playErr => {
            voiceSpeaking = false;
            showVoiceFailureTextOnly(playErr.message || 'audio play blocked');
            showManualVoicePlayer(audioUrl, 'Backend voice audio blocked. Click Play Voice.');
            finish({
                started: false,
                completed: false,
                played: false,
                error: voiceLastBackendError,
                provider: 'backend',
                needsManual: true,
                manualUrl: audioUrl,
            });
        });
        setTimeout(() => {
            if (!settled && !played) {
                showManualVoicePlayer(audioUrl, 'Backend voice audio blocked. Click Play Voice.');
                finish({
                    started: false,
                    completed: false,
                    played: false,
                    error: 'autoplay not confirmed — use Play Voice',
                    provider: 'backend',
                    needsManual: true,
                    manualUrl: audioUrl,
                });
            }
        }, 2500);
    });
}

function shouldReducePollingLoad() {
    return isBackendOffline || voiceJobRunning || lastKnownCpu > 85 || lastKnownRam > 85;
}

function updatePollingLoadMode(stats) {
    if (stats) {
        if (typeof stats.cpu === 'number') lastKnownCpu = stats.cpu;
        if (typeof stats.ram === 'number') lastKnownRam = stats.ram;
    }
    const reduce = shouldReducePollingLoad();
    if (reduce === pollingReduced) return;
    pollingReduced = reduce;
}

function maybeClearLiveStateStale() {
    if (!liveStateStale) return;
    liveStateStale = false;
    const label = document.getElementById('neena-state-label');
    if (label && (label.textContent || '').includes('Live state stale')) {
        setNeenaState('online', 'Neena Online');
    }
}

function voiceDedupeAllows(key) {
    if (!key) return true;
    const last = voiceDedupeMap[key] || 0;
    if (Date.now() - last < VOICE_DEDUPE_MS) return false;
    voiceDedupeMap[key] = Date.now();
    return true;
}

function enqueueVoiceItem(item) {
    const prioRank = { test_voice: 0, error: 1, timeout: 1, final: 2, progress: 5 };
    const rank = prioRank[item.priority] ?? 5;
    if (rank >= prioRank.progress) {
        voiceQueue = voiceQueue.filter(q => (prioRank[q.priority] ?? 5) < prioRank.progress).concat([item]);
    } else {
        voiceQueue = voiceQueue.filter(q => q.priority !== 'progress').concat([item]);
    }
    drainVoiceQueue();
}

function drainVoiceQueue() {
    if (voiceActiveBackendJobId || voiceJobRunning) return;
    const next = voiceQueue.shift();
    if (!next) return;
    runVoiceQueueItem(next);
}

async function pollBackendVoiceJob(jobId, callbacks) {
    const deadline = Date.now() + VOICE_JOB_POLL_MAX_MS;
    voiceActiveBackendJobId = jobId;
    voiceJobRunning = true;
    setVoiceStatusBadge('backend_testing', 'Backend voice generating…');
    while (Date.now() < deadline) {
        try {
            const res = await fetch(`${API_BASE}/neena/cockpit-voice/jobs/${jobId}`, { cache: 'no-store' });
            const job = await res.json().catch(() => ({}));
            if (job.status === 'succeeded' && job.audio_url) {
                voiceActiveBackendJobId = null;
                voiceJobRunning = false;
                updatePollingLoadMode(null);
                await deliverBackendAudio(job.audio_url, callbacks);
                drainVoiceQueue();
                return { completed: true, provider: 'backend', job };
            }
            if (job.status === 'failed' || job.status === 'dropped') {
                voiceActiveBackendJobId = null;
                voiceJobRunning = false;
                updatePollingLoadMode(null);
                const err = job.error_summary || 'backend voice job failed';
                if (callbacks && callbacks.onFail) callbacks.onFail(err);
                else showVoiceFailureTextOnly(err);
                drainVoiceQueue();
                return { completed: false, error: err, provider: 'backend' };
            }
        } catch (_) { /* retry poll */ }
        await sleepMs(VOICE_JOB_POLL_MS);
    }
    voiceActiveBackendJobId = null;
    voiceJobRunning = false;
    updatePollingLoadMode(null);
    const err = 'backend voice job timeout';
    if (callbacks && callbacks.onFail) callbacks.onFail(err);
    else showVoiceFailureTextOnly(err);
    drainVoiceQueue();
    return { completed: false, error: err, provider: 'backend' };
}

async function deliverBackendAudio(audioUrl, callbacks) {
    const audioUrlRel = audioUrl;
    const fullUrl = absoluteCockpitAudioUrl(audioUrlRel);
    currentCockpitAudioUrl = fullUrl;
    const manualAudio = showManualVoicePlayer(audioUrlRel, 'Backend voice ready — tap Play Voice.');
    const audio = manualAudio || new Audio(fullUrl);
    if (!manualAudio) {
        audio.preload = 'auto';
        audio.src = fullUrl;
        currentCockpitAudio = audio;
    }
    const playRes = await playAudioElementAsync(audio, fullUrl);
    if (playRes.completed && playRes.played) {
        setVoiceStatusBadge('ready_backend');
        if (callbacks && callbacks.onReady) callbacks.onReady(playRes);
        return playRes;
    }
    if (playRes.needsManual) {
        setVoiceStatusBadge('backend_ready', 'Click Play Voice');
        if (callbacks && callbacks.onManual) callbacks.onManual(playRes);
        return Object.assign({}, playRes, { manualReady: true });
    }
    showVoiceFailureTextOnly(playRes.error || 'backend playback failed');
    if (callbacks && callbacks.onFail) callbacks.onFail(playRes.error);
    return playRes;
}

async function startBackendVoiceJob(text, options) {
    const opts = Object.assign({ priority: 'progress', dedupeKey: null, callbacks: null, fastFail: false }, options || {});
    const cleanText = (text || '').trim();
    if (!cleanText) return { completed: false, error: 'empty speech text' };
    if (opts.dedupeKey && !voiceDedupeAllows(opts.dedupeKey)) {
        return { completed: false, skipped: true, reason: 'dedupe' };
    }
    voiceJobRunning = true;
    updatePollingLoadMode(null);
    const postTimeoutMs = opts.fastFail ? VOICE_BACKEND_FAST_FAIL_MS : VOICE_SPEAK_POST_TIMEOUT_MS;
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), postTimeoutMs);
        let response;
        try {
            response = await adminFetch(`${API_BASE}/neena/cockpit-voice/speak`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: cleanText,
                    voice: 'default',
                    purpose: 'owner_cockpit',
                    priority: opts.priority || 'progress',
                }),
                signal: controller.signal,
            });
        } finally {
            clearTimeout(timeoutId);
        }
        const data = await response.json().catch(() => ({}));
        if (!data.ok) {
            voiceJobRunning = false;
            updatePollingLoadMode(null);
            const reason = data.reason || data.message || 'backend voice unavailable';
            return { completed: false, error: reason };
        }
        if (data.mode === 'cached' || data.status === 'succeeded') {
            if (data.audio_url) {
                voiceJobRunning = false;
                return deliverBackendAudio(data.audio_url, opts.callbacks);
            }
        }
        if (data.voice_job_id) {
            if (opts.fastFail) {
                voiceJobRunning = false;
                updatePollingLoadMode(null);
                return { completed: false, error: 'backend voice slow — browser fallback' };
            }
            return pollBackendVoiceJob(data.voice_job_id, opts.callbacks);
        }
        voiceJobRunning = false;
        return { completed: false, error: 'no voice job id' };
    } catch (e) {
        voiceJobRunning = false;
        updatePollingLoadMode(null);
        const err = (e && e.name === 'AbortError') ? 'backend voice queue timeout' : (e.message || 'backend request failed');
        return { completed: false, error: err };
    }
}

async function speakWithBrowserFallback(text, options) {
    const opts = Object.assign({ priority: 'progress', dedupeKey: null, fastFail: true }, options || {});
    const clean = shortReplyForVoice(text);
    if (!clean) return { completed: false, error: 'empty speech text' };
    voiceOwnerGestureUnlocked = true;
    if ('speechSynthesis' in window) {
        window.speechSynthesis.getVoices();
        if (typeof ensureBrowserVoicesReady === 'function') {
            await ensureBrowserVoicesReady(1500);
        }
    }

    const effective = opts.forceProvider || getEffectiveVoiceProvider();
    if (effective !== 'browser') {
        const backendRes = await startBackendVoiceJob(clean, {
            priority: opts.priority,
            dedupeKey: opts.dedupeKey,
            fastFail: opts.fastFail !== false,
        });
        if (backendRes.completed || backendRes.played || backendRes.manualReady) {
            return backendRes;
        }
    }

    const browserRes = await speakBrowserAsync(clean, { fastProbe: false });
    if (browserRes.completed) {
        setVoiceStatusBadge('browser_fallback');
        return browserRes;
    }
    setVoiceStatusBadge('browser_fallback');
    return browserRes;
}

function queueNeenaVoice(text, options) {
    const opts = Object.assign({
        priority: 'progress',
        dedupeKey: null,
        forceProvider: null,
        callbacks: null,
        isFailureNotice: false,
    }, options || {});
    if (opts.isFailureNotice) return null;
    const clean = shortReplyForVoice(text);
    if (!clean) return null;
    const effective = opts.forceProvider || getEffectiveVoiceProvider();
    if (effective === 'browser') {
        speakBrowserAsync(clean, { fastProbe: false }).then(res => {
            if (res.completed) setVoiceStatusBadge('ready_browser');
            else showVoiceFailureTextOnly(res.error || 'browser speech failed');
        });
        return { queued: true, provider: 'browser' };
    }
    if (effective === 'auto') {
        speakBrowserAsync(clean, { fastProbe: true }).then(res => {
            if (res.completed) {
                setVoiceStatusBadge('ready_browser');
                return;
            }
            noteBrowserFailureForAuto(res.error);
            enqueueVoiceItem({ text: clean, priority: opts.priority, dedupeKey: opts.dedupeKey, callbacks: opts.callbacks });
        });
        return { queued: true, provider: 'auto' };
    }
    enqueueVoiceItem({
        text: clean,
        priority: opts.priority,
        dedupeKey: opts.dedupeKey,
        callbacks: opts.callbacks,
    });
    return { queued: true, provider: 'backend' };
}

async function runVoiceQueueItem(item) {
    const res = await startBackendVoiceJob(item.text, {
        priority: item.priority,
        dedupeKey: item.dedupeKey,
        callbacks: item.callbacks,
        fastFail: true,
    });
    if (res.completed || res.played || res.manualReady) return res;
    if ('speechSynthesis' in window) {
        voiceOwnerGestureUnlocked = true;
        const browserRes = await speakBrowserAsync(item.text, { fastProbe: false });
        if (browserRes.completed) {
            setVoiceStatusBadge('browser_fallback');
            return browserRes;
        }
    }
    setVoiceStatusBadge('browser_fallback');
    return res;
}

async function playBackendVoiceAsync(text, options) {
    return startBackendVoiceJob(text, options);
}

async function playFallbackVoiceAsync(text, options) {
    return startBackendVoiceJob(text, options);
}

async function speakWithProviderAsync(text, options) {
    return queueNeenaVoice(text, options);
}

async function speakWithFallbackAsync(text, options) {
    return queueNeenaVoice(text, options);
}

async function refreshFallbackVoiceStatus() {
    try {
        const response = await fetch(`${API_BASE}/neena/cockpit-voice/status`, { cache: 'no-store' });
        voiceFallbackProviderStatus = await response.json().catch(() => ({}));
    } catch (e) {
        voiceFallbackProviderStatus = { ok: false, reason: 'status_fetch_failed' };
    }
    return voiceFallbackProviderStatus;
}

async function announceNeena(message, options) {
    const opts = Object.assign({
        showCockpit: true,
        appendChat: false,
        speak: null,
        taskFeed: null,
        taskType: 'info',
        forceSpeak: false,
        ui_action: null,
        meta: null,
        voicePriority: 'progress',
        voiceDedupeKey: null,
        isFailureNotice: false,
    }, options || {});
    const text = (message || '').trim();
    const out = {
        displayed: false,
        speak_requested: false,
        speak_queued: false,
    };
    if (!text) return out;
    // Chat me text; voice pad pe full reply duplicate mat dikhao.
    if (opts.appendChat) {
        appendChatMessage('assistant', text, opts.meta || {});
        opts.showCockpit = false;
    }
    if (opts.showCockpit) {
        showCockpitReply(text);
        out.displayed = true;
    }
    if (opts.taskFeed) appendCockpitTask(opts.taskFeed, opts.taskType);
    const wantSpeak = !opts.isFailureNotice && (opts.forceSpeak || (opts.speak !== null ? opts.speak : isSpeakResponsesEnabled()));
    if (wantSpeak) {
        out.speak_requested = true;
        // Speaking: clear rail text (chat already has it if appendChat).
        const rail = document.getElementById('cockpit-voice-reply');
        if (rail && opts.appendChat) rail.textContent = '';
        const q = queueNeenaVoice(text, {
            priority: opts.voicePriority,
            dedupeKey: opts.voiceDedupeKey,
            isFailureNotice: opts.isFailureNotice,
        });
        out.speak_queued = !!(q && q.queued);
    }
    if (opts.ui_action) handleNeenaUiAction(opts.ui_action, opts.meta || {});
    return out;
}

function deliverNeenaReply(message, options) {
    const opts = Object.assign({ voicePriority: 'final' }, options || {});
    return announceNeena(message, opts);
}

async function testOwnerVoice() {
    voiceOwnerGestureUnlocked = true;
    if (window.speechSynthesis) window.speechSynthesis.getVoices();
    appendCockpitTask('Voice test start…', 'info');
    showCockpitReply('Voice test…');

    const res = await speakWithBrowserFallback(VOICE_TEST_PHRASE, {
        priority: 'test_voice',
        dedupeKey: 'test_voice',
        fastFail: true,
    });
    if (res.completed || res.played) {
        appendCockpitTask('Voice test OK', 'success');
        showCockpitReply('Voice test successful.');
        return { mode: res.provider || 'voice', res };
    }
    appendCockpitTask('Voice test: browser fallback active', 'info');
    showCockpitReply(VOICE_TEST_PHRASE);
    setVoiceStatusBadge('browser_fallback');
    return { mode: 'browser_fallback', res };
}

async function testBrowserVoiceOnly() {
    voiceOwnerGestureUnlocked = true;
    if (window.speechSynthesis) window.speechSynthesis.getVoices();
    setVoiceStatusBadge('testing');
    appendCockpitTask('Browser-only voice test…', 'info');
    const res = await speakWithProviderAsync(VOICE_TEST_PHRASE, { forceProvider: 'browser', logBrowserFail: true });
    if (res.completed) {
        appendCockpitTask('Browser voice test OK', 'success');
        setVoiceStatusBadge('ready_browser');
    } else {
        appendCockpitTask(`Browser voice failed: ${res.error || 'unknown'}`, 'error');
        setVoiceStatusBadge('browser_failed', res.error);
    }
    return res;
}

async function testFallbackVoiceOnly() {
    setVoiceStatusBadge('testing');
    appendCockpitTask('Backend-only voice test…', 'info');
    const res = await speakWithProviderAsync(VOICE_TEST_PHRASE, { forceProvider: 'backend' });
    if (res.completed) {
        appendCockpitTask('Backend voice test OK', 'success');
        setVoiceStatusBadge('ready_backend');
    } else if (res.needsManual || res.manualReady) {
        appendCockpitTask('Backend voice ready — click Play Voice', 'info');
        setVoiceStatusBadge('backend_ready', 'Click Play Voice');
    } else {
        appendCockpitTask(`Backend voice failed: ${res.error || 'unknown'}`, 'error');
        setVoiceStatusBadge('backend_failed', res.error);
    }
    return res;
}

async function showVoiceDiagnostics() {
    await refreshFallbackVoiceStatus();
    const synthExists = 'speechSynthesis' in window;
    const voices = synthExists ? window.speechSynthesis.getVoices() : [];
    const lines = [
        `speechSynthesis exists: ${synthExists}`,
        `voices count: ${voices.length}`,
        `voice provider mode: ${voiceProviderMode}`,
        `effective provider: ${getEffectiveVoiceProvider()}`,
        `last browser error: ${voiceLastBrowserError || '—'}`,
        `browser known failed: ${voiceBrowserKnownFailed}`,
        `backend provider ok: ${voiceFallbackProviderStatus && voiceFallbackProviderStatus.ok}`,
        `backend provider: ${(voiceFallbackProviderStatus && voiceFallbackProviderStatus.provider) || '—'}`,
        `backend reason: ${(voiceFallbackProviderStatus && voiceFallbackProviderStatus.reason) || '—'}`,
        `last backend play error: ${voiceLastBackendError || '—'}`,
        `current audio url: ${currentCockpitAudioUrl || '—'}`,
        `voice status: ${voiceStatusState}`,
        `tab muted: cannot detect — check system volume & tab mute icon`,
    ];
    const pre = document.getElementById('voice-diagnostics-output');
    if (pre) {
        pre.textContent = lines.join('\n');
        pre.classList.remove('hidden');
    }
    appendCockpitTask('Voice diagnostics updated', 'info');
    return lines.join('\n');
}
