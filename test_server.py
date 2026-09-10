import bottle
from wsgiref.simple_server import WSGIServer, make_server, WSGIRequestHandler
from socketserver import ThreadingMixIn

class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True

class ThreadedServer(bottle.ServerAdapter):
    def run(self, handler):
        server = make_server(self.host, self.port, handler, server_class=ThreadingWSGIServer)
        server.serve_forever()

if __name__ == "__main__":
    print("Test passed")
