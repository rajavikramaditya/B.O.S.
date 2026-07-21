// ==== Orai Command Center — dashboards, settings, monitor, health module ====
// Auto-split from the former monolithic app.js (M6 Phase 4c, SRP).
// Loaded as an ordered classic <script>; shares one global scope with sibling
// modules (core.js, voice.js, admin.js, cockpit.js, panels.js, app.js).

async function fetchTelemetryStats() {
    if (isBackendOffline) return;
    try {
        const response = await fetch(`${API_BASE}/runtime/status`);
        if (response.ok) {
            const data = await response.json();
            
            // Update CPU Gauge
            const cpu = data.stats.cpu || 0;
            const cpuGauge = document.getElementById('cpu-gauge');
            cpuGauge.style.background = `radial-gradient(closest-side, #080c14 79%, transparent 80% 100%), conic-gradient(var(--cyan) ${cpu}%, var(--bg-card-border) ${cpu}% 100%)`;
            document.getElementById('cpu-gauge-value').textContent = `${cpu}%`;
            
            // Update RAM Gauge
            const ram = data.stats.ram || 0;
            const ramGauge = document.getElementById('ram-gauge');
            ramGauge.style.background = `radial-gradient(closest-side, #080c14 79%, transparent 80% 100%), conic-gradient(var(--cyan) ${ram}%, var(--bg-card-border) ${ram}% 100%)`;
            document.getElementById('ram-gauge-value').textContent = `${ram}%`;
            updatePollingLoadMode({ cpu, ram });
            
            // Update Text items — reflect backend truth only; never assert a mode
            // the backend did not report.
            const isLocal = data.mode === 'LOCAL_TEST_MODE';
            const modeBadge = document.getElementById('telemetry-vm-mode');
            modeBadge.textContent = data.mode ? (isLocal ? 'LOCAL TEST MODE' : 'VM LIVE MODE') : 'Not checked';
            // Mode is informational (not an attention state) → neutral, not amber.
            modeBadge.className = data.mode ? (isLocal ? 'badge badge-neutral' : 'badge badge-success') : 'badge badge-neutral';
            
            // Gauge Labels
            document.getElementById('cpu-gauge-label').textContent = isLocal ? 'Local CPU Load' : 'VM CPU Load';
            document.getElementById('ram-gauge-label').textContent = isLocal ? 'Local RAM Usage' : 'VM RAM Usage';
            
            // VM Status Row
            const vmStatusEl = document.getElementById('telemetry-vm-status');
            const statusLabelEl = document.getElementById('telemetry-status-label');
            if (isLocal) {
                statusLabelEl.textContent = 'Runtime Status:';
                vmStatusEl.textContent = 'Local mode (VM not checked)';
                // Informational, not an alert → muted rather than amber.
                vmStatusEl.className = 'text-muted';
            } else {
                statusLabelEl.textContent = 'Runtime Status:';
                // Env-derived, not a live probe — do not claim "Verified".
                vmStatusEl.textContent = 'VM mode (reported)';
                vmStatusEl.className = 'text-success';
            }

            // Uptime Row
            const uptimeLabelEl = document.getElementById('telemetry-uptime-label');
            uptimeLabelEl.textContent = isLocal ? 'Local Process Uptime:' : 'Server Uptime:';
            document.getElementById('telemetry-uptime').textContent = data.uptime || 'Not checked';

            // Configured target — show backend-reported target, else Not checked.
            const ipLabelEl = document.getElementById('telemetry-public-ip-label');
            const ipValEl = document.getElementById('telemetry-public-ip');
            ipLabelEl.textContent = 'Configured Target:';
            ipValEl.textContent = data.public_ip || 'Not checked';

            // First Greeting Bubble Update
            const firstBubble = document.getElementById('console-first-bubble');
            if (firstBubble) {
                if (isLocal) {
                    firstBubble.innerHTML = "Ji sir, Command Center ready hai. Local status, source tools, approval queue aur creative work available hai. Playout aur VM live check unverified.";
                } else {
                    firstBubble.innerHTML = "Ji sir, Command Center ready hai. Playout aur VM fully stable hain. Aaj content, schedule, scripts ya station status me kya dekhna hai?";
                }
            }

            // Radio stream connection status (from station runtime DB, not a
            // live AzuraCast probe — so this row is honestly labelled "Radio Stream").
            const streamBadge = document.getElementById('telemetry-azuracast-status');
            const streamStatus = data.radio_stream;
            if (!streamStatus) {
                streamBadge.textContent = 'Not checked';
                streamBadge.className = 'badge badge-neutral';
            } else if (streamStatus === 'LIVE') {
                streamBadge.textContent = 'LIVE';
                streamBadge.className = 'badge badge-success';
            } else if (streamStatus === 'UNKNOWN') {
                streamBadge.textContent = 'Not checked';
                streamBadge.className = 'badge badge-neutral';
            } else {
                streamBadge.textContent = streamStatus;
                streamBadge.className = 'badge badge-warning';
            }

            // Autopilot / playlist mode — reflect reported value only.
            const autoBadge = document.getElementById('telemetry-autopilot-status');
            if (!data.auto_mode) {
                autoBadge.textContent = 'Not checked';
                autoBadge.className = 'badge badge-neutral';
            } else if (data.auto_mode === 'ON') {
                autoBadge.textContent = 'AUTO-PILOT: ON';
                autoBadge.className = 'badge badge-success';
            } else {
                autoBadge.textContent = `AUTO-PILOT: ${data.auto_mode}`;
                // OFF/other is a mode state, not an attention alert → neutral.
                autoBadge.className = 'badge badge-neutral';
            }
            
            // Sidebar server badge is updated from cockpit-status (fetchCockpitData)
            renderActivityLogs(data.commands);
        }
    } catch (e) {
        // Telemetry failure is non-blocking — do not mark server offline
    }
}

