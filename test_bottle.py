from bottle import Bottle, request, response, HTTPResponse
import json

app = Bottle()

@app.hook('before_request')
def intercept_version():
    if request.query.get("version"):
        res = HTTPResponse(status=200, body=json.dumps({"ok": True, "version": "1.0"}))
        res.content_type = "application/json"
        raise res

@app.get("/ping")
def ping():
    return "pong"

import threading
import time
from wsgiref.simple_server import make_server

server = make_server('127.0.0.1', 8092, app)
t = threading.Thread(target=server.serve_forever)
t.daemon = True
t.start()

time.sleep(0.5)

import urllib.request
print(urllib.request.urlopen("http://127.0.0.1:8092/ping").read().decode('utf-8'))
print(urllib.request.urlopen("http://127.0.0.1:8092/ping?version=1").read().decode('utf-8'))

server.shutdown()
