import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "radio_station.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Clean up old tables from previous setup
    for old_table in ["chats", "calls", "call_logs", "rate_card", "song_requests"]:
        cursor.execute(f"DROP TABLE IF EXISTS {old_table}")
    
    # 2. Create Market Rates table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT UNIQUE NOT NULL,
        price TEXT NOT NULL,
        unit TEXT NOT NULL,
        trend TEXT DEFAULT 'up', -- 'up' or 'down'
        price_change TEXT NOT NULL,
        category TEXT NOT NULL -- 'mandi' or 'sarafa'
    )
    """)
    
    # 3. Create Station Commands table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS station_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        command_type TEXT NOT NULL,
        payload_json TEXT,
        status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'success', 'failed'
        result_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 4. Create Station Runtime Status table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS station_runtime_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_name TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL,
        last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP,
        details_json TEXT
    )
    """)
    
    # 5. Create Activity Log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        activity_type TEXT NOT NULL,
        detail TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 6. Create now_playing table (useful for telemetry cache)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS now_playing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        artist TEXT NOT NULL,
        duration_seconds INTEGER,
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 6.5. Create song_dedications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS song_dedications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listener_name TEXT NOT NULL,
        region TEXT NOT NULL,
        dedicated_to TEXT NOT NULL,
        song_title TEXT NOT NULL,
        message TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 6.6. Create birthday_wishes table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS birthday_wishes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listener_name TEXT NOT NULL,
        region TEXT NOT NULL,
        wish_for TEXT NOT NULL,
        message TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 7. Create service_registry table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS service_registry (
        service_name TEXT PRIMARY KEY,
        service_type TEXT NOT NULL,
        display_name TEXT NOT NULL,
        health_url TEXT,
        command_start TEXT,
        command_stop TEXT,
        command_restart TEXT,
        enabled INTEGER DEFAULT 1,
        configured INTEGER DEFAULT 1,
        last_status TEXT DEFAULT 'unknown',
        last_error TEXT,
        last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP,
        allowed_actions TEXT -- JSON list of actions
    )
    """)

    # 7.5. Create sponsor_campaigns table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sponsor_campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sponsor_name TEXT NOT NULL,
        campaign_name TEXT NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        audio_file_path TEXT NOT NULL,
        play_slots_limit INTEGER DEFAULT 5,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 7.6. Create approval_queue table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS approval_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_type TEXT NOT NULL, -- 'news_script', 'show_script', 'audio_ad', 'voice_capsule'
        content_data TEXT NOT NULL,
        source_path TEXT,
        status TEXT NOT NULL DEFAULT 'pending_review', -- 'pending_review', 'approved', 'rejected'
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 7.7. Create voice_personas table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voice_personas (
        id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        elevenlabs_voice_id TEXT,
        consent_status TEXT NOT NULL DEFAULT 'Pending', -- 'Pending', 'Approved', 'Rejected'
        active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 7.8. Create voice_scraped_references table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voice_scraped_references (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_name TEXT NOT NULL,
        source_url TEXT NOT NULL,
        local_wav_path TEXT NOT NULL,
        duration_seconds REAL,
        scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 7.9. Create voice_assets table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voice_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        script_id INTEGER,
        voice_id TEXT NOT NULL,
        text_content TEXT NOT NULL,
        audio_file_path TEXT NOT NULL,
        status TEXT DEFAULT 'rendered',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 7.10. Create voice_usage_log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voice_usage_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voice_id TEXT NOT NULL,
        character_count INTEGER NOT NULL,
        estimated_cost_usd REAL DEFAULT 0.0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 8. Create playout_schedule table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS playout_schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        time_slot TEXT NOT NULL,
        program_name TEXT NOT NULL,
        description TEXT,
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 8.1. Broadcast capsules (M4-A1) — script/approval/audio/AzuraCast tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS broadcast_capsules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        approval_queue_id INTEGER UNIQUE,
        capsule_type TEXT NOT NULL DEFAULT 'unknown',
        title TEXT,
        topic TEXT,
        script_text TEXT NOT NULL,
        language TEXT,
        tone TEXT,
        status TEXT NOT NULL DEFAULT 'draft',
        source TEXT NOT NULL DEFAULT 'unknown',
        audio_file_path TEXT,
        audio_path TEXT,
        audio_truth_level TEXT NOT NULL DEFAULT 'none',
        audio_status TEXT NOT NULL DEFAULT 'none',
        audio_provider TEXT,
        approval_status TEXT NOT NULL DEFAULT 'pending',
        azuracast_status TEXT NOT NULL DEFAULT 'not_sent',
        azuracast_playlist_id TEXT,
        azuracast_media_id TEXT,
        stream_verification_status TEXT NOT NULL DEFAULT 'unknown',
        truth_level TEXT NOT NULL DEFAULT 'local_only',
        owner_notes TEXT,
        safety_notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT,
        approved_at DATETIME,
        approved_by TEXT,
        rejected_at DATETIME,
        rejected_by TEXT,
        reject_reason TEXT,
        error_message TEXT,
        metadata_json TEXT,
        audio_metadata_json TEXT,
        broadcast_ready INTEGER DEFAULT 0,
        production_asset INTEGER DEFAULT 0
    )
    """)

    # Migration: Add missing columns if existing table does not have them (no data loss)
    cursor.execute("PRAGMA table_info(broadcast_capsules)")
    columns = [row[1] for row in cursor.fetchall()]
    new_cols = {
        "approval_queue_id": "INTEGER",
        "capsule_type": "TEXT NOT NULL DEFAULT 'unknown'",
        "title": "TEXT",
        "topic": "TEXT",
        "script_text": "TEXT NOT NULL DEFAULT ''",
        "language": "TEXT",
        "tone": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'draft'",
        "source": "TEXT NOT NULL DEFAULT 'unknown'",
        "audio_file_path": "TEXT",
        "audio_path": "TEXT",
        "audio_truth_level": "TEXT NOT NULL DEFAULT 'none'",
        "audio_status": "TEXT NOT NULL DEFAULT 'none'",
        "audio_provider": "TEXT",
        "approval_status": "TEXT NOT NULL DEFAULT 'pending'",
        "azuracast_status": "TEXT NOT NULL DEFAULT 'not_sent'",
        "azuracast_playlist_id": "TEXT",
        "azuracast_media_id": "TEXT",
        "stream_verification_status": "TEXT NOT NULL DEFAULT 'unknown'",
        "truth_level": "TEXT NOT NULL DEFAULT 'local_only'",
        "owner_notes": "TEXT",
        "safety_notes": "TEXT",
        "created_by": "TEXT",
        "approved_at": "DATETIME",
        "approved_by": "TEXT",
        "rejected_at": "DATETIME",
        "rejected_by": "TEXT",
        "reject_reason": "TEXT",
        "error_message": "TEXT",
        "metadata_json": "TEXT",
        "audio_metadata_json": "TEXT",
        "broadcast_ready": "INTEGER DEFAULT 0",
        "production_asset": "INTEGER DEFAULT 0",
        "created_at": "DATETIME DEFAULT NULL",
        "updated_at": "DATETIME DEFAULT NULL"
    }
    for col, type_info in new_cols.items():
        if col not in columns:
            cursor.execute(f"ALTER TABLE broadcast_capsules ADD COLUMN {col} {type_info}")



    # 9. Create neena_chat_history table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS neena_chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL, -- 'user' or 'model'
        message TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # 10. Create app_config table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS app_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    # 10.1 M4-A8.3 — cockpit background jobs (SQLite-backed)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cockpit_jobs (
        job_id TEXT PRIMARY KEY,
        action TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'queued',
        progress_message TEXT,
        owner_message TEXT,
        safe_details_json TEXT,
        payload_json TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        finished_at TEXT,
        error_summary TEXT,
        gemini_calls INTEGER DEFAULT 0,
        latency_ms INTEGER
    )
    """)

    # 10.2 — Command Center interaction recording (agent analysis / runtime UX)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS command_center_sessions (
        session_id TEXT PRIMARY KEY,
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        ended_at DATETIME,
        end_reason TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS command_center_turns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        channel TEXT NOT NULL,
        user_input TEXT NOT NULL,
        assistant_reply TEXT,
        intent TEXT,
        route TEXT,
        action_type TEXT,
        policy_decision TEXT,
        command_triggered TEXT,
        outcome TEXT NOT NULL DEFAULT 'success',
        blocked INTEGER NOT NULL DEFAULT 0,
        block_reason TEXT,
        selected_model TEXT,
        actual_model TEXT,
        latency_ms INTEGER,
        trace_json TEXT,
        FOREIGN KEY (session_id) REFERENCES command_center_sessions(session_id)
    )
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_cc_turns_session
    ON command_center_turns (session_id, created_at DESC)
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_cc_turns_created
    ON command_center_turns (created_at DESC)
    """)

    cursor.execute("SELECT COUNT(*) FROM app_config")
    if cursor.fetchone()[0] == 0:
        default_config = [
            ("api_base_url", "http://35.244.15.150:8080"),
            ("stream_url", "http://35.244.15.150/listen/orai_radio/radio.mp3"),
            ("backup_stream_url", ""),
            ("maintenance_mode", "false"),
            ("maintenance_message", "Orai Radio is under maintenance. We will be back online soon!"),
            ("force_update", "false"),
            ("minimum_supported_version", "1")
        ]
        cursor.executemany(
            "INSERT INTO app_config (key, value) VALUES (?, ?)",
            default_config
        )
        conn.commit()

    # Seed default playout schedule if empty
    cursor.execute("SELECT COUNT(*) FROM playout_schedule")
    if cursor.fetchone()[0] == 0:
        default_schedule = [
            ("08:00 AM - 09:00 AM", "Bundelkhand Devotional Hour", "Start the day with traditional Bundeli bhajans."),
            ("09:00 AM - 10:00 AM", "Mandi Report & Regional News", "Live market prices from Orai and regional updates."),
            ("07:00 PM - 09:00 PM", "RJ Neena Farmaish Capsule", "Listener song requests and dedications with RJ Neena.")
        ]
        cursor.executemany(
            "INSERT INTO playout_schedule (time_slot, program_name, description) VALUES (?, ?, ?)",
            default_schedule
        )
        conn.commit()
    
    # Seed default Market Rates if empty
    cursor.execute("SELECT COUNT(*) FROM market_rates")
    if cursor.fetchone()[0] == 0:
        default_rates = [
            ("Matar (Green Peas)", "4,200", "per quintal", "up", "+150", "mandi"),
            ("Gehu (Wheat)", "2,450", "per quintal", "down", "-20", "mandi"),
            ("Sarso (Mustard)", "5,800", "per quintal", "up", "+50", "mandi"),
            ("Gold Rate (24K)", "72,450", "per 10g", "up", "+320", "sarafa"),
            ("Silver Rate", "88,200", "per 1kg", "down", "-150", "sarafa")
        ]
        cursor.executemany(
            "INSERT INTO market_rates (item_name, price, unit, trend, price_change, category) VALUES (?, ?, ?, ?, ?, ?)",
            default_rates
        )
        conn.commit()

    # Seed default now_playing if empty
    cursor.execute("SELECT COUNT(*) FROM now_playing")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO now_playing (title, artist, duration_seconds) VALUES (?, ?, ?)", 
                       ("Bundeli Folk Fusion (Mix)", "Local Artists Orai", 180))
        conn.commit()

    # Seed default Sponsor Campaigns if empty
    cursor.execute("SELECT COUNT(*) FROM sponsor_campaigns")
    if cursor.fetchone()[0] == 0:
        default_campaigns = [
            ("Orai Gold Jewelers", "Shubh Vivah Shagun Campaign", "2026-06-01", "2026-06-30", "media/sponsors/orai_gold_jingle.mp3", 3),
            ("Kalyan Mandi Traders", "Mandi Monsoon Dhamaka", "2026-06-15", "2026-06-25", "media/sponsors/kalyan_mandi_jingle.mp3", 4)
        ]
        cursor.executemany(
            "INSERT INTO sponsor_campaigns (sponsor_name, campaign_name, start_date, end_date, audio_file_path, play_slots_limit) VALUES (?, ?, ?, ?, ?, ?)",
            default_campaigns
        )
        conn.commit()

    # Seed default Voice Personas if empty
    cursor.execute("SELECT COUNT(*) FROM voice_personas")
    if cursor.fetchone()[0] == 0:
        default_personas = [
            ("rj_neena", "RJ Neena Gupta (Bundelkhand Voice)", "21m00Tcm4TlvDq8ikWAM", "Approved", 1),
            ("guest_actor_1", "Bundeli Folk Singer (Guest)", None, "Pending", 1),
            ("unauthorized_voice", "Political Figure Voice Clone", None, "Rejected", 1)
        ]
        cursor.executemany(
            "INSERT INTO voice_personas (id, display_name, elevenlabs_voice_id, consent_status, active) VALUES (?, ?, ?, ?, ?)",
            default_personas
        )
        conn.commit()

    # Seed default Service Registry if empty
    cursor.execute("SELECT COUNT(*) FROM service_registry")
    if cursor.fetchone()[0] == 0:
        backend_url = os.environ.get("BACKEND_INTERNAL_HEALTH_URL") or "http://localhost:8000/api/config/status"
        whatsapp_url = os.environ.get("WHATSAPP_GATEWAY_URL") or "http://localhost:3001/api/status"
        default_services = [
            ("command_center_backend", "core", "FastAPI Backend Admin Console", backend_url, "", "", "", 1, 1, "Healthy", None, '["restart"]'),
            ("whatsapp_gateway", "gateway", "WhatsApp API Node Gateway", whatsapp_url, "npm start", "", "", 1, 1, "Offline", None, '["restart"]'),
            ("azuracast_stream", "stream", "AzuraCast Audio Icecast Stream", "", "", "", "", 1, 1, "unknown", None, "[]"),
            ("neena_operator", "operator", "Neena Gupta Operations Brain Module", None, "", "", "", 1, 1, "Healthy", None, "[]")
        ]
        cursor.executemany(
            """INSERT INTO service_registry (service_name, service_type, display_name, health_url, command_start, command_stop, command_restart, enabled, configured, last_status, last_error, allowed_actions)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            default_services
        )
        conn.commit()

    conn.close()

def add_activity_log(activity_type, detail):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activity_log (activity_type, detail) VALUES (?, ?)",
        (activity_type, detail)
    )
    conn.commit()
    conn.close()

def get_market_rates():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM market_rates")
    rates = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rates

def update_market_rate(item_name, price, trend, price_change):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE market_rates 
        SET price = ?, trend = ?, price_change = ?
        WHERE item_name = ?
    """, (price, trend, price_change, item_name))
    conn.commit()
    conn.close()
    add_activity_log("system", f"Updated market rate for '{item_name}': Price: ₹{price}, Trend: {trend}, Change: {price_change}")

