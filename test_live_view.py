import paho.mqtt.client as mqtt
import json
import time
import threading

results = []

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("Connected! Subscribing to reports/sse/updates...")
        client.subscribe("reports/sse/updates")
        
        # Publish start command
        payload = {
            "action": "start",
            "interval": 1,
            "points": [
                {
                    "protocol": "modbus",
                    "device": "127.0.0.1",
                    "obj": "test_ping_modbus",
                    "address": "127.0.0.1",
                    "port": 502,
                    "unit": 1,
                    "function": 3,
                    "reg": 0,
                    "type": "int16"
                }
            ]
        }
        client.publish("dt/cmd/rpi01/live_view", json.dumps(payload))
        print("Published start command!")

def on_message(client, userdata, msg):
    print(f"Received on {msg.topic}: {msg.payload.decode()}")
    results.append(msg.payload.decode())

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

client.connect("127.0.0.1", 1883, 60)

def loop_it():
    client.loop_forever()
    
t = threading.Thread(target=loop_it, daemon=True)
t.start()

time.sleep(3)
client.publish("dt/cmd/rpi01/live_view", json.dumps({"action": "stop"}))
print("Published stop command!")
time.sleep(1)
