from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import logging
from dotenv import load_dotenv
import openai
import googlemaps
import urllib.parse
import re
from typing import List, Dict

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for all routes

# Get API keys from environment variables (Render will provide these)
openai_api_key = os.getenv("OPENAI_API_KEY")
google_places_api_key = os.getenv("GOOGLE_PLACES_API_KEY")

# Initialize OpenAI client with error handling
openai_client = None
if openai_api_key:
    try:
        # Fixed OpenAI client initialization
        openai_client = openai.OpenAI(api_key=openai_api_key)
        logger.info("✅ OpenAI client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize OpenAI client: {str(e)}")
        # Fallback: try alternative initialization method
        try:
            openai.api_key = openai_api_key
            openai_client = openai
            logger.info("✅ OpenAI client initialized with fallback method")
        except Exception as fallback_error:
            logger.error(f"Both OpenAI initialization methods failed: {str(fallback_error)}")
            openai_client = None
else:
    logger.warning("OPENAI_API_KEY not set in environment variables")

# Initialize Google Maps client
gmaps_client = None
if google_places_api_key:
    try:
        gmaps_client = googlemaps.Client(key=google_places_api_key)
        logger.info("✅ Google Maps client initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Google Maps client: {str(e)}")
else:
    logger.warning("GOOGLE_PLACES_API_KEY not set in environment variables")

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

def process_google_photos(photos_data, place_name):
    """
    Process Google Places photos and create proper URLs
    """
    processed_photos = []
    
    if not photos_data or not google_places_api_key:
        return processed_photos
    
    try:
        for i, photo in enumerate(photos_data[:3]):  # Limit to 3 photos
            photo_reference = photo.get('photo_reference')
            if photo_reference:
                # Create different sizes for responsive images
                photo_urls = {
                    'thumb': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=150&photoreference={photo_reference}&key={google_places_api_key}",
                    'medium': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={google_places_api_key}",
                    'large': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_reference}&key={google_places_api_key}"
                }
                
                processed_photos.append({
                    'urls': photo_urls,
                    'alt': f"{place_name} photo {i+1}",
                    'source': 'Google Places'
                })
    except Exception as e:
        logger.error(f"Error processing Google photos: {str(e)}")
    
    return processed_photos

def get_fallback_image_by_type(place_types):
    """
    Return high-quality fallback images based on place type
    """
    type_images = {
        'restaurant': 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800&q=80',
        'lodging': 'https://images.unsplash.com/photo-1566073771259-6a8506099945?w=800&q=80',
        'tourist_attraction': 'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=800&q=80',
        'museum': 'https://images.unsplash.com/photo-1581833971358-2c8b550f87b3?w=800&q=80',
        'shopping_mall': 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=800&q=80',
        'park': 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800&q=80',
        'cafe': 'https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=800&q=80',
        'bar': 'https://images.unsplash.com/photo-1566417713940-fe7c737a9ef2?w=800&q=80'
    }
    
    if place_types:
        for place_type in place_types:
            if place_type in type_images:
                return type_images[place_type]
    
    # Default travel image
    return 'https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800&q=80'

def get_place_category(place_types):
    """
    Categorize places for better UI organization
    """
    if not place_types:
        return 'general'
        
    categories = {
        'food': ['restaurant', 'cafe', 'bar', 'bakery', 'meal_takeaway', 'food'],
        'accommodation': ['lodging', 'hotel', 'resort'],
        'attractions': ['tourist_attraction', 'museum', 'amusement_park', 'zoo'],
        'shopping': ['shopping_mall', 'store', 'clothing_store'],
        'entertainment': ['night_club', 'movie_theater', 'casino'],
        'transport': ['airport', 'train_station', 'bus_station'],
        'nature': ['park', 'beach', 'hiking_area']
    }
    
    for category, types in categories.items():
        if any(ptype in place_types for ptype in types):
            return category
    
    return 'general'

