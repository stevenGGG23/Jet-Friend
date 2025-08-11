#!/usr/bin/env python3
import http.server
import socketserver
import json

class TestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/test":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {'status': 'ok', 'message': 'Test server working'}
            self.wfile.write(json.dumps(response).encode())
            return
        else:
            return super().do_GET()

if __name__ == "__main__":
    port = 5002
    try:
        with socketserver.TCPServer(("", port), TestHandler) as httpd:
            print(f"✅ Test server running on port {port}")
            print(f"🌐 Visit: http://localhost:{port}/api/test")
            httpd.serve_forever()
    except Exception as e:
        print(f"❌ Error starting server: {e}")
