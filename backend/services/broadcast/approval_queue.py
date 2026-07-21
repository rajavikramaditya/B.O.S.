import os
import sys
import shutil
import logging

# Adjust path to find sibling imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
import database as db

logger = logging.getLogger(__name__)

def queue_asset_for_review(asset_type: str, content_data: str, source_path: str = None) -> int:
    """
    Writes a row in SQLite approval_queue table with status = 'pending_review'
    """
    try:
        item_id = db.add_approval_item(asset_type, content_data, source_path)
        db.add_activity_log("staging", f"Queued {asset_type} for review (ID: {item_id})")
        return item_id
    except Exception as e:
        logger.error(f"Failed to queue asset for review: {e}")
        raise e

def process_approval_action(approval_id: int, action: str) -> dict:
    """
    Processes an approval action ('approve' or 'reject').
    If action is 'approve':
        - If source_path exists, copies it to the active playout directory.
        - Sets status to 'approved'.
    If action is 'reject':
        - If source_path exists, deletes the sandboxed file.
        - Sets status to 'rejected'.
    """
    try:
        # Fetch the item first to know its details
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM approval_queue WHERE id = ?", (approval_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"success": False, "message": f"Approval item ID {approval_id} not found."}
            
        item = dict(row)
        asset_type = item.get("asset_type")
        source_path = item.get("source_path")
        
        if action == "approve":
            # Copy file to active playout/capsules folder if applicable
            if source_path and os.path.exists(source_path):
                # active playout directory
                playout_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "playout", "active")
                os.makedirs(playout_dir, exist_ok=True)
                dest_path = os.path.join(playout_dir, os.path.basename(source_path))
                shutil.copy2(source_path, dest_path)
                logger.info(f"Approved asset ID {approval_id}: Copied {source_path} -> {dest_path}")
                
            db.update_approval_status(approval_id, "approved")
            try:
                from services.broadcast.capsule_service import update_capsule_approval_status
                update_capsule_approval_status(approval_id, "approved")
            except Exception as cap_err:
                logger.warning(f"Capsule approval sync failed for {approval_id}: {cap_err}")
            db.add_activity_log("staging", f"Approved {asset_type} (ID: {approval_id})")
            return {"success": True, "message": f"Asset {approval_id} ({asset_type}) approved successfully."}
            
        elif action in ("reject", "dismiss", "delete"):
            # Delete temporary sandbox file if applicable
            if source_path and os.path.exists(source_path):
                try:
                    os.remove(source_path)
                    logger.info(f"Rejected asset ID {approval_id}: Deleted temp file {source_path}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file {source_path} on rejection: {e}")

            new_status = "dismissed" if action in ("dismiss", "delete") else "rejected"
            db.update_approval_status(approval_id, new_status)
            try:
                from services.broadcast.capsule_service import update_capsule_approval_status
                update_capsule_approval_status(approval_id, "rejected")
            except Exception as cap_err:
                logger.warning(f"Capsule rejection sync failed for {approval_id}: {cap_err}")
            db.add_activity_log("staging", f"{new_status.title()} {asset_type} (ID: {approval_id})")
            return {"success": True, "message": f"Asset {approval_id} ({asset_type}) {new_status}."}

        else:
            return {"success": False, "message": f"Invalid action '{action}'. Use 'approve', 'reject', or 'dismiss'."}
            
    except Exception as e:
        logger.error(f"Error processing approval action: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}
