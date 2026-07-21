// ==== Orai Command Center — owner console chat + background-job completion delivery module ====
// Auto-split from the former monolithic app.js (M6 Phase 4c, SRP).
// Loaded as an ordered classic <script>; shares one global scope with sibling
// modules (core.js, voice.js, admin.js, cockpit.js, panels.js, app.js).

async function tryLocalLiveOpsBeforeChat(msg) {
    try {
        const response = await adminFetchWithTimeout(`${API_BASE}/neena/live-ops/quick`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg }),
        }, LIVE_STATE_TIMEOUT_MS);
        if (!response.ok) return false;
        const data = await response.json();
        if (!data.handled) return false;
        removeNeenaLoader();
        const isBackground = data.mode === 'background' && data.job_id;
        await announceNeena(data.reply, {
            appendChat: true,
            meta: data,
            ui_action: isBackground ? null : data.ui_action,
            taskFeed: isBackground ? 'Creative job queued' : 'Local answer (no model)',
            taskType: isBackground ? 'command' : 'success',
            voicePriority: isBackground ? 'progress' : 'final',
            voiceDedupeKey: isBackground ? `job_start_${data.job_id}` : null,
        });
        if (isBackground) {
            handleNeenaUiAction(
                data.ui_action || { type: 'poll_cockpit_job', job_id: data.job_id, action_key: 'creative_job' },
                data
            );
        } else if (data.ui_action) {
            handleNeenaUiAction(data.ui_action, data);
        }
        updateProviderStatusWidget(data);
        fetchCockpitData();
        fetchNeenaLabData();
        setNeenaState('online', 'Neena Online');
        return true;
    } catch (e) {
        return false;
    }
}


// 1. CHAT CONSOLE LOGIC
// 1. CHAT CONSOLE LOGIC
let activeLoaderIntervals = [];
let neenaChatInFlight = false;


let lastCockpitJobProgress = '';

// Server-side follow-through: drain finished background-job results that were
// not delivered live (tab reloaded, poll window expired). Ensures Neena reports
// "result aa gaya" instead of going silent after "job start ho gaya".
async function drainPendingCompletions() {
    try {
        const response = await adminFetch(`${API_BASE}/neena/pending-completions`);
        if (!response || response.status === 401) return;
        const data = await response.json().catch(() => ({}));
        const completions = (data && data.completions) || [];
        for (const job of completions) {
            if (!job || !job.owner_message) continue;
            const isFail = job.status === 'failed';
            deliverNeenaReply(job.owner_message, {
                appendChat: true,
                meta: { job_id: job.job_id, action: job.action, delivery: 'followup' },
                voicePriority: isFail ? 'error' : 'final',
                voiceDedupeKey: `job_followup_${job.job_id}`,
            });
            appendCockpitTask(
                `${job.action || 'Background job'} result: ${isFail ? 'issue' : 'ready'}`,
                isFail ? 'error' : 'success'
            );
        }
    } catch (e) {
        /* best-effort */
    }
}

async function pollCockpitJobInBackground(jobId, ui, actionKey) {
    const deadline = Date.now() + COCKPIT_JOB_POLL_MAX_MS;
    if (actionKey === 'verify_latest_stream') {
        setNeenaState('executing', 'Stream verification chal rahi hai…');
    } else if (actionKey === 'creative_job') {
        setNeenaState('thinking', 'Creative generation chal rahi hai…');
    } else {
        setNeenaState('thinking', 'Background job chal rahi hai…');
    }
    while (Date.now() < deadline) {
        await sleepMs(COCKPIT_JOB_POLL_MS);
        try {
            const response = await adminFetch(`${API_BASE}/neena/cockpit-jobs/${jobId}`);
            if (response.status === 401) return;
            const job = await response.json().catch(() => ({}));
            if (job.progress_message && job.progress_message !== lastCockpitJobProgress) {
                lastCockpitJobProgress = job.progress_message;
                showCockpitReply(job.progress_message);
            }
            if (job.status === 'succeeded') {
                lastCockpitJobProgress = '';
                deliverNeenaReply(job.owner_message || ui.success, {
                    appendChat: true,
                    meta: { job_id: jobId, action: actionKey },
                    voicePriority: 'final',
                    voiceDedupeKey: `job_final_${jobId}`,
                });
                appendCockpitTask(ui.success, 'success');
                setNeenaState('online', 'Neena Online');
                fetchCockpitData();
                fetchNeenaLabData();
                return;
            }
            if (job.status === 'failed') {
                lastCockpitJobProgress = '';
                deliverNeenaReply(job.owner_message || job.error_summary || ui.fail, {
                    appendChat: true,
                    meta: { job_id: jobId, action: actionKey },
                    voicePriority: 'error',
                    voiceDedupeKey: `job_fail_${jobId}`,
                });
                appendCockpitTask(ui.fail, 'error');
                setNeenaState('error', 'Error');
                return;
            }
        } catch (e) {
            /* keep polling */
        }
    }
    const timeoutMsg = ui.timeoutPoll || ui.timeout || 'Background job timeout.';
    deliverNeenaReply(timeoutMsg, { appendChat: true, meta: { job_id: jobId } });
    appendCockpitTask(timeoutMsg, 'error');
    setNeenaState('online', 'Neena Online');
}

