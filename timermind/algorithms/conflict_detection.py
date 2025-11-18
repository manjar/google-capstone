"""
Conflict detection algorithms for TimerMind.

This module provides functions to detect:
- Timeline conflicts (impossible schedules)
- Travel time conflicts (insufficient time to travel between locations)
- Nearby timers (events close in time that may need location confirmation)
"""

import sqlite3
from datetime import timedelta
from typing import Optional

from config import DB_PATH


def detect_timeline_conflicts(
    new_timer_data: dict,
    existing_timers: Optional[list] = None
) -> list[dict]:
    """
    Detect spatiotemporal conflicts between a new timer and existing timers.

    Uses actual Google Maps travel times to detect impossible timelines.

    Checks for:
    1. Location conflicts - being at different locations at overlapping times
    2. Travel time conflicts - insufficient time to travel between consecutive locations (uses real Maps API data)
    3. Impossible timelines - need to leave before a previous event ends

    Args:
        new_timer_data: Dict with new timer info (label, deadline, destination_address,
                       arrival_time, departure_time, etc.)
        existing_timers: Optional list of existing timers (if None, fetches from DB)

    Returns:
        List of conflict dicts, each containing:
        - type: "location_overlap", "insufficient_travel_time", or "impossible_timeline"
        - description: Human-readable description
        - conflicting_timer: The timer that conflicts
        - severity: "critical" or "warning"
        - actual_travel_time: Minutes needed (if calculated)
        - time_available: Minutes available
    """
    from dateutil import parser as date_parser
    from services.google_maps_service import get_maps_service

    conflicts = []
    maps_service = get_maps_service()

    # Get existing timers if not provided
    if existing_timers is None:
        # Import here to avoid circular dependency
        from database.operations import list_timers_from_db
        existing_timers = list_timers_from_db()

    # Parse new timer times
    new_deadline = new_timer_data.get('deadline')
    new_arrival = new_timer_data.get('arrival_time')
    new_departure = new_timer_data.get('departure_time')
    new_destination = new_timer_data.get('destination_address')
    new_label = new_timer_data.get('label', 'New timer')
    new_duration_minutes = new_timer_data.get('estimated_duration_minutes', 0)

    if not new_deadline and not new_arrival:
        # No deadline, can't check conflicts
        return conflicts

    # Use arrival time if it's a location-based timer, otherwise use deadline
    new_time_str = new_arrival or new_deadline

    try:
        new_time = date_parser.isoparse(new_time_str)
        if new_departure:
            new_departure_dt = date_parser.isoparse(new_departure)
        else:
            new_departure_dt = None

        # Calculate end time for appointments/events with duration
        # new_time is the start time (arrival or deadline)
        # end time = start time + duration
        new_end_time = new_time + timedelta(minutes=new_duration_minutes) if new_duration_minutes else new_time
    except:
        return conflicts

    # Build timeline of all timers with times
    timeline = []
    for timer in existing_timers:
        timer_deadline = timer.get('deadline')
        timer_arrival = timer.get('arrival_time')
        timer_departure = timer.get('departure_time')
        timer_destination = timer.get('destination_address')
        timer_duration_minutes = timer.get('estimated_duration_minutes', 0)

        if not timer_deadline and not timer_arrival:
            continue

        # Use arrival time for location-based timers, deadline otherwise
        timer_time_str = timer_arrival or timer_deadline
        try:
            timer_time = date_parser.isoparse(timer_time_str)
            timer_departure_dt = date_parser.isoparse(timer_departure) if timer_departure else None
            timer_arrival_dt = date_parser.isoparse(timer_arrival) if timer_arrival else None

            # Calculate end time for appointments/events with duration
            timer_end_time = timer_time + timedelta(minutes=timer_duration_minutes) if timer_duration_minutes else timer_time
        except:
            continue

        timeline.append({
            'timer': timer,
            'time': timer_time,
            'end_time': timer_end_time,
            'duration_minutes': timer_duration_minutes,
            'arrival_time': timer_arrival,
            'arrival_dt': timer_arrival_dt,
            'departure_time': timer_departure,
            'departure_dt': timer_departure_dt,
            'destination': timer_destination,
            'label': timer.get('label', 'Timer')
        })

    # Sort timeline by time
    timeline.sort(key=lambda x: x['time'])

    # Check for conflicts with each existing timer
    for timeline_item in timeline:
        existing_timer = timeline_item['timer']
        existing_time = timeline_item['time']
        existing_end_time = timeline_item['end_time']
        existing_duration = timeline_item['duration_minutes']
        existing_destination = timeline_item['destination']
        existing_label = timeline_item['label']
        existing_arrival_dt = timeline_item['arrival_dt']
        existing_departure_dt = timeline_item['departure_dt']

        # Skip if neither timer has a location
        if not new_destination and not existing_destination:
            continue

        # Check 1: Impossible timeline - need to depart before existing event ends
        if existing_time < new_time and new_departure_dt:
            # Existing event is before new event
            # Check if we need to leave for new event before existing event completes
            # Use end time if appointment has duration, otherwise use start time
            if new_departure_dt < existing_end_time:
                time_gap_minutes = (existing_end_time - new_departure_dt).total_seconds() / 60
                duration_msg = f" (ends at {existing_end_time.strftime('%I:%M %p')})" if existing_duration else ""
                conflicts.append({
                    'type': 'impossible_timeline',
                    'description': f"You need to leave for '{new_label}' at {new_departure_dt.strftime('%I:%M %p')}, but '{existing_label}'{duration_msg} doesn't finish until {existing_end_time.strftime('%I:%M %p')} ({int(abs(time_gap_minutes))} minutes later)",
                    'conflicting_timer': existing_timer,
                    'severity': 'critical',
                    'time_available': -int(time_gap_minutes)  # Negative = impossible
                })

        # Check 2: Insufficient travel time using ACTUAL Maps API calculation
        # After new event, check if there's time to get to existing event
        if new_time < existing_time and new_destination and existing_destination and existing_departure_dt:
            # New event is before existing event
            # Calculate actual travel time from new destination to existing destination
            # Use end time if new event has duration
            time_available_minutes = (existing_departure_dt - new_end_time).total_seconds() / 60

            # Only check if events are within reasonable time of each other (same day)
            if time_available_minutes > 0 and time_available_minutes < 720:  # Within 12 hours
                # Use Maps API to get actual travel time
                if maps_service.is_enabled():
                    result = maps_service.calculate_departure_time(
                        origin=new_destination,
                        destination=existing_destination,
                        arrival_time=existing_time  # When we need to arrive at existing event
                    )

                    if result:
                        _, actual_travel_minutes, _ = result

                        # Check if we have enough time
                        if time_available_minutes < actual_travel_minutes:
                            shortfall = actual_travel_minutes - time_available_minutes
                            new_duration_msg = f" ({new_duration_minutes} min duration, ends {new_end_time.strftime('%I:%M %p')})" if new_duration_minutes else f" (ends {new_end_time.strftime('%I:%M %p')})"
                            conflicts.append({
                                'type': 'insufficient_travel_time',
                                'description': f"After '{new_label}' at {new_destination}{new_duration_msg}, you need to be at '{existing_label}' in {existing_destination} by {existing_departure_dt.strftime('%I:%M %p')}. Travel time is {int(actual_travel_minutes)} minutes, but you only have {int(time_available_minutes)} minutes available (short by {int(shortfall)} minutes)",
                                'conflicting_timer': existing_timer,
                                'severity': 'critical' if shortfall > 5 else 'warning',
                                'actual_travel_time': int(actual_travel_minutes),
                                'time_available': int(time_available_minutes)
                            })

        # Check 3: After existing event, check if there's time to get to new event
        # LOCATION CHAINING: Calculate direct travel from existing location to new location
        if existing_time < new_time and new_destination and existing_destination:
            # Existing event is before new event
            # Calculate actual travel time from existing destination to new destination
            # This implements proper location state tracking - you're AT the existing location after it ends
            # Use end time if existing event has duration
            time_available_minutes = (new_time - existing_end_time).total_seconds() / 60

            # Only check if events are within reasonable time of each other
            if time_available_minutes > 0 and time_available_minutes < 720:  # Within 12 hours
                # Use Maps API to get actual travel time
                if maps_service.is_enabled():
                    result = maps_service.calculate_departure_time(
                        origin=existing_destination,
                        destination=new_destination,
                        arrival_time=new_time  # When we need to arrive at new event
                    )

                    if result:
                        _, actual_travel_minutes, _ = result

                        # Check if we have enough time
                        if time_available_minutes < actual_travel_minutes:
                            shortfall = actual_travel_minutes - time_available_minutes
                            existing_duration_msg = f" ({existing_duration} min duration, ends {existing_end_time.strftime('%I:%M %p')})" if existing_duration else f" (ends {existing_end_time.strftime('%I:%M %p')})"
                            conflicts.append({
                                'type': 'insufficient_travel_time',
                                'description': f"After '{existing_label}' at {existing_destination}{existing_duration_msg}, you need to be at '{new_label}' in {new_destination} by {new_time.strftime('%I:%M %p')}. Travel time is {int(actual_travel_minutes)} minutes, but you only have {int(time_available_minutes)} minutes available (short by {int(shortfall)} minutes)",
                                'conflicting_timer': existing_timer,
                                'severity': 'critical' if shortfall > 5 else 'warning',
                                'actual_travel_time': int(actual_travel_minutes),
                                'time_available': int(time_available_minutes)
                            })

    return conflicts


