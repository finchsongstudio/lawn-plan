"""Decision engine for evaluating application triggers."""

from datetime import date, datetime, timedelta
from typing import Any


def parse_date(date_str: str, year: int | None = None) -> date:
    """Parse a date string, handling MM-DD format by adding current year."""
    if year is None:
        year = date.today().year

    if len(date_str) == 5:  # MM-DD format
        return datetime.strptime(f"{year}-{date_str}", "%Y-%m-%d").date()
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def count_consecutive_days_at_temp(
    history: list[dict],
    threshold: float,
    direction: str,
) -> int:
    """
    Count consecutive days where temp meets threshold condition.

    Args:
        history: List of {"date": "YYYY-MM-DD", "temp": float} entries, newest first
        threshold: Temperature threshold in Fahrenheit
        direction: "rising" (temp >= threshold) or "falling" (temp <= threshold)

    Returns:
        Number of consecutive days meeting the condition
    """
    if not history:
        return 0

    count = 0
    for entry in history:
        temp = entry["temp"]
        if direction == "rising" and temp >= threshold:
            count += 1
        elif direction == "falling" and temp <= threshold:
            count += 1
        else:
            break

    return count


def evaluate_trigger(
    app: dict[str, Any],
    state: dict[str, Any],
    soil_temp: float | None,
    today: date,
    all_apps: dict[str, dict],
) -> dict[str, Any]:
    """
    Evaluate if an application's trigger condition is met.

    Returns:
        {
            "ready": bool,
            "projected_date": date | None,
            "reason": str,
            "window_start": date | None,
            "window_end": date | None,
        }
    """
    trigger = app.get("trigger", {})
    trigger_type = trigger.get("type")
    completed = state.get("completed", {})
    history = state.get("soil_temp_history", [])

    result = {
        "ready": False,
        "projected_date": None,
        "reason": "",
        "window_start": None,
        "window_end": None,
    }

    # Already completed
    if app["id"] in completed:
        result["reason"] = f"Completed on {completed[app['id']]}"
        return result

    if trigger_type == "soil_temp":
        result = _evaluate_soil_temp_rising(app, trigger, history, soil_temp, today, result)

    elif trigger_type == "soil_temp_falling":
        result = _evaluate_soil_temp_falling(app, trigger, history, soil_temp, today, result)

    elif trigger_type == "days_after":
        result = _evaluate_days_after(trigger, completed, today, result)

    elif trigger_type == "calendar_window":
        result = _evaluate_calendar_window(trigger, today, result)

    elif trigger_type == "same_as":
        result = _evaluate_same_as(trigger, all_apps, state, soil_temp, today, result)

    else:
        result["reason"] = f"Unknown trigger type: {trigger_type}"

    return result


def _evaluate_soil_temp_rising(
    app: dict,
    trigger: dict,
    history: list,
    soil_temp: float | None,
    today: date,
    result: dict,
) -> dict:
    """Evaluate soil_temp trigger (rising)."""
    threshold = trigger["threshold_f"]
    direction = trigger.get("direction", "rising")
    consecutive_needed = trigger.get("consecutive_days", 1)

    # Set typical window if available (for sorting)
    if "kc_typical_window" in app:
        result["window_start"] = parse_date(app["kc_typical_window"]["start"])
        result["window_end"] = parse_date(app["kc_typical_window"]["end"])

    if soil_temp is None:
        result["reason"] = "Waiting for soil temp data"
        return result

    consecutive = count_consecutive_days_at_temp(history, threshold, direction)

    if consecutive >= consecutive_needed:
        result["ready"] = True
        result["projected_date"] = today
        result["reason"] = f"Soil temp {soil_temp}°F (>={threshold}°F for {consecutive} days)"
    else:
        result["reason"] = (
            f"Soil temp {soil_temp}°F, need {consecutive_needed} consecutive days "
            f"at {'>=' if direction == 'rising' else '<='}{threshold}°F (currently {consecutive})"
        )

    return result


def _evaluate_soil_temp_falling(
    app: dict,
    trigger: dict,
    history: list,
    soil_temp: float | None,
    today: date,
    result: dict,
) -> dict:
    """Evaluate soil_temp_falling trigger."""
    threshold = trigger["threshold_f"]
    consecutive_needed = trigger.get("consecutive_days", 1)

    # Fall triggers shouldn't fire before August
    if today.month < 8:
        result["reason"] = "Fall application - waiting for fall season"
        if "kc_typical_window" in app:
            result["window_start"] = parse_date(app["kc_typical_window"]["start"])
            result["window_end"] = parse_date(app["kc_typical_window"]["end"])
        return result

    if soil_temp is None:
        result["reason"] = "Waiting for soil temp data"
        return result

    consecutive = count_consecutive_days_at_temp(history, threshold, "falling")

    if consecutive >= consecutive_needed:
        result["ready"] = True
        result["projected_date"] = today
        result["reason"] = f"Soil temp {soil_temp}°F (<={threshold}°F for {consecutive} days)"
    else:
        result["reason"] = (
            f"Soil temp {soil_temp}°F, need {consecutive_needed} consecutive days "
            f"<={threshold}°F (currently {consecutive})"
        )

    if "kc_typical_window" in app:
        result["window_start"] = parse_date(app["kc_typical_window"]["start"])
        result["window_end"] = parse_date(app["kc_typical_window"]["end"])

    return result


