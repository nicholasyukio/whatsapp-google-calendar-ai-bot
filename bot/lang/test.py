from datetime import datetime, timedelta, time

blocked_times = {
    "weekdays": [
        (time(0, 0), time(7, 59)),
        (time(22, 0), time(23, 59)),
    ],
    "weekends": "all",
}

# ✅ MOCK: replace with your real calendar access logic
def list_events(time_min, time_max, max_results=100, include_past=False):
    # Return sample busy events for testing
    return [
        {
            "start": {"dateTime": "2025-04-29T10:00:00"},
            "end": {"dateTime": "2025-04-29T11:00:00"},
        },
        {
            "start": {"dateTime": "2025-04-29T13:00:00"},
            "end": {"dateTime": "2025-04-29T14:00:00"},
        }
    ]

# ✅ MOCK: replace with real blocked time logic if needed
def is_time_blocked(dt):
    # Block nothing for testing
    return False

def is_time_blocked_orig(check_time: datetime) -> bool:
    weekday = check_time.weekday()
    t = check_time.time()

    if weekday >= 5:  # Saturday=5, Sunday=6
        return blocked_times["weekends"] == "all"

    for start, end in blocked_times["weekdays"]:
        if start <= t <= end:
            return True
    return False

def suggest_time_slots_testable():
    # 🔧 Static test input
    state = {}  # Not used in this version
    action_input = {
        "start_time": "2025-04-27T00:00:00",
        "end_time": "2025-05-04T00:00:00"
    }
    slot_duration_minutes = 60

    start_time_str = action_input.get("start_time")
    end_time_str = action_input.get("end_time")

    if not start_time_str or not end_time_str:
        return {
            "success": False,
            "info": "Start time and end time are required to suggest time slots."
        }

    start_time = datetime.fromisoformat(start_time_str)
    end_time = datetime.fromisoformat(end_time_str)

    events = list_events(
        time_min=start_time_str, 
        time_max=end_time_str, 
        max_results=100,
        include_past=False
    )

    busy_times = []
    for event in events:
        event_start = event.get('start', {}).get('dateTime')
        event_end = event.get('end', {}).get('dateTime')
        if event_start and event_end:
            busy_times.append((
                datetime.fromisoformat(event_start),
                datetime.fromisoformat(event_end)
            ))

    busy_times.sort(key=lambda x: x[0])

    suggestions = []
    current_time = start_time

    while current_time + timedelta(minutes=slot_duration_minutes) <= end_time:
        slot_end_time = current_time + timedelta(minutes=slot_duration_minutes)

        overlapping = any(
            not (slot_end_time <= busy_start or current_time >= busy_end)
            for busy_start, busy_end in busy_times
        )

        blocked = is_time_blocked_orig(current_time)

        if not overlapping and not blocked:
            suggestions.append(f"{current_time.strftime('%Y-%m-%d %H:%M')} to {slot_end_time.strftime('%H:%M')}")

        current_time += timedelta(minutes=slot_duration_minutes)

    if not suggestions:
        info = "No available time slots found."
    else:
        info = "Here are some available time slots:\n" + "\n".join(suggestions)

    return {
        "success": True,
        "info": info
    }

def is_time_slot_available(start_time_str: str, end_time_str: str) -> bool:
    start_time = datetime.fromisoformat(start_time_str)
    end_time = datetime.fromisoformat(end_time_str)

    if start_time > end_time:
        return False

    # 1. Check if time is blocked
    current = start_time
    while current < end_time:
        if is_time_blocked_orig(current):
            return False
        current += timedelta(minutes=1)

    # 2. Check for overlap with busy events
    events = list_events(
        time_min=start_time_str,
        time_max=end_time_str,
        max_results=100,
        include_past=False
    )

    for event in events:
        event_start = datetime.fromisoformat(event['start']['dateTime'])
        event_end = datetime.fromisoformat(event['end']['dateTime'])

        # Check if the input time overlaps with any busy event
        if not (end_time <= event_start or start_time >= event_end):
            return False

    return True

# Run test
#if __name__ == "__main__":
#    result = suggest_time_slots_testable()
#    print(result["info"])
    #dtobj = datetime.fromisoformat("2025-05-03T12:00:00")
    #print(is_time_blocked_orig(dtobj))

# 🔧 Test
if __name__ == "__main__":
    tests = [
        ("2025-04-29T09:00:00", "2025-04-29T10:00:00"),  # ✅ free
        ("2025-04-29T10:30:00", "2025-04-29T11:30:00"),  # ❌ overlaps
        ("2025-04-29T12:00:00", "2025-04-29T13:00:00"),  # ✅ free
        ("2025-04-29T23:30:00", "2025-04-29T23:50:00"),
    ]

    for start, end in tests:
        available = is_time_slot_available(start, end)
        print(f"{start} to {end} -> {'Available' if available else 'Unavailable'}")