def detect_nearby_timers(
    new_timer_data: dict,
    existing_timers: Optional[list] = None,
    proximity_window_hours: float = 3.0
) -> list[dict]:
    """
    Detect timers that are temporally close to a new timer.

    This function identifies "nearby" events that warrant location confirmation
    to prevent potential conflicts. It flags cases where:
    - Two timers are within proximity_window_hours of each other
    - At least one has a location specified
    - User should confirm locations are compatible

    Args:
        new_timer_data: Dict with 'label', 'deadline', 'destination_address', etc.
        existing_timers: List of existing timer dicts to check against
        proximity_window_hours: Time window (hours) to consider "nearby" (default: 3.0)

    Returns:
        List of proximity warnings with suggested confirmation questions
    """
    from dateutil import parser as date_parser

    proximity_warnings = []

    # Parse new timer data
    new_label = new_timer_data.get('label', 'New timer')
    new_deadline_str = new_timer_data.get('deadline')
    new_destination = new_timer_data.get('destination_address')
    new_arrival_str = new_timer_data.get('arrival_time')
    new_departure_str = new_timer_data.get('departure_time')

    if not new_deadline_str:
        return proximity_warnings

    try:
        new_time = date_parser.isoparse(new_deadline_str)
    except (ValueError, TypeError):
        return proximity_warnings

    # Determine the "event time" for the new timer (departure if location-based, else deadline)
    new_event_time = new_time
    if new_departure_str:
        try:
            new_event_time = date_parser.isoparse(new_departure_str)
        except (ValueError, TypeError):
            pass

    # Fetch existing timers if not provided
    if existing_timers is None:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("""
                SELECT id, label, deadline, destination_address, arrival_time, departure_time, status
                FROM timers
                WHERE status != 'completed'
            """).fetchall()
            existing_timers = [
                {
                    'id': row[0],
                    'label': row[1],
                    'deadline': row[2],
                    'destination_address': row[3],
                    'arrival_time': row[4],
                    'departure_time': row[5],
                    'status': row[6]
                }
                for row in rows
            ]

    proximity_window_minutes = proximity_window_hours * 60

    for existing_timer in existing_timers:
        existing_label = existing_timer.get('label', 'Existing timer')
        existing_deadline = existing_timer.get('deadline')
        existing_destination = existing_timer.get('destination_address')
        existing_arrival = existing_timer.get('arrival_time')
        existing_departure = existing_timer.get('departure_time')

        if not existing_deadline:
            continue

        try:
            existing_time = date_parser.isoparse(existing_deadline)
        except (ValueError, TypeError):
            continue

        # Determine event time for existing timer
        existing_event_time = existing_time
        if existing_departure:
            try:
                existing_event_time = date_parser.isoparse(existing_departure)
            except (ValueError, TypeError):
                pass

        # Calculate time difference
        time_diff_minutes = abs((new_event_time - existing_event_time).total_seconds() / 60)

        # Check if timers are within proximity window
        if time_diff_minutes <= proximity_window_minutes:
            # Only flag if at least one has a location
            has_location = new_destination or existing_destination

            if has_location:
                # Build proximity warning
                time_diff_hours = time_diff_minutes / 60

                # Determine the relationship
                if time_diff_minutes < 30:
                    proximity_type = 'very_close'  # Less than 30 minutes apart
                    severity = 'high'
                elif time_diff_minutes < 120:
                    proximity_type = 'close'  # 30 min to 2 hours
                    severity = 'medium'
                else:
                    proximity_type = 'nearby'  # 2-3 hours
                    severity = 'low'

                # Format time information
                if new_event_time < existing_event_time:
                    order = f"{new_label} ({new_event_time.strftime('%I:%M %p')}) is {int(time_diff_minutes)} minutes before {existing_label} ({existing_event_time.strftime('%I:%M %p')})"
                else:
                    order = f"{new_label} ({new_event_time.strftime('%I:%M %p')}) is {int(time_diff_minutes)} minutes after {existing_label} ({existing_event_time.strftime('%I:%M %p')})"

                # Create location summary
                location_info = []
                if new_destination:
                    location_info.append(f"'{new_label}' is at {new_destination}")
                else:
                    location_info.append(f"'{new_label}' has no location specified")

                if existing_destination:
                    location_info.append(f"'{existing_label}' is at {existing_destination}")
                else:
                    location_info.append(f"'{existing_label}' has no location specified")

                location_summary = ". ".join(location_info)

                # Create suggested question
                if new_destination and existing_destination:
                    if new_destination.lower() == existing_destination.lower():
                        suggested_question = f"Both events are at the same location ({new_destination}). Is this correct?"
                    else:
                        suggested_question = f"You have two events at different locations within {int(time_diff_hours)} hours. Can you confirm the locations are correct?"
                elif new_destination and not existing_destination:
                    suggested_question = f"'{new_label}' is at {new_destination}, but '{existing_label}' has no location. Where is '{existing_label}'?"
                else:  # existing has location, new doesn't
                    suggested_question = f"'{existing_label}' is at {existing_destination}, but '{new_label}' has no location. Where is '{new_label}'?"

                proximity_warnings.append({
                    'type': proximity_type,
                    'severity': severity,
                    'time_difference_minutes': int(time_diff_minutes),
                    'nearby_timer': existing_timer,
                    'order': order,
                    'location_summary': location_summary,
                    'suggested_question': suggested_question,
                    'description': f"{order}. {location_summary}"
                })

    return proximity_warnings
