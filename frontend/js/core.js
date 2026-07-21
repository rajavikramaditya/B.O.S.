// ==== Orai Command Center — shared config + state module ====
// Auto-split from the former monolithic app.js (M6 Phase 4c, SRP).
// Loaded as an ordered classic <script>; shares one global scope with sibling
// modules (core.js, voice.js, admin.js, cockpit.js, panels.js, app.js).

// Orai Radio Admin Console Javascript Controller

const API_BASE = window.location.origin.startsWith('http') ? window.location.origin + '/api' : 'http://localhost:8000/api';
// Soft Gemma(8–10s)+flash-lite should finish well under this; keep headroom for status/humanize.
const NEENA_CHAT_TIMEOUT_MS = 120000;

const COCKPIT_ACTION_TIMEOUT_MS = {
    station_status: 8000,
    diagnostics_fast: 12000,
    diagnostics: 12000,
    verify_latest_stream: 8000,
    broadcast_readiness: 10000,
    latest_verified_capsule: 10000,
};

const COCKPIT_JOB_POLL_MS = 2000;
const COCKPIT_JOB_POLL_MAX_MS = 120000;
const LIVE_STATE_TIMEOUT_MS = 5000;
const AUTO_BROWSER_PROBE_MS = 1200;
const BROWSER_SPEECH_FULL_TIMEOUT_MS = 120000;
const MAX_VOICE_CHARS = 1200;
const VOICE_JOB_POLL_MS = 1500;
const VOICE_JOB_POLL_MAX_MS = 120000;
const VOICE_SPEAK_POST_TIMEOUT_MS = 8000;
const VOICE_BACKEND_FAST_FAIL_MS = 2000;
const VOICE_DEDUPE_MS = 10000;
const LIVE_STATE_STALE_SPEAK_MS = 60000;
const SPEAK_PREF_KEY = 'orai_speak_responses';
const VOICE_MODE_KEY = 'orai_voice_provider_mode';
const VOICE_TEST_PHRASE = 'Neena voice test successful. Main aapko bolkar updates dungi.';
const BROWSER_FAIL_AUTO_BACKEND_ERRORS = ['synthesis-failed', 'speech timeout', 'not-allowed', 'interrupted'];

let voiceOwnerGestureUnlocked = false;
let voiceSpeaking = false;
let voiceStatusState = 'idle';
let voiceBrowserKnownFailed = false;
let voiceLastBrowserError = null;
let voiceLastBackendError = null;
let voiceFallbackProviderStatus = null;
let voiceProviderMode = 'auto';
let lastBrowserVoiceHealthy = true;
let currentCockpitAudio = null;
let currentCockpitAudioUrl = null;
let voiceJobRunning = false;
let voiceQueue = [];
let voiceActiveBackendJobId = null;
let voicePollTimer = null;
let voiceDedupeMap = {};
let liveStateStale = false;
let lastLiveStateFailSpeakAt = 0;
let lastKnownCpu = 0;
let lastKnownRam = 0;
let pollingReduced = false;

// Voice UX State Machine variables
let currentState = 'IDLE'; // LOCKED, IDLE, LISTENING, PROCESSING, SPEAKING, WAITING_FOR_FOLLOWUP, ERROR
let followUpTimeoutId = null;
let activeChatAbortController = null;
let lastSpokenResponseId = null;
let lastCockpitTaskText = '';
let lastCockpitTaskAt = 0;

let activeTab = 'console';
let telemetryInterval = null;
let whatsappInterval = null;
let nowPlayingInterval = null;
let speechSynthAvailable = true;
let speechVoicesPrimed = false;
let speechWarningShown = false;

// M4-A8 — Owner phrase unlock (HttpOnly cookie; voice-first UX)
const COCKPIT_ADMIN_LOCK_ENABLED = true;
// Voice recognition language. Use en-IN (not hi-IN) so Hindi/Hinglish speech is
// transcribed in Latin script ("command center lock karo") instead of Devanagari
// ("कमांड सेंटर लॉक करो"). The LLM interpreter and prompts are built for Hinglish/
// English; feeding Devanagari caused intent misreads. Fix the input at the source
// rather than adding script-specific matching downstream.
const VOICE_COMMAND_LANG = 'en-IN';
const VOICE_UNLOCK_LANG = 'en-IN';
let adminAuthRequired = false;
let adminSessionUnlocked = false;
let manualUnlockPanelOpen = false;
let voiceRecognitionMode = 'command';

function sleepMs(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
