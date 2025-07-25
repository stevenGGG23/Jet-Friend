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
        'directions', 'how to get', 'distance', 'travel time',
        'food', 'eat', 'drink', 'stay', 'sleep', 'visit', 'see', 'do',
        'breakfast', 'lunch', 'dinner', 'brunch', 'coffee', 'dessert',
        'nightlife', 'entertainment', 'activities', 'sights', 'landmarks',
        'hidden gems', 'local favorites', 'underground', 'authentic',
        'reservations', 'book', 'call', 'website', 'menu', 'prices'
    ]
    
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in location_keywords)

def search_underground_places(query: str, location: str = None) -> List[Dict]:
    """
    Search for underground, authentic, and local favorite places
    """
    if not gmaps_client:
        return []

    try:
        underground_queries = [
            f"{query} hidden gem {location or ''}",
            f"{query} local favorite {location or ''}",
            f"{query} authentic {location or ''}",
            f"{query} underground {location or ''}",
            f"best {query} locals {location or ''}",
            f"{query} hole in the wall {location or ''}"
        ]

        all_places = []
        seen_place_ids = set()

        for search_query in underground_queries:
            try:
                places_result = gmaps_client.places(query=search_query.strip())
                for place in places_result.get('results', [])[:3]:  # Top 3 from each query
                    place_id = place.get('place_id', '')
                    if place_id and place_id not in seen_place_ids:
                        seen_place_ids.add(place_id)
                        all_places.append(place)
            except Exception as e:
                logger.warning(f"Underground search failed for '{search_query}': {str(e)}")
                continue

        return all_places[:6]  # Return top 6 unique underground places
    except Exception as e:
        logger.error(f"Error in underground search: {str(e)}")
        return []

def search_places(query: str, location: str = None, radius: int = 5000) -> List[Dict]:
    """
    Enhanced search for places using Google Places API with detailed information
    """
    if not gmaps_client:
        return []

    try:
        # Enhanced search strategy
        if location:
            # Use nearby search for more accurate local results
            geocode_result = gmaps_client.geocode(location)
            if geocode_result:
                lat = geocode_result[0]['geometry']['location']['lat']
                lng = geocode_result[0]['geometry']['location']['lng']
                places_result = gmaps_client.places_nearby(
                    location=(lat, lng),
                    keyword=query,
                    radius=radius,
                    type='establishment'
                )
            else:
                # Fallback to text search
                places_result = gmaps_client.places(
                    query=f"{query} near {location}",
                    radius=radius
                )
        else:
            # General text search
            places_result = gmaps_client.places(query=query)

        places = []
        for place in places_result.get('results', [])[:8]:  # Increased to 8 results
            place_id = place.get('place_id', '')

            # Get detailed place information
            try:
                place_details_result = gmaps_client.place(
                    place_id=place_id,
                    fields=['name', 'formatted_address', 'rating', 'price_level',
                           'types', 'website', 'formatted_phone_number', 'opening_hours',
                           'photos', 'reviews', 'user_ratings_total', 'url']
                )
                detailed_place = place_details_result.get('result', {})
            except:
                detailed_place = place

            # Enhanced place data structure
            place_info = {
                'name': detailed_place.get('name', place.get('name', '')),
                'address': detailed_place.get('formatted_address', place.get('formatted_address', '')),
                'rating': detailed_place.get('rating', place.get('rating', 0)),
                'rating_count': detailed_place.get('user_ratings_total', 0),
                'price_level': detailed_place.get('price_level', place.get('price_level', 0)),
                'types': detailed_place.get('types', place.get('types', [])),
                'place_id': place_id,
                'website': detailed_place.get('website', ''),
                'phone': detailed_place.get('formatted_phone_number', ''),
                'opening_hours': detailed_place.get('opening_hours', {}).get('weekday_text', []),
                'is_open': detailed_place.get('opening_hours', {}).get('open_now', None),
                'photos': detailed_place.get('photos', []),
                'reviews': detailed_place.get('reviews', [])[:3],  # Top 3 reviews
                'google_maps_url': f"https://maps.google.com/maps/place/?q=place_id:{place_id}",
                'google_search_url': f"https://www.google.com/search?q={detailed_place.get('name', '').replace(' ', '+')}",
                'yelp_search_url': f"https://www.yelp.com/search?find_desc={detailed_place.get('name', '').replace(' ', '+')}&find_loc={location or 'near me'}",
                'tripadvisor_search_url': f"https://www.tripadvisor.com/Search?q={detailed_place.get('name', '').replace(' ', '+')}"
            }
            places.append(place_info)

        return places
    except Exception as e:
        logger.error(f"Error searching places: {str(e)}")
        return []

