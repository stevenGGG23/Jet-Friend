#!/usr/bin/env python3
"""
Test script to validate that place cards show for ALL location-based queries,
not just restaurants. Tests the detect_location_query function and API responses.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import detect_location_query

def test_location_detection():
    """Test the location detection function with various travel queries"""
    
    test_queries = [
        # Trip planning queries (should detect location)
        "3 day trip to Paris",
        "Plan a 5 day itinerary for Tokyo",
        "What to do in Rome for 2 days",
        "Weekend getaway to Barcelona",
        "1 week vacation in Thailand",
        
        # Hotel queries (should detect location)
        "hotels in Tokyo",
        "best places to stay in London",
        "accommodation in Barcelona",
        "where to stay in Paris",
        "luxury hotels near Times Square",
        
        # Attraction queries (should detect location)
        "things to do in Rome",
        "attractions in London",
        "museums near me",
        "parks in Central Park area",
        "sights to see in Amsterdam",
        
        # Activity queries (should detect location)
        "what to see in Madrid",
        "activities in San Francisco",
        "tour options in Egypt",
        "experiences in Bali",
        "adventures in Costa Rica",
        
        # Restaurant queries (should detect location)
        "restaurants in Italy",
        "best food in Bangkok",
        "where to eat in Paris",
        "local cuisine in Mexico",
        
        # General travel queries (should detect location)
        "travel guide for Japan",
        "visit recommendations for Greece",
        "explore options in Iceland",
        "discover hidden gems in Portugal",
        
        # Non-location queries (should NOT detect location)
        "What is the weather like?",
        "How do airplanes work?",
        "Tell me about quantum physics",
        "What's the meaning of life?",
        "How to learn programming?",
    ]
    
    print("🧪 Testing Location Detection for Place Cards")
    print("=" * 60)
    
    should_detect = test_queries[:-5]  # All except the last 5
    should_not_detect = test_queries[-5:]  # Last 5 queries
    
    print(f"\n✅ Testing queries that SHOULD show place cards ({len(should_detect)} queries):")
    print("-" * 60)
    
    success_count = 0
    for query in should_detect:
        is_detected = detect_location_query(query)
        status = "✅ PASS" if is_detected else "❌ FAIL"
        print(f"{status} | {query}")
        if is_detected:
            success_count += 1
    
    print(f"\nResults: {success_count}/{len(should_detect)} location queries detected correctly")
    
    print(f"\n🚫 Testing queries that should NOT show place cards ({len(should_not_detect)} queries):")
    print("-" * 60)
    
    success_count_negative = 0
    for query in should_not_detect:
        is_detected = detect_location_query(query)
        status = "✅ PASS" if not is_detected else "❌ FAIL"
        print(f"{status} | {query}")
        if not is_detected:
            success_count_negative += 1
    
    print(f"\nResults: {success_count_negative}/{len(should_not_detect)} non-location queries detected correctly")
    
    total_success = success_count + success_count_negative
    total_tests = len(test_queries)
    
    print("\n" + "=" * 60)
    print(f"📊 FINAL RESULTS: {total_success}/{total_tests} tests passed ({total_success/total_tests*100:.1f}%)")
    
    if total_success == total_tests:
        print("🎉 All tests passed! Place cards should show for ALL travel-related queries.")
    else:
        print("⚠️  Some tests failed. Check the location detection logic.")
    
    return total_success == total_tests

def test_example_api_calls():
    """Test example API calls to demonstrate place card responses"""
    
    print("\n" + "=" * 60)
    print("🔍 Example API Response Simulation")
    print("=" * 60)
    
    example_queries = [
        "3 day trip to Paris",
        "hotels in Tokyo", 
        "things to do in Rome",
        "museums near me",
        "attractions in London"
    ]
    
    for query in example_queries:
        location_detected = detect_location_query(query)
        print(f"\nQuery: '{query}'")
        print(f"Location Detected: {location_detected}")
        print(f"Expected API Response:")
        print(f"  - places_found: {'>0' if location_detected else '0'}")
        print(f"  - enhanced_with_location: {location_detected}")
        print(f"  - place_cards_shown: {'Yes' if location_detected else 'No'}")

if __name__ == "__main__":
    success = test_location_detection()
    test_example_api_calls()
    
    print("\n" + "=" * 60)
    print("🎯 Key Points:")
    print("- Place cards should show for ANY travel/location query")
    print("- Backend uses detect_location_query() to check places_found > 0")
    print("- Frontend logs metadata and shows location badge")
    print("- Enhanced keywords now include trip planning, hotels, attractions")
    
    if success:
        print("\n✅ Location detection is working correctly!")
        print("💡 Place cards should now appear for all travel-related queries.")
    else:
        print("\n❌ Some location detection issues found.")
        print("💡 Review the location_keywords list in app.py")
