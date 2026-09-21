"""Helpers for point labels and trend display."""
from __future__ import annotations

import datetime
import json
import re

def format_human_date(dt):
    if not dt:
        return "-"
    now = datetime.datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return "Il y a moins d'une minute"
    elif seconds < 1800:
        return "Il y a quelques minutes"
    elif seconds < 7200:
        return "Il y a une demi-heure"

    today = now.date()
    dt_date = dt.date()
    days_diff = (today - dt_date).days

    if days_diff == 0:
        return "Aujourd'hui"
    elif days_diff == 1:
        return "Hier"
    elif days_diff < 7:
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        return jours[dt.weekday()]
    elif days_diff < 14:
        return "La semaine passée"
    elif days_diff < 21:
        return "Il y a deux semaines"
    else:
        return dt.strftime("%d/%m/%Y")

def _calc_trend(curr, prev):
    if curr is None or prev is None:
        return ""
    if curr == prev:
        return "stable"
    try:
        cf = float(curr)
        pf = float(prev)
        if cf > pf: return "up"
        if cf < pf: return "down"
        return "stable"
    except ValueError:
        return "diff"

_MODBUS_OBJ_RE = re.compile(r'^FC(\d+)_(-?\d+)$', re.IGNORECASE)

def _load_template_point_labels(cur, hostnames, chantier_id):
    """
    Resout le libelle (description) des points a partir du template partage
    utilise par leur appareil, sans jamais dupliquer ce libelle : le boitier
    ne renvoie que "quel appareil utilise quel template" (boitier_template_usage,
    voir services/sync.py::_push_template_usage) ; le libelle vient du
    registre/objet correspondant dans la definition du template
    (boitier_modbus_templates / boitier_bacnet_templates), deja synchronisee
    quand le template est partage. Voir docs/integrations/FLEET_API_CHANGES.md
    (depot rpinode) pour le contexte complet.

    Retourne un dict {(boitier_id, protocol, device): {obj: label}} pret a
    etre consulte pour chaque point affiche.
    """
    if not hostnames:
        return {}

    format_strings = ','.join(['%s'] * len(hostnames))
    cur.execute(f'''
        SELECT boitier_id, protocol, device_name, revision_uuid
        FROM boitier_template_usage
        WHERE boitier_id IN ({format_strings}) AND chantier_id = %s
    ''', tuple(hostnames) + (chantier_id,))
    usage_rows = cur.fetchall()
    if not usage_rows:
        return {}

    modbus_revs = {r['revision_uuid'] for r in usage_rows if (r['protocol'] or 'modbus') == 'modbus'}
    bacnet_revs = {r['revision_uuid'] for r in usage_rows if r['protocol'] == 'bacnet'}

    # Pour Modbus, les registres sont identifies par (fonction, adresse) ;
    # l'"obj" du point (ex: "FC04_200") est reparse pour retrouver ce couple.
    reg_labels_by_rev = {}
    if modbus_revs:
        fmt = ','.join(['%s'] * len(modbus_revs))
        cur.execute(f"SELECT revision_uuid, definition_json FROM boitier_modbus_templates WHERE revision_uuid IN ({fmt})", tuple(modbus_revs))
        for row in cur.fetchall():
            try:
                definition = json.loads(row['definition_json'])
            except (TypeError, ValueError):
                continue
            labels = {}
            for read in definition.get('reads', []) or []:
                label = read.get('label') or read.get('name')
                if not label:
                    continue
                try:
                    func = int(read.get('function', 3))
                    addr = int(read.get('address', read.get('reg', 0)))
                except (TypeError, ValueError):
                    continue
                labels[(func, addr)] = label
            reg_labels_by_rev[row['revision_uuid']] = labels

    # Pour BACnet, l'"obj" du point correspond directement au champ "obj" du
    # template (ex: "analog-input:1").
    obj_labels_by_rev = {}
    if bacnet_revs:
        fmt = ','.join(['%s'] * len(bacnet_revs))
        cur.execute(f"SELECT revision_uuid, definition_json FROM boitier_bacnet_templates WHERE revision_uuid IN ({fmt})", tuple(bacnet_revs))
        for row in cur.fetchall():
            try:
                definition = json.loads(row['definition_json'])
            except (TypeError, ValueError):
                continue
            labels = {}
            for obj_def in definition.get('objects', []) or []:
                label = obj_def.get('name') or obj_def.get('label')
                obj_key = obj_def.get('obj')
                if label and obj_key:
                    labels[str(obj_key)] = label
            obj_labels_by_rev[row['revision_uuid']] = labels

    result = {}
    for r in usage_rows:
        protocol = r['protocol'] or 'modbus'
        rev_uuid = r['revision_uuid']
        key = (r['boitier_id'], protocol, str(r['device_name']))
        if protocol == 'bacnet':
            result[key] = obj_labels_by_rev.get(rev_uuid, {})
        else:
            result[key] = reg_labels_by_rev.get(rev_uuid, {})
    return result

def _resolve_point_label(tpl_labels, boitier_id, protocol, device, obj):
    """Retrouve le libelle d'un point precis dans le resultat de
    `_load_template_point_labels`, ou None si son template n'est pas
    partage / connu de docs (le point reste alors affiche sans description)."""
    labels = tpl_labels.get((boitier_id, protocol, str(device)))
    if not labels:
        return None
    if protocol == 'bacnet':
        return labels.get(str(obj))
    m = _MODBUS_OBJ_RE.match(str(obj))
    if not m:
        return None
    return labels.get((int(m.group(1)), int(m.group(2))))