function renderActivityLogs(commands) {
    const container = document.getElementById('activities-scroller-container');
    if (!commands || commands.length === 0) {
        container.innerHTML = '<p class="empty-state">No activities logged yet.</p>';
        return;
    }
    
    container.innerHTML = '';
    commands.forEach(cmd => {
        const row = document.createElement('div');
        row.className = 'log-item-row';
        
        // Extract time
        const date = new Date(cmd.created_at || cmd.updated_at);
        const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        
        let resultMsg = 'Queued for VM execution';
        if (cmd.result_json) {
            try {
                resultMsg = JSON.parse(cmd.result_json).message || cmd.status;
            } catch (e) {}
        }
        
        row.innerHTML = `<span class="time">[${timeStr}]</span> <strong>${cmd.command_type}</strong>: ${resultMsg}`;
        container.appendChild(row);
    });
}

// Live Playout Streaming Audio Toggle
function toggleDashboardAudio() {
    const player = document.getElementById('dashboard-stream-player');
    const disc = document.getElementById('vinyl-disc');
    const playBtn = document.getElementById('player-play-btn');
    
    if (player.paused) {
        player.load();
        player.play().then(() => {
            disc.classList.add('spinning');
            playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
        }).catch(err => {
            alert('Live stream play failure: server buffer is currently syncing or offline.');
        });
    } else {
        player.pause();
        disc.classList.remove('spinning');
        playBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
    }
}

async function fetchNowPlayingMetadata() {
    try {
        const res = await fetch(`${API_BASE}/public/now-playing`);
        if (res.ok) {
            const data = await res.json();
            document.getElementById('player-track-title').textContent = data.title;
            document.getElementById('player-track-artist').textContent = data.artist;
            // Dynamically set the audio player source if stream URL is available
            if (data.stream_url) {
                const player = document.getElementById('dashboard-stream-player');
                if (player && !player.src) {
                    player.src = data.stream_url;
                }
            }
        }
    } catch(e) {}
}


// 5. NEENA LAB DATA FETCHER
let neenaLabInterval = null;
let _labDayFoldersOpen = {};
/** Persist checkbox selection across poll re-renders: "capsule:12" / "approval:81" */
let _labSelectedKeys = new Set();
let _labFoldersFingerprint = '';
let _labCheckListenerBound = false;

function _labItemKey(kind, id) {
    return `${kind}:${id}`;
}

function _captureLabChecksFromDom() {
    document.querySelectorAll('#neena-lab-day-folders input.lab-item-check').forEach((el) => {
        const key = _labItemKey(el.getAttribute('data-kind'), el.getAttribute('data-id'));
        if (el.checked) _labSelectedKeys.add(key);
        else _labSelectedKeys.delete(key);
    });
}

function _restoreLabChecksToDom() {
    document.querySelectorAll('#neena-lab-day-folders input.lab-item-check').forEach((el) => {
        const key = _labItemKey(el.getAttribute('data-kind'), el.getAttribute('data-id'));
        el.checked = _labSelectedKeys.has(key);
    });
}

function _bindLabCheckListener() {
    if (_labCheckListenerBound) return;
    const foldersEl = document.getElementById('neena-lab-day-folders');
    if (!foldersEl) return;
    foldersEl.addEventListener('change', (e) => {
        const t = e.target;
        if (!t || !t.classList || !t.classList.contains('lab-item-check')) return;
        const key = _labItemKey(t.getAttribute('data-kind'), t.getAttribute('data-id'));
        if (t.checked) _labSelectedKeys.add(key);
        else _labSelectedKeys.delete(key);
    });
    _labCheckListenerBound = true;
}

function _labFoldersDataFingerprint(data) {
    const caps = (data.broadcast_capsules || []).map((c) =>
        [c.id, c.approval_status, c.audio_truth_level, c.azuracast_status, (c.script_text || '').length, c.updated_at || c.created_at || ''].join(':')
    );
    const apps = (data.approval_queue || []).map((a) =>
        [a.id, a.status, (a.content_data || a.content_preview || '').length, a.created_at || ''].join(':')
    );
    return caps.join('|') + '||' + apps.join('|');
}

function _labDayKey(raw) {
    const s = String(raw || '').trim();
    if (!s) return 'Unknown day';
    const m = s.match(/(\d{4}-\d{2}-\d{2})/);
    return m ? m[1] : s.slice(0, 10);
}

