"""
Google Maps Platform integration for location-aware features.

Provides:
- Geocoding (address to coordinates)
- Travel time calculations with real-time traffic
- Distance calculations

Design Decision: Using Google Maps Platform because:
1. Consistent with project's Google stack (Gemini, ADK)
2. Industry-leading traffic predictions
3. Comprehensive location data
"""

import os
import requests
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger("timermind")


class GoogleMapsService:
    """Service for Google Maps API interactions."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Google Maps service.

        Args:
            api_key: Google Maps API key (optional, will use env var if not provided)
        """
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        self.geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
        self.distancematrix_url = "https://maps.googleapis.com/maps/api/distancematrix/json"

    def is_enabled(self) -> bool:
        """Check if Maps API is configured."""
        return self.api_key is not None

    def geocode(self, address: str) -> Optional[Dict]:
        """
        Convert address to coordinates.

        Args:
            address: Address string to geocode

        Returns:
            Dict with lat, lng, formatted_address, or None if geocoding fails
        """
        if not self.is_enabled():
            logger.warning("Maps API not configured - cannot geocode")
            return None

        try:
            response = requests.get(
                self.geocoding_url,
                params={
                    "address": address,
                    "key": self.api_key
                },
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            if data["status"] == "OK" and data["results"]:
                result = data["results"][0]
                location = result["geometry"]["location"]
                return {
                    "lat": location["lat"],
                    "lng": location["lng"],
                    "formatted_address": result["formatted_address"]
                }
            else:
                logger.warning(f"Geocoding failed for '{address}': {data['status']}")
                return None

        except Exception as e:
            logger.error(f"Geocoding error for '{address}': {e}")
            return None

    def calculate_travel_time(
        self,
        origin: str,
        destination: str,
        arrival_time: Optional[datetime] = None,
        departure_time: Optional[datetime] = None
    ) -> Optional[Dict]:
        """
        Calculate travel time between origin and destination with traffic.

        Args:
            origin: Origin address
            destination: Destination address
            arrival_time: Desired arrival time (for traffic-aware routing)
            departure_time: Departure time (alternative to arrival_time)

        Returns:
            Dict with:
            - duration_minutes: Travel time in minutes (with traffic)
            - duration_in_traffic_minutes: Current traffic-aware duration
            - distance_km: Distance in kilometers
            - distance_meters: Distance in meters
            - origin_address: Formatted origin address
            - destination_address: Formatted destination address
            Or None if calculation fails
        """
        if not self.is_enabled():
            logger.warning("Maps API not configured - cannot calculate travel time")
            return None

        try:
            params = {
                "origins": origin,
                "destinations": destination,
                "key": self.api_key,
                "mode": "driving",
                "departure_time": "now"  # Default to current traffic
            }

            # Use arrival_time if provided (for backward calculation)
            if arrival_time:
                # Convert to Unix timestamp
                timestamp = int(arrival_time.timestamp())
                params["arrival_time"] = timestamp
                del params["departure_time"]
            elif departure_time:
                timestamp = int(departure_time.timestamp())
                params["departure_time"] = timestamp

            response = requests.get(
                self.distancematrix_url,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data["status"] == "OK" and data["rows"]:
                row = data["rows"][0]
                if row["elements"] and row["elements"][0]["status"] == "OK":
                    element = row["elements"][0]

                    # Get duration (base time) and duration_in_traffic (current traffic)
                    duration_seconds = element["duration"]["value"]
                    duration_minutes = duration_seconds / 60

                    # Duration in traffic (if available)
                    traffic_duration_minutes = duration_minutes
                    if "duration_in_traffic" in element:
                        traffic_duration_minutes = element["duration_in_traffic"]["value"] / 60

                    distance_meters = element["distance"]["value"]
                    distance_km = distance_meters / 1000

                    return {
                        "duration_minutes": round(duration_minutes, 1),
                        "duration_in_traffic_minutes": round(traffic_duration_minutes, 1),
                        "distance_km": round(distance_km, 2),
                        "distance_meters": distance_meters,
                        "origin_address": data["origin_addresses"][0],
                        "destination_address": data["destination_addresses"][0]
                    }
                else:
                    logger.warning(f"No route found from '{origin}' to '{destination}'")
                    return None
            else:
                logger.warning(f"Distance Matrix API error: {data['status']}")
                return None

        except Exception as e:
            logger.error(f"Travel time calculation error: {e}")
            return None

    def calculate_departure_time(
        self,
        origin: str,
        destination: str,
        arrival_time: datetime
    ) -> Optional[Tuple[datetime, int, float]]:
        """
        Calculate when to leave to arrive at a destination by a specific time.

        Args:
            origin: Origin address
            destination: Destination address
            arrival_time: Desired arrival time

        Returns:
            Tuple of (departure_time, travel_minutes, distance_km) or None
        """
        result = self.calculate_travel_time(
            origin=origin,
            destination=destination,
            arrival_time=arrival_time
        )

        if not result:
            return None

        # Use traffic-aware duration
        travel_minutes = result["duration_in_traffic_minutes"]
        distance_km = result["distance_km"]

        # Calculate departure time
        from datetime import timedelta
        departure_time = arrival_time - timedelta(minutes=travel_minutes)

        return (departure_time, int(travel_minutes), distance_km)


# Global instance
_maps_service = None

def get_maps_service() -> GoogleMapsService:
    """Get or create the global Maps service instance."""
    global _maps_service
    if _maps_service is None:
        _maps_service = GoogleMapsService()
    return _maps_service
