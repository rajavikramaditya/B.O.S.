import os
import sys

def main():
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE cockpit_jobs SET status = 'failed' WHERE status = 'running'")
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    print(f"Stuck cockpit jobs cleared: {rows_affected} jobs updated.")

if __name__ == "__main__":
    main()
