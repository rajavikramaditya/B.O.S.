import os
import sys

# Adjust path to find sibling imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db

def load_chat_history_contents(limit: int = 10) -> list:
    """
    Loads conversation turns from SQLite database and formats them into
    Gemini API contents array, ensuring strict alternating roles (user/model).
    """
    try:
        history = db.get_chat_history(limit=limit)
    except Exception:
        history = []
        
    contents = []
    last_role = None
    for h in history:
        role = "user" if h["role"] == "user" else "model"
        if role == last_role:
            continue
        contents.append({
            "role": role,
            "parts": [{"text": h["message"]}]
        })
        last_role = role
        
    # Gemini requires contents to start with user/model, but if the very last loaded history is a 'user' message,
    # appending the current user message will create consecutive identical roles. We pop the last turn if it was 'user'.
    if last_role == "user" and contents:
        contents.pop()
        
    return contents

def save_chat_turn(role: str, message: str):
    """
    Saves a single conversation turn (role: 'user' or 'model') to SQLite history.
    """
    try:
        db.add_chat_message(role, message)
    except Exception:
        pass
