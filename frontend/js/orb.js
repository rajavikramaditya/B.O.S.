// ==== Neena Core orb (Option D / Hybrid + Phase 2 state wiring) ====
// Visual + priority resolver for the Home AI-core globe.
// Demo cycler: local-only (localhost + ?orbDemo=1 / localStorage.cc_orb_demo=1).
// Plan §6 sound: WebAudio cues on transitions only; default OFF (localStorage cc-sound).

const NC_ORB_STATES = {
    idle: { label: 'Idle — monitoring station', cls: 'idle' },
    listening: { label: 'Listening…', cls: 'listening' },
    thinking: { label: 'Thinking…', cls: 'thinking' },
    working: { label: 'Working…', cls: 'working' },
    speaking: { label: 'Speaking', cls: 'speaking' },
    syncing: { label: 'Syncing station data…', cls: 'syncing' },
    sleeping: { label: 'Sleeping — locked / offline', cls: 'sleeping' },
    audio_gen: { label: 'Generating audio…', cls: 'audio_gen' },
    azura_push: { label: 'Pushing to AzuraCast…', cls: 'azura_push' },
    stream_verify: { label: 'Verifying live stream…', cls: 'stream_verify' },
    approval_needed: { label: 'Waiting for your approval', cls: 'approval_needed' },
    success: { label: 'Done', cls: 'success' },
    error: { label: 'Attention needed', cls: 'error' },
};

/** Highest priority wins. */
const NC_ORB_PRIORITY = [
    'error',
    'azura_push',
    'stream_verify',
    'syncing',
    'audio_gen',
    'speaking',
    'listening',
    'thinking',
    'working',
    'approval_needed',
    'sleeping',
    'success',
    'idle',
];
// Expose for e2e plan §4 contract (classic script const is not on window by default).
window.NC_ORB_PRIORITY = NC_ORB_PRIORITY;

const NC_ORB_DEMO_CYCLE = [
    'idle', 'listening', 'thinking', 'working', 'speaking',
    'syncing', 'audio_gen', 'azura_push', 'stream_verify',
    'approval_needed', 'success', 'error', 'sleeping',
];

const NC_STATION_SUBTITLE = 'Orai · Jalaun · Bundelkhand';
const NC_SOUND_KEY = 'cc-sound';

let _ncOrbDemoTimer = null;
let _ncOrbDemoIndex = 0;
let _ncOrbCurrent = 'idle';
let _ncSuccessTimer = null;
let _ncAudioCtx = null;
let _ncSoundLastAt = 0;
let _ncLastSoundedState = null;
let _ncPrevResolvedForSound = 'idle';

/** Layered activity truth — client in-flight + polled server hints. */
const _ncActivity = {
    client: null,          // short-lived: listening|thinking|speaking|audio_gen|azura_push|stream_verify|working|error|success
    clientLabel: null,
    pendingApproval: false,
    pendingCount: 0,
    activeJob: null,       // { action, progress_message, job_id } | null
    openGoal: null,
};

function _ncIsLocalHost() {
    const h = (window.location && window.location.hostname) || '';
    return h === 'localhost' || h === '127.0.0.1' || h === '0.0.0.0' || h === '[::1]';
}

/** Demo cycler ONLY on local hosts with explicit opt-in. Never on production. */
function isNcOrbDemoAllowed() {
    if (!_ncIsLocalHost()) return false;
    try {
        const q = new URLSearchParams(window.location.search || '');
        if (q.get('orbDemo') === '1') return true;
        if (localStorage.getItem('cc_orb_demo') === '1') return true;
    } catch (e) { /* ignore */ }
    return false;
}

/** Plan §6: default OFF until owner opts in via header toggle. */
function isNcSoundEnabled() {
    try {
        return localStorage.getItem(NC_SOUND_KEY) === '1';
    } catch (e) {
        return false;
    }
}