function _labEscape(s) {
    return String(s || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function toggleLabDayFolder(dayKey) {
    _labDayFoldersOpen[dayKey] = !_labDayFoldersOpen[dayKey];
    const body = document.getElementById(`lab-day-body-${dayKey}`);
    const chev = document.getElementById(`lab-day-chev-${dayKey}`);
    if (body) body.classList.toggle('hidden', !_labDayFoldersOpen[dayKey]);
    if (chev) chev.className = _labDayFoldersOpen[dayKey]
        ? 'fa-solid fa-chevron-down'
        : 'fa-solid fa-chevron-right';
}

function _renderLabDayFolders(data, force) {
    const foldersEl = document.getElementById('neena-lab-day-folders');
    if (!foldersEl) return;
    _bindLabCheckListener();

    const fp = _labFoldersDataFingerprint(data);
    if (!force && fp === _labFoldersFingerprint && foldersEl.querySelector('.lab-day-folder')) {
        return;
    }
    _labFoldersFingerprint = fp;
    _captureLabChecksFromDom();

    const items = [];
    (data.broadcast_capsules || []).forEach((c) => {
        items.push({
            kind: 'capsule',
            id: c.id,
            day: _labDayKey(c.created_at),
            sort: c.created_at || '',
            title: c.title || `Capsule #${c.id}`,
            preview: (c.script_text || '').substring(0, 160),
            full: c.script_text || '',
            meta: c,
        });
    });
    (data.approval_queue || []).forEach((a) => {
        const linked = (data.broadcast_capsules || []).some(
            (c) => Number(c.approval_queue_id) === Number(a.id)
        );
        if (linked) return;
        items.push({
            kind: 'approval',
            id: a.id,
            day: _labDayKey(a.created_at),
            sort: a.created_at || '',
            title: `${a.type || 'script'} (approval #${a.id})`,
            preview: a.content_preview || (a.content_data || '').slice(0, 160),
            full: a.content_data || a.content_preview || '',
            meta: a,
        });
    });

    window.labApprovalCache = {};
    items.filter((it) => it.kind === 'approval').forEach((it) => {
        window.labApprovalCache[it.id] = it.full;
    });

    if (!items.length) {
        foldersEl.innerHTML = '<p class="empty-state">No Lab work yet. Neena scripts/capsules yahan day folders me aayenge.</p>';
        return;
    }

    items.sort((a, b) => String(b.sort).localeCompare(String(a.sort)));
    const byDay = {};
    items.forEach((it) => {
        if (!byDay[it.day]) byDay[it.day] = [];
        byDay[it.day].push(it);
    });
    const days = Object.keys(byDay).sort((a, b) => b.localeCompare(a));
    if (!_labDayFoldersOpen[days[0]]) _labDayFoldersOpen[days[0]] = true;

    foldersEl.innerHTML = days.map((day) => {
        const open = !!_labDayFoldersOpen[day];
        const rows = byDay[day].map((it) => {
            if (it.kind === 'capsule') {
                const c = it.meta;
                const approvalId = c.approval_queue_id;
                const audioUrl = c.audio_url || '';
                const audioPlayable = c.audio_playable && audioUrl;
                const canSendAzura = c.azuracast_push_allowed === true;
                const canEnsurePlayback = (c.azuracast_status === 'uploaded' || c.azuracast_status === 'scheduled');
                const checked = _labSelectedKeys.has(_labItemKey('capsule', c.id)) ? ' checked' : '';
                return `<div class="lab-item-row lab-day-item">
                    <div class="lab-item-top">
                        <label class="lab-check-label"><input type="checkbox" class="lab-item-check" data-kind="capsule" data-id="${c.id}"${checked}></label>
                        <span class="badge badge-info">Capsule #${c.id}</span>
                        <span class="lab-item-meta">${_labEscape(c.created_at || '')}</span>
                    </div>
                    <div class="lab-item-title"><strong>Capsule #${c.id}</strong>${c.title && String(c.title).length < 60 ? ` · ${_labEscape(c.title)}` : ''}</div>
                    <div class="capsule-status-badges">
                        <span class="badge badge-${c.approval_status === 'approved' ? 'success' : (c.approval_status === 'rejected' ? 'danger' : 'warning')}">approval: ${c.approval_status}</span>
                        <span class="badge badge-secondary">audio: ${c.audio_truth_level || 'none'}</span>
                        <span class="badge badge-secondary">azura: ${c.azuracast_status || '—'}</span>
                    </div>
                    <div class="lab-item-preview">${_labEscape(it.preview)}${(c.script_text || '').length > 160 ? '…' : ''}</div>
                    <div class="lab-item-actions">
                        <button type="button" class="btn btn-secondary btn-sm" onclick="showCapsuleScript(${c.id})"><i class="fa-solid fa-eye"></i> Open</button>
                        ${c.approval_status === 'pending' && approvalId ? `
                        <button type="button" class="btn btn-primary btn-sm" onclick="approveQueueItem(${approvalId})">Approve</button>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="rejectQueueItem(${approvalId})">Reject</button>` : ''}
                        ${c.approval_status === 'approved' ? `
                        <button type="button" class="btn btn-primary btn-sm" onclick="generateCapsuleAudio(${c.id}, ${!!audioPlayable})">${audioPlayable ? 'Regen audio' : 'Generate audio'}</button>` : ''}
                        ${canSendAzura ? `<button type="button" class="btn btn-primary btn-sm" onclick="sendCapsuleAzuracast(${c.id})">Send Azura</button>` : ''}
                        ${canEnsurePlayback ? `<button type="button" class="btn btn-secondary btn-sm" onclick="verifyCapsuleStream(${c.id}, false)">Verify</button>` : ''}
                        <button type="button" class="btn btn-secondary btn-sm" onclick="labArchiveCapsule(${c.id})"><i class="fa-solid fa-trash"></i></button>
                    </div>
                    ${audioPlayable ? `<audio controls src="${audioUrl}" class="lab-audio"></audio>` : ''}
                </div>`;
            }
            const a = it.meta;
            const checked = _labSelectedKeys.has(_labItemKey('approval', a.id)) ? ' checked' : '';
            return `<div class="lab-item-row lab-day-item">
                <div class="lab-item-top">
                    <label class="lab-check-label"><input type="checkbox" class="lab-item-check" data-kind="approval" data-id="${a.id}"${checked}></label>
                    <span class="badge badge-warning">Queue #${a.id}</span>
                    <span class="lab-item-meta">${_labEscape(a.status || '')} · ${_labEscape(a.created_at || '')}</span>
                </div>
                <div class="lab-item-title"><strong>${_labEscape(it.title)}</strong></div>
                <div class="lab-item-preview">${_labEscape(it.preview)}</div>
                <div class="lab-item-actions">
                    <button type="button" class="btn btn-secondary btn-sm" onclick="openApprovalScript(${a.id})"><i class="fa-solid fa-eye"></i> Open</button>
                    <button type="button" class="btn btn-primary btn-sm" onclick="approveQueueItem(${a.id})">Approve</button>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="rejectQueueItem(${a.id})">Reject</button>
                    <button type="button" class="btn btn-secondary btn-sm" onclick="labDismissApproval(${a.id})"><i class="fa-solid fa-trash"></i></button>
                </div>
            </div>`;
        }).join('');

        return `<div class="lab-day-folder" data-day="${day}">
            <button type="button" class="lab-day-folder-head" onclick="toggleLabDayFolder('${day}')">
                <i id="lab-day-chev-${day}" class="fa-solid ${open ? 'fa-chevron-down' : 'fa-chevron-right'}"></i>
                <span class="lab-day-label">${day}</span>
                <span class="lab-day-count">${byDay[day].length} item(s)</span>
            </button>
            <div id="lab-day-body-${day}" class="lab-day-folder-body ${open ? '' : 'hidden'}">${rows}</div>
        </div>`;
    }).join('');

    _restoreLabChecksToDom();
}

async function labArchiveCapsule(id) {
    if (!window.confirm(`Archive capsule #${id}?`)) return;
    try {
        const res = await adminFetch(`${API_BASE}/admin/broadcast-capsules/${id}/archive`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}',
        });
        if (!res.ok) throw new Error('archive failed');
        _labSelectedKeys.delete(_labItemKey('capsule', id));
        appendCockpitTask(`Capsule #${id} archived`, 'success');
        fetchNeenaLabData(true);
        fetchCockpitData();
    } catch (e) {
        appendCockpitTask(`Archive failed #${id}`, 'error');
    }
}