function appendNeenaLoader() {
    const container = document.getElementById('console-chat-messages');
    if (!container) return;
    
    const row = document.createElement('div');
    row.className = 'chat-row assistant loading-row';
    row.id = 'neena-loading-row';
    
    const avatar = document.createElement('div');
    avatar.className = 'avatar-tag';
    avatar.textContent = 'N';
    
    const loaderCard = document.createElement('div');
    loaderCard.className = 'neena-trace-loader';
    
    loaderCard.innerHTML = `
        <div class="loader-header">
            <i class="fa-solid fa-circle-notch fa-spin"></i> Neena is processing...
        </div>
        <div class="loader-steps">
            <div class="loader-step-item active" id="loader-step-received">
                <i class="fa-solid fa-spinner fa-spin"></i> Message received
            </div>
            <div class="loader-step-item" id="loader-step-routing">
                <i class="fa-regular fa-circle"></i> Intent routing...
            </div>
            <div class="loader-step-item" id="loader-step-tools">
                <i class="fa-regular fa-circle"></i> Checking tools & database...
            </div>
            <div class="loader-step-item" id="loader-step-llm">
                <i class="fa-regular fa-circle"></i> Querying Gemini API...
            </div>
            <div class="loader-step-item" id="loader-step-final">
                <i class="fa-regular fa-circle"></i> Finalizing response...
            </div>
        </div>
    `;
    
    row.appendChild(avatar);
    row.appendChild(loaderCard);
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
    
    // Animate the steps
    const step1 = document.getElementById('loader-step-received');
    const step2 = document.getElementById('loader-step-routing');
    const step3 = document.getElementById('loader-step-tools');
    const step4 = document.getElementById('loader-step-llm');
    const step5 = document.getElementById('loader-step-final');
    
    // Clear any previous intervals/timeouts
    activeLoaderIntervals.forEach(t => clearTimeout(t));
    activeLoaderIntervals = [];
    
    // Animate steps
    activeLoaderIntervals.push(setTimeout(() => {
        if (!step1) return;
        step1.className = 'loader-step-item completed';
        step1.innerHTML = `<i class="fa-solid fa-circle-check"></i> Message received`;
        step2.className = 'loader-step-item active';
        step2.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Intent routing...`;
    }, 250));
    
    activeLoaderIntervals.push(setTimeout(() => {
        if (!step2) return;
        step2.className = 'loader-step-item completed';
        step2.innerHTML = `<i class="fa-solid fa-circle-check"></i> Intent routed`;
        step3.className = 'loader-step-item active';
        step3.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Checking tools & database...`;
    }, 600));
    
    activeLoaderIntervals.push(setTimeout(() => {
        if (!step3) return;
        step3.className = 'loader-step-item completed';
        step3.innerHTML = `<i class="fa-solid fa-circle-check"></i> Pre-routing & tools verification done`;
        step4.className = 'loader-step-item active';
        step4.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Querying Gemini API...`;
    }, 1100));
    
    activeLoaderIntervals.push(setTimeout(() => {
        if (!step4) return;
        step4.className = 'loader-step-item completed';
        step4.innerHTML = `<i class="fa-solid fa-circle-check"></i> Creative context compiled`;
        step5.className = 'loader-step-item active';
        step5.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Finalizing response...`;
    }, 2500));
}

