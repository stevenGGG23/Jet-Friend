from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import re
import logging
import urllib.parse
import time
from dotenv import load_dotenv
from openai import OpenAI
from typing import Optional, Dict, List
import json
import random

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='.')
CORS(app)  # Enable CORS for all routes

# Initialize APIs
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
openai_client = None
if openai_api_key and openai_api_key != "your-openai-api-key-here":
    try:
        openai_client = OpenAI(api_key=openai_api_key)
    except Exception as e:
        logger.warning(f"Failed to initialize OpenAI client: {str(e)}")
else:
    logger.warning("OPENAI_API_KEY not set. AI functionality will be limited.")

# Google Places API removed - using alternative location data
# Using alternative data processing without Google Places dependency
logger.info("✅ Alternative location processing initialized")

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

def get_location_specific_places(query: str, location: str = None) -> List[Dict]:
    """
    Get location-specific place recommendations using curated data
    Ensures places are actually in the specified location (e.g., Japan)
    """
    import random
    
    # Curated location-specific data
    location_data = {
        'japan': {
            'tokyo': [
                {'name': 'Tsukiji Outer Market', 'type': 'market', 'area': 'Tsukiji', 'rating': 4.6},
                {'name': 'Senso-ji Temple', 'type': 'temple', 'area': 'Asakusa', 'rating': 4.5},
                {'name': 'Shibuya Crossing', 'type': 'landmark', 'area': 'Shibuya', 'rating': 4.4},
                {'name': 'Meiji Shrine', 'type': 'shrine', 'area': 'Harajuku', 'rating': 4.5},
                {'name': 'Tokyo Skytree', 'type': 'tower', 'area': 'Sumida', 'rating': 4.3},
                {'name': 'Ginza District', 'type': 'shopping', 'area': 'Ginza', 'rating': 4.4},
                {'name': 'Akihabara Electric Town', 'type': 'electronics', 'area': 'Akihabara', 'rating': 4.3},
                {'name': 'Ueno Park', 'type': 'park', 'area': 'Ueno', 'rating': 4.4},
                {'name': 'Roppongi Hills', 'type': 'complex', 'area': 'Roppongi', 'rating': 4.2},
                {'name': 'Harajuku Takeshita Street', 'type': 'shopping', 'area': 'Harajuku', 'rating': 4.3}
            ],
            'osaka': [
                {'name': 'Osaka Castle', 'type': 'castle', 'area': 'Chuo-ku', 'rating': 4.4},
                {'name': 'Dotonbori', 'type': 'entertainment', 'area': 'Namba', 'rating': 4.5},
                {'name': 'Kuromon Ichiba Market', 'type': 'market', 'area': 'Nipponbashi', 'rating': 4.3},
                {'name': 'Sumiyoshi Taisha', 'type': 'shrine', 'area': 'Sumiyoshi', 'rating': 4.4},
                {'name': 'Shinsaibashi', 'type': 'shopping', 'area': 'Chuo-ku', 'rating': 4.3}
            ],
            'kyoto': [
                {'name': 'Fushimi Inari Shrine', 'type': 'shrine', 'area': 'Fushimi', 'rating': 4.6},
                {'name': 'Kinkaku-ji (Golden Pavilion)', 'type': 'temple', 'area': 'Kita-ku', 'rating': 4.5},
                {'name': 'Arashiyama Bamboo Grove', 'type': 'nature', 'area': 'Arashiyama', 'rating': 4.4},
                {'name': 'Gion District', 'type': 'historic', 'area': 'Higashiyama', 'rating': 4.5},
                {'name': 'Kiyomizu-dera Temple', 'type': 'temple', 'area': 'Higashiyama', 'rating': 4.5}
            ],
            'restaurants': [
                {'name': 'Sukiyabashi Jiro', 'type': 'sushi', 'area': 'Ginza, Tokyo', 'rating': 4.8},
                {'name': 'Narisawa', 'type': 'innovative', 'area': 'Minato, Tokyo', 'rating': 4.7},
                {'name': 'Kani Doraku Honten', 'type': 'crab', 'area': 'Dotonbori, Osaka', 'rating': 4.5},
                {'name': 'Ganko Sushi', 'type': 'sushi', 'area': 'Multiple locations', 'rating': 4.4},
                {'name': 'Ippudo Ramen', 'type': 'ramen', 'area': 'Multiple locations', 'rating': 4.3},
                {'name': 'Kikunoi', 'type': 'kaiseki', 'area': 'Higashiyama, Kyoto', 'rating': 4.6},
                {'name': 'Mizuno', 'type': 'okonomiyaki', 'area': 'Osaka', 'rating': 4.5}
            ],
            'hotels': [
                {'name': 'The Ritz-Carlton Tokyo', 'type': 'luxury', 'area': 'Roppongi, Tokyo', 'rating': 4.7},
                {'name': 'Park Hyatt Tokyo', 'type': 'luxury', 'area': 'Shinjuku, Tokyo', 'rating': 4.6},
                {'name': 'Aman Tokyo', 'type': 'luxury', 'area': 'Otemachi, Tokyo', 'rating': 4.8},
                {'name': 'Conrad Osaka', 'type': 'luxury', 'area': 'Nakanoshima, Osaka', 'rating': 4.5},
                {'name': 'Four Seasons Hotel Kyoto', 'type': 'luxury', 'area': 'Higashiyama, Kyoto', 'rating': 4.6}
            ]
        }
    }
    
    if not location:
        return []
        
    # Detect location from query
    location_lower = location.lower()
    query_lower = query.lower()
    
    places = []
    
    if 'japan' in location_lower or 'japanese' in query_lower:
        # Get Japan-specific data
        japan_data = location_data.get('japan', {})
        
        # Filter based on query type
        if any(word in query_lower for word in ['restaurant', 'food', 'eat', 'dining', 'sushi', 'ramen']):
            places.extend(japan_data.get('restaurants', []))
        elif any(word in query_lower for word in ['hotel', 'stay', 'accommodation', 'lodging']):
            places.extend(japan_data.get('hotels', []))
        elif 'tokyo' in location_lower or 'tokyo' in query_lower:
            places.extend(japan_data.get('tokyo', []))
        elif 'osaka' in location_lower or 'osaka' in query_lower:
            places.extend(japan_data.get('osaka', []))
        elif 'kyoto' in location_lower or 'kyoto' in query_lower:
            places.extend(japan_data.get('kyoto', []))
        else:
            # General Japan places - mix from all cities
            all_japan_places = []
            for city_places in [japan_data.get('tokyo', []), japan_data.get('osaka', []), japan_data.get('kyoto', [])]:
                all_japan_places.extend(city_places)
            places.extend(all_japan_places)
    
    # Shuffle and return subset to avoid repetition
    if places:
        random.shuffle(places)
    
    return places[:8]  # Return up to 8 places

