#!/usr/bin/env python3
"""
KC Lawn Care Notification System

Orchestrates soil temp fetching, trigger evaluation, and notifications.
Features: soil temp projections, mark-as-done via ntfy, heads-up alerts.
"""

import json
import logging
from datetime import date

from lawn_care import (
    load_config,
    load_schedule,
    load_state,
    save_state,
    fetch_soil_temp,
    fetch_air_temp_forecast,
    project_soil_temps,
    get_upcoming_applications,
    update_soil_temp_history,
    format_notification,
    format_ready_notification,
    format_heads_up_notification,
    send_ready_notification,
    send_heads_up_notification,
    poll_done_topic,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def process_done_messages(config: dict, state: dict, schedule: dict, today: date) -> None:
    """Poll ntfy done topic and mark completed apps in state."""
    done_ids = poll_done_topic(config)
    if not done_ids:
        return

    valid_app_ids = {app["id"] for app in schedule.get("applications", [])}
    completed = state.setdefault("completed", {})
    sent_alerts = state.get("sent_alerts", {})
    today_str = today.strftime("%Y-%m-%d")

    for app_id in done_ids:
        if app_id not in valid_app_ids:
            logger.warning(f"Unknown app_id from done topic: {app_id}")
            continue
        if app_id in completed:
            logger.info(f"Already completed: {app_id}")
            continue

        completed[app_id] = today_str
        # Clear sent_alerts entry when app is completed
        if app_id in sent_alerts:
            del sent_alerts[app_id]
        logger.info(f"Marked done: {app_id}")

    save_state(state)


def send_notifications(
    upcoming: list[dict],
    config: dict,
    state: dict,
    soil_temp: float | None,
    projections: list[dict] | None,
    today: date,
) -> None:
    """Send appropriate notifications for ready and heads-up apps."""
    area_sqft = config.get("area_sqft")
    today_str = today.strftime("%Y-%m-%d")
    sent_alerts = state.setdefault("sent_alerts", {})

    ready_apps = [a for a in upcoming if a["ready"]]
    heads_up_apps = [a for a in upcoming if a.get("heads_up")]

    # Send one notification per ready app (each with its own Mark Done button)
    for app in ready_apps:
        message = format_ready_notification(app, soil_temp, area_sqft)
        send_ready_notification(app, message, config)

    # Send a single heads-up notification for all heads-up apps (skip already-alerted)
    new_heads_up = [a for a in heads_up_apps if a["id"] not in sent_alerts]
    if new_heads_up:
        message = format_heads_up_notification(new_heads_up, soil_temp, projections, area_sqft)
        if send_heads_up_notification(message, config):
            for app in new_heads_up:
                sent_alerts[app["id"]] = today_str
            save_state(state)


def main():
    """Main entry point."""
    today = date.today()
    logger.info(f"Lawn care check for {today}")

    # Load configuration and data
    try:
        config = load_config()
        schedule = load_schedule()
        state = load_state()
    except FileNotFoundError as e:
        logger.error(f"Missing required file: {e}")
        return 1
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return 1

    # Poll done topic before evaluating triggers
    process_done_messages(config, state, schedule, today)

    # Fetch soil temperature
    soil_temp = fetch_soil_temp(config)

    # Update state with new reading
    update_soil_temp_history(state, soil_temp, today)
    save_state(state)

    # Build soil temp projections from weather forecast
    projections = None
    if soil_temp is not None:
        air_forecast = fetch_air_temp_forecast(config)
        if air_forecast:
            projections = project_soil_temps(soil_temp, air_forecast)
            if projections:
                logger.info(
                    f"Projected soil temps: today {soil_temp}F -> "
                    f"{projections[-1]['date']} {projections[-1]['projected_soil_temp']}F"
                )

    # Get upcoming applications
    upcoming = get_upcoming_applications(schedule, state, soil_temp, today, projections=projections)

    if not upcoming:
        logger.info("No upcoming applications found")
        return 0

    # Check counts
    ready_apps = [a for a in upcoming if a["ready"]]
    heads_up_apps = [a for a in upcoming if a.get("heads_up")]

    # Format and display full summary to console
    area_sqft = config.get("area_sqft")
    message = format_notification(upcoming, soil_temp, projections, area_sqft)
    print("\n" + message + "\n")

    # Send notifications if anything is actionable
    if ready_apps or heads_up_apps:
        logger.info(f"{len(ready_apps)} ready, {len(heads_up_apps)} heads-up")
        send_notifications(upcoming, config, state, soil_temp, projections, today)
    else:
        logger.info("No applications ready or approaching")

    return 0


if __name__ == "__main__":
    exit(main())
