"""Routes for the node inventory."""
from __future__ import annotations

import datetime

from core.database import get_db
from web.templating import view
from web.ui import format_human_date, ui_app

@ui_app.get("/nodes")
def nodes_view():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute('''
                SELECT b.id, b.hostname, b.tailscale_name, b.last_sync_at, b.last_ip, c.ref as chantier_ref
                FROM boitier_registre b
                LEFT JOIN chantiers c ON b.chantier_id = c.id
                ORDER BY b.id
            ''')
            boitiers = cur.fetchall()

            cur.execute('SELECT boitier_id, COUNT(*) as c FROM boitier_trends GROUP BY boitier_id')
            trends_count = {row['boitier_id']: row['c'] for row in cur.fetchall()}

            cur.execute('SELECT boitier_id, COUNT(*) as c FROM boitier_points_config GROUP BY boitier_id')
            config_count = {row['boitier_id']: row['c'] for row in cur.fetchall()}
    finally:
        db.close()

    return view('nodes',
                title='Nodes - Deltathermic',
                boitiers=boitiers,
                trends_count=trends_count,
                config_count=config_count,
                format_human_date=format_human_date,
                datetime=datetime)