def add_station_command(command_type, payload_json=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO station_commands (command_type, payload_json, status)
        VALUES (?, ?, 'pending')
    """, (command_type, payload_json))
    command_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return command_id

def update_station_command(command_id, status, result_json=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE station_commands
        SET status = ?, result_json = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, result_json, command_id))
    conn.commit()
    conn.close()

def get_last_station_commands(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM station_commands ORDER BY created_at DESC LIMIT ?", (limit,))
    commands = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return commands

def update_station_runtime(service_name, status, details_json=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if there is an existing status and if it's different
    cursor.execute("SELECT status FROM station_runtime_status WHERE service_name = ?", (service_name,))
    row = cursor.fetchone()
    old_status = row[0] if row else None
    
    cursor.execute("""
        INSERT INTO station_runtime_status (service_name, status, last_heartbeat, details_json)
        VALUES (?, ?, CURRENT_TIMESTAMP, ?)
        ON CONFLICT(service_name) DO UPDATE SET
            status = excluded.status,
            last_heartbeat = CURRENT_TIMESTAMP,
            details_json = excluded.details_json
    """, (service_name, status, details_json))
    
    if old_status != status:
        cursor.execute(
            "INSERT INTO activity_log (activity_type, detail) VALUES (?, ?)",
            ("system", f"Runtime status changes: '{service_name}' updated from '{old_status or 'None'}' to '{status}'.")
        )
        
    conn.commit()
    conn.close()

def get_station_runtime_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM station_runtime_status")
    status_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return status_list

def get_recent_activities(limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    activities = []
    
    # Fetch Activity Log table
    try:
        cursor.execute("SELECT timestamp, activity_type, detail FROM activity_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        for row in cursor.fetchall():
            activities.append({
                "timestamp": row["timestamp"],
                "type": row["activity_type"],
                "detail": row["detail"]
            })
    except Exception:
        pass
        
    # Fetch Station Commands
    try:
        cursor.execute("SELECT created_at, command_type, status, result_json FROM station_commands ORDER BY created_at DESC LIMIT ?", (limit,))
        for row in cursor.fetchall():
            res_msg = ""
            if row["result_json"]:
                try:
                    res_msg = json.loads(row["result_json"]).get("message", "")
                except Exception:
                    pass
            
            if row["status"] == "success":
                detail = f"Command '{row['command_type']}' completed successfully. {res_msg}"
            elif row["status"] == "failed":
                detail = f"Command '{row['command_type']}' failed."
            else:
                detail = f"Command '{row['command_type']}' is in state '{row['status']}'."
                
            activities.append({
                "timestamp": row["created_at"],
                "type": "command",
                "detail": detail
            })
    except Exception:
        pass

    activities.sort(key=lambda x: x["timestamp"], reverse=True)
    conn.close()
    return activities[:limit]

def get_now_playing():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM now_playing ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_now_playing(title, artist, duration_seconds=180):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO now_playing (title, artist, duration_seconds) VALUES (?, ?, ?)",
                   (title, artist, duration_seconds))
    conn.commit()
    conn.close()

def get_service_registry():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM service_registry")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def update_service_status(service_name, status, error=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if error is not None:
        cursor.execute("""
            UPDATE service_registry 
            SET last_status = ?, last_error = ?, last_heartbeat = CURRENT_TIMESTAMP 
            WHERE service_name = ?
        """, (status, error, service_name))
    else:
        cursor.execute("""
            UPDATE service_registry 
            SET last_status = ?, last_heartbeat = CURRENT_TIMESTAMP 
            WHERE service_name = ?
        """, (status, service_name))
    conn.commit()
    conn.close()

def add_song_dedication(listener_name, region, dedicated_to, song_title, message=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO song_dedications (listener_name, region, dedicated_to, song_title, message)
        VALUES (?, ?, ?, ?, ?)
    """, (listener_name, region, dedicated_to, song_title, message))
    conn.commit()
    conn.close()