def get_jetfriend_system_prompt() -> str:
    """
    Return the enhanced JetFriend personality focused on convenience and real web data
    """
    return """You are JetFriend, your ultimate travel convenience companion! I'm obsessed with making travel planning EFFORTLESS by providing you with real, clickable links and insider data that saves you hours of research.

CRITICAL FORMATTING RULES - FOLLOW EXACTLY:
- Use ONLY clean, left-aligned Markdown formatting
- NEVER center content or use centered text
- For each location/item: put name, rating, and description on SEPARATE lines
- Put ALL links on their OWN individual lines, directly under the item they relate to
- Use standard Markdown format: [Google Maps](URL) - NO parentheses or curly braces around links
- AVOID inline links inside sentences whenever possible
- NEVER group multiple links on the same line - each link gets its own line
- Keep formatting consistent and easy to scan
- Make sure all links are properly formatted and clickable

CONVENIENCE-FIRST PERSONALITY:
- I'm your research ninja - I dig deep to find hidden gems and underground spots that aren't just first-page Google results
- Every recommendation comes with MULTIPLE clickable links for instant access
- I provide real reviews, ratings, phone numbers, hours, and website links whenever possible
- I connect you directly to Yelp, TripAdvisor, Google Maps, and official websites
- I'm all about actionable intel that gets you from planning to doing FAST

REAL WEB DATA OBSESSION:
- I always include current ratings and review counts when available
- I provide direct links to: Google Maps, Yelp reviews, TripAdvisor, official websites, phone numbers
- I mention specific review highlights and what people actually say
- I include opening hours, price levels, and current availability when possible
- I focus on places with strong online presence and verified reviews

UNDERGROUND & AUTHENTIC FOCUS:
- I prioritize local favorites over tourist traps
- I look for places with passionate followings, not just high ratings
- I mention food trucks, hidden bars, local markets, neighborhood gems
- I include insider tips from actual reviews and local knowledge
- I suggest off-the-beaten-path alternatives alongside popular spots

MANDATORY FORMATTING EXAMPLE - COPY THIS STYLE EXACTLY:

**Di Fara Pizza**
★4.6 (1,847 reviews)
1424 Avenue J - Dom DeMarco still hand-makes every pizza!
[Google Maps](link)
[Yelp Reviews](link)
Call: (718) 258-1367

**L'industrie Pizzeria**
★4.7 (3,241 reviews)
254 S 2nd St - That viral burrata slice everyone's talking about
[Google Maps](link)
[Yelp Reviews](link)
[Website](link)

ACTION-ORIENTED GOALS:
- Get users clicking and booking immediately
- Eliminate the need for additional research
- Provide everything needed to make instant decisions
- Connect users directly to the places and experiences they want

Remember: I'm not just giving recommendations - I'm your personal travel concierge providing instant access to everything you need! ALWAYS follow the formatting rules above for clean, scannable responses with working links."""

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
        
        # Enhance user message with comprehensive places data
        enhanced_message = user_message
        if places_data and len(places_data) > 0:
            places_text = "\n\nREAL-TIME PLACE DATA WITH FULL WEB LINKS:\n"
            for i, place in enumerate(places_data[:5], 1):  # Top 5 places
                places_text += f"{i}. **{place['name']}**\n"
                places_text += f"   Address: {place['address']}\n"

                if place['rating']:
                    places_text += f"   Rating: ★{place['rating']}"
                    if place['rating_count']:
                        places_text += f" ({place['rating_count']:,} reviews)"
                    places_text += "\n"

                if place['price_level']:
                    price_symbols = '$' * place['price_level']
                    places_text += f"   Price: {price_symbols}\n"

                if place['phone']:
                    places_text += f"   Phone: {place['phone']}\n"

                if place['is_open'] is not None:
                    status = "OPEN NOW" if place['is_open'] else "CLOSED NOW"
                    places_text += f"   Status: {status}\n"

                # Add all clickable links
                places_text += "   Links: "
                places_text += f"[Google Maps]({place['google_maps_url']}) | "
                places_text += f"[Yelp Reviews]({place['yelp_search_url']}) | "
                places_text += f"[TripAdvisor]({place['tripadvisor_search_url']})"

                if place['website']:
                    places_text += f" | [Official Website]({place['website']})"

                places_text += "\n"

                # Add recent reviews if available
                if place['reviews']:
                    places_text += "   Recent Reviews:\n"
                    for review in place['reviews'][:2]:  # Top 2 reviews
                        reviewer = review.get('author_name', 'Anonymous')
                        rating = review.get('rating', 0)
                        text = review.get('text', '')[:100] + "..." if len(review.get('text', '')) > 100 else review.get('text', '')
                        places_text += f"     - {reviewer} (★{rating}): {text}\n"

                places_text += "\n"

            enhanced_message = f"{user_message}\n{places_text}\n\nINSTRUCTIONS: Use this real data to provide specific, actionable recommendations with ALL the clickable links. Focus on convenience and immediate utility. Include ratings, phone numbers, and direct access links in your response. Prioritize places with good reviews and current information."
        
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

            # Search for both regular and underground places
            regular_places = search_places(user_message, location)
            underground_places = search_underground_places(user_message, location)

            # Combine and deduplicate by place_id
            all_places = []
            seen_ids = set()

            # Prioritize underground places for authentic experience
            for place in underground_places + regular_places:
                place_id = place.get('place_id', '')
                if place_id and place_id not in seen_ids:
                    seen_ids.add(place_id)
                    all_places.append(place)

            places_data = all_places[:8]  # Return top 8 mixed results
        
        # Get AI response with enhanced data
        ai_response = get_ai_response(user_message, conversation_history, places_data)
        
        # Log for debugging
        logger.info(f"Chat request: '{user_message}' - Location detected: {detect_location_query(user_message)} - Places found: {len(places_data)}")
        if places_data:
            logger.info(f"Sample place data: {places_data[0] if places_data else 'None'}")

        return jsonify({
            'success': True,
            'response': ai_response,
            'places_found': len(places_data),
            'enhanced_with_location': len(places_data) > 0,
            'location_detected': detect_location_query(user_message),
            'gmaps_available': gmaps_client is not None,
            'debug_location': location if 'location' in locals() else None,
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
    """Enhanced test for Google Places API connectivity with detailed debugging"""
    if not gmaps_client:
        return jsonify({
            'success': False,
            'error': 'GOOGLE_PLACES_API_KEY not configured',
            'places_status': 'disconnected',
            'message': 'Please set the GOOGLE_PLACES_API_KEY environment variable. Upgrade to JetFriend Premium for enhanced location services!'
        }), 503

    try:
        # Test multiple search types
        test_query = "pizza restaurant"
        test_location = "San Francisco"

        logger.info(f"Testing Google Places API with query: '{test_query}' in '{test_location}'")

        # Test regular search
        regular_places = search_places(test_query, test_location)

        # Test underground search
        underground_places = search_underground_places(test_query, test_location)

        # Test basic API connectivity
        basic_test = gmaps_client.places(query="Starbucks San Francisco")

        return jsonify({
            'success': True,
            'places_status': 'connected',
            'regular_search_results': len(regular_places),
            'underground_search_results': len(underground_places),
            'basic_api_results': len(basic_test.get('results', [])),
            'sample_regular_place': regular_places[0] if regular_places else None,
            'sample_underground_place': underground_places[0] if underground_places else None,
            'api_response_sample': basic_test.get('results', [])[0] if basic_test.get('results') else None,
            'test_query': test_query,
            'test_location': test_location
        })
    except Exception as e:
        logger.error(f"Places API test failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'places_status': 'disconnected',
            'error_type': type(e).__name__
        }), 500

# Performance optimizations for cold starts
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year cache for static files
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False  # Disable pretty printing for performance

# Add caching headers for static files
@app.after_request
def add_header(response):
    # Add cache headers for better performance
    if request.endpoint and 'static' in request.endpoint:
        response.cache_control.max_age = 31536000  # 1 year
        response.cache_control.public = True

    # Add compression hint
    response.headers['Vary'] = 'Accept-Encoding'

    # Security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'

    return response

# Warm up the application
def warm_up():
    """Warm up the application by initializing connections"""
    try:
        # Test OpenAI connection if available
        if openai_client:
            logger.info("🔥 Warming up OpenAI connection...")

        # Test Google Places if available
        if gmaps_client:
            logger.info("🔥 Warming up Google Places connection...")

        logger.info("🔥 Application warmed up successfully")
    except Exception as e:
        logger.warning(f"⚠️ Warm up partially failed: {str(e)}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'

    print(f"🚀 JetFriend API v2.0 starting on port {port}")
    print(f"🌐 Visit: http://localhost:{port}")
    print(f"🤖 OpenAI GPT-4o: {'✅ Connected' if openai_client else '❌ Not configured'}")
    print(f"📍 Google Places: {'✅ Connected' if gmaps_client else '❌ Not configured'}")

    # Warm up the application
    warm_up()

    app.run(host='0.0.0.0', port=port, debug=debug_mode, threaded=True)
