#!/usr/bin/env python3
import http.server
import socketserver
import json
import urllib.parse
import os
import urllib.request
from datetime import datetime
import re

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

def get_ai_response_openai(user_message, conversation_history=None, places_data=None):
    """
    Send a message to OpenAI ChatGPT and get a response with place cards
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-openai-key-here":
        return "I'm sorry, but AI functionality is currently unavailable. Please set your OPENAI_API_KEY environment variable to enable AI responses."

    try:
        # Create system prompt
        system_prompt = """You are JetFriend, an intelligent AI travel companion. 

PERSONALITY & TONE:
- Be friendly, enthusiastic, and knowledgeable about travel
- Use a conversational, helpful tone
- Be concise but thorough
- Show excitement about travel and destinations

FORMATTING RULES:
- Keep responses under 300 words when possible
- Use simple formatting that works in chat
- For lists, use "•" bullet points or numbered items
- Use line breaks for better readability

TRAVEL EXPERTISE:
- Focus on practical, actionable travel advice
- Ask clarifying questions about budget, dates, preferences
- Suggest specific destinations, activities, and tips
- Consider seasonality, weather, and local events
- Mention approximate costs when relevant

When recommending places, always use this format:
<div class="place-card">
  <div class="place-image">
    <img src="[image_url]" alt="[place_name]" loading="lazy">
  </div>
  <div class="place-info">
    <div class="place-header-compact">
      <h3 class="place-name">[place_name]</h3>
      <div class="place-rating">★★★★★ [rating] ([review_count] reviews)</div>
    </div>
    <p class="place-description">[description]</p>
    <div class="place-links">
      <a href="[google_maps_url]" target="_blank">📍 Google Maps</a>
      <a href="[website]" target="_blank">🌐 Website</a>
    </div>
  </div>