def get_pending_dedications(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM song_dedications WHERE status = 'pending' ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def add_birthday_wish(listener_name, region, wish_for, message=""):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO birthday_wishes (listener_name, region, wish_for, message)
        VALUES (?, ?, ?, ?)
    """, (listener_name, region, wish_for, message))
    conn.commit()
    conn.close()

def get_pending_birthday_wishes(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM birthday_wishes WHERE status = 'pending' ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def mark_dedication_announced(dedication_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE song_dedications SET status = 'announced' WHERE id = ?", (dedication_id,))
    conn.commit()
    conn.close()

def add_sponsor_campaign(sponsor_name, campaign_name, start_date, end_date, audio_file_path, play_slots_limit=5):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sponsor_campaigns (sponsor_name, campaign_name, start_date, end_date, audio_file_path, play_slots_limit)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (sponsor_name, campaign_name, start_date, end_date, audio_file_path, play_slots_limit))
    conn.commit()
    conn.close()

def get_active_campaigns(target_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM sponsor_campaigns 
        WHERE start_date <= ? AND end_date >= ? AND is_active = 1
    """, (target_date, target_date))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def add_approval_item(asset_type, content_data, source_path=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO approval_queue (asset_type, content_data, source_path, status)
        VALUES (?, ?, ?, 'pending_review')
    """, (asset_type, content_data, source_path))
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id

def get_pending_approvals(limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM approval_queue WHERE status = 'pending_review' ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def update_approval_status(item_id, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE approval_queue 
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, item_id))
    conn.commit()
    conn.close()

def add_voice_persona(persona_id, display_name, elevenlabs_voice_id=None, consent_status="Pending", active=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO voice_personas (id, display_name, elevenlabs_voice_id, consent_status, active)
        VALUES (?, ?, ?, ?, ?)
    """, (persona_id, display_name, elevenlabs_voice_id, consent_status, active))
    conn.commit()
    conn.close()

