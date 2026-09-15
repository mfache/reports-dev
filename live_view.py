#!/opt/boitier-bacnet/venv/bin/python
import asyncio
import json
import os
import sys
import threading
import paho.mqtt.client as mqtt

# Ajout du chemin pour importer points.py
sys.path.append("/opt/boitier-bacnet")
from points import make_app, safe_read, fmt
from bacpypes3.pdu import Address

BOITIER_ID = os.environ.get("BOITIER_ID", "rpi01")
MQTT_BROKER = "100.64.0.4" # IP de docs
CMD_TOPIC = f"dt/cmd/{BOITIER_ID}/live_view"
DATA_TOPIC = "reports/sse/updates"

state = {
    "points": [],
    "interval": 1,
    "running": False
}

app = None

async def read_points_loop():
    global app
    app = await make_app()
    print("BACnet app created")
    try:
        while True:
            if not state["running"] or not state["points"]:
                await asyncio.sleep(1)
                continue
            
            # Copie locale pour éviter les modifications pendant la boucle
            pts = list(state["points"])
            interval = state["interval"]
            
            sem = asyncio.Semaphore(16)
            async def read_one(pt):
                # pt = {"protocol": "bacnet", "device": "192.168.1.x", "obj": "analog-value:1"}
                addr = Address(pt["device"])
                obj = pt["obj"]
                async with sem:
                    v = await safe_read(app, addr, obj, "present-value", timeout=2)
                return pt, v
            
            results = await asyncio.gather(*[read_one(p) for p in pts])
            
            payload = {}
            for pt, v in results:
                if v is not None:
                    val = fmt(v)
                    key = f"{BOITIER_ID}|{pt['protocol']}|{pt['device']}|{pt['obj']}"
                    payload[key] = {"v": val, "c": 0}
            
            if payload:
                # Publier sur MQTT
                client.publish(DATA_TOPIC, json.dumps(payload))
                
            await asyncio.sleep(interval)
    finally:
        app.close()

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connecté MQTT (rc={rc})")
    client.subscribe(CMD_TOPIC)
    print(f"Écoute sur {CMD_TOPIC}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        action = payload.get("action")
        
        if action == "start":
            state["points"] = payload.get("points", [])
            state["interval"] = payload.get("interval", 1)
            state["running"] = True
            print(f"Live view START : {len(state['points'])} points")
        elif action == "stop":
            state["running"] = False
            state["points"] = []
            print("Live view STOP")
            
    except Exception as e:
        print(f"Erreur message: {e}")

if __name__ == "__main__":
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Démarrer le client MQTT en arrière-plan
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
    
    try:
        asyncio.run(read_points_loop())
    except KeyboardInterrupt:
        print("Arrêt...")
        client.loop_stop()
