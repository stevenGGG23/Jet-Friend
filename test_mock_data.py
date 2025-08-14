#!/usr/bin/env python3

import sys
import os
import json
import re
import random

# Mock the dependencies for testing
class MockLogger:
    def info(self, msg): 
        print(f"INFO: {msg}")

logger = MockLogger()

def detect_singular_request(message: str) -> bool:
    """
    Detect if user is asking for a single place vs multiple places.
    """
    message_lower = message.lower()
    
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
    
    # Default to singular for ambiguous cases
    return True

def generate_mock_places_data(query: str) -> list:
    """
    Generate realistic mock place data with working images for demo purposes
    when Google Places API is not available
    """
    
    # Extract location from query if possible
    location_match = re.search(r'(?:in|at|near)\s+([A-Za-z\s]+?)(?:\s|$|[.,!?])', query, re.IGNORECASE)
    location = location_match.group(1).strip() if location_match else "your area"
    
    # Determine request type
    is_singular = detect_singular_request(query)
    max_results = 1 if is_singular else 6
    
    # Mock places database with real working images
    mock_restaurants = [
        {
            'name': 'The Local Bistro',
            'address': f'123 Main Street, {location}',
            'rating': 4.5,
            'rating_count': 324,
            'types': ['restaurant', 'food'],
            'category_badge': '🍽️ Restaurant',
            'hero_image': 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200&auto=format&fit=crop',
            'description': f'A cozy neighborhood restaurant serving fresh, locally-sourced cuisine in the heart of {location}.'
        },
        {
            'name': 'Pizza Corner',
            'address': f'456 Oak Avenue, {location}',
            'rating': 4.3,
            'rating_count': 187,
            'types': ['restaurant', 'food', 'pizza'],
            'category_badge': '🍕 Pizza',
            'hero_image': 'https://images.unsplash.com/photo-1565299624946-b28f40a0ca4b?w=1200&auto=format&fit=crop',
            'description': f'Authentic wood-fired pizza with fresh ingredients, a local favorite in {location}.'
        },
        {
            'name': 'Café Delights',
            'address': f'789 Elm Street, {location}',
            'rating': 4.7,
            'rating_count': 245,
            'types': ['cafe', 'food'],
            'category_badge': '☕ Café',
            'hero_image': 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?w=1200&auto=format&fit=crop',
            'description': f'Artisanal coffee and fresh pastries in a warm, welcoming atmosphere.'
        }
    ]
    
    mock_hotels = [
        {
            'name': 'Grand Hotel',
            'address': f'100 Central Plaza, {location}',
            'rating': 4.4,
            'rating_count': 156,
            'types': ['lodging', 'hotel'],
            'category_badge': '🏨 Hotel',
            'hero_image': 'https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1200&auto=format&fit=crop',
            'description': f'Luxury accommodations in the heart of {location} with world-class amenities.'
        },
        {
            'name': 'Boutique Inn',
            'address': f'250 Heritage Lane, {location}',
            'rating': 4.6,
            'rating_count': 89,
            'types': ['lodging', 'hotel'],
            'category_badge': '🏨 Hotel',
            'hero_image': 'https://images.unsplash.com/photo-1578683010236-d716f9a3f461?w=1200&auto=format&fit=crop',
            'description': f'Charming boutique hotel with personalized service and unique character.'
        }
    ]
    
    mock_attractions = [
        {
            'name': 'City Museum',
            'address': f'300 Culture Street, {location}',
            'rating': 4.2,
            'rating_count': 234,
            'types': ['museum', 'tourist_attraction'],
            'category_badge': '🏛️ Museum',
            'hero_image': 'https://images.unsplash.com/photo-1595862804940-94ad0b0b54a4?w=1200&auto=format&fit=crop',
            'description': f'Discover the rich history and culture of {location} through fascinating exhibits.'
        },
        {
            'name': 'Central Park',
            'address': f'400 Green Avenue, {location}',
            'rating': 4.5,
            'rating_count': 412,
            'types': ['park', 'tourist_attraction'],
            'category_badge': '🌳 Park',
            'hero_image': 'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=1200&auto=format&fit=crop',
            'description': f'Beautiful green space perfect for relaxation and outdoor activities.'
        }
    ]
    
    # Select appropriate mock data based on query
    if 'restaurant' in query.lower() or 'food' in query.lower() or 'eat' in query.lower():
        mock_places = mock_restaurants
    elif 'hotel' in query.lower() or 'stay' in query.lower() or 'accommodation' in query.lower():
        mock_places = mock_hotels
    elif 'museum' in query.lower() or 'park' in query.lower() or 'attraction' in query.lower():
        mock_places = mock_attractions
    else:
        # Mix of different types for general queries
        mock_places = mock_restaurants + mock_hotels + mock_attractions
    
    # Randomly select places and add required fields
    selected_places = random.sample(mock_places, min(max_results, len(mock_places)))
    
    for place in selected_places:
        place.update({
            'place_id': f"mock_{random.randint(1000, 9999)}",
            'smart_tags': [],
            'has_real_photos': False,
            'image_source': 'unsplash_demo',
            'google_maps_url': f"https://www.google.com/maps/search/{place['name'].replace(' ', '+')}+{location.replace(' ', '+')}",
            'google_search_url': f"https://www.google.com/search?q={place['name'].replace(' ', '+')}+{location.replace(' ', '+')}",
            'website': '',
            'phone': '',
            'price_level': random.randint(1, 4)
        })
        
        # Add smart tags based on rating
        if place['rating'] >= 4.5:
            place['smart_tags'].append('highly-rated')
        if place['price_level'] <= 2:
            place['smart_tags'].append('budget-friendly')
        elif place['price_level'] >= 4:
            place['smart_tags'].append('premium')
    
    return selected_places

# Test the function
if __name__ == "__main__":
    test_queries = [
        "restaurants in Tokyo",
        "a restaurant in Paris", 
        "hotels in New York",
        "attractions in London"
    ]
    
    print("Testing mock places generation:")
    print("=" * 50)
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        places = generate_mock_places_data(query)
        print(f"Generated {len(places)} places:")
        
        for i, place in enumerate(places, 1):
            print(f"  {i}. {place['name']}")
            print(f"     Image: {place['hero_image']}")
            print(f"     Rating: {place['rating']} ({place['rating_count']} reviews)")
            print(f"     Tags: {place['smart_tags']}")
            print()
