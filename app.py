from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import re
import logging
import urllib.parse
import time
from dotenv import load_dotenv
from openai import OpenAI
import googlemaps
from typing import Optional, Dict, List
from data_validation import ComprehensiveDataProcessor, DataValidator, ImageSourcer

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
google_images_api_key = os.getenv("GOOGLE_IMAGES_API_KEY")
google_search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

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

# Initialize Comprehensive Data Processor for Builder.io integration
data_processor = None
try:
    data_processor = ComprehensiveDataProcessor(
        gmaps_client=gmaps_client,
        google_images_api_key=google_images_api_key,
        google_search_engine_id=google_search_engine_id
    )
    logger.info("✅ Comprehensive Data Processor initialized for Builder.io integration")
except Exception as e:
    logger.warning(f"Failed to initialize data processor: {str(e)}")
    logger.warning("Data validation and image sourcing will use fallback methods")

def is_basic_question(message: str) -> bool:
    """
    Detect if this is a basic question that doesn't require location cards
    Returns True for general questions, greetings, time, weather, etc.
    """
    basic_keywords = [
        # Greetings and general
        'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
        'how are you', 'what is', 'what are', 'who is', 'when is', 'why',
        'explain', 'tell me about', 'what does', 'how does', 'define',

        # Time and weather
        'what time', 'time zone', 'current time', 'weather', 'temperature',
        'forecast', 'rain', 'sunny', 'cloudy',

        # Currency and general info
        'currency', 'exchange rate', 'language', 'translate', 'how to say',
        'thank you', 'please', 'excuse me', 'culture', 'history',

        # Help and guidance
        'help', 'assistance', 'support', 'how can', 'what can you do',
        'features', 'capabilities'
    ]

    message_lower = message.lower()
    return any(keyword in message_lower for keyword in basic_keywords)

def detect_singular_request(message: str) -> bool:
    """
    Detect if user is asking for a single place vs multiple places.
    Returns True for singular requests like "a restaurant", "the best hotel"
    Returns False for plural requests like "restaurants", "places to eat", "things to do"
    """
    message_lower = message.lower()

    # Strong indicators of singular requests
    singular_patterns = [
        r'\ba\s+(?:good|nice|great|best)?\s*(?:restaurant|hotel|cafe|bar|place|spot)',
        r'\bthe\s+(?:best|top|most popular)\s+(?:restaurant|hotel|cafe|bar|place|spot)',
        r'\bone\s+(?:good|nice|great|restaurant|hotel|cafe|bar|place|spot)',
        r'\bfind\s+(?:me\s+)?(?:a|one)\s+(?:restaurant|hotel|cafe|bar|place|spot)',
        r'\bwhere\s+(?:is|can\s+i\s+find)\s+(?:a|the|one)\s+(?:good|nice|great)?\s*(?:restaurant|hotel|cafe|bar|place|spot)',
        r'\brecommend\s+(?:me\s+)?(?:a|one)\s+(?:good|nice|great)?\s*(?:restaurant|hotel|cafe|bar|place|spot)',
        r'\bneed\s+(?:a|one)\s+(?:good|nice|great)?\s*(?:restaurant|hotel|cafe|bar|place|spot)',
        r'\blooking\s+for\s+(?:a|one)\s+(?:good|nice|great)?\s*(?:restaurant|hotel|cafe|bar|place|spot)'
    ]

    # Strong indicators of plural/multiple requests
    plural_patterns = [
        r'\b(?:restaurants|hotels|cafes|bars|places|spots)\b',
        r'\b(?:some|several|multiple|few)\s+(?:restaurant|hotel|cafe|bar|place|spot)',
        r'\b(?:list|show|give)\s+me\s+(?:some|several|multiple|a\s+few)',
        r'\bwhat\s+(?:are\s+some|are\s+the\s+best)\s+(?:restaurant|hotel|cafe|bar|place|spot)',
        r'\btop\s+\d+\s+(?:restaurant|hotel|cafe|bar|place|spot)',
        r'\bbest\s+(?:restaurant|hotel|cafe|bar|place|spot)s\b',
        r'\b(?:things\s+to\s+do|activities|attractions|sights)\b',
        r'\bmulti[\s-]?day\b',
        r'\bitinerary\b',
        r'\bday\s+\d+\b',
        r'\b\d+\s+day\b',
        r'\bentire\s+day\b',
        r'\bfull\s+day\b',
        r'\bweekend\b',
        r'\btrip\b'
    ]

    # Check for plural patterns first (stronger indicators)
    for pattern in plural_patterns:
        if re.search(pattern, message_lower):
            return False

    # Check for singular patterns
    for pattern in singular_patterns:
        if re.search(pattern, message_lower):
            return True

    # Default to singular for ambiguous cases
    return True

