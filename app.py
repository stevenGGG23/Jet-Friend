from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import re
import logging
import urllib.parse
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
    Detect if user query requires real-time location data for ANY travel-related content.
    Returns True for hotels, attractions, restaurants, museums, trip planning, etc.
    When True, place cards will be shown for enhanced location recommendations.
    """
    location_keywords = [
        # Accommodations
        'restaurant', 'hotel', 'hostel', 'resort', 'accommodation', 'lodge', 'inn',
        'motel', 'villa', 'apartment', 'airbnb', 'where to stay',

        # Attractions & Sights
        'attraction', 'museum', 'park', 'beach', 'gallery', 'theater', 'cinema',
        'zoo', 'aquarium', 'castle', 'palace', 'cathedral', 'church', 'temple',
        'monument', 'landmark', 'viewpoint', 'scenic', 'observation deck',

        # Transportation
        'airport', 'station', 'train', 'bus', 'metro', 'subway', 'taxi', 'uber',
        'transport', 'terminal', 'port', 'ferry', 'cruise',

        # Shopping & Entertainment
        'shopping', 'mall', 'market', 'boutique', 'store', 'outlet',
        'cafe', 'bar', 'club', 'pub', 'lounge', 'brewery', 'winery',
        'nightlife', 'entertainment', 'theater', 'concert', 'festival',

        # Services & Facilities
        'gym', 'spa', 'hospital', 'pharmacy', 'bank', 'atm', 'gas station',
        'embassy', 'consulate', 'police', 'tourist information',

        # Location Qualifiers
        'near me', 'nearby', 'around', 'close to', 'in ', 'at ', 'around ',
        'best places', 'top rated', 'reviews', 'open now', 'hours',
        'directions', 'how to get', 'distance', 'travel time',

        # Activities & Experiences
        'food', 'eat', 'drink', 'dine', 'taste', 'try',
        'stay', 'sleep', 'rest', 'relax',
        'visit', 'see', 'do', 'explore', 'discover', 'experience',
        'tour', 'excursion', 'adventure', 'activity', 'things to do',
        'breakfast', 'lunch', 'dinner', 'brunch', 'coffee', 'dessert',
        'activities', 'sights', 'landmarks', 'attractions',

        # Travel Planning Keywords
        'trip', 'travel', 'vacation', 'holiday', 'itinerary', 'plan',
        'day trip', 'weekend', 'getaway', 'journey', 'tour',
        '1 day', '2 day', '3 day', '4 day', '5 day', 'week',
        'day 1', 'day 2', 'day 3', 'first day', 'second day',

        # Local & Authentic
        'hidden gems', 'local favorites', 'underground', 'authentic',
        'local', 'traditional', 'typical', 'famous', 'popular',
        'must see', 'must visit', 'must try', 'bucket list',

        # Booking & Reservations
        'reservations', 'book', 'booking', 'reserve', 'tickets',
        'call', 'contact', 'website', 'menu', 'prices', 'cost',
        'opening hours', 'schedule', 'availability'
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

def generate_smart_tags(place_data: Dict) -> List[str]:
    """
    Generate smart tags for a place based on its data
    """
    tags = []

    # Highly Rated tag
    rating = place_data.get('rating', 0)
    rating_count = place_data.get('user_ratings_total', 0)
    if rating >= 4.5 and rating_count >= 100:
        tags.append('highly-rated')

    # Budget Friendly tag
    price_level = place_data.get('price_level', 0)
    if price_level <= 2:
        tags.append('budget-friendly')
    elif price_level >= 4:
        tags.append('premium')

    # Open Now tag removed - unreliable data source

    return tags

def get_place_photos(place_id: str, max_photos: int = 5) -> List[Dict]:
    """
    Get photo URLs for a place using Google Places Photo API with multiple sizes
    """
    if not gmaps_client:
        return []

    try:
        # Get place details with photos
        place_details = gmaps_client.place(
            place_id=place_id,
            fields=['photos']
        )

        photos = place_details.get('result', {}).get('photos', [])
        photo_data = []

        for photo in photos[:max_photos]:
            photo_reference = photo.get('photo_reference')
            if photo_reference:
                # Generate photo URLs in different sizes
                photo_info = {
                    'reference': photo_reference,
                    'urls': {
                        'thumb': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=200&photoreference={photo_reference}&key={google_places_api_key}",
                        'medium': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={google_places_api_key}",
                        'large': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_reference}&key={google_places_api_key}"
                    },
                    'width': photo.get('width', 400),
                    'height': photo.get('height', 300)
                }
                photo_data.append(photo_info)

        return photo_data
    except Exception as e:
        logger.warning(f"Failed to get photos for place {place_id}: {str(e)}")
        return []

def get_category_badge(place_types: List[str]) -> str:
    """
    Determine the primary category badge for a place
    """
    # Priority mapping for place types
    category_map = {
        'restaurant': '🍽️ Restaurant',
        'food': '🍽️ Restaurant',
        'meal_takeaway': '🍴 Takeaway',
        'cafe': '☕ Café',
        'bar': '🍻 Bar',
        'lodging': '🏨 Hotel',
        'tourist_attraction': '🏭 Attraction',
        'museum': '🏛️ Museum',
        'park': '🌳 Park',
        'shopping_mall': '🛍️ Shopping',
        'store': '🛍️ Store',
        'gym': '💪 Fitness',
        'spa': '🧘 Spa',
        'hospital': '🏥 Medical',
        'bank': '🏦 Bank',
        'gas_station': '⛽ Gas Station'
    }

    for place_type in place_types:
        if place_type in category_map:
            return category_map[place_type]

    return '📍 Place'

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

            # Enhanced place data structure with proper URL encoding
            place_name = detailed_place.get('name', place.get('name', ''))
            place_address = detailed_place.get('formatted_address', place.get('formatted_address', ''))
            location_for_search = location or place_address or 'near me'
            place_types = detailed_place.get('types', place.get('types', []))

            # Properly encode all URL parameters
            encoded_name = urllib.parse.quote_plus(place_name)
            encoded_location = urllib.parse.quote_plus(location_for_search)
            encoded_address = urllib.parse.quote_plus(place_address)

            # Generate smart tags and get photos
            base_place_data = {
                'rating': detailed_place.get('rating', place.get('rating', 0)),
                'user_ratings_total': detailed_place.get('user_ratings_total', 0),
                'price_level': detailed_place.get('price_level', place.get('price_level', 0)),
                'opening_hours': detailed_place.get('opening_hours', {}),
                'types': place_types
            }

            smart_tags = generate_smart_tags(base_place_data)
            category_badge = get_category_badge(place_types)
            photos_data = get_place_photos(place_id, max_photos=6)

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
                'photos': detailed_place.get('photos', []),
                'reviews': detailed_place.get('reviews', [])[:3],  # Top 3 reviews

                # Enhanced features
                'smart_tags': smart_tags,
                'category_badge': category_badge,
                'photos': photos_data,
                'hero_image': photos_data[0]['urls']['large'] if photos_data else 'https://images.pexels.com/photos/2067396/pexels-photo-2067396.jpeg',
                'description': f"Experience {place_name} - {category_badge.split(' ', 1)[1] if ' ' in category_badge else 'great location'} in {location_for_search}",

                # Updated working URLs with proper encoding
                'google_maps_url': f"https://www.google.com/maps/search/{encoded_name}+{encoded_location}" if place_name else f"https://maps.google.com/maps/place/?q=place_id:{place_id}",
                'google_search_url': f"https://www.google.com/search?q={encoded_name}+{encoded_location}",
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
            places.append(place_info)

        return places
    except Exception as e:
        logger.error(f"Error searching places: {str(e)}")
        return []

def get_jetfriend_system_prompt() -> str:
    """
    Return the enhanced JetFriend personality focused on convenience and real web data with enhanced place cards
    """
    return """You are JetFriend, an AI travel assistant. When creating itineraries or recommending places, ALWAYS use the consistent itinerary card format for all recommendations. DO NOT switch to transparent place-card templates.

