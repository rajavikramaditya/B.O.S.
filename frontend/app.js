// ==== Orai Command Center — bootstrap module ====
// Auto-split from the former monolithic app.js (M6 Phase 4c, SRP).
// Loaded as an ordered classic <script>; shares one global scope with sibling
// modules (core.js, voice.js, admin.js, cockpit.js, panels.js, app.js).


// Initialise dashboard polling
function initPolling() {
    fetchTelemetryStats();
    fetchLaunchHealthBadges();
    fetchWhatsAppGatewayStatus();
    fetchStationSettingsConfig();
    fetchNeenaAgentFlags();
    fetchNowPlayingMetadata();
    fetchPendingDedications();
    
    telemetryInterval = setInterval(fetchTelemetryStats, 6000);
    setInterval(() => { if (!shouldReducePollingLoad()) fetchLaunchHealthBadges(); }, 15000);
    whatsappInterval = setInterval(() => { if (!shouldReducePollingLoad()) fetchWhatsAppGatewayStatus(); }, 5000);
    nowPlayingInterval = setInterval(() => { if (!shouldReducePollingLoad()) fetchNowPlayingMetadata(); }, 10000);
    setInterval(() => { if (!shouldReducePollingLoad()) fetchPendingDedications(); }, 8000);
    neenaLabInterval = setInterval(() => { if (!shouldReducePollingLoad()) fetchNeenaLabData(); }, 10000);
    setInterval(fetchCockpitData, 12000);
    if (typeof fetchNeenaLiveHome === 'function') {
        fetchNeenaLiveHome();
        setInterval(() => { if (typeof fetchNeenaLiveHome === 'function') fetchNeenaLiveHome(); }, 8000);
    }
    drainPendingCompletions();
    setInterval(() => { if (!shouldReducePollingLoad()) drainPendingCompletions(); }, 15000);
}

async function loadBusinessConfig() {
    try {
        const response = await fetch('/api/business-config');
        if (response.ok) {
            const data = await response.json();
            document.title = `${data.name} — Command Center`;
            
            // Update brand logo elements
            const brands = document.querySelectorAll('.cc-gate-brand, .brand-info h2');
            brands.forEach(el => {
                el.textContent = data.name;
            });
            
            const subtitle = document.getElementById('viewport-subtitle');
            if (subtitle) {
                subtitle.textContent = `${data.type} AI Manager`;
                subtitle.classList.remove('visually-hidden');
            }
            console.log(`Loaded business config: ${data.name} (${data.type})`);
        }
    } catch (e) {
        console.error("Failed to load business config:", e);
    }
}

// Boot up
window.addEventListener('DOMContentLoaded', async () => {
    await loadBusinessConfig();
    if (typeof initCcChrome === 'function') initCcChrome();
    if (typeof initNeenaVoicePadToggle === 'function') initNeenaVoicePadToggle();
    if (typeof initNeenaCoreOrb === 'function') initNeenaCoreOrb();
    document.body.addEventListener('click', (ev) => {
        if (!document.body.classList.contains('cc-sidebar-open')) return;
        if (ev.target.closest('.sidebar-panel') || ev.target.closest('.cc-sidebar-toggle')) return;
        closeCcSidebarDrawer();
    });
    document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape' && typeof closeCommandDrawer === 'function') closeCommandDrawer();
    });
    // Resolve lock state before first meaningful paint of gate vs shell
    await fetchAdminSecurityStatus();
    initPolling();
    initOwnerVoice();
    initVoiceRecognition();
    setNeenaState('online', 'Neena Online');
    
    // Perform initial health check
    const isUp = await checkBackendHealth();
    if (!isUp) {
        setBackendOfflineState(true);
    } else {
        fetchCockpitData();
    }
    
    appendCockpitTask('Command Center online.', 'info');
    refreshOwnerWorkingContext();
    hydrateOwnerChatThread();
    // Pre-populate keys inputs if environment has cached ones
    fetch(`${API_BASE}/config/status`).then(res => res.json()).then(data => {
        // We do not load actual secret keys in DOM inputs for safety, 
        // but can prefill placeholders
        if (data.gemini_api_key_configured) {
            document.getElementById('setting-gemini-key').placeholder = 'GEMINI KEY IS ACTIVE (Enter new key to overwrite)';
        }
        if (data.elevenlabs_api_key_configured) {
            document.getElementById('setting-elevenlabs-key').placeholder = 'ELEVENLABS KEY IS ACTIVE (Enter new key to overwrite)';
        }
        updateModelSelectorDropdown(data.fallback_model_verified);
    }).catch(e=>{});
});
window.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        try { window.speechSynthesis.cancel(); } catch(e){}
        if (voiceRecognition && voiceListening) {
            try { voiceRecognition.stop(); } catch(e){}
        }
    }
});

window.addEventListener('beforeunload', () => {
    try { window.speechSynthesis.cancel(); } catch(e){}
});
