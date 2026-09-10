"""Relevés historiques (trends), configuration des points scannés, et
suppression de colonnes personnalisées. Extrait d'api.py lors de la
refonte (voir CAHIER-DES-CHARGES-REFONTE.md)."""
from __future__ import annotations

from bottle import request

from core.database import get_db
from web.api import api_app
from web.responses import json_error, json_ok
from services.fleet import authenticate_boitier, log_write, notify_fleet_change

@api_app.post("/trends")
def trends():
    """
    Envoie des relevés historiques (trends) de capteurs.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Payload:
        {
            "trends": [
                {
                    "s": "ID_site",
                    "p": "bacnet",
                    "t": 1698240000,
                    "d": "1234",
                    "o": "AI:1",
                    "v": "23.5"
                }
            ]
        }

    Réponse:
        {
            "ok": true,
            "status": "ok",
            "received": 1,
            "inserted": 1
        }
    """
    # Ouverture de la connexion à la base de données
    db = get_db()
    try:
        with db.cursor() as cur:
            # Authentification du boîtier via son jeton pour vérifier ses droits d'accès
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            # Récupération de la charge utile JSON envoyée par le boîtier
            data = request.json or {}
            trends_data = data.get("trends", [])

            # S'il n'y a aucune donnée à traiter, on retourne immédiatement un succès
            if not trends_data:
                return json_ok({"status": "ok", "received": 0, "inserted": 0})

            # L'identifiant (hostname) du boîtier qui servira de référence pour chaque ligne
            boitier_id = boitier["hostname"]

            # Préparation des enregistrements pour une insertion groupée (batch)
            values = []
            for t in trends_data:
                # Vérification de la présence de tous les champs obligatoires :
                # p: protocole, t: timestamp, d: device, o: object, v: value
                if "p" not in t or "t" not in t or "d" not in t or "o" not in t or "v" not in t:
                    continue

                # Conversion des types et troncature des chaînes de caractères aux limites
                # des colonnes en base pour éviter des erreurs SQL de débordement
                values.append((
                    boitier_id,
                    str(t.get("s", ""))[:128],  # Site (champ optionnel, par défaut vide)
                    str(t["p"])[:32],           # Protocole (ex: bacnet, modbus...)
                    int(t["t"]),                # Horodatage (epoch)
                    str(t["d"])[:128],          # Équipement / Périphérique (device)
                    str(t["o"])[:128],          # Identifiant du point de mesure (object)
                    str(t["v"])[:255]           # Valeur relevée (stockée sous forme de chaîne)
                ))


                # try:
                #     payload = {
                #         # Ajout du préfixe sse_ pour l'injection auto
                #         "tmp_value": str(t["v"])[:255]
                #     }
                #     mqtt_publish.single(
                #         "reports/sse/updates",
                #         json.dumps(payload), # Garantit un JSON parfaitement valide
                #         hostname="127.0.0.1"
                #     )
                # except Exception:
                #     pass

            # Si toutes les données ont été ignorées (invalides), on arrête là
            if not values:
                return json_ok({"status": "ok", "received": len(trends_data), "inserted": 0})

            # Insertion en base de données. L'utilisation de INSERT IGNORE permet
            # d'ignorer silencieusement les doublons (si le boîtier renvoie une donnée déjà reçue)
            cur.executemany(
                "INSERT IGNORE INTO boitier_trends (boitier_id, site, protocol, timestamp, device, obj, value) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                values
            )
            # rowcount donne le nombre de lignes réellement insérées (hors doublons)
            inserted = cur.rowcount

        # Succès : on renvoie au boîtier le bilan des données traitées
        return json_ok({"status": "ok", "received": len(trends_data), "inserted": inserted})
    except Exception as e:
        # En cas d'erreur inattendue (ex: base de données injoignable), on retourne un code 500
        return json_error(500, f"Erreur interne: {str(e)}")
    finally:
        # Assure la libération du pool / fermeture de la connexion DB systématiquement
        db.close()


@api_app.post("/points-config")
def points_config():
    """
    Envoie ou met à jour la configuration des points scannés par le boîtier.

    Headers:
        Authorization: Bearer <token_du_boitier>

    Payload:
        {
            "points": [
                {
                    "s": "ID_site",
                    "p": "bacnet",
                    "d": "1234",
                    "o": "AI:1",
                    "label": "Température Ambiante"
                }
            ]
        }

    Réponse:
        {
            "ok": true,
            "status": "ok",
            "updated": 1
        }
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            data = request.json or {}
            points_data = data.get("points", [])

            if not points_data:
                return json_ok({"status": "ok", "updated": 0})

            boitier_id = boitier["hostname"]

            values = []
            for p in points_data:
                if "p" not in p or "d" not in p or "o" not in p:
                    continue
                values.append((boitier_id, str(p.get("s", ""))[:128], str(p["p"])[:32], str(p["d"])[:128], str(p["o"])[:128], p.get("label")))

            if not values:
                return json_ok({"status": "ok", "updated": 0})

            cur.executemany(
                "INSERT INTO boitier_points_config (boitier_id, site, protocol, device, obj, label) "
                "VALUES (%s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE label = VALUES(label)",
                values
            )
            updated = cur.rowcount

        return json_ok({"status": "ok", "updated": updated})
    except Exception as e:
        return json_error(500, f"Erreur interne: {str(e)}")
    finally:
        db.close()


@api_app.post("/table/column/delete")
def delete_table_column():
    """
    Supprime une définition de colonne personnalisée.
    """
    db = get_db()
    try:
        with db.cursor() as cur:
            boitier = authenticate_boitier(cur)
            if not boitier:
                return json_error(401, "Jeton invalide ou absent.")

            data = request.json or {}
            table_id = data.get("table_id")
            column_key = data.get("column_key")

            if not table_id or not column_key:
                return json_error(400, "Données manquantes")

            cur.execute(
                "DELETE FROM boitier_table_columns WHERE table_id=%s AND column_key=%s",
                (table_id, column_key)
            )
            log_write(cur, boitier["id"], "boitier_table_columns", f"{table_id}:{column_key}", "delete")

        notify_fleet_change(data.get("hostname", "?"))
        return json_ok({"status": "ok"})
    finally:
        db.close()