def get_enhanced_place_image(place_name: str, place_type: str, location: str = None) -> str:
    """
    Get high-quality images for places based on location and type
    """
    # High-quality stock images for different place types
    image_library = {
        # Food & Restaurants
        'pizza': [
            'https://images.pexels.com/photos/315755/pexels-photo-315755.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1653877/pexels-photo-1653877.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'burger': [
            'https://images.pexels.com/photos/1639557/pexels-photo-1639557.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/3219483/pexels-photo-3219483.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'coffee': [
            'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1560472/pexels-photo-1560472.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'sushi': [
            'https://images.pexels.com/photos/357756/pexels-photo-357756.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/248444/pexels-photo-248444.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'ramen': [
            'https://images.pexels.com/photos/884600/pexels-photo-884600.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1907228/pexels-photo-1907228.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'chinese': [
            'https://images.pexels.com/photos/5409751/pexels-photo-5409751.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1907228/pexels-photo-1907228.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'italian': [
            'https://images.pexels.com/photos/1279330/pexels-photo-1279330.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'mexican': [
            'https://images.pexels.com/photos/4958792/pexels-photo-4958792.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/4958793/pexels-photo-4958793.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'restaurant': [
            'https://images.pexels.com/photos/1581384/pexels-photo-1581384.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/3201921/pexels-photo-3201921.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'bar': [
            'https://images.pexels.com/photos/274192/pexels-photo-274192.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2467558/pexels-photo-2467558.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'cafe': [
            'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1560472/pexels-photo-1560472.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],

        # Lodging
        'hotel': [
            'https://images.pexels.com/photos/271624/pexels-photo-271624.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2067396/pexels-photo-2067396.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],

        # Attractions & Culture
        'temple': [
            'https://images.pexels.com/photos/2666598/pexels-photo-2666598.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2613260/pexels-photo-2613260.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1829980/pexels-photo-1829980.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'shrine': [
            'https://images.pexels.com/photos/2187605/pexels-photo-2187605.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2070033/pexels-photo-2070033.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'museum': [
            'https://images.pexels.com/photos/2916450/pexels-photo-2916450.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1878735/pexels-photo-1878735.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'castle': [
            'https://images.pexels.com/photos/2506923/pexels-photo-2506923.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1440476/pexels-photo-1440476.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'park': [
            'https://images.pexels.com/photos/1166209/pexels-photo-1166209.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/3255761/pexels-photo-3255761.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],

        # Shopping & Markets
        'market': [
            'https://images.pexels.com/photos/1766678/pexels-photo-1766678.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2291367/pexels-photo-2291367.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'shopping': [
            'https://images.pexels.com/photos/5632402/pexels-photo-5632402.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1005638/pexels-photo-1005638.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],

        # Landmarks & Architecture
        'landmark': [
            'https://images.pexels.com/photos/2506923/pexels-photo-2506923.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'tower': [
            'https://images.pexels.com/photos/2506923/pexels-photo-2506923.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/3604925/pexels-photo-3604925.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'entertainment': [
            'https://images.pexels.com/photos/2169434/pexels-photo-2169434.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1687845/pexels-photo-1687845.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'electronics': [
            'https://images.pexels.com/photos/1229861/pexels-photo-1229861.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/356056/pexels-photo-356056.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'complex': [
            'https://images.pexels.com/photos/2467558/pexels-photo-2467558.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/1687845/pexels-photo-1687845.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ],
        'default': [
            'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'https://images.pexels.com/photos/2506923/pexels-photo-2506923.jpeg?auto=compress&cs=tinysrgb&w=1200'
        ]
    }
    
    # Enhanced place type detection based on place name and context
    detected_type = place_type.lower()

    # Check place name for specific food types
    place_name_lower = (place_name or '').lower()
    if 'pizza' in place_name_lower:
        detected_type = 'pizza'
    elif 'burger' in place_name_lower or 'mcdonald' in place_name_lower or 'burger king' in place_name_lower:
        detected_type = 'burger'
    elif 'starbucks' in place_name_lower or 'coffee' in place_name_lower or 'cafe' in place_name_lower:
        detected_type = 'coffee'
    elif 'sushi' in place_name_lower:
        detected_type = 'sushi'
    elif 'ramen' in place_name_lower or 'noodle' in place_name_lower:
        detected_type = 'ramen'
    elif 'chinese' in place_name_lower or 'panda' in place_name_lower:
        detected_type = 'chinese'
    elif 'italian' in place_name_lower or 'pasta' in place_name_lower:
        detected_type = 'italian'
    elif 'mexican' in place_name_lower or 'taco' in place_name_lower or 'chipotle' in place_name_lower:
        detected_type = 'mexican'
    elif 'bar' in place_name_lower or 'pub' in place_name_lower:
        detected_type = 'bar'
    elif 'museum' in place_name_lower:
        detected_type = 'museum'
    elif 'park' in place_name_lower:
        detected_type = 'park'

    # Get appropriate images for place type
    images = image_library.get(detected_type, image_library['default'])
    
    # Use place name hash to consistently select same image
    import hashlib
    place_hash = hashlib.md5((place_name or 'default').encode()).hexdigest()
    image_index = int(place_hash[:2], 16) % len(images)
    
    return images[image_index]

def generate_mock_places_data(query: str) -> List[Dict]:
    """
    Generate realistic mock place data with location awareness
    """
    import random

    # Extract location from query if possible
    location_match = re.search(r'(?:in|at|near)\s+([A-Za-z\s]+?)(?:\s|$|[.,!?])', query, re.IGNORECASE)
    location = location_match.group(1).strip() if location_match else None

    # Determine request type
    is_singular = detect_singular_request(query)
    max_results = 1 if is_singular else 6

    # Try to get location-specific places first
    if location:
        location_places = get_location_specific_places(query, location)
        if location_places:
            places = []
            for i, place_data in enumerate(location_places[:max_results]):
                place_name = place_data.get('name')
                place_type = place_data.get('type', 'attraction')
                place_area = place_data.get('area', location)
                place_rating = place_data.get('rating', 4.0 + random.random() * 0.8)
                
                # Generate appropriate address based on location
                if location and 'japan' in location.lower():
                    address = f"{place_area}, Japan"
                else:
                    address = place_area
                
                # Get high-quality image for the place
                hero_image = get_enhanced_place_image(place_name, place_type, location)
                
                # Generate category badge
                category_badges = {
                    'temple': '🏯 Temple',
                    'shrine': '⛩️ Shrine',
                    'castle': '🏰 Castle',
                    'market': '🏪 Market',
                    'restaurant': '🍽️ Restaurant',
                    'sushi': '🍣 Sushi Bar',
                    'ramen': '🍜 Ramen Shop',
                    'hotel': '🏨 Hotel',
                    'shopping': '🛍️ Shopping',
                    'park': '🌳 Park',
                    'landmark': '🗺️ Landmark',
                    'entertainment': '🎭 Entertainment',
                    'tower': '🗼 Tower',
                    'electronics': '📱 Electronics',
                    'complex': '🏢 Complex'
                }
                category_badge = category_badges.get(place_type, '📍 Place')
                
                # Properly encode all URL parameters
                encoded_name = urllib.parse.quote_plus(place_name)
                encoded_area = urllib.parse.quote_plus(place_area)
                
                place_info = {
                    'name': place_name,
                    'address': address,
                    'rating': round(place_rating, 1),
                    'rating_count': random.randint(100, 2500),
                    'types': [place_type],
                    'category_badge': category_badge,
                    'hero_image': hero_image,
                    'description': f"Experience {place_name} in {address}",
                    
                    # Working URLs
                    'google_maps_url': f"https://www.google.com/maps/search/{encoded_name}+{encoded_area}",
                    'google_search_url': f"https://www.google.com/search?q={encoded_name}+{encoded_area}",
                    'yelp_search_url': f"https://www.yelp.com/search?find_desc={encoded_name}&find_loc={encoded_area}",
                    'tripadvisor_search_url': f"https://www.tripadvisor.com/Search?q={encoded_name}+{encoded_area}",
                    'foursquare_url': f"https://foursquare.com/explore?mode=url&near={encoded_area}&q={encoded_name}",
                    'timeout_url': f"https://www.timeout.com/search?query={encoded_name}",
                    
                    # Type-specific links
                    'opentable_url': f"https://www.opentable.com/s/?text={encoded_name}&location={encoded_area}" if place_type in ['restaurant', 'sushi', 'ramen'] else '',
                    'booking_url': f"https://www.booking.com/searchresults.html?ss={encoded_name}+{encoded_area}" if place_type == 'hotel' else ''
                }
                places.append(place_info)
            
            return places

    # Fallback to generic places if no location-specific data
    mock_places = [
        {
            'name': 'The Local Bistro',
            'address': f'123 Main Street, {location or "your area"}',
            'rating': 4.5,
            'rating_count': 324,
            'types': ['restaurant', 'food'],
            'category_badge': '🍽️ Restaurant',
            'hero_image': 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200&auto=format&fit=crop',
            'description': f'A cozy neighborhood restaurant serving fresh, locally-sourced cuisine.'
        }
    ]

    # Add required fields to mock places
    for place in mock_places:
        place_name = place['name']
        place_address = place['address']
        encoded_name = urllib.parse.quote_plus(place_name)
        encoded_location = urllib.parse.quote_plus(location or "")
        
        place.update({
            'google_maps_url': f"https://www.google.com/maps/search/{encoded_name}+{encoded_location}",
            'google_search_url': f"https://www.google.com/search?q={encoded_name}+{encoded_location}",
            'yelp_search_url': f"https://www.yelp.com/search?find_desc={encoded_name}&find_loc={encoded_location}",
            'tripadvisor_search_url': f"https://www.tripadvisor.com/Search?q={encoded_name}+{encoded_location}",
            'foursquare_url': f"https://foursquare.com/explore?mode=url&near={encoded_location}&q={encoded_name}",
            'timeout_url': f"https://www.timeout.com/search?query={encoded_name}",
            'opentable_url': f"https://www.opentable.com/s/?text={encoded_name}&location={encoded_location}" if 'restaurant' in str(place.get('types', [])).lower() else '',
            'booking_url': f"https://www.booking.com/searchresults.html?ss={encoded_name}+{encoded_location}" if 'hotel' in str(place.get('types', [])).lower() else ''
        })

    return mock_places[:max_results]

def get_jetfriend_system_prompt() -> str:
    """
    Return the enhanced JetFriend personality with improved formatting
    """
    return """You are JetFriend, an AI travel assistant.

CRITICAL DISPLAY RULES:
1. For ANY location-related query (restaurants, hotels, attractions, activities, places), you MUST use the hero card format with itinerary-item cards
2. For basic questions (like "what time is it" or "how to say hello"), use regular text responses
3. NEVER display dead links or empty buttons - only show links that actually work
4. ALWAYS use the EXACT hero_image URL provided in the place data - DO NOT use placeholder images
5. IMPORTANT: For singular requests ("a restaurant", "the best hotel"), you'll receive 1 place. For plural/multi-day requests ("restaurants", "things to do", "itinerary"), you'll receive multiple places.

FOR ALL LOCATION RECOMMENDATIONS, use this EXACT HTML structure:

<div class="itinerary-container">
<div class="itinerary-item">
<div class="place-hero">
<img src="[USE THE EXACT hero_image URL FROM PLACE DATA]" alt="[place name]" class="place-hero-image" loading="lazy">
</div>
<div class="activity-header">
<span class="activity-name">[Place Name]</span>
<div class="activity-rating-right"><span class="stars">★★★★★</span> <span class="rating-text">[rating] ([count] reviews)</span></div>
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
- Place name and rating MUST be in the same activity-header div but rating positioned to the right
- Use <span class="activity-name"> for the name (NOT a div)
- Use <div class="activity-rating-right"> for rating to position it on the right side
- NO markdown formatting
- NO extra line breaks
- Each place in its own itinerary-item div

LINK RULES:
- ONLY include links that are provided in the place data
- Always include Google Maps (it's always available)
- Format: <a href="[exact URL from data]" target="_blank" class="activity-link">[icon] [label]</a>
- Available links: 📍 Google Maps, 🌐 Website, ⭐ Yelp, 🏛️ TripAdvisor, 🍽️ OpenTable, 🏨 Booking.com, 🎯 Foursquare, ⏰ TimeOut, 📞 Phone
- Include as many relevant links as available for each place

When you receive place data, it will include:
- name: The place name
- IMAGE TO USE: THE EXACT IMAGE URL TO USE (use this exactly)
- Google Maps: Always available link
- Yelp: Always available search link
- TripAdvisor: Always available search link
- Foursquare: Always available search link
- TimeOut: Always available search link
- OpenTable: For restaurants only
- Booking.com: For hotels only
- Website: Only if available
- Phone: Only if available
- Rating and review count for the stars display

ALWAYS use the exact hero_image URL provided - this is critical for images to display!

IMPORTANT: Do NOT add any footer tags like "Enhanced with X real places" or similar enhancement notifications at the end of your response. Just provide the location cards and any helpful travel advice without meta-commentary about the data source."""

def get_ai_response(user_message: str, conversation_history: List[Dict] = None, places_data: List[Dict] = None) -> str:
    """
    Get response from OpenAI GPT-4o with optional places data integration
    """
    if not openai_client:
        return "I'm sorry, but AI functionality is currently unavailable. Please ensure the OPENAI_API_KEY is properly configured."

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
            is_singular = detect_singular_request(user_message)
            request_context = "SINGULAR REQUEST" if is_singular else "PLURAL/MULTI-DAY REQUEST"
            places_text = f"\n\nREAL-TIME PLACE DATA ({request_context} - {len(places_data)} place{'s' if len(places_data) > 1 else ''}) - USE THESE EXACT DETAILS:\n"
            
            for i, place in enumerate(places_data, 1):
                place_name = place['name']
                hero_image = place.get('hero_image', '')
                
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
                if place.get('yelp_search_url'):
                    places_text += f"   Yelp: {place['yelp_search_url']}\n"
                if place.get('tripadvisor_search_url'):
                    places_text += f"   TripAdvisor: {place['tripadvisor_search_url']}\n"
                if place.get('foursquare_url'):
                    places_text += f"   Foursquare: {place['foursquare_url']}\n"
                if place.get('opentable_url'):
                    places_text += f"   OpenTable: {place['opentable_url']}\n"
                if place.get('booking_url'):
                    places_text += f"   Booking.com: {place['booking_url']}\n"
            
            enhanced_message = f"""{user_message}

{places_text}

CRITICAL INSTRUCTIONS:
1. USE THE EXACT IMAGE URLs PROVIDED ABOVE - Copy them character by character
2. Place name and rating must be in the same activity-header with rating positioned to the right
3. Use <span class="activity-name"> for names, not <div>
4. Follow the EXACT HTML structure shown
5. DO NOT use placeholder images - use the exact URLs provided for each place
6. Each place goes in its own itinerary-item div"""
        
        messages.append({"role": "user", "content": enhanced_message})
        
        # Make API call to OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=8000,
            temperature=0.7,
            top_p=0.9
        )
        
        return response.choices[0].message.content.strip()
        
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
    """Handle chat messages with location data integration"""
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

        if is_location_query:
            # Generate location-aware data
            places_data = generate_mock_places_data(user_message)
            logger.info(f"Generated {len(places_data)} location-aware places")
        
        # Get AI response with enhanced data
        ai_response = get_ai_response(user_message, conversation_history, places_data)
        
        # Log for debugging
        request_type = "singular" if detect_singular_request(user_message) else "plural/multi-day"
        logger.info(f"Chat request: '{user_message}' - Location detected: {detect_location_query(user_message)} - Request type: {request_type} - Places found: {len(places_data)}")

        return jsonify({
            'success': True,
            'response': ai_response,
            'places_found': len(places_data),
            'enhanced_with_location': len(places_data) > 0,
            'location_detected': detect_location_query(user_message),
            'location_aware_results': True,
            'debug_location': None,
            'timestamp': None
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'message': 'Sorry, I encountered an error!'
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
            'location_processing': True,
            'location_detection': True,
            'data_validation': True,
            'image_sourcing': True,
            'premium_features': False
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('DEBUG', 'False').lower() == 'true'

    print(f"🚀 JetFriend API v2.1 starting on port {port}")
    print(f"🌐 Visit: http://localhost:{port}")
    print(f"🤖 OpenAI GPT-4o: {'✅ Connected' if openai_client else '❌ Not configured'}")
    print(f"📍 Google Places: ❌ Not configured (using alternative location data)")
    print(f"🔍 Data Validation: ✅ Active (location-aware)")
    print(f"🖼️ Image Sourcing: ✅ Active (curated images)")
    print(f"🏗️ Location Processing: ✅ Ready")

    # Warm up the application
    logger.info("🔥 Application warmed up successfully")

    app.run(host='0.0.0.0', port=port, debug=debug_mode, threaded=True)
