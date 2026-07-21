import os
import sys
import shutil
import logging

# Adjust path to find sibling imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db

logger = logging.getLogger(__name__)


def push_capsule_local_simulated(file_path: str, playlist_name: str) -> dict:
    """
    Explicit development-only local folder copy. Never reported as real AzuraCast API success.
  Requires AZURACAST_PUSH_MODE=local_simulated and is only invoked from azuracast_client.
    """
    if not os.path.exists(file_path):
        return {"success": False, "message": f"Source file {file_path} does not exist."}

    try:
        azura_playout_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "playout",
            "azuracast_sync",
            playlist_name,
        )
        os.makedirs(azura_playout_dir, exist_ok=True)

        dest_path = os.path.join(azura_playout_dir, os.path.basename(file_path))
        shutil.copy2(file_path, dest_path)

        db.add_activity_log(
            "playout",
            f"LOCAL_SIMULATED playout copy '{os.path.basename(file_path)}' -> {dest_path}",
        )
        logger.info("Local simulated playout copy %s -> %s", file_path, dest_path)

        return {
            "success": True,
            "source": file_path,
            "destination": dest_path,
            "playlist": playlist_name,
            "mode": "local_simulated",
            "message": (
                "Local simulated copy only — not real AzuraCast API push. "
                "Set real API config for production."
            ),
        }
    except Exception as e:
        logger.error(f"Error in local simulated playout copy: {e}")
        return {"success": False, "message": f"Local simulated copy failed: {str(e)}"}


# Backward-compatible alias (deprecated)
def push_capsule_to_azuracast_playlist(file_path: str, playlist_name: str) -> dict:
    """DEPRECATED — use push_capsule_local_simulated via AZURACAST_PUSH_MODE=local_simulated only."""
    result = push_capsule_local_simulated(file_path, playlist_name)
    if result.get("success"):
        result["mode"] = "simulated"
    return result
