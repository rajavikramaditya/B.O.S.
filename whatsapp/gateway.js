const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const cors = require('cors');
const qrcodeTerm = require('qrcode-terminal');
const QRCode = require('qrcode');
const axios = require('axios');
const path = require('path');
const fs = require('fs');

// Load ../.env into process.env (owner number, gateway config) WITHOUT adding a
// dependency. The gateway often runs as a bare host process where docker-compose
// env is not injected, so the owner number must be read from the shared .env.
function loadEnvFile() {
    try {
        const envPath = path.join(__dirname, '..', '.env');
        if (!fs.existsSync(envPath)) return;
        const lines = fs.readFileSync(envPath, 'utf8').split(/\r?\n/);
        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) continue;
            const eq = trimmed.indexOf('=');
            if (eq === -1) continue;
            const key = trimmed.slice(0, eq).trim();
            let value = trimmed.slice(eq + 1).trim();
            if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
                value = value.slice(1, -1);
            }
            if (key && process.env[key] === undefined) {
                process.env[key] = value;
            }
        }
        console.log('[WhatsApp Gateway] Loaded config from .env');
    } catch (err) {
        console.error('[WhatsApp Gateway] Could not load .env:', err.message);
    }
}
loadEnvFile();

// Robust owner match. WhatsApp multi-device can deliver an incoming message from
// a privacy "LID" (a long linked-id like 2352...888) instead of the real phone
// number, which does NOT match OWNER_WHATSAPP_NUMBER and used to misroute the
// owner as a customer. So we match against SEVERAL candidate identifiers (real
// resolved number preferred) by last-10 digits, and any hit means owner.
function ownerDigits() {
    // No hardcoded fallback — missing OWNER_WHATSAPP_NUMBER fails closed
    // (nobody matches as owner) rather than baking a phone into source.
    const ownerRaw = process.env.OWNER_WHATSAPP_NUMBER || '';
    return ownerRaw.replace(/\D/g, '');
}

function digitsMatchOwner(candidateDigits) {
    const owner = ownerDigits();
    if (!candidateDigits || !owner) return false;
    const tail = (s) => s.slice(-10);
    return candidateDigits === owner || tail(candidateDigits) === tail(owner);
}

// Returns { isOwner, realNumber } after inspecting every candidate identifier.
function resolveSender(candidates) {
    let realNumber = '';
    for (const c of candidates) {
        const d = String(c || '').replace(/\D/g, '');
        if (!d) continue;
        if (!realNumber) realNumber = d;         // first usable becomes the number we forward
        if (digitsMatchOwner(d)) {
            return { isOwner: true, realNumber: d };
        }
    }
    return { isOwner: false, realNumber };
}

