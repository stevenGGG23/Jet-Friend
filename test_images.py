#!/usr/bin/env python3

# Quick test to check image generation
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import get_enhanced_place_image, generate_query_specific_places

def test_image_generation():
    print("Testing image generation...")
    
    # Test pizza place image
    pizza_image = get_enhanced_place_image("Tony's Pizza Palace", "pizza", "New York")
    print(f"Pizza place image: {pizza_image}")
    
    # Test burger place image
    burger_image = get_enhanced_place_image("The Burger Joint", "burger", "New York")
    print(f"Burger place image: {burger_image}")
    
    # Test coffee shop image
    coffee_image = get_enhanced_place_image("The Daily Grind", "coffee", "New York")
    print(f"Coffee shop image: {coffee_image}")
    
    print("\nTesting place generation...")
    
    # Test pizza places
    pizza_places = generate_query_specific_places("pizza places in New York", "New York", 2)
    for place in pizza_places:
        print(f"Pizza place: {place['name']} - Image: {place['hero_image']}")
    
    # Test coffee places
    coffee_places = generate_query_specific_places("coffee shops in Seattle", "Seattle", 2)
    for place in coffee_places:
        print(f"Coffee place: {place['name']} - Image: {place['hero_image']}")

if __name__ == "__main__":
    test_image_generation()