def get_voice_persona(persona_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM voice_personas WHERE id = ?", (persona_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_scraped_reference(actor_name, source_url, local_wav_path, duration_seconds=0.0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO voice_scraped_references (actor_name, source_url, local_wav_path, duration_seconds)
        VALUES (?, ?, ?, ?)
    """, (actor_name, source_url, local_wav_path, duration_seconds))
    conn.commit()
    conn.close()

def add_voice_asset(script_id, voice_id, text_content, audio_file_path, status="rendered"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO voice_assets (script_id, voice_id, text_content, audio_file_path, status)
        VALUES (?, ?, ?, ?, ?)
    """, (script_id, voice_id, text_content, audio_file_path, status))
    conn.commit()
    conn.close()

def log_voice_usage(voice_id, character_count, estimated_cost_usd=0.0):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO voice_usage_log (voice_id, character_count, estimated_cost_usd)
        VALUES (?, ?, ?)
    """, (voice_id, character_count, estimated_cost_usd))
    conn.commit()
    conn.close()

def get_voice_usage_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(character_count) as total_chars, SUM(estimated_cost_usd) as total_cost FROM voice_usage_log")
    row = cursor.fetchone()
    conn.close()
    if row and row["total_chars"] is not None:
        return {"total_chars": row["total_chars"], "total_cost": row["total_cost"]}
    return {"total_chars": 0, "total_cost": 0.0}

def get_playout_schedule():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM playout_schedule WHERE is_active = 1 ORDER BY id ASC")
    schedule = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return schedule

def add_schedule_slot(time_slot, program_name, description=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO playout_schedule (time_slot, program_name, description)
        VALUES (?, ?, ?)
    """, (time_slot, program_name, description))
    conn.commit()
    conn.close()
    add_activity_log("system", f"Added schedule slot: {time_slot} -> {program_name}")