function syncCcSoundToggle() {
    const on = isNcSoundEnabled();
    const btn = document.getElementById('cc-sound-toggle');
    const icon = document.getElementById('cc-sound-icon');
    if (btn) {
        btn.classList.toggle('is-muted', !on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        btn.title = on ? 'Orb sound cues on — click to mute' : 'Orb sound cues off — click to enable';
    }
    if (icon) {
        icon.className = on ? 'fa-solid fa-volume-high' : 'fa-solid fa-volume-xmark';
    }
}

function toggleCcSound() {
    const next = !isNcSoundEnabled();
    try {
        localStorage.setItem(NC_SOUND_KEY, next ? '1' : '0');
    } catch (e) { /* ignore */ }
    syncCcSoundToggle();
    if (next) {
        // Unlock AudioContext on user gesture.
        _ncEnsureAudioCtx();
        playNcOrbCue('listening');
    }
}

function _ncEnsureAudioCtx() {
    if (_ncAudioCtx) return _ncAudioCtx;
    try {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return null;
        _ncAudioCtx = new Ctx();
    } catch (e) {
        return null;
    }
    return _ncAudioCtx;
}

function _ncBeep(freq, durMs, type, gainVal, when) {
    const ctx = _ncEnsureAudioCtx();
    if (!ctx) return;
    const t0 = (when != null ? when : ctx.currentTime);
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type || 'sine';
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(gainVal || 0.05, t0 + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + (durMs / 1000));
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(t0);
    osc.stop(t0 + (durMs / 1000) + 0.02);
}

/**
 * Plan §6 cues — transitions only, debounced, never on poll refresh of same state.
 * listening=chime, approval=double-chime, success=tick, azura done=whoosh, error=low tone.
 */
function playNcOrbCue(state, fromState) {
    if (!isNcSoundEnabled()) return;
    if (isNcOrbDemoAllowed()) return;
    const now = Date.now();
    if (now - _ncSoundLastAt < 180) return;
    if (state === _ncLastSoundedState && state !== 'success' && state !== 'error') return;
    _ncSoundLastAt = now;
    _ncLastSoundedState = state;

    const ctx = _ncEnsureAudioCtx();
    if (ctx && ctx.state === 'suspended') {
        try { ctx.resume(); } catch (e) { /* ignore */ }
    }

    if (state === 'listening') {
        _ncBeep(880, 90, 'sine', 0.04);
        return;
    }
    if (state === 'approval_needed') {
        _ncBeep(660, 80, 'sine', 0.045);
        _ncBeep(880, 90, 'sine', 0.04, (_ncAudioCtx && _ncAudioCtx.currentTime + 0.14) || undefined);
        return;
    }
    if (state === 'success') {
        if (fromState === 'azura_push') {
            // whoosh-ish descending sweep
            const c = _ncEnsureAudioCtx();
            if (!c) return;
            const t0 = c.currentTime;
            const osc = c.createOscillator();
            const g = c.createGain();
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(420, t0);
            osc.frequency.exponentialRampToValueAtTime(120, t0 + 0.22);
            g.gain.setValueAtTime(0.0001, t0);
            g.gain.exponentialRampToValueAtTime(0.03, t0 + 0.02);
            g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.24);
            osc.connect(g);
            g.connect(c.destination);
            osc.start(t0);
            osc.stop(t0 + 0.26);
            return;
        }
        _ncBeep(1046, 70, 'triangle', 0.035);
        return;
    }
    if (state === 'error') {
        _ncBeep(180, 160, 'triangle', 0.05);
        return;
    }
    if (state === 'stream_verify' && fromState !== 'stream_verify') {
        // confirmation blip reserved for verified → success path; skip enter noise
        return;
    }
}

function setCoreOrbState(state, customLabel) {
    const cfg = NC_ORB_STATES[state] || NC_ORB_STATES.idle;
    const prev = _ncOrbCurrent;
    _ncOrbCurrent = cfg.cls;
    const orb = document.getElementById('neena-core-orb');
    const labelEl = document.getElementById('nc-orb-state-label');
    if (orb) orb.setAttribute('data-orb-state', cfg.cls);
    if (labelEl) labelEl.textContent = customLabel || cfg.label;
    if (cfg.cls !== prev) {
        playNcOrbCue(cfg.cls, prev);
    }
}

