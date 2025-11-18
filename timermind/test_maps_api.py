#!/usr/bin/env python3
"""
Quick test script to verify Google Maps API integration.
"""
import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from services.google_maps_service import get_maps_service

def test_maps_api():
    """Test Google Maps API functionality."""

    print("=" * 60)
    print("Testing Google Maps API Integration")
    print("=" * 60)

    # Get the Maps service
    maps_service = get_maps_service()

    # Test 1: Check if API key is configured
    print("\n[Test 1] API Key Configuration")
    if maps_service.is_enabled():
        print("✓ Google Maps API key is configured")
    else:
        print("✗ Google Maps API key is NOT configured")
        return False

    # Test 2: Geocode an address
    print("\n[Test 2] Geocoding Test")
    test_address = "Campbell, CA"
    result = maps_service.geocode(test_address)

    if result:
        print(f"✓ Geocoding successful for '{test_address}'")
        print(f"  - Formatted address: {result['formatted_address']}")
        print(f"  - Coordinates: ({result['lat']}, {result['lng']})")
    else:
        print(f"✗ Geocoding failed for '{test_address}'")
        return False

    # Test 3: Calculate travel time
    print("\n[Test 3] Travel Time Calculation")
    origin = "San Jose, CA"
    destination = "Campbell, CA"

    result = maps_service.calculate_travel_time(
        origin=origin,
        destination=destination
    )

    if result:
        print(f"✓ Travel time calculation successful")
        print(f"  - From: {result['origin_address']}")
        print(f"  - To: {result['destination_address']}")
        print(f"  - Distance: {result['distance_km']} km ({result['distance_meters']} meters)")
        print(f"  - Duration: {result['duration_minutes']} minutes")
        print(f"  - Duration in traffic: {result['duration_in_traffic_minutes']} minutes")
    else:
        print(f"✗ Travel time calculation failed")
        return False

    # Test 4: Calculate departure time
    print("\n[Test 4] Departure Time Calculation")
    arrival_time = datetime.now() + timedelta(hours=2)

    result = maps_service.calculate_departure_time(
        origin=origin,
        destination=destination,
        arrival_time=arrival_time
    )

    if result:
        departure_time, travel_minutes, distance_km = result
        print(f"✓ Departure time calculation successful")
        print(f"  - Desired arrival: {arrival_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  - Recommended departure: {departure_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  - Travel time: {travel_minutes} minutes")
        print(f"  - Distance: {distance_km} km")
    else:
        print(f"✗ Departure time calculation failed")
        return False

    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_maps_api()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