def detect_location_query(message: str) -> bool:
    """
    Detect if user query requires real-time location data for ANY travel-related content.
    Returns True for hotels, attractions, restaurants, museums, trip planning, etc.
    When True, hero place cards will be shown for enhanced location recommendations.
    This ensures all location queries use the hero card format unless it's a basic question.
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
        'opening hours', 'schedule', 'availability',

        # Additional location triggers
        'where', 'location', 'place', 'spot', 'venue', 'destination',
        'address', 'find', 'search', 'recommend', 'suggest', 'show me',
        'best', 'top', 'good', 'great', 'nice', 'cheap', 'expensive',
        'close', 'nearby', 'around here', 'walking distance'
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

def get_place_photos(place_id: str, max_photos: int = 8) -> List[Dict]:
    """
    Get photo URLs for a place using Google Places Photo API with multiple sizes
    Enhanced to ensure we get real, specific photos from the actual place
    """
    if not gmaps_client:
        return []

    try:
        # Get place details with photos
        place_details = gmaps_client.place(
            place_id=place_id,
            fields=['photos', 'name', 'types']
        )

        photos = place_details.get('result', {}).get('photos', [])
        photo_data = []

        for photo in photos[:max_photos]:
            photo_reference = photo.get('photo_reference')
            if photo_reference:
                # Generate photo URLs in different sizes with priority on larger, clearer images
                photo_info = {
                    'reference': photo_reference,
                    'urls': {
                        'thumb': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=200&photoreference={photo_reference}&key={google_places_api_key}",
                        'medium': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=600&photoreference={photo_reference}&key={google_places_api_key}",
                        'large': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=1200&photoreference={photo_reference}&key={google_places_api_key}",
                        'hero': f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=1600&photoreference={photo_reference}&key={google_places_api_key}"
                    },
                    'width': photo.get('width', 400),
                    'height': photo.get('height', 300),
                    'source': 'google_places_api',
                    'attribution': photo.get('html_attributions', ['Google'])[0] if photo.get('html_attributions') else 'Google'
                }
                photo_data.append(photo_info)

        return photo_data
    except Exception as e:
        logger.warning(f"Failed to get photos for place {place_id}: {str(e)}")
        return []

def validate_and_filter_links(place_info: Dict) -> Dict:
    """
    Validate links and remove any that are invalid or lead to dead endpoints
    Only keep links that are confirmed to work
    """
    # Always keep these core links (they're search-based and reliable)
    essential_links = ['google_maps_url', 'google_search_url']

    # Links to conditionally validate/include
    conditional_links = [
        'website', 'yelp_search_url', 'tripadvisor_search_url',
        'opentable_url', 'booking_url', 'uber_url', 'lyft_url'
    ]

    validated_place = place_info.copy()

    # Remove empty or invalid conditional links
    for link_key in conditional_links:
        link_value = validated_place.get(link_key, '')

        # Remove if empty, just placeholder, or clearly invalid
        if not link_value or link_value.strip() == '' or link_value == '#':
            if link_key in validated_place:
                del validated_place[link_key]
        # Additional validation for specific link types
        elif link_key == 'website' and not link_value.startswith(('http://', 'https://')):
            if link_key in validated_place:
                del validated_place[link_key]
        elif link_key in ['opentable_url', 'booking_url', 'uber_url', 'lyft_url']:
            # Only keep these if they have actual data (not just search URLs)
            if not validated_place.get('name') or not validated_place.get('address'):
                if link_key in validated_place:
                    del validated_place[link_key]

    # Ensure phone is properly formatted or remove it
    phone = validated_place.get('phone', '')
    if phone and not phone.startswith(('+', '(')):
        # If phone doesn't look properly formatted, remove it
        if 'phone' in validated_place:
            del validated_place['phone']

    return validated_place

def get_enhanced_fallback_image(place_name: str, place_types: List[str], location: str = None) -> str:
    """
    Get enhanced fallback images based on place type with higher quality sources
    Used only when Google Places Photos API doesn't return images
    """
    place_types_str = str(place_types).lower()

    # High-quality category-specific fallback images from Pexels (royalty-free)
    fallback_images = {
        'restaurant': [
            'https://images.pexels.com/photos/1581384/pexels-photo-1581384.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/3201921/pexels-photo-3201921.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/696218/pexels-photo-696218.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2474658/pexels-photo-2474658.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'pizza': [
            'https://images.pexels.com/photos/315755/pexels-photo-315755.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1653877/pexels-photo-1653877.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/845808/pexels-photo-845808.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1566837/pexels-photo-1566837.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'hotel': [
            'https://images.pexels.com/photos/2067396/pexels-photo-2067396.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/271624/pexels-photo-271624.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1001965/pexels-photo-1001965.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2034335/pexels-photo-2034335.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'bar': [
            'https://images.pexels.com/photos/941864/pexels-photo-941864.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/274192/pexels-photo-274192.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1267320/pexels-photo-1267320.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2795026/pexels-photo-2795026.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'cafe': [
            'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1833399/pexels-photo-1833399.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1307698/pexels-photo-1307698.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'attraction': [
            'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1323550/pexels-photo-1323550.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2506923/pexels-photo-2506923.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'museum': [
            'https://images.pexels.com/photos/1263986/pexels-photo-1263986.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/587816/pexels-photo-587816.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2372978/pexels-photo-2372978.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'park': [
            'https://images.pexels.com/photos/1680172/pexels-photo-1680172.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/305821/pexels-photo-305821.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1463917/pexels-photo-1463917.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'shopping': [
            'https://images.pexels.com/photos/1005058/pexels-photo-1005058.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/298863/pexels-photo-298863.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1488463/pexels-photo-1488463.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ]
    }

    # Determine category and select appropriate image
    if 'pizza' in place_name.lower() or 'pizzeria' in place_name.lower():
        images = fallback_images['pizza']
    elif 'restaurant' in place_types_str or 'food' in place_types_str or 'meal_takeaway' in place_types_str:
        images = fallback_images['restaurant']
    elif 'bar' in place_types_str or 'night_club' in place_types_str:
        images = fallback_images['bar']
    elif 'cafe' in place_types_str:
        images = fallback_images['cafe']
    elif 'lodging' in place_types_str or 'hotel' in place_types_str:
        images = fallback_images['hotel']
    elif 'tourist_attraction' in place_types_str:
        images = fallback_images['attraction']
    elif 'museum' in place_types_str:
        images = fallback_images['museum']
    elif 'park' in place_types_str:
        images = fallback_images['park']
    elif 'shopping' in place_types_str or 'store' in place_types_str:
        images = fallback_images['shopping']
    else:
        images = fallback_images['attraction']  # Default fallback

    # Use hash of place name to consistently select same image for same place
    import hashlib
    place_hash = hashlib.md5((place_name or 'default').encode()).hexdigest()
    image_index = int(place_hash[:2], 16) % len(images)

    return images[image_index]

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
        raw_places = []

        for place in places_result.get('results', [])[:12]:  # Get more results for filtering
            place_id = place.get('place_id', '')

            # Get detailed place information
            try:
                place_details_result = gmaps_client.place(
                    place_id=place_id,
                    fields=['name', 'formatted_address', 'rating', 'price_level',
                           'types', 'website', 'formatted_phone_number', 'opening_hours',
                           'photos', 'reviews', 'user_ratings_total', 'url', 'geometry']
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

            # Generate smart tags and get photos with enhanced image sourcing
            base_place_data = {
                'rating': detailed_place.get('rating', place.get('rating', 0)),
                'user_ratings_total': detailed_place.get('user_ratings_total', 0),
                'price_level': detailed_place.get('price_level', place.get('price_level', 0)),
                'opening_hours': detailed_place.get('opening_hours', {}),
                'types': place_types
            }

            smart_tags = generate_smart_tags(base_place_data)
            category_badge = get_category_badge(place_types)

            # Get real photos from Google Places API first (prioritize actual place photos)
            photos_data = get_place_photos(place_id, max_photos=8)

            # Determine the best hero image - prioritize real photos from the place
            hero_image_url = None
            if photos_data and len(photos_data) > 0:
                # Use the largest/highest quality photo from Google Places
                hero_image_url = photos_data[0]['urls']['hero']  # Use hero size (1600px)
                logger.info(f"Using real photo for {place_name}: {len(photos_data)} photos found")
            else:
                # Fallback to category-specific high-quality stock image
                hero_image_url = get_enhanced_fallback_image(place_name, place_types, location_for_search)
                logger.warning(f"No real photos found for {place_name}, using fallback image")

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
                'geometry': detailed_place.get('geometry', place.get('geometry', {})),

                # Enhanced features with single guaranteed high-quality image
                'smart_tags': smart_tags,
                'category_badge': category_badge,
                'hero_image': hero_image_url,  # Single high-quality image only
                'has_real_photos': len(photos_data) > 0,  # Flag to indicate if real photos are available
                'image_source': 'google_places' if photos_data else 'stock_image',
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

            # Validate and filter links to prevent dead links
            validated_place_info = validate_and_filter_links(place_info)
            raw_places.append(validated_place_info)

        # Apply comprehensive data validation and enhancement
        if data_processor:
            logger.info(f"🔍 Processing {len(raw_places)} places through comprehensive validation...")

            enhanced_places = []
            for place_data in raw_places:
                try:
                    enhanced_place = data_processor.process_place_data(place_data)
                    enhanced_places.append(enhanced_place)
                except Exception as e:
                    logger.warning(f"Failed to process place {place_data.get('name', 'Unknown')}: {str(e)}")
                    # Fall back to original data if processing fails
                    enhanced_places.append(place_data)

            # Filter for high-confidence results only
            high_confidence_places = data_processor.filter_high_confidence_places(
                enhanced_places,
                min_confidence=0.6  # Adjustable threshold
            )

            places = high_confidence_places[:8]  # Return top 8 high-confidence places

            logger.info(f"✅ Filtered to {len(places)} high-confidence places with validated data")
        else:
            # Fallback to original processing if data processor unavailable
            places = raw_places[:8]
            logger.warning("Using fallback processing - data validation unavailable")

        return places
    except Exception as e:
        logger.error(f"Error searching places: {str(e)}")
        return []

def get_jetfriend_system_prompt() -> str:
    """
    Return the enhanced JetFriend personality focused on convenience and real web data with enhanced place cards
    """
    return """You are JetFriend, an AI travel assistant.

