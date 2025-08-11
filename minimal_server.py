#!/usr/bin/env python3
import http.server
import socketserver
import json
import os

class MinimalHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {
                'status': 'healthy',
                'service': 'JetFriend Minimal Server',
                'version': '1.0.0'
            }
            self.wfile.write(json.dumps(response).encode())
            return
        return super().do_GET()

if __name__ == "__main__":
    PORT = 5002
    print(f"���� Starting minimal server on port {PORT}")
    
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True
    
    try:
        with ReusableTCPServer(("", PORT), MinimalHandler) as httpd:
            print(f"✅ Server running at http://localhost:{PORT}")
            print(f"🏥 Health check: http://localhost:{PORT}/api/health")
            httpd.serve_forever()
    except Exception as e:
        print(f"❌ Server error: {e}")
