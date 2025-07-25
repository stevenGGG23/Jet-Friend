#!/usr/bin/env python3
import http.server
import socketserver
import os

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "JetFriend"}')
            return
        return super().do_GET()

if __name__ == "__main__":
    port = 5000
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True
    
    with ReusableTCPServer(("", port), Handler) as httpd:
        print(f"Server running on port {port}")
        httpd.serve_forever()
