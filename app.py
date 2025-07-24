from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import re
import logging
from dotenv import load_dotenv
from openai import OpenAI
import googlemaps
from typing import Optional, Dict, List

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for all routes

# Initialize APIs
openai_api_key = os.getenv("OPENAI_API_KEY")
google_places_api_key = os.getenv("GOOGLE_PLACES_API_KEY")

# Initialize OpenAI client
openai_client = None
if openai_api_key and openai_api_key != "your-openai-api-key-here":
    try:
        openai_client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        logger.warning(f"Failed to initialize OpenAI client: {str(e)}")
else:
    logger.warning("OPENAI_API_KEY not set. AI functionality will be limited.")

# Initialize Google Maps client
gmaps_client = None
if google_places_api_key and google_places_api_key != "your-google-places-api-key-here":
    try:
        gmaps_client = googlemaps.Client(key=google_places_api_key)
    except Exception as e:
        logger.warning(f"Failed to initialize Google Maps client: {str(e)}")
else:
    logger.warning("GOOGLE_PLACES_API_KEY not set. Location features will be limited.")

def detect_location_query(message: str) -> bool:
    """
    Detect if user query requires real-time location or restaurant data
    """
    location_keywords = [
        'restaurant', 'hotel', 'attraction', 'museum', 'park', 'beach',
        'airport', 'station', 'shopping', 'mall', 'cafe', 'bar', 'club',
        'gym', 'hospital', 'pharmacy', 'bank', 'atm', 'gas station',
        'near me', 'nearby', 'around', 'close to', 'in ', 'at ',
        'best places', 'top rated', 'reviews', 'open now', 'hours',
        'directions', 'how to get', 'distance', 'travel time'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in location_keywords)

def search_places(query: str, location: str = None, radius: int = 5000) -> List[Dict]:
    """
    Search for places using Google Places API
    """
    if not gmaps_client:
        return []
    
    try:
        # If no specific location provided, use a general search
        if location:
            places_result = gmaps_client.places(
                query=f"{query} near {location}",
                radius=radius
            )
        else:
            places_result = gmaps_client.places(query=query)
        
        places = []
        for place in places_result.get('results', [])[:5]:  # Limit to top 5 results
            place_details = {
                'name': place.get('name', ''),
                'address': place.get('formatted_address', ''),
                'rating': place.get('rating', 0),
                'price_level': place.get('price_level', 0),
                'types': place.get('types', []),
                'place_id': place.get('place_id', ''),
                'url': f"https://maps.google.com/maps/place/?q=place_id:{place.get('place_id', '')}"
            }
            places.append(place_details)
        
        return places
    except Exception as e:
        logger.error(f"Error searching places: {str(e)}")
        return []

def get_jetfriend_system_prompt() -> str:
    """
    Return the detailed JetFriend personality and behavior prompt
    """
    return """You are JetFriend, an expert AI travel companion and personal travel assistant. Your mission is to help travelers plan amazing trips with personalized recommendations, insider tips, and detailed itineraries.

PERSONALITY & TONE:
- Enthusiastic travel expert who's been everywhere and knows hidden gems
- Friendly, warm, and encouraging - like a knowledgeable travel buddy
- Professional yet conversational - balance expertise with approachability
- Confident in recommendations while acknowledging personal preferences matter
- Use travel industry insights and current trends

RESPONSE STRUCTURE & FORMATTING:
- Keep responses under 200 words for quick consumption
- Use clear bullet points (•) and numbered lists for organization
- Include clickable links when possible using format: [Location Name](URL)
- Structure day-by-day plans as: "Day 1:", "Day 2:", etc.
- Use line breaks for readability and easy scanning

TRAVEL EXPERTISE FOCUS:
- Provide specific, actionable recommendations with reasoning
- Include budget-conscious options and money-saving tips
- Mention seasonal considerations, weather, and optimal timing
- Suggest authentic local experiences beyond tourist traps
- Consider transportation, accommodation, and dining logistics

MONEY-SAVING TIPS:
- Always include at least one discount tip or budget hack
- Mention free activities, happy hours, local deals
- Suggest optimal booking times and price comparison strategies
- Recommend budget-friendly alternatives to expensive attractions

PREMIUM FEATURES MESSAGING:
- For advanced features not available, mention: "Upgrade to JetFriend Premium for real-time availability, exclusive deals, and personalized booking assistance."
- Suggest premium benefits naturally without being pushy

RESPONSE EXAMPLES:
✓ "Paris in spring is magical! Here's your 3-day starter plan:

Day 1: Montmartre & Sacré-Cœur
• Morning: [Sacré-Cœur Basilica](link) - free entry, amazing views
• Afternoon: Artist squares & street cafes
• Money tip: Skip tourist restaurants, try local bistros for 50% savings

Day 2: Louvre & Seine
• Book timed entry tickets online to skip lines
• Evening Seine cruise - book sunset slots for best photos

Want real-time restaurant availability and exclusive local deals? Upgrade to JetFriend Premium!"

CURRENT CONVERSATION CONTEXT:
Respond to travel questions with specific, helpful advice. If location data is provided, incorporate those real places and details into your recommendations."""