CRITICAL DISPLAY RULES:
1. For ANY location-related query (restaurants, hotels, attractions, activities, places), you MUST use the hero card format with itinerary-item cards
2. For basic questions (like "what time is it" or "how to say hello"), use regular text responses
3. NEVER display dead links or empty buttons - only show links that actually work
4. ALWAYS use the EXACT hero_image URL provided in the place data - DO NOT use placeholder images

FOR ALL LOCATION RECOMMENDATIONS, use this EXACT HTML structure:

<div class="itinerary-container">
<div class="itinerary-item">
<div class="place-hero">
<img src="[USE THE EXACT hero_image URL FROM PLACE DATA]" alt="[place name]" class="place-hero-image" loading="lazy">
</div>
<div class="activity-header">
<span class="activity-name">[Place Name]</span>
<div class="activity-rating"><span class="stars">★★★★★</span> <span class="rating-text">[rating] ([count] reviews)</span></div>
</div>
<div class="activity">[Brief description - address and highlights]</div>
<div class="activity-links">
[Only include links that exist in the place data]
</div>
</div>
</div>

CRITICAL IMAGE RULES:
- You will receive a hero_image URL for each place in the format: "IMAGE TO USE: [url]"
- You MUST use this EXACT URL in the img src attribute
- DO NOT use any other image URLs or placeholders
- The image MUST be the first element inside each itinerary-item

