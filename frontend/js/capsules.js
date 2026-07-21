// ==== Orai Command Center — broadcast capsule pipeline (approval, audio, azuracast, verify, render) module ====
// Auto-split from the former monolithic app.js (M6 Phase 4c, SRP).
// Loaded as an ordered classic <script>; shares one global scope with sibling
// modules (core.js, voice.js, admin.js, cockpit.js, panels.js, app.js).

function showCapsuleScript(capsuleId) {
    const cap = (cockpitCapsulesCache || []).find(c => Number(c.id) === Number(capsuleId));
    if (!cap || !(cap.script_text || '').trim()) {
        announceNeena('Script text nahi mila is capsule ke liye.', {
            taskFeed: `Show script failed #${capsuleId}`,
            taskType: 'error',
        });
        return;
    }
    openLabScriptModal(`Capsule #${capsuleId}`, cap.script_text);
    announceNeena(`Capsule #${capsuleId} script khol di hai.`, {
        taskFeed: `Script opened #${capsuleId}`,
        taskType: 'success',
    });
}

function openLabScriptModal(title, text) {
    const modal = document.getElementById('lab-script-modal');
    const titleEl = document.getElementById('lab-script-modal-title');
    const body = document.getElementById('lab-script-modal-body');
    const ta = document.getElementById('generated-script-output');
    if (titleEl) titleEl.innerHTML = `<i class="fa-solid fa-file-lines"></i> ${title || 'Script'}`;
    if (body) body.textContent = text || '';
    if (ta) ta.value = text || '';
    if (modal) modal.classList.remove('hidden');
}

function closeLabScriptModal() {
    const modal = document.getElementById('lab-script-modal');
    if (modal) modal.classList.add('hidden');
}

function openApprovalScript(approvalId, preview) {
    const cached = (window.labApprovalCache && window.labApprovalCache[approvalId]) || '';
    const text = (cached || preview || '').trim();
    if (!text) {
        announceNeena('Is approval item me script text nahi mila.', { taskType: 'error' });
        return;
    }
    openLabScriptModal(`Approval #${approvalId}`, text);
}


async function approveQueueItem(id) {
    try {
        const response = await adminFetch(`${API_BASE}/admin/approval-queue/${id}/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'approve' })
        });
        if (response.ok) {
            appendCockpitTask(`Approval #${id} approved`, 'success');
            await announceNeena(`Approval #${id} approve ho gaya. Ab audio generate next step hai.`, {
                taskFeed: `Approval #${id} approved`,
                taskType: 'success',
            });
            fetchNeenaLabData();
            fetchCockpitData();
        } else {
            const err = await response.json().catch(() => ({}));
            const isServiceError = (response.status === 503 || response.status === 502 || response.status === 504);
            const msg = isServiceError ? 'Approval service unavailable, protected action blocked.' : `Approval fail: ${err.detail || 'unknown error'}`;
            await announceNeena(msg, { taskType: 'error' });
        }
    } catch(e) {
        await announceNeena('Approval service unavailable / degraded', { taskType: 'error' });
    }
}

async function rejectQueueItem(id) {
    if (confirm('Kya aap sach mein is script draft ko reject karna chahte hain?')) {
        try {
            const response = await adminFetch(`${API_BASE}/admin/approval-queue/${id}/action`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'reject' })
            });
            if (response.ok) {
                alert('Item rejected successfully.');
                fetchNeenaLabData();
            } else {
                const err = await response.json().catch(() => ({}));
                const isServiceError = (response.status === 503 || response.status === 502 || response.status === 504);
                const msg = isServiceError ? 'Approval service unavailable, protected action blocked.' : `Rejection failed: ${err.detail || 'unknown error'}`;
                alert(msg);
            }
        } catch(e) {
            alert('Approval service unavailable / degraded');
        }
    }
}

