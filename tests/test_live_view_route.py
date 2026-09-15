"""Non-regression du bouton Live View (vue chantier) : verifie le round-trip
complet POST /chantier/<id>/live-view -> publication MQTT sur
dt/cmd/<boitier_id>/live_view, avec un jeu de donnees reel (chantier HORNU4,
id 16, boitier rpi01, point BACnet 1088/analog-value:20). Necessite un broker
MQTT local actif (Mosquitto), comme le reste de l'architecture SSE/MQTT de
l'application (voir docs/SSE-MQTT-ARCHITECTURE.md).
"""
from __future__ import annotations

import json
import threading
import time

import paho.mqtt.client as mqtt

from _helpers import call_wsgi


def test_live_view_start_publie_sur_mqtt(wsgi_app, base_path):
    received = []
    ready = threading.Event()

    def on_connect(client, userdata, flags, rc, properties=None):
        client.subscribe("dt/cmd/rpi01/live_view")
        ready.set()

    def on_message(client, userdata, msg):
        received.append(msg.payload.decode())

    sub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    sub.on_connect = on_connect
    sub.on_message = on_message
    sub.connect("127.0.0.1", 1883, 60)
    sub.loop_start()
    ready.wait(timeout=5)

    payload = {
        "boitier_id": "rpi01",
        "active": True,
        "points": [
            {"protocol": "bacnet", "device": "1088", "obj": "analog-value:20"},
        ],
    }
    status, _, body = call_wsgi(
        wsgi_app,
        f"{base_path}/chantier/16/live-view",
        method="POST",
        body=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    time.sleep(1)
    sub.loop_stop()
    sub.disconnect()

    assert status == "200 OK", body
    data = json.loads(body)
    assert data.get("status") == "ok", data
    assert len(received) == 1, f"Aucun message MQTT recu : {received}"
    msg = json.loads(received[0])
    assert msg["action"] == "start"
    assert msg["points"][0]["device"] == "1088"
