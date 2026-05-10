import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from core.db import init_db_pool, get_db

init_db_pool()

with get_db() as (conn, cur):
    try:
        cur.execute("ALTER TABLE absence_events ADD COLUMN is_on_pip BOOLEAN DEFAULT FALSE;")
        conn.commit()
        print("Successfully added is_on_pip to absence_events table.")
    except Exception as e:
        print(f"Error: {e}")