async function ensureCapsulePlayback(capsuleId, mode = 'auto', watchSeconds = 0) {
    const label = mode === 'queue_now' ? 'Queue Now + watch' : 'Ensure Playback';
    if (mode === 'queue_now' && !confirm('Media ko AzuraCast queue me add karna hai (immediate attempt)?')) return;
    try {
        const url = `${API_BASE}/broadcast/capsules/${capsuleId}/ensure-playback?mode=${encodeURIComponent(mode)}&watch_seconds=${watchSeconds}`;
        const response = await adminFetch(url, { method: 'POST' });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const isServiceError = (response.status === 503 || response.status === 502 || response.status === 504);
            const msg = isServiceError ? 'Approval service unavailable, protected action blocked.' : (data.detail || data.message || 'Playback control blocked.');
            alert(msg);
            fetchNeenaLabData();
            return;
        }
        const v = data.verification || {};
        alert(`${label}: ${data.playback_status}\n${data.message || ''}\nStream verify: ${data.stream_verification_status || v.verification_status || 'pending'}`);
        fetchNeenaLabData();
        fetchCockpitData();
    } catch (e) {
        alert('Approval service unavailable, protected action blocked.');
    }
}

async function verifyCapsuleStream(capsuleId, watch = false) {
    const watchSeconds = watch ? 60 : 0;
    const label = watch ? `Watch ${watchSeconds}s` : 'Verify';
    if (watch && !confirm(`Stream verify with ${watchSeconds}s polling? AutoDJ rotation ka wait hoga.`)) return;
    if (typeof setNcClientActivity === 'function') {
        setNcClientActivity('stream_verify', `Verifying stream — capsule #${capsuleId}`);
    }
    try {
        const url = `${API_BASE}/broadcast/capsules/${capsuleId}/verify-stream?watch_seconds=${watchSeconds}`;
        const response = await adminFetch(url, { method: 'POST' });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const isServiceError = (response.status === 503 || response.status === 502 || response.status === 504);
            const msg = isServiceError ? 'Approval service unavailable, protected action blocked.' : (data.detail || data.message || 'Stream verification blocked.');
            alert(msg);
            if (typeof setNcClientActivity === 'function') setNcClientActivity('error', 'Verify failed');
            fetchNeenaLabData();
            return;
        }
        const np = data.now_playing_snapshot || {};
        alert(`${label}: ${data.verification_status || data.stream_verification_status}\n${data.message || ''}\nNow playing: ${np.artist ? np.artist + ' - ' : ''}${np.title || '?'}\nStream online: ${data.stream_reachable ? 'yes' : 'no'}`);
        if (typeof setNcClientActivity === 'function') {
            const ok = (data.verification_status || data.stream_verification_status) === 'verified';
            setNcClientActivity(ok ? 'success' : null, ok ? 'Stream verified' : null);
        }
        fetchNeenaLabData();
        fetchCockpitData();
        if (typeof fetchNeenaLiveHome === 'function') fetchNeenaLiveHome();
    } catch (e) {
        if (typeof setNcClientActivity === 'function') setNcClientActivity('error', 'Verify failed');
        alert('Approval service unavailable, protected action blocked.');
    }
}