function removeNeenaLoader() {
    const loaderRow = document.getElementById('neena-loading-row');
    if (loaderRow) {
        loaderRow.remove();
    }
    activeLoaderIntervals.forEach(t => clearTimeout(t));
    activeLoaderIntervals = [];
}

async function submitOwnerConsoleMessage() {
    const inputEl = document.getElementById('owner-console-input');
    const msg = inputEl.value.trim();
    if (!msg) return;
    if (neenaChatInFlight) {
        // Never silently drop a quick 2nd command: keep the typed text and tell the owner.
        appendCockpitTask('Neena abhi pichhla jawab de rahi hai — ek second ruk kar dobara bhej dijiye.', 'info');
        showCockpitReply('Ek second sir, main abhi pichhla jawab de rahi hoon. Poora hote hi ye command bhej dijiye.');
        return;
    }
    if (!isCommandCenterUnlocked()) {
        notifyAdminLocked();
        return;
    }
    
    inputEl.value = '';
    const routed = await tryCapsuleVoiceShortcut(msg);
    if (routed) return;

    appendChatMessage('user', msg);
    appendNeenaLoader();

    neenaChatInFlight = true;
    setQuickActionsDisabled(true);
    const inputElCreative = document.getElementById('owner-console-input');
    const isCreative = inputElCreative && inputElCreative.dataset.creativeCommand === '1';
    
    transitionToState('PROCESSING', isCreative ? 'Neena creative script generate kar rahi hai…' : 'Processing command…');
    appendCockpitTask(`Command: ${msg.substring(0, 80)}`, 'command');

    const localHandled = await tryLocalLiveOpsBeforeChat(msg);
    if (localHandled) {
        neenaChatInFlight = false;
        setQuickActionsDisabled(false);
        removeNeenaLoader();
        if (currentState === 'PROCESSING') {
            transitionToState('IDLE');
        }
        return;
    }

    await announceNeena(isCreative ? 'Script generate ho rahi hai…' : null, {
        showCockpit: !!isCreative,
        speak: isCreative,
        taskFeed: isCreative ? 'Processing creative command…' : null,
        voicePriority: 'progress',
    });
    
    const controller = new AbortController();
    activeChatAbortController = controller;
    const timeoutId = setTimeout(() => controller.abort(), NEENA_CHAT_TIMEOUT_MS);
    
    try {
        const modelSelect = document.getElementById('chat-model-selector');
        const selectedModel = modelSelect ? modelSelect.value : 'auto';
        const response = await adminFetch(`${API_BASE}/neena/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg, model: selectedModel }),
            signal: controller.signal
        });
        
        removeNeenaLoader();
        
        if (response.status === 401) {
            transitionToState('LOCKED');
            await announceNeena('Sir, Command Center locked hai. Pehle owner unlock phrase boliye.', {
                taskFeed: 'Auth locked',
                taskType: 'error',
                speak: true,
            });
            return;
        }
        
        if (response.ok) {
            const data = await response.json();
            
            // Phase 4: response_id guard
            const responseId = data.response_id || data.id || null;
            if (responseId && responseId === lastSpokenResponseId) {
                return;
            }
            lastSpokenResponseId = responseId;
            
            const reply = data.reply;
            const processedReply = processNeenaReplyText(reply);
            const isBackground = data.mode === 'background' && data.job_id;
            if (isBackground) {
                deliverNeenaReply(processedReply, {
                    appendChat: true,
                    meta: data,
                    voicePriority: 'progress',
                    voiceDedupeKey: `job_start_${data.job_id}`,
                    responseId: responseId
                });
                handleNeenaUiAction(
                    data.ui_action || { type: 'poll_cockpit_job', job_id: data.job_id, action_key: 'creative_job' },
                    data
                );
            } else {
                deliverNeenaReply(processedReply, {
                    appendChat: true,
                    meta: data,
                    ui_action: data.ui_action,
                    voicePriority: 'final',
                    responseId: responseId
                });
                if (data.job_id && !data.ui_action) {
                    handleNeenaUiAction(
                        { type: 'poll_cockpit_job', job_id: data.job_id, action_key: 'verify_latest_stream' },
                        data
                    );
                }
            }
            updateProviderStatusWidget(data);
            appendCockpitTask(isBackground ? 'Background job started' : 'Neena replied', 'success');
            
            if (currentState === 'PROCESSING') {
                transitionToState('IDLE');
            }
            
            if (data.command_triggered) {
                setTimeout(fetchTelemetryStats, 1000);
            }
            fetchCockpitData();
            fetchNeenaLabData();
        } else {
            appendCockpitTask('Chat HTTP error', 'error');
            transitionToState('ERROR', 'Error');
            // Rare: HTTP non-OK. Dual models should still have answered — this is transport/auth.
            deliverNeenaReply('Sir, Command Center request fail hui (HTTP). Unlock/session check karke ek baar dobara bhejiye.');
        }
    } catch (e) {
        removeNeenaLoader();
        if (e && e.name === 'AbortError') {
            if (currentState === 'LISTENING') {
                const title = document.getElementById('neena-state-title');
                if (title) title.textContent = 'Cancelled. Listening…';
            } else {
                // Browser aborted waiting — usually slow internet or local hang, not "no models".
                deliverNeenaReply('Sir, jawab aane me bahut time lag gaya (network/slow). Main yahin hoon — thoda ruk kar dobara bhejiye.', { appendChat: true });
                transitionToState('ERROR', 'Timeout');
            }
            appendCockpitTask('Timeout or Cancelled', 'error');
        } else {
            transitionToState('ERROR', 'Connection Error');
            deliverNeenaReply('Sir, browser se server tak connection toot gaya. Net/VM check karke dobara try kariye.');
            appendCockpitTask('Connection failed', 'error');
        }
    } finally {
        clearTimeout(timeoutId);
        neenaChatInFlight = false;
        setQuickActionsDisabled(false);
        const inputClear = document.getElementById('owner-console-input');
        if (inputClear) inputClear.dataset.creativeCommand = '';
        activeChatAbortController = null;
        // Plan §4: error → idle only on owner next action (not immediately after fail).
        if (
            currentState !== 'LISTENING'
            && currentState !== 'SPEAKING'
            && currentState !== 'WAITING_FOR_FOLLOWUP'
            && currentState !== 'ERROR'
        ) {
            transitionToState('IDLE');
        }
        refreshOwnerWorkingContext();
    }
}

function handleConsoleInputKey(event) {
    if (event.key === 'Enter') {
        submitOwnerConsoleMessage();
    }
}

function appendChatMessage(sender, text, metadata = null) {
    const container = document.getElementById('console-chat-messages');
    if (!container) return;
    
    const row = document.createElement('div');
    row.className = `chat-row ${sender}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'avatar-tag';
    avatar.textContent = sender === 'assistant' ? 'N' : 'U';
    
    row.appendChild(avatar);
    
    if (sender === 'assistant') {
        const contentContainer = document.createElement('div');
        contentContainer.className = 'chat-content-container';
        
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.innerHTML = text.replace(/\n/g, '<br>');
        contentContainer.appendChild(bubble);
        
        // If we have metadata, add badge and trace
        if (metadata) {
            // Create metadata bar
            const metaBar = document.createElement('div');
            metaBar.className = 'chat-metadata-bar';
            const traceVal = (value, fallback = 'None') => (
                value === undefined || value === null || value === '' ? fallback : value
            );
            const traceList = (value) => {
                if (Array.isArray(value)) return value.length ? value.join(', ') : '[]';
                return traceVal(value, '[]');
            };
            const selectedModelLabel = traceVal(metadata.selected_model, 'auto');
            const badgeModel = traceVal(metadata.actual_model || metadata.actual_api_model_id || metadata.selected_model, 'local');
            
            // Build the clean reply badge
            const routeLabelMap = {
                "manager_response": "manager response",
                "capability_report": "capability report",
                "status_explanation": "status explanation",
                "style_memory_ack": "style memory ack",
                "creative_generation": "creative generation",
                "live_ops_explanation": "live ops explanation"
            };

            let badgeText;
            let badgeClass;
            if (metadata.model_rate_limited || metadata.route === 'model_cooldown_retry') {
                badgeText = `GEMINI COOLDOWN • retry ${metadata.retry_after_hint || '20-30s'}`;
                badgeClass = "badge-llm-blocked";
            } else if (metadata.selected_model === "local-control-only") {
                badgeText = "LOCAL CONTROL ONLY • no LLM";
                badgeClass = "badge-local-control";
            } else if (metadata.route === "blocked_creative" || metadata.source === "llm_blocked" || metadata.model_unavailable_reason) {
                badgeText = `${badgeModel.replace(/-/g, ' ').toUpperCase()} unavailable`;
                badgeClass = "badge-llm-blocked";
            } else if (metadata.protected_action_blocked === "Yes" || metadata.route === "live_ops_triage") {
                badgeText = "LIVE OPS • approval required";
                badgeClass = "badge-llm-blocked";
            } else if (metadata.route && routeLabelMap[metadata.route]) {
                const modelUpper = badgeModel.replace(/-/g, ' ').toUpperCase();
                badgeText = `${modelUpper} • ${routeLabelMap[metadata.route]}`;
                badgeClass = metadata.route === "creative_generation" ? "badge-creative" : "badge-fallback";
            } else if (metadata.route === "creative_llm" || metadata.route_type === "creative_generation" || metadata.is_creative) {
                const modelUpper = badgeModel.replace(/-/g, ' ').toUpperCase();
                badgeText = `${modelUpper} • creative`;
                badgeClass = "badge-creative";
            } else if (metadata.local_tool_executed && metadata.local_tool_executed !== "None") {
                badgeText = `LOCAL TOOL • ${metadata.local_tool_executed.toUpperCase()}`;
                badgeClass = "badge-local-tool";
            } else if (metadata.intent && metadata.intent !== "local_fallback") {
                const modelUpper = badgeModel.replace(/-/g, ' ').toUpperCase();
                badgeText = `${modelUpper} • intent`;
                badgeClass = "badge-fallback";
            } else {
                // Local tool
                let subType = metadata.route || "status";
                if (subType === "source_tools_status") subType = "source tools";
                if (subType === "stream_status" || subType === "whatsapp_status" || subType === "schedule_read") subType = "status";
                if (subType === "live_ops_triage") subType = "live ops triage";
                badgeText = `LOCAL TOOL • ${subType.replace(/_/g, ' ').toUpperCase()}`;
                badgeClass = "badge-local-tool";
            }
            
            const replyBadge = document.createElement('span');
            replyBadge.className = `reply-badge ${badgeClass}`;
            replyBadge.textContent = badgeText;
            metaBar.appendChild(replyBadge);
            
            // Trace Toggle Link/Button (PART E)
            const traceBtn = document.createElement('button');
            traceBtn.className = 'btn-meta-trace';
            traceBtn.innerHTML = `<i class="fa-solid fa-code-branch"></i> View trace`;
            
            const traceId = `trace-${Date.now()}-${Math.floor(Math.random()*1000)}`;
            traceBtn.onclick = () => {
                const traceDiv = document.getElementById(traceId);
                if (traceDiv.style.display === 'none') {
                    traceDiv.style.display = 'block';
                    container.scrollTop = container.scrollHeight;
                } else {
                    traceDiv.style.display = 'none';
                }
            };
            metaBar.appendChild(traceBtn);
            contentContainer.appendChild(metaBar);
            
            // Create trace container (collapsed by default)
            const traceContainer = document.createElement('div');
            traceContainer.id = traceId;
            traceContainer.className = 'chat-trace-details';
            traceContainer.style.display = 'none';
            
            // Build the trace details summary grid
            let traceHtml = `<div class="trace-summary-grid">
                <div><strong>Selected Model:</strong> ${selectedModelLabel}</div>
                <div><strong>Actual Model:</strong> ${traceVal(metadata.actual_model, 'None')}</div>
                <div><strong>Actual API Model ID:</strong> ${traceVal(metadata.actual_api_model_id, 'None')}</div>
                <div><strong>Candidate Models:</strong> ${traceList(metadata.candidate_models || metadata.candidate_ids)}</div>
                <div><strong>Model Verification:</strong> ${traceVal(metadata.model_verification_status, 'not_checked')}</div>
                <div><strong>Fallback Model Used:</strong> ${metadata.fallback_model_used ? 'Yes' : 'No'}</div>
                <div><strong>Model Unavailable Reason:</strong> ${traceVal(metadata.model_unavailable_reason, 'None')}</div>
                
                <div><strong>Intent Model Calls:</strong> ${metadata.intent_model_call_count !== undefined ? metadata.intent_model_call_count : 0}</div>
                <div><strong>Response Model Calls:</strong> ${metadata.response_model_call_count !== undefined ? metadata.response_model_call_count : 0}</div>
                <div><strong>Total Model Calls:</strong> ${metadata.total_model_call_count !== undefined ? metadata.total_model_call_count : 0}</div>
                
                <div><strong>Intent:</strong> ${metadata.intent || 'None'}</div>
                <div><strong>Confidence:</strong> ${metadata.confidence !== undefined ? metadata.confidence : 'N/A'}</div>
                <div><strong>Route Type:</strong> ${metadata.route_type || 'None'}</div>
                <div><strong>Tool:</strong> ${metadata.tool || 'None'}</div>
                <div><strong>Tool Suggested:</strong> ${traceVal(metadata.tool_suggested, 'None')}</div>
                <div><strong>Tool Executed:</strong> ${traceVal(metadata.tool_executed, 'false')}</div>
                <div><strong>Tool Result Present:</strong> ${traceVal(metadata.tool_result_present, 'false')}</div>
                <div><strong>Executed Tool Name:</strong> ${traceVal(metadata.executed_tool_name, 'None')}</div>
                <div><strong>Risk Level:</strong> ${metadata.risk_level || 'low'}</div>
                <div><strong>Needs Approval:</strong> ${metadata.needs_owner_approval ? 'Yes' : 'No'}</div>
                <div><strong>Protected Action:</strong> ${metadata.protected_action_requested || 'None'}</div>
                <div><strong>Next Safe Action:</strong> ${metadata.next_safe_action || 'None'}</div>
                <div><strong>Local Tool Executed:</strong> ${metadata.local_tool_executed || 'None'}</div>
                <div><strong>Protected Action Blocked:</strong> ${metadata.protected_action_blocked || 'No'}</div>
                
                <div><strong>Memory Mode:</strong> ${metadata.memory_mode || 'short_term_only'}</div>
                <div><strong>Memory Search Used:</strong> ${metadata.memory_search_used || 'short_term_only'}</div>
                <div><strong>Memory Hits Count:</strong> ${metadata.memory_hits_count !== undefined ? metadata.memory_hits_count : 0}</div>
                <div><strong>Embedding Model:</strong> ${metadata.embedding_model_used || 'None'}</div>
                <div><strong>Memory Save Status:</strong> ${traceVal(metadata.memory_save_status, 'not_attempted')}</div>
                <div><strong>Short Context Used:</strong> ${metadata.short_context_used || 'No'}</div>
                
                <div><strong>Manager Action Packet Used:</strong> ${metadata.manager_action_packet_used || 'No'}</div>
                <div><strong>Is Followup:</strong> ${metadata.is_followup || 'No'}</div>
                <div><strong>Followup Type:</strong> ${metadata.followup_type || 'None'}</div>
                <div><strong>Refers to Pending Action:</strong> ${metadata.refers_to_pending_action || 'No'}</div>
                <div><strong>Approval Strength:</strong> ${metadata.approval_strength || 'None'}</div>
                
                <div><strong>Pending Action Type:</strong> ${metadata.pending_action_type || 'None'}</div>
                <div><strong>Pending Action Protected:</strong> ${metadata.pending_action_protected || 'No'}</div>
                <div><strong>Pending Action Executable Now:</strong> ${metadata.pending_action_executable_now || 'No'}</div>
                
                <div><strong>Policy Decision:</strong> ${metadata.policy_decision || 'None'}</div>
                <div><strong>Approval Consumed:</strong> ${metadata.approval_consumed || 'No'}</div>
                <div><strong>Approval Blocked Reason:</strong> ${metadata.approval_blocked_reason || 'None'}</div>
                
                <div><strong>Pending Approval Type:</strong> ${metadata.pending_approval_type || 'None'}</div>
                <div><strong>Pending Approval Active:</strong> ${metadata.pending_approval_active || 'No'}</div>

                <div><strong>Capability Manifest Used:</strong> ${metadata.capability_manifest_used || 'No'}</div>
                <div><strong>Capabilities Count:</strong> ${metadata.capabilities_count !== undefined ? metadata.capabilities_count : 0}</div>
                <div><strong>Unavailable Capabilities Count:</strong> ${metadata.unavailable_capabilities_count !== undefined ? metadata.unavailable_capabilities_count : 0}</div>
                <div><strong>Capability Truth Level Summary:</strong> ${metadata.capability_truth_level_summary || 'None'}</div>
                
                <div><strong>Timing:</strong> Total: ${metadata.timing ? metadata.timing.total_ms : 0}ms (LLM: ${metadata.timing ? (metadata.timing.llm_ms || 0) : 0}ms, Tools: ${metadata.timing ? (metadata.timing.tools_ms || 0) : 0}ms)</div>
            </div>`;
            if (metadata.trace && metadata.trace.length > 0) {
                traceHtml += `<div class="trace-steps-title">Execution Steps:</div>`;
                metadata.trace.forEach(step => {
                    let stepDuration = "";
                    if (step.step === 'routing' && metadata.timing && metadata.timing.routing_ms) {
                        stepDuration = `+${metadata.timing.routing_ms}ms`;
                    } else if (step.step === 'tool_call' && metadata.timing && metadata.timing.tools_ms) {
                        stepDuration = `+${metadata.timing.tools_ms}ms`;
                    } else if (step.step === 'llm_call' && metadata.timing && metadata.timing.llm_ms) {
                        stepDuration = `+${metadata.timing.llm_ms}ms`;
                    } else if (step.step === 'db' && metadata.timing && metadata.timing.db_ms) {
                        stepDuration = `+${metadata.timing.db_ms}ms`;
                    }
                    traceHtml += `<div class="trace-step-item">
                        <div style="display: flex; gap: 8px;">
                            <span class="trace-step-label">[${step.step.toUpperCase()}]</span>
                            <span class="trace-step-desc">${step.message}</span>
                        </div>
                        <span class="trace-step-time">${stepDuration}</span>
                    </div>`;
                });
            }
            
            traceContainer.innerHTML = traceHtml;
            contentContainer.appendChild(traceContainer);
        }
        
        row.appendChild(contentContainer);
    } else {
        const bubble = document.createElement('div');
        bubble.className = 'chat-bubble';
        bubble.innerHTML = text.replace(/\n/g, '<br>');
        row.appendChild(bubble);
    }
    
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
}

// Scan Neena's replies for [SCRIPT_OUTPUT] tags and render in Creator Panel
function processNeenaReplyText(text) {
    const scriptStartTag = '[SCRIPT_OUTPUT]';
    const scriptEndTag = '[/SCRIPT_OUTPUT]';
    
    if (text.includes(scriptStartTag) && text.includes(scriptEndTag)) {
        const startIndex = text.indexOf(scriptStartTag);
        const endIndex = text.indexOf(scriptEndTag);
        
        const beforeScript = text.substring(0, startIndex).trim();
        const scriptContent = text.substring(startIndex + scriptStartTag.length, endIndex).trim();
        const afterScript = text.substring(endIndex + scriptEndTag.length).trim();
        
        // Populate script editor panel
        const scriptTextarea = document.getElementById('generated-script-output');
        scriptTextarea.value = scriptContent;
        
        // Return text cleaned of the script blocks for the chat bubble
        return `${beforeScript}\n\n*(Script matches loaded into the side Content Creator panel)*\n\n${afterScript}`.trim();
    }
    
    return text;
}

function copyGeneratedScript() {
    const scriptTextarea = document.getElementById('generated-script-output');
    if (!scriptTextarea.value) return;
    
    scriptTextarea.select();
    document.execCommand('copy');
    
    alert('Radio script copied to clipboard!');
}

async function refreshOwnerWorkingContext() {
    const lastEl = document.getElementById('agent-ctx-last');
    const pendingEl = document.getElementById('agent-pending-chip');
    const homeLast = document.getElementById('nc-last-action');
    const homePending = document.getElementById('nc-pending-approval');
    const homeTask = document.getElementById('nc-current-task');
    try {
        const response = await adminFetch(`${API_BASE}/neena/working-context`);
        if (!response || response.status === 401) return;
        const data = await response.json().catch(() => ({}));
        const ctx = (data && data.context) || {};
        const action = ctx.last_action_type || null;
        const route = ctx.last_route ? ` · ${ctx.last_route}` : '';
        if (lastEl) {
            lastEl.textContent = data.enabled === false
                ? 'Working context off'
                : (action ? `Last: ${action}${route}` : 'Last: —');
        }
        if (homeLast) {
            if (data.enabled === false) homeLast.textContent = 'Working context off';
            else if (action) homeLast.textContent = `${action}${route}`;
            else homeLast.textContent = 'No last action';
        }
        if (pendingEl) {
            if (ctx.pending && ctx.pending.action_type) {
                const mid = ctx.pending.memory_id != null ? ` id=${ctx.pending.memory_id}` : '';
                pendingEl.textContent = `Pending: ${ctx.pending.action_type}${mid}`;
                pendingEl.classList.remove('hidden');
            } else {
                pendingEl.classList.add('hidden');
            }
        }
        if (homePending && ctx.pending && ctx.pending.action_type) {
            homePending.textContent = ctx.pending.action_type;
            homePending.dataset.fromContext = '1';
            homePending.dataset.checked = '1';
            if (typeof setNcPendingAttention === 'function') {
                setNcPendingAttention(1, false);
            }
            if (typeof setNcPolledActivity === 'function') {
                setNcPolledActivity({ pendingApproval: true, pendingCount: 1 });
            }
        } else if (homePending && homePending.dataset.fromContext === '1' && homePending.dataset.fromLive !== '1') {
            // Only clear orb approval when THIS context source drops — do not
            // override live-state / cockpit pending (plan §4 layered truth).
            delete homePending.dataset.fromContext;
            if (typeof setNcPendingAttention === 'function') {
                setNcPendingAttention(0, false);
            }
            if (typeof setNcPolledActivity === 'function') {
                setNcPolledActivity({ pendingApproval: false, pendingCount: 0 });
            }
        } else if (homePending && !homePending.dataset.fromLive && !homePending.dataset.fromContext) {
            if (typeof setNcPendingAttention === 'function') {
                setNcPendingAttention(0, false);
            }
        }
        if (homeTask && ctx.open_goal) {
            homeTask.textContent = ctx.open_goal;
            homeTask.dataset.fromContext = '1';
            if (typeof setNcPolledActivity === 'function') {
                setNcPolledActivity({ openGoal: ctx.open_goal });
            }
        } else if (homeTask && homeTask.textContent === 'Not checked') {
            homeTask.textContent = 'No active task';
        }
    } catch (e) {
        /* best-effort */
    }
}

async function hydrateOwnerChatThread() {
    const container = document.getElementById('console-chat-messages');
    if (!container || container.dataset.hydrated === '1') return;
    try {
        const response = await adminFetch(`${API_BASE}/neena/interaction-records/recent?session_limit=3&turn_limit=16&channel=chat`);
        if (!response || !response.ok) return;
        const data = await response.json().catch(() => ({}));
        let flat = (data && data.recent_turns) || (data && data.turns) || [];
        if ((!flat || !flat.length) && data.sessions && Array.isArray(data.sessions)) {
            flat = [];
            data.sessions.slice(0, 2).forEach((s) => {
                (s.turns || []).forEach((t) => flat.push(t));
            });
        }
        if (!Array.isArray(flat) || !flat.length) {
            container.dataset.hydrated = '1';
            return;
        }
        // Owner CC thread = chat channel only (never mix WA / listener / live_ops)
        flat = flat.filter((t) => !t.channel || t.channel === 'chat');
        flat.slice(-12).forEach((t) => {
            const user = (t.user_input || t.message || '').trim();
            const reply = (t.reply || t.assistant_reply || '').trim();
            if (user) appendChatMessage('user', user);
            if (reply) appendChatMessage('assistant', reply, {
                route: t.route,
                action_type: t.action_type,
                selected_model: t.selected_model,
            });
        });
        container.dataset.hydrated = '1';
        container.scrollTop = container.scrollHeight;
    } catch (e) {
        /* best-effort */
    }
}

// 2. VM TELEMETRY MONITOR & PLAYER LOGIC