def generate_place_tags(detailed_place, place_types):
    """
    Generate relevant tags for better display
    """
    tags = []
    
    # Rating-based tags
    rating = detailed_place.get('rating', 0)
    if rating >= 4.5:
        tags.append('Highly Rated')
    elif rating >= 4.0:
        tags.append('Well Rated')
    
    # Price level tags
    price_level = detailed_place.get('price_level', 0)
    if price_level == 1:
        tags.append('Budget Friendly')
    elif price_level == 4:
        tags.append('Luxury')
    elif price_level >= 2:
        tags.append('Mid-Range')
    
    # Type-based tags
    if place_types:
        if any('restaurant' in ptype for ptype in place_types):
            tags.append('Dining')
        if any('tourist_attraction' in ptype for ptype in place_types):
            tags.append('Must See')
        if any('lodging' in ptype for ptype in place_types):
            tags.append('Accommodation')
    
    # Status tags
    if detailed_place.get('opening_hours', {}).get('open_now'):
        tags.append('Open Now')
    
    return tags[:4]  # Limit to 4 tags

def enhance_place_data(place, detailed_place):
    """
    Add enhanced visual data to existing place structure
    """
    place_name = detailed_place.get('name', place.get('name', ''))
    place_types = detailed_place.get('types', place.get('types', []))
    
    # Process photos
    photos = process_google_photos(
        detailed_place.get('photos', []), 
        place_name
    )
    
    # Get fallback image if no photos
    fallback_image = get_fallback_image_by_type(place_types)
    hero_image = photos[0]['urls']['large'] if photos else fallback_image
    
    # Return enhanced data to ADD to existing place_info dict
    return {
        'photos': photos,
        'hero_image': hero_image,
        'thumbnail': photos[0]['urls']['thumb'] if photos else fallback_image,
        'category': get_place_category(place_types),
        'tags': generate_place_tags(detailed_place, place_types),
        'photo_count': len(photos)
    }

def calculate_estimated_tokens(places_data, conversation_history=None):
    """
    Estimate tokens needed for visual place cards and conversation
    """
    base_tokens = 1000  # For system prompt + instructions
    tokens_per_place = 1500  # Conservative estimate for visual cards with photos
    
    # Add conversation history tokens
    if conversation_history:
        history_tokens = len(conversation_history) * 100  # Rough estimate
        base_tokens += history_tokens
    
    total_estimated = base_tokens + (len(places_data) * tokens_per_place)
    return total_estimated

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
    Enhanced search for places using Google Places API with visual content
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

            # Enhanced place data structure with proper URL encoding
            place_name = detailed_place.get('name', place.get('name', ''))
            place_address = detailed_place.get('formatted_address', place.get('formatted_address', ''))
            location_for_search = location or place_address or 'near me'

            # Properly encode all URL parameters
            encoded_name = urllib.parse.quote_plus(place_name)
            encoded_location = urllib.parse.quote_plus(location_for_search)
            encoded_address = urllib.parse.quote_plus(place_address)

            # Create base place_info with existing structure
            place_info = {
                'name': place_name,
                'address': place_address,
                'rating': detailed_place.get('rating', place.get('rating', 0)),
                'rating_count': detailed_place.get('user_ratings_total', 0),
                'price_level': detailed_place.get('price_level', place.get('price_level', 0)),
                'types': detailed_place.get('types', place.get('types', [])),
                'place_id': place_id,
                'website': detailed_place.get('website', ''),
                'phone': detailed_place.get('formatted_phone_number', ''),
                'opening_hours': detailed_place.get('opening_hours', {}).get('weekday_text', []),
                'is_open': detailed_place.get('opening_hours', {}).get('open_now', None),
                'reviews': detailed_place.get('reviews', [])[:3],  # Top 3 reviews

                # Updated working URLs with proper encoding
                'Maps_url': f"https://www.google.com/maps/search/{encoded_name}+{encoded_location}" if place_name else f"https://maps.google.com/maps/place/?q=place_id:{place_id}",
                'Google Search_url': f"https://www.google.com/search?q={encoded_name}+{encoded_location}",
                'yelp_search_url': f"https://www.yelp.com/search?find_desc={encoded_name}&find_loc={encoded_location}",
                'tripadvisor_search_url': f"https://www.tripadvisor.com/Search?q={encoded_name}+{encoded_location}",
                'foursquare_url': f"https://foursquare.com/explore?mode=url&near={encoded_location}&q={encoded_name}",
                'timeout_url': f"https://www.timeout.com/search?query={encoded_name}",

                # Restaurant-specific links
                'opentable_url': f"https://www.opentable.com/s/?text={encoded_name}&location={encoded_location}" if 'restaurant' in str(detailed_place.get('types', [])).lower() else '',

                # Hotel-specific links
                'booking_url': f"https://www.booking.com/searchresults.html?ss={encoded_name}+{encoded_location}" if 'lodging' in str(detailed_place.get('types', [])).lower() else '',
                'expedia_url': f"https://www.expedia.com/Hotel-Search?destination={encoded_location}" if 'lodging' in str(detailed_place.get('types', [])).lower() else '',

                # Activity/tour links
                'getyourguide_url': f"https://www.getyourguide.com/s/?q={encoded_name}+{encoded_location}",
                'viator_url': f"https://www.viator.com/searchResults/all?text={encoded_name}+{encoded_location}",

                # Transportation links
                'uber_url': f"https://m.uber.com/ul/?pickup=my_location&dropoff[formatted_address]={encoded_address}" if place_address else '',
                'lyft_url': f"https://lyft.com/ride?destination[address]={encoded_address}" if place_address else ''
            }

            # Add enhanced visual data
            enhanced_data = enhance_place_data(place, detailed_place)
            place_info.update(enhanced_data)

            places.append(place_info)

        return places
    except Exception as e:
        logger.error(f"Error searching places: {str(e)}")
        return []

