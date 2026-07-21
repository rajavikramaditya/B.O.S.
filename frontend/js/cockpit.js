// ==== Orai Command Center — command-center cockpit shell (state, mic, quick actions) module ====
// Auto-split from the former monolithic app.js (M6 Phase 4c, SRP).
// Loaded as an ordered classic <script>; shares one global scope with sibling
// modules (core.js, voice.js, admin.js, cockpit.js, panels.js, app.js).

async function runLiveWhatNow() {
    if (neenaChatInFlight) return;
    neenaChatInFlight = true;
    setQuickActionsDisabled(true);
    setNeenaState('thinking', 'Live state check…');
    let staleState = false;
    try {
        const response = await adminFetchWithTimeout(`${API_BASE}/neena/live-ops/quick`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'what_now' }),
        }, LIVE_STATE_TIMEOUT_MS);
        const data = await response.json().catch(() => ({}));
        if (response.ok && data.handled) {
            liveStateStale = false;
            announceNeena(data.reply, { appendChat: true, meta: data, taskFeed: 'What now (live)', taskType: 'success', voicePriority: 'final' });
        } else {
            staleState = true;
            liveStateStale = true;
            announceNeena('Live state check fail ho gaya. Main cached status use kar rahi hoon.', {
                taskType: 'error',
                taskFeed: 'Live state unavailable',
                speak: false,
            });
            if (Date.now() - lastLiveStateFailSpeakAt > LIVE_STATE_STALE_SPEAK_MS) {
                lastLiveStateFailSpeakAt = Date.now();
                queueNeenaVoice('Live state check fail ho gaya. Main cached status use kar rahi hoon.', {
                    priority: 'error',
                    dedupeKey: 'live_state_fail',
                });
            }
        }
    } catch (e) {
        staleState = true;
        liveStateStale = true;
        const isTimeout = e && (e.name === 'AbortError');
        const msg = isTimeout
            ? 'Live state check timeout ho gaya. Main cached status use kar rahi hoon.'
            : 'Live state check fail ho gaya. Main cached status use kar rahi hoon.';
        announceNeena(msg, { taskFeed: 'Live state unavailable', taskType: 'error', speak: false });
        if (Date.now() - lastLiveStateFailSpeakAt > LIVE_STATE_STALE_SPEAK_MS) {
            lastLiveStateFailSpeakAt = Date.now();
            queueNeenaVoice(msg, { priority: 'error', dedupeKey: 'live_state_fail' });
        }
    } finally {
        neenaChatInFlight = false;
        setQuickActionsDisabled(false);
        setNeenaState('online', staleState ? 'Live state stale' : 'Neena Online');
    }
}

const COCKPIT_ACTION_UI = {
    station_status: {
        start: 'Checking status…',
        success: 'Status ready',
        timeout: 'Status check slow ho gaya. Backend busy lag raha hai.',
        fail: 'Status check failed',
    },
    diagnostics_fast: {
        start: 'Fast diagnostics running…',
        success: 'Fast diagnostics ready',
        timeout: 'Diagnostics slow ho gaye — thodi der baad dubara try kariye.',
        fail: 'Fast diagnostics failed',
    },
    diagnostics: {
        start: 'Fast diagnostics running…',
        success: 'Fast diagnostics ready',
        timeout: 'Diagnostics slow ho gaye — thodi der baad dubara try kariye.',
        fail: 'Fast diagnostics failed',
    },
    verify_latest_stream: {
        start: 'Verifying stream on air…',
        success: 'Stream verify complete',
        timeout: 'Verification start nahi ho paayi.',
        timeoutPoll: 'Stream verification abhi complete nahi hui. Main final result nahi de paayi.',
        fail: 'Stream verify failed',
    },
    creative_job: {
        start: 'Creative job chal rahi hai…',
        success: 'Creative job complete',
        timeout: 'Creative job slow ho gayi.',
        timeoutPoll: 'Creative job abhi complete nahi hui.',
        fail: 'Creative job failed',
    },
};

const CC_THEME_KEY = 'cc-theme-v2';
const CC_SIDEBAR_KEY = 'cc-sidebar-collapsed';

function initCcChrome() {
    // Neena Core: light theme retired — always dark. Theme toggle kept as safe no-op for e2e.
    document.body.setAttribute('data-theme', 'dark');
    try { localStorage.setItem(CC_THEME_KEY, 'dark'); } catch (e) { /* ignore */ }
    syncCcThemeIcon('dark');
    if (localStorage.getItem(CC_SIDEBAR_KEY) === '1' && window.matchMedia('(min-width: 961px)').matches) {
        document.body.classList.add('cc-sidebar-collapsed');
    }
    loadBuildInfo();
}

const CC_BUILD_INFO_URL = '/__cc-version.json';
let _ccBuildInfo = null;

function _ccBuildTimeShort(iso) {
    if (!iso) return '';
    const s = String(iso);
    if (s.indexOf('__') !== -1) return ''; // unfilled deploy placeholder
    return s.replace('T', ' ').replace('Z', '').slice(0, 16);
}

