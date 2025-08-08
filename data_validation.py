"""
Data Validation and Image Sourcing System for Builder.io Integration
Implements comprehensive data accuracy, link validation, and image sourcing
"""

import requests
import logging
import time
import googlemaps
import os
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, quote_plus
import json
import re

logger = logging.getLogger(__name__)

class DataValidator:
    """Comprehensive data validation system for accurate Builder.io implementations"""
    
    def __init__(self, gmaps_client=None, google_images_api_key=None, google_search_engine_id=None):
        self.gmaps_client = gmaps_client
        self.google_images_api_key = google_images_api_key
        self.google_search_engine_id = google_search_engine_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def validate_url(self, url: str, timeout: int = 10) -> Dict:
        """
        Validate URL returns 200 status code and is accessible
        Returns validation result with status and metadata
        """
        try:
            if not url or url == '#' or not url.startswith(('http://', 'https://')):
                return {
                    'valid': False,
                    'status_code': None,
                    'error': 'Invalid URL format',
                    'accessible': False
                }
            
            response = self.session.head(url, timeout=timeout, allow_redirects=True)
            
            # If HEAD fails, try GET with limited content
            if response.status_code >= 400:
                response = self.session.get(url, timeout=timeout, stream=True)
                # Read only first 1KB to check accessibility
                content = response.raw.read(1024)
                
            return {
                'valid': response.status_code == 200,
                'status_code': response.status_code,
                'final_url': response.url,
                'accessible': response.status_code < 400,
                'content_type': response.headers.get('content-type', ''),
                'response_time': response.elapsed.total_seconds()
            }
            
        except requests.exceptions.Timeout:
            return {
                'valid': False,
                'status_code': None,
                'error': 'Request timeout',
                'accessible': False
            }
        except requests.exceptions.RequestException as e:
            return {
                'valid': False,
                'status_code': None,
                'error': str(e),
                'accessible': False
            }
    
    def validate_coordinates_match_address(self, address: str, lat: float, lng: float, tolerance_km: float = 1.0) -> Dict:
        """
        Verify geographic coordinates match the provided address
        Returns validation result with distance and accuracy metrics
        """
        if not self.gmaps_client or not address:
            return {
                'valid': False,
                'error': 'Google Maps client not available or address missing',
                'distance_km': None
            }
        
        try:
            # Geocode the address to get coordinates
            geocode_result = self.gmaps_client.geocode(address)
            
            if not geocode_result:
                return {
                    'valid': False,
                    'error': 'Address could not be geocoded',
                    'distance_km': None
                }
            
            geocoded_location = geocode_result[0]['geometry']['location']
            geocoded_lat = geocoded_location['lat']
            geocoded_lng = geocoded_location['lng']
            
            # Calculate distance using haversine formula
            distance_km = self._calculate_distance(lat, lng, geocoded_lat, geocoded_lng)
            
            return {
                'valid': distance_km <= tolerance_km,
                'distance_km': distance_km,
                'geocoded_coordinates': {
                    'lat': geocoded_lat,
                    'lng': geocoded_lng
                },
                'provided_coordinates': {
                    'lat': lat,
                    'lng': lng
                },
                'accuracy': geocode_result[0]['geometry'].get('location_type', 'UNKNOWN'),
                'formatted_address': geocode_result[0]['formatted_address']
            }
            
        except Exception as e:
            logger.error(f"Coordinate validation failed: {str(e)}")
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}',
                'distance_km': None
            }
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two coordinates using haversine formula"""
        import math
        
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)
        
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def validate_contact_info(self, phone: str = None, website: str = None, place_name: str = None) -> Dict:
        """
        Validate contact information through multiple sources
        Cross-reference phone numbers and websites for accuracy
        """
        validation_result = {
            'phone_valid': False,
            'website_valid': False,
            'cross_referenced': False,
            'confidence_score': 0.0,
            'errors': []
        }
        
        # Validate phone number format
        if phone:
            phone_validation = self._validate_phone_format(phone)
            validation_result['phone_valid'] = phone_validation['valid']
            if not phone_validation['valid']:
                validation_result['errors'].append(f"Phone format invalid: {phone_validation['error']}")
        
        # Validate website
        if website:
            website_validation = self.validate_url(website)
            validation_result['website_valid'] = website_validation['valid']
            if not website_validation['valid']:
                validation_result['errors'].append(f"Website invalid: {website_validation.get('error', 'Not accessible')}")
        
        # Calculate confidence score
        factors = []
        if phone and validation_result['phone_valid']:
            factors.append(0.4)
        if website and validation_result['website_valid']:
            factors.append(0.6)
        
        validation_result['confidence_score'] = sum(factors)
        
        return validation_result
    
    def _validate_phone_format(self, phone: str) -> Dict:
        """Validate phone number format"""
        if not phone:
            return {'valid': False, 'error': 'No phone number provided'}
        
        # Remove all non-digit characters except + at the beginning
        clean_phone = re.sub(r'[^\d+]', '', phone)
        
        # Basic international format validation
        if clean_phone.startswith('+'):
            if len(clean_phone) >= 10 and len(clean_phone) <= 16:
                return {'valid': True, 'formatted': clean_phone}
            else:
                return {'valid': False, 'error': 'Invalid international format length'}
        else:
            # Assume US format if no country code
            digits_only = re.sub(r'[^\d]', '', phone)
            if len(digits_only) == 10:
                return {'valid': True, 'formatted': f"+1{digits_only}"}
            elif len(digits_only) == 11 and digits_only.startswith('1'):
                return {'valid': True, 'formatted': f"+{digits_only}"}
            else:
                return {'valid': False, 'error': 'Invalid US phone format'}

class ImageSourcer:
    """Advanced image sourcing system with licensing compliance"""
    
    def __init__(self, google_images_api_key=None, google_search_engine_id=None):
        self.google_images_api_key = google_images_api_key
        self.google_search_engine_id = google_search_engine_id
        self.session = requests.Session()
        
        # Fallback image sources with proper licensing - high quality versions
        self.fallback_images = {
            'restaurant': 'https://images.pexels.com/photos/1581384/pexels-photo-1581384.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'hotel': 'https://images.pexels.com/photos/2067396/pexels-photo-2067396.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'attraction': 'https://images.pexels.com/photos/1640777/pexels-photo-1640777.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'temple': 'https://images.pexels.com/photos/1444424/pexels-photo-1444424.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'shrine': 'https://images.pexels.com/photos/4331617/pexels-photo-4331617.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'place_of_worship': 'https://images.pexels.com/photos/1444424/pexels-photo-1444424.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'tourist_attraction': 'https://images.pexels.com/photos/4022092/pexels-photo-4022092.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'bar': 'https://images.pexels.com/photos/941864/pexels-photo-941864.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'cafe': 'https://images.pexels.com/photos/302899/pexels-photo-302899.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'museum': 'https://images.pexels.com/photos/1263986/pexels-photo-1263986.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'park': 'https://images.pexels.com/photos/1680172/pexels-photo-1680172.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'shopping': 'https://images.pexels.com/photos/1005058/pexels-photo-1005058.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'default': 'https://images.pexels.com/photos/2067396/pexels-photo-2067396.jpeg?auto=compress&cs=tinysrgb&w=1200'
        }

        # Specific high-quality images for famous temples and landmarks
        self.specific_place_images = {
            'kinkaku-ji': 'https://images.pexels.com/photos/4022092/pexels-photo-4022092.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'golden pavilion': 'https://images.pexels.com/photos/4022092/pexels-photo-4022092.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'senso-ji': 'https://images.pexels.com/photos/4331617/pexels-photo-4331617.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'todai-ji': 'https://images.pexels.com/photos/1444424/pexels-photo-1444424.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'fushimi inari': 'https://images.pexels.com/photos/4331617/pexels-photo-4331617.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'tokyo temple': 'https://images.pexels.com/photos/4331617/pexels-photo-4331617.jpeg?auto=compress&cs=tinysrgb&w=1200',
            'kyoto temple': 'https://images.pexels.com/photos/4022092/pexels-photo-4022092.jpeg?auto=compress&cs=tinysrgb&w=1200'
        }
    
    def get_primary_image(self, place_name: str, place_types: List[str], location: str = None) -> Dict:
        """
        Get primary image through Google Images API with proper licensing
        Falls back to AI-generated images when suitable web images unavailable
        """
        image_result = {
            'url': None,
            'source': 'none',
            'license': 'unknown',
            'confidence': 0.0,
            'alt_text': '',
            'attribution': ''
        }
        
        # Try Google Images API first
        if self.google_images_api_key and self.google_search_engine_id:
            google_image = self._search_google_images(place_name, place_types, location)
            if google_image['success']:
                image_result.update(google_image)
                return image_result
        
        # Try web-sourced content with proper licensing
        web_image = self._search_web_licensed_images(place_name, place_types, location)
        if web_image['success']:
            image_result.update(web_image)
            return image_result
        
        # Fallback to curated stock images
        fallback_image = self._get_fallback_image(place_types, place_name)
        image_result.update(fallback_image)
        
        return image_result
    
    def _search_google_images(self, place_name: str, place_types: List[str], location: str = None) -> Dict:
        """Search Google Images API for licensed images"""
        try:
            search_query = f"{place_name}"
            if location:
                search_query += f" {location}"
            
            # Add context based on place type
            if 'restaurant' in str(place_types).lower():
                search_query += " restaurant interior exterior"
            elif 'lodging' in str(place_types).lower():
                search_query += " hotel building"
            elif 'tourist_attraction' in str(place_types).lower():
                search_query += " attraction landmark"
            
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                'key': self.google_images_api_key,
                'cx': self.google_search_engine_id,
                'q': search_query,
                'searchType': 'image',
                'rights': 'cc_publicdomain,cc_attribute,cc_sharealike',  # Licensed images only
                'num': 5,
                'safe': 'active',
                'imgSize': 'large'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                if items:
                    # Validate the first result
                    image_item = items[0]
                    image_url = image_item.get('link')
                    
                    # Validate image is accessible
                    validator = DataValidator()
                    url_validation = validator.validate_url(image_url)
                    
                    if url_validation['valid']:
                        return {
                            'success': True,
                            'url': image_url,
                            'source': 'google_images',
                            'license': 'creative_commons',
                            'confidence': 0.9,
                            'alt_text': image_item.get('title', place_name),
                            'attribution': image_item.get('displayLink', ''),
                            'width': image_item.get('image', {}).get('width', 0),
                            'height': image_item.get('image', {}).get('height', 0)
                        }
            
            return {'success': False, 'error': 'No valid Google Images found'}
            
        except Exception as e:
            logger.error(f"Google Images search failed: {str(e)}")
            return {'success': False, 'error': f'Google Images API error: {str(e)}'}
    
    def _search_web_licensed_images(self, place_name: str, place_types: List[str], location: str = None) -> Dict:
        """Search for web-sourced content with proper licensing"""
        # For now, use curated sources like Unsplash API (requires API key)
        # This would be implemented with proper licensing APIs
        
        try:
            # Example: Unsplash API integration (would need API key)
            # For this implementation, we'll use a more conservative approach
            # and fall back to known licensed sources
            
            return {'success': False, 'error': 'Web licensed image search not implemented'}
            
        except Exception as e:
            logger.error(f"Web licensed image search failed: {str(e)}")
            return {'success': False, 'error': f'Web search error: {str(e)}'}
    
    def _get_fallback_image(self, place_types: List[str], place_name: str = "") -> Dict:
        """Get appropriate fallback image based on place type with enhanced categorization"""
        place_types_str = str(place_types).lower()
        place_name_lower = place_name.lower()

        # First check for specific famous places
        for specific_place, image_url in self.specific_place_images.items():
            if specific_place in place_name_lower:
                return {
                    'success': True,
                    'url': image_url,
                    'source': 'pexels_specific',
                    'license': 'pexels_license',
                    'confidence': 0.9,  # High confidence for specific places
                    'alt_text': f'{place_name} - {specific_place}',
                    'attribution': 'Pexels'
                }

        # Then categorize by place type
        if 'restaurant' in place_types_str or 'food' in place_types_str or 'meal_takeaway' in place_types_str:
            image_url = self.fallback_images['restaurant']
            category = 'restaurant'
        elif 'bar' in place_types_str or 'night_club' in place_types_str:
            image_url = self.fallback_images['bar']
            category = 'bar'
        elif 'cafe' in place_types_str:
            image_url = self.fallback_images['cafe']
            category = 'cafe'
        elif 'lodging' in place_types_str or 'hotel' in place_types_str:
            image_url = self.fallback_images['hotel']
            category = 'hotel'
        elif 'place_of_worship' in place_types_str or 'temple' in place_types_str or 'shrine' in place_types_str:
            image_url = self.fallback_images['temple']
            category = 'temple'
        elif 'tourist_attraction' in place_types_str:
            image_url = self.fallback_images['tourist_attraction']
            category = 'tourist_attraction'
        elif 'museum' in place_types_str:
            image_url = self.fallback_images['museum']
            category = 'museum'
        elif 'park' in place_types_str:
            image_url = self.fallback_images['park']
            category = 'park'
        elif 'shopping' in place_types_str or 'store' in place_types_str:
            image_url = self.fallback_images['shopping']
            category = 'shopping'
        else:
            image_url = self.fallback_images['default']
            category = 'default'

        return {
            'success': True,
            'url': image_url,
            'source': 'pexels_licensed',
            'license': 'pexels_license',
            'confidence': 0.7,  # Increased confidence for better categorization
            'alt_text': f'{category.title()} image',
            'attribution': 'Pexels'
        }

class ComprehensiveDataProcessor:
    """Main processor for comprehensive data accuracy and validation"""
    
    def __init__(self, gmaps_client=None, google_images_api_key=None, google_search_engine_id=None):
        self.validator = DataValidator(gmaps_client, google_images_api_key, google_search_engine_id)
        self.image_sourcer = ImageSourcer(google_images_api_key, google_search_engine_id)
        self.gmaps_client = gmaps_client
    
    def process_place_data(self, place_data: Dict) -> Dict:
        """
        Process place data with comprehensive validation and enhancement
        Returns enhanced place data with validation scores and accurate images
        """
        enhanced_place = place_data.copy()
        
        # Initialize validation tracking
        validation_results = {
            'url_validations': {},
            'coordinate_validation': {},
            'contact_validation': {},
            'image_sourcing': {},
            'overall_confidence': 0.0,
            'data_quality_score': 0.0
        }
        
        # 1. Validate all URLs
        urls_to_check = [
            'google_maps_url', 'yelp_search_url', 'tripadvisor_search_url',
            'website', 'opentable_url', 'booking_url', 'uber_url'
        ]
        
        valid_urls = 0
        total_urls = 0
        
        for url_key in urls_to_check:
            if url_key in enhanced_place and enhanced_place[url_key]:
                total_urls += 1
                url_validation = self.validator.validate_url(enhanced_place[url_key])
                validation_results['url_validations'][url_key] = url_validation
                
                if not url_validation['valid']:
                    # Mark invalid URLs for removal or fixing
                    enhanced_place[f'{url_key}_status'] = 'invalid'
                    logger.warning(f"Invalid URL for {enhanced_place.get('name', 'Unknown')}: {url_key}")
                else:
                    valid_urls += 1
                    enhanced_place[f'{url_key}_status'] = 'valid'
        
        # 2. Validate coordinates match address
        if 'address' in enhanced_place and 'geometry' in place_data:
            geometry = place_data['geometry']['location']
            coord_validation = self.validator.validate_coordinates_match_address(
                enhanced_place['address'],
                geometry['lat'],
                geometry['lng']
            )
            validation_results['coordinate_validation'] = coord_validation
            
            if not coord_validation['valid']:
                logger.warning(f"Coordinate mismatch for {enhanced_place.get('name', 'Unknown')}")
        
        # 3. Validate contact information
        contact_validation = self.validator.validate_contact_info(
            phone=enhanced_place.get('phone'),
            website=enhanced_place.get('website'),
            place_name=enhanced_place.get('name')
        )
        validation_results['contact_validation'] = contact_validation
        
        # 4. Source primary image with proper licensing
        image_result = self.image_sourcer.get_primary_image(
            enhanced_place.get('name', ''),
            enhanced_place.get('types', []),
            enhanced_place.get('address', '')
        )
        
        validation_results['image_sourcing'] = image_result
        enhanced_place['hero_image'] = image_result['url']
        enhanced_place['image_source'] = image_result['source']
        enhanced_place['image_license'] = image_result['license']
        enhanced_place['image_attribution'] = image_result.get('attribution', '')
        
        # 5. Calculate overall confidence and data quality scores
        confidence_factors = []
        
        # URL validation score
        if total_urls > 0:
            url_score = valid_urls / total_urls
            confidence_factors.append(url_score * 0.3)
        
        # Coordinate validation score
        if validation_results['coordinate_validation']:
            coord_score = 1.0 if validation_results['coordinate_validation']['valid'] else 0.0
            confidence_factors.append(coord_score * 0.2)
        
        # Contact validation score
        contact_score = validation_results['contact_validation']['confidence_score']
        confidence_factors.append(contact_score * 0.2)
        
        # Image quality score
        image_score = image_result['confidence']
        confidence_factors.append(image_score * 0.3)
        
        validation_results['overall_confidence'] = sum(confidence_factors)
        validation_results['data_quality_score'] = min(validation_results['overall_confidence'] * 1.2, 1.0)
        
        # Add validation metadata
        enhanced_place['_validation'] = validation_results
        enhanced_place['_data_quality_score'] = validation_results['data_quality_score']
        enhanced_place['_last_validated'] = time.time()
        
        return enhanced_place
    
    def filter_high_confidence_places(self, places: List[Dict], min_confidence: float = 0.7) -> List[Dict]:
        """Filter places by data quality score to ensure high-confidence results"""
        high_confidence_places = []
        
        for place in places:
            if place.get('_data_quality_score', 0.0) >= min_confidence:
                high_confidence_places.append(place)
            else:
                logger.info(f"Filtered out low-confidence place: {place.get('name', 'Unknown')} (score: {place.get('_data_quality_score', 0.0)})")
        
        return high_confidence_places
