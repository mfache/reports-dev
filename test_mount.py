from bottle import Bottle, request, HTTPResponse

root = Bottle()
app = Bottle()

@app.get('/ping')
def ping():
    return "pong"

@app.hook('before_request')
def intercept():
    print(f"Intercept path: {request.path}")
    for r in app.routes:
        print(f"Route rule: {r.rule}")

root.mount('/api', app)

import threading
import time
from wsgiref.simple_server import make_server

server = make_server('127.0.0.1', 8092, root)
t = threading.Thread(target=server.serve_forever)
t.daemon = True
t.start()

time.sleep(0.5)

import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8092/api/ping/usage").read()
except Exception as e:
    print(e)

server.shutdown()