def clear_playout_schedule():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM playout_schedule")
    conn.commit()
    conn.close()
    add_activity_log("system", "Cleared daily playout schedule.")

def add_chat_message(role, message):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO neena_chat_history (role, message)
        VALUES (?, ?)
    """, (role, message))
    conn.commit()
    conn.close()

def get_chat_history(limit=15):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM (
            SELECT role, message, id FROM neena_chat_history ORDER BY id DESC LIMIT ?
        ) ORDER BY id ASC
    """, (limit,))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history

def get_app_config() -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM app_config")
    rows = cursor.fetchall()
    conn.close()
    
    config = {}
    for row in rows:
        val = row["value"]
        if val.lower() == "true":
            config[row["key"]] = True
        elif val.lower() == "false":
            config[row["key"]] = False
        elif val.isdigit():
            config[row["key"]] = int(val)
        else:
            config[row["key"]] = val
    return config

def update_app_config(key: str, value: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO app_config (key, value)
        VALUES (?, ?)
    """, (key, str(value)))
    conn.commit()
    conn.close()
    add_activity_log("system", f"Updated app config: {key} -> {value}")


def start_command_center_session(session_id: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO command_center_sessions (session_id, started_at, ended_at, end_reason)
        VALUES (?, CURRENT_TIMESTAMP, NULL, NULL)
        """,
        (session_id,),
    )
    conn.commit()
    conn.close()