async function labDismissApproval(id) {
    if (!window.confirm(`Delete approval #${id} from queue?`)) return;
    try {
        const res = await adminFetch(`${API_BASE}/admin/approval-queue/${id}/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'dismiss' }),
        });
        if (!res.ok) throw new Error('dismiss failed');
        _labSelectedKeys.delete(_labItemKey('approval', id));
        appendCockpitTask(`Approval #${id} dismissed`, 'success');
        fetchNeenaLabData(true);
        fetchCockpitData();
    } catch (e) {
        appendCockpitTask(`Dismiss failed #${id}`, 'error');
    }
}

async function fetchStationClockPlan() {
    const el = document.getElementById('neena-lab-station-clock');
    if (!el) return;
    try {
        const res = await fetch(`${API_BASE}/neena/station-plan`);
        if (!res.ok) {
            el.innerHTML = '<p class="empty-state">Station plan unavailable.</p>';
            return;
        }
        const data = await res.json();
        const plan = data.plan;
        if (!plan || data.empty) {
            el.innerHTML = '<p class="empty-state">No active Station Clock plan. Use “4h plan”.</p>';
            return;
        }
        const blocks = Array.isArray(plan.blocks) ? plan.blocks : [];
        const rows = blocks.slice(0, 8).map((b) => {
            const st = b.status || 'pending';
            const cap = b.capsule_id ? ` · capsule #${b.capsule_id}` : '';
            return `<li><strong>${st}</strong> — ${b.title || b.kind || b.id}${cap}</li>`;
        }).join('');
        el.innerHTML = `
            <p class="lab-item-meta">${plan.horizon || ''} · ${plan.window_start || ''} → ${plan.window_end || ''} · ${blocks.length} blocks</p>
            <ul class="nc-lab-clock-list">${rows || '<li>No blocks</li>'}</ul>
        `;
    } catch (e) {
        el.innerHTML = '<p class="empty-state">Station plan load failed.</p>';
    }
}

async function createStationClockPlan() {
    try {
        const res = await fetch(`${API_BASE}/neena/station-plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ horizon: 'shift_4h', theme: '' }),
        });
        const data = await res.json().catch(() => ({}));
        appendCockpitTask(data.reply || (data.ok ? 'Station Clock plan created' : 'Plan create failed'), data.ok ? 'success' : 'error');
        await fetchStationClockPlan();
        fetchNeenaLabData(true);
    } catch (e) {
        appendCockpitTask('Station plan create failed', 'error');
    }
}

async function draftNextStationPlanBlock() {
    try {
        const res = await fetch(`${API_BASE}/neena/station-plan/draft-next`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const data = await res.json().catch(() => ({}));
        appendCockpitTask(data.reply || (data.ok ? 'Block drafted' : 'Draft failed'), data.ok ? 'success' : 'error');
        await fetchStationClockPlan();
        fetchNeenaLabData(true);
    } catch (e) {
        appendCockpitTask('Draft next block failed', 'error');
    }
}

async function fetchNeenaLabData(force) {
    try {
        fetchStationClockPlan();
        const res = await fetch(`${API_BASE}/neena/lab`);
        if (!res.ok) return;
        const data = await res.json();

        const modeBadge = document.getElementById('neena-lab-mode-badge');
        if (modeBadge) {
            const labMode = data.mode || '';
            modeBadge.textContent = labMode ? labMode.replace(/_/g, ' ') : 'Not checked';
            // Mode label is informational → neutral, not amber.
            modeBadge.className = labMode
                ? (labMode === 'LOCAL_TEST_MODE' ? 'badge badge-neutral' : 'badge badge-success')
                : 'badge badge-neutral';
        }

        const taskEl = document.getElementById('neena-lab-current-task');
        if (taskEl) {
            let nextHtml;
            if (data.current_task && data.current_task.status !== 'idle') {
                nextHtml = `<p><strong>${data.current_task.title || 'Working...'}</strong> — ${data.current_task.status}</p>`;
            } else {
                nextHtml = '<p class="empty-state">Neena is idle. No active task.</p>';
            }
            if (taskEl.dataset.lastHtml !== nextHtml) {
                taskEl.innerHTML = nextHtml;
                taskEl.dataset.lastHtml = nextHtml;
            }
        }

        const readinessEl = document.getElementById('neena-lab-broadcast-readiness');
        if (readinessEl && data.broadcast_readiness) {
            const br = data.broadcast_readiness;
            const audio = br.audio || {};
            const az = br.azuracast || {};
            const ttsLabel = audio.tts_status === 'real_available' ? 'real available' : 'simulated only';
            const ttsBadge = audio.tts_status === 'real_available' ? 'success' : 'warning';
            const azLabel = az.ready_for_real_push ? 'ready' : 'missing config';
            const azBadge = az.ready_for_real_push ? 'success' : 'danger';
            const blockers = (br.blockers || []).slice(0, 4).join(', ');
            const nextHtml = `
                <div style="display:flex; flex-wrap:wrap; gap:6px; align-items:center;">
                    <span class="badge badge-${ttsBadge}">TTS: ${ttsLabel}</span>
                    <span class="badge badge-secondary">${audio.active_provider || 'unknown'}</span>
                    <span class="badge badge-${azBadge}">AzuraCast write: ${azLabel}</span>
                    ${br.real_push_ready ? '<span class="badge badge-success">real push ready</span>' : ''}
                </div>
                ${blockers ? `<div style="margin-top:4px; color: var(--warning, #e6a23c); font-size:0.85rem;">Blocked: ${blockers}</div>` : ''}
            `;
            if (readinessEl.dataset.lastHtml !== nextHtml) {
                readinessEl.innerHTML = nextHtml;
                readinessEl.dataset.lastHtml = nextHtml;
            }
        }

        _renderLabDayFolders(data, !!force);

        if (Array.isArray(data.broadcast_capsules)) {
            window.cockpitCapsulesCache = data.broadcast_capsules;
        }
        // Right-column status panels removed — no DOM rewrite for voice/schedule/tools/activity.
    } catch (e) {
        console.error('Neena Lab fetch error:', e);
    }
}


// 3. WHATSAPP LINKER GATEWAY STATUS
async function fetchWhatsAppGatewayStatus() {
    try {
        const response = await fetch(`${API_BASE}/whatsapp/status`);
        if (response.ok) {
            const data = await response.json();
            
            const badge = document.getElementById('whatsapp-linker-status-badge');
            const qrSpinner = document.getElementById('whatsapp-qr-spinner');
            const qrContainer = document.getElementById('whatsapp-qr-container');
            const qrConnected = document.getElementById('whatsapp-connected-message');
            
            // Sidebar WhatsApp indicator
            const sideDot = document.getElementById('sidebar-whatsapp-dot');
            const sideText = document.getElementById('sidebar-whatsapp-text');
            // Header WhatsApp dot — keep it truthful & consistent with the badge
            // (was previously never updated, which read as a permanent "unknown"
            // next to a CONNECTED gateway badge).
            const setWaHeaderDot = (state) => {
                const el = document.getElementById('dot-whatsapp');
                if (el) el.className = `status-dot ${state}`;
            };
            
            if (!data.gateway_running) {
                setWaHeaderDot('off');
                badge.textContent = 'GATEWAY OFFLINE';
                badge.className = 'badge badge-danger';
                sideDot.className = 'dot offline';
                sideText.textContent = 'Offline';
                
                qrSpinner.classList.remove('hidden');
                qrSpinner.innerHTML = `
                    <i class="fa-solid fa-circle-exclamation text-danger" style="font-size: 2.5rem; margin-bottom: 12px;"></i>
                    <p style="font-weight: 500;">Local WhatsApp gateway not running.</p>
                    <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">Start whatsapp gateway to show QR.</p>
                `;
                qrContainer.classList.add('hidden');
                qrConnected.classList.add('hidden');
            } else if (data.status === 'connected') {
                setWaHeaderDot('ok');
                badge.textContent = 'CONNECTED';
                badge.className = 'badge badge-success';
                sideDot.className = 'dot live';
                sideText.textContent = 'Connected';
                
                qrSpinner.classList.add('hidden');
                qrContainer.classList.add('hidden');
                qrConnected.classList.remove('hidden');
                
                document.getElementById('whatsapp-linked-phone').textContent = `Phone: ${data.phone || 'Ready'}`;
            } else if (data.status === 'qr_ready' && data.qr_code_data) {
                setWaHeaderDot('warn');
                badge.textContent = 'SCAN QR CODE';
                badge.className = 'badge badge-warning';
                sideDot.className = 'dot offline';
                sideText.textContent = 'Syncing...';
                
                qrSpinner.classList.add('hidden');
                qrConnected.classList.add('hidden');
                qrContainer.classList.remove('hidden');
                
                const qrImg = document.getElementById('whatsapp-qr-img');
                if (data.qr_code_data.startsWith('data:image/')) {
                    qrImg.src = data.qr_code_data;
                } else {
                    qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=230x230&data=${encodeURIComponent(data.qr_code_data)}`;
                }
            } else {
                setWaHeaderDot('warn');
                badge.textContent = data.status ? data.status.toUpperCase() : 'CHECKING…';
                badge.className = 'badge badge-warning';
                sideDot.className = 'dot offline';
                sideText.textContent = 'Syncing...';
                
                qrSpinner.classList.remove('hidden');
                qrSpinner.innerHTML = `
                    <i class="fa-solid fa-circle-notch fa-spin" style="font-size: 2.5rem; margin-bottom: 12px; color: var(--cyan);"></i>
                    <p>Status: ${data.status ? data.status.toUpperCase() : 'PENDING'}. Waiting for QR...</p>
                `;
                qrContainer.classList.add('hidden');
                qrConnected.classList.add('hidden');
            }
        }
    } catch (e) {
        const sideDot = document.getElementById('sidebar-whatsapp-dot');
        sideDot.className = 'dot offline';
        document.getElementById('sidebar-whatsapp-text').textContent = 'Offline';
        const waHeaderDot = document.getElementById('dot-whatsapp');
        if (waHeaderDot) waHeaderDot.className = 'status-dot off';
    }
}