async function sendCapsuleAzuracast(capsuleId) {
    if (!confirm('Approved real audio ko AzuraCast par push karna hai? Stream verification abhi pending rahegi.')) return;
    if (typeof setNcClientActivity === 'function') {
        setNcClientActivity('azura_push', `Pushing to AzuraCast — capsule #${capsuleId}`);
    }
    try {
        const response = await adminFetch(`${API_BASE}/broadcast/capsules/${capsuleId}/send-azuracast`, {
            method: 'POST'
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.blocked || data.success === false) {
            const isServiceError = (response.status === 503 || response.status === 502 || response.status === 504);
            const msg = isServiceError ? 'Approval service unavailable, protected action blocked.' : (data.message || data.error_message || data.detail || 'AzuraCast push blocked or failed.');
            alert(msg);
            if (typeof setNcClientActivity === 'function') setNcClientActivity('error', 'AzuraCast push blocked');
            fetchNeenaLabData();
            return;
        }
        alert(`AzuraCast: ${data.azuracast_status || data.mode}\n${data.message || ''}\n${data.next_step || ''}`);
        if (typeof setNcClientActivity === 'function') setNcClientActivity('success', 'AzuraCast push done');
        fetchNeenaLabData();
        fetchCockpitData();
        if (typeof fetchNeenaLiveHome === 'function') fetchNeenaLiveHome();
    } catch (e) {
        if (typeof setNcClientActivity === 'function') setNcClientActivity('error', 'AzuraCast push failed');
        alert('Approval service unavailable, protected action blocked.');
    }
}

async function generateCapsuleAudio(capsuleId, regenerate = false) {
    const endpoint = regenerate ? 'regenerate-audio' : 'generate-audio';
    if (typeof setNcClientActivity === 'function') {
        setNcClientActivity('audio_gen', `Generating audio — capsule #${capsuleId}`);
    }
    try {
        const response = await adminFetch(`${API_BASE}/broadcast/capsules/${capsuleId}/${endpoint}`, {
            method: 'POST'
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            const isServiceError = (response.status === 503 || response.status === 502 || response.status === 504);
            const msg = isServiceError ? 'Approval service unavailable, protected action blocked.' : (data.detail || data.message || 'Audio generation blocked or failed.');
            alert(msg);
            if (typeof setNcClientActivity === 'function') setNcClientActivity('error', 'Audio generation failed');
            return;
        }
        const level = data.audio_truth_level || 'unknown';
        const msg = data.message || 'Audio generation complete.';
        alert(`Audio: ${level}\n${msg}\nProduction asset: no (preview only)`);
        if (typeof setNcClientActivity === 'function') setNcClientActivity('success', 'Audio ready');
        fetchNeenaLabData();
        fetchCockpitData();
        if (typeof fetchNeenaLiveHome === 'function') fetchNeenaLiveHome();
    } catch (e) {
        if (typeof setNcClientActivity === 'function') setNcClientActivity('error', 'Audio generation failed');
        alert('Approval service unavailable, protected action blocked.');
    }
}

async function generateVoicePreview(id) {
    try {
        const response = await adminFetch(`${API_BASE}/admin/approval-queue/${id}/voice-preview`, {
            method: 'POST'
        });
        if (response.ok) {
            const data = await response.json();
            const status = data.preview_status || data.status || 'unknown';
            const message = data.message || 'Voice preview action completed.';
            alert(`Voice preview status: ${status}\n${message}`);
            fetchNeenaLabData();
        } else {
            const err = await response.json().catch(() => ({}));
            const isServiceError = (response.status === 503 || response.status === 502 || response.status === 504);
            const msg = isServiceError ? 'Approval service unavailable, protected action blocked.' : (err.detail || 'unknown error');
            alert(`Voice generation failed: ${msg}`);
        }
    } catch(e) {
        alert('Approval service unavailable, protected action blocked.');
    }
}

async function getLatestCapsule() {
    if (cockpitCapsulesCache.length) return cockpitCapsulesCache[0];
    try {
        const res = await fetch(`${API_BASE}/broadcast/capsules?limit=5`);
        if (res.ok) {
            const data = await res.json();
            cockpitCapsulesCache = data.capsules || [];
            return cockpitCapsulesCache[0] || null;
        }
    } catch (e) { /* ignore */ }
    return null;
}

async function tryCapsuleVoiceShortcut(msg) {
    // M4-A1: Natural owner commands must go through backend model-based command interpreter.
    return false;
}

async function runCapsuleVoiceAction(action) {
    const cap = await getLatestCapsule();
    if (!cap) {
        announceNeena('Koi capsule nahi mila.', { taskType: 'error' });
        return;
    }
    if (action === 'verify') await verifyCapsuleStreamSilent(cap.id, 30);
    fetchCockpitData();
}

async function sendCapsuleAzuracastSilent(capsuleId) {
    try {
        const response = await adminFetch(`${API_BASE}/broadcast/capsules/${capsuleId}/send-azuracast`, { method: 'POST' });
        const data = await response.json().catch(() => ({}));
        appendCockpitTask(data.message || data.azuracast_status || 'AzuraCast push', data.success ? 'success' : 'error');
        announceNeena(data.message || '', { taskFeed: 'Capsule action', taskType: 'success' });
    } catch (e) {
        appendCockpitTask('AzuraCast push failed', 'error');
    }
}

async function ensureCapsulePlaybackSilent(capsuleId, mode, watch) {
    try {
        const url = `${API_BASE}/broadcast/capsules/${capsuleId}/ensure-playback?mode=${mode}&watch_seconds=${watch}`;
        const response = await adminFetch(url, { method: 'POST' });
        const data = await response.json().catch(() => ({}));
        appendCockpitTask(data.message || data.playback_status || 'Playback', 'info');
        announceNeena(data.message || '', { taskFeed: 'Capsule action', taskType: 'success' });
    } catch (e) {
        appendCockpitTask('Playback control failed', 'error');
    }
}

async function verifyCapsuleStreamSilent(capsuleId, watchSeconds) {
    if (typeof setNcClientActivity === 'function') {
        setNcClientActivity('stream_verify', 'Verifying live stream…');
    }
    setNeenaState('executing', 'Verifying stream…');
    try {
        const url = `${API_BASE}/broadcast/capsules/${capsuleId}/verify-stream?watch_seconds=${watchSeconds}`;
        const response = await adminFetch(url, { method: 'POST' });
        const data = await response.json().catch(() => ({}));
        appendCockpitTask(data.message || data.verification_status, data.verification_status === 'verified' ? 'success' : 'info');
        announceNeena(data.message || '', { taskFeed: 'Capsule action', taskType: 'success' });
        if (data.verification_status === 'verified') {
            setNeenaState('online', 'Neena Online');
            if (typeof setNcClientActivity === 'function') setNcClientActivity('success', 'Stream verified');
        } else {
            setNeenaState('online', 'Neena Online');
            if (typeof setNcClientActivity === 'function') setNcClientActivity(null);
        }
    } catch (e) {
        appendCockpitTask('Stream verify failed', 'error');
        setNeenaState('error', 'Verify failed');
        if (typeof setNcClientActivity === 'function') setNcClientActivity('error', 'Verify failed');
    }
}

function pipelineStepClass(done, active) {
    if (done) return 'step-done';
    if (active) return 'step-active';
    return 'step-pending';
}

function renderCockpitPipeline(capsules) {
    const el = document.getElementById('cockpit-pipeline-list');
    if (!el) return;
    cockpitCapsulesCache = capsules || [];
    if (!capsules || !capsules.length) {
        el.innerHTML = '<p class="empty-state">No broadcast capsules yet.</p>';
        return;
    }
    el.innerHTML = capsules.slice(0, 4).map(c => {
        const steps = [
            { label: 'Script', done: !!(c.script_text) },
            { label: 'Approval', done: c.approval_status === 'approved', active: c.approval_status === 'pending' },
            { label: 'Audio', done: ['real', 'simulated'].includes(c.audio_truth_level), active: c.approval_status === 'approved' && !c.audio_playable },
            { label: 'Azura Push', done: ['uploaded', 'scheduled'].includes(c.azuracast_status) },
            { label: 'Queue', done: ['queued', 'playlist_assigned', 'verified'].includes(c.playback_status || '') },
            { label: 'Stream Verify', done: c.stream_verification_status === 'verified' },
        ];
        const stepsHtml = steps.map(s =>
            `<div class="pipeline-step ${pipelineStepClass(s.done, s.active)}"><span>${s.label}</span></div>`
        ).join('');
        const actions = (c.azuracast_status === 'uploaded' || c.azuracast_status === 'scheduled') ? `
            <button class="btn btn-secondary btn-sm" onclick="ensureCapsulePlayback(${c.id}, 'auto', 0)">Queue</button>
            <button class="btn btn-secondary btn-sm" onclick="verifyCapsuleStream(${c.id}, true)">Watch</button>` : '';
        return `<div class="pipeline-capsule-card">
            <div class="pipeline-header">
                <strong>#${c.id}</strong> ${c.capsule_type || ''}
                <span class="badge badge-secondary">${c.stream_verification_status || 'unknown'}</span>
            </div>
            <div class="pipeline-timeline">${stepsHtml}</div>
            <div class="pipeline-actions">
                <button class="btn btn-secondary btn-sm" onclick="showCapsuleScript(${c.id})">Show Script</button>
                ${c.approval_status === 'pending' ? `<button class="btn btn-primary btn-sm" onclick="approveQueueItem(${c.approval_queue_id})">Approve</button>` : ''}
                ${c.approval_status === 'approved' ? `<button class="btn btn-primary btn-sm" onclick="generateCapsuleAudio(${c.id}, ${!!c.audio_playable})">Audio</button>` : ''}
                ${c.azuracast_push_allowed ? `<button class="btn btn-primary btn-sm" onclick="sendCapsuleAzuracast(${c.id})">AzuraCast</button>` : ''}
                ${actions}
            </div>
        </div>`;
    }).join('');
}

function updateCockpitReadiness(data) {
    const brain = document.getElementById('ready-brain');
    const tts = document.getElementById('ready-tts');
    const az = document.getElementById('ready-azura');
    const stream = document.getElementById('ready-stream');
    const verified = document.getElementById('ready-verified-capsule');
    const blocker = document.getElementById('ready-blocker');
    if (!data) return;
    const launch = data.launch || {};
    const readiness = data.broadcast_readiness || {};
    const audio = readiness.audio || {};
    const azCfg = readiness.azuracast || {};
    const brainState = launch.brain_status || (launch.backend === 'online' ? 'ready' : launch.backend || '—');
    if (brain) brain.textContent = brainState;
    if (tts) {
        const ttsLabel = audio.tts_status === 'real_available' ? 'real' : (audio.can_produce_real_audio ? 'real' : 'simulated');
        tts.textContent = ttsLabel;
    }
    if (az) az.textContent = azCfg.ready_for_real_push ? 'ready' : 'missing';
    if (stream) stream.textContent = data.stream_online ? 'online' : 'offline';
    if (verified) verified.textContent = data.last_verified_capsule_id ? `#${data.last_verified_capsule_id}` : '—';
    if (blocker) {
        const blockers = (readiness.blockers || []).slice(0, 2).join(', ');
        blocker.textContent = blockers ? `Blocker: ${blockers}` : '';
    }
    setStatusDot('dot-backend', launch.backend === 'online');
    setStatusDot('dot-tts', audio.tts_status === 'real_available' || audio.can_produce_real_audio);
    setStatusDot('dot-azura', !!azCfg.ready_for_real_push);
    setStatusDot('dot-stream', !!data.stream_online);
}

function setStatusDot(id, ok) {
    const el = document.getElementById(id);
    if (el) el.className = `status-dot ${ok ? 'ok' : 'warn'}`;
}

function updateSidebarServerBadge(online) {
    const serverDot = document.getElementById('sidebar-server-dot');
    const serverText = document.getElementById('sidebar-server-text');
    if (!serverDot || !serverText) return;
    if (online) {
        serverDot.className = 'dot live';
        serverText.textContent = 'Online';
    } else {
        serverDot.className = 'dot offline';
        serverText.textContent = 'Offline';
    }
}

async function fetchCockpitData() {
    if (isBackendOffline) return;
    try {
        const res = await fetch(`${API_BASE}/neena/cockpit-status`, { cache: 'no-store' });
        if (res.ok) {
            const data = await res.json();
            updateCockpitReadiness(data);
            renderCockpitPipeline(data.capsules || []);
            const backendOnline = (data.launch || {}).backend === 'online';
            updateSidebarServerBadge(backendOnline);
            if (data.local_stats) updatePollingLoadMode(data.local_stats);
            maybeClearLiveStateStale();
            if (typeof syncNeenaCorePlaceholders === 'function') syncNeenaCorePlaceholders(data);
            return;
        }
    } catch (e) { /* fallback */ }
    try {
        const [capRes, readyRes] = await Promise.all([
            fetch(`${API_BASE}/broadcast/capsules?limit=5`),
            fetch(`${API_BASE}/broadcast/audio/readiness`),
        ]);
        if (capRes.ok) {
            const caps = await capRes.json();
            renderCockpitPipeline(caps.capsules || []);
        }
        if (readyRes.ok) {
            const r = await readyRes.json();
            updateCockpitReadiness({ broadcast_readiness: r.readiness, launch: { backend: 'online', brain_status: 'ready' } });
            updateSidebarServerBadge(true);
            if (typeof syncNeenaCorePlaceholders === 'function') {
                syncNeenaCorePlaceholders({ broadcast_readiness: r.readiness, launch: { backend: 'online' } });
            }
        }
    } catch (e) { /* silent */ }
}