</div>"""

        # Build messages array
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Keep last 6 messages
                role = "user" if msg.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})

        # Enhanced user message with places data
        enhanced_message = user_message
        if places_data and len(places_data) > 0:
            enhanced_message += "\n\nREAL PLACE DATA FOR YOUR RESPONSE:\n"
            for i, place in enumerate(places_data[:3], 1):  # Top 3 places
                enhanced_message += f"{i}. {place['name']}\n"
                enhanced_message += f"   Address: {place['address']}\n"
                enhanced_message += f"   Rating: {place['rating']} ({place['rating_count']} reviews)\n"
                enhanced_message += f"   Image: {place['image_url']}\n"
                enhanced_message += f"   Google Maps: {place['google_maps_url']}\n"
                if place['website']:
                    enhanced_message += f"   Website: {place['website']}\n"
                enhanced_message += "\n"
            
            enhanced_message += "INSTRUCTIONS: Use this real data to create place cards in your response using the exact format specified in your system prompt."

        messages.append({"role": "user", "content": enhanced_message})

        # Prepare OpenAI API request
        payload = {
            "model": "gpt-3.5-turbo",  # Using gpt-3.5-turbo for better cost efficiency
            "messages": messages,
            "max_tokens": 2000,
            "temperature": 0.7
        }

        # Make API request to OpenAI
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }

        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    return content.strip()
                else:
                    return "I'm sorry, I didn't receive a proper response. Please try again."
            else:
                return f"I'm sorry, I'm having trouble connecting right now. Please try again in a moment. Error: {response.status}"

    except Exception as e:
        return f"I'm sorry, I'm having trouble connecting right now. Please try again in a moment. Error: {str(e)}"

# Predefined image mapping for food/restaurant keywords
KEYWORD_IMAGES = {
    'pizza': 'https://images.pexels.com/photos/315755/pexels-photo-315755.jpeg?auto=compress&cs=tinysrgb&w=600',
    'cafe': 'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?auto=compress&cs=tinysrgb&w=600',
    'coffee': 'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?auto=compress&cs=tinysrgb&w=600',
    'temple': 'https://images.pexels.com/photos/161409/angkor-wat-temple-siem-reap-cambodia-161409.jpeg?auto=compress&cs=tinysrgb&w=600',
    'food truck': 'https://images.pexels.com/photos/4253312/pexels-photo-4253312.jpeg?auto=compress&cs=tinysrgb&w=600',
    'gyro': 'https://images.pexels.com/photos/7625056/pexels-photo-7625056.jpeg?auto=compress&cs=tinysrgb&w=600',
    'steakhouse': 'https://images.pexels.com/photos/361184/asparagus-steak-veal-steak-veal-361184.jpeg?auto=compress&cs=tinysrgb&w=600',
    'sushi': 'https://images.pexels.com/photos/357756/pexels-photo-357756.jpeg?auto=compress&cs=tinysrgb&w=600',
    'bistro': 'https://images.pexels.com/photos/67468/pexels-photo-67468.jpeg?auto=compress&cs=tinysrgb&w=600',
    'ice cream': 'https://images.pexels.com/photos/1362534/pexels-photo-1362534.jpeg?auto=compress&cs=tinysrgb&w=600',
    'bakery': 'https://images.pexels.com/photos/2067396/pexels-photo-2067396.jpeg?auto=compress&cs=tinysrgb&w=600',
    'brewery': 'https://images.pexels.com/photos/1552630/pexels-photo-1552630.jpeg?auto=compress&cs=tinysrgb&w=600',
    'winery': 'https://images.pexels.com/photos/34085/pexels-photo.jpg?auto=compress&cs=tinysrgb&w=600',
    'tapas': 'https://images.pexels.com/photos/1566837/pexels-photo-1566837.jpeg?auto=compress&cs=tinysrgb&w=600',
    'bbq': 'https://images.pexels.com/photos/1251208/pexels-photo-1251208.jpeg?auto=compress&cs=tinysrgb&w=600',
    'noodle shop': 'https://images.pexels.com/photos/884600/pexels-photo-884600.jpeg?auto=compress&cs=tinysrgb&w=600',
    'deli': 'https://images.pexels.com/photos/1639557/pexels-photo-1639557.jpeg?auto=compress&cs=tinysrgb&w=600',
    'dim sum': 'https://images.pexels.com/photos/1092730/pexels-photo-1092730.jpeg?auto=compress&cs=tinysrgb&w=600',
    'tacos': 'https://images.pexels.com/photos/461198/pexels-photo-461198.jpeg?auto=compress&cs=tinysrgb&w=600',
    'bagels': 'https://images.pexels.com/photos/209206/pexels-photo-209206.jpeg?auto=compress&cs=tinysrgb&w=600',
    'tea house': 'https://images.pexels.com/photos/230477/pexels-photo-230477.jpeg?auto=compress&cs=tinysrgb&w=600',
    'street market': 'https://images.pexels.com/photos/2819095/pexels-photo-2819095.jpeg?auto=compress&cs=tinysrgb&w=600',
    'pub': 'https://images.pexels.com/photos/5490778/pexels-photo-5490778.jpeg?auto=compress&cs=tinysrgb&w=600',
    'ramen': 'https://images.pexels.com/photos/884600/pexels-photo-884600.jpeg?auto=compress&cs=tinysrgb&w=600',
    'gelato': 'https://images.pexels.com/photos/1362534/pexels-photo-1362534.jpeg?auto=compress&cs=tinysrgb&w=600',
    'falafel': 'https://images.pexels.com/photos/6275093/pexels-photo-6275093.jpeg?auto=compress&cs=tinysrgb&w=600',
    'donut shop': 'https://images.pexels.com/photos/205961/pexels-photo-205961.jpeg?auto=compress&cs=tinysrgb&w=600',
    'smoothie bar': 'https://images.pexels.com/photos/1092730/pexels-photo-1092730.jpeg?auto=compress&cs=tinysrgb&w=600',
    'vegan restaurant': 'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=600',
    'seafood shack': 'https://images.pexels.com/photos/725992/pexels-photo-725992.jpeg?auto=compress&cs=tinysrgb&w=600',
    'dessert café': 'https://images.pexels.com/photos/291528/pexels-photo-291528.jpeg?auto=compress&cs=tinysrgb&w=600',
    'restaurant': 'https://images.pexels.com/photos/67468/pexels-photo-67468.jpeg?auto=compress&cs=tinysrgb&w=600',
    'bar': 'https://images.pexels.com/photos/5490778/pexels-photo-5490778.jpeg?auto=compress&cs=tinysrgb&w=600',
    'fast food': 'https://images.pexels.com/photos/1633578/pexels-photo-1633578.jpeg?auto=compress&cs=tinysrgb&w=600'
}

def search_places_keyword(query, location=None):
    """
    Search for places using predefined keyword images
    """
    query_lower = query.lower()
    places = []

    # Look for keyword matches in the query
    for keyword, image_url in KEYWORD_IMAGES.items():
        if keyword in query_lower:
            # Create a mock place entry
            place_name = f"{keyword.title()} Place"
            if location:
                place_name += f" in {location}"

            place_info = {
                'name': place_name,
                'address': location if location else 'Location not specified',
                'rating': 4.5,  # Default good rating
                'rating_count': 250,  # Default review count
                'image_url': image_url,
                'google_maps_url': f"https://www.google.com/maps/search/{urllib.parse.quote_plus(keyword)}+{urllib.parse.quote_plus(location or '')}",
                'website': '',
                'place_id': f"keyword_{keyword.replace(' ', '_')}"
            }
            places.append(place_info)

            # Only return the first match to avoid duplicates
            break

    # If no keyword match found, return a generic restaurant image
    if not places:
        place_info = {
            'name': f"Restaurant" + (f" in {location}" if location else ""),
            'address': location if location else 'Location not specified',
            'rating': 4.0,
            'rating_count': 150,
            'image_url': KEYWORD_IMAGES['restaurant'],
            'google_maps_url': f"https://www.google.com/maps/search/{urllib.parse.quote_plus(query)}+{urllib.parse.quote_plus(location or '')}",
            'website': '',
            'place_id': 'keyword_generic'
        }
        places.append(place_info)

    return places

def detect_location_query(message):
    """
    Detect if user query requires location data
    """
    location_keywords = [
        'restaurant', 'hotel', 'attraction', 'museum', 'park', 'bar', 'cafe',
        'where', 'visit', 'see', 'eat', 'stay', 'near', 'in ', 'at ',
        'best places', 'things to do', 'activities', 'food', 'drink'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in location_keywords)

class JetFriendHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.path = "/index.html"
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Check API status
            openai_status = bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your-openai-key-here")

            response = {
                'status': 'healthy',
                'service': 'JetFriend API (Keyword Images Version)',
                'version': '2.1.0',
                'apis_configured': {
                    'openai': openai_status,
                    'keyword_images': True,
                    'available_keywords': len(KEYWORD_IMAGES)
                }
            }
            self.wfile.write(json.dumps(response).encode())
            return
        elif self.path == "/api/test":
            # Test both APIs
            openai_key = os.getenv("OPENAI_API_KEY")
            google_key = os.getenv("GOOGLE_PLACES_API_KEY")
            
            if not openai_key or openai_key == "your-openai-key-here":
                self.send_response(503)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {
                    'success': False,
                    'error': 'OPENAI_API_KEY not configured',
                    'message': 'Please set your OPENAI_API_KEY environment variable.'
                }
                self.wfile.write(json.dumps(response).encode())
                return
            
            try:
                test_response = get_ai_response_openai("Hello! Can you tell me you're working correctly as JetFriend?")
                places_test = search_places_keyword("restaurant", "New York")
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {
                    'success': True,
                    'test_response': test_response,
                    'places_found': len(places_test),
                    'openai_status': 'connected',
                    'keyword_images_status': 'active'
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
                    'openai_status': 'disconnected'
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
                
                # Check if query needs location data
                places_data = []
                if detect_location_query(user_message):
                    # Extract location from message
                    location_match = re.search(r'(?:in|at|near)\s+([A-Za-z\s]+?)(?:\s|$|[.,!?])', user_message, re.IGNORECASE)
                    location = location_match.group(1).strip() if location_match else None
                    
                    # Search for places
                    places_data = search_places_keyword(user_message, location)
                
                # Get AI response with places data
                ai_response = get_ai_response_openai(user_message, conversation_history, places_data)
                
                response = {
                    'success': True,
                    'response': ai_response,
                    'places_found': len(places_data),
                    'timestamp': datetime.now().isoformat()
                }
                
            except Exception as e:
                response = {
                    'success': False,
                    'error': 'Internal server error',
                    'message': f'Sorry, I encountered an error: {str(e)}'
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
    port = int(os.environ.get('PORT', 5001))

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    # Try to start server, if port busy try next port
    max_attempts = 10
    started = False

    for attempt in range(max_attempts):
        try:
            httpd = ReusableTCPServer(("", port), JetFriendHandler)
            print(f"🚀 JetFriend API (2-API Version) starting on port {port}")
            print(f"🌐 Visit: http://localhost:{port}")
            print(f"📊 Server status: RUNNING on 0.0.0.0:{port}")

            # Check API configuration
            openai_configured = bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your-openai-key-here")

            print(f"🤖 OpenAI ChatGPT: {'✅ Connected' if openai_configured else '❌ Not configured'}")
            print(f"📍 Keyword Images: ✅ Active with {len(KEYWORD_IMAGES)} predefined categories")
            print(f"📸 Images: ✅ Predefined keyword-based images")

            if not openai_configured:
                print("⚠️  Set OPENAI_API_KEY for AI chat functionality")

            print(f"🔄 Ready to accept requests on port {port}")
            started = True
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
                print(f"❌ Server error: {e}")
                raise e
        except KeyboardInterrupt:
            print("\n🛑 Server stopped by user")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            break

    if not started:
        print("❌ Failed to start server")
        exit(1)