async function triggerRestartWhatsAppGateway() {
    if (confirm('Kya aap sach mein WhatsApp Gateway ko restart karna chahte hain?')) {
        try {
            const response = await adminFetch(`${API_BASE}/runtime/command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command_type: 'RESTART_WHATSAPP' })
            });
            if (response.ok) {
                alert('WhatsApp gateway reboot job queued successfully. Please wait 10 seconds...');
                setTimeout(fetchWhatsAppGatewayStatus, 2000);
            }
        } catch(e) {}
    }
}


function updateModelSelectorDropdown(fallbackVerified) {
    const modelSelect = document.getElementById('chat-model-selector');
    if (!modelSelect) return;
    
    const currentVal = modelSelect.value;
    modelSelect.innerHTML = '';
    
    const optAuto = document.createElement('option');
    optAuto.value = 'auto';
    optAuto.textContent = 'Auto';
    modelSelect.appendChild(optAuto);
    
    const optFlash = document.createElement('option');
    optFlash.value = 'gemini-3.1-flash-lite';
    optFlash.textContent = 'Gemini 3.1 Flash Lite';
    modelSelect.appendChild(optFlash);
    
    if (fallbackVerified) {
        const optGemma = document.createElement('option');
        optGemma.value = 'gemma-4-31b';
        optGemma.textContent = 'Gemma 4 31B';
        modelSelect.appendChild(optGemma);
    }
    
    const optLocal = document.createElement('option');
    optLocal.value = 'local-control-only';
    optLocal.textContent = 'Local Control Only';
    modelSelect.appendChild(optLocal);
    
    if (Array.from(modelSelect.options).some(o => o.value === currentVal)) {
        modelSelect.value = currentVal;
    } else {
        modelSelect.value = 'auto';
    }
}

// 4. SETTINGS & RATES EDITING LOGIC
async function fetchStationSettingsConfig() {
    try {
        const response = await fetch(`${API_BASE}/config/status`);
        if (response.ok) {
            const data = await response.json();
            
            // Sidebar Gemini label
            const geminiDot = document.getElementById('sidebar-gemini-sidebar');
            const geminiText = document.getElementById('sidebar-gemini-text');
            if (geminiDot) {
                if (data.gemini_api_key_configured) {
                    geminiDot.className = 'dot live';
                    if (geminiText) geminiText.textContent = 'Active';
                    else geminiDot.parentNode.querySelector('strong').textContent = 'Active';
                } else {
                    geminiDot.className = 'dot offline';
                    if (geminiText) geminiText.textContent = 'Missing';
                    else geminiDot.parentNode.querySelector('strong').textContent = 'Missing';
                }
            }
            updateModelSelectorDropdown(data.fallback_model_verified);
        }
    } catch(e) {}
}

async function saveStationAPIKeys() {
    const geminiKey = document.getElementById('setting-gemini-key').value.trim();
    const elevenKey = document.getElementById('setting-elevenlabs-key').value.trim();
    
    if (!geminiKey) {
        alert('Gemini key is required to configure Neena!');
        return;
    }
    
    try {
        const response = await adminFetch(`${API_BASE}/config/key`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gemini_key: geminiKey,
                elevenlabs_key: elevenKey
            })
        });
        
        if (response.ok) {
            alert('Settings credentials successfully saved and synchronized!');
            fetchStationSettingsConfig();
        } else {
            alert('Failed to save settings.');
        }
    } catch(e) {
        alert('Server connection error saving keys.');
    }
}

async function fetchNeenaAgentFlags() {
    const list = document.getElementById('neena-agent-flags-list');
    if (!list) return;
    try {
        const response = await adminFetch(`${API_BASE}/neena/feature-flags`);
        if (!response || response.status === 401) {
            list.innerHTML = '<p class="empty-state">Unlock Command Center to manage flags.</p>';
            return;
        }
        if (!response.ok) {
            list.innerHTML = '<p class="empty-state">Flags load failed.</p>';
            return;
        }
        const data = await response.json();
        const flags = (data && data.flags) || {};
        const keys = Object.keys(flags);
        if (!keys.length) {
            list.innerHTML = '<p class="empty-state">No agent flags.</p>';
            return;
        }
        list.innerHTML = '';
        keys.forEach((key) => {
            const f = flags[key] || {};
            const row = document.createElement('div');
            row.className = 'neena-flag-row';
            const checked = f.enabled ? 'checked' : '';
            const overrideNote = f.override === null || f.override === undefined
                ? `env default: ${f.env_default ? 'on' : 'off'}`
                : `override: ${f.override ? 'on' : 'off'} (env ${f.env_default ? 'on' : 'off'})`;
            row.innerHTML = `
                <label>
                    <input type="checkbox" data-flag="${key}" ${checked} onchange="toggleNeenaAgentFlag(this)">
                    <span>
                        <span class="flag-title">${f.label || key}</span>
                        <span class="flag-desc">${f.description || ''}</span>
                        <span class="flag-meta">${key} · ${overrideNote}</span>
                    </span>
                </label>
            `;
            list.appendChild(row);
        });
    } catch (e) {
        list.innerHTML = '<p class="empty-state">Flags unavailable.</p>';
    }
}

async function toggleNeenaAgentFlag(el) {
    if (!el || !el.dataset.flag) return;
    const flag = el.dataset.flag;
    const enabled = !!el.checked;
    try {
        const response = await adminFetch(`${API_BASE}/neena/feature-flags`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ flag, enabled }),
        });
        if (!response.ok) {
            el.checked = !enabled;
            alert('Flag update failed.');
            return;
        }
        fetchNeenaAgentFlags();
        refreshOwnerWorkingContext();
    } catch (e) {
        el.checked = !enabled;
        alert('Flag update connection error.');
    }
}

async function fetchMarketRatesList() {
    const container = document.getElementById('market-rates-items-container');
    try {
        const response = await fetch(`${API_BASE}/market-rates`);
        if (response.ok) {
            const rates = await response.json();
            
            if (rates.length === 0) {
                container.innerHTML = '<p class="empty-state">No market items configured.</p>';
                return;
            }
            
            container.innerHTML = '';
            rates.forEach(item => {
                const card = document.createElement('div');
                card.className = 'rate-editor-card';
                
                card.innerHTML = `
                    <div class="rate-item-meta">
                        <h4>${item.item_name}</h4>
                        <span>Category: ${item.category.toUpperCase()} (${item.unit})</span>
                    </div>
                    <div class="rate-inputs-row">
                        <input type="text" value="${item.price}" class="input-sci price-input" id="rate-price-${item.id}">
                        <input type="text" value="${item.price_change}" class="input-sci change-input" id="rate-change-${item.id}">
                        <select class="select-trend" id="rate-trend-${item.id}">
                            <option value="up" ${item.trend === 'up' ? 'selected' : ''}>📈 Up</option>
                            <option value="down" ${item.trend === 'down' ? 'selected' : ''}>📉 Down</option>
                        </select>
                        <button class="btn btn-secondary btn-sm" onclick="saveMarketItemRate('${item.item_name}', ${item.id})">
                            Update
                        </button>
                    </div>
                `;
                container.appendChild(card);
            });
        }
    } catch (e) {
        container.innerHTML = '<p class="empty-state text-danger">Failed to connect to rates database.</p>';
    }
}

async function saveMarketItemRate(itemName, id) {
    const price = document.getElementById(`rate-price-${id}`).value.trim();
    const change = document.getElementById(`rate-change-${id}`).value.trim();
    const trend = document.getElementById(`rate-trend-${id}`).value;
    
    if (!price || !change) {
        alert('Price and Change fields cannot be empty!');
        return;
    }
    
    try {
        const response = await adminFetch(`${API_BASE}/market-rates/${encodeURIComponent(itemName)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                price: price,
                trend: trend,
                price_change: change
            })
        });
        
        if (response.ok) {
            alert(`Market rate updated successfully for ${itemName}!`);
            fetchMarketRatesList();
        } else {
            alert('Failed to update market rate.');
        }
    } catch(e) {
        alert('Network failure syncing market rates.');
    }
}

