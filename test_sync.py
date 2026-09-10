from db import get_db

db = get_db()
with db.cursor() as cur:
    cur.execute("SELECT token_hash FROM boitier_registre LIMIT 1")
    res = cur.fetchone()
    print("Has token:", bool(res))