def end_command_center_session(session_id: str, end_reason: str = "lock") -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE command_center_sessions
        SET ended_at = CURRENT_TIMESTAMP, end_reason = ?
        WHERE session_id = ? AND ended_at IS NULL
        """,
        (end_reason, session_id),
    )
    conn.commit()
    conn.close()


def command_center_session_is_open(session_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1 FROM command_center_sessions
        WHERE session_id = ? AND ended_at IS NULL
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None


def insert_command_center_turn(
    *,
    session_id: str | None,
    channel: str,
    user_input: str,
    assistant_reply: str | None = None,
    intent: str | None = None,
    route: str | None = None,
    action_type: str | None = None,
    policy_decision: str | None = None,
    command_triggered: str | None = None,
    outcome: str = "success",
    blocked: bool = False,
    block_reason: str | None = None,
    selected_model: str | None = None,
    actual_model: str | None = None,
    latency_ms: int | None = None,
    trace_json: str | None = None,
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO command_center_turns (
            session_id, channel, user_input, assistant_reply, intent, route,
            action_type, policy_decision, command_triggered, outcome, blocked,
            block_reason, selected_model, actual_model, latency_ms, trace_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            channel,
            user_input,
            assistant_reply,
            intent,
            route,
            action_type,
            policy_decision,
            command_triggered,
            outcome,
            1 if blocked else 0,
            block_reason,
            selected_model,
            actual_model,
            latency_ms,
            trace_json,
        ),
    )
    turn_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    return turn_id


def list_command_center_sessions(limit: int = 20) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT session_id, started_at, ended_at, end_reason
        FROM command_center_sessions
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (max(1, min(int(limit), 100)),),
    )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def list_command_center_turns(
  session_id: str | None = None,
  limit: int = 50,
) -> list[dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    safe_limit = max(1, min(int(limit), 200))
    if session_id:
        cursor.execute(
            """
            SELECT id, session_id, created_at, channel, user_input, assistant_reply,
                   intent, route, action_type, policy_decision, command_triggered,
                   outcome, blocked, block_reason, selected_model, actual_model,
                   latency_ms, trace_json
            FROM command_center_turns
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, safe_limit),
        )
    else:
        cursor.execute(
            """
            SELECT id, session_id, created_at, channel, user_input, assistant_reply,
                   intent, route, action_type, policy_decision, command_triggered,
                   outcome, blocked, block_reason, selected_model, actual_model,
                   latency_ms, trace_json
            FROM command_center_turns
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    if not session_id:
        rows.reverse()
    return rows


def list_command_center_turns_between(
    start_iso: str,
    end_iso: str,
    *,
    limit: int = 80,
    channels: list[str] | None = None,
) -> list[dict]:
    """Turns with created_at in [start_iso, end_iso), oldest-first.

    Used for day-memory recall. Channel filter optional (owner channels).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    safe_limit = max(1, min(int(limit), 200))
    start = (start_iso or "").strip()
    end = (end_iso or "").strip()
    if not start or not end:
        conn.close()
        return []

    chan = [c.strip() for c in (channels or []) if (c or "").strip()]
    if chan:
        placeholders = ",".join("?" for _ in chan)
        cursor.execute(
            f"""
            SELECT id, session_id, created_at, channel, user_input, assistant_reply,
                   intent, route, action_type, policy_decision, command_triggered,
                   outcome, blocked, block_reason, selected_model, actual_model,
                   latency_ms
            FROM command_center_turns
            WHERE created_at >= ? AND created_at < ?
              AND channel IN ({placeholders})
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (start, end, *chan, safe_limit),
        )
    else:
        cursor.execute(
            """
            SELECT id, session_id, created_at, channel, user_input, assistant_reply,
                   intent, route, action_type, policy_decision, command_triggered,
                   outcome, blocked, block_reason, selected_model, actual_model,
                   latency_ms
            FROM command_center_turns
            WHERE created_at >= ? AND created_at < ?
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (start, end, safe_limit),
        )
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

