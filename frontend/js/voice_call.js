/**
 * Neena Live Voice Call client module (using Gemini Live API / WebSockets).
 * No modal popups — uses the central orb and header pill button.
 */

let voiceCallWs = null;
let audioContext = null;
let audioSource = null;
let audioProcessor = null;
let micStream = null;
let playbackContext = null;
let nextPlaybackTime = 0;
let isCallMuted = false;
let isLiveActive = false;

async function toggleNeenaLiveCall() {
    if (!isLiveActive) {
        await startNeenaLiveCall();
    } else {
        endNeenaLiveCall();
    }
}

async function startNeenaLiveCall() {
    isLiveActive = true;
    isCallMuted = false;

    // Update Go Live button UI to active/live state (pulsating red)
    const btn = document.getElementById('cc-header-call-btn');
    const dot = document.getElementById('cc-header-live-dot');
    const txt = document.getElementById('cc-header-live-text');
    if (btn && dot && txt) {
        btn.style.background = "rgba(239, 68, 68, 0.15)";
        btn.style.borderColor = "#ef4444";
        btn.style.color = "#ef4444";
        dot.style.background = "#ef4444";
        dot.style.boxShadow = "0 0 8px #ef4444";
        dot.style.animation = "pulse 1s infinite alternate";
        txt.innerText = "Disconnect";
    }

    // Set central orb state to thinking/connecting
    if (typeof setCoreOrbState === 'function') {
        setCoreOrbState('thinking', 'Connecting live voice...');
    }

    // Establish WebSocket Connection
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/api/neena/live-voice`;
    
    try {
        voiceCallWs = new WebSocket(wsUrl);
        voiceCallWs.binaryType = 'arraybuffer';

        voiceCallWs.onopen = async () => {
            if (typeof setCoreOrbState === 'function') {
                setCoreOrbState('listening', 'Live — Listening');
            }
            await initAudioCapture();
            initAudioPlayback();
        };

        voiceCallWs.onmessage = (event) => {
            if (event.data instanceof ArrayBuffer) {
                // Incoming native PCM audio chunk from Gemini
                playIncomingPCM(event.data);
                // Animate orb to speaking state
                animateOrbSpeaking(true);
            }
        };

        voiceCallWs.onerror = (err) => {
            console.error("Live Voice WebSocket error:", err);
            if (typeof setCoreOrbState === 'function') {
                setCoreOrbState('error', 'Voice connection error');
            }
        };

        voiceCallWs.onclose = () => {
            if (typeof setCoreOrbState === 'function') {
                setCoreOrbState('idle');
            }
            cleanupAudio();
            resetButtonUI();
            isLiveActive = false;
        };

    } catch (e) {
        console.error("Failed to start Live Voice call:", e);
        if (typeof setCoreOrbState === 'function') {
            setCoreOrbState('error', 'Failed to connect');
        }
        resetButtonUI();
        isLiveActive = false;
    }
}

function endNeenaLiveCall() {
    if (voiceCallWs) {
        voiceCallWs.close();
        voiceCallWs = null;
    }
    cleanupAudio();
    resetButtonUI();
    isLiveActive = false;
}

function resetButtonUI() {
    const btn = document.getElementById('cc-header-call-btn');
    const dot = document.getElementById('cc-header-live-dot');
    const txt = document.getElementById('cc-header-live-text');
    if (btn && dot && txt) {
        btn.style.background = "rgba(16, 185, 129, 0.15)";
        btn.style.borderColor = "var(--accent-light, #10b981)";
        btn.style.color = "var(--accent-light, #10b981)";
        dot.style.background = "var(--accent-light, #10b981)";
        dot.style.boxShadow = "0 0 8px var(--accent-light, #10b981)";
        dot.style.animation = "none";
        txt.innerText = "Go Live";
    }
}

async function initAudioCapture() {
    try {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        audioSource = audioContext.createMediaStreamSource(micStream);
        
        // ScriptProcessorNode buffers mono audio at 16kHz
        audioProcessor = audioContext.createScriptProcessor(2048, 1, 1);
        
        audioProcessor.onaudioprocess = (e) => {
            if (isCallMuted) return;

            const inputData = e.inputBuffer.getChannelData(0);
            const pcmBuffer = new Int16Array(inputData.length);
            for (let i = 0; i < inputData.length; i++) {
                const s = Math.max(-1, Math.min(1, inputData[i]));
                pcmBuffer[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            if (voiceCallWs && voiceCallWs.readyState === WebSocket.OPEN) {
                voiceCallWs.send(pcmBuffer.buffer);
            }
        };

        audioSource.connect(audioProcessor);
        audioProcessor.connect(audioContext.destination);

    } catch (err) {
        console.error("Microphone capture failed:", err);
        if (typeof setCoreOrbState === 'function') {
            setCoreOrbState('error', 'Mic access denied');
        }
        cleanupAudio();
    }
}

function initAudioPlayback() {
    playbackContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    nextPlaybackTime = 0;
}

function playIncomingPCM(arrayBuffer) {
    if (!playbackContext) return;
    
    // Convert 24kHz Int16 PCM to Float32
    const int16Array = new Int16Array(arrayBuffer);
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
    }

    const audioBuffer = playbackContext.createBuffer(1, float32Array.length, 24000);
    audioBuffer.getChannelData(0).set(float32Array);

    const source = playbackContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playbackContext.destination);

    const now = playbackContext.currentTime;
    if (nextPlaybackTime < now) {
        nextPlaybackTime = now + 0.05; // 50ms buffer offset to prevent crackle
    }
    source.start(nextPlaybackTime);
    nextPlaybackTime += audioBuffer.duration;
}

let speakAnimTimeout = null;
function animateOrbSpeaking(speaking) {
    if (speaking && typeof setCoreOrbState === 'function') {
        setCoreOrbState('speaking', 'Live — Speaking');
        
        if (speakAnimTimeout) clearTimeout(speakAnimTimeout);
        speakAnimTimeout = setTimeout(() => {
            if (isLiveActive) {
                setCoreOrbState('listening', 'Live — Listening');
            }
        }, 850);
    }
}

function cleanupAudio() {
    if (audioProcessor) {
        audioProcessor.disconnect();
        audioProcessor = null;
    }
    if (audioSource) {
        audioSource.disconnect();
        audioSource = null;
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    if (playbackContext) {
        playbackContext.close();
        playbackContext = null;
    }
    if (micStream) {
        micStream.getTracks().forEach(track => track.stop());
        micStream = null;
    }
}