// Mask a digit string for logs: keep first 4 + last 3, star the middle (no PII leak).
function maskDigits(s) {
    const d = String(s || '').replace(/\D/g, '');
    if (d.length <= 7) return d ? '***' : '';
    return `${d.slice(0, 4)}****${d.slice(-3)}`;
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Customer WhatsApp: sometimes send 2–3 short bubbles (human feel).
 * Not every reply — ~45% when there are 2+ short lines. Owner never uses this.
 */
async function sendCustomerReplyBubbles(waClient, chatId, text) {
    const raw = String(text || '').trim();
    if (!raw) return;

    const lines = raw.split(/\n+/).map((l) => l.trim()).filter(Boolean);
    const canSplit = lines.length >= 2 && lines.length <= 4
        && lines.every((l) => l.length <= 160)
        && raw.length <= 420;

    // Random-ish: not a fixed pattern every time.
    const roll = Math.random();
    if (!canSplit || roll > 0.45) {
        await waClient.sendMessage(chatId, raw);
        return;
    }

    const maxBubbles = Math.min(3, lines.length);
    const chunks = lines.slice(0, maxBubbles);
    // If leftover lines, append to last bubble.
    if (lines.length > maxBubbles) {
        chunks[chunks.length - 1] = `${chunks[chunks.length - 1]}\n${lines.slice(maxBubbles).join('\n')}`;
    }

    for (let i = 0; i < chunks.length; i++) {
        await waClient.sendMessage(chatId, chunks[i]);
        if (i < chunks.length - 1) {
            await sleep(350 + Math.floor(Math.random() * 550));
        }
    }
}

const app = express();
app.use(cors());
app.use(express.json());

const PORT = 3001;
const PYTHON_BACKEND = process.env.PYTHON_BACKEND_URL || 'http://localhost:8080';

let qrCodeData = "";
let clientStatus = "disconnected";
let clientNumber = "";

// Helper to find browser executable (Linux VM + Windows dev)
function getSystemBrowserPath() {
    const envPath = process.env.PUPPETEER_EXECUTABLE_PATH || process.env.CHROME_EXECUTABLE_PATH;
    if (envPath && fs.existsSync(envPath)) {
        console.log(`[WhatsApp Gateway] Using browser from env: ${envPath}`);
        return envPath;
    }
    const paths = [
        '/usr/bin/google-chrome-stable',
        '/usr/bin/google-chrome',
        '/usr/bin/chromium-browser',
        '/usr/bin/chromium',
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    ];
    for (const p of paths) {
        if (fs.existsSync(p)) {
            console.log(`[WhatsApp Gateway] Using system browser found at: ${p}`);
            return p;
        }
    }
    return undefined;
}

let qrGeneratedAt = 0;

// Initialize WhatsApp client
// Using headless: true and --no-sandbox to run smoothly on servers
const client = new Client({
    authStrategy: new LocalAuth({
        dataPath: path.join(__dirname, '.wwebjs_auth')
    }),
    webVersionCache: {
        type: 'remote',
        remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.2412.54.html'
    },
    puppeteer: {
        headless: true,
        executablePath: getSystemBrowserPath(),
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            '--disable-gpu',
            // Cap Chromium fan-out on 2-vCPU VMs (prevents idle renderer pile-up).
            '--renderer-process-limit=2',
            '--disable-extensions',
            '--mute-audio'
        ]
    }
});

// Helper to notify Python backend of status change
async function notifyPythonBackend(status, extraData = {}) {
    try {
        await axios.post(`${PYTHON_BACKEND}/api/whatsapp/status`, {
            status: status,
            qr_code_data: qrCodeData,
            phone: clientNumber,
            ...extraData
        });
        console.log(`[Status Sync] Sent status: ${status} to Python Backend.`);
    } catch (err) {
        console.error(`[Status Sync Error] Failed to sync status with Python backend: ${err.message}`);
    }
}

client.on('qr', (qr) => {
    console.log('[WhatsApp Gateway] QR Code generated. Scan it with your phone:');
    // Display QR in console for terminal logging
    qrcodeTerm.generate(qr, { small: true });
    
    // Generate QR Image Data URL to send to frontend dashboard
    QRCode.toDataURL(qr, (err, url) => {
        if (!err) {
            qrCodeData = url;
            qrGeneratedAt = Date.now();
            clientStatus = "qr_ready";
            notifyPythonBackend("qr_ready");
        }
    });
});

client.on('ready', () => {
    console.log('[WhatsApp Gateway] Client is ready and connected!');
    clientStatus = "connected";
    clientNumber = client.info.wid.user;
    qrCodeData = "";
    notifyPythonBackend("connected");
});

client.on('authenticated', () => {
    console.log('[WhatsApp Gateway] Authenticated successfully.');
});

client.on('auth_failure', (msg) => {
    console.error('[WhatsApp Gateway] Authentication failure:', msg);
    clientStatus = "disconnected";
    qrCodeData = "";
    notifyPythonBackend("disconnected", { notes: "Authentication failure: " + msg });
});

client.on('disconnected', (reason) => {
    console.log('[WhatsApp Gateway] Client disconnected:', reason);
    clientStatus = "disconnected";
    qrCodeData = "";
    notifyPythonBackend("disconnected", { notes: "Disconnected: " + reason });
});