def get_jetfriend_system_prompt() -> str:
    """
    Enhanced system prompt with visual place cards
    """
    return """You are JetFriend, a premium AI travel assistant with access to high-quality visual content.

ENHANCED FORMATTING FOR PLACE RECOMMENDATIONS:

When you have multiple place recommendations (3+), create visual place cards using this format:

<div class="place-card" style="background: linear-gradient(135deg, rgba(0,0,0,0.7), rgba(0,0,0,0.5)), url('{HERO_IMAGE}'); background-size: cover; background-position: center; border-radius: 16px; padding: 24px; margin: 20px 0; color: white; position: relative; min-height: 200px; box-shadow: 0 10px 30px rgba(0,0,0,0.3);">

<div style="position: relative; z-index: 2;">
<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
<h3 style="color: white; font-weight: 700; font-size: 20px; margin: 0;">{PLACE_NAME}</h3>
<span style="background: rgba(255,255,255,0.2); padding: 4px 8px; border-radius: 8px; font-size: 11px; font-weight: 600;">{CATEGORY}</span>
</div>

<div style="margin-bottom: 12px;">
<span style="color: #fbbf24; font-size: 16px;">{STAR_RATING}</span>
<span style="color: #e5e7eb; margin-left: 8px; font-size: 14px;">{RATING} ({REVIEW_COUNT} reviews)</span>
</div>

<p style="color: #f3f4f6; margin-bottom: 16px; line-height: 1.5; font-size: 14px;">{ADDRESS}</p>

<div style="margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 6px;">
{TAGS_AS_BADGES}
</div>

<div style="display: flex; flex-wrap: wrap; gap: 8px;">
{BOOKING_LINKS}
</div>

{PHOTO_GALLERY_IF_AVAILABLE}

</div>
</div>

TAG BADGE FORMAT:
<span style="background: rgba(255,255,255,0.2); color: white; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">{TAG_TEXT}</span>

LINK FORMAT:
<a href="{URL}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 4px; color: #06b6d4; text-decoration: none; font-size: 11px; background: rgba(6, 182, 212, 0.15); padding: 6px 10px; border-radius: 8px; border: 1px solid rgba(6, 182, 212, 0.3);">Google Maps</a>

PHOTO GALLERY FORMAT (when multiple photos available):
<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 12px; border-radius: 8px; overflow: hidden;">
<img src="{PHOTO_URL}" alt="{ALT_TEXT}" style="width: 100%; height: 60px; object-fit: cover;">
</div>

For single place recommendations or simple questions, use plain text with markdown links.

Use real place data when available including photos, ratings, and comprehensive booking links."""

