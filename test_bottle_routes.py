from bottle import Bottle, request, HTTPResponse

app = Bottle()

@app.get('/ping')
def ping():
    """This is the ping docstring."""
    return "pong"

@app.hook('before_request')
def intercept():
    if request.path.endswith('/usage'):
        base_path = request.path[:-len('/usage')]
        doc = "Not found"
        for r in app.routes:
            if r.rule == base_path:
                doc = r.callback.__doc__
                break
        res = HTTPResponse(status=200, body=doc)
        res.content_type = 'text/plain'
        raise res

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
    print(urllib.request.urlopen("http://127.0.0.1:8092/ping/usage").read().decode('utf-8'))
except Exception as e:
    print(e)

server.shutdown()