async function fetchPendingDedications() {
    try {
        const response = await fetch(`${API_BASE}/neena/dedications`);
        if (response.ok) {
            const dedications = await response.json();
            const container = document.getElementById('admin-dedications-list');
            
            if (!container) return;
            
            if (dedications.length === 0) {
                container.innerHTML = '<p class="empty-state">No pending song dedications.</p>';
                return;
            }
            
            container.innerHTML = '';
            dedications.forEach(item => {
                const row = document.createElement('div');
                row.className = 'dedication-item-row';
                row.innerHTML = `
                    <div>Listener <strong>${item.listener_name}</strong> from <strong>${item.region}</strong> is requesting:</div>
                    <div style="margin-top: 4px; font-weight: 600; color: var(--cyan);"><i class="fa-solid fa-music"></i> ${item.song_title}</div>
                    ${item.message ? `<div style="margin-top: 4px; font-style: italic; color: var(--text-muted); opacity: 0.85;">"${item.message}"</div>` : ''}
                    <div class="meta">
                        <span>Dedicated to: <strong>${item.dedicated_to}</strong></span>
                        <span>${new Date(item.created_at || Date.now()).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                    </div>
                `;
                container.appendChild(row);
            });
        }
    } catch (e) {
        console.error("Failed to fetch song dedications:", e);
    }
}

