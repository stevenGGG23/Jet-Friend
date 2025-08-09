#!/usr/bin/env python3
import http.server
import socketserver
import json
import urllib.parse
import os
import urllib.request
from datetime import datetime

# Load environment variables
def load_env():
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
                    os.environ[key] = value
    except FileNotFoundError:
        pass
    return env_vars

# Load .env file
load_env()

def get_ai_response(user_message, conversation_history=None):
    """
    Send a message to Google Gemini and get a response
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "I'm sorry, but AI functionality is currently unavailable. Please set the GEMINI_API_KEY environment variable to enable AI responses."

    try:
        # Create the prompt with system context
        full_prompt = """You are JetFriend, an intelligent AI travel companion. Follow these guidelines:

PERSONALITY & TONE:
- Be friendly, enthusiastic, and knowledgeable about travel
- Use a conversational, helpful tone
- Be concise but thorough
- Show excitement about travel and destinations

FORMATTING RULES:
- Keep responses under 200 words when possible
- Use simple formatting that works in chat
- For lists, use "•" bullet points or numbered items (1., 2., 3.)
- Use line breaks for better readability
- Avoid complex markdown or special characters

TRAVEL EXPERTISE:
- Focus on practical, actionable travel advice
- Ask clarifying questions about budget, dates, preferences
- Suggest specific destinations, activities, and tips
- Consider seasonality, weather, and local events
- Mention approximate costs when relevant

RESPONSE STRUCTURE:
- Start with enthusiasm/acknowledgment
- Ask 1-2 key questions if needed
- Provide specific recommendations
- End with an engaging follow-up question

EXAMPLES OF GOOD RESPONSES:
"Exciting! Paris in spring is magical!

To help plan your perfect trip:
• What's your budget range?
• How many days will you stay?
• Interested in museums, food, or nightlife?

I can suggest the best neighborhoods to stay in and must-see spots based on your preferences!"

"""

        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                role = "Human" if msg.get("role") == "user" else "Assistant"
                full_prompt += f"{role}: {msg.get('content', '')}\n"

        # Add current user message
        full_prompt += f"Human: {user_message}\nAssistant:"

        # Prepare the request payload for Gemini
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": full_prompt
                        }
                    ]
                }
            ]
        }

        # Make the API request
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        headers = {
            'Content-Type': 'application/json',
            'X-goog-api-key': api_key
        }

        # Create request
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        # Send request
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if 'candidates' in data and len(data['candidates']) > 0:
                    content = data['candidates'][0]['content']['parts'][0]['text']
                    return content.strip()
                else:
                    return "I'm sorry, I didn't receive a proper response. Please try again."
            else:
                return f"I'm sorry, I'm having trouble connecting right now. Please try again in a moment. Error: {response.status}"

    except Exception as e:
        return f"I'm sorry, I'm having trouble connecting right now. Please try again in a moment. Error: {str(e)}"

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
                'service': 'JetFriend API',
                'version': '1.0.0'
            }
            self.wfile.write(json.dumps(response).encode())
            return
        elif self.path == "/api/test":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
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
            
            try:
                test_response = get_ai_response("Hello! Can you tell me you're working correctly?")
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {
                    'success': True,
                    'test_response': test_response,
                    'ai_status': 'connected'
                }
                self.wfile.write(json.dumps(response).encode())
                return
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {
                    'success': False,
                    'error': str(e),
                    'ai_status': 'disconnected'
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
                conversation_history = data.get('history', [])
                
                if not user_message:
                    response = {'error': 'Message is required'}
                    self.wfile.write(json.dumps(response).encode())
                    return
                
                # Get AI response using Gemini API
                ai_response = get_ai_response(user_message, conversation_history)
                
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
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    # Try to start server, if port busy try next port
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            with ReusableTCPServer(("", port), JetFriendHandler) as httpd:
                print(f"🚀 JetFriend API starting on port {port}")
                print(f"🌐 Visit: http://localhost:{port}")
                if os.getenv("GEMINI_API_KEY"):
                    print("✅ Gemini AI integration enabled")
                else:
                    print("⚠️  Gemini AI integration disabled - no API key found")
                httpd.serve_forever()
                break
        except OSError as e:
            if e.errno == 98:  # Address already in use
                print(f"⚠️  Port {port} is busy, trying port {port + 1}")
                port += 1
                if attempt == max_attempts - 1:
                    print(f"❌ Could not find available port after {max_attempts} attempts")
                    exit(1)
            else:
                raise e
