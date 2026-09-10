#!/opt/venv/reports/bin/python3
import time
import json
import random
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Connecté au broker MQTT local")
    else:
        print(f"Échec de connexion, code de retour: {reason_code}")

# Création du client (Paho v2.x nécessite l'API callback_api_version)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "reports_publisher_service")
client.on_connect = on_connect

# Connexion au broker local (sans mot de passe)
client.connect("127.0.0.1", 1883, 60)

# Démarrage de la boucle réseau en tâche de fond
client.loop_start()

try:
    print("Démarrage de l'émission MQTT...")
    while True:
        # Générer des données fictives pour tester (à remplacer par vos données réelles)
        data = {
            "heartbeat": True
        }

        # On publie sur le topic "reports/sse/updates"
        client.publish("reports/sse/updates", json.dumps(data))
        # print(f"Publié: {data}")

        # Attente de 5 secondes avant le prochain envoi
        time.sleep(5)
except KeyboardInterrupt:
    print("Arrêt demandé par l'utilisateur")
finally:
    client.loop_stop()
    client.disconnect()