def _evaluate_days_after(
    trigger: dict,
    completed: dict,
    today: date,
    result: dict,
) -> dict:
    """Evaluate days_after trigger."""
    ref_id = trigger["reference_id"]
    days_min = trigger["days_min"]
    days_max = trigger["days_max"]

    if ref_id not in completed:
        result["reason"] = f"Waiting on {ref_id} to complete"
        return result

    ref_date = datetime.strptime(completed[ref_id], "%Y-%m-%d").date()
    window_start = ref_date + timedelta(days=days_min)
    window_end = ref_date + timedelta(days=days_max)

    result["window_start"] = window_start
    result["window_end"] = window_end

    if window_start <= today <= window_end:
        result["ready"] = True
        result["projected_date"] = today
        result["reason"] = f"In window ({days_min}-{days_max} days after {ref_id})"
    elif today < window_start:
        result["projected_date"] = window_start
        days_until = (window_start - today).days
        result["reason"] = f"Window opens in {days_until} days ({window_start})"
    else:
        result["reason"] = f"Window closed on {window_end}"

    return result


def _evaluate_calendar_window(
    trigger: dict,
    today: date,
    result: dict,
) -> dict:
    """Evaluate calendar_window trigger."""
    window_start = parse_date(trigger["window_start"])
    window_end = parse_date(trigger["window_end"])

    result["window_start"] = window_start
    result["window_end"] = window_end

    if window_start <= today <= window_end:
        result["ready"] = True
        result["projected_date"] = today
        result["reason"] = f"In calendar window ({window_start} to {window_end})"
    elif today < window_start:
        result["projected_date"] = window_start
        days_until = (window_start - today).days
        result["reason"] = f"Window opens in {days_until} days ({window_start})"
    else:
        result["reason"] = f"Window closed on {window_end}"

    return result


def _evaluate_same_as(
    trigger: dict,
    all_apps: dict,
    state: dict,
    soil_temp: float | None,
    today: date,
    result: dict,
) -> dict:
    """Evaluate same_as trigger."""
    ref_id = trigger["reference_id"]

    if ref_id not in all_apps:
        result["reason"] = f"Reference app {ref_id} not found"
        return result

    # Recursively evaluate the reference app
    ref_result = evaluate_trigger(all_apps[ref_id], state, soil_temp, today, all_apps)
    result["ready"] = ref_result["ready"]
    result["projected_date"] = ref_result["projected_date"]
    result["window_start"] = ref_result["window_start"]
    result["window_end"] = ref_result["window_end"]
    result["reason"] = f"Same as {ref_id}: {ref_result['reason']}"

    return result


def get_upcoming_applications(
    schedule: dict[str, Any],
    state: dict[str, Any],
    soil_temp: float | None,
    today: date,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Get list of upcoming applications sorted by readiness and projected date.

    Returns list of dicts with app info and trigger evaluation results.
    """
    applications = schedule.get("applications", [])
    completed = state.get("completed", {})

    # Build lookup dict for same_as references
    all_apps = {app["id"]: app for app in applications}

    upcoming = []

    for idx, app in enumerate(applications):
        app_id = app["id"]

        # Skip completed applications
        if app_id in completed:
            continue

        # Evaluate trigger
        trigger_result = evaluate_trigger(app, state, soil_temp, today, all_apps)

        # Build result entry
        entry = {
            "id": app_id,
            "name": app["name"],
            "category": app.get("category", "unknown"),
            "month_target": app.get("month_target", ""),
            "products": app.get("products", []),
            "warnings": app.get("warnings", []),
            "optional": app.get("optional", False),
            "schedule_order": idx,
            **trigger_result,
        }

        upcoming.append(entry)

    # Sort by: ready first, then by projected date/window, then by schedule order
    def sort_key(x):
        ready_sort = 0 if x["ready"] else 1
        proj_date = x["projected_date"] or x["window_start"] or date(9999, 12, 31)
        return (ready_sort, proj_date, x["schedule_order"])

    upcoming.sort(key=sort_key)

    return upcoming[:limit]


def update_soil_temp_history(
    state: dict[str, Any],
    soil_temp: float | None,
    today: date,
) -> None:
    """Update soil temperature history in state."""
    if soil_temp is None:
        return

    history = state.get("soil_temp_history", [])
    today_str = today.strftime("%Y-%m-%d")

    # Check if we already have an entry for today
    if history and history[0].get("date") == today_str:
        history[0]["temp"] = soil_temp
    else:
        history.insert(0, {"date": today_str, "temp": soil_temp})

    # Keep only last 14 days of history
    state["soil_temp_history"] = history[:14]
    state["last_soil_temp_f"] = soil_temp
    state["last_check"] = today_str