// Listen to incoming messages
client.on('message', async (msg) => {
    // Ignore messages from groups or broadcast lists
    if (msg.from.endsWith('@g.us') || msg.broadcast || msg.isStatus) {
        return;
    }
    
    // Ignore our own messages
    if (msg.fromMe) {
        return;
    }

    const phone = msg.from.split('@')[0];
    const messageContent = msg.body;
    
    console.log(`[New Message] From ${phone}: ${messageContent}`);

    // Resolve real sender identity. contact.number gives the actual phone number
    // even when msg.from is a LID; we gather every candidate for robust matching.
    let senderName = "Client";
    let contactNumber = "";
    let contactId = "";
    try {
        const contact = await msg.getContact();
        senderName = contact.pushname || contact.name || "Client";
        contactNumber = contact.number || (contact.id && contact.id.user) || "";
        contactId = (contact.id && contact.id._serialized) || "";
    } catch (e) {
        console.error("Failed to get contact:", e.message);
    }

    try {
        const authorRaw = msg.author ? msg.author.split('@')[0] : '';
        // Order matters: prefer the resolved real number, then raw from/author.
        const candidates = [contactNumber, phone, authorRaw, contactId];
        const { isOwner, realNumber } = resolveSender(candidates);
        const forwardPhone = realNumber || phone;

        const endpoint = isOwner ? '/api/whatsapp/webhook' : '/api/leads/inbound-webhook';

        // Masked diagnostic: confirms which identifier carries the real number so
        // owner-recognition can be verified from a single owner test message.
        console.log(
            `[Routing] owner=${isOwner} -> ${endpoint} | from=${maskDigits(phone)} ` +
            `contact=${maskDigits(contactNumber)} author=${maskDigits(authorRaw)} fwd=${maskDigits(forwardPhone)}`
        );

        // Show "typing…" while Neena thinks — human manager feel (especially for customers).
        let chat = null;
        let typingTimer = null;
        try {
            chat = await msg.getChat();
            await chat.sendStateTyping();
            // Refresh typing every ~20s for longer brain calls (API lasts ~25s).
            typingTimer = setInterval(() => {
                chat.sendStateTyping().catch(() => {});
            }, 20000);
        } catch (typeErr) {
            console.warn('[Typing] could not start:', typeErr.message);
        }

        try {
            // Forward resolved real number so backend owner re-check matches gateway routing.
            const response = await axios.post(`${PYTHON_BACKEND}${endpoint}`, {
                phone: forwardPhone,
                message: messageContent,
                sender_name: senderName,
                is_owner: isOwner
            }, { timeout: 120000 });

            const aiReply = response.data.reply;
            if (aiReply) {
                console.log(`[AI Reply] Sending to ${phone}: ${aiReply}`);
                // Owner: one bubble (ops clarity). Customer: sometimes 2–3 short
                // bubbles like a real WhatsApp chat — not every reply.
                if (isOwner) {
                    await client.sendMessage(msg.from, aiReply);
                } else {
                    await sendCustomerReplyBubbles(client, msg.from, aiReply);
                }
            }
        } finally {
            if (typingTimer) clearInterval(typingTimer);
            if (chat) {
                try { await chat.clearState(); } catch (_) { /* ignore */ }
            }
        }
    } catch (err) {
        console.error(`[Error Processing Message] webhook failed: ${err.message}`);
    }
});

// API for python backend to send custom/manual messages
app.post('/api/send-message', async (req, res) => {
    const { phone, message } = req.body;
    
    if (!phone || !message) {
        return res.status(400).json({ error: 'phone and message are required' });
    }
    
    if (clientStatus !== 'connected') {
        return res.status(400).json({ error: 'WhatsApp client is not connected' });
    }

    try {
        const formattedPhone = phone.includes('@c.us') ? phone : `${phone}@c.us`;
        await client.sendMessage(formattedPhone, message);
        res.json({ status: 'success' });
    } catch (err) {
        console.error('Failed to send message:', err.message);
        res.status(500).json({ error: 'Failed to send message: ' + err.message });
    }
});

// Endpoint to fetch current local status directly
app.get('/api/status', (req, res) => {
    res.json({
        status: clientStatus,
        qr_code_data: qrCodeData,
        phone: clientNumber,
        qr_age_seconds: qrGeneratedAt ? Math.round((Date.now() - qrGeneratedAt) / 1000) : null
    });
});

app.listen(PORT, () => {
    console.log(`[WhatsApp Gateway Server] Running on http://localhost:${PORT}`);
    
    // Start WhatsApp client connection
    client.initialize().catch(err => {
        console.error('Failed to initialize WhatsApp client:', err.message);
    });
});