let isBackendOffline = false;
let backendRetryCountdown = 5;
let offlineCountdownInterval = null;

async function checkBackendHealth() {
    try {
        const res = await fetch(`${API_BASE}/config/status`, { cache: 'no-store' });
        if (res.ok) {
            setBackendOfflineState(false);
            return true;
        }
    } catch (e) {
        // network error
    }
    setBackendOfflineState(true);
    return false;
}

function setBackendOfflineState(offline) {
    if (offline === isBackendOffline) return;
    isBackendOffline = offline;
    
    const micBtn = document.getElementById('cockpit-mic-btn');
    const pills = document.querySelectorAll('.cockpit-quick-pills button');
    const manualInput = document.getElementById('owner-console-input');
    const manualBtn = document.querySelector('.chat-input-bar button');
    const unlockPhrase = document.getElementById('cockpit-unlock-phrase-input');
    const unlockBtn = document.querySelector('#cockpit-manual-unlock-panel button');
    const testVoiceBtn = document.getElementById('btn-test-voice');
    const diagnosticBtns = document.querySelectorAll('#launch-status-badges button');
    const sidebarServerDot = document.getElementById('sidebar-server-dot');
    const sidebarServerText = document.getElementById('sidebar-server-text');
    
    if (offline) {
        // Show Offline status in UI
        setNeenaState('error', 'Backend offline / recovering');
        if (sidebarServerDot) {
            sidebarServerDot.className = 'dot offline';
            sidebarServerText.textContent = 'Offline';
        }
        
        // Disable controls
        if (micBtn) micBtn.disabled = true;
        pills.forEach(btn => btn.disabled = true);
        if (manualInput) manualInput.disabled = true;
        if (manualBtn) manualBtn.disabled = true;
        if (unlockPhrase) unlockPhrase.disabled = true;
        if (unlockBtn) unlockBtn.disabled = true;
        if (testVoiceBtn) testVoiceBtn.disabled = true;
        diagnosticBtns.forEach(btn => btn.disabled = true);
        
        // Start countdown to retry
        startOfflineRetryCountdown();
    } else {
        // Restore controls
        setNeenaState('online', 'Neena Online');
        if (sidebarServerDot) {
            sidebarServerDot.className = 'dot live';
            sidebarServerText.textContent = 'Online';
        }
        
        if (micBtn) micBtn.disabled = false;
        pills.forEach(btn => btn.disabled = false);
        if (manualInput) manualInput.disabled = false;
        if (manualBtn) manualBtn.disabled = false;
        if (unlockPhrase) unlockPhrase.disabled = false;
        if (unlockBtn) unlockBtn.disabled = false;
        if (testVoiceBtn) testVoiceBtn.disabled = false;
        diagnosticBtns.forEach(btn => btn.disabled = false);
        
        // Stop countdown
        stopOfflineRetryCountdown();
        
        // Fetch fresh data
        fetchCockpitData();
    }
}

function startOfflineRetryCountdown() {
    if (offlineCountdownInterval) clearInterval(offlineCountdownInterval);
    backendRetryCountdown = 5;
    
    updateOfflineStatusLabel();
    
    offlineCountdownInterval = setInterval(async () => {
        backendRetryCountdown--;
        if (backendRetryCountdown <= 0) {
            // Check health
            const ok = await checkBackendHealth();
            if (ok) {
                return;
            }
            backendRetryCountdown = 5;
        }
        updateOfflineStatusLabel();
    }, 1000);
}

function stopOfflineRetryCountdown() {
    if (offlineCountdownInterval) {
        clearInterval(offlineCountdownInterval);
        offlineCountdownInterval = null;
    }
}

function updateOfflineStatusLabel() {
    const label = `Backend offline / recovering. Retrying in ${backendRetryCountdown}s…`;
    setNeenaState('error', label);
}