/** Public alias used by docs / Gemini-style prompts. */
function setNcOrbState(state, customLabel) {
    return setCoreOrbState(state, customLabel);
}
window.setNcOrbState = setNcOrbState;
window.setCoreOrbState = setCoreOrbState;

function getCoreOrbState() {
    return _ncOrbCurrent;
}

function initNeenaCoreOrb() {
    syncCcSoundToggle();
    setCoreOrbState('idle');
    const sub = document.getElementById('nc-orb-task-line');
    if (sub && (!sub.textContent || sub.textContent.indexOf('Not checked') !== -1 || sub.textContent.indexOf('shown') !== -1)) {
        sub.textContent = NC_STATION_SUBTITLE;
    }
    if (isNcOrbDemoAllowed()) {
        startNcOrbDemo();
    } else {
        stopNcOrbDemo();
        resolveNcOrbState();
    }
}

/**
 * Set ephemeral client-side activity (chat/mic/TTS/capsule POSTs).
 * Pass null to clear. success auto-clears after ~3s (plan §4).
 * Plan priority: error > speaking — speaking must not overwrite an active error.
 */
function setNcClientActivity(state, label) {
    if (isNcOrbDemoAllowed()) return;
    if (_ncSuccessTimer) {
        clearTimeout(_ncSuccessTimer);
        _ncSuccessTimer = null;
    }
    if (!state) {
        _ncActivity.client = null;
        _ncActivity.clientLabel = null;
        resolveNcOrbState();
        return;
    }
    const cfg = NC_ORB_STATES[state];
    if (!cfg) return;
    // error > speaking (Section 4 priority): keep error visible while TTS may still play.
    if (cfg.cls === 'speaking' && _ncActivity.client === 'error') {
        return;
    }
    _ncActivity.client = cfg.cls;
    _ncActivity.clientLabel = label || cfg.label;
    resolveNcOrbState();
    if (cfg.cls === 'success') {
        _ncSuccessTimer = setTimeout(() => {
            if (_ncActivity.client === 'success') {
                _ncActivity.client = null;
                _ncActivity.clientLabel = null;
                resolveNcOrbState();
            }
        }, 3000);
    }
}

/** Update polled server hints (live-state / working-context / cockpit). */
function setNcPolledActivity(partial) {
    if (!partial || typeof partial !== 'object') return;
    if (Object.prototype.hasOwnProperty.call(partial, 'pendingApproval')) {
        _ncActivity.pendingApproval = !!partial.pendingApproval;
        if (!_ncActivity.pendingApproval) _ncActivity.pendingCount = 0;
    }
    if (Object.prototype.hasOwnProperty.call(partial, 'pendingCount')) {
        const n = Number(partial.pendingCount) || 0;
        _ncActivity.pendingCount = n;
        if (n > 0) _ncActivity.pendingApproval = true;
    }
    if (Object.prototype.hasOwnProperty.call(partial, 'activeJob')) {
        _ncActivity.activeJob = partial.activeJob || null;
    }
    if (Object.prototype.hasOwnProperty.call(partial, 'openGoal')) {
        _ncActivity.openGoal = partial.openGoal || null;
    }
    if (!isNcOrbDemoAllowed()) resolveNcOrbState();
}

function _ncApprovalLabel() {
    const n = _ncActivity.pendingCount > 0 ? _ncActivity.pendingCount : 1;
    return `Waiting for your approval (${n})`;
}

