#!/opt/venv/reports/bin/python3
import time
import json
import random
import os
import sys

# Ajoute dynamiquement le dossier src au chemin d'import, quel que soit le dossier d'exécution
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.append(os.path.join(project_root, 'src'))

# Force l'utilisation du fichier d'environnement de dev si non spécifié
if "DB_ENV_FILE" not in os.environ:
    os.environ["DB_ENV_FILE"] = "/etc/boitier-fleet/db-dev.env"

from core.database import get_db
import paho.mqtt.client as mqtt

def main():
    print("Démarrage du simulateur de valeurs temps réel...")
    
    # 1. Connexion au broker MQTT local
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "reports_simulator")
    try:
        client.connect("127.0.0.1", 1883, 60)
        client.loop_start()
        print("Connecté au broker MQTT. Prêt à simuler l'activité !")
    except Exception as e:
        print(f"Erreur de connexion MQTT: {e}")
        sys.exit(1)

    try:
        while True:
            db = get_db()
            with db.cursor() as cursor:
                # 2. Prendre 5 points au hasard dans la base
                cursor.execute("""
                    SELECT t.boitier_id, t.protocol, t.device, t.obj, t.value 
                    FROM boitier_trends t
                    ORDER BY RAND() LIMIT 5
                """)
                points = cursor.fetchall()
                
                if points:
                    update_data = {}
                    for p in points:
                        # 3. Génération d'une variation réaliste (+/- 5%)
                        try:
                            val = float(p['value'])
                            variation = val * random.uniform(-0.05, 0.05)
                            nouvelle_valeur = round(val + variation, 2)
                        except (ValueError, TypeError):
                            nouvelle_valeur = p['value'] # Garde la valeur texte si ce n'est pas un nombre
                        
                        # Format attendu par le JS (ex: rpi01|modbus|EASTRON|FC04_72)
                        point_key = f"{p['boitier_id']}|{p['protocol']}|{p['device']}|{p['obj']}"
                        
                        update_data[point_key] = {
                            'v': nouvelle_valeur,
                            'c': random.randint(10, 500) # Simule le nombre de relevés
                        }
                        print(f"[{time.strftime('%H:%M:%S')}] Simulé : {point_key} -> {nouvelle_valeur}")
                    
                    # 4. Publication MQTT -> Le script web/stream.py le relaie au navigateur via SSE
                    client.publish("reports/sse/updates", json.dumps(update_data))
                    
                    # Publication du heartbeat pour faire clignoter le point d'activité API (en haut à droite)
                    client.publish("reports/sse/updates", json.dumps({"action": "ping"}))
                    
            db.close()
            time.sleep(3) # Rafraichit l'UI toutes les 3 secondes
            
    except KeyboardInterrupt:
        print("\nArrêt du simulateur demandé par l'utilisateur.")
    except Exception as e:
        print(f"Erreur inattendue: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
