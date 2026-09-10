"""Appel direct d'une application WSGI, sans serveur reseau reel. Permet
de tester le comportement complet (montage, routage, hooks Bottle) tel
qu'uwsgi le voit vraiment, plus fidele qu'un test qui invoquerait les
fonctions de route directement (cf. incident du 10 septembre 2026 :
l'UI n'etait pas montee, jamais detecte faute de test de bout en bout)."""
from __future__ import annotations

import sys
from io import BytesIO


def call_wsgi(app, path, method="GET", body=None, headers=None, query=""):
    body_bytes = body.encode("utf-8") if isinstance(body, str) else (body or b"")
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query,
        "SERVER_NAME": "testserver",
        "SERVER_PORT": "80",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": BytesIO(body_bytes),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "CONTENT_LENGTH": str(len(body_bytes)),
    }
    for k, v in (headers or {}).items():
        if k.lower() == "content-type":
            environ["CONTENT_TYPE"] = v
        else:
            environ["HTTP_" + k.upper().replace("-", "_")] = v

    captured = {}

    def start_response(status, response_headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(response_headers)

    result = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], result.decode("utf-8", errors="replace")
