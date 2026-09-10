from core.database import get_db
db = get_db()
with db.cursor() as cur:
    cur.execute("DESCRIBE chantiers")
    for row in cur.fetchall():
        print(row)
