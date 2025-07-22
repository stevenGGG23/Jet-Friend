#!/usr/bin/env python3
import http.server
import socketserver
import json
import urllib.parse
import os
from datetime import datetime

class JetFriendHandler(http.server.SimpleHTTPRequestHandler):
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
                'service': 'JetFriend API (Simple Server)',
                'version': '1.0.0'
            }
            self.wfile.write(json.dumps(response).encode())
            return
        elif self.path == "/api/test":
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = {
                'success': False,
                'error': 'GEMINI_API_KEY not configured',
                'ai_status': 'disconnected',
                'message': 'Please set the GEMINI_API_KEY environment variable to enable AI functionality.'
            }
            self.wfile.write(json.dumps(response).encode())
            return
        
        return super().do_GET()
    
    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            try:
                data = json.loads(post_data.decode())
                user_message = data.get('message', '').strip()
                
                if not user_message:
                    response = {'error': 'Message is required'}
                    self.wfile.write(json.dumps(response).encode())
                    return
                
                # Mock AI response since Flask/requests aren't available
                ai_response = f"Hello! I'm JetFriend, your AI travel companion! 🛫\n\nI'd love to help you with your travel plans. However, I'm currently running in a simplified mode without full AI capabilities.\n\nYou asked: \"{user_message}\"\n\nTo enable full AI functionality, please:\n• Set up the GEMINI_API_KEY environment variable\n• Install the required Flask dependencies\n\nIn the meantime, I can still help with basic travel advice and information!"
                
                response = {
                    'success': True,
                    'response': ai_response,
                    'timestamp': datetime.now().isoformat()
                }
                
            except Exception as e:
                response = {
                    'success': False,
                    'error': 'Internal server error',
                    'message': 'Sorry, I encountered an error processing your request.'
                }
            
            self.wfile.write(json.dumps(response).encode())
            return
        
        self.send_response(405)
        self.end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    
    with socketserver.TCPServer(("", port), JetFriendHandler) as httpd:
        print(f"🚀 JetFriend Simple Server starting on port {port}")
        print(f"🌐 Visit: http://localhost:{port}")
        print("💡 Note: Running in simplified mode. Install Flask dependencies for full functionality.")
        httpd.serve_forever()
