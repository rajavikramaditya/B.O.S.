import os
import sys
import requests
import json
import urllib3

# Suppress self-signed cert warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def verify():
    admin_key = os.environ.get("ADMIN_KEY", "").strip()
    if not admin_key:
        print("ERROR: ADMIN_KEY environment variable is missing.")
        sys.exit(1)

    base_url = "https://127.0.0.1:8443"
    headers = {
        "Authorization": f"Bearer {admin_key}",
        "Content-Type": "application/json"
    }

    # Helper to create capsule
    def create_capsule(title):
        create_payload = {
            "script_text": f"Verify M1 deployment test script content - {title}.",
            "capsule_type": "rj_intro",
            "title": title,
            "topic": "testing",
            "language": "Hindi",
            "tone": "casual",
            "created_by": "verification_script"
        }
        res = requests.post(f"{base_url}/api/neena/capsules", headers=headers, json=create_payload, verify=False)
        if res.status_code != 200:
            print(f"Create failed: {res.text}")
            sys.exit(1)
        capsule = res.json().get("capsule", {})
        print(f"Created pending capsule '{title}' with ID: {capsule.get('id')}")
        return capsule

    # Helper to send chat
    def send_chat(msg):
        print(f"\nSending command: '{msg}'")
        chat_payload = {"message": msg, "model": "auto"}
        r = requests.post(f"{base_url}/api/neena/chat", headers=headers, json=chat_payload, verify=False)
        if r.status_code == 200:
            resp_data = r.json()
            print(f"Reply: {resp_data.get('reply')}")
            print(f"Action: {resp_data.get('action_type') or resp_data.get('action')}")
            return resp_data
        else:
            print(f"Failed: {r.text}")
            return None

    # Helper to get DB status
    def get_capsule_status(capsule_id):
        res = requests.get(f"{base_url}/api/neena/capsules/{capsule_id}", headers=headers, verify=False)
        cap = res.json().get("capsule", {})
        return cap.get("status"), cap.get("approval_status"), cap.get("broadcast_ready")

    created_ids = []

    try:
        # Test Case 1: Revision Flow
        print("\n=== RUNNING REVISION TEST ===")
        cap1 = create_capsule("Revision Test Capsule")
        cid1 = cap1.get("id")
        created_ids.append((cid1, cap1.get("approval_queue_id")))

        send_chat("revision chahiye")
        status, app_status, br_ready = get_capsule_status(cid1)
        print(f"DB State -> Status: {status}, Approval Status: {app_status}, Broadcast Ready: {br_ready}")
        assert status == "needs_revision"
        assert app_status == "needs_revision"
        assert br_ready == 0 or br_ready is False

        # Test Case 2: Rejection Flow
        print("\n=== RUNNING REJECTION TEST ===")
        cap2 = create_capsule("Rejection Test Capsule")
        cid2 = cap2.get("id")
        created_ids.append((cid2, cap2.get("approval_queue_id")))

        send_chat("script reject karo")
        status, app_status, br_ready = get_capsule_status(cid2)
        print(f"DB State -> Status: {status}, Approval Status: {app_status}, Broadcast Ready: {br_ready}")
        assert status == "rejected"
        assert app_status == "rejected"
        assert br_ready == 0 or br_ready is False

    finally:
        # Cleanup
        print("\nCleaning up test capsules from database...")
        import subprocess
        for cid, aid in created_ids:
            cleanup_cmd = f"sqlite3 backend/radio_station.db \"DELETE FROM broadcast_capsules WHERE id = {cid}; DELETE FROM approval_queue WHERE id = {aid or 0};\""
            ssh_cmd = ["ssh", "-i", "C:\\Users\\vikas\\.ssh\\gcp_key", "mahilkingdomorai@35.244.15.150", f"cd /opt/orai-radio-command-center && {cleanup_cmd}"]
            subprocess.run(ssh_cmd, check=True)
            print(f"Cleaned capsule #{cid}")

if __name__ == "__main__":
    verify()