def get_ai_response(user_message: str, conversation_history: List[Dict] = None, places_data: List[Dict] = None) -> str:
    """
    Get response from OpenAI GPT-4o with enhanced places data integration and adaptive token management
    """
    if not openai_client:
        return "I'm currently unable to process requests. Please ensure the OpenAI API is configured properly."

    try:
        # Create messages array for ChatGPT
        messages = [{"role": "system", "content": get_jetfriend_system_prompt()}]
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Keep last 6 messages for context
                role = "user" if msg.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": msg.get("content", "")})
        
        # ADAPTIVE TOKEN MANAGEMENT: Optimize place count based on estimated token usage
        if places_data and len(places_data) > 0:
            estimated_tokens = calculate_estimated_tokens(places_data, conversation_history)
            
            # Adaptive place count based on token limit (leave 1000 tokens buffer)
            if estimated_tokens > 7000:
                max_places = min(len(places_data), 3)  # Limit to 3 high-quality places
                places_data = places_data[:max_places]
                logger.info(f"🎯 Optimized to {max_places} places to ensure complete visual responses (estimated {estimated_tokens} tokens)")
            elif estimated_tokens > 6000:
                max_places = min(len(places_data), 4)  # Allow 4 places
                places_data = places_data[:max_places]
                logger.info(f"🎯 Optimized to {max_places} places for balanced response (estimated {estimated_tokens} tokens)")
            else:
                max_places = min(len(places_data), 5)  # Up to 5 places when tokens allow
                places_data = places_data[:max_places]
                logger.info(f"🎯 Using {max_places} places with available token capacity (estimated {estimated_tokens} tokens)")
        
        # Enhance user message with comprehensive places data including visual content
        enhanced_message = user_message
        if places_data and len(places_data) > 0:
            places_text = "\n\nREAL-TIME PLACE DATA WITH VISUAL CONTENT (OPTIMIZED FOR TOKENS):\n"
            for i, place in enumerate(places_data, 1):  # Use optimized place count
                places_text += f"{i}. **{place['name']}**\n"
                places_text += f"   Address: {place['address']}\n"
                places_text += f"   Category: {place.get('category', 'general')}\n"

                if place.get('rating'):
                    places_text += f"   Rating: ★{place['rating']}"
                    if place.get('rating_count'):
                        places_text += f" ({place['rating_count']:,} reviews)"
                    places_text += "\n"

                # Fixed price level handling
                if place.get('price_level'):
                    try:
                        # Ensure price_level is an integer before multiplication
                        price_level = int(place['price_level'])
                        price_symbols = '$' * price_level
                        places_text += f"   Price: {price_symbols}\n"
                    except (ValueError, TypeError):
                        # This handles cases where price_level might not be a valid number
                        pass

                if place.get('tags'):
                    places_text += f"   Tags: {', '.join(place['tags'])}\n"

                if place.get('hero_image'):
                    places_text += f"   Hero Image: {place['hero_image']}\n"

                if place.get('photos'):
                    places_text += f"   Photos Available: {len(place['photos'])} images\n"

                if place.get('phone'):
                    places_text += f"   Phone: {place['phone']}\n"

                if place.get('is_open') is not None:
                    status = "OPEN NOW" if place['is_open'] else "CLOSED NOW"
                    places_text += f"   Status: {status}\n"

                # Add comprehensive clickable links
                places_text += "   Essential Links:\n"
                places_text += f"   [Google Maps]({place['Maps_url']})\n"
                places_text += f"   [Yelp Reviews]({place['yelp_search_url']})\n"
                places_text += f"   [TripAdvisor]({place['tripadvisor_search_url']})\n"

                if place.get('website'):
                    places_text += f"   [Official Website]({place['website']})\n"

                # Add category-specific booking links
                place_types = str(place.get('types', [])).lower()

                if 'restaurant' in place_types or 'food' in place_types:
                    if place.get('opentable_url'):
                        places_text += f"   [OpenTable Reservations]({place['opentable_url']})\n"

                if 'lodging' in place_types or 'hotel' in place_types:
                    if place.get('booking_url'):
                        places_text += f"   [Booking.com]({place['booking_url']})\n"
                    if place.get('expedia_url'):
                        places_text += f"   [Expedia]({place['expedia_url']})\n"

                # Add activity and transportation links for all places
                places_text += f"   [GetYourGuide Tours]({place['getyourguide_url']})\n"
                places_text += f"   [Foursquare]({place['foursquare_url']})\n"

                if place.get('uber_url'):
                    places_text += f"   [Uber Ride]({place['uber_url']})\n"
                if place.get('lyft_url'):
                    places_text += f"   [Lyft Ride]({place['lyft_url']})\n"

                # Add recent reviews if available
                if place.get('reviews'):
                    places_text += "   Recent Reviews:\n"
                    for review in place['reviews'][:2]:  # Top 2 reviews
                        reviewer = review.get('author_name', 'Anonymous')
                        rating = review.get('rating', 0)
                        text = review.get('text', '')[:100] + "..." if len(review.get('text', '')) > 100 else review.get('text', '')
                        places_text += f"      - {reviewer} (★{rating}): {text}\n"

                places_text += "\n"

            enhanced_message = f"""{user_message}

{places_text}

INSTRUCTIONS: Create visually stunning place recommendations using the enhanced place card format with hero images as backgrounds. You have comprehensive data including:
- High-quality photos and hero images from Google Places
- Professional categorization and smart tags
- Complete booking ecosystem links
- Real-time status and reviews

IMPORTANT: The place count has been optimized for token efficiency. Focus on creating detailed, high-quality visual place cards rather than trying to include more places. Use the enhanced HTML place card format with hero images as card backgrounds. Include photo galleries when multiple images are available. Focus on professional presentation with working functionality.

TOKEN OPTIMIZATION: Create {len(places_data)} detailed visual place cards to ensure complete responses without truncation."""
        
        messages.append({"role": "user", "content": enhanced_message})
        
        # Make API call to OpenAI with increased token limit
        # Handle both old and new OpenAI client methods
        try:
            if hasattr(openai_client, 'chat') and hasattr(openai_client.chat, 'completions'):
                # New OpenAI client (v1.0+)
                response = openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=8000,
                    temperature=0.7,
                    top_p=0.9
                )
                return response.choices[0].message.content.strip()
            else:
                # Fallback to old OpenAI client
                response = openai.ChatCompletion.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=8000,
                    temperature=0.7,
                    top_p=0.9
                )
                return response.choices[0].message['content'].strip()
        except Exception as api_error:
            logger.error(f"OpenAI API call failed: {str(api_error)}")
            return f"I'm experiencing some technical difficulties with the AI service right now. Please try again in a moment!"
        
    except Exception as e:
        logger.error(f"Error getting AI response: {str(e)}")
        return f"I'm experiencing some technical difficulties right now. Please try again in a moment! Error details: {str(e)[:50]}..."

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
    """Handle chat messages with enhanced visual integration"""
    try:
        data = request.json
        user_message = data.get('message', '').strip()
        conversation_history = data.get('history', [])
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Check if query requires location data
        places_data = []
        is_location_query = detect_location_query(user_message)

        if is_location_query and gmaps_client:
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
        elif is_location_query and not gmaps_client:
            # Add note about API limitation but still provide helpful guidance
            user_message += "\n\nNOTE: Google Places API is not configured, so I can't provide real-time visual content right now, but I can still give you excellent travel advice based on my knowledge!"
        
        # Get AI response with places data
        ai_response = get_ai_response(user_message, conversation_history, places_data)
        
        # Return response with metadata
        return jsonify({
            'response': ai_response,
            'places_found': len(places_data),
            'has_visual_content': len(places_data) > 0 and any(p.get('hero_image') for p in places_data)
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({'error': 'An error occurred processing your request'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'openai_configured': openai_client is not None,
        'google_places_configured': gmaps_client is not None
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get configuration status"""
    return jsonify({
        'features': {
            'ai_chat': openai_client is not None,
            'places_search': gmaps_client is not None,
            'visual_cards': gmaps_client is not None and google_places_api_key is not None
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    logger.info(f"🚀 JetFriend Travel Assistant starting on port {port}")
    logger.info(f"📍 OpenAI API: {'✅ Configured' if openai_client else '❌ Not configured - Set OPENAI_API_KEY in Render environment variables'}")
    logger.info(f"🗺️ Google Places API: {'✅ Configured' if gmaps_client else '❌ Not configured - Set GOOGLE_PLACES_API_KEY in Render environment variables'}")
    
    # Run with production settings for Render
    app.run(host='0.0.0.0', port=port, debug=False)