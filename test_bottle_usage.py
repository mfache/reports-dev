from bottle import Bottle, request, HTTPResponse
import json

app = Bottle()

@app.hook('before_request')
def intercept():
    print("Intercepting:", request.path)
    if request.path.endswith('/usage'):
        base_path = request.path[:-6]
        print("Looking for route:", base_path)
        doc = None
        for r in app.routes:
            print("Found route rule:", r.rule)
            if r.rule == base_path or r.rule == base_path + "/":
                doc = "DOCSTRING!"
                break
        
        if doc:
            print("Found doc")
        else:
            print("Doc not found")

@app.get('/ping')
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
try:
    urllib.request.urlopen("http://127.0.0.1:8092/usage")
except Exception as e:
    print(e)
try:
    urllib.request.urlopen("http://127.0.0.1:8092/ping/usage")
except Exception as e:
    print(e)

server.shutdown()