async function loadBuildInfo() {
    const badge = document.getElementById('cc-build-badge-text');
    try {
        const res = await fetch(CC_BUILD_INFO_URL + '?t=' + Date.now(), { cache: 'no-store' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        _ccBuildInfo = await res.json();
    } catch (e) {
        _ccBuildInfo = { _error: String((e && e.message) || e) };
    }
    if (badge) {
        if (_ccBuildInfo && !_ccBuildInfo._error) {
            const name = _ccBuildInfo.build_name || 'build';
            const dep = _ccBuildTimeShort(_ccBuildInfo.deploy_time_utc);
            badge.textContent = dep ? (name + ' \u00b7 ' + dep) : name;
        } else {
            badge.textContent = 'build ?';
        }
    }
    return _ccBuildInfo;
}

function _abSet(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = (val === undefined || val === null || val === '') ? '\u2014' : String(val);
}

function populateAboutModal() {
    const b = _ccBuildInfo || {};
    _abSet('ab-app_name', b.app_name);
    _abSet('ab-build_name', b.build_name);
    _abSet('ab-git_commit', b.git_commit);
    _abSet('ab-build_time_utc', b.build_time_utc);
    _abSet('ab-deploy_time_utc', b.deploy_time_utc);
    _abSet('ab-served_from', b.served_from);
    _abSet('ab-backend_version', b.backend_version);
    _abSet('ab-frontend_asset_version', b.frontend_asset_version);
    _abSet('ab-data_build', document.body.getAttribute('data-build'));
    _abSet('ab-current_url', window.location.href);
    _abSet('ab-browser_time', new Date().toString());
    const note = document.getElementById('cc-about-note');
    if (note) {
        note.textContent = b._error
            ? ('Could not load /__cc-version.json: ' + b._error + ' \u2014 nginx may be serving the wrong path.')
            : 'If this shows the expected build but the page still looks old, your browser is running stale JS/CSS \u2014 do a full reload. If /__cc-version.json is missing or old, nginx is serving the wrong static path.';
    }
}

async function openAboutModal() {
    const ov = document.getElementById('cc-about-overlay');
    if (!ov) return;
    if (!_ccBuildInfo) await loadBuildInfo();
    populateAboutModal();
    ov.hidden = false;
}

function closeAboutModal() {
    const ov = document.getElementById('cc-about-overlay');
    if (ov) ov.hidden = true;
}

async function refreshAboutModal() {
    await loadBuildInfo();
    populateAboutModal();
}

function syncCcThemeIcon(theme) {
    const icon = document.getElementById('cc-theme-icon');
    if (!icon) return;
    icon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
}

function toggleCcTheme() {
    // Light theme retired for Neena Core command room. Keep handler for e2e contract.
    document.body.setAttribute('data-theme', 'dark');
    try { localStorage.setItem(CC_THEME_KEY, 'dark'); } catch (e) { /* ignore */ }
    syncCcThemeIcon('dark');
}

function toggleCcSidebar() {
    const mobile = window.matchMedia('(max-width: 960px)').matches;
    if (mobile) {
        document.body.classList.toggle('cc-sidebar-open');
        return;
    }
    document.body.classList.toggle('cc-sidebar-collapsed');
    localStorage.setItem(
        CC_SIDEBAR_KEY,
        document.body.classList.contains('cc-sidebar-collapsed') ? '1' : '0'
    );
}

function closeCcSidebarDrawer() {
    document.body.classList.remove('cc-sidebar-open');
}

// Globals
function switchTab(tabId) {
    if (tabId === 'whatsapp') tabId = 'settings';
    activeTab = tabId;
    
    // Toggle active buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelectorAll('.nav-btn').forEach(btn => btn.removeAttribute('aria-current'));
    const activeBtn = document.getElementById(`tab-btn-${tabId}`);
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.setAttribute('aria-current', 'page');
    }
    
    // Toggle active screen panels
    document.querySelectorAll('.screen-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    const activePanel = document.getElementById(`screen-${tabId}`);
    if (activePanel) activePanel.classList.add('active');
    
    // Update header title/subtitle
    const titleEl = document.getElementById('viewport-title');
    const subtitleEl = document.getElementById('viewport-subtitle');
    
    if (tabId === 'console') {
        if (titleEl) titleEl.textContent = 'Neena';
        if (subtitleEl) subtitleEl.textContent = 'Station manager agent — operations from here.';
        fetchCockpitData();
    } else if (tabId === 'neenalab') {
        if (titleEl) titleEl.textContent = 'Lab';
        if (subtitleEl) subtitleEl.textContent = 'Scripts, approvals, pipeline, schedule, source tools.';
        closeCommandDrawer();
        fetchNeenaLabData();
        fetchCockpitData();
    } else if (tabId === 'monitor') {
        if (titleEl) titleEl.textContent = 'Monitor';
        if (subtitleEl) subtitleEl.textContent = 'Telemetry, stream health, station readiness.';
        closeCommandDrawer();
        fetchCockpitData();
    } else if (tabId === 'settings') {
        if (titleEl) titleEl.textContent = 'Settings';
        if (subtitleEl) subtitleEl.textContent = 'Gateway, credentials, voice, agent flags, market rates.';
        closeCommandDrawer();
        fetchMarketRatesList();
        fetchWhatsAppGatewayStatus();
        fetchNeenaAgentFlags();
    }
    closeCcSidebarDrawer();
}

// Pending-approval HUD state: neutral when zero, amber only for real attention.
function setNcPendingAttention(count, urgent) {
    const panel = document.querySelector('.nc-hud-attention');
    if (!panel) return;
    const has = Number(count) > 0;
    panel.classList.toggle('has-pending', has);
    panel.classList.toggle('is-urgent', has && !!urgent);
}

function openCommandDrawer() {
    const drawer = document.getElementById('cc-command-drawer');
    if (!drawer) return;
    drawer.hidden = false;
    document.body.classList.add('cc-drawer-open');
    const input = document.getElementById('owner-console-input');
    if (input) {
        try { input.focus(); } catch (e) { /* ignore */ }
    }
}

function closeCommandDrawer() {
    const drawer = document.getElementById('cc-command-drawer');
    if (!drawer) return;
    drawer.hidden = true;
    document.body.classList.remove('cc-drawer-open');
}

function isCommandDrawerOpen() {
    const drawer = document.getElementById('cc-command-drawer');
    return !!(drawer && !drawer.hidden);
}

/** Phase 2: Home tiles from cockpit-status — never invent live claims. */
function syncNeenaCorePlaceholders(data) {
    if (!data) return;
    const launch = data.launch || {};
    const br = data.broadcast_readiness || {};
    const audio = br.audio || {};
    const azura = br.azuracast || {};

    const setTxt = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    if (launch.backend === 'online') setTxt('nc-status-backend', 'Online');
    else if (launch.backend) setTxt('nc-status-backend', String(launch.backend));
    else setTxt('nc-status-backend', 'Not checked');

    if (data.stream_online === true) setTxt('nc-status-stream', data.stream_stale ? 'Online (stale)' : 'Online');
    else if (data.stream_online === false) setTxt('nc-status-stream', 'Offline');
    else if (data.stream_status_cached) setTxt('nc-status-stream', 'Cached');
    // leave "Not checked" if unknown

    if (azura.ready_for_real_push === true) setTxt('nc-status-azura', 'Push ready');
    else if (azura.ready_for_real_push === false) setTxt('nc-status-azura', 'Not ready');

    if (audio.can_produce_real_audio === true) setTxt('nc-status-tts', 'Ready');
    else if (audio.tts_status) setTxt('nc-status-tts', String(audio.tts_status));
    else if (audio.can_produce_real_audio === false) setTxt('nc-status-tts', 'Not ready');

    if (data.whatsapp_gateway) {
        const wa = String(data.whatsapp_gateway);
        setTxt('nc-status-whatsapp', wa.charAt(0).toUpperCase() + wa.slice(1));
    }

    const pendingCaps = (data.capsules || []).filter((c) => {
        const s = (c.approval_status || c.status || '').toLowerCase();
        return s.includes('pending') || s === 'pending_review';
    });
    const homePending = document.getElementById('nc-pending-approval');
    if (homePending) {
        if (pendingCaps.length) {
            homePending.textContent = `${pendingCaps.length} capsule(s) awaiting review`;
            homePending.dataset.checked = '1';
            setNcPendingAttention(pendingCaps.length, pendingCaps.length >= 3);
        } else if (Array.isArray(data.capsules)) {
            // We received a list; no pending capsules from this source
            if (homePending.dataset.fromLive !== '1' && homePending.dataset.fromContext !== '1') {
                homePending.textContent = 'No pending approvals';
                homePending.dataset.checked = '1';
            }
            if (homePending.dataset.fromContext !== '1') setNcPendingAttention(0, false);
        }
    }

    if (typeof setNcPolledActivity === 'function') {
        setNcPolledActivity({
            pendingApproval: !!pendingCaps.length || !!(homePending && homePending.dataset.fromContext === '1'),
            pendingCount: pendingCaps.length || (homePending && homePending.dataset.fromContext === '1' ? 1 : 0),
        });
    }
}

/** Phase 2: poll /neena/live-state for jobs + pending + station pulse. */
async function fetchNeenaLiveHome() {
    if (typeof isBackendOffline !== 'undefined' && isBackendOffline) return;
    if (typeof shouldReducePollingLoad === 'function' && shouldReducePollingLoad()) return;
    try {
        const res = await fetch(`${API_BASE}/neena/live-state`, { cache: 'no-store' });
        if (!res.ok) return;
        const wrap = await res.json().catch(() => ({}));
        const live = wrap.live_state || wrap;
        if (!live || typeof live !== 'object') return;

        const setTxt = (id, val) => {
            const el = document.getElementById(id);
            if (el && val != null && val !== '') el.textContent = val;
        };

        if (live.stream === 'online') setTxt('nc-status-stream', live.stream_stale ? 'Online (stale)' : 'Online');
        else if (live.stream === 'offline') setTxt('nc-status-stream', 'Offline');
        else if (live.stream === 'unknown') { /* keep prior / Not checked */ }

        if (live.azuracast === 'ready') setTxt('nc-status-azura', 'Push ready');
        else if (live.azuracast === 'not_ready') setTxt('nc-status-azura', 'Not ready');

        if (live.tts === 'real' || live.tts === 'simulated') setTxt('nc-status-tts', live.tts === 'real' ? 'Ready' : 'Simulated');
        else if (live.tts === 'not_ready') setTxt('nc-status-tts', 'Not ready');

        if (live.whatsapp === 'online') setTxt('nc-status-whatsapp', 'Online');
        else if (live.whatsapp === 'offline') setTxt('nc-status-whatsapp', 'Offline');
        else if (live.whatsapp === 'non_blocking') setTxt('nc-status-whatsapp', 'Non-blocking');

        if (live.server === 'online') setTxt('nc-status-backend', 'Online');

        const pendingCount = Number(live.pending_scripts_count || 0);
        const homePending = document.getElementById('nc-pending-approval');
        if (homePending) {
            if (pendingCount > 0) {
                const top = (live.pending_scripts && live.pending_scripts[0]) || null;
                const preview = top && top.preview ? ` — ${String(top.preview).slice(0, 48)}` : '';
                homePending.textContent = `${pendingCount} awaiting review${preview}`;
                homePending.dataset.fromLive = '1';
                homePending.dataset.checked = '1';
                setNcPendingAttention(pendingCount, pendingCount >= 3);
            } else {
                homePending.textContent = 'No pending approvals';
                homePending.dataset.fromLive = '1';
                homePending.dataset.checked = '1';
                delete homePending.dataset.fromContext;
                setNcPendingAttention(0, false);
            }
        }

        const jobsEl = document.getElementById('nc-active-jobs');
        const jobs = Array.isArray(live.active_jobs) ? live.active_jobs : [];
        if (jobsEl) {
            jobsEl.dataset.filled = '1';
            if (!jobs.length) {
                jobsEl.innerHTML = '<p class="nc-muted">No active jobs</p>';
            } else {
                jobsEl.innerHTML = jobs.slice(0, 4).map((j) => {
                    const title = j.progress_message || j.action || j.job_id || 'Job';
                    const st = j.status ? ` · ${j.status}` : '';
                    return `<p class="nc-job-line">${String(title)}${st}</p>`;
                }).join('');
            }
        }

        const homeTask = document.getElementById('nc-current-task');
        let openGoal = null;
        if (jobs.length && (jobs[0].progress_message || jobs[0].action)) {
            openGoal = jobs[0].progress_message || jobs[0].action;
            if (homeTask) homeTask.textContent = openGoal;
        } else if (live.recommended_next_action && homeTask && !homeTask.dataset.fromContext) {
            // recommended_next_action is a hint code, not a fake status — show as next step
            homeTask.textContent = `Next: ${live.recommended_next_action}`;
        } else if (homeTask && !homeTask.dataset.fromContext && !jobs.length) {
            homeTask.textContent = 'No active task';
        }

        if (typeof setNcPolledActivity === 'function') {
            setNcPolledActivity({
                pendingApproval: pendingCount > 0,
                pendingCount: pendingCount,
                activeJob: jobs.length ? {
                    job_id: jobs[0].job_id,
                    action: jobs[0].action,
                    progress_message: jobs[0].progress_message,
                } : null,
                openGoal: openGoal || (homeTask && homeTask.dataset.fromContext === '1' ? homeTask.textContent : null),
            });
        }
    } catch (e) {
        /* best-effort */
    }
}

function toggleNeenaVoicePad() {
    const grid = document.getElementById('cc-drawer-body') || document.querySelector('.neena-chat-grid');
    const btn = document.getElementById('cc-header-voice-toggle');
    if (!grid) return;
    if (!isCommandDrawerOpen()) openCommandDrawer();
    const collapsed = grid.classList.toggle('neena-voice-pad-collapsed');
    try {
        localStorage.setItem('cc_voice_pad_collapsed', collapsed ? '1' : '0');
    } catch (e) { /* ignore */ }
    if (btn) btn.classList.toggle('is-on', !collapsed);
    if (!collapsed && activeTab !== 'console') {
        switchTab('console');
    }
}

function initNeenaVoicePadToggle() {
    const grid = document.getElementById('cc-drawer-body') || document.querySelector('.neena-chat-grid');
    const btn = document.getElementById('cc-header-voice-toggle');
    let collapsed = true;
    try {
        const saved = localStorage.getItem('cc_voice_pad_collapsed');
        if (saved === '0') collapsed = false;
        if (saved === '1') collapsed = true;
    } catch (e) { /* ignore */ }
    if (grid) grid.classList.toggle('neena-voice-pad-collapsed', collapsed);
    if (btn) btn.classList.toggle('is-on', !collapsed);
}
function setQuickActionsDisabled(disabled) {
    document.querySelectorAll('.quick-action-btn, .cockpit-pill').forEach(btn => {
        btn.disabled = disabled;
        btn.classList.toggle('is-busy', disabled);
    });
}

function runOwnerQuickAction(commandText) {
    runVoiceCommand(commandText);
}

function runVoiceCommand(commandText, options) {
    const inputEl = document.getElementById('owner-console-input');
    if (!inputEl || neenaChatInFlight) return;
    if (!isCommandCenterUnlocked()) {
        notifyAdminLocked();
        return;
    }
    if (typeof setHeardLine === 'function') {
        setHeardLine(`Heard: ${commandText}`);
    } else {
        const heard = document.getElementById('neena-heard-line');
        if (heard) heard.textContent = `Heard: ${commandText}`;
    }
    inputEl.value = commandText;
    inputEl.dataset.creativeCommand = options && options.creative ? '1' : '';
    submitOwnerConsoleMessage();
}

function initOwnerVoice() {
    const saved = sessionStorage.getItem(SPEAK_PREF_KEY);
    const defaultOn = saved === null || saved === '1';
    getSpeakCheckboxElements().forEach(el => {
        el.checked = defaultOn;
        el.addEventListener('change', () => syncSpeakCheckboxes(el.checked));
    });
    const savedMode = sessionStorage.getItem(VOICE_MODE_KEY);
    syncVoiceModeSelector(savedMode || 'auto');
    refreshFallbackVoiceStatus();
    if (!('speechSynthesis' in window)) {
        speechSynthAvailable = false;
        if (!speechWarningShown) {
            speechWarningShown = true;
            appendCockpitTask('Browser speech unavailable — Backend voice mode recommended.', 'info');
        }
        syncVoiceModeSelector('backend');
        setVoiceStatusBadge('idle', 'Backend/Edge mode');
        return;
    }
    speechSynthAvailable = true;
    const primeVoices = () => {
        window.speechSynthesis.getVoices();
        speechVoicesPrimed = true;
        refreshVoiceEngineStatus();
    };
    primeVoices();
    window.speechSynthesis.addEventListener('voiceschanged', primeVoices);
    document.body.addEventListener('click', function unlockOwnerVoice() {
        voiceOwnerGestureUnlocked = true;
        primeVoices();
        document.body.removeEventListener('click', unlockOwnerVoice);
    }, { once: true });
    refreshVoiceEngineStatus();
}

function handleNeenaUiAction(uiAction, meta) {
    if (!uiAction || !uiAction.type) return;
    if (uiAction.type === 'open_latest_script') {
        switchTab('neenalab');
        fetchNeenaLabData();
        appendCockpitTask(
            uiAction.capsule_id
                ? `Opened Capsule #${uiAction.capsule_id} in Neena Lab`
                : 'Neena Lab opened for script review',
            'info'
        );
        return;
    }
    if (uiAction.type === 'poll_cockpit_job' && uiAction.job_id) {
        const actionKey = uiAction.action_key || 'verify_latest_stream';
        const ui = COCKPIT_ACTION_UI[actionKey] || {
            success: 'Job complete',
            fail: 'Job failed',
            timeoutPoll: 'Job timeout',
        };
        pollCockpitJobInBackground(uiAction.job_id, ui, actionKey);
        return;
    }
    if (uiAction.type === 'refresh_cockpit') {
        fetchCockpitData();
        fetchNeenaLabData();
        return;
    }
    if (uiAction.type === 'admin_lock') {
        lockCommandCenter();
    }
}

async function runCockpitAction(action) {
    if (neenaChatInFlight) return;
    if (!isCommandCenterUnlocked()) {
        notifyAdminLocked();
        return;
    }
    const actionKey = action || 'station_status';
    const ui = COCKPIT_ACTION_UI[actionKey] || {
        start: 'Running action…',
        success: 'Action complete',
        timeout: 'Action timeout — dubara try kariye.',
        fail: 'Action failed',
    };
    const timeoutMs = COCKPIT_ACTION_TIMEOUT_MS[actionKey] || 15000;
    const isBackgroundAction = actionKey === 'verify_latest_stream';

    neenaChatInFlight = true;
    setQuickActionsDisabled(true);
    if (isBackgroundAction) {
        setNeenaState('executing', ui.start);
    } else {
        setNeenaState('thinking', ui.start);
    }
    appendCockpitTask(ui.start, 'command');
    await announceNeena(ui.start, { showCockpit: true, speak: true });
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    let releasedForBackground = false;
    try {
        const body = { action: actionKey };
        if (actionKey === 'verify_latest_stream') body.watch_seconds = 30;
        const response = await adminFetch(`${API_BASE}/neena/cockpit-action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: controller.signal,
        });
        if (response.status === 401) {
            setNeenaState('error', 'Locked');
            await announceNeena('Sir, Command Center locked hai. Pehle owner unlock phrase boliye.', {
                taskFeed: 'Auth locked',
                taskType: 'error',
                speak: true,
            });
            return;
        }
        const data = await response.json().catch(() => ({}));
        if (response.ok && data.ok && data.mode === 'background' && data.job_id) {
            deliverNeenaReply(data.message || ui.start, {
                appendChat: true,
                meta: { action: actionKey, job_id: data.job_id },
            });
            appendCockpitTask(`Background job ${data.job_id} (${data.latency_ms || '?'}ms)`, 'info');
            neenaChatInFlight = false;
            setQuickActionsDisabled(false);
            releasedForBackground = true;
            pollCockpitJobInBackground(data.job_id, ui, actionKey);
            return;
        }
        if (response.ok && data.ok) {
            const msg = data.message || 'Done.';
            deliverNeenaReply(msg, {
                appendChat: true,
                meta: { action_type: data.action, latency_ms: data.latency_ms },
            });
            appendCockpitTask(`${ui.success} (${data.latency_ms || '?'}ms)`, 'success');
            setNeenaState('online', 'Neena Online');
            fetchCockpitData();
        } else {
            const reason = data.message || data.detail || ui.fail;
            deliverNeenaReply(reason, { appendChat: true });
            appendCockpitTask(`${ui.fail}: ${reason}`.substring(0, 120), 'error');
            setNeenaState('error', 'Error');
        }
    } catch (e) {
        if (e && e.name === 'AbortError') {
            deliverNeenaReply(ui.timeout, { appendChat: true });
            appendCockpitTask(ui.timeout, 'error');
        } else {
            deliverNeenaReply('Server se connect nahi ho paya.', { appendChat: true });
            appendCockpitTask(ui.fail, 'error');
        }
        setNeenaState('error', 'Connection Error');
    } finally {
        clearTimeout(timeoutId);
        if (!releasedForBackground) {
            neenaChatInFlight = false;
            setQuickActionsDisabled(false);
            setNeenaState('online', 'Neena Online');
        }
    }
}

async function fetchLaunchHealthBadges() {
    try {
        const response = await fetch(`${API_BASE}/neena/launch-health`, { cache: 'no-store' });
        if (!response.ok) return;
        const data = await response.json();
        const setBadge = (id, label, value, okValues) => {
            const el = document.getElementById(id);
            if (!el) return;
            const normalized = (value || 'unknown').toString();
            const isOk = okValues.some(v => normalized.toLowerCase().includes(v));
            el.className = `launch-badge ${isOk ? 'badge-ok' : 'badge-warn'}`;
            el.innerHTML = `${label}: <strong>${normalized}</strong>`;
        };
        setBadge('badge-backend', 'Backend', data.backend || 'online', ['online', 'active']);
        setBadge('badge-postgres', 'PostgreSQL', data.postgres, ['healthy']);
        setBadge('badge-pgvector', 'pgvector', data.pgvector, ['active']);
        setBadge('badge-redis', 'Redis', data.redis, ['healthy']);
        const wa = (data.whatsapp_gateway || 'offline').toString();
        const waEl = document.getElementById('badge-whatsapp');
        if (waEl) {
            const offline = wa.toLowerCase().includes('offline') || wa.toLowerCase().includes('unavailable');
            waEl.className = `launch-badge ${offline ? 'badge-warn' : 'badge-ok'}`;
            const display = offline ? 'offline — non-blocking' : wa;
            waEl.innerHTML = `WhatsApp: <strong>${display}</strong>`;
        }
    } catch (e) {
        // Silent — badges are informational only
    }
}

function updateProviderStatusWidget(metadata) {
    if (!metadata) return;
    
    const selectedModel = metadata.selected_model || 'auto';
    const actualModel = metadata.actual_model || 'none';
    const source = metadata.source || 'local_tool';
    const llmStatus = metadata.llm ? metadata.llm.status : 'not_used';
    const latency = metadata.timing ? `${metadata.timing.total_ms}ms` : '—';
    const fallbackUsed = metadata.fallback_used ? 'Yes' : 'No';
    
    const modelEl = document.getElementById('status-val-model');
    const actualEl = document.getElementById('status-val-actual');
    const sourceEl = document.getElementById('status-val-source');
    const llmStatusEl = document.getElementById('status-val-llm-status');
    const latencyEl = document.getElementById('status-val-latency');
    const fallbackEl = document.getElementById('status-val-fallback');
    
    if (modelEl) modelEl.innerHTML = `Selected: <strong>${selectedModel.replace(/-/g, ' ').toUpperCase()}</strong>`;
    if (actualEl) actualEl.innerHTML = `Last Model: <strong>${actualModel.replace(/-/g, ' ').toUpperCase()}</strong>`;
    if (sourceEl) sourceEl.innerHTML = `Source: <strong>${source.replace(/_/g, ' ').toUpperCase()}</strong>`;
    if (llmStatusEl) llmStatusEl.innerHTML = `LLM Status: <strong>${llmStatus.toUpperCase()}</strong>`;
    if (latencyEl) latencyEl.innerHTML = `Latency: <strong>${latency}</strong>`;
    if (fallbackEl) fallbackEl.innerHTML = `Fallback: <strong>${fallbackUsed}</strong>`;
    
    // Support showing cooldown details in widget
    const cooldownDiv = document.getElementById('status-val-cooldown');
    const cooldownDivider = document.getElementById('status-divider-cooldown');
    if (cooldownDiv && cooldownDivider) {
        if (llmStatus === 'cooldown' || metadata.model_rate_limited) {
            cooldownDiv.style.display = 'inline';
            cooldownDivider.style.display = 'inline';
            const hint = metadata.retry_after_hint ? ` (${metadata.retry_after_hint})` : '';
            cooldownDiv.innerHTML = `Cooldown: <strong class="text-warning">Active${hint}</strong>`;
        } else {
            cooldownDiv.style.display = 'none';
            cooldownDivider.style.display = 'none';
        }
    }
}

// =============================================================================
// M4-A5R — Voice-first Command Center cockpit
// =============================================================================

let voiceRecognition = null;
let voiceListening = false;
let cockpitCapsulesCache = [];

const NEENA_STATES = {
    online: { label: 'Neena Online', cls: 'online' },
    listening: { label: 'Listening…', cls: 'listening' },
    thinking: { label: 'Processing command…', cls: 'thinking' },
    executing: { label: 'Executing…', cls: 'executing' },
    broadcasting: { label: 'Broadcasting', cls: 'broadcasting' },
    error: { label: 'Error', cls: 'error' },
};

function syncGateGuideMode(mode) {
    const stage = document.getElementById('cc-gate-neena');
    const avatar = document.getElementById('cc-gate-avatar');
    if (!stage) return;
    // Static portrait only — modes kept for mic/listening chrome, no lip-sync.
    let next = mode || 'idle';
    if (!['idle', 'listening', 'speaking'].includes(next)) next = 'idle';
    stage.classList.remove('is-idle', 'is-listening', 'is-thinking', 'is-speaking');
    stage.classList.add(`is-${next === 'speaking' ? 'idle' : next}`);
    if (avatar) avatar.dataset.mode = next;
}

function setNeenaState(state, customLabel) {
    const cfg = NEENA_STATES[state] || NEENA_STATES.online;
    const label = customLabel || cfg.label;
    const title = document.getElementById('neena-state-title');
    const badge = document.getElementById('cockpit-state-label');
    const dot = document.getElementById('cockpit-state-dot');
    const orb = document.getElementById('neena-orb-wrap');
    if (title) title.textContent = label;
    if (badge) badge.textContent = label;
    if (dot) dot.className = `state-dot ${cfg.cls}`;
    if (orb) orb.className = `neena-orb-wrap state-${cfg.cls}`;

    // Bridge legacy states onto the Home core orb (Phase 2 priority resolver).
    if (typeof applyLegacyNeenaStateToOrb === 'function') {
        applyLegacyNeenaStateToOrb(cfg.cls, label);
    } else if (typeof isNcOrbDemoAllowed === 'function' && !isNcOrbDemoAllowed() && typeof setCoreOrbState === 'function') {
        const orbState = typeof mapLegacyNeenaStateToOrb === 'function' ? mapLegacyNeenaStateToOrb(cfg.cls) : 'idle';
        if (orbState) setCoreOrbState(orbState, label);
    }

    let gateMode = 'idle';
    if (cfg.cls === 'listening') gateMode = 'listening';
    syncGateGuideMode(gateMode);

    // Do not push long/redundant labels onto the locked gate chrome.
    const gateState = document.getElementById('cc-gate-state-label');
    if (gateState && document.body.classList.contains('cc-locked')) {
        gateState.textContent = gateMode === 'listening' ? 'Listening' : 'Locked';
    }
}

function appendCockpitTask(text, type = 'info') {
    const feed = document.getElementById('cockpit-task-feed');
    if (!feed) return;
    const normalized = (text || '').trim().toLowerCase();
    if (normalized === lastCockpitTaskText && Date.now() - lastCockpitTaskAt < 10000) return;
    lastCockpitTaskText = normalized;
    lastCockpitTaskAt = Date.now();
    const item = document.createElement('div');
    item.className = `task-item task-${type}`;
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    item.innerHTML = `<span class="task-time">${time}</span> ${text}`;
    feed.prepend(item);
    while (feed.children.length > 10) feed.removeChild(feed.lastChild);
}

function showCockpitReply(text) {
    const el = document.getElementById('cockpit-voice-reply');
    const clean = (text || '').replace(/<[^>]+>/g, '').replace(/\*.*?\*/g, '').trim();
    if (el) el.textContent = clean;
    // Never mirror Hinglish speak text onto the locked gate chrome.
    if (document.body.classList.contains('cc-locked')) return;
    const gateReply = document.getElementById('cc-gate-reply');
    if (gateReply) gateReply.textContent = clean;
}

function shortReplyForVoice(text) {
    const clean = (text || '').replace(/<[^>]+>/g, '').replace(/\*.*?\*/g, '').trim();
    const limit = (typeof MAX_VOICE_CHARS === 'number' && MAX_VOICE_CHARS > 0) ? MAX_VOICE_CHARS : 1200;
    if (clean.length <= limit) return clean;
    const cut = clean.substring(0, limit);
    const lastStop = Math.max(
        cut.lastIndexOf('।'),
        cut.lastIndexOf('.'),
        cut.lastIndexOf('!'),
        cut.lastIndexOf('?'),
        cut.lastIndexOf('\n')
    );
    if (lastStop > limit * 0.55) return cut.substring(0, lastStop + 1).trim();
    return cut.trim();
}

function toggleManualDrawer() {
    // Advanced / Debug drawer removed — keep no-op for any leftover callers.
}

function labSelectAll(on) {
    document.querySelectorAll('#neena-lab-day-folders input.lab-item-check').forEach((el) => {
        el.checked = !!on;
        const key = `${el.getAttribute('data-kind')}:${el.getAttribute('data-id')}`;
        if (typeof _labSelectedKeys !== 'undefined') {
            if (on) _labSelectedKeys.add(key);
            else _labSelectedKeys.delete(key);
        }
    });
}

async function labDeleteSelected() {
    const boxes = [...document.querySelectorAll('#neena-lab-day-folders input.lab-item-check:checked')];
    if (!boxes.length) {
        announceNeena('Koi item select nahi hai.', { taskType: 'error' });
        return;
    }
    if (!window.confirm(`Delete / archive ${boxes.length} selected item(s)?`)) return;
    let ok = 0;
    let fail = 0;
    for (const box of boxes) {
        const kind = box.getAttribute('data-kind');
        const id = Number(box.getAttribute('data-id'));
        try {
            if (kind === 'approval') {
                const res = await adminFetch(`${API_BASE}/admin/approval-queue/${id}/action`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'dismiss' }),
                });
                if (res.ok) {
                    ok += 1;
                    if (typeof _labSelectedKeys !== 'undefined') _labSelectedKeys.delete(`approval:${id}`);
                } else fail += 1;
            } else if (kind === 'capsule') {
                const res = await adminFetch(`${API_BASE}/admin/broadcast-capsules/${id}/archive`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                if (res.ok) {
                    ok += 1;
                    if (typeof _labSelectedKeys !== 'undefined') _labSelectedKeys.delete(`capsule:${id}`);
                } else fail += 1;
            }
        } catch (e) {
            fail += 1;
        }
    }
    appendCockpitTask(`Lab delete: ${ok} ok, ${fail} failed`, fail ? 'error' : 'success');
    fetchNeenaLabData(true);
    fetchCockpitData();
}

function initVoiceRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const note = document.getElementById('voice-fallback-note');
    if (!SpeechRecognition) {
        if (note) note.classList.remove('hidden');
        return;
    }
    voiceRecognition = new SpeechRecognition();
    voiceRecognition.lang = VOICE_COMMAND_LANG;
    voiceRecognition.interimResults = false;
    voiceRecognition.maxAlternatives = 1;
    voiceRecognition.onstart = () => {
        voiceListening = true;
        const isUnlock = voiceRecognitionMode === 'unlock';
        if (isUnlock) {
            transitionToState('LOCKED', 'Listening for unlock phrase…');
            const lbl = document.getElementById('cockpit-mic-label');
            if (lbl) lbl.textContent = 'Listening… tap to stop';
        } else {
            transitionToState('LISTENING');
        }
    };
    voiceRecognition.onend = () => {
        voiceListening = false;
        voiceRecognitionMode = 'command';
        if (!neenaChatInFlight && currentState !== 'PROCESSING') {
            if (!isCommandCenterUnlocked()) {
                transitionToState('LOCKED');
            } else {
                transitionToState('IDLE');
            }
        }
    };
    voiceRecognition.onerror = () => {
        voiceRecognitionMode = 'command';
        appendCockpitTask('Voice recognition error', 'error');
        if (!isCommandCenterUnlocked()) {
            transitionToState('LOCKED');
        } else {
            transitionToState('ERROR', 'Mic Error');
        }
    };
    voiceRecognition.onresult = (ev) => {
        const transcript = ev.results[0][0].transcript.trim();
        if (typeof setHeardLine === 'function') {
            setHeardLine(`Heard: ${transcript}`);
        } else {
            const heard = document.getElementById('neena-heard-line');
            if (heard) heard.textContent = `Heard: ${transcript}`;
        }
        voiceRecognitionMode = 'command';
        if (!isCommandCenterUnlocked()) {
            handleUnlockPhraseHeard(ev);
            return;
        }
        appendCockpitTask(`Heard: ${transcript}`, 'command');
        runVoiceCommand(transcript);
    };
}

function toggleVoiceListening() {
    if (!isCommandCenterUnlocked()) {
        startUnlockListening();
        return;
    }
    voiceRecognitionMode = 'command';
    setVoiceRecognitionLang('command');
    if (!voiceRecognition) {
        const note = document.getElementById('voice-fallback-note');
        if (note) note.classList.remove('hidden');
        appendCockpitTask('Voice input unavailable — use chat', 'info');
        return;
    }

    if (currentState === 'SPEAKING') {
        try { window.speechSynthesis.cancel(); } catch (e) {}
        if (currentCockpitAudio) {
            try { currentCockpitAudio.pause(); } catch (e) {}
        }
        voiceSpeaking = false;
        voiceQueue = [];
        appendCockpitTask('Voice interrupted by owner', 'info');
        
        transitionToState('LISTENING');
        try {
            voiceRecognition.start();
        } catch (e) { /* ignore */ }
        return;
    }

    if (currentState === 'LISTENING' || currentState === 'WAITING_FOR_FOLLOWUP') {
        try { voiceRecognition.stop(); } catch (e) {}
        transitionToState('IDLE');
        return;
    }

    if (currentState === 'PROCESSING') {
        if (activeChatAbortController) {
            activeChatAbortController.abort();
            activeChatAbortController = null;
        }
        appendCockpitTask('Processing cancelled by owner', 'info');
        transitionToState('LISTENING');
        try {
            voiceRecognition.start();
        } catch (e) { /* ignore */ }
        return;
    }

    if (currentState === 'IDLE' || currentState === 'ERROR') {
        transitionToState('LISTENING');
        try {
            voiceRecognition.start();
        } catch (e) {
            appendCockpitTask('Mic start failed — use Manual drawer', 'error');
            transitionToState('ERROR', 'Mic Error');
        }
        return;
    }
}