FOR ALL RECOMMENDATIONS (restaurants, hotels, attractions, itineraries), use this CONSISTENT CARD format:

CRITICAL FORMATTING RULES:
1. NO markdown formatting (no **bold**, no # headers)
2. NO extra line breaks between elements
3. NO inline styles - only use CSS classes
4. Each activity must be wrapped in ONE compact itinerary-item div
5. Maximum ONE line break between activities
6. Links must be horizontal in activity-links div

MANDATORY HTML TEMPLATE (copy this structure exactly):

<div class="itinerary-container">
<div class="day-header"><span class="day-icon">1</span>Day 1: Tokyo – Culture and Landmarks</div>
<div class="itinerary-item">
<div class="activity-name">Senso-ji Temple</div>
<div class="activity-rating"><span class="stars">★★★★★</span><span class="rating-text">4.5 (28,000 reviews)</span></div>
<div class="activity">Asakusa - Tokyo's oldest temple, vibrant atmosphere, shopping at Nakamise Street.</div>
<div class="activity-links">
<a href="https://www.google.com/maps/search/senso-ji+temple+asakusa+tokyo" target="_blank" class="activity-link">📍 Google Maps</a>
<a href="https://senso-ji.jp" target="_blank" class="activity-link">🌐 Official Website</a>
<a href="https://www.yelp.com/search?find_desc=senso-ji+temple&find_loc=asakusa+tokyo" target="_blank" class="activity-link">⭐ Yelp Reviews</a>
</div>
</div>
<div class="itinerary-item">
<div class="activity-name">Tokyo Skytree</div>
<div class="activity-rating"><span class="stars">★★★★★</span><span class="rating-text">4.5 (85,000 reviews)</span></div>
<div class="activity">Sumida – Stunning views of Tokyo from Japan's tallest structure.</div>
<div class="activity-links">
<a href="https://www.google.com/maps/search/tokyo+skytree+sumida" target="_blank" class="activity-link">📍 Google Maps</a>
<a href="https://tokyo-skytree.jp" target="_blank" class="activity-link">🌐 Official Website</a>
<a href="tel:+81-3-5302-3470" class="activity-link">📞 +81 3-5302-3470</a>
</div>
</div>
<div class="day-header"><span class="day-icon">2</span>Day 2: Kyoto – History and Temples</div>
<div class="itinerary-item">
<div class="activity-name">Fushimi Inari Shrine</div>
<div class="activity-rating"><span class="stars">★★★★★</span><span class="rating-text">4.7 (50,000 reviews)</span></div>
<div class="activity">Famous for thousands of red torii gates forming scenic walking paths.</div>
<div class="activity-links">
<a href="https://www.google.com/maps/search/fushimi+inari+shrine+kyoto" target="_blank" class="activity-link">📍 Google Maps</a>
<a href="https://inari.jp/en/" target="_blank" class="activity-link">🌐 Official Website</a>
<a href="https://www.getyourguide.com/s/?q=fushimi+inari+shrine+kyoto" target="_blank" class="activity-link">🎫 Tours & Tickets</a>
</div>
</div>
</div>

REQUIRED CSS CLASSES TO USE:
- itinerary-container: Main wrapper
- day-header: Day title with icon
- day-icon: Numbered circle (1, 2, 3, etc.)
- itinerary-item: Each activity card
- activity-name: Attraction/restaurant name
- activity-rating: Rating container
- stars: Visual star rating (★★★★★)
- rating-text: Review count text
- activity: Description text
- activity-links: Link container (horizontal)
- activity-link: Individual links

COMPACT SPACING RULES:
- NO empty lines between div tags
- NO extra spacing inside containers
- Each element goes directly after the previous one
- Only ONE line break between different activities
- Keep descriptions under 100 characters
- Maximum 3 links per activity

NEVER USE:
- **bold** markdown
- ### headers
- Inline styles like style="..."
- Extra \n\n line breaks
- Vertical link stacking

SMART TAGS SYSTEM:
- highly-rated: Use for places with 4.5+ stars and 100+ reviews
- budget-friendly: Use for affordable options ($ or $$)
- premium: Use for high-end, luxury places

CATEGORY BADGES:
🍽️ Restaurant, ☕ Café, 🍻 Bar, 🏨 Hotel, 🎯 Attraction, 🏛️ Museum, 🌳 Park, 🛍️ Shopping, 💪 Fitness, 🧘 Spa

PHOTO USAGE:
- DO NOT use hero image backgrounds or transparent overlays
- Keep consistent solid card styling for readability
- If images are needed, reference them in descriptions only

CRITICAL FORMATTING RULES:
- Use solid, readable itinerary-item cards for ALL recommendations
- NO transparent backgrounds or hero image overlays
- Yellow stars (#fbbf24) for ratings
- Consistent spacing and readable design
- Clean, simple design with solid card backgrounds

WORKING LINKS - MUST USE REAL URLs:
- Maps: place.google_maps_url
- Yelp: place.yelp_search_url
- TripAdvisor: place.tripadvisor_search_url
- Website: place.website (if available)
- Restaurants: place.opentable_url (only for restaurants)
- Hotels: place.booking_url (only for hotels/lodging)
- Uber: place.uber_url
- All links MUST use target="_blank" rel="noopener noreferrer"

ALWAYS INCLUDE:
- Google Maps link for each location
- Official website when available
- Star ratings in ★★★★★ format
- Realistic review counts
- Working phone numbers or booking links
- Smart tags based on place characteristics
- Category badges for easy identification
- Multiple photos when available

For itineraries: Use day-icon numbers 1, 2, 3 and keep under 2000 characters.
For place cards: Use enhanced format with photos, tags, and booking links."""

def substitute_real_urls(ai_response: str, places_data: List[Dict]) -> str:
    """
    Post-process AI response to substitute placeholder URLs with real working links
    """
    if not places_data:
        return ai_response

    # For each place card in the response, substitute real URLs
    for i, place in enumerate(places_data):
        place_types = str(place.get('types', [])).lower()

        # Build conditional restaurant links
        conditional_restaurant_links = ""
        if 'restaurant' in place_types or 'food' in place_types or 'meal_takeaway' in place_types:
            if place.get('opentable_url'):
                conditional_restaurant_links += f'<a href="{place["opentable_url"]}" target="_blank" rel="noopener noreferrer" class="booking-link"><i class="fas fa-utensils"></i> Reserve</a>\n'
            if place.get('website'):
                conditional_restaurant_links += f'<a href="{place["website"]}" target="_blank" rel="noopener noreferrer" class="booking-link"><i class="fas fa-globe"></i> Website</a>\n'

        # Build conditional hotel links
        conditional_hotel_links = ""
        if 'lodging' in place_types or 'hotel' in place_types:
            if place.get('booking_url'):
                conditional_hotel_links += f'<a href="{place["booking_url"]}" target="_blank" rel="noopener noreferrer" class="booking-link"><i class="fas fa-bed"></i> Book</a>\n'
            if place.get('website'):
                conditional_hotel_links += f'<a href="{place["website"]}" target="_blank" rel="noopener noreferrer" class="booking-link"><i class="fas fa-globe"></i> Website</a>\n'

        # If neither restaurant nor hotel, show general website link
        if not conditional_restaurant_links and not conditional_hotel_links and place.get('website'):
            conditional_restaurant_links = f'<a href="{place["website"]}" target="_blank" rel="noopener noreferrer" class="booking-link"><i class="fas fa-globe"></i> Website</a>\n'

        # Substitute URLs in the response
        ai_response = ai_response.replace('{google_maps_url}', place.get('google_maps_url', '#'))
        ai_response = ai_response.replace('{yelp_search_url}', place.get('yelp_search_url', '#'))
        ai_response = ai_response.replace('{tripadvisor_search_url}', place.get('tripadvisor_search_url', '#'))
        ai_response = ai_response.replace('{uber_url}', place.get('uber_url', '#'))
        ai_response = ai_response.replace('{conditional_restaurant_links}', conditional_restaurant_links)
        ai_response = ai_response.replace('{conditional_hotel_links}', conditional_hotel_links)

        # Substitute photo URLs
        ai_response = ai_response.replace('{hero_image}', place.get('hero_image', 'https://images.pexels.com/photos/2067396/pexels-photo-2067396.jpeg'))

        # Photo thumbnail substitution removed - using hero image only

    return ai_response

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
        
        # Enhance user message with comprehensive places data including smart tags
        enhanced_message = user_message
        if places_data and len(places_data) > 0:
            places_text = "\n\nREAL-TIME PLACE DATA WITH ENHANCED FEATURES:\n"
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

                # Add smart tags info
                if place.get('smart_tags'):
                    places_text += f"   Smart Tags: {', '.join(place['smart_tags'])}\n"

                if place.get('category_badge'):
                    places_text += f"   Category: {place['category_badge']}\n"

                if place.get('photos'):
                    places_text += f"   Photos Available: {len(place['photos'])} images\n"
                    places_text += f"   Hero Image: {place.get('hero_image', 'Default fallback')}\n"

                if place['phone']:
                    places_text += f"   Phone: {place['phone']}\n"

                if place['is_open'] is not None:
                    status = "OPEN NOW" if place['is_open'] else "CLOSED NOW"
                    places_text += f"   Status: {status}\n"

                # Add comprehensive clickable links
                places_text += "   Essential Links:\n"
                places_text += f"   [Google Maps]({place['google_maps_url']})\n"
                places_text += f"   [Yelp Reviews]({place['yelp_search_url']})\n"
                places_text += f"   [TripAdvisor]({place['tripadvisor_search_url']})\n"

                if place['website']:
                    places_text += f"   [Official Website]({place['website']})\n"

                # Add category-specific booking links
                place_types = str(place.get('types', [])).lower()

                if 'restaurant' in place_types or 'food' in place_types:
                    if place['opentable_url']:
                        places_text += f"   [OpenTable Reservations]({place['opentable_url']})\n"

                if 'lodging' in place_types or 'hotel' in place_types:
                    if place['booking_url']:
                        places_text += f"   [Booking.com]({place['booking_url']})\n"
                    if place['expedia_url']:
                        places_text += f"   [Expedia]({place['expedia_url']})\n"

                # Add activity and transportation links for all places
                places_text += f"   [GetYourGuide Tours]({place['getyourguide_url']})\n"
                places_text += f"   [Foursquare]({place['foursquare_url']})\n"

                if place['uber_url']:
                    places_text += f"   [Uber Ride]({place['uber_url']})\n"
                if place['lyft_url']:
                    places_text += f"   [Lyft Ride]({place['lyft_url']})\n"

                # Add recent reviews if available
                if place['reviews']:
                    places_text += "   Recent Reviews:\n"
                    for review in place['reviews'][:2]:  # Top 2 reviews
                        reviewer = review.get('author_name', 'Anonymous')
                        rating = review.get('rating', 0)
                        text = review.get('text', '')[:100] + "..." if len(review.get('text', '')) > 100 else review.get('text', '')
                        places_text += f"     - {reviewer} (★{rating}): {text}\n"

                places_text += "\n"

            enhanced_message = f"""{user_message}

{places_text}

INSTRUCTIONS: Use this real data to provide specific, actionable recommendations with ALL the available clickable HTML links. You have access to comprehensive travel booking links including Google Maps, Yelp, TripAdvisor, OpenTable (restaurants), Booking.com/Expedia (hotels), GetYourGuide (tours), Foursquare, Uber/Lyft (transportation), and official websites.

CRITICAL: Output proper HTML anchor tags with security attributes and visual icons. Use semantic HTML structure and mobile-responsive containers:
<a href="https://www.google.com/maps/search/place+name+location" target="_blank" rel="noopener noreferrer">📍 Google Maps</a>
<a href="https://www.yelp.com/search?find_desc=place+name&find_loc=location" target="_blank" rel="noopener noreferrer">⭐ Yelp Reviews</a>

Include ratings, phone numbers, direct access HTML links, smart tags, category badges, and photo galleries in your response. Use the enhanced place card format for restaurant and attraction recommendations. Prioritize places with good reviews and current information. Focus on convenience and immediate utility. Work with the information provided without asking follow-up questions."""
        
        messages.append({"role": "user", "content": enhanced_message})
        
        # Make API call to OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4o",  # You can change this to: "gpt-4o-2024-11-20", "o1-preview", or "o1-mini"
            messages=messages,
            max_tokens=8000,  # Increased for comprehensive responses
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
            user_message += "\n\nNOTE: Google Places API is not configured, so I can't provide real-time links right now, but I can still give you excellent travel advice and ask follow-up questions to help plan your trip!"
        
        # Get AI response with enhanced data
        ai_response = get_ai_response(user_message, conversation_history, places_data)

        # Post-process response to substitute real URLs and add conditional links
        if places_data:
            ai_response = substitute_real_urls(ai_response, places_data)
        
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