function resolveNcOrbState() {
    if (isNcOrbDemoAllowed()) return;

    let resolved = 'idle';
    let label = NC_ORB_STATES.idle.label;

    if (_ncActivity.client && NC_ORB_STATES[_ncActivity.client]) {
        resolved = _ncActivity.client;
        label = _ncActivity.clientLabel || NC_ORB_STATES[resolved].label;
    } else if (_ncActivity.activeJob) {
        const action = String(_ncActivity.activeJob.action || '').toLowerCase();
        if (action.indexOf('verify') !== -1) {
            resolved = 'stream_verify';
        } else {
            resolved = 'working';
        }
        label = _ncActivity.activeJob.progress_message
            || _ncActivity.activeJob.action
            || NC_ORB_STATES[resolved].label;
    } else if (_ncActivity.pendingApproval) {
        resolved = 'approval_needed';
        label = _ncApprovalLabel();
    }

    // Priority sanity: if client is idle-cleared but we somehow have both, prefer higher
    const candidates = [];
    if (_ncActivity.client) candidates.push(_ncActivity.client);
    if (_ncActivity.activeJob) {
        const action = String(_ncActivity.activeJob.action || '').toLowerCase();
        candidates.push(action.indexOf('verify') !== -1 ? 'stream_verify' : 'working');
    }
    if (_ncActivity.pendingApproval) candidates.push('approval_needed');
    if (!candidates.length) candidates.push('idle');

    let best = 'idle';
    let bestRank = NC_ORB_PRIORITY.length;
    candidates.forEach((c) => {
        const rank = NC_ORB_PRIORITY.indexOf(c);
        if (rank >= 0 && rank < bestRank) {
            bestRank = rank;
            best = c;
        }
    });
    resolved = best;
    if (resolved === _ncActivity.client && _ncActivity.clientLabel) {
        label = _ncActivity.clientLabel;
    } else if ((resolved === 'working' || resolved === 'stream_verify') && _ncActivity.activeJob) {
        label = _ncActivity.activeJob.progress_message
            || _ncActivity.activeJob.action
            || NC_ORB_STATES[resolved].label;
    } else if (resolved === 'approval_needed') {
        label = _ncApprovalLabel();
    } else {
        label = NC_ORB_STATES[resolved].label;
    }

    // Avoid re-sounding approval on every poll refresh of the same state.
    const prevForSound = _ncPrevResolvedForSound;
    _ncPrevResolvedForSound = resolved;
    if (resolved === prevForSound && resolved === 'approval_needed') {
        _ncLastSoundedState = 'approval_needed';
    }

    setCoreOrbState(resolved, label);

    const sub = document.getElementById('nc-orb-task-line');
    if (sub) {
        if (_ncActivity.openGoal) {
            sub.textContent = _ncActivity.openGoal;
        } else if (resolved === 'idle') {
            sub.textContent = NC_STATION_SUBTITLE;
        } else if (_ncActivity.activeJob && _ncActivity.activeJob.progress_message) {
            sub.textContent = _ncActivity.activeJob.progress_message;
        } else {
            sub.textContent = 'No active task';
        }
    }
}

function stopNcOrbDemo() {
    if (_ncOrbDemoTimer) {
        clearInterval(_ncOrbDemoTimer);
        _ncOrbDemoTimer = null;
    }
    const hint = document.getElementById('nc-orb-demo-hint');
    if (hint) hint.classList.add('hidden');
}

function startNcOrbDemo() {
    stopNcOrbDemo();
    if (!isNcOrbDemoAllowed()) return;
    const hint = document.getElementById('nc-orb-demo-hint');
    if (hint) hint.classList.remove('hidden');
    _ncOrbDemoIndex = 0;
    setCoreOrbState(NC_ORB_DEMO_CYCLE[0]);
    _ncOrbDemoTimer = setInterval(() => {
        _ncOrbDemoIndex = (_ncOrbDemoIndex + 1) % NC_ORB_DEMO_CYCLE.length;
        setCoreOrbState(NC_ORB_DEMO_CYCLE[_ncOrbDemoIndex]);
    }, 2800);
}

/** Map legacy setNeenaState / voice classes onto orb activity. */
function mapLegacyNeenaStateToOrb(legacyCls) {
    const map = {
        online: null, // clear client → fall through to polled idle/approval/jobs
        listening: 'listening',
        thinking: 'thinking',
        executing: 'working',
        broadcasting: 'speaking',
        error: 'error',
    };
    return Object.prototype.hasOwnProperty.call(map, legacyCls) ? map[legacyCls] : null;
}

function applyLegacyNeenaStateToOrb(legacyCls, label) {
    if (isNcOrbDemoAllowed()) return;
    const mapped = mapLegacyNeenaStateToOrb(legacyCls);
    if (mapped === null) {
        // "online" / idle-like — clear client activity so polled truth can show
        setNcClientActivity(null);
        return;
    }
    if (mapped) setNcClientActivity(mapped, label);
}