def get_ai_response(user_message: str, conversation_history: List[Dict] = None, places_data: List[Dict] = None) -> str:
    """
    Get response from OpenAI GPT-4o with optional places data integration
    """
    if not openai_client:
        return "I'm sorry, but AI functionality is currently unavailable. Please ensure the OPENAI_API_KEY is properly configured. Upgrade to JetFriend Premium for priority support!"

    try:
        # Create messages array for ChatGPT
        messages = [{"role": "system", "content": get_jetfriend_system_prompt()}]
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Keep last 6 messages for context
                role = "user" if msg.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})
        
        # Enhance user message with places data if available
        enhanced_message = user_message
        if places_data and len(places_data) > 0:
            places_text = "\n\nReal-time location data found:\n"
            for i, place in enumerate(places_data[:3], 1):  # Top 3 places
                places_text += f"{i}. {place['name']} - {place['address']}"
                if place['rating']:
                    places_text += f" (★{place['rating']})"
                if place['url']:
                    places_text += f" [View on Maps]({place['url']})"
                places_text += "\n"
            
            enhanced_message = f"{user_message}\n{places_text}\nPlease incorporate these real places into your response with clickable links."
        
        messages.append({"role": "user", "content": enhanced_message})
        
        # Make API call to OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=400,
            temperature=0.7,
            top_p=0.9
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error getting AI response: {str(e)}")
        return f"I'm experiencing some technical difficulties right now. Please try again in a moment! For priority support and advanced features, upgrade to JetFriend Premium. Error details: {str(e)[:50]}..."

@app.route('/')
def serve_index():
    """Serve the main HTML file"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages with optional location data integration"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Check if query requires location data
        places_data = []
        if detect_location_query(user_message) and gmaps_client:
            # Extract location from message or use general search
            location_match = re.search(r'(?:in|at|near)\s+([A-Za-z\s]+?)(?:\s|$|[.,!?])', user_message, re.IGNORECASE)
            location = location_match.group(1).strip() if location_match else None
            
            # Search for relevant places
            places_data = search_places(user_message, location)
        
        # Get AI response with enhanced data
        ai_response = get_ai_response(user_message, conversation_history, places_data)
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'places_found': len(places_data),
            'enhanced_with_location': len(places_data) > 0,
            'timestamp': request.timestamp if hasattr(request, 'timestamp') else None
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'Sorry, I encountered an error. For priority support, upgrade to JetFriend Premium!'
        }), 500

@app.route('/api/places', methods=['POST'])
def places_search():
    """External places search endpoint"""
    try:
        data = request.json
        query = data.get('query', '').strip()
        location = data.get('location', '').strip()
        radius = data.get('radius', 5000)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        if not gmaps_client:
            return jsonify({
                'success': False,
                'error': 'Google Places API not configured',
                'message': 'Location search unavailable. Upgrade to JetFriend Premium for enhanced location services!'
            }), 503
        
        places_data = search_places(query, location, radius)
        
        return jsonify({
            'success': True,
            'places': places_data,
            'count': len(places_data),
            'query': query,
            'location': location if location else 'Global search'
        })
        
    except Exception as e:
        logger.error(f"Error in places search: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Places search error. For priority support, upgrade to JetFriend Premium!'
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint with API status"""
    return jsonify({
        'status': 'healthy',
        'service': 'JetFriend API',
        'version': '2.0.0',
        'features': {
            'openai_gpt4o': openai_client is not None,
            'google_places': gmaps_client is not None,
            'location_detection': True,
            'premium_features': False
        }
    })

@app.route('/api/test-ai', methods=['GET'])
def test_ai():
    """Test OpenAI connectivity"""
    if not openai_client:
        return jsonify({
            'success': False,
            'error': 'OPENAI_API_KEY not configured',
            'ai_status': 'disconnected',
            'message': 'Please set the OPENAI_API_KEY environment variable. Upgrade to JetFriend Premium for priority API access!'
        }), 503

    try:
        test_response = get_ai_response("Hello! Can you tell me you're working correctly as JetFriend?")
        return jsonify({
            'success': True,
            'test_response': test_response,
            'ai_status': 'connected',
            'model': 'gpt-4o'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'ai_status': 'disconnected'
        }), 500

@app.route('/api/test-places', methods=['GET'])
def test_places():
    """Test Google Places API connectivity"""
    if not gmaps_client:
        return jsonify({
            'success': False,
            'error': 'GOOGLE_PLACES_API_KEY not configured',
            'places_status': 'disconnected',
            'message': 'Please set the GOOGLE_PLACES_API_KEY environment variable. Upgrade to JetFriend Premium for enhanced location services!'
        }), 503

    try:
        # Test with a simple search
        test_places = search_places("coffee shop", "New York")
        return jsonify({
            'success': True,
            'places_status': 'connected',
            'test_results': len(test_places),
            'sample_place': test_places[0] if test_places else None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'places_status': 'disconnected'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'

    print(f"🚀 JetFriend API v2.0 starting on port {port}")
    print(f"🌐 Visit: http://localhost:{port}")
    print(f"🤖 OpenAI GPT-4o: {'✅ Connected' if openai_client else '❌ Not configured'}")
    print(f"📍 Google Places: {'✅ Connected' if gmaps_client else '❌ Not configured'}")

    app.run(host='0.0.0.0', port=port, debug=debug_mode)
