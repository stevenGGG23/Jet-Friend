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
    <h3 class="place-name">[place_name]</h3>
    <div class="place-rating">★★★★★ [rating] ([review_count] reviews)</div>
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

def search_places_google(query, location=None):
    """
    Search for places using Google Places API and get images
    """
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key or api_key == "your-google-places-key-here":
        return []

    try:
        # Build search query
        search_query = query
        if location:
            search_query += f" in {location}"

        # URL encode the query
        encoded_query = urllib.parse.quote_plus(search_query)
        
        # Google Places Text Search API
        url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={encoded_query}&key={api_key}"
        
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                places = []
                
                for place in data.get('results', [])[:5]:  # Top 5 results
                    place_id = place.get('place_id', '')
                    name = place.get('name', '')
                    address = place.get('formatted_address', '')
                    rating = place.get('rating', 0)
                    rating_count = place.get('user_ratings_total', 0)
                    
                    # Get place photo if available
                    image_url = "https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=600"  # Default fallback
                    
                    if place.get('photos') and len(place['photos']) > 0:
                        photo_reference = place['photos'][0].get('photo_reference')
                        if photo_reference:
                            image_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=600&photoreference={photo_reference}&key={api_key}"
                    
                    # Create Google Maps URL
                    encoded_name = urllib.parse.quote_plus(name)
                    encoded_address = urllib.parse.quote_plus(address)
                    google_maps_url = f"https://www.google.com/maps/search/{encoded_name}+{encoded_address}"
                    
                    # Get place details for website
                    website = ""
                    try:
                        details_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=website&key={api_key}"
                        with urllib.request.urlopen(details_url) as details_response:
                            if details_response.status == 200:
                                details_data = json.loads(details_response.read().decode())
                                website = details_data.get('result', {}).get('website', '')
                    except:
                        pass  # If details request fails, continue without website
                    
                    place_info = {
                        'name': name,
                        'address': address,
                        'rating': rating,
                        'rating_count': rating_count,
                        'image_url': image_url,
                        'google_maps_url': google_maps_url,
                        'website': website,
                        'place_id': place_id
                    }
                    places.append(place_info)
                
                return places
            else:
                print(f"Google Places API error: {response.status}")
                return []
                
    except Exception as e:
        print(f"Error searching places: {str(e)}")
        return []

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
            google_status = bool(os.getenv("GOOGLE_PLACES_API_KEY") and os.getenv("GOOGLE_PLACES_API_KEY") != "your-google-places-key-here")
            
            response = {
                'status': 'healthy',
                'service': 'JetFriend API (2-API Version)',
                'version': '2.0.0',
                'apis_configured': {
                    'openai': openai_status,
                    'google_places': google_status
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
                places_test = search_places_google("restaurant", "New York") if google_key and google_key != "your-google-places-key-here" else []
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                response = {
                    'success': True,
                    'test_response': test_response,
                    'places_found': len(places_test),
                    'openai_status': 'connected',
                    'google_places_status': 'connected' if places_test else 'limited'
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
                    places_data = search_places_google(user_message, location)
                
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
            google_configured = bool(os.getenv("GOOGLE_PLACES_API_KEY") and os.getenv("GOOGLE_PLACES_API_KEY") != "your-google-places-key-here")

            print(f"🤖 OpenAI ChatGPT: {'✅ Connected' if openai_configured else '❌ Not configured'}")
            print(f"📍 Google Places: {'✅ Connected' if google_configured else '❌ Not configured'}")
            print(f"📸 Images: {'✅ Google Photos API' if google_configured else '❌ Limited to fallback'}")

            if not openai_configured:
                print("⚠️  Set OPENAI_API_KEY for AI chat functionality")
            if not google_configured:
                print("⚠️  Set GOOGLE_PLACES_API_KEY for location & image features")

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