CRITICAL FORMAT RULES:
- Place name and rating MUST be on the same line in activity-header
- Use <span class="activity-name"> for the name (NOT a div)
- Rating div stays inline next to the name
- NO markdown formatting
- NO extra line breaks
- Each place in its own itinerary-item div

LINK RULES:
- ONLY include links that are provided in the place data
- Always include Google Maps (it's always available)
- Format: <a href="[exact URL from data]" target="_blank" class="activity-link">[icon] [label]</a>
- Common links: 📍 Google Maps, 🌐 Website, ⭐ Yelp, 📞 Phone

When you receive place data, it will include:
- name: The place name
- IMAGE TO USE: THE EXACT IMAGE URL TO USE (use this exactly)
- Google Maps: Always available link
- Website: Only if available
- Phone: Only if available
- Rating and review count for the stars display

ALWAYS use the exact hero_image URL provided - this is critical for images to display!"""

def substitute_real_urls(ai_response: str, places_data: List[Dict]) -> str:
    """
    Post-process AI response to substitute placeholder URLs with real working links for itinerary format
    """
    if not places_data:
        return ai_response

    # Since we're using consistent itinerary format, the AI should be including real URLs directly
    # This function is mainly for any remaining placeholder substitutions
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
        
        # Enhance user message with comprehensive places data
        enhanced_message = user_message
        if places_data and len(places_data) > 0:
            # Create a VERY clear mapping of images for the AI to use
            image_map = {}
            places_text = "\n\nREAL-TIME PLACE DATA - USE THESE EXACT DETAILS:\n"
            
            for i, place in enumerate(places_data[:5], 1):
                place_name = place['name']
                hero_image = place.get('hero_image', '')
                
                # Store in image map for easy reference
                image_map[place_name] = hero_image
                
                places_text += f"\n{i}. {place_name}\n"
                places_text += f"   IMAGE TO USE: {hero_image}\n"
                places_text += f"   Address: {place['address']}\n"
                
                if place['rating']:
                    places_text += f"   Rating: {place['rating']} stars"
                    if place['rating_count']:
                        places_text += f" ({place['rating_count']:,} reviews)"
                    places_text += "\n"
                
                # Add working links
                places_text += f"   Google Maps: {place['google_maps_url']}\n"
                if place.get('website'):
                    places_text += f"   Website: {place['website']}\n"
                if place.get('phone'):
                    places_text += f"   Phone: {place['phone']}\n"
                if place.get('yelp_search_url'):
                    places_text += f"   Yelp: {place['yelp_search_url']}\n"
            
            # Create explicit HTML examples for the AI
            example_html = "\n\nEXACT HTML TO USE FOR EACH PLACE:\n"
            for place in places_data[:2]:  # Show 2 examples
                example_html += f"""
For {place['name']}:
<div class="itinerary-item">
<div class="place-hero">
<img src="{place.get('hero_image', '')}" alt="{place['name']}" class="place-hero-image" loading="lazy">
</div>
<div class="activity-header">
<span class="activity-name">{place['name']}</span>
<div class="activity-rating"><span class="stars">{'★' * int(place.get('rating', 4))}</span> <span class="rating-text">{place.get('rating', 4.5)} ({place.get('rating_count', 100):,} reviews)</span></div>
</div>
<div class="activity">{place['address']}</div>
<div class="activity-links">
<a href="{place['google_maps_url']}" target="_blank" class="activity-link">📍 Google Maps</a>
{f'<a href="{place["website"]}" target="_blank" class="activity-link">🌐 Website</a>' if place.get('website') else ''}
{f'<a href="tel:{place["phone"]}" class="activity-link">📞 {place["phone"]}</a>' if place.get('phone') else ''}
</div>
</div>
"""
            
            enhanced_message = f"""{user_message}

{places_text}

{example_html}

CRITICAL INSTRUCTIONS:
1. USE THE EXACT IMAGE URLs PROVIDED ABOVE - Copy them character by character
2. Place name and rating must be on the SAME LINE using the activity-header structure shown
3. Use <span class="activity-name"> for names, not <div>
4. Follow the EXACT HTML structure shown in the examples above
5. DO NOT use placeholder images - use the exact URLs provided for each place
6. Each place goes in its own itinerary-item div"""
        
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
        
        # Check if query requires location data vs basic response
        places_data = []
        is_basic = is_basic_question(user_message)
        is_location_query = detect_location_query(user_message) and not is_basic

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
        'version': '2.1.0',
        'features': {
            'openai_gpt4o': openai_client is not None,
            'google_places': gmaps_client is not None,
            'location_detection': True,
            'data_validation': data_processor is not None,
            'image_sourcing': data_processor is not None and data_processor.image_sourcer is not None,
            'comprehensive_validation': data_processor is not None,
            'premium_features': False
        },
        'builder_io_integration': {
            'data_accuracy': data_processor is not None,
            'link_validation': data_processor is not None,
            'coordinate_verification': gmaps_client is not None,
            'image_sourcing': data_processor is not None,
            'licensing_compliance': True
        }
    })

@app.route('/api/validation-status', methods=['GET'])
def validation_status():
    """Get comprehensive validation system status"""
    if not data_processor:
        return jsonify({
            'success': False,
            'error': 'Data validation system not available',
            'status': 'disabled'
        }), 503

    # Test validation capabilities
    test_results = {
        'url_validation': False,
        'coordinate_validation': False,
        'contact_validation': False,
        'image_sourcing': False,
        'google_images_api': False,
        'licensing_compliance': True
    }

    try:
        # Test URL validation
        test_url_result = data_processor.validator.validate_url('https://www.google.com')
        test_results['url_validation'] = test_url_result.get('valid', False)

        # Test coordinate validation (if Google Maps available)
        if gmaps_client:
            test_coord_result = data_processor.validator.validate_coordinates_match_address(
                'Times Square, New York, NY', 40.7580, -73.9855
            )
            test_results['coordinate_validation'] = test_coord_result.get('valid', False)

        # Test contact validation
        test_contact_result = data_processor.validator.validate_contact_info(
            phone='+1234567890',
            website='https://www.example.com'
        )
        test_results['contact_validation'] = test_contact_result.get('confidence_score', 0) > 0

        # Test image sourcing
        test_image_result = data_processor.image_sourcer.get_primary_image(
            'Test Restaurant', ['restaurant'], 'New York'
        )
        test_results['image_sourcing'] = test_image_result.get('url') is not None

        # Check Google Images API
        test_results['google_images_api'] = (
            data_processor.image_sourcer.google_images_api_key is not None and
            data_processor.image_sourcer.google_search_engine_id is not None
        )

    except Exception as e:
        logger.error(f"Validation status test failed: {str(e)}")

    return jsonify({
        'success': True,
        'status': 'active',
        'capabilities': test_results,
        'version': '1.0.0',
        'last_tested': time.time()
    })

@app.route('/api/image-sourcing-test', methods=['POST'])
def image_sourcing_test():
    """Test image sourcing capabilities"""
    if not data_processor:
        return jsonify({
            'success': False,
            'error': 'Image sourcing system not available'
        }), 503

    try:
        data = request.json
        place_name = data.get('place_name', 'Test Place')
        place_types = data.get('place_types', ['restaurant'])
        location = data.get('location', 'New York')

        # Test image sourcing
        image_result = data_processor.image_sourcer.get_primary_image(
            place_name, place_types, location
        )

        return jsonify({
            'success': True,
            'image_result': {
                'url': image_result.get('url'),
                'source': image_result.get('source'),
                'license': image_result.get('license'),
                'confidence': image_result.get('confidence'),
                'attribution': image_result.get('attribution', '')
            },
            'test_parameters': {
                'place_name': place_name,
                'place_types': place_types,
                'location': location
            }
        })

    except Exception as e:
        logger.error(f"Image sourcing test failed: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Image sourcing test error: {str(e)}'
        }), 500

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
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'

    print(f"🚀 JetFriend API v2.1 starting on port {port}")
    print(f"🌐 Visit: http://localhost:{port}")
    print(f"🤖 OpenAI GPT-4o: {'✅ Connected' if openai_client else '❌ Not configured'}")
    print(f"📍 Google Places: {'✅ Connected' if gmaps_client else '❌ Not configured'}")
    print(f"🔍 Data Validation: {'✅ Active' if data_processor else '❌ Not configured'}")
    print(f"🖼️ Image Sourcing: {'✅ Active' if data_processor and data_processor.image_sourcer else '❌ Not configured'}")
    print(f"🏗️ Builder.io Integration: {'✅ Ready' if data_processor else '❌ Limited'}")

    # Warm up the application
    warm_up()

    app.run(host='0.0.0.0', port=port, debug=debug_mode, threaded=True)
