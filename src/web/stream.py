"""Flux Server-Sent Events (SSE) : notifie les clients connectes des
evenements globaux (activite API) et des mises a jour propres a un
chantier, en relayant les messages du broker MQTT local. Extrait d'ui.py
lors de la refonte (voir CAHIER-DES-CHARGES-REFONTE.md)."""
from __future__ import annotations

import queue

import paho.mqtt.client as mqtt
from bottle import response

from web.ui import ui_app

@ui_app.get("/reports_sse")
def global_sse():
    """
    Global Server-Sent Events endpoint to notify clients of global events
    like API activity.
    """
    response.content_type = 'text/event-stream'
    response.cache_control = 'no-cache'
    response.headers['Access-Control-Allow-Origin'] = '*'

    q = queue.Queue()

    def on_message(client, userdata, msg):
        try:
            q.put(msg.payload.decode('utf-8'))
        except Exception:
            pass

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    
    try:
        client.connect("127.0.0.1", 1883, 60)
        client.subscribe("reports/sse/updates")
        client.loop_start()
    except Exception as e:
        return f"Erreur MQTT: {str(e)}"

    def generate():
        yield "event: ping\ndata: connected\n\n"
        
        try:
            while True:
                try:
                    msg = q.get(timeout=10)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ":\n\n"
        finally:
            client.loop_stop()
            client.disconnect()

    return generate()

@ui_app.get("/chantier/<chantier_id:int>/reports_sse")
def chantier_sse(chantier_id):
    """
    Server-Sent Events endpoint to notify clients when new data is available.
    Subscribes to the local MQTT broker and proxies messages to the client.
    """
    response.content_type = 'text/event-stream'
    response.cache_control = 'no-cache'
    response.headers['Access-Control-Allow-Origin'] = '*'

    # Queue thread-safe pour communiquer entre le callback MQTT et le flux web
    q = queue.Queue()

    def on_message(client, userdata, msg):
        try:
            # Dès qu'on reçoit un message MQTT, on le place dans la file d'attente
            q.put(msg.payload.decode('utf-8'))
        except Exception:
            pass

    # Connexion du client MQTT spécifique à ce flux SSE
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    
    try:
        client.connect("127.0.0.1", 1883, 60)
        # On s'abonne aux mises à jour générales
        client.subscribe("reports/sse/updates")
        client.loop_start()
    except Exception as e:
        return f"Erreur MQTT: {str(e)}"

    def generate():
        # Ping initial pour confirmer la connexion au frontend
        yield "event: ping\ndata: connected\n\n"
        
        try:
            while True:
                # Récupère le prochain message avec un timeout pour éviter un blocage total
                # Le timeout permet de vérifier régulièrement si le client web a fermé la connexion
                try:
                    msg = q.get(timeout=5)
                    # Si c'est un ping d'activité API, on peut le relayer
                    # msg contient déjà le JSON prêt à l'emploi
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    # Envoi d'un "keep-alive" vide si rien ne se passe
                    yield ":\n\n"
        finally:
            # Nettoyage indispensable lorsque le navigateur coupe la connexion
            client.loop_stop()
            client.disconnect()

    return generate()

