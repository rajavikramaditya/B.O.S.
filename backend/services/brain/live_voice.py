"""Gemini Live Voice Call WebSocket endpoint handler."""
from __future__ import annotations

import os
import json
import base64
import asyncio
import logging
import aiohttp
import re
import uuid
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

def load_recent_turns_context(limit: int = 5) -> list:
    try:
        import database as db
        turns = db.list_command_center_turns(limit=limit)
        turns_oldest_first = list(reversed(turns))
        
        google_turns = []
        for turn in turns_oldest_first:
            user_in = turn.get("user_input") or ""
            assistant_rep = turn.get("assistant_reply") or ""
            # Strip [customer...] tag
            user_in_clean = re.sub(r"^\[customer\s+[^\]]+\]\s*", "", user_in).strip()
            if user_in_clean and assistant_rep:
                google_turns.append({
                    "role": "user",
                    "parts": [{"text": user_in_clean}]
                })
                google_turns.append({
                    "role": "model",
                    "parts": [{"text": assistant_rep}]
                })
        return google_turns
    except Exception as e:
        logger.error("Failed to load recent turns context for voice session: %s", e)
        return []

async def handle_live_voice_websocket(websocket: WebSocket) -> None:
    from services.llm.provider_router import get_gemini_api_key
    api_key = get_gemini_api_key()
    if not api_key:
        logger.error("Gemini API key missing for Live Voice connection")
        await websocket.close(code=4003, reason="API Key Missing")
        return

    # Google Gemini Live API websocket endpoint
    google_ws_url = (
        f"wss://generativelanguage.googleapis.com/ws/"
        f"google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent?key={api_key}"
    )

    session_id = f"voice-{uuid.uuid4().hex[:8]}"
    await websocket.accept()
    logger.info("Live Voice client WebSocket accepted, session_id=%s", session_id)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.ws_connect(google_ws_url) as google_ws:
                logger.info("Connected to Google Gemini Live WebSocket API")

                # Send the Setup message to Google Live API immediately
                setup_msg = {
                    "setup": {
                        "model": "models/gemini-2.5-flash-native-audio-latest",
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {
                                "voiceConfig": {
                                    "prebuiltVoiceConfig": {
                                        "voiceName": "Kore"
                                    }
                                }
                            }
                        },
                        "systemInstruction": {
                            "parts": [
                                {
                                    "text": "You are Neena Gupta, the AI assistant of Orai Radio. Keep your responses short, conversational, and directly in Hindi. Speak immediately without explaining your thinking or using preambles."
                                }
                            ]
                        }
                    }
                }
                await google_ws.send_json(setup_msg)

                # Send initial clientContent turn with recent database chat history context loaded
                recent_turns = load_recent_turns_context(5)
                recent_turns.append({
                    "role": "user",
                    "parts": [
                        {
                            "text": "Hello Neena! Greet the owner right now in Hindi by saying exactly: 'Sir, ab main live hoon. Batayein kya karna hai?'"
                        }
                    ]
                })
                
                initial_msg = {
                    "clientContent": {
                        "turns": recent_turns,
                        "turnComplete": True
                    }
                }
                await google_ws.send_json(initial_msg)

                # Define task to read from Google and forward to client
                user_input_accumulated = ""
                assistant_reply_accumulated = ""

                async def receive_from_google():
                    nonlocal user_input_accumulated, assistant_reply_accumulated
                    try:
                        async for msg in google_ws:
                            if msg.type in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                                raw_str = msg.data if msg.type == aiohttp.WSMsgType.TEXT else msg.data.decode("utf-8")
                                logger.info("Received message from Google: type=%s, len=%d, start=%s", msg.type, len(raw_str), raw_str[:300])
                                data = json.loads(raw_str)
                                server_content = data.get("serverContent", {})
                                
                                # Accumulate text responses from parts
                                model_turn = server_content.get("modelTurn", {})
                                parts = model_turn.get("parts", [])
                                for part in parts:
                                    if "text" in part:
                                        assistant_reply_accumulated += part["text"]
                                    inline = part.get("inlineData") or part.get("inline_data")
                                    if inline and inline.get("data"):
                                        audio_base64 = inline["data"]
                                        audio_bytes = base64.b64decode(audio_base64)
                                        # Forward raw binary audio bytes to the browser client
                                        await websocket.send_bytes(audio_bytes)
                                
                                # Accumulate user input transcription if any
                                input_trans = server_content.get("inputTranscription", {})
                                if input_trans and input_trans.get("text"):
                                    user_input_accumulated += input_trans["text"]
                                
                                # If turn is complete, save to database
                                if server_content.get("turnComplete"):
                                    if assistant_reply_accumulated:
                                        try:
                                            import database as db
                                            user_in = user_input_accumulated.strip() or "[Voice Input]"
                                            db.insert_command_center_turn(
                                                session_id=session_id,
                                                channel="live_voice",
                                                user_input=user_in,
                                                assistant_reply=assistant_reply_accumulated,
                                                outcome="success"
                                            )
                                            logger.info("Saved live voice turn to DB: User='%s', Neena='%s'", user_in, assistant_reply_accumulated)
                                        except Exception as db_err:
                                            logger.error("Failed to save live voice turn: %s", db_err)
                                        user_input_accumulated = ""
                                        assistant_reply_accumulated = ""
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                logger.info("Google Live API connection closed: WSMsgType.CLOSED")
                                break
                    except Exception as e:
                        logger.error("Error receiving from Google Live API: %s", e)
                    finally:
                        try:
                            await websocket.close()
                        except Exception:
                            pass

                # Define task to read from client and forward to Google
                async def send_to_google():
                    try:
                        chunk_count = 0
                        async for msg in websocket.iter_bytes():
                            chunk_count += 1
                            if chunk_count <= 5 or chunk_count % 100 == 0:
                                logger.info("Client audio flow: chunk #%d (%d bytes)", chunk_count, len(msg))
                            # Wrap raw binary audio bytes in the required envelope
                            encoded_data = base64.b64encode(msg).decode("utf-8")
                            input_msg = {
                                "realtimeInput": {
                                    "mediaChunks": [
                                        {
                                            "mimeType": "audio/pcm;rate=16000",
                                            "data": encoded_data
                                        }
                                    ]
                                }
                            }
                            await google_ws.send_json(input_msg)
                    except WebSocketDisconnect:
                        logger.info("Live Voice client disconnected")
                    except Exception as e:
                        logger.error("Error forwarding client audio to Google: %s", e)
                    finally:
                        try:
                            await google_ws.close()
                        except Exception:
                            pass

                # Run both tasks concurrently
                await asyncio.gather(
                    receive_from_google(),
                    send_to_google()
                )

        except Exception as e:
            logger.error("Failed to connect to Google Gemini Live API: %s", e)
            try:
                await websocket.close(code=4000, reason="Google Connection Failed")
            except Exception:
                pass
