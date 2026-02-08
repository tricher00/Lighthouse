import sqlite3
from pathlib import Path

db_path = Path("data/lighthouse.db")
if not db_path.exists():
    print("Database not found")
else:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(traffic_routes)")
    columns = [row[1] for row in cursor.fetchall()]
    print("Columns in traffic_routes:")
    for col in columns:
        print(f" - {col}")
    conn.close()